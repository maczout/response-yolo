"""
Reinforcing steel bar definitions.

R2K allows bars to be specified as:
  - Individual bars at specific (y, area) locations
  - Layers (a row of bars at a given depth)

Convention: y is measured from the BOTTOM of the section.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import List, Optional

from response_yolo.materials.steel import ReinforcingSteel


@dataclass
class RebarBar:
    """A single reinforcing bar or group of bars at a point.

    Parameters
    ----------
    y : float
        Elevation from section bottom (mm).
    area : float
        Total bar area at this location (mm^2).
    material : ReinforcingSteel
        Steel material.
    """

    y: float
    area: float
    material: ReinforcingSteel


@dataclass
class RebarLayer:
    """A layer of reinforcing bars.

    Parameters
    ----------
    y : float
        Elevation from section bottom (mm).
    n_bars : int
        Number of bars.
    bar_diameter : float
        Diameter of each bar (mm).
    material : ReinforcingSteel
        Steel material.
    """

    y: float
    n_bars: int
    bar_diameter: float
    material: ReinforcingSteel

    @property
    def bar_area(self) -> float:
        return math.pi / 4.0 * self.bar_diameter ** 2

    @property
    def total_area(self) -> float:
        return self.n_bars * self.bar_area

    def to_bar(self) -> RebarBar:
        """Convert to a single lumped RebarBar."""
        return RebarBar(y=self.y, area=self.total_area, material=self.material)
