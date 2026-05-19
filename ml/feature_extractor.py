"""
FeatureExtractor — statistical + spectral features from HF vibration data.

Input:  pd.DataFrame with HF tag columns, timestamp index
Output: dict of named features used by AnomalyDetector and FaultClassifier

Statistical features (primary vibration signal):
  mean, std, rms, peak_to_peak, kurtosis, skewness,
  crest_factor, shape_factor, impulse_factor

Spectral features (FFT on primary vibration, fs=10 Hz):
  dominant_frequency_hz, spectral_rms, spectral_centroid_hz,
  sub_sync_power, sync_power, 2x_sync_power, high_freq_power

Trend features:
  vib_trend_slope (mm/s per hour), temp_delta (°C), efficiency_slope
"""
from __future__ import annotations

import math
import numpy as np
import pandas as pd
from scipy import stats as sp_stats
from typing import Optional


# Primary vibration tag names by asset type
_PRIMARY_VIB_TAG = {
    "Pump":         "vib_x_hf",
    "Compressor":   "vib_radial_hf",
    "Turbocharger": "vib_radial_hf",
    "Purifier":     "vib_radial_hf",
    "Generator":    "vib_radial_hf",
}

# Bearing temperature tag by asset type
_BEARING_TEMP_TAG = {
    "Pump":         "bearing_temp_hf",
    "Compressor":   "motor_temp_hf",
    "Turbocharger": "bearing_temp_de_hf",
    "Purifier":     "motor_temp_hf",
    "Generator":    "jacket_water_temp_hf",
}

# Nominal running frequency (shaft RPM / 60) per asset type
_NOMINAL_FREQ_HZ = {
    "Pump":         24.0,   # ~1450 RPM
    "Compressor":   16.7,   # ~1000 RPM
    "Turbocharger": 333.3,  # ~20000 RPM (HF sensor still captures sub-harmonics)
    "Purifier":     100.0,  # ~6000 RPM bowl speed
    "Generator":    8.33,   # ~500 RPM diesel engine
}

HF_RATE = 10   # Hz


