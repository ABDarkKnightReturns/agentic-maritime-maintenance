import math
from datetime import datetime
from simulator.base_simulator import BaseSimulator


class TurboSimulator(BaseSimulator):
    """
    TURBO-001 — Main Engine Turbocharger (MAN TCA88-21)
    Rated: ~25,000 RPM, boost pressure 2.8 bar, exhaust in ~480°C

    Degradation signature:
    - Speed drops (fouled nozzle ring / blade erosion)
    - Boost pressure drops (reduced compression)
    - Exhaust delta temp widens (inefficient energy extraction)
    - Lube oil pressure drops (worn journal bearing)
    - Vibration increases (rotor imbalance from blade erosion)
    """

    RATED_SPEED = 25_000.0    # RPM
    RATED_BOOST_P = 2.8       # bar
    RATED_EXHAUST_IN = 480.0  # degC
    RATED_EXHAUST_OUT = 320.0 # degC
    RATED_LUBE_P = 2.2        # bar

    def _generate_readings(self, ts: datetime) -> dict[str, float]:
        h = self.health
        L = self.load

        # Speed: drops with fouling and blade erosion
        speed = self.RATED_SPEED * L * (0.65 + 0.35 * h) + self._noise(50)

        # Boost pressure: speed-squared affinity plus fouling/erosion efficiency loss.
        # A healthy turbo delivers full boost for its speed; degradation (fouling,
        # blade erosion) reduces compressor efficiency so boost drops below the
        # speed-expected value. The CEP divides actual boost by speed-expected boost
        # to compute turbo_efficiency — this gives: efficiency% ≈ h*100 at full load.
        speed_ratio = speed / self.RATED_SPEED
        fouling_factor = h   # h=1 → full boost; h=0 → zero boost (efficiency maps directly to h%)
        boost_p = self.RATED_BOOST_P * speed_ratio ** 2 * fouling_factor + self._noise(0.03)

        # Exhaust in: rises when turbo can't extract energy efficiently
        exhaust_in = self.RATED_EXHAUST_IN + 60.0 * (1 - h) + L * 40.0 + self._noise(2.0)

        # Exhaust out: should drop with better extraction — but with degradation it rises too
        exhaust_out = self.RATED_EXHAUST_OUT + 50.0 * (1 - h) + L * 25.0 + self._noise(1.5)

        # Lube oil pressure: drops with bearing wear
        lube_p = self.RATED_LUBE_P * (0.55 + 0.45 * h) + self._noise(0.04)

        # Vibration: rotor imbalance from blade erosion — key fault indicator
        vibration = 0.8 + 8.0 * (1 - h) ** 2.2 + self._noise(0.15)

        return {
            "speed_rpm": round(max(0.0, speed), 0),
            "boost_pressure_bar": round(max(0.0, boost_p), 3),
            "exhaust_temp_in_c": round(exhaust_in, 1),
            "exhaust_temp_out_c": round(exhaust_out, 1),
            "lube_oil_pressure_bar": round(max(0.0, lube_p), 3),
            "vibration_mms": round(max(0.0, vibration), 3),
        }

    def _generate_hf_readings(self, ts) -> dict[str, float]:
        """12-tag HF readings at 10 Hz for turbocharger."""
        h = self.health
        L = self.load
        t = self._hf_tick * 0.1

        rotor_rpm   = self.RATED_SPEED * L * (0.65 + 0.35 * h) + self._noise(40)
        rotor_freq  = max(1.0, rotor_rpm / 60.0)

        # Blade erosion creates sub-synchronous vibration
        erosion_amp = 0.0 if h > 0.85 else (1 - h) * 4.0
        sub_freq    = rotor_freq * 0.35
        vib_sub     = erosion_amp * abs(math.sin(2 * math.pi * sub_freq * t * 0.001))

        vib_radial  = 0.8 + 8.0 * (1 - h) ** 2.2 + vib_sub + self._noise(0.12)
        vib_axial   = 0.5 + 4.0 * (1 - h) ** 2.0 + self._noise(0.08)

        exhaust_in  = self.RATED_EXHAUST_IN  + 60 * (1 - h) + L * 40 + self._noise(1.5)
        exhaust_out = self.RATED_EXHAUST_OUT + 50 * (1 - h) + L * 25 + self._noise(1.2)
        boost_p     = self.RATED_BOOST_P * (rotor_rpm / self.RATED_SPEED) ** 2 * h + self._noise(0.02)
        comp_in_t   = 35.0 + L * 5 + self._noise(0.3)
        turb_in_t   = self.RATED_EXHAUST_IN + 60 * (1 - h) + L * 40 + self._noise(1.5)
        lube_oil_p  = self.RATED_LUBE_P * (0.55 + 0.45 * h) + self._noise(0.03)
        lube_oil_t  = 55.0 + 20.0 * (1 - h) + L * 5 + self._noise(0.3)
        bearing_de  = 50.0 + 30.0 * (1 - h) ** 1.8 + L * 6 + self._noise(0.3)
        bearing_fe  = 48.0 + 28.0 * (1 - h) ** 1.8 + L * 5 + self._noise(0.3)

        return {
            "vib_radial_hf":             round(max(0.0, vib_radial), 4),
            "vib_axial_hf":              round(max(0.0, vib_axial), 4),
            "rotor_speed_hf":            round(max(0.0, rotor_rpm), 0),
            "exhaust_in_temp_hf":        round(exhaust_in, 2),
            "exhaust_out_temp_hf":       round(exhaust_out, 2),
            "boost_pressure_hf":         round(max(0.0, boost_p), 3),
            "compressor_inlet_temp_hf":  round(comp_in_t, 2),
            "turbine_inlet_temp_hf":     round(turb_in_t, 2),
            "lube_oil_pressure_hf":      round(max(0.0, lube_oil_p), 3),
            "lube_oil_temp_hf":          round(lube_oil_t, 2),
            "bearing_temp_de_hf":        round(bearing_de, 2),
            "bearing_temp_fe_hf":        round(bearing_fe, 2),
        }

    def _units(self) -> dict[str, str]:
        return {
            "speed_rpm": "RPM",
            "boost_pressure_bar": "bar",
            "exhaust_temp_in_c": "degC",
            "exhaust_temp_out_c": "degC",
            "lube_oil_pressure_bar": "bar",
            "vibration_mms": "mm/s",
        }
