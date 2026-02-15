"""
Concrete constitutive model faithful to Response-2000.

Compression:
  - Hognestad parabola (default for normal-strength)
  - Popovics / Thorenfeldt / Collins curve (default for HSC)
  - Collins & Mitchell 1991 base curve with softening

Tension:
  - Linear-elastic up to cracking
  - MCFT tension-stiffening: f_t = f_cr / (1 + sqrt(500 * eps))
  - Optional linear tension softening for FRC

Sign convention (R2K-compatible):
  - Compression is NEGATIVE strain / stress
  - Tension is POSITIVE strain / stress

Reference: Bentz (2000), Chapter 3; Collins & Mitchell (1991).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class CompressionModel(Enum):
    HOGNESTAD = "hognestad"
    POPOVICS = "popovics"
    COLLINS_MITCHELL = "collins_mitchell"


class TensionModel(Enum):
    MCFT = "mcft"
    LINEAR_CUTOFF = "linear_cutoff"
    NO_TENSION = "no_tension"


@dataclass
class Concrete:
    """Concrete material following Response-2000 constitutive relationships.

    Parameters
    ----------
    fc : float
        Compressive strength in MPa (positive value, e.g. 40.0).
    ec : float, optional
        Strain at peak compressive stress (positive value).
        Default: estimated from fc per Collins & Mitchell.
    Ec : float, optional
        Initial tangent modulus in MPa.
        Default: 3320*sqrt(fc) + 6900 MPa (Collins & Mitchell 1991).
    ft : float, optional
        Tensile strength in MPa.
        Default: 0.33*sqrt(fc) MPa.
    ecu : float
        Ultimate compressive strain (positive value). Default 0.0035.
    compression_model : CompressionModel
        Which compression backbone to use.
    tension_model : TensionModel
        Which tension model to use.
    aggregate_size : float
        Maximum aggregate size in mm (used for crack-spacing calculations).
    density : float
        Concrete density in kg/m^3 (for self-weight, default 2400).
    """

    fc: float
    ec: Optional[float] = None
    Ec: Optional[float] = None
    ft: Optional[float] = None
    ecu: float = 0.0035
    compression_model: CompressionModel = CompressionModel.POPOVICS
    tension_model: TensionModel = TensionModel.MCFT
    aggregate_size: float = 19.0
    density: float = 2400.0

    # Derived quantities (computed in __post_init__)
    _n: float = field(init=False, repr=False, default=0.0)
    _k: float = field(init=False, repr=False, default=0.0)

    def __post_init__(self) -> None:
        if self.fc <= 0:
            raise ValueError(f"fc must be positive, got {self.fc}")

        # Collins & Mitchell (1991) defaults
        if self.Ec is None:
            self.Ec = 3320.0 * math.sqrt(self.fc) + 6900.0
        if self.ft is None:
            self.ft = 0.33 * math.sqrt(self.fc)
        if self.ec is None:
            # ec = fc/Ec * n/(n-1) is implicit; use simple estimate
            self.ec = self.fc / self.Ec * 2.0  # ~= 0.002 for 30 MPa

        # Popovics curve-fitting parameter
        # n = 0.8 + fc/17  (Collins & Mitchell 1991)
        self._n = 0.8 + self.fc / 17.0
        # Post-peak decay factor (Thorenfeldt et al. 1987)
        if self.fc <= 67.0:
            self._k = 1.0
        else:
            self._k = 0.67 + self.fc / 62.0

    @property
    def ecr(self) -> float:
        """Cracking strain."""
        return self.ft / self.Ec

    def stress(self, strain: float) -> float:
        """Return stress (MPa) for a given strain.

        Compression is negative, tension is positive.
        """
        if strain < -self.ecu:
            # Beyond ultimate compressive strain - crushed
            return 0.0
        elif strain < 0:
            return self._compression_stress(-strain)
        elif strain == 0.0:
            return 0.0
        else:
            return self._tension_stress(strain)

    def tangent(self, strain: float) -> float:
        """Return tangent modulus (MPa) at given strain via central difference."""
        ds = 1.0e-8
        s1 = self.stress(strain - ds)
        s2 = self.stress(strain + ds)
        return (s2 - s1) / (2.0 * ds)

    # ------------------------------------------------------------------
    # Compression backbone (strain input is positive magnitude)
    # ------------------------------------------------------------------
    def _compression_stress(self, eps: float) -> float:
        """Return compressive stress as a negative value."""
        if self.compression_model == CompressionModel.POPOVICS:
            return -self._popovics(eps)
        elif self.compression_model == CompressionModel.HOGNESTAD:
            return -self._hognestad(eps)
        elif self.compression_model == CompressionModel.COLLINS_MITCHELL:
            return -self._collins_mitchell(eps)
        raise ValueError(f"Unknown compression model: {self.compression_model}")

    def _popovics(self, eps: float) -> float:
        """Popovics / Thorenfeldt / Collins compression curve.

        f = fc * (eps/ec) * n / (n - 1 + (eps/ec)^(n*k))

        Pre-peak: k = 1.0
        Post-peak: k from Thorenfeldt
        """
        n = self._n
        ratio = eps / self.ec
        if ratio <= 1.0:
            k = 1.0
        else:
            k = self._k
        denom = n - 1.0 + ratio ** (n * k)
        if denom <= 0:
            return 0.0
        return self.fc * ratio * n / denom

    def _hognestad(self, eps: float) -> float:
        """Hognestad parabola.

        Pre-peak:  f = fc * [2*(eps/ec) - (eps/ec)^2]
        Post-peak: linear descent to 0.85*fc at ecu
        """
        ratio = eps / self.ec
        if ratio <= 1.0:
            return self.fc * (2.0 * ratio - ratio * ratio)
        else:
            # Linear descending branch
            slope = 0.15 * self.fc / (self.ecu - self.ec)
            return max(0.0, self.fc - slope * (eps - self.ec))

    def _collins_mitchell(self, eps: float) -> float:
        """Collins & Mitchell 1991 base curve (same as Popovics with k=1)."""
        n = self._n
        ratio = eps / self.ec
        denom = n - 1.0 + ratio ** n
        if denom <= 0:
            return 0.0
        return self.fc * ratio * n / denom

    # ------------------------------------------------------------------
    # Tension
    # ------------------------------------------------------------------
    def _tension_stress(self, eps: float) -> float:
        """Return tensile stress as a positive value."""
        if self.tension_model == TensionModel.NO_TENSION:
            return 0.0

        if eps <= self.ecr:
            # Linear elastic
            return self.Ec * eps

        if self.tension_model == TensionModel.MCFT:
            return self._mcft_tension(eps)
        elif self.tension_model == TensionModel.LINEAR_CUTOFF:
            return 0.0  # immediate drop
        return 0.0

    # ------------------------------------------------------------------
    # Compression softening for MCFT biaxial analysis
    # ------------------------------------------------------------------
    def compression_stress_softened(self, eps_magnitude: float, eps_1: float) -> float:
        """Softened compressive stress per Vecchio & Collins (1986).

        In biaxial tension-compression, transverse tensile strains reduce
        the concrete compressive strength.  The softening factor is:

            beta = 1 / (0.8 + 170 * eps_1)   ≤ 1.0

        The peak stress becomes beta*fc and the peak strain becomes beta*ec.

        Parameters
        ----------
        eps_magnitude : float
            Compressive strain magnitude (positive value).
        eps_1 : float
            Principal tensile strain (positive value).

        Returns
        -------
        float
            Softened compressive stress as a positive magnitude.

        Reference: Vecchio & Collins (1986); Bentz (2000), Chapter 3.
        """
        eps_1 = max(eps_1, 0.0)
        beta = 1.0 / (0.8 + 170.0 * eps_1)
        beta = min(beta, 1.0)
        # Physical minimum — avoid numerical collapse
        beta = max(beta, 0.15)

        # Scale strain to the softened peak and evaluate base curve
        if self.compression_model == CompressionModel.HOGNESTAD:
            base = self._hognestad(eps_magnitude / beta)
        elif self.compression_model == CompressionModel.COLLINS_MITCHELL:
            base = self._collins_mitchell(eps_magnitude / beta)
        else:
            base = self._popovics(eps_magnitude / beta)

        return beta * base

    def _mcft_tension(self, eps: float) -> float:
        """MCFT tension stiffening: f_t = f_cr / (1 + sqrt(500 * eps)).

        Vecchio & Collins (1986), as used in Response-2000.
        """
        return self.ft / (1.0 + math.sqrt(500.0 * eps))

    # ------------------------------------------------------------------
    # Serialization helpers
    # ------------------------------------------------------------------
    def to_dict(self) -> dict:
        return {
            "type": "concrete",
            "fc": self.fc,
            "ec": self.ec,
            "Ec": self.Ec,
            "ft": self.ft,
            "ecu": self.ecu,
            "compression_model": self.compression_model.value,
            "tension_model": self.tension_model.value,
            "aggregate_size": self.aggregate_size,
            "density": self.density,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Concrete":
        return cls(
            fc=d["fc"],
            ec=d.get("ec"),
            Ec=d.get("Ec"),
            ft=d.get("ft"),
            ecu=d.get("ecu", 0.0035),
            compression_model=CompressionModel(d.get("compression_model", "popovics")),
            tension_model=TensionModel(d.get("tension_model", "mcft")),
            aggregate_size=d.get("aggregate_size", 19.0),
            density=d.get("density", 2400.0),
        )
