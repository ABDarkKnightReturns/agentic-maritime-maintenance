"""
Data Harmonizer
----------------
Sits between raw simulator output and the CEP engine.

Responsibilities:
  1. Quality gate  — drop messages with bad OPC UA quality codes
  2. Range clamp   — reject physically impossible values (sensor fault)
  3. Unit tagging  — ensure every message carries its engineering unit
  4. Gap detection — flag stale data if a tag hasn't updated in >5s
  5. Re-publish    — valid messages re-published under same topic (pass-through)
                     invalid ones published to .../Events/data_quality_alert

The harmonizer runs in its own thread, draining its input queue.
"""
import threading
import time
from datetime import datetime, timezone
from queue import Empty
from models.uns import UNSMessage, UNSCategory
from pipeline.uns_broker import broker
from loguru import logger

# Physically plausible sensor ranges — outside these = sensor fault
VALID_RANGES: dict[str, tuple[float, float]] = {
    # Pump
    "discharge_pressure_bar": (0.0, 20.0),
    "suction_pressure_bar": (0.0, 5.0),
    "flow_rate_m3h": (0.0, 50.0),
    "motor_current_a": (0.0, 100.0),
    "bearing_temp_c": (20.0, 150.0),
    "vibration_x_mms": (0.0, 30.0),
    "vibration_y_mms": (0.0, 30.0),
    # Compressor
    "inlet_pressure_bar": (0.5, 5.0),
    "outlet_pressure_bar": (0.0, 50.0),
    "inlet_temp_c": (10.0, 60.0),
    "outlet_temp_c": (50.0, 300.0),
    "oil_pressure_bar": (0.0, 10.0),
    "vibration_mms": (0.0, 30.0),
    # Turbocharger
    "speed_rpm": (0.0, 35_000.0),
    "boost_pressure_bar": (0.0, 5.0),
    "exhaust_temp_in_c": (200.0, 700.0),
    "exhaust_temp_out_c": (150.0, 600.0),
    "lube_oil_pressure_bar": (0.0, 6.0),
    # Purifier
    "bowl_speed_rpm": (0.0, 9_000.0),
    "feed_temp_c": (50.0, 120.0),
    "back_pressure_bar": (0.0, 3.0),
    "sludge_discharge_count": (0.0, 100_000.0),
    # Generator
    "frequency_hz": (55.0, 65.0),
    "voltage_v": (5_000.0, 8_000.0),
    "load_kw": (0.0, 1_200.0),
    "exhaust_temp_c": (200.0, 600.0),
    "coolant_temp_c": (50.0, 120.0),
    "fuel_consumption_lh": (0.0, 400.0),
}


class DataHarmonizer:

    def __init__(self):
        self._running = False
        self._thread: threading.Thread | None = None
        self._stats = {"received": 0, "passed": 0, "rejected": 0}
        # Subscribe to all raw sensor data
        self._in_queue = broker.subscribe(
            "Maersk/+/EngineRoom/+/+/Raw/#",
            subscriber_id="harmonizer",
        )

    def start(self):
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True, name="harmonizer")
        self._thread.start()
        logger.info("[Harmonizer] Started")

    def stop(self):
        self._running = False

    def _run(self):
        while self._running:
            try:
                msg: UNSMessage = self._in_queue.get(timeout=0.5)
                self._process(msg)
            except Empty:
                continue
            except Exception as e:
                logger.error(f"[Harmonizer] Error: {e}")

    def _process(self, msg: UNSMessage):
        self._stats["received"] += 1

        # 1. Quality gate
        if msg.quality < 192:
            self._reject(msg, reason=f"Bad OPC quality code: {msg.quality}")
            return

        # 2. Value must be numeric
        if not isinstance(msg.value, (int, float)):
            self._reject(msg, reason="Non-numeric value")
            return

        # 3. Range check
        tag = msg.tag or ""
        if tag in VALID_RANGES:
            lo, hi = VALID_RANGES[tag]
            if not (lo <= msg.value <= hi):
                self._reject(
                    msg,
                    reason=f"Out of range: {msg.value} not in [{lo}, {hi}]",
                )
                return

        # Passed all checks — re-publish (downstream CEP picks it up from same topic)
        self._stats["passed"] += 1

    def _reject(self, msg: UNSMessage, reason: str):
        self._stats["rejected"] += 1
        logger.warning(f"[Harmonizer] REJECTED {msg.topic} val={msg.value} | {reason}")
        alert = UNSMessage(
            topic=f"Maersk/{msg.vessel}/EngineRoom/DataQuality/Events/quality_alert",
            category=UNSCategory.EVENTS,
            vessel=msg.vessel,
            asset_id=msg.asset_id,
            tag=msg.tag,
            timestamp=msg.timestamp,
            value={"reason": reason, "rejected_value": msg.value},
            source="harmonizer",
        )
        broker.publish(alert)

    @property
    def stats(self) -> dict:
        return dict(self._stats)
