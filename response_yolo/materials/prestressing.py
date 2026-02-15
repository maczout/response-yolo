"""
Prestressing steel constitutive model faithful to Response-2000.

Uses the Ramberg-Osgood / power formula commonly adopted in R2K:
    eps = f/Ep + k * (f/fpu)^N
where k and N are fitted so the curve passes through (fpy, epy).

Also supports a simplified bilinear model.

Reference: Collins & Mitchell (1991); Bentz (2000), Chapter 3.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum
from typing import Optional


class PrestressModel(Enum):
    POWER_FORMULA = "power_formula"
    BILINEAR = "bilinear"


@dataclass
class PrestressingSteel:
    """Prestressing strand / wire / bar material.

    Parameters
    ----------
    fpu : float
        Ultimate tensile strength in MPa (e.g. 1860).
    Ep : float
        Elastic modulus in MPa (default 196500 for strand).
    fpy : float, optional
        Yield stress (0.1% offset). Default 0.9*fpu.
    epu : float
        Strain at ultimate stress. Default 0.04.
    model : PrestressModel
        Backbone curve type.
    """

    fpu: float
    Ep: float = 196_500.0
    fpy: Optional[float] = None
    epu: float = 0.04
    model: PrestressModel = PrestressModel.POWER_FORMULA

    # Power-formula parameters (derived)
    _N: float = 0.0
    _k: float = 0.0

    def __post_init__(self) -> None:
        if self.fpu <= 0:
            raise ValueError(f"fpu must be positive, got {self.fpu}")
        if self.fpy is None:
            self.fpy = 0.9 * self.fpu

        # Fit power formula: eps = f/Ep + k*(f/fpu)^N
        # At yield point: epy = fpy/Ep + 0.001 (0.1% offset definition)
        # So k*(fpy/fpu)^N = 0.001
        # At ultimate: epu = fpu/Ep + k  (since (fpu/fpu)^N = 1)
        # So k = epu - fpu/Ep
        self._k = self.epu - self.fpu / self.Ep
        if self._k > 0 and self.fpy < self.fpu:
            ratio = self.fpy / self.fpu
            target = 0.001  # 0.1% offset
            if ratio > 0 and ratio < 1 and target < self._k:
                self._N = math.log(target / self._k) / math.log(ratio)
            else:
                self._N = 7.0  # fallback
        else:
            self._N = 7.0
            self._k = max(self._k, 0.001)

    def stress(self, strain: float) -> float:
        """Return stress for a given strain.

        Prestressing steel is tension-only in R2K; returns 0 for compression.
        """
        if strain <= 0:
            return 0.0
        if strain >= self.epu:
            return 0.0  # ruptured

        if self.model == PrestressModel.BILINEAR:
            return self._bilinear(strain)
        return self._power_formula(strain)

    def tangent(self, strain: float) -> float:
        ds = 1.0e-8
        return (self.stress(strain + ds) - self.stress(strain - ds)) / (2.0 * ds)

    def _power_formula(self, eps: float) -> float:
        """Inverse Ramberg-Osgood solved iteratively.

        eps = f/Ep + k*(f/fpu)^N  =>  solve for f given eps.
        Newton-Raphson iteration.
        """
        # Initial guess: elastic
        f = min(eps * self.Ep, self.fpu * 0.999)
        for _ in range(50):
            ratio = f / self.fpu
            if ratio <= 0:
                ratio = 1e-12
            eps_calc = f / self.Ep + self._k * ratio ** self._N
            deps_df = 1.0 / self.Ep + self._k * self._N * ratio ** (self._N - 1.0) / self.fpu
            residual = eps_calc - eps
            if abs(residual) < 1e-12:
                break
            f -= residual / deps_df
            f = max(0.0, min(f, self.fpu * 0.9999))
        return f

    def _bilinear(self, eps: float) -> float:
        epy = self.fpy / self.Ep + 0.001
        if eps <= epy:
            return self.Ep * eps
        Ep2 = (self.fpu - self.fpy) / (self.epu - epy) if self.epu > epy else 0.0
        return self.fpy + Ep2 * (eps - epy)

    def to_dict(self) -> dict:
        return {
            "type": "prestressing_steel",
            "fpu": self.fpu,
            "Ep": self.Ep,
            "fpy": self.fpy,
            "epu": self.epu,
            "model": self.model.value,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "PrestressingSteel":
        return cls(
            fpu=d["fpu"],
            Ep=d.get("Ep", 196_500.0),
            fpy=d.get("fpy"),
            epu=d.get("epu", 0.04),
            model=PrestressModel(d.get("model", "power_formula")),
        )
