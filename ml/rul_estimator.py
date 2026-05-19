"""
RULEstimator — Remaining Useful Life from HF vibration trend.

Method:
  1. Build a health proxy series from the vibration RMS in the HF window.
     health_proxy = 1 - clip(rms / VIB_ALARM_THRESHOLD, 0, 1)
  2. Fit linear regression on the last N points of the health proxy.
  3. Project time to health_proxy = 0.0 (failure).
  4. Take the conservative minimum of HF-RUL and CEP-RUL.

Confidence based on R²:
  R² > 0.85 → high
  R² > 0.60 → medium
  else      → low
"""
from __future__ import annotations

import math
import numpy as np
from scipy import stats as sp_stats
from loguru import logger


# Vibration threshold above which health proxy = 0 (failure)
VIB_ALARM_THRESHOLD = 7.1   # mm/s  (ISO 10816-3 Zone D boundary)
HF_RATE = 10   # Hz

# If RUL is extreme or negative, cap at this
MAX_RUL_DAYS = 365.0
MIN_RUL_DAYS = 0.5


class RULEstimator:

    def estimate(
        self,
        features:   dict,
        df_vib:     "np.ndarray | None" = None,   # raw vibration series from HF window
        cep_health: float | None = None,
        cep_rul:    float | None = None,
    ) -> tuple[float, str, float]:
        """
        Estimate RUL.

        Parameters
        ----------
        features   : dict from FeatureExtractor (used for current RMS)
        df_vib     : optional raw vibration ndarray for trend fitting
        cep_health : optional CEP health score (0–100)
        cep_rul    : optional CEP RUL in days

        Returns
        -------
        (rul_days, confidence, trend_slope_per_hour)
        """
        rms_current = features.get("rms", 0.8)
        trend_slope = features.get("vib_trend_slope", 0.0)   # mm/s per hour

        # ── RUL from trend ─────────────────────────────────────────────
        hf_rul   = MAX_RUL_DAYS
        r2       = 0.0

        if df_vib is not None and len(df_vib) >= 20:
            hf_rul, r2 = self._rul_from_series(df_vib, rms_current)
        elif abs(trend_slope) > 1e-6:
            # Fall back: use feature slope directly
            health_proxy = max(0.0, 1.0 - rms_current / VIB_ALARM_THRESHOLD)
            rate_per_hour = abs(trend_slope) / VIB_ALARM_THRESHOLD
            if rate_per_hour > 1e-9:
                rul_hours = health_proxy / rate_per_hour
                hf_rul = min(MAX_RUL_DAYS, max(MIN_RUL_DAYS, rul_hours / 24.0))
            r2 = 0.4   # medium confidence for slope-only method

        # ── Blend with CEP RUL (take conservative / minimum) ──────────
        if cep_rul is not None and cep_rul > 0:
            final_rul = min(hf_rul, cep_rul)
            if cep_rul < hf_rul:
                logger.debug(f"[RULEstimator] CEP RUL {cep_rul:.1f}d < HF RUL {hf_rul:.1f}d — using CEP")
        else:
            final_rul = hf_rul

        final_rul = max(MIN_RUL_DAYS, min(MAX_RUL_DAYS, final_rul))
        confidence = self._confidence_from_r2(r2, cep_rul)

        logger.debug(
            f"[RULEstimator] hf_rul={hf_rul:.1f}d cep_rul={cep_rul} "
            f"final={final_rul:.1f}d conf={confidence} R²={r2:.3f}"
        )

        return round(final_rul, 1), confidence, round(trend_slope, 4)

    # ── Trend fitting ──────────────────────────────────────────────────────

    def _rul_from_series(self, vib_series: np.ndarray, rms_current: float) -> tuple[float, float]:
        """
        Fit linear regression on health proxy series, project to failure.
        Returns (rul_days, r2).
        """
        # Use last 60 s worth of points at 10 Hz = 600 points (or all if shorter)
        n_fit = min(600, len(vib_series))
        series = vib_series[-n_fit:]

        # Build health proxy (1 = healthy, 0 = failure)
        health_proxy = np.clip(1.0 - series / VIB_ALARM_THRESHOLD, 0.0, 1.0)

        n = len(health_proxy)
        t = np.arange(n) / HF_RATE / 3600.0   # hours

        try:
            slope, intercept, r_value, _, _ = sp_stats.linregress(t, health_proxy)
            r2 = r_value ** 2
        except Exception:
            return MAX_RUL_DAYS, 0.0

        # If not degrading, return max RUL
        if slope >= -1e-9:
            return MAX_RUL_DAYS, r2

        # Current health proxy value at t=0 (intercept at the last point)
        hp_now = health_proxy[-1]
        if hp_now <= 0.0:
            return MIN_RUL_DAYS, r2

        # Time to health_proxy = 0 (failure)
        rul_hours = hp_now / abs(slope)
        rul_days  = rul_hours / 24.0

        return round(max(MIN_RUL_DAYS, min(MAX_RUL_DAYS, rul_days)), 1), round(r2, 3)

    @staticmethod
    def _confidence_from_r2(r2: float, cep_rul: float | None) -> str:
        """Map R² + CEP agreement to confidence level."""
        if cep_rul is not None and r2 > 0.85:
            return "high"
        if r2 > 0.85:
            return "high"
        if r2 > 0.60:
            return "medium"
        return "low"