class FeatureExtractor:

    def extract(self, df: pd.DataFrame, asset_type: str) -> dict:
        """
        Extract all features from a HF data window.

        Parameters
        ----------
        df         : DataFrame — columns are HF tags, index is timestamps
        asset_type : str — used to select correct primary vibration tag

        Returns
        -------
        dict of feature_name → float
        """
        features: dict[str, float] = {}

        # Select primary vibration series
        vib_tag = _PRIMARY_VIB_TAG.get(asset_type, "vib_x_hf")
        vib_tag_actual = _get_first_available(df, [vib_tag,
                                                   "vib_x_hf", "vib_radial_hf",
                                                   "vib_axial_hf", "vib_z_hf"])
        if vib_tag_actual and vib_tag_actual in df.columns:
            vib = df[vib_tag_actual].dropna().values.astype(float)
        else:
            # Fall back to first numeric column
            numeric_cols = df.select_dtypes(include=[np.number]).columns
            vib = df[numeric_cols[0]].dropna().values.astype(float) if len(numeric_cols) > 0 else np.zeros(10)

        # ── Statistical features ──────────────────────────────────────
        stat = self._statistical_features(vib)
        features.update(stat)

        # ── Spectral features ─────────────────────────────────────────
        nominal_freq = _NOMINAL_FREQ_HZ.get(asset_type, 16.7)
        spec = self._spectral_features(vib, fs=HF_RATE, nominal_freq=nominal_freq)
        features.update(spec)

        # ── Bearing temperature delta ─────────────────────────────────
        temp_tag = _BEARING_TEMP_TAG.get(asset_type)
        temp_tag_actual = _get_first_available(df, [temp_tag,
                                                    "bearing_temp_hf", "motor_temp_hf",
                                                    "bearing_temp_de_hf"])
        if temp_tag_actual and temp_tag_actual in df.columns:
            temp_series = df[temp_tag_actual].dropna().values.astype(float)
            if len(temp_series) >= 2:
                features["temp_delta"] = float(temp_series[-1] - temp_series[0])
                features["temp_mean"]  = float(np.mean(temp_series))
                features["temp_max"]   = float(np.max(temp_series))
            else:
                features["temp_delta"] = 0.0
                features["temp_mean"]  = 0.0
                features["temp_max"]   = 0.0
        else:
            features["temp_delta"] = 0.0
            features["temp_mean"]  = 0.0
            features["temp_max"]   = 0.0

        # ── Vibration trend slope (mm/s per hour) ────────────────────
        if len(vib) >= 10:
            n = len(vib)
            t = np.arange(n) / HF_RATE / 3600.0   # hours
            try:
                slope, _, _, _, _ = sp_stats.linregress(t, vib)
                features["vib_trend_slope"] = float(slope)
            except Exception:
                features["vib_trend_slope"] = 0.0
        else:
            features["vib_trend_slope"] = 0.0

        # ── Axial vibration ratio (misalignment indicator) ────────────
        axial_tag = _get_first_available(df, ["vib_axial_hf", "vib_z_hf"])
        if axial_tag and axial_tag in df.columns:
            axial = df[axial_tag].dropna().values.astype(float)
            axial_rms = float(_rms(axial)) if len(axial) > 0 else 0.0
            radial_rms = features.get("rms", 1.0)
            features["axial_radial_ratio"] = (axial_rms / radial_rms) if radial_rms > 1e-6 else 0.0
        else:
            features["axial_radial_ratio"] = 0.0

        # ── Seal/flow indicators (pump/compressor only) ────────────────
        for pressure_tag in ["suction_pressure_hf", "inlet_pressure_hf"]:
            if pressure_tag in df.columns:
                p = df[pressure_tag].dropna().values.astype(float)
                if len(p) >= 2:
                    features["pressure_fluctuation"] = float(np.std(p))
                break
        if "pressure_fluctuation" not in features:
            features["pressure_fluctuation"] = 0.0

        # Add asset type for use in classifier
        features["_asset_type"] = asset_type   # not a float but used by classifier

        return features

    # ── Statistical features ──────────────────────────────────────────────

    @staticmethod
    def _statistical_features(x: np.ndarray) -> dict:
        if len(x) == 0:
            return {k: 0.0 for k in ["mean","std","rms","peak","peak_to_peak",
                                      "kurtosis","skewness","crest_factor",
                                      "shape_factor","impulse_factor"]}
        mean_val  = float(np.mean(x))
        std_val   = float(np.std(x))
        rms_val   = float(_rms(x))
        peak_val  = float(np.max(np.abs(x)))
        ptp_val   = float(np.ptp(x))

        kurt_val  = float(sp_stats.kurtosis(x, fisher=False))   # Pearson (>3 = platykurtic warning)
        skew_val  = float(sp_stats.skew(x))

        crest     = (peak_val / rms_val)   if rms_val > 1e-9 else 0.0
        mean_abs  = float(np.mean(np.abs(x)))
        shape     = (rms_val  / mean_abs)  if mean_abs > 1e-9 else 0.0
        impulse   = (peak_val / mean_abs)  if mean_abs > 1e-9 else 0.0

        return {
            "mean":          mean_val,
            "std":           std_val,
            "rms":           rms_val,
            "peak":          peak_val,
            "peak_to_peak":  ptp_val,
            "kurtosis":      kurt_val,
            "skewness":      skew_val,
            "crest_factor":  crest,
            "shape_factor":  shape,
            "impulse_factor": impulse,
        }

    @staticmethod
    def _spectral_features(x: np.ndarray, fs: float = 10.0,
                            nominal_freq: float = 16.7) -> dict:
        n = len(x)
        if n < 4:
            return {k: 0.0 for k in ["dominant_frequency_hz","spectral_rms",
                                      "spectral_centroid_hz","sub_sync_power",
                                      "sync_power","2x_sync_power","high_freq_power"]}
        # FFT (one-sided)
        fft_vals = np.fft.rfft(x - np.mean(x))   # remove DC
        freqs    = np.fft.rfftfreq(n, d=1.0/fs)
        power    = np.abs(fft_vals) ** 2

        # Dominant frequency
        dom_idx           = int(np.argmax(power[1:]) + 1)  # skip DC
        dominant_freq_hz  = float(freqs[dom_idx])

        # Spectral RMS
        spectral_rms      = float(math.sqrt(np.mean(power)))

        # Spectral centroid
        total_power       = float(np.sum(power))
        if total_power > 1e-12:
            spectral_centroid = float(np.sum(freqs * power) / total_power)
        else:
            spectral_centroid = 0.0

        # Band power ratios (relative to nominal running frequency)
        fn = nominal_freq
        sub_sync  = _band_power(freqs, power, 0.0,       0.4 * fn)
        sync      = _band_power(freqs, power, 0.8 * fn,  1.2 * fn)
        two_x     = _band_power(freqs, power, 1.7 * fn,  2.3 * fn)
        high_freq = _band_power(freqs, power, 3.0 * fn,  fs / 2)

        # Normalise band powers as fraction of total
        tp = total_power if total_power > 1e-12 else 1.0
        return {
            "dominant_frequency_hz": dominant_freq_hz,
            "spectral_rms":          spectral_rms,
            "spectral_centroid_hz":  spectral_centroid,
            "sub_sync_power":        sub_sync / tp,
            "sync_power":            sync / tp,
            "2x_sync_power":         two_x / tp,
            "high_freq_power":       high_freq / tp,
        }


# ── Helpers ───────────────────────────────────────────────────────────────────

def _rms(x: np.ndarray) -> float:
    return float(math.sqrt(np.mean(x ** 2))) if len(x) > 0 else 0.0


def _band_power(freqs: np.ndarray, power: np.ndarray,
                f_low: float, f_high: float) -> float:
    mask = (freqs >= f_low) & (freqs <= f_high)
    return float(np.sum(power[mask])) if np.any(mask) else 0.0


def _get_first_available(df: pd.DataFrame, candidates: list) -> Optional[str]:
    """Return the first candidate column name that exists in df."""
    for c in candidates:
        if c and c in df.columns:
            return c
    return None
