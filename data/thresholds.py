"""
Per-asset, per-metric alarm thresholds.

Each entry: (warning_value, alarm_value, unit, source, direction, tier, compliance_code)
  direction: "above"  → alert when metric > threshold
             "below"  → alert when metric < threshold

  tier: 1 = Monitor only (Warning shown on dashboard, no agent cascade)
        2 = Investigate (Alarm → Watchkeeper + Deep Diagnostics + Maintenance Planner)
        3 = Critical Incident (Alarm on SOLAS/ISM-critical parameter → full 5-agent chain)

  compliance_code: regulatory reference for Tier 3 parameters (e.g. "SOLAS-II-1/28")

Sources: ISO 10816-3, DNV Rules Pt.4 Ch.8, OEM manuals, SOLAS II-1/28.
"""

from dataclasses import dataclass
from typing import Literal, Optional


@dataclass(frozen=True)
class Threshold:
    warning: float
    alarm: float
    unit: str
    source: str
    direction: Literal["above", "below"] = "above"
    tier: int = 2                           # 2=Investigate, 3=Critical/SOLAS
    compliance_code: Optional[str] = None   # e.g. "SOLAS-II-1/28", "ISM-10.1"

    def check(self, value: float) -> str | None:
        """Returns 'Alarm', 'Warning', or None."""
        if self.direction == "above":
            if value >= self.alarm:   return "Alarm"
            if value >= self.warning: return "Warning"
        else:
            if value <= self.alarm:   return "Alarm"
            if value <= self.warning: return "Warning"
        return None


# ── Universal thresholds (all assets) ────────────────────────────────────────

VIBRATION_RMS = Threshold(
    warning=4.5, alarm=7.1, unit="mm/s",
    source="ISO 10816-3 Class III Zone B/C boundary",
    tier=2,
)

HEALTH_SCORE = Threshold(
    warning=70.0, alarm=55.0, unit="%",
    source="Internal health score model",
    direction="below",
    tier=2,
)

# ── PUMP-001 (Lube Oil Pump) ──────────────────────────────────────────────────

PUMP_THRESHOLDS: dict[str, Threshold] = {
    "vibration_rms_mms": VIBRATION_RMS,
    "bearing_temp_c": Threshold(
        warning=65.0, alarm=78.0, unit="°C",
        source="OEM pump manual — rated max bearing temp 80°C",
        tier=2,
    ),
    # Tier 3: lube oil starvation → main engine bearing damage (ISM Code §10.1)
    "pump_efficiency_pct": Threshold(
        warning=80.0, alarm=65.0, unit="%",
        source="OEM pump manual — efficiency < 65% indicates severe wear ring erosion",
        direction="below",
        tier=3,
        compliance_code="ISM-10.1",
    ),
    "overall_health_score": HEALTH_SCORE,
}

# ── COMP-001 (Starting Air Compressor) ───────────────────────────────────────

COMP_THRESHOLDS: dict[str, Threshold] = {
    "vibration_rms_mms": VIBRATION_RMS,
    # Tier 3: SOLAS II-1/28 — cannot start main engine → loss of propulsion
    "volumetric_efficiency_pct": Threshold(
        warning=65.0, alarm=55.0, unit="%",
        source="SOLAS II-1/28 — below 55% compressor cannot charge receivers "
               "within required time; Hamworthy OEM manual",
        direction="below",
        tier=3,
        compliance_code="SOLAS-II-1/28",
    ),
    "overall_health_score": HEALTH_SCORE,
}

# ── TURBO-001 (Turbocharger) ──────────────────────────────────────────────────

TURBO_THRESHOLDS: dict[str, Threshold] = {
    "vibration_rms_mms": VIBRATION_RMS,
    # Tier 3: main engine power loss → maneuvering restriction (ISM Code §10.1)
    "turbo_efficiency_pct": Threshold(
        warning=60.0, alarm=50.0, unit="%",
        source="MAN B&W turbocharger manual — below 60% indicates heavy fouling "
               "or blade damage",
        direction="below",
        tier=3,
        compliance_code="ISM-10.1",
    ),
    # surge_margin_pct is intentionally NOT an alarm threshold — load fluctuations
    # in healthy operation can transiently dip the margin below 10%, causing spurious
    # triggers. Folded into overall_health_score penalty instead.
    "overall_health_score": HEALTH_SCORE,
}

# ── PURIF-001 (Fuel Oil Purifier) ─────────────────────────────────────────────

PURIF_THRESHOLDS: dict[str, Threshold] = {
    "vibration_rms_mms": Threshold(
        warning=3.5, alarm=5.5, unit="mm/s",
        source="Alfa Laval FOPX manual — purifier bowl vibration tighter limits "
               "due to high rotating mass",
        tier=2,
    ),
    # Tier 3: fuel contamination risk → main engine damage (ISM Code §10.3)
    "bowl_speed_deviation_pct": Threshold(
        warning=3.0, alarm=7.0, unit="%",
        source="Alfa Laval FOPX service manual — >3% indicates disc fouling; "
               ">7% indicates bearing wear or bowl imbalance",
        tier=3,
        compliance_code="ISM-10.3",
    ),
    "separation_efficiency_pct": Threshold(
        warning=75.0, alarm=60.0, unit="%",
        source="Alfa Laval operational guidance",
        direction="below",
        tier=2,
    ),
    "overall_health_score": HEALTH_SCORE,
}

# ── AUXGEN-001 (Auxiliary Generator) ─────────────────────────────────────────

GEN_THRESHOLDS: dict[str, Threshold] = {
    "vibration_rms_mms": VIBRATION_RMS,
    # Tier 3: electrical quality failure → blackout risk (SOLAS II-1)
    "frequency_deviation_hz": Threshold(
        warning=0.8, alarm=1.5, unit="Hz",
        source="IEC 60092-301 — ±1.5 Hz operational limit; "
               "±0.8 Hz governor hunting warning per DNV Rules Pt.4 Ch.8",
        tier=3,
        compliance_code="SOLAS-II-1",
    ),
    "load_factor_pct": Threshold(
        warning=85.0, alarm=95.0, unit="%",
        source="DNV class rules — sustained overload above 95% rated kW "
               "triggers thermal protection",
        tier=1,   # Monitor only — load oscillates naturally in sea-state; no agent cascade
    ),
    "overall_health_score": Threshold(
        warning=75.0, alarm=65.0, unit="%",
        source="Internal health score model — generator tighter limits "
               "due to frequency deviation impact on electrical quality",
        direction="below",
        tier=2,
    ),
}

# ── Master lookup by asset_id ──────────────────────────────────────────────────

ASSET_THRESHOLDS: dict[str, dict[str, Threshold]] = {
    "PUMP-001":   PUMP_THRESHOLDS,
    "COMP-001":   COMP_THRESHOLDS,
    "TURBO-001":  TURBO_THRESHOLDS,
    "PURIF-001":  PURIF_THRESHOLDS,
    "AUXGEN-001": GEN_THRESHOLDS,
}


def get_thresholds(asset_id: str) -> dict[str, Threshold]:
    return ASSET_THRESHOLDS.get(asset_id, {})
