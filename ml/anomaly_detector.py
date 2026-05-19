"""
AnomalyDetector — Isolation Forest wrapper.

One model is fitted per asset_id using the first 60 seconds of healthy
baseline data after app start.  If insufficient real data is available,
a synthetic baseline is generated from nominal healthy parameters.

Anomaly score is mapped 0.0 (normal) → 1.0 (anomaly).
  score > 0.65 → anomaly_detected = True

Feature vector (10 features):
  rms, kurtosis, crest_factor, dominant_frequency_hz,
  spectral_centroid_hz, sub_sync_power, 2x_sync_power,
  high_freq_power, temp_delta, vib_trend_slope
"""
from __future__ import annotations

import numpy as np
from sklearn.ensemble import IsolationForest
from loguru import logger


ANOMALY_THRESHOLD = 0.65

# Feature names used to build the vector (must match FeatureExtractor output keys)
FEATURE_KEYS = [
    "rms",
    "kurtosis",
    "crest_factor",
    "dominant_frequency_hz",
    "spectral_centroid_hz",
    "sub_sync_power",
    "2x_sync_power",
    "high_freq_power",
    "temp_delta",
    "vib_trend_slope",
]


class AnomalyDetector:

    def __init__(self):
        self._models:     dict[str, IsolationForest] = {}
        self._is_fitted:  dict[str, bool]            = {}

    # ── Fit ──────────────────────────────────────────────────────────────

    def fit(self, asset_id: str, feature_list: list[dict]) -> None:
        """
        Fit an IsolationForest on a list of feature dicts (healthy baseline).
        Each dict is the output of FeatureExtractor.extract().
        Minimum 5 feature sets required.
        """
        if len(feature_list) < 5:
            logger.warning(f"[AnomalyDetector] {asset_id}: insufficient baseline samples "
                           f"({len(feature_list)} < 5) — using synthetic baseline")
            self._fit_synthetic(asset_id)
            return

        X = self._build_feature_matrix(feature_list)
        model = IsolationForest(
            n_estimators=100,
            contamination=0.1,
            random_state=42,
            n_jobs=1,
        )
        model.fit(X)
        self._models[asset_id]    = model
        self._is_fitted[asset_id] = True
        logger.info(f"[AnomalyDetector] {asset_id}: fitted on {len(feature_list)} samples")

    def fit_synthetic(self, asset_id: str) -> None:
        """Public entry point to force a synthetic fit."""
        self._fit_synthetic(asset_id)

    def _fit_synthetic(self, asset_id: str) -> None:
        """Generate synthetic healthy baseline and fit."""
        rng = np.random.default_rng(42)
        # Simulate 200 samples of healthy machinery features
        n = 200
        X = np.column_stack([
            rng.normal(0.8, 0.1, n),      # rms
            rng.normal(3.0, 0.3, n),      # kurtosis (healthy ≈ 3)
            rng.normal(2.5, 0.3, n),      # crest_factor
            rng.normal(20.0, 2.0, n),     # dominant_frequency_hz
            rng.normal(18.0, 2.0, n),     # spectral_centroid_hz
            rng.normal(0.05, 0.02, n),    # sub_sync_power
            rng.normal(0.05, 0.02, n),    # 2x_sync_power
            rng.normal(0.05, 0.02, n),    # high_freq_power
            rng.normal(0.0,  0.5, n),     # temp_delta
            rng.normal(0.0,  0.1, n),     # vib_trend_slope
        ])
        model = IsolationForest(n_estimators=100, contamination=0.1, random_state=42, n_jobs=1)
        model.fit(X)
        self._models[asset_id]    = model
        self._is_fitted[asset_id] = True
        logger.info(f"[AnomalyDetector] {asset_id}: fitted on synthetic baseline")

    # ── Score ─────────────────────────────────────────────────────────────

    def score(self, asset_id: str, features: dict) -> float:
        """
        Return anomaly score 0.0–1.0 for a feature dict.
        0.0 = perfectly normal, 1.0 = extreme anomaly.
        Auto-fits synthetic baseline if model not yet fitted.
        """
        if asset_id not in self._is_fitted or not self._is_fitted[asset_id]:
            self._fit_synthetic(asset_id)

        model = self._models[asset_id]
        x = self._build_feature_vector(features).reshape(1, -1)

        # IsolationForest.decision_function: positive = normal, negative = anomaly
        # Map to [0, 1]: score = -decision_function, clipped and normalized
        raw = float(model.decision_function(x)[0])
        # Typical range: [-0.5, 0.5]
        # Map: 0.5 → 0.0 (normal), -0.5 → 1.0 (anomaly)
        anomaly_score = max(0.0, min(1.0, (0.5 - raw)))
        return anomaly_score

    def is_anomaly(self, score: float) -> bool:
        return score > ANOMALY_THRESHOLD

    def is_fitted(self, asset_id: str) -> bool:
        return self._is_fitted.get(asset_id, False)

    # ── Feature vector helpers ─────────────────────────────────────────────

    def _build_feature_vector(self, features: dict) -> np.ndarray:
        return np.array([
            float(features.get(k, 0.0)) for k in FEATURE_KEYS
        ], dtype=float)

    def _build_feature_matrix(self, feature_list: list[dict]) -> np.ndarray:
        return np.array([
            [float(f.get(k, 0.0)) for k in FEATURE_KEYS]
            for f in feature_list
        ], dtype=float)
