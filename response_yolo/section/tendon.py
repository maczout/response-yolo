"""
Prestressing tendon definitions.

Each tendon is defined by its location, area, and initial prestrain.
"""

from __future__ import annotations

from dataclasses import dataclass

from response_yolo.materials.prestressing import PrestressingSteel


@dataclass
class Tendon:
    """A prestressing tendon or group of strands.

    Parameters
    ----------
    y : float
        Elevation from section bottom (mm).
    area : float
        Total strand area at this location (mm^2).
    material : PrestressingSteel
        Prestressing steel material.
    prestrain : float
        Initial tensile prestrain (positive, e.g. 0.005).
        This is the strain in the tendon after all losses,
        at the zero-load state of the member.
    """

    y: float
    area: float
    material: PrestressingSteel
    prestrain: float = 0.0
