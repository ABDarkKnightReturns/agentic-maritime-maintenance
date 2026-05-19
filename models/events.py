from enum import Enum
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class AlertSeverity(str, Enum):
    INFO = "Info"
    WARNING = "Warning"
    ALARM = "Alarm"
    CRITICAL = "Critical"


class EventType(str, Enum):
    THRESHOLD_BREACH = "threshold_breach"
    ANOMALY_DETECTED = "anomaly_detected"
    RUL_MILESTONE = "rul_milestone"         # RUL crossed 30/15/7/2-day boundary
    PATTERN_DETECTED = "pattern_detected"   # CEP multi-sensor pattern
    AGENT_ALERT = "agent_alert"             # Agent-generated finding
    HUMAN_ACKNOWLEDGED = "human_acknowledged"
    WORK_ORDER_RAISED = "work_order_raised"


class AlertEvent(BaseModel):
    event_id: str
    asset_id: str
    timestamp: datetime
    event_type: EventType
    severity: AlertSeverity
    title: str
    description: str
    uns_topic: Optional[str] = None

    # Triggering values
    tag: Optional[str] = None
    observed_value: Optional[float] = None
    threshold_value: Optional[float] = None
    unit: Optional[str] = None

    # Agent reasoning
    agent_name: Optional[str] = None
    agent_reasoning: Optional[str] = None      # Claude's explanation
    recommended_action: Optional[str] = None

    # Lifecycle
    acknowledged: bool = False
    acknowledged_by: Optional[str] = None      # "Chief Engineer" / "Superintendent"
    acknowledged_at: Optional[datetime] = None
    resolved: bool = False
    resolved_at: Optional[datetime] = None
    work_order_id: Optional[str] = None

    # ISM traceability
    ism_reference: Optional[str] = None        # e.g. "ISM Code 10.1 - Maintenance"
