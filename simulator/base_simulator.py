import random
import math
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from models.telemetry import RawTelemetry, TelemetrySnapshot
from models.uns import UNSMessage, UNSCategory


class BaseSimulator(ABC):
    """
    Generates realistic sensor readings for one shipboard asset.

    Each simulator has two internal states:
      - health (1.0 = new, 0.0 = failed) — static until inject_fault() is called
      - load   (0.0–1.0) — varies with sea state / operational demand

    Health only changes on two explicit user actions:
      - inject_fault(severity) → one-time step down by severity percentage
      - reset()               → restored to 1.0

    There is NO background degradation. A healthy asset stays healthy
    indefinitely. Fault injection is the only path to degradation.

    HF mode (10 Hz):
      - tick_hf() emits 12-tag high-frequency readings for ML analysis
      - _generate_hf_readings(ts) is implemented by each subclass
    """

    def __init__(self, asset_id: str, asset_type: str, vessel: str = "MV-Eindhoven"):
        self.asset_id = asset_id
        self.asset_type = asset_type
        self.vessel = vessel
        self.health: float = 1.0          # 1.0 = healthy, 0.0 = failed
        self.load: float = 0.75           # typical sea-going load
        self._tick: int = 0               # call counter
        self._hf_tick: int = 0            # HF call counter (10 Hz)

    def tick(self) -> tuple[TelemetrySnapshot, list[UNSMessage]]:
        """Advance simulation by one second. Returns snapshot + UNS messages."""
        self._tick += 1
        self._update_load()
        # No _degrade() call — health is static until inject_fault() is called

        ts = datetime.now(timezone.utc)
        readings = self._generate_readings(ts)

        snapshot = TelemetrySnapshot(
            asset_id=self.asset_id,
            timestamp=ts,
            readings=readings,
        )

        messages = [
            UNSMessage.from_telemetry(
                asset_id=self.asset_id,
                asset_type=self.asset_type,
                tag=tag,
                value=value,
                unit=self._units().get(tag, ""),
                timestamp=ts,
                vessel=self.vessel,
            )
            for tag, value in readings.items()
        ]

        return snapshot, messages

    def tick_hf(self):
        """
        Advance HF simulation by one 10Hz tick.
        Returns an HFSample with 12 tags.
        Import HFSample here to avoid circular imports at module level.
        """
        from storage.hf_store import HFSample
        self._hf_tick += 1
        ts = datetime.now(timezone.utc)
        readings = self._generate_hf_readings(ts)
        return HFSample(
            asset_id=self.asset_id,
            timestamp=ts,
            readings=readings,
        )

    def _update_load(self):
        """Simulate slow sea-state driven load oscillation."""
        # Sinusoidal drift with small random walk — mimics wave-induced demand
        self.load = 0.75 + 0.15 * math.sin(self._tick / 120) + random.gauss(0, 0.02)
        self.load = max(0.3, min(1.0, self.load))

    def _noise(self, sigma: float) -> float:
        return random.gauss(0, sigma)

    def inject_fault(self, severity: float = 0.3):
        """
        Drop health by severity — one-time step, health stays at new level.
        Click the fault button again to drop further.
        Used by UI Demo Controls to trigger fault scenarios.
        """
        self.health = max(0.0, self.health - severity)

    def reset(self):
        self.health = 1.0
        self.load = 0.75
        self._tick = 0
        self._hf_tick = 0

    @abstractmethod
    def _generate_readings(self, ts: datetime) -> dict[str, float]:
        """Return {tag: value} dict. Health and load are available as self.health/load."""

    @abstractmethod
    def _generate_hf_readings(self, ts: datetime) -> dict[str, float]:
        """
        Return 12-tag HF readings at 10 Hz.
        Health and load are available as self.health/load.
        """

    @abstractmethod
    def _units(self) -> dict[str, str]:
        """Return {tag: unit_string} for every tag this simulator emits."""
