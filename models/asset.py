from enum import Enum
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class AssetType(str, Enum):
    PUMP = "Pump"
    COMPRESSOR = "Compressor"
    TURBOCHARGER = "Turbocharger"
    PURIFIER = "Purifier"
    GENERATOR = "Generator"


class AssetStatus(str, Enum):
    RUNNING = "running"
    DEGRADED = "degraded"
    CRITICAL = "critical"
    OFFLINE = "offline"
    MAINTENANCE = "maintenance"


class HealthTier(str, Enum):
    HEALTHY = "Healthy"          # RUL > 30 days
    WATCH = "Watch"              # RUL 15–30 days
    ADVISORY = "Advisory"        # RUL 7–15 days
    URGENT = "Urgent"            # RUL 2–7 days
    CRITICAL = "Critical"        # RUL < 2 days


class Asset(BaseModel):
    asset_id: str                           # e.g. "PUMP-001"
    display_name: str                       # e.g. "Lube Oil Pump #1"
    asset_type: AssetType
    vessel: str = "MV-Eindhoven"
    location: str = "Engine Room"
    manufacturer: str
    model_number: str
    commissioned_date: datetime
    rated_power_kw: float
    status: AssetStatus = AssetStatus.RUNNING
    health_tier: HealthTier = HealthTier.HEALTHY
    rul_days: Optional[float] = None        # Remaining Useful Life
    last_maintenance: Optional[datetime] = None
    next_scheduled_maintenance: Optional[datetime] = None
    running_hours: float = 0.0
    # ISM / class society fields
    class_society: str = "DNV"
    imo_equipment_code: Optional[str] = None
    pms_job_code: Optional[str] = None     # Planned Maintenance System code

    @property
    def uns_path_prefix(self) -> str:
        return f"Maersk/{self.vessel}/EngineRoom/{self.asset_type.value}/{self.asset_id}"
