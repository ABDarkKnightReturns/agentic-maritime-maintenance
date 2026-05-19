import math
from datetime import datetime
from simulator.base_simulator import BaseSimulator


class PurifierSimulator(BaseSimulator):
    """
    PURIF-001 — Fuel Oil Purifier (Alfa Laval S-875)
    Rated: 7.5 kW, bowl speed ~7,200 RPM

    Degradation signature:
    - Bowl speed deviation increases (disc stack fouling / bearing wear)
    - Feed temperature drops (heat exchanger fouling)
    - Back pressure rises (blocked outlet / disc stack blockage)
    - Motor current rises (working harder against increased resistance)
    - Vibration increases (bowl imbalance from fouling)
    - Sludge discharge frequency decreases then spikes (blocked → purge cycle)
    """

    RATED_BOWL_SPEED = 7_200.0  # RPM
    RATED_FEED_TEMP = 98.0      # degC (HFO needs high temp for separation)
    RATED_BACK_P = 0.35         # bar
    RATED_CURRENT = 14.0        # A
    SLUDGE_INTERVAL = 120       # ticks between sludge discharges (healthy)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._sludge_counter = 0
        self._ticks_since_sludge = 0

    def _generate_readings(self, ts: datetime) -> dict[str, float]:
        h = self.health
        L = self.load

        # Bowl speed: drops with disc fouling, oscillates with bearing wear
        bowl_wobble = 0.5 * math.sin(self._tick / 30) * (1 - h)
        bowl_speed = self.RATED_BOWL_SPEED * (0.85 + 0.15 * h) + bowl_wobble * 50 + self._noise(10)

        # Feed temperature: drops as heat exchanger fouls
        feed_temp = self.RATED_FEED_TEMP * (0.85 + 0.15 * h) + self._noise(0.4)

        # Back pressure: rises with disc stack blockage
        back_p = self.RATED_BACK_P + 0.4 * (1 - h) ** 1.5 + self._noise(0.01)

        # Motor current: rises with increased resistance
        current = self.RATED_CURRENT * (1.0 + 0.5 * (1 - h)) + L * 1.5 + self._noise(0.2)

        # Vibration: bowl imbalance from uneven fouling / sludge buildup
        vibration = 1.0 + 7.0 * (1 - h) ** 2.0 + self._noise(0.1)

        # Sludge discharge: healthy = regular interval; degraded = longer gaps then big discharge
        self._ticks_since_sludge += 1
        sludge_interval = self.SLUDGE_INTERVAL * (1.0 + 2.0 * (1 - h))
        if self._ticks_since_sludge >= sludge_interval:
            self._sludge_counter += 1
            self._ticks_since_sludge = 0

        return {
            "bowl_speed_rpm": round(max(0.0, bowl_speed), 0),
            "feed_temp_c": round(feed_temp, 1),
            "back_pressure_bar": round(max(0.0, back_p), 3),
            "motor_current_a": round(max(0.0, current), 2),
            "vibration_mms": round(max(0.0, vibration), 3),
            "sludge_discharge_count": float(self._sludge_counter),
        }

    def _generate_hf_readings(self, ts) -> dict[str, float]:
        """12-tag HF readings at 10 Hz for purifier."""
        h = self.health
        L = self.load
        t = self._hf_tick * 0.1

        bowl_wobble = 0.5 * math.sin(self._hf_tick / 300) * (1 - h)
        bowl_rpm    = self.RATED_BOWL_SPEED * (0.85 + 0.15 * h) + bowl_wobble * 50 + self._noise(8)
        bowl_freq   = max(1.0, bowl_rpm / 60.0)

        # Imbalance due to uneven disc fouling
        imbalance   = (1 - h) * 2.0
        vib_radial  = 1.0 + 7.0 * (1 - h) ** 2.0 + imbalance * abs(math.sin(2 * math.pi * bowl_freq * t * 0.001)) + self._noise(0.08)
        vib_axial   = 0.6 + 3.0 * (1 - h) ** 1.8 + self._noise(0.05)
        frame_vib   = 0.4 + 2.0 * (1 - h) ** 1.5 + self._noise(0.04)

        feed_temp   = self.RATED_FEED_TEMP * (0.85 + 0.15 * h) + self._noise(0.3)
        back_p      = self.RATED_BACK_P + 0.4 * (1 - h) ** 1.5 + self._noise(0.008)
        sludge_p    = max(0.0, 0.1 + 0.5 * (1 - h) ** 2 + self._noise(0.01))
        motor_curr  = self.RATED_CURRENT * (1.0 + 0.5 * (1 - h)) + L * 1.5 + self._noise(0.15)
        motor_temp  = 65.0 + 20.0 * (1 - h) + L * 5 + self._noise(0.3)
        op_water_p  = max(0.0, 2.5 * h + self._noise(0.02))
        discharge_t = self.RATED_FEED_TEMP - 10 + 5 * (1 - h) + self._noise(0.2)
        feed_flow   = max(0.0, 800 * h * L + self._noise(10))

        return {
            "vib_radial_hf":         round(max(0.0, vib_radial), 4),
            "vib_axial_hf":          round(max(0.0, vib_axial), 4),
            "bowl_speed_hf":         round(max(0.0, bowl_rpm), 1),
            "motor_current_hf":      round(max(0.0, motor_curr), 3),
            "feed_flow_hf":          round(max(0.0, feed_flow), 1),
            "feed_temp_hf":          round(feed_temp, 2),
            "back_pressure_hf":      round(max(0.0, back_p), 3),
            "sludge_pressure_hf":    round(max(0.0, sludge_p), 3),
            "motor_temp_hf":         round(motor_temp, 2),
            "frame_vib_hf":          round(max(0.0, frame_vib), 4),
            "op_water_pressure_hf":  round(max(0.0, op_water_p), 3),
            "discharge_temp_hf":     round(discharge_t, 2),
        }

    def _units(self) -> dict[str, str]:
        return {
            "bowl_speed_rpm": "RPM",
            "feed_temp_c": "degC",
            "back_pressure_bar": "bar",
            "motor_current_a": "A",
            "vibration_mms": "mm/s",
            "sludge_discharge_count": "count",
        }
