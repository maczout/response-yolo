"""Cross-section geometry and fibre discretisation.

The section is described as a collection of:
* **concrete layers** – horizontal strips spanning the section width at a
  given depth, and
* **reinforcing bar groups** – discrete bar areas at specified depths.

All depths are measured from the **top of the section** (y = 0 at top,
y increasing downward).  The reference axis for curvature is the centroid of
the *gross* concrete section.

Public API
----------
Section          – high-level description (rect shortcut + arbitrary).
DiscretisedSection – ready-to-analyse fibre model.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from .materials import Concrete, Steel


# ---------------------------------------------------------------------------
# Rebar group
# ---------------------------------------------------------------------------
@dataclass
class RebarGroup:
    """A group of identical bars at the same depth.

    Parameters
    ----------
    area : float   – total bar area in mm².
    depth : float  – distance from section top to bar centroid (mm).
    steel : Steel  – material model.
    label : str    – optional identifier.
    """

    area: float
    depth: float
    steel: Steel
    label: str = ""


# ---------------------------------------------------------------------------
# Concrete layer (for arbitrary shapes)
# ---------------------------------------------------------------------------
@dataclass
class ConcreteLayer:
    """One horizontal slice of concrete.

    Parameters
    ----------
    y_top : float    – depth of slice top from section top (mm).
    y_bot : float    – depth of slice bottom from section top (mm).
    width : float    – width of this slice (mm).
    concrete : Concrete
    """

    y_top: float
    y_bot: float
    width: float
    concrete: Concrete


# ---------------------------------------------------------------------------
# Section definition
# ---------------------------------------------------------------------------
@dataclass
class Section:
    """High-level section description.

    For a simple rectangle use the class method :meth:`rectangle`.
    For arbitrary shapes, pass a list of :class:`ConcreteLayer` objects.
    """

    layers: list[ConcreteLayer] = field(default_factory=list)
    rebar: list[RebarGroup] = field(default_factory=list)

    # convenience ---------------------------------------------------------
    @classmethod
    def rectangle(
        cls,
        width: float,
        height: float,
        concrete: Concrete,
        rebar: list[RebarGroup] | None = None,
    ) -> "Section":
        """Create a rectangular section.

        The rectangle extends from y = 0 (top) to y = *height* (bottom).
        A single :class:`ConcreteLayer` spanning the full depth is created.
        """
        layer = ConcreteLayer(y_top=0.0, y_bot=height, width=width, concrete=concrete)
        return cls(layers=[layer], rebar=rebar or [])

    # geometry helpers ----------------------------------------------------
    @property
    def y_top(self) -> float:
        return min(l.y_top for l in self.layers)

    @property
    def y_bot(self) -> float:
        return max(l.y_bot for l in self.layers)

    @property
    def height(self) -> float:
        return self.y_bot - self.y_top

    def gross_area(self) -> float:
        return sum((l.y_bot - l.y_top) * l.width for l in self.layers)

    def gross_centroid(self) -> float:
        """Depth of gross-section centroid from section top (mm)."""
        a_total = 0.0
        ay_total = 0.0
        for l in self.layers:
            a = (l.y_bot - l.y_top) * l.width
            y_mid = (l.y_top + l.y_bot) / 2.0
            a_total += a
            ay_total += a * y_mid
        if a_total == 0.0:
            return 0.0
        return ay_total / a_total

    def gross_moment_of_inertia(self) -> float:
        """Second moment of area about the gross centroid (mm⁴)."""
        yc = self.gross_centroid()
        I_total = 0.0
        for l in self.layers:
            b = l.width
            h = l.y_bot - l.y_top
            y_mid = (l.y_top + l.y_bot) / 2.0
            I_local = b * h**3 / 12.0
            I_total += I_local + b * h * (y_mid - yc) ** 2
        return I_total


# ---------------------------------------------------------------------------
# Fibre model for analysis
# ---------------------------------------------------------------------------
@dataclass
class ConcreteFibre:
    y: float          # depth of fibre centroid from section top
    area: float       # fibre area (mm²)
    concrete: Concrete


@dataclass
class SteelFibre:
    y: float
    area: float
    steel: Steel
    label: str = ""


@dataclass
class DiscretisedSection:
    """Fibre model of the section ready for analysis."""

    concrete_fibres: list[ConcreteFibre]
    steel_fibres: list[SteelFibre]
    centroid_y: float  # reference axis depth (mm from top)

    @classmethod
    def from_section(cls, section: Section, n_fibres: int = 100) -> "DiscretisedSection":
        """Discretise *section* into fibres.

        Each :class:`ConcreteLayer` is subdivided into roughly equal-thickness
        strips so the total concrete fibre count across all layers is
        approximately *n_fibres*.
        """
        centroid_y = section.gross_centroid()

        # Determine per-layer fibre counts proportional to layer thickness
        total_h = sum(l.y_bot - l.y_top for l in section.layers)
        if total_h == 0:
            raise ValueError("Section has zero depth")

        concrete_fibres: list[ConcreteFibre] = []
        for layer in section.layers:
            h = layer.y_bot - layer.y_top
            n = max(1, round(n_fibres * h / total_h))
            dy = h / n
            for i in range(n):
                y_mid = layer.y_top + dy * (i + 0.5)
                area = layer.width * dy
                concrete_fibres.append(ConcreteFibre(y=y_mid, area=area, concrete=layer.concrete))

        steel_fibres = [
            SteelFibre(y=r.depth, area=r.area, steel=r.steel, label=r.label)
            for r in section.rebar
        ]

        return cls(
            concrete_fibres=concrete_fibres,
            steel_fibres=steel_fibres,
            centroid_y=centroid_y,
        )
