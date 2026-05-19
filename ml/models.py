"""
MLAnalysisResult — structured output of the HF ML analysis pipeline.

Returned by MLPipeline.analyze() and stored on IncidentRecord.ml_result.
Also serialised to JSON for the get_hf_analysis agent tool.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional


@dataclass
class MLAnalysisResult:
    # ── Identity ────────────────────────────────────────────────────────
    asset_id:         str
    asset_type:       str
    analyzed_at:      datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    window_duration_s: float = 0.0
    sample_count:     int   = 0

    # ── Anomaly Detection (Isolation Forest) ────────────────────────────
    anomaly_score:    float = 0.0     # 0.0 (normal) → 1.0 (anomaly)
    anomaly_detected: bool  = False   # score > 0.65

    # ── Fault Classification (rule-based probabilistic) ──────────────────
    fault_class:       str   = "normal"   # bearing_wear / cavitation / etc
    fault_probability: float = 0.0        # 0.0 – 1.0
    fault_candidates:  list  = field(default_factory=list)  # [{class, prob}] top 3

    # ── RUL ─────────────────────────────────────────────────────────────
    rul_days:         float  = 0.0
    rul_confidence:   str    = "low"   # high / medium / low
    rul_trend_slope:  float  = 0.0    # health decay rate per hour (negative = degrading)

    # ── Key Features (for UI display) ───────────────────────────────────
    vibration_rms_hf:       float = 0.0
    dominant_frequency_hz:  float = 0.0
    kurtosis:               float = 0.0
    crest_factor:           float = 0.0
    spectral_centroid_hz:   float = 0.0
    bearing_temp_delta:     float = 0.0   # °C rise over window

    # ── Full feature dict (for UI expander) ─────────────────────────────
    feature_detail: dict = field(default_factory=dict)

    # ── Human-readable narrative (fed to Claude as context) ─────────────
    narrative: str = ""

    # ── Error flag (set when pipeline cannot run) ────────────────────────
    error: Optional[str] = None

    def to_agent_dict(self) -> dict:
        """Serialise to dict for the get_hf_analysis tool response."""
        return {
            "asset_id":              self.asset_id,
            "asset_type":            self.asset_type,
            "analyzed_at":           self.analyzed_at.isoformat(),
            "window_duration_s":     self.window_duration_s,
            "sample_count":          self.sample_count,
            "anomaly_score":         round(self.anomaly_score, 3),
            "anomaly_detected":      self.anomaly_detected,
            "fault_class":           self.fault_class,
            "fault_probability":     round(self.fault_probability, 3),
            "fault_candidates":      self.fault_candidates,
            "rul_days":              round(self.rul_days, 1),
            "rul_confidence":        self.rul_confidence,
            "rul_trend_slope_per_hr": round(self.rul_trend_slope, 4),
            "vibration_rms_hf_mms":  round(self.vibration_rms_hf, 3),
            "dominant_frequency_hz": round(self.dominant_frequency_hz, 1),
            "kurtosis":              round(self.kurtosis, 2),
            "crest_factor":          round(self.crest_factor, 2),
            "spectral_centroid_hz":  round(self.spectral_centroid_hz, 1),
            "bearing_temp_delta_c":  round(self.bearing_temp_delta, 2),
            "narrative":             self.narrative,
            "error":                 self.error,
        }
