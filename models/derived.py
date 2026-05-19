from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class BearingCondition(str):
    GOOD = "Good"
    MARGINAL = "Marginal"
    DEGRADED = "Degraded"
    FAILED = "Failed"


class DerivedMetrics(BaseModel):
    """
    CEP-computed health metrics for one asset at one timestamp.
    These are published to the UNS under the /Derived/ category.
    """
    asset_id: str
    timestamp: datetime
    computed_by: str = "cep_engine"

    # --- Universal health indicators (all asset types) ---
    overall_health_score: float = Field(ge=0.0, le=100.0)  # 100 = perfect
    rul_days: Optional[float] = None                        # Remaining Useful Life
    anomaly_score: float = Field(default=0.0, ge=0.0, le=1.0)  # 0=normal, 1=extreme

    # --- Pump-specific ---
    pump_efficiency_pct: Optional[float] = None     # (actual flow / rated flow) * 100
    differential_pressure_bar: Optional[float] = None
    bearing_wear_index: Optional[float] = None      # 0–1, derived from vibration trend

    # --- Compressor-specific ---
    compression_ratio: Optional[float] = None       # outlet_p / inlet_p
    volumetric_efficiency_pct: Optional[float] = None
    specific_power_kwm3: Optional[float] = None     # power per unit flow

    # --- Turbocharger-specific ---
    turbo_efficiency_pct: Optional[float] = None
    surge_margin_pct: Optional[float] = None        # distance from surge line
    exhaust_delta_temp_c: Optional[float] = None    # in - out temp differential

    # --- Purifier-specific ---
    bowl_speed_deviation_pct: Optional[float] = None   # vs. rated speed
    separation_efficiency_pct: Optional[float] = None

    # --- Generator-specific ---
    load_factor_pct: Optional[float] = None         # load_kw / rated_kw * 100
    frequency_deviation_hz: Optional[float] = None  # vs. 60 Hz nominal
    specific_fuel_consumption: Optional[float] = None  # L/kWh

    # --- Vibration (all assets) ---
    vibration_rms_mms: Optional[float] = None
    vibration_trend_slope: Optional[float] = None   # mms/hour — positive = worsening

    # --- Raw-tag passthrough for alarm checking ---
    bearing_temp_c: Optional[float] = None          # pump bearing temperature

    @property
    def health_tier(self) -> str:
        if self.rul_days is None:
            return "Unknown"
        if self.rul_days > 30:
            return "Healthy"
        elif self.rul_days > 15:
            return "Watch"
        elif self.rul_days > 7:
            return "Advisory"
        elif self.rul_days > 2:
            return "Urgent"
        return "Critical"
