import math
from datetime import datetime
from simulator.base_simulator import BaseSimulator


class GeneratorSimulator(BaseSimulator):
    """
    AUXGEN-001 — Auxiliary Generator (Wärtsilä 6L20 / 910 kW)
    Rated: 910 kW, 60 Hz, 6,600 V

    Degradation signature:
    - Frequency deviation increases (governor wear / fuel system issues)
    - Exhaust temp rises unevenly across cylinders (injector wear)
    - Coolant temperature rises (heat exchanger fouling)
    - Lube oil pressure drops (bearing wear / oil pump wear)
    - Fuel consumption rises (combustion efficiency loss)
    """

    RATED_FREQ = 60.0         # Hz
    RATED_VOLTAGE = 6_600.0   # V
    RATED_KW = 910.0          # kW
    RATED_EXHAUST_T = 380.0   # degC
    RATED_COOLANT_T = 80.0    # degC
    RATED_LUBE_P = 4.0        # bar
    RATED_FUEL = 180.0        # L/h at full load

    def _generate_readings(self, ts: datetime) -> dict[str, float]:
        h = self.health
        L = self.load

        # Load in kW
        load_kw = self.RATED_KW * L + self._noise(5.0)

        # Frequency: governor hunting — persistent positive offset with oscillation
        # abs(sin) keeps deviation non-zero so health score doesn't falsely recover
        freq_deviation = 2.5 * (1 - h) * (0.5 + 0.5 * abs(math.sin(self._tick / 20)))
        frequency = self.RATED_FREQ + freq_deviation + self._noise(0.05)

        # Voltage: relatively stable (AVR regulates it), slight drop with load
        voltage = self.RATED_VOLTAGE - L * 50 + self._noise(10.0)

        # Exhaust temp: rises with injector wear, higher at high load
        exhaust_t = self.RATED_EXHAUST_T + 80.0 * (1 - h) + L * 60.0 + self._noise(2.0)

        # Coolant temp: rises as heat exchanger fouls
        coolant_t = self.RATED_COOLANT_T + 20.0 * (1 - h) + L * 8.0 + self._noise(0.5)

        # Lube oil pressure: drops with bearing and pump wear
        lube_p = self.RATED_LUBE_P * (0.6 + 0.4 * h) + self._noise(0.06)

        # Fuel consumption: increases as combustion efficiency drops
        fuel = self.RATED_FUEL * L * (1.0 + 0.3 * (1 - h)) + self._noise(1.5)

        # Vibration: engine imbalance and bearing wear from degradation
        vibration = 0.8 + 6.0 * (1 - h) ** 1.5 + self._noise(0.1)

        return {
            "frequency_hz": round(frequency, 3),
            "voltage_v": round(max(0.0, voltage), 1),
            "load_kw": round(max(0.0, load_kw), 1),
            "exhaust_temp_c": round(exhaust_t, 1),
            "coolant_temp_c": round(coolant_t, 1),
            "lube_oil_pressure_bar": round(max(0.0, lube_p), 3),
            "fuel_consumption_lh": round(max(0.0, fuel), 1),
            "vibration_mms": round(max(0.0, vibration), 3),
        }

    def _generate_hf_readings(self, ts) -> dict[str, float]:
        """12-tag HF readings at 10 Hz for auxiliary generator."""
        h = self.health
        L = self.load
        t = self._hf_tick * 0.1

        # Engine speed ~500 RPM (8.33 Hz)
        shaft_rpm  = 500.0 * (0.98 + 0.02 * h) + self._noise(2)
        shaft_freq = shaft_rpm / 60.0

        # Engine imbalance (combustion variation between cylinders with wear)
        imbalance  = (1 - h) * 2.5
        vib_radial = 0.8 + 6.0 * (1 - h) ** 1.5 + imbalance * abs(math.sin(2 * math.pi * shaft_freq * t * 0.01)) + self._noise(0.08)
        vib_axial  = 0.5 + 3.5 * (1 - h) ** 1.5 + self._noise(0.05)

        load_kw    = self.RATED_KW * L + self._noise(4.0)
        # Governor hunting at HF (< 0.5 Hz oscillation)
        freq_dev   = 2.5 * (1 - h) * (0.5 + 0.5 * abs(math.sin(2 * math.pi * 0.1 * t)))
        frequency  = self.RATED_FREQ + freq_dev + self._noise(0.04)
        voltage    = self.RATED_VOLTAGE - L * 50 + self._noise(8)
        current    = (load_kw * 1000) / max(1.0, voltage * 1.732) + self._noise(0.5)
        exhaust_t  = self.RATED_EXHAUST_T + 80 * (1 - h) + L * 60 + self._noise(1.5)
        jacket_t   = self.RATED_COOLANT_T + 20 * (1 - h) + L * 8 + self._noise(0.4)
        lube_oil_p = self.RATED_LUBE_P * (0.6 + 0.4 * h) + self._noise(0.05)
        fuel_rack  = min(100.0, 60.0 * L * (1 + 0.25 * (1 - h)) + self._noise(1.0))
        turbo_spd  = 20000 * L * h + self._noise(30)   # simplified turbo speed

        return {
            "vib_radial_hf":         round(max(0.0, vib_radial), 4),
            "vib_axial_hf":          round(max(0.0, vib_axial), 4),
            "shaft_speed_hf":        round(max(0.0, shaft_rpm), 1),
            "load_kw_hf":            round(max(0.0, load_kw), 2),
            "frequency_hf":          round(frequency, 4),
            "voltage_hf":            round(max(0.0, voltage), 1),
            "current_hf":            round(max(0.0, current), 3),
            "exhaust_temp_hf":       round(exhaust_t, 2),
            "jacket_water_temp_hf":  round(jacket_t, 2),
            "lube_oil_pressure_hf":  round(max(0.0, lube_oil_p), 3),
            "fuel_rack_hf":          round(min(100.0, max(0.0, fuel_rack)), 2),
            "turbo_speed_hf":        round(max(0.0, turbo_spd), 0),
        }

    def _units(self) -> dict[str, str]:
        return {
            "frequency_hz": "Hz",
            "voltage_v": "V",
            "load_kw": "kW",
            "exhaust_temp_c": "degC",
            "coolant_temp_c": "degC",
            "lube_oil_pressure_bar": "bar",
            "fuel_consumption_lh": "L/h",
            "vibration_mms": "mm/s",
        }
