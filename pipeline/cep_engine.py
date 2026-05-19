"""
Complex Event Processing (CEP) Engine
---------------------------------------
Subscribes to raw UNS telemetry, maintains a rolling window per asset,
and computes derived health metrics every second.

Derived metrics published to:
  Maersk/{vessel}/EngineRoom/{AssetType}/{AssetID}/Derived/health_snapshot

Key computations per asset type:
  Pump       — pump efficiency, differential pressure, bearing wear index
  Compressor — compression ratio, volumetric efficiency, specific power
  Turbo      — turbo efficiency, exhaust delta temp, surge margin
  Purifier   — bowl speed deviation, separation efficiency estimate
  Generator  — load factor, frequency deviation, specific fuel consumption

Universal — vibration RMS, vibration trend slope, overall health score, RUL
"""
import threading
import time
import math
from collections import deque
from datetime import datetime, timezone
from queue import Empty
from typing import Optional

import numpy as np
from models.derived import DerivedMetrics
from models.uns import UNSMessage, UNSCategory
from pipeline.uns_broker import broker
from pipeline.alarm_manager import alarm_manager
from data.inventory import ASSETS
from loguru import logger

WINDOW_SIZE = 60        # seconds of rolling data for trend calculations
COMPUTE_INTERVAL = 1.0  # seconds between derived metric publishes

# Asset type lookup by asset_id
_ASSET_TYPE_MAP = {aid: a.asset_type.value for aid, a in ASSETS.items()}


class AssetWindow:
    """Rolling in-memory window of raw readings for one asset."""

    def __init__(self, asset_id: str, window: int = WINDOW_SIZE):
        self.asset_id = asset_id
        self._window = window
        # tag -> deque of (timestamp, value)
        self._data: dict[str, deque] = {}

    def update(self, tag: str, value: float, ts: datetime):
        if tag not in self._data:
            self._data[tag] = deque(maxlen=self._window)
        self._data[tag].append((ts, value))

    def latest(self, tag: str, default: float = 0.0) -> float:
        if tag in self._data and self._data[tag]:
            return self._data[tag][-1][1]
        return default

    def mean(self, tag: str, n: int = 30) -> float:
        if tag not in self._data or not self._data[tag]:
            return 0.0
        vals = [v for _, v in list(self._data[tag])[-n:]]
        return float(np.mean(vals)) if vals else 0.0

    def trend_slope(self, tag: str) -> float:
        """Linear regression slope (value/second) over the window."""
        if tag not in self._data or len(self._data[tag]) < 5:
            return 0.0
        pts = list(self._data[tag])
        t0 = pts[0][0].timestamp()
        xs = np.array([p[0].timestamp() - t0 for p in pts])
        ys = np.array([p[1] for p in pts])
        if xs.std() < 1e-9:
            return 0.0
        slope = float(np.polyfit(xs, ys, 1)[0])
        return slope

    def count(self, tag: str) -> int:
        """Number of samples currently buffered for this tag."""
        if tag not in self._data:
            return 0
        return len(self._data[tag])

    def has_data(self, *tags: str) -> bool:
        return all(t in self._data and self._data[t] for t in tags)


