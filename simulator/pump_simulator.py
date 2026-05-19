import math
from datetime import datetime
from simulator.base_simulator import BaseSimulator


class PumpSimulator(BaseSimulator):
    """
    PUMP-001 — Lube Oil Pump (Alfa Laval LKH-25)
    Rated: 11 kW, 25 m³/h flow, 6 bar discharge

    Degradation signature:
    - Bearing temperature rises as health degrades (worn bearing)
    - Vibration increases (imbalance / worn seal)
    - Flow rate drops (pump efficiency loss)
    - Motor current rises (compensating for inefficiency)
    """

    RATED_FLOW = 25.0         # m³/h
    RATED_DISCHARGE = 6.0     # bar
    RATED_SUCTION = 0.5       # bar
    RATED_CURRENT = 22.0      # A at full load

    def _generate_readings(self, ts: datetime) -> dict[str, float]:
        h = self.health
        L = self.load

        # Differential pressure degrades with health (worn impeller)
        discharge_p = self.RATED_DISCHARGE * L * (0.7 + 0.3 * h) + self._noise(0.05)
        suction_p = self.RATED_SUCTION + self._noise(0.01)

        # Flow drops with health and load
        flow = self.RATED_FLOW * L * (0.65 + 0.35 * h) + self._noise(0.3)

        # Current rises when pump works harder to maintain flow despite wear
        current = self.RATED_CURRENT * L * (1.0 + 0.4 * (1 - h)) + self._noise(0.2)

        # Bearing temperature: baseline 45°C, rises sharply with wear
        bearing_temp = 45.0 + 35.0 * (1 - h) ** 1.5 + L * 8.0 + self._noise(0.5)

        # Vibration: baseline 0.8 mm/s at full health, rises sharply with wear
        vib_base = 0.8 + 5.5 * (1 - h) ** 2
        vibration_x = vib_base + self._noise(0.1)
        vibration_y = vib_base * 0.85 + self._noise(0.08)

        return {
            "discharge_pressure_bar": round(max(0.0, discharge_p), 3),
            "suction_pressure_bar": round(max(0.0, suction_p), 3),
            "flow_rate_m3h": round(max(0.0, flow), 2),
            "motor_current_a": round(max(0.0, current), 2),
            "bearing_temp_c": round(bearing_temp, 1),
            "vibration_x_mms": round(max(0.0, vibration_x), 3),
            "vibration_y_mms": round(max(0.0, vibration_y), 3),
        }

    def _generate_hf_readings(self, ts) -> dict[str, float]:
        """
        12-tag HF readings at 10 Hz.
        Degradation signatures at reduced health:
        - Vibration (x/y/z) increases, bearing defect frequencies emerge
        - Bearing temp rises faster
        - Seal leakage increases
        - Motor current ripple increases
        """
        h = self.health
        L = self.load
        t = self._hf_tick * 0.1   # seconds

        # Shaft speed: 1450 RPM nominal (~24.2 Hz)
        shaft_rpm = 1450.0 * (0.95 + 0.05 * h) + self._noise(5)
        shaft_freq = shaft_rpm / 60.0   # ~24 Hz

        # Vibration — healthy RMS ~0.8 mm/s; rises with wear
        vib_base    = 0.8 + 5.5 * (1 - h) ** 2
        # Add bearing defect impulsiveness when degraded (kurtosis increases)
        # Bearing outer race defect frequency ~3.4× shaft freq
        bpfo = 3.4 * shaft_freq
        defect_amp  = 0.0 if h > 0.85 else (1 - h) * 3.0
        defect_sig  = defect_amp * abs(math.sin(2 * math.pi * bpfo * t * 0.01))

        vib_x = vib_base + defect_sig + self._noise(0.08)
        vib_y = vib_base * 0.88 + defect_sig * 0.8 + self._noise(0.07)
        vib_z = vib_base * 0.35 + self._noise(0.04)   # axial lower

        bearing_temp  = 45.0 + 35.0 * (1 - h) ** 1.5 + L * 8.0 + self._noise(0.3)
        motor_current = self.RATED_CURRENT * L * (1.0 + 0.4 * (1 - h)) + self._noise(0.15)
        discharge_p   = self.RATED_DISCHARGE * L * (0.7 + 0.3 * h) + self._noise(0.04)
        suction_p     = self.RATED_SUCTION + self._noise(0.008)
        flow_rate     = self.RATED_FLOW * L * (0.65 + 0.35 * h) + self._noise(0.2)
        motor_temp    = 65.0 + 20.0 * (1 - h) + L * 10.0 + self._noise(0.3)
        # Seal leakage rises sharply near failure
        seal_leak     = max(0.0, 0.5 + 15.0 * (1 - h) ** 3 + self._noise(0.05))
        outlet_temp   = 45.0 + 5.0 * (1 - h) + self._noise(0.2)

        return {
            "vib_x_hf":             round(max(0.0, vib_x), 4),
            "vib_y_hf":             round(max(0.0, vib_y), 4),
            "vib_z_hf":             round(max(0.0, vib_z), 4),
            "bearing_temp_hf":      round(bearing_temp, 2),
            "motor_current_hf":     round(max(0.0, motor_current), 3),
            "discharge_pressure_hf": round(max(0.0, discharge_p), 3),
            "suction_pressure_hf":  round(max(0.0, suction_p), 3),
            "flow_rate_hf":         round(max(0.0, flow_rate), 3),
            "shaft_speed_hf":       round(max(0.0, shaft_rpm), 1),
            "motor_temp_hf":        round(motor_temp, 2),
            "seal_leakage_hf":      round(seal_leak, 3),
            "outlet_temp_hf":       round(outlet_temp, 2),
        }

    def _units(self) -> dict[str, str]:
        return {
            "discharge_pressure_bar": "bar",
            "suction_pressure_bar": "bar",
            "flow_rate_m3h": "m3/h",
            "motor_current_a": "A",
            "bearing_temp_c": "degC",
            "vibration_x_mms": "mm/s",
            "vibration_y_mms": "mm/s",
        }
