"""
FaultClassifier — rule-based probabilistic fault classification.

For each fault class a physics-informed score is computed from the
extracted features.  Scores are normalised via softmax to probabilities.

Fault classes:
  bearing_wear, cavitation, imbalance, misalignment,
  looseness, seal_leak, fouling, normal
"""
from __future__ import annotations

import math
import numpy as np
from typing import Optional


FAULT_CLASSES = [
    "bearing_wear",
    "cavitation",
    "imbalance",
    "misalignment",
    "looseness",
    "seal_leak",
    "fouling",
    "normal",
]


class FaultClassifier:

    def classify(
        self,
        features: dict,
        asset_type: str,
    ) -> tuple[str, float, list[dict]]:
        """
        Classify the fault from extracted features.

        Returns
        -------
        (fault_class, probability, candidates)
          fault_class   : str — top predicted fault
          probability   : float — normalised probability of top class
          candidates    : list[dict] — top-3 [{class, prob}] sorted desc
        """
        scores = {
            "bearing_wear": self._score_bearing_wear(features),
            "cavitation":   self._score_cavitation(features, asset_type),
            "imbalance":    self._score_imbalance(features),
            "misalignment": self._score_misalignment(features),
            "looseness":    self._score_looseness(features),
            "seal_leak":    self._score_seal_leak(features, asset_type),
            "fouling":      self._score_fouling(features, asset_type),
            "normal":       self._score_normal(features),
        }

        probs = self._to_probabilities(scores)
        sorted_classes = sorted(probs.items(), key=lambda x: x[1], reverse=True)

        top_class, top_prob = sorted_classes[0]
        candidates = [{"class": c, "probability": round(p, 3)}
                      for c, p in sorted_classes[:3]]

        return top_class, round(top_prob, 3), candidates

    # ── Individual fault scorers ──────────────────────────────────────────

    @staticmethod
    def _score_bearing_wear(f: dict) -> float:
        """
        Bearing wear: elevated kurtosis + high crest factor +
        high-freq power elevation + rising temperature.
        """
        score = 0.0
        kurt  = f.get("kurtosis", 3.0)
        cf    = f.get("crest_factor", 2.5)
        hfp   = f.get("high_freq_power", 0.0)
        td    = f.get("temp_delta", 0.0)

        # Kurtosis: healthy ~3 (Gaussian), bearing defect >4, severe >8
        if kurt > 8:    score += 3.0
        elif kurt > 6:  score += 2.0
        elif kurt > 4:  score += 1.0

        # Crest factor: healthy ~2.5, impulsive bearing >5
        if cf > 8:    score += 2.5
        elif cf > 6:  score += 1.5
        elif cf > 4:  score += 0.7

        # High-frequency spectral power (bearing defect frequencies)
        if hfp > 0.20:  score += 2.0
        elif hfp > 0.10: score += 1.0

        # Temperature rise (bearing running hot)
        if td > 10:   score += 1.5
        elif td > 5:  score += 0.8

        return score

    @staticmethod
    def _score_cavitation(f: dict, asset_type: str) -> float:
        """
        Cavitation (pumps and compressors): broadband vibration,
        pressure fluctuation, sub-sync and 2× harmonics.
        """
        # Cavitation only makes sense for pumps and compressors
        if asset_type not in ("Pump", "Compressor"):
            return 0.0

        score = 0.0
        rms    = f.get("rms", 0.8)
        sub    = f.get("sub_sync_power", 0.0)
        two_x  = f.get("2x_sync_power", 0.0)
        pf     = f.get("pressure_fluctuation", 0.0)

        # Broadband vibration without high kurtosis (cavitation is random noise)
        kurt = f.get("kurtosis", 3.0)
        if rms > 3.0 and kurt < 5:
            score += 2.0
        elif rms > 2.0 and kurt < 4:
            score += 1.0

        if sub > 0.15:   score += 1.5
        if two_x > 0.15: score += 1.0
        if pf > 0.1:     score += 1.5

        return score

    @staticmethod
    def _score_imbalance(f: dict) -> float:
        """
        Imbalance: dominant 1× running frequency, moderate RMS,
        relatively smooth spectrum (low kurtosis).
        """
        score  = 0.0
        sync   = f.get("sync_power", 0.0)
        kurt   = f.get("kurtosis", 3.0)
        rms    = f.get("rms", 0.8)

        # Imbalance: strong 1× with moderate vibration, normal kurtosis
        if sync > 0.40:  score += 3.0
        elif sync > 0.25: score += 1.5

        # Normal/low kurtosis distinguishes imbalance from bearing defects
        if kurt < 4:     score += 1.0

        if rms > 2.0 and rms < 6.0:  score += 0.5

        return score

    @staticmethod
    def _score_misalignment(f: dict) -> float:
        """
        Misalignment: elevated 2× harmonic, high axial-to-radial ratio,
        mild temperature rise.
        """
        score    = 0.0
        two_x    = f.get("2x_sync_power", 0.0)
        axial_r  = f.get("axial_radial_ratio", 0.0)
        td       = f.get("temp_delta", 0.0)

        if two_x > 0.30:   score += 3.0
        elif two_x > 0.15: score += 1.5

        # Misalignment often elevates axial vibration
        if axial_r > 0.7:  score += 2.0
        elif axial_r > 0.4: score += 1.0

        if 2 < td < 8:     score += 0.5   # mild thermal

        return score

    @staticmethod
    def _score_looseness(f: dict) -> float:
        """
        Mechanical looseness: sub-synchronous power, multiple harmonics,
        asymmetric vibration (high skewness).
        """
        score   = 0.0
        sub     = f.get("sub_sync_power", 0.0)
        sync    = f.get("sync_power", 0.0)
        two_x   = f.get("2x_sync_power", 0.0)
        skew    = abs(f.get("skewness", 0.0))

        if sub > 0.20:   score += 2.5
        elif sub > 0.10: score += 1.0

        # Looseness often generates harmonics across the spectrum
        harmonic_spread = sub + sync + two_x
        if harmonic_spread > 0.40:  score += 1.5

        if skew > 1.5:   score += 1.0
        elif skew > 0.8: score += 0.5

        return score

    @staticmethod
    def _score_seal_leak(f: dict, asset_type: str) -> float:
        """
        Seal leakage (pumps and compressors): pressure drop,
        relatively normal vibration.
        """
        if asset_type not in ("Pump", "Compressor"):
            return 0.0

        score = 0.0
        pf    = f.get("pressure_fluctuation", 0.0)
        rms   = f.get("rms", 0.8)
        kurt  = f.get("kurtosis", 3.0)

        # Seal leak: low-moderate vibration, unstable pressure
        if pf > 0.15 and rms < 3.0 and kurt < 4.5:
            score += 2.5
        elif pf > 0.08:
            score += 1.0

        return score

    @staticmethod
    def _score_fouling(f: dict, asset_type: str) -> float:
        """
        Fouling (turbochargers, purifiers): reduced efficiency
        (reflected in reduced pressure ratio / spectral centroid shift),
        moderate vibration, high temperature.
        """
        if asset_type not in ("Turbocharger", "Purifier", "Generator"):
            return 0.0

        score  = 0.0
        rms    = f.get("rms", 0.8)
        td     = f.get("temp_delta", 0.0)
        kurt   = f.get("kurtosis", 3.0)

        # Fouling: higher temperatures, mildly elevated vibration, normal kurtosis
        if td > 8:   score += 2.0
        elif td > 4: score += 1.0

        if 1.0 < rms < 4.0 and kurt < 4:  score += 1.5

        return score

    @staticmethod
    def _score_normal(f: dict) -> float:
        """Baseline 'normal' score — constant anchor."""
        return 0.5

    # ── Softmax normalisation ─────────────────────────────────────────────

    @staticmethod
    def _to_probabilities(scores: dict[str, float]) -> dict[str, float]:
        """Apply temperature-scaled softmax to convert scores → probabilities."""
        temperature = 1.5   # higher T = softer probabilities
        names  = list(scores.keys())
        values = np.array([scores[n] for n in names], dtype=float)

        # Softmax
        shifted = values / temperature
        shifted -= shifted.max()    # numerical stability
        exp_v   = np.exp(shifted)
        probs   = exp_v / exp_v.sum()

        return {n: float(p) for n, p in zip(names, probs)}