class CEPEngine:

    def __init__(self):
        self._running = False
        self._thread: threading.Thread | None = None
        self._windows: dict[str, AssetWindow] = {
            aid: AssetWindow(aid) for aid in ASSETS
        }
        self._in_queue = broker.subscribe(
            "Maersk/+/EngineRoom/+/+/Raw/#",
            subscriber_id="cep_engine",
        )
        # Cache latest derived metrics for agent queries (no DB needed at this layer)
        self.latest_derived: dict[str, DerivedMetrics] = {}

    def start(self):
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True, name="cep_engine")
        self._thread.start()
        logger.info("[CEP] Started")

    def stop(self):
        self._running = False

    def reset(self):
        """Clear rolling windows and derived cache — called on fleet reset."""
        for window in self._windows.values():
            window._data.clear()
        self.latest_derived.clear()

    # ------------------------------------------------------------------
    # Main loop — drain queue then compute
    # ------------------------------------------------------------------

    def _run(self):
        last_compute = time.monotonic()
        while self._running:
            # Drain all available messages into windows
            drained = 0
            while True:
                try:
                    msg: UNSMessage = self._in_queue.get_nowait()
                    if msg.tag and isinstance(msg.value, (int, float)):
                        w = self._windows.get(msg.asset_id)
                        if w:
                            w.update(msg.tag, float(msg.value), msg.timestamp)
                    drained += 1
                except Empty:
                    break

            # Compute derived metrics on schedule
            now = time.monotonic()
            if now - last_compute >= COMPUTE_INTERVAL:
                for asset_id, window in self._windows.items():
                    self._compute_and_publish(asset_id, window)
                last_compute = now

            time.sleep(0.05)

    # ------------------------------------------------------------------
    # Derived metric computation
    # ------------------------------------------------------------------

    def _compute_and_publish(self, asset_id: str, w: AssetWindow):
        ts = datetime.now(timezone.utc)
        asset_type = _ASSET_TYPE_MAP.get(asset_id, "")

        metrics = DerivedMetrics(
            asset_id=asset_id,
            timestamp=ts,
            overall_health_score=100.0,     # computed below
        )

        if asset_type == "Pump":
            self._compute_pump(w, metrics)
        elif asset_type == "Compressor":
            self._compute_compressor(w, metrics)
        elif asset_type == "Turbocharger":
            self._compute_turbo(w, metrics)
        elif asset_type == "Purifier":
            self._compute_purifier(w, metrics)
        elif asset_type == "Generator":
            self._compute_generator(w, metrics)

        self._compute_universal(w, metrics, asset_type)
        self._compute_health_score(metrics)
        self._estimate_rul(asset_id, metrics)

        self.latest_derived[asset_id] = metrics
        self._publish(asset_id, asset_type, metrics, ts)

        # Warm-up guard: skip alarm evaluation until we have at least 10 samples.
        # Prevents spurious alarms during the first ~10 seconds after a fleet reset
        # when rolling-window statistics are not yet stable.
        warmup_tag = "vibration_x_mms" if asset_type == "Pump" else "vibration_mms"
        if w.count(warmup_tag) >= 10:
            alarm_manager.evaluate(metrics)

    # --- Asset-type specific computations ---

    def _compute_pump(self, w: AssetWindow, m: DerivedMetrics):
        disch = w.latest("discharge_pressure_bar")
        suct = w.latest("suction_pressure_bar")
        flow = w.latest("flow_rate_m3h")
        current = w.latest("motor_current_a")
        m.bearing_temp_c = round(w.latest("bearing_temp_c"), 1)

        m.differential_pressure_bar = round(disch - suct, 3)

        # Efficiency: dp vs. expected dp at current load (current-based load estimate)
        # At full health: I = rated_I * L → L_est = I / rated_I
        # At degraded health: I rises (motor works harder) → L_est overestimates L
        # → expected_dp is higher than actual → efficiency drops. Correct behaviour.
        rated_current = 22.0
        l_est = max(0.1, min(1.0, current / rated_current))
        expected_dp = 5.5 * l_est
        if expected_dp > 0:
            m.pump_efficiency_pct = round(
                min(100.0, (m.differential_pressure_bar / expected_dp) * 100), 1
            )

        # Bearing wear index — normalised vibration trend
        vib_x = w.latest("vibration_x_mms")
        vib_slope = w.trend_slope("vibration_x_mms") * 3600  # per hour
        # Index 0=new, 1=failed; 7 mm/s is alarm threshold
        m.bearing_wear_index = round(min(1.0, max(0.0, vib_x / 7.0)), 3)
        m.vibration_trend_slope = round(vib_slope, 4)

    def _compute_compressor(self, w: AssetWindow, m: DerivedMetrics):
        inlet_p = w.latest("inlet_pressure_bar", default=1.0)
        outlet_p = w.latest("outlet_pressure_bar")
        current = w.latest("motor_current_a")

        if inlet_p > 0:
            m.compression_ratio = round(outlet_p / inlet_p, 2)

        # Volumetric efficiency: cr vs. expected cr at current load
        # At full health: cr = 30*L, current = 42*L → L_est = I/42 → expected_cr = 30*L_est
        rated_cr = 30.0
        rated_current = 42.0
        l_est_comp = max(0.1, min(1.0, current / rated_current))
        expected_cr = rated_cr * l_est_comp
        if expected_cr > 0 and m.compression_ratio:
            m.volumetric_efficiency_pct = round(
                min(100.0, (m.compression_ratio / expected_cr) * 100), 1
            )

        # Specific power = kW / (m³/h equivalent) — proxy using current
        rated_current = 42.0
        if rated_current > 0:
            m.specific_power_kwm3 = round(current / rated_current, 3)

    def _compute_turbo(self, w: AssetWindow, m: DerivedMetrics):
        speed = w.latest("speed_rpm")
        exhaust_in = w.latest("exhaust_temp_in_c")
        exhaust_out = w.latest("exhaust_temp_out_c")
        boost_p = w.latest("boost_pressure_bar")

        m.exhaust_delta_temp_c = round(exhaust_in - exhaust_out, 1)

        # Efficiency: ratio of actual boost to expected boost for this speed
        rated_speed = 25_000.0
        rated_boost = 2.8
        if rated_speed > 0:
            expected_boost = rated_boost * (speed / rated_speed) ** 2
            if expected_boost > 0.1:
                m.turbo_efficiency_pct = round(
                    min(100.0, (boost_p / expected_boost) * 100), 1
                )

        # Surge margin: use a 10-sample mean to smooth load-driven transients.
        # A single noisy tick at low load can spike the margin below threshold;
        # averaging over 10s gives a stable estimate of sustained operating point.
        surge_speed = rated_speed * 0.65
        if w.has_data("speed_rpm") and rated_speed > surge_speed:
            smooth_speed = w.mean("speed_rpm", n=10) or speed
            m.surge_margin_pct = round(
                max(0.0, (smooth_speed - surge_speed) / (rated_speed - surge_speed) * 100), 1
            )

    def _compute_purifier(self, w: AssetWindow, m: DerivedMetrics):
        bowl_speed = w.latest("bowl_speed_rpm")
        feed_temp = w.latest("feed_temp_c")
        back_p = w.latest("back_pressure_bar")

        rated_bowl = 7_200.0
        if rated_bowl > 0:
            deviation = abs(bowl_speed - rated_bowl) / rated_bowl * 100
            m.bowl_speed_deviation_pct = round(deviation, 2)

        # Separation efficiency proxy: high feed temp + low back pressure = good
        # Normalise to 0-100%
        temp_score = min(1.0, feed_temp / 98.0)       # 98°C is rated
        pressure_score = max(0.0, 1 - (back_p - 0.35) / 0.6)  # above 0.95 bar = very bad
        m.separation_efficiency_pct = round(
            (0.6 * temp_score + 0.4 * pressure_score) * 100, 1
        )

    def _compute_generator(self, w: AssetWindow, m: DerivedMetrics):
        # Use 10-sample mean for frequency to smooth sine-wave oscillation
        freq = w.mean("frequency_hz", n=10) or 60.0
        load_kw = w.latest("load_kw")
        fuel = w.latest("fuel_consumption_lh")

        m.frequency_deviation_hz = round(abs(freq - 60.0), 3)
        m.load_factor_pct = round(min(100.0, load_kw / 910.0 * 100), 1)

        if load_kw > 10:
            m.specific_fuel_consumption = round(fuel / load_kw, 4)  # L/kWh

    # --- Universal metrics ---

    def _compute_universal(self, w: AssetWindow, m: DerivedMetrics, asset_type: str):
        # Find the vibration tag for this asset type
        vib_tag = "vibration_mms"
        if asset_type == "Pump":
            vib_x = w.mean("vibration_x_mms", n=10)
            vib_y = w.mean("vibration_y_mms", n=10)
            vib_rms = math.sqrt((vib_x ** 2 + vib_y ** 2) / 2)
            slope = w.trend_slope("vibration_x_mms") * 3600
        else:
            vib_rms = w.mean(vib_tag, n=10)
            slope = w.trend_slope(vib_tag) * 3600

        m.vibration_rms_mms = round(vib_rms, 3)
        m.vibration_trend_slope = round(slope, 4)

        # Anomaly score: z-score of 10-sample mean vs. 30-sample baseline, normalised.
        # Requires 30 samples before computing — with fewer samples the rolling mean is
        # unstable and the z-score spikes spuriously, causing false 20-point health
        # penalties on a freshly reset (healthy) asset.
        vib_tag_anomaly = vib_tag if asset_type != "Pump" else "vibration_x_mms"
        if w.count(vib_tag_anomaly) >= 30:
            vib_mean30 = w.mean(vib_tag_anomaly, n=30)
            if vib_mean30 > 0.1:
                z = abs(vib_rms - vib_mean30) / max(vib_mean30 * 0.1, 0.01)
                m.anomaly_score = round(min(1.0, z / 5.0), 3)
        # else: anomaly_score stays 0.0 (DerivedMetrics default) — no penalty during warm-up

    def _compute_health_score(self, m: DerivedMetrics):
        """
        Composite health score 0–100.
        Weighted penalty model: vibration, efficiency, and anomaly all contribute.
        """
        score = 100.0

        # Vibration penalty — ISO 10816-3 Zone A upper limit is 2.3 mm/s (new machinery).
        # No penalty within Zone A; full 40pt penalty at Zone D boundary (7.1 mm/s).
        VIB_ZONE_A = 2.3
        VIB_ALARM  = 7.1
        if m.vibration_rms_mms is not None and m.vibration_rms_mms > VIB_ZONE_A:
            excess = m.vibration_rms_mms - VIB_ZONE_A
            vib_penalty = min(40.0, (excess / (VIB_ALARM - VIB_ZONE_A)) * 40.0)
            score -= vib_penalty

        # Efficiency penalty (if available)
        for eff_attr in ("pump_efficiency_pct", "turbo_efficiency_pct",
                          "volumetric_efficiency_pct", "separation_efficiency_pct"):
            eff = getattr(m, eff_attr, None)
            if eff is not None:
                eff_penalty = max(0.0, (100.0 - eff) * 0.4)
                score -= min(30.0, eff_penalty)
                break

        # Bowl speed deviation penalty (purifier — alarm at 7%)
        if m.bowl_speed_deviation_pct is not None:
            bowl_penalty = min(30.0, (m.bowl_speed_deviation_pct / 7.0) * 30.0)
            score -= bowl_penalty

        # Frequency deviation penalty (generator — alarm at 2.5 Hz)
        if m.frequency_deviation_hz is not None:
            freq_penalty = min(30.0, (m.frequency_deviation_hz / 2.5) * 30.0)
            score -= freq_penalty

        # Anomaly score penalty
        score -= m.anomaly_score * 20.0

        m.overall_health_score = round(max(0.0, min(100.0, score)), 1)

    def _estimate_rul(self, asset_id: str, m: DerivedMetrics):
        """
        Estimate Remaining Useful Life in days.
        Uses vibration trend slope: projects when vibration will hit 7.1 mm/s alarm.
        Falls back to health score if trend is flat or window is too small.
        Requires at least 30s of data before trusting the slope (prevents noisy
        startup projections from a few-sample linear regression giving 0d on healthy assets).
        """
        vib = m.vibration_rms_mms or 0.0
        slope = m.vibration_trend_slope or 0.0
        alarm_threshold = 7.1   # mm/s

        # Only use slope-based projection when:
        # 1. slope is meaningfully positive (not noise)
        # 2. vibration is already elevated enough that the projection is credible
        # 3. we project > 1 day (avoids false 0d on healthy startup)
        if slope > 0.05 and vib > 1.5 and vib < alarm_threshold:
            hours_to_alarm = (alarm_threshold - vib) / slope
            projected_days = round(hours_to_alarm / 24, 1)
            if projected_days >= 1.0:
                m.rul_days = projected_days
            else:
                m.rul_days = round((m.overall_health_score / 100.0) * 60.0, 1)
        else:
            # Fallback: map health score linearly to RUL (100% health = 60 days)
            m.rul_days = round((m.overall_health_score / 100.0) * 60.0, 1)

        m.rul_days = max(0.0, m.rul_days)

    # ------------------------------------------------------------------
    # Publish derived snapshot back to UNS
    # ------------------------------------------------------------------

    def _publish(self, asset_id: str, asset_type: str, m: DerivedMetrics, ts: datetime):
        topic = UNSMessage.build_topic(
            vessel="MV-Eindhoven",
            asset_type=asset_type,
            asset_id=asset_id,
            category=UNSCategory.DERIVED,
            tag="health_snapshot",
        )
        msg = UNSMessage(
            topic=topic,
            category=UNSCategory.DERIVED,
            asset_id=asset_id,
            timestamp=ts,
            value=m.model_dump(mode="json"),  # datetime → ISO string for JSON-safe dict
            source="cep_engine",
        )
        broker.publish(msg)
