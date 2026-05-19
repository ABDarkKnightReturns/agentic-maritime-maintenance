from enum import Enum
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class SensorTag(str, Enum):
    # Pump tags
    PUMP_DISCHARGE_PRESSURE = "discharge_pressure_bar"
    PUMP_SUCTION_PRESSURE = "suction_pressure_bar"
    PUMP_FLOW_RATE = "flow_rate_m3h"
    PUMP_MOTOR_CURRENT = "motor_current_a"
    PUMP_BEARING_TEMP = "bearing_temp_c"
    PUMP_VIBRATION_X = "vibration_x_mms"
    PUMP_VIBRATION_Y = "vibration_y_mms"

    # Compressor tags
    COMP_INLET_PRESSURE = "inlet_pressure_bar"
    COMP_OUTLET_PRESSURE = "outlet_pressure_bar"
    COMP_INLET_TEMP = "inlet_temp_c"
    COMP_OUTLET_TEMP = "outlet_temp_c"
    COMP_MOTOR_CURRENT = "motor_current_a"
    COMP_VIBRATION = "vibration_mms"
    COMP_OIL_PRESSURE = "oil_pressure_bar"

    # Turbocharger tags
    TURBO_SPEED_RPM = "speed_rpm"
    TURBO_EXHAUST_TEMP_IN = "exhaust_temp_in_c"
    TURBO_EXHAUST_TEMP_OUT = "exhaust_temp_out_c"
    TURBO_BOOST_PRESSURE = "boost_pressure_bar"
    TURBO_LUBE_OIL_PRESSURE = "lube_oil_pressure_bar"
    TURBO_VIBRATION = "vibration_mms"

    # Purifier tags
    PURIF_BOWL_SPEED_RPM = "bowl_speed_rpm"
    PURIF_FEED_TEMP = "feed_temp_c"
    PURIF_BACK_PRESSURE = "back_pressure_bar"
    PURIF_MOTOR_CURRENT = "motor_current_a"
    PURIF_VIBRATION = "vibration_mms"
    PURIF_SLUDGE_COUNTER = "sludge_discharge_count"

    # Auxiliary Generator tags
    AUXGEN_FREQUENCY_HZ = "frequency_hz"
    AUXGEN_VOLTAGE_V = "voltage_v"
    AUXGEN_LOAD_KW = "load_kw"
    AUXGEN_EXHAUST_TEMP = "exhaust_temp_c"
    AUXGEN_COOLANT_TEMP = "coolant_temp_c"
    AUXGEN_LUBE_OIL_PRESSURE = "lube_oil_pressure_bar"
    AUXGEN_FUEL_CONSUMPTION = "fuel_consumption_lh"


class RawTelemetry(BaseModel):
    asset_id: str
    timestamp: datetime
    tag: str                        # SensorTag value or raw tag name
    value: float
    unit: str
    quality: int = 192              # OPC UA quality: 192 = Good
    uns_topic: Optional[str] = None # Full UNS topic this was published on

    @property
    def is_good_quality(self) -> bool:
        return self.quality >= 192


class TelemetrySnapshot(BaseModel):
    """All current readings for one asset at one timestamp — used by CEP engine."""
    asset_id: str
    timestamp: datetime
    readings: dict[str, float] = Field(default_factory=dict)  # tag -> value
    quality_flags: dict[str, int] = Field(default_factory=dict)

    def get(self, tag: str, default: float = 0.0) -> float:
        return self.readings.get(tag, default)
