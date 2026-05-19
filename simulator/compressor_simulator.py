from datetime import datetime
from simulator.base_simulator import BaseSimulator


class CompressorSimulator(BaseSimulator):
    """
    COMP-001 — Starting Air Compressor (Hamworthy Purus 2-150)
    Rated: 22 kW, 150 bar outlet, 1 bar inlet

    Degradation signature:
    - Outlet pressure drops (valve wear — can't seal compression chamber)
    - Outlet temperature rises (gas blow-by past worn valves)
    - Motor current rises (working harder for less compression)
    - Oil pressure drops (worn oil pump / seal leakage)
    - Vibration increases (piston ring wear / imbalance)
    """

    RATED_INLET_P = 1.0       # bar
    RATED_OUTLET_P = 30.0     # bar (demo-scaled from 150 bar)
    RATED_INLET_T = 35.0      # degC
    RATED_OUTLET_T = 160.0    # degC
    RATED_CURRENT = 42.0      # A
    RATED_OIL_P = 3.5         # bar

    def _generate_readings(self, ts: datetime) -> dict[str, float]:
        h = self.health
        L = self.load

        inlet_p = self.RATED_INLET_P + self._noise(0.02)
        inlet_t = self.RATED_INLET_T + L * 5.0 + self._noise(0.3)

        # Outlet pressure drops as valves wear
        outlet_p = self.RATED_OUTLET_P * (0.6 + 0.4 * h) * L + self._noise(0.4)

        # Outlet temp rises with blow-by (heat not doing useful work)
        outlet_t = self.RATED_OUTLET_T + 40.0 * (1 - h) + L * 15.0 + self._noise(1.0)

        # Current spikes as motor compensates
        current = self.RATED_CURRENT * L * (1.0 + 0.35 * (1 - h)) + self._noise(0.3)

        # Oil pressure drops with wear
        oil_p = self.RATED_OIL_P * (0.5 + 0.5 * h) + self._noise(0.05)

        # Vibration — piston ring wear causes uneven stroke
        vibration = 0.8 + 6.0 * (1 - h) ** 1.8 + self._noise(0.12)

        return {
            "inlet_pressure_bar": round(max(0.5, inlet_p), 3),
            "outlet_pressure_bar": round(max(0.0, outlet_p), 2),
            "inlet_temp_c": round(inlet_t, 1),
            "outlet_temp_c": round(outlet_t, 1),
            "motor_current_a": round(max(0.0, current), 2),
            "oil_pressure_bar": round(max(0.0, oil_p), 3),
            "vibration_mms": round(max(0.0, vibration), 3),
        }

    def _generate_hf_readings(self, ts) -> dict[str, float]:
        """12-tag HF readings at 10 Hz for compressor."""
        import math
        h = self.health
        L = self.load
        t = self._hf_tick * 0.1

        shaft_rpm   = 1000.0 * (0.95 + 0.05 * h) + self._noise(3)
        shaft_freq  = shaft_rpm / 60.0

        # Valve impact count rises with wear
        valve_click = max(0.0, 2.0 + 8.0 * (1 - h) ** 2 + self._noise(0.3))

        vib_base    = 0.8 + 6.0 * (1 - h) ** 1.8
        # Piston imbalance at 1× running frequency
        imbalance_amp = (1 - h) * 1.5
        vib_radial  = vib_base + imbalance_amp * abs(math.sin(2 * math.pi * shaft_freq * t * 0.01)) + self._noise(0.07)
        vib_axial   = vib_base * 0.4 + self._noise(0.04)
        vib_z       = vib_base * 0.3 + self._noise(0.03)

        inlet_p     = self.RATED_INLET_P + self._noise(0.015)
        outlet_p    = self.RATED_OUTLET_P * (0.6 + 0.4 * h) * L + self._noise(0.3)
        inlet_t     = self.RATED_INLET_T + L * 5 + self._noise(0.2)
        outlet_t    = self.RATED_OUTLET_T + 40 * (1 - h) + L * 15 + self._noise(0.8)
        motor_temp  = 70.0 + 25.0 * (1 - h) + L * 8 + self._noise(0.3)
        motor_curr  = self.RATED_CURRENT * L * (1.0 + 0.35 * (1 - h)) + self._noise(0.2)
        lube_oil_p  = self.RATED_OIL_P * (0.5 + 0.5 * h) + self._noise(0.04)

        return {
            "vib_radial_hf":       round(max(0.0, vib_radial), 4),
            "vib_axial_hf":        round(max(0.0, vib_axial), 4),
            "motor_current_hf":    round(max(0.0, motor_curr), 3),
            "inlet_pressure_hf":   round(max(0.0, inlet_p), 3),
            "outlet_pressure_hf":  round(max(0.0, outlet_p), 3),
            "inlet_temp_hf":       round(inlet_t, 2),
            "outlet_temp_hf":      round(outlet_t, 2),
            "shaft_speed_hf":      round(max(0.0, shaft_rpm), 1),
            "valve_click_hf":      round(max(0.0, valve_click), 2),
            "motor_temp_hf":       round(motor_temp, 2),
            "lube_oil_pressure_hf": round(max(0.0, lube_oil_p), 3),
            "vib_z_hf":            round(max(0.0, vib_z), 4),
        }

    def _units(self) -> dict[str, str]:
        return {
            "inlet_pressure_bar": "bar",
            "outlet_pressure_bar": "bar",
            "inlet_temp_c": "degC",
            "outlet_temp_c": "degC",
            "motor_current_a": "A",
            "oil_pressure_bar": "bar",
            "vibration_mms": "mm/s",
        }
