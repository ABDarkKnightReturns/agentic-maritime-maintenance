from enum import Enum
from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel, Field


class UNSCategory(str, Enum):
    """
    ISA-95 / Unified Namespace topic categories.
    Full topic: Maersk/{Vessel}/EngineRoom/{AssetType}/{AssetID}/{Category}/{Tag}
    """
    RAW = "Raw"             # Direct sensor readings (1Hz)
    DERIVED = "Derived"     # CEP-computed metrics
    EVENTS = "Events"       # Alerts and anomalies
    COMMANDS = "Commands"   # Actuation / agent instructions
    STATUS = "Status"       # Asset lifecycle state
    METADATA = "Metadata"   # Asset master data


class UNSMessage(BaseModel):
    """
    Canonical envelope for every message on the Unified Namespace.
    Mirrors an MQTT/Kafka message payload — all data flows through this shape.
    """
    # Routing
    topic: str                  # Full UNS topic string
    category: UNSCategory

    # Identity
    vessel: str = "MV-Eindhoven"
    asset_id: str
    tag: Optional[str] = None   # Leaf-level tag name (None for aggregate messages)

    # Payload
    timestamp: datetime
    value: Any                  # float for telemetry, dict for complex payloads
    unit: Optional[str] = None

    # OPC UA quality code (192 = Good, 0 = Bad)
    quality: int = 192

    # Provenance
    source: str = "simulator"   # "simulator" | "cep_engine" | "agent_*"
    schema_version: str = "1.0"

    @classmethod
    def build_topic(
        cls,
        vessel: str,
        asset_type: str,
        asset_id: str,
        category: UNSCategory,
        tag: Optional[str] = None,
    ) -> str:
        base = f"Maersk/{vessel}/EngineRoom/{asset_type}/{asset_id}/{category.value}"
        return f"{base}/{tag}" if tag else base

    @classmethod
    def from_telemetry(
        cls,
        asset_id: str,
        asset_type: str,
        tag: str,
        value: float,
        unit: str,
        timestamp: datetime,
        quality: int = 192,
        vessel: str = "MV-Eindhoven",
    ) -> "UNSMessage":
        topic = cls.build_topic(vessel, asset_type, asset_id, UNSCategory.RAW, tag)
        return cls(
            topic=topic,
            category=UNSCategory.RAW,
            vessel=vessel,
            asset_id=asset_id,
            tag=tag,
            timestamp=timestamp,
            value=value,
            unit=unit,
            quality=quality,
            source="simulator",
        )
