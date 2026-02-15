"""
Section geometry definitions and concrete layer discretisation.

Response-2000 discretises the cross-section into horizontal layers (fibres)
for the layered analysis.  Each layer has:
  - y_mid   : distance from the section reference axis (bottom by default)
  - width   : layer width at that elevation
  - thickness: layer thickness (height)
  - area    : width * thickness
  - material: reference to a Concrete material

The reference axis is at the BOTTOM of the section (y = 0) by convention,
matching R2K.

Supported section shapes:
  - Rectangular
  - Tee / inverted-Tee / L-shape
  - Circular
  - Generic (user-defined width-vs-depth profile)
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import List, Optional

from response_yolo.materials.concrete import Concrete

# Avoid circular import — steel is only needed at runtime for type hints
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from response_yolo.materials.steel import ReinforcingSteel


@dataclass
class ConcreteLayer:
    """A single horizontal concrete fibre (layer).

    Attributes
    ----------
    y_bot : float
        Y-coordinate of the bottom of this layer (from section bottom).
    y_top : float
        Y-coordinate of the top of this layer.
    width : float
        Width of the layer.
    material : Concrete
        Concrete material for this layer.
    rho_y : float
        Transverse (shear) reinforcement ratio Av/(b*s) at this layer.
        Default 0.0 (no stirrups).  Used by MCFT biaxial analysis.
    stirrup_material : ReinforcingSteel or None
        Material for transverse reinforcement.  None means no stirrups.
    """

    y_bot: float
    y_top: float
    width: float
    material: Concrete
    rho_y: float = 0.0
    stirrup_material: Optional["ReinforcingSteel"] = None

    @property
    def y_mid(self) -> float:
        return 0.5 * (self.y_bot + self.y_top)

    @property
    def thickness(self) -> float:
        return self.y_top - self.y_bot

    @property
    def area(self) -> float:
        return self.width * self.thickness


class _SectionShape:
    """Base class for section shapes — provides layer generation."""

    def width_at(self, y: float) -> float:
        """Return section width at elevation y (from bottom)."""
        raise NotImplementedError

    @property
    def height(self) -> float:
        raise NotImplementedError

    def discretise(self, material: Concrete, n_layers: int = 100) -> List[ConcreteLayer]:
        """Slice the section into n_layers horizontal concrete layers."""
        h = self.height
        t = h / n_layers
        layers = []
        for i in range(n_layers):
            y_bot = i * t
            y_top = (i + 1) * t
            y_mid = 0.5 * (y_bot + y_top)
            w = self.width_at(y_mid)
            if w > 0:
                layers.append(ConcreteLayer(y_bot=y_bot, y_top=y_top, width=w, material=material))
        return layers


@dataclass
class RectangularSection(_SectionShape):
    """Simple rectangular cross-section.

    Parameters
    ----------
    b : float  – width (mm)
    h : float  – total height (mm)
    """

    b: float
    h: float

    @property
    def height(self) -> float:
        return self.h

    def width_at(self, y: float) -> float:
        if 0 <= y <= self.h:
            return self.b
        return 0.0


@dataclass
class TeeSection(_SectionShape):
    """Tee (or inverted-Tee) section.

    Parameters
    ----------
    bw : float – web width
    hw : float – web height (below flange)
    bf : float – flange width
    hf : float – flange thickness
    """

    bw: float
    hw: float
    bf: float
    hf: float

    @property
    def height(self) -> float:
        return self.hw + self.hf

    def width_at(self, y: float) -> float:
        if y < 0 or y > self.height:
            return 0.0
        if y <= self.hw:
            return self.bw
        return self.bf


@dataclass
class CircularSection(_SectionShape):
    """Circular cross-section.

    Parameters
    ----------
    diameter : float – outer diameter (mm)
    """

    diameter: float

    @property
    def height(self) -> float:
        return self.diameter

    def width_at(self, y: float) -> float:
        r = self.diameter / 2.0
        dy = y - r  # distance from centre
        if abs(dy) >= r:
            return 0.0
        return 2.0 * math.sqrt(r * r - dy * dy)


@dataclass
class GenericSection(_SectionShape):
    """User-defined section via a width-vs-y profile.

    Parameters
    ----------
    profile : list of (y, width) tuples, sorted ascending by y.
    """

    profile: List[tuple]  # [(y0, w0), (y1, w1), ...]

    def __post_init__(self) -> None:
        self.profile.sort(key=lambda p: p[0])

    @property
    def height(self) -> float:
        return self.profile[-1][0] - self.profile[0][0]

    def width_at(self, y: float) -> float:
        pts = self.profile
        if y <= pts[0][0]:
            return pts[0][1]
        if y >= pts[-1][0]:
            return pts[-1][1]
        # Linear interpolation
        for i in range(len(pts) - 1):
            y0, w0 = pts[i]
            y1, w1 = pts[i + 1]
            if y0 <= y <= y1:
                t = (y - y0) / (y1 - y0)
                return w0 + t * (w1 - w0)
        return 0.0
