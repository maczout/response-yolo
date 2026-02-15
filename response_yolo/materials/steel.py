"""
Reinforcing steel constitutive model faithful to Response-2000.

Supports:
  - Bilinear (elastic-perfectly-plastic or with strain hardening)
  - Trilinear (elastic, yield plateau, strain hardening)
  - Menegotto-Pinto for cyclic (stub — monotonic only for now)

Sign convention: tension positive, compression negative (symmetric).

Reference: Bentz (2000), Chapter 3.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class SteelModel(Enum):
    BILINEAR = "bilinear"
    TRILINEAR = "trilinear"


@dataclass
class ReinforcingSteel:
    """Reinforcing steel bar material.

    Parameters
    ----------
    fy : float
        Yield stress in MPa.
    Es : float
        Elastic modulus in MPa (default 200000).
    fu : float, optional
        Ultimate stress in MPa. Default = fy (perfectly plastic).
    esh : float, optional
        Strain at onset of strain hardening. Default = 5 * ey.
    esu : float, optional
        Strain at ultimate stress. Default 0.05.
    model : SteelModel
        Backbone model. Default TRILINEAR.
    """

    fy: float
    Es: float = 200_000.0
    fu: Optional[float] = None
    esh: Optional[float] = None
    esu: float = 0.05
    model: SteelModel = SteelModel.TRILINEAR

    def __post_init__(self) -> None:
        if self.fy <= 0:
            raise ValueError(f"fy must be positive, got {self.fy}")
        if self.fu is None:
            self.fu = self.fy
        if self.esh is None:
            self.esh = self.ey * 5.0

    @property
    def ey(self) -> float:
        """Yield strain."""
        return self.fy / self.Es

    def stress(self, strain: float) -> float:
        """Return stress for given strain (symmetric in tension/compression)."""
        eps = abs(strain)
        sign = 1.0 if strain >= 0 else -1.0

        if eps >= self.esu:
            # Fractured — return zero (R2K behaviour)
            return 0.0

        if self.model == SteelModel.BILINEAR:
            s = self._bilinear(eps)
        else:
            s = self._trilinear(eps)

        return sign * s

    def tangent(self, strain: float) -> float:
        """Tangent modulus via central difference."""
        ds = 1.0e-8
        return (self.stress(strain + ds) - self.stress(strain - ds)) / (2.0 * ds)

    def _bilinear(self, eps: float) -> float:
        if eps <= self.ey:
            return self.Es * eps
        # Strain hardening slope
        Esh = (self.fu - self.fy) / (self.esu - self.ey) if self.esu > self.ey else 0.0
        return self.fy + Esh * (eps - self.ey)

    def _trilinear(self, eps: float) -> float:
        if eps <= self.ey:
            return self.Es * eps
        if eps <= self.esh:
            return self.fy  # yield plateau
        # Strain-hardening branch (parabolic per R2K)
        # R2K uses a parabolic hardening curve:
        #   f = fu - (fu - fy) * ((esu - eps) / (esu - esh))^p
        # With p chosen so the curve passes through (esh, fy) and (esu, fu).
        # For the classic R2K shape, p = 2 is a good default.
        if self.esu <= self.esh:
            return self.fy
        ratio = (eps - self.esh) / (self.esu - self.esh)
        # Parabolic hardening (R2K style)
        return self.fy + (self.fu - self.fy) * (2.0 * ratio - ratio * ratio)

    def to_dict(self) -> dict:
        return {
            "type": "reinforcing_steel",
            "fy": self.fy,
            "Es": self.Es,
            "fu": self.fu,
            "esh": self.esh,
            "esu": self.esu,
            "model": self.model.value,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "ReinforcingSteel":
        return cls(
            fy=d["fy"],
            Es=d.get("Es", 200_000.0),
            fu=d.get("fu"),
            esh=d.get("esh"),
            esu=d.get("esu", 0.05),
            model=SteelModel(d.get("model", "trilinear")),
        )
