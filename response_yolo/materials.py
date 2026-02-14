"""Material constitutive models for concrete and reinforcing steel.

Concrete compression: Popovics / Thorenfeldt / Collins model.
Concrete tension: linear-elastic up to cracking, then tension-stiffening
    per Collins & Mitchell (1991).
Steel: elastic-perfectly-plastic (with optional strain hardening).

Sign convention throughout this module
---------------------------------------
Compression is **negative** strain / stress.
Tension   is **positive** strain / stress.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Protocol


# ---------------------------------------------------------------------------
# Protocol – any material must expose stress(strain) -> stress
# ---------------------------------------------------------------------------
class Material(Protocol):
    def stress(self, strain: float) -> float: ...  # pragma: no cover


# ---------------------------------------------------------------------------
# Concrete
# ---------------------------------------------------------------------------
@dataclass
class Concrete:
    """Concrete material using Popovics/Thorenfeldt/Collins compression model
    and Collins & Mitchell tension stiffening.

    Parameters
    ----------
    fc : float
        Compressive strength in **MPa** (positive value, e.g. 40).
    ec0 : float | None
        Strain at peak compressive stress (negative value).
        If *None* the Collins–Mitchell estimate ``-fc / (5000 * sqrt(fc))``
        is used (strain in mm/mm when *fc* is in MPa).
    ft : float | None
        Tensile strength in MPa.  If *None*, ``0.33 * sqrt(fc)`` is used.
    Ec : float | None
        Initial tangent modulus in MPa.  If *None*, ``4500 * sqrt(fc)``.
    tension_stiffening : bool
        If True (default) use Collins & Mitchell post-cracking model;
        otherwise concrete carries zero tension after cracking.
    """

    fc: float
    ec0: float | None = None
    ft: float | None = None
    Ec: float | None = None
    tension_stiffening: bool = True

    # Derived (set in __post_init__)
    _fc: float = field(init=False, repr=False)
    _ec0: float = field(init=False, repr=False)
    _ft: float = field(init=False, repr=False)
    _Ec: float = field(init=False, repr=False)
    _ecr: float = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if self.fc <= 0:
            raise ValueError("fc must be positive (compressive strength in MPa)")
        self._fc = self.fc
        sqrt_fc = math.sqrt(self._fc)

        self._Ec = self.Ec if self.Ec is not None else 4500.0 * sqrt_fc
        self._ec0 = self.ec0 if self.ec0 is not None else -(self._fc / (5000.0 * sqrt_fc))
        self._ft = self.ft if self.ft is not None else 0.33 * sqrt_fc
        # Cracking strain
        self._ecr = self._ft / self._Ec

    # ---- public helpers ---------------------------------------------------
    @property
    def elastic_modulus(self) -> float:
        return self._Ec

    # ---- constitutive law -------------------------------------------------
    def stress(self, strain: float) -> float:
        """Return stress (MPa) for a given strain (mm/mm)."""
        if strain <= 0.0:
            return self._compression(strain)
        return self._tension(strain)

    # ---- compression (Popovics / Thorenfeldt / Collins) -------------------
    def _compression(self, strain: float) -> float:
        """Negative strain → negative stress."""
        if strain >= 0.0:
            return 0.0

        fc = self._fc
        ec0 = self._ec0  # negative

        # Thorenfeldt n and k parameters
        n = 0.8 + fc / 17.0
        k = 1.0 if strain >= ec0 else 0.67 + fc / 62.0

        eta = strain / ec0  # positive ratio (both negative)
        denom = (n - 1.0) + eta ** (n * k)
        if denom == 0.0:
            return 0.0
        stress = -fc * (n * eta) / denom
        # Limit to prevent numerical issues at very large strains
        if stress > 0.0:
            stress = 0.0
        return stress

    # ---- tension ----------------------------------------------------------
    def _tension(self, strain: float) -> float:
        """Positive strain → positive stress."""
        if strain <= 0.0:
            return 0.0

        ecr = self._ecr
        ft = self._ft

        if strain <= ecr:
            # Linear elastic
            return self._Ec * strain

        if not self.tension_stiffening:
            return 0.0

        # Collins & Mitchell tension stiffening: ft / (1 + sqrt(200 * strain))
        # (strain in mm/mm; the 200 factor assumes this unit system)
        return ft / (1.0 + math.sqrt(200.0 * strain))


# ---------------------------------------------------------------------------
# Reinforcing steel
# ---------------------------------------------------------------------------
@dataclass
class Steel:
    """Reinforcing steel – elastic-perfectly-plastic with optional
    linear strain hardening.

    Parameters
    ----------
    fy : float
        Yield strength (MPa, positive).
    Es : float
        Elastic modulus (MPa), default 200 000.
    fu : float | None
        Ultimate strength (MPa).  If provided, linear hardening from
        *ey_sh* to *esu* is used.
    esh : float
        Strain at onset of strain hardening (positive). Default 0.01.
    esu : float
        Ultimate strain (positive). Default 0.10.
    """

    fy: float
    Es: float = 200_000.0
    fu: float | None = None
    esh: float = 0.01
    esu: float = 0.10

    # Derived
    _ey: float = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if self.fy <= 0:
            raise ValueError("fy must be positive")
        self._ey = self.fy / self.Es

    @property
    def elastic_modulus(self) -> float:
        return self.Es

    def stress(self, strain: float) -> float:
        """Return stress for a given strain.  Works for both signs."""
        sign = 1.0 if strain >= 0.0 else -1.0
        eps = abs(strain)
        ey = self._ey
        fy = self.fy

        if eps <= ey:
            return sign * self.Es * eps

        if self.fu is not None and eps > self.esh:
            if eps >= self.esu:
                return sign * self.fu
            # Linear hardening
            return sign * (fy + (self.fu - fy) * (eps - self.esh) / (self.esu - self.esh))

        # Perfectly plastic plateau (or no hardening defined)
        return sign * fy
