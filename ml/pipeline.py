"""
MLPipeline — orchestrator for the HF data analysis pipeline.

Instantiated once at app startup (module-level singleton).
Requires an HFStore instance.

Usage:
    from ml.pipeline import ml_pipeline
    result = ml_pipeline.analyze("PUMP-001", "Pump")

Flow:
    1. Fetch HF window from HFStore (alarm snapshot if available, else rolling)
    2. FeatureExtractor.extract(df, asset_type)
    3. AnomalyDetector.score(asset_id, features)
    4. FaultClassifier.classify(features, asset_type)
    5. RULEstimator.estimate(features, vib_series, cep_health, cep_rul)
    6. Build MLAnalysisResult + narrative
    7. Store result; return to caller
"""
from __future__ import annotations

import threading
import time
from datetime import datetime, timezone
from typing import Optional

import numpy as np
from loguru import logger

from storage.hf_store import HFStore, HF_RATE
from ml.models          import MLAnalysisResult
from ml.feature_extractor import FeatureExtractor, _PRIMARY_VIB_TAG
from ml.anomaly_detector  import AnomalyDetector
from ml.fault_classifier  import FaultClassifier
from ml.rul_estimator     import RULEstimator


class MLPipeline:

    def __init__(self, hf_store: HFStore):
        self.hf_store          = hf_store
        self.extractor         = FeatureExtractor()
        self.anomaly_detector  = AnomalyDetector()
        self.fault_classifier  = FaultClassifier()
        self.rul_estimator     = RULEstimator()

        self._result_store: dict[str, MLAnalysisResult] = {}
        self._lock              = threading.Lock()
        self._baseline_fitted:  dict[str, bool] = {}
        self._baseline_samples: dict[str, list[dict]] = {}  # collect during baseline phase

    # ── Baseline management ───────────────────────────────────────────────

    @property
    def baselines_fitted(self) -> bool:
        return len(self._baseline_fitted) > 0

    def accumulate_baseline(self, asset_id: str, asset_type: str, df) -> None:
        """
        Called during the first 60s of operation to build healthy baseline.
        df is a small window (e.g. 5s) of HF data.
        """
        if self._baseline_fitted.get(asset_id):
            return
        if df is None or len(df) == 0:
            return
        features = self.extractor.extract(df, asset_type)
        with self._lock:
            if asset_id not in self._baseline_samples:
                self._baseline_samples[asset_id] = []
            self._baseline_samples[asset_id].append(features)

    def try_fit_baselines(self, asset_registry: dict[str, str]) -> None:
        """
        Attempt to fit anomaly detector models for all assets.
        asset_registry: {asset_id: asset_type}
        Called periodically from the HF sim loop.
        """
        for asset_id, asset_type in asset_registry.items():
            if self._baseline_fitted.get(asset_id):
                continue
            with self._lock:
                samples = self._baseline_samples.get(asset_id, [])
            if len(samples) >= 5:
                self.anomaly_detector.fit(asset_id, samples)
                self._baseline_fitted[asset_id] = True
                logger.info(f"[MLPipeline] Baseline fitted for {asset_id} "
                            f"({len(samples)} feature samples)")
            else:
                # Force synthetic fit so we're never unfit
                self.anomaly_detector.fit_synthetic(asset_id)
                self._baseline_fitted[asset_id] = True
                logger.info(f"[MLPipeline] Synthetic baseline fitted for {asset_id}")

    def ensure_fitted(self, asset_id: str) -> None:
        """Guarantee anomaly detector is fitted before first use."""
        if not self._baseline_fitted.get(asset_id):
            self.anomaly_detector.fit_synthetic(asset_id)
            self._baseline_fitted[asset_id] = True

    # ── Main analysis entry point ─────────────────────────────────────────

    def analyze(
        self,
        asset_id:    str,
        asset_type:  str,
        duration_s:  float = 120.0,
        cep_health:  Optional[float] = None,
        cep_rul:     Optional[float] = None,
    ) -> MLAnalysisResult:
        """
        Run the full ML analysis pipeline on the HF data for one asset.

        Prefers alarm snapshot (frozen at alarm time); falls back to
        rolling window if no snapshot exists.

        Returns MLAnalysisResult.
        """
        t0 = time.monotonic()
        logger.info(f"[MLPipeline] Starting analysis for {asset_id} ({asset_type})")

        # ── 1. Get HF data ────────────────────────────────────────────
        df = self.hf_store.get_alarm_snapshot(asset_id)
        used_snapshot = df is not None
        if df is None:
            df = self.hf_store.get_window(asset_id, duration_s=duration_s)
        if df is None or len(df) == 0:
            logger.warning(f"[MLPipeline] No HF data for {asset_id} — returning stub result")
            result = MLAnalysisResult(
                asset_id=asset_id, asset_type=asset_type,
                error="No HF data available for this asset"
            )
            result.narrative = self._build_narrative(result)
            self._store_result(asset_id, result)
            return result

        sample_count = len(df)
        actual_duration_s = sample_count / HF_RATE

        # ── 2. Feature extraction ─────────────────────────────────────
        try:
            features = self.extractor.extract(df, asset_type)
        except Exception as e:
            logger.error(f"[MLPipeline] Feature extraction failed for {asset_id}: {e}")
            result = MLAnalysisResult(
                asset_id=asset_id, asset_type=asset_type,
                error=f"Feature extraction error: {e}"
            )
            result.narrative = self._build_narrative(result)
            self._store_result(asset_id, result)
            return result

        # ── 3. Anomaly detection ──────────────────────────────────────
        self.ensure_fitted(asset_id)
        try:
            anomaly_score = self.anomaly_detector.score(asset_id, features)
            anomaly_detected = self.anomaly_detector.is_anomaly(anomaly_score)
        except Exception as e:
            logger.error(f"[MLPipeline] Anomaly detection failed for {asset_id}: {e}")
            anomaly_score    = 0.0
            anomaly_detected = False

        # ── 4. Fault classification ───────────────────────────────────
        try:
            fault_class, fault_prob, candidates = self.fault_classifier.classify(
                features, asset_type
            )
        except Exception as e:
            logger.error(f"[MLPipeline] Fault classification failed for {asset_id}: {e}")
            fault_class  = "normal"
            fault_prob   = 0.5
            candidates   = [{"class": "normal", "probability": 0.5}]

        # ── 5. RUL estimation ─────────────────────────────────────────
        # Extract primary vibration series for trend fitting
        vib_tag = _PRIMARY_VIB_TAG.get(asset_type, "vib_x_hf")
        vib_cols = [c for c in df.columns if "vib" in c.lower()]
        vib_series = None
        if vib_tag in df.columns:
            vib_series = df[vib_tag].dropna().values.astype(float)
        elif vib_cols:
            vib_series = df[vib_cols[0]].dropna().values.astype(float)

        try:
            rul_days, rul_conf, trend_slope = self.rul_estimator.estimate(
                features,
                df_vib=vib_series,
                cep_health=cep_health,
                cep_rul=cep_rul,
            )
        except Exception as e:
            logger.error(f"[MLPipeline] RUL estimation failed for {asset_id}: {e}")
            rul_days    = 30.0
            rul_conf    = "low"
            trend_slope = 0.0

        # ── 6. Bearing temperature delta ─────────────────────────────
        temp_delta = features.get("temp_delta", 0.0)

        # ── 7. Build result ───────────────────────────────────────────
        result = MLAnalysisResult(
            asset_id            = asset_id,
            asset_type          = asset_type,
            analyzed_at         = datetime.now(timezone.utc),
            window_duration_s   = round(actual_duration_s, 1),
            sample_count        = sample_count,
            anomaly_score       = round(anomaly_score, 3),
            anomaly_detected    = anomaly_detected,
            fault_class         = fault_class,
            fault_probability   = fault_prob,
            fault_candidates    = candidates,
            rul_days            = rul_days,
            rul_confidence      = rul_conf,
            rul_trend_slope     = trend_slope,
            vibration_rms_hf    = round(features.get("rms", 0.0), 3),
            dominant_frequency_hz = round(features.get("dominant_frequency_hz", 0.0), 1),
            kurtosis            = round(features.get("kurtosis", 3.0), 2),
            crest_factor        = round(features.get("crest_factor", 2.5), 2),
            spectral_centroid_hz = round(features.get("spectral_centroid_hz", 0.0), 1),
            bearing_temp_delta  = round(temp_delta, 2),
            feature_detail      = {k: round(v, 4) if isinstance(v, float) else v
                                   for k, v in features.items()
                                   if not k.startswith("_")},
        )
        result.narrative = self._build_narrative(result)

        elapsed = round(time.monotonic() - t0, 2)
        src = "alarm snapshot" if used_snapshot else "rolling window"
        logger.info(
            f"[MLPipeline] {asset_id} done in {elapsed}s — "
            f"{fault_class} p={fault_prob:.2f} anomaly={anomaly_score:.2f} "
            f"RUL={rul_days}d ({src})"
        )

        self._store_result(asset_id, result)
        return result

    # ── Storage ────────────────────────────────────────────────────────────

    def _store_result(self, asset_id: str, result: MLAnalysisResult) -> None:
        with self._lock:
            self._result_store[asset_id] = result

    def get_latest(self, asset_id: str) -> Optional[MLAnalysisResult]:
        with self._lock:
            return self._result_store.get(asset_id)

    # ── Narrative builder ──────────────────────────────────────────────────

    @staticmethod
    def _build_narrative(result: MLAnalysisResult) -> str:
        if result.error:
            return f"⚠️ ML analysis could not complete: {result.error}"

        lines = [
            f"**HF ML Analysis — {result.asset_id} ({result.asset_type})**",
            f"Window: {result.window_duration_s:.0f}s · {result.sample_count} samples @ 10 Hz",
            "",
        ]

        # Anomaly block
        anom_icon = "🔴" if result.anomaly_detected else "🟢"
        lines.append(
            f"{anom_icon} **Anomaly Detection**: score={result.anomaly_score:.2f} "
            f"({'ANOMALY DETECTED' if result.anomaly_detected else 'Normal range'})"
        )

        # Fault classification block
        lines.append(
            f"🔧 **Fault Classification**: {result.fault_class.replace('_', ' ').title()} "
            f"(p={result.fault_probability:.2f})"
        )
        if result.fault_candidates:
            cands = ", ".join(
                f"{c['class'].replace('_',' ')} p={c['probability']:.2f}"
                for c in result.fault_candidates[:3]
            )
            lines.append(f"   Candidates: {cands}")

        lines.append("")

        # Key features
        lines.append("**Signal Features:**")
        lines.append(f"- Vibration RMS: {result.vibration_rms_hf:.2f} mm/s")
        lines.append(f"- Kurtosis: {result.kurtosis:.1f} "
                     f"({'⚠ bearing defect indicator' if result.kurtosis > 4 else 'normal range'})")
        lines.append(f"- Crest Factor: {result.crest_factor:.1f} "
                     f"({'⚠ impulsive signal' if result.crest_factor > 6 else 'normal'})")
        lines.append(f"- Dominant Frequency: {result.dominant_frequency_hz:.1f} Hz")
        lines.append(f"- Bearing Temp Delta: +{result.bearing_temp_delta:.1f}°C over window")

        # RUL block
        lines.append("")
        conf_icon = {"high": "🟢", "medium": "🟡", "low": "🔴"}.get(result.rul_confidence, "⚪")
        lines.append(
            f"{conf_icon} **RUL Estimate**: {result.rul_days:.1f} days "
            f"(confidence: {result.rul_confidence})"
        )
        if result.rul_trend_slope < 0:
            lines.append(
                f"   Vibration degradation rate: {abs(result.rul_trend_slope):.3f} mm/s per hour"
            )

        # Interpretation
        lines.append("")
        lines.append("**Interpretation for Chief Engineer:**")
        if result.fault_class == "bearing_wear":
            lines.append(
                f"Kurtosis of {result.kurtosis:.1f} (threshold >4 per ISO 13373-3) combined with "
                f"crest factor {result.crest_factor:.1f} and elevated high-frequency spectral power "
                f"are consistent with bearing race spalling or rolling element defects. "
                f"Dominant frequency {result.dominant_frequency_hz:.0f} Hz should be cross-referenced "
                f"against BPFI/BPFO for rated shaft speed."
            )
        elif result.fault_class == "cavitation":
            lines.append(
                f"Broadband vibration elevation with relatively low kurtosis ({result.kurtosis:.1f}) "
                f"is consistent with cavitation (random bubble collapse signature). "
                f"Sub-sync and 2× harmonic power elevated. Check suction pressure and NPSH margin."
            )
        elif result.fault_class == "imbalance":
            lines.append(
                f"Dominant synchronous (1×) spectral component with moderate kurtosis ({result.kurtosis:.1f}) "
                f"indicates mass imbalance. Consider balancing at next port call."
            )
        elif result.fault_class == "misalignment":
            lines.append(
                f"Elevated 2× harmonic and high axial-to-radial vibration ratio "
                f"indicate coupling or shaft misalignment. "
                f"Re-alignment recommended at next port call (require laser alignment tool)."
            )
        elif result.fault_class == "looseness":
            lines.append(
                f"Sub-synchronous spectral power elevated. Asymmetric vibration waveform. "
                f"Consistent with mechanical looseness (fasteners, bearing housing, baseplate)."
            )
        elif result.fault_class == "fouling":
            lines.append(
                f"Temperature delta of +{result.bearing_temp_delta:.1f}°C with moderate vibration "
                f"suggests fouling reducing heat transfer or flow efficiency. "
                f"Inspect filter, strainer, and cooler surfaces."
            )
        elif result.fault_class == "seal_leak":
            lines.append(
                f"Pressure fluctuation detected with otherwise normal vibration pattern. "
                f"Inspect mechanical seal and gland packing."
            )
        else:
            lines.append("No significant fault pattern detected. Continue monitoring.")

        return "\n".join(lines)


# ── Module-level singleton (requires hf_store to be provided at init) ─────────
# Created in app.py: ml_pipeline = MLPipeline(hf_store)
