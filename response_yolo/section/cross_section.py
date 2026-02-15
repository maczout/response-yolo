"""
CrossSection: the assembled composite cross-section for analysis.

Aggregates concrete layers, rebar bars, and tendons into one object
that the analysis engine operates on.  This is the R2K "section" concept.

Key responsibilities:
  - Hold geometry + material assignments
  - Compute section centroid and gross properties (Ig, Ag, etc.)
  - Provide force/moment integration for a given strain profile
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from response_yolo.section.geometry import ConcreteLayer, _SectionShape
from response_yolo.section.rebar import RebarBar, RebarLayer
from response_yolo.section.tendon import Tendon
from response_yolo.materials.concrete import Concrete


@dataclass
class CrossSection:
    """Composite reinforced/prestressed concrete cross-section.

    Build one by providing a shape + material, then adding reinforcement:

        shape = RectangularSection(b=300, h=500)
        conc = Concrete(fc=35)
        xs = CrossSection.from_shape(shape, conc, n_layers=80)
        xs.add_rebar(RebarBar(y=50, area=1500, material=steel))
        xs.add_rebar(RebarBar(y=450, area=1500, material=steel))

    Parameters
    ----------
    concrete_layers : list of ConcreteLayer
    rebars : list of RebarBar
    tendons : list of Tendon
    """

    concrete_layers: List[ConcreteLayer] = field(default_factory=list)
    rebars: List[RebarBar] = field(default_factory=list)
    tendons: List[Tendon] = field(default_factory=list)

    # ------------------------------------------------------------------
    # Constructors
    # ------------------------------------------------------------------
    @classmethod
    def from_shape(
        cls,
        shape: _SectionShape,
        material: Concrete,
        n_layers: int = 100,
    ) -> "CrossSection":
        """Create a CrossSection by discretising a shape into layers."""
        layers = shape.discretise(material, n_layers)
        return cls(concrete_layers=layers)

    # ------------------------------------------------------------------
    # Adding reinforcement
    # ------------------------------------------------------------------
    def add_rebar(self, bar: RebarBar) -> None:
        self.rebars.append(bar)

    def add_rebar_layer(self, layer: RebarLayer) -> None:
        self.rebars.append(layer.to_bar())

    def add_tendon(self, tendon: Tendon) -> None:
        self.tendons.append(tendon)

    # ------------------------------------------------------------------
    # Gross section properties
    # ------------------------------------------------------------------
    @property
    def height(self) -> float:
        if not self.concrete_layers:
            return 0.0
        return self.concrete_layers[-1].y_top - self.concrete_layers[0].y_bot

    @property
    def y_bottom(self) -> float:
        if not self.concrete_layers:
            return 0.0
        return self.concrete_layers[0].y_bot

    @property
    def y_top(self) -> float:
        if not self.concrete_layers:
            return 0.0
        return self.concrete_layers[-1].y_top

    @property
    def gross_area(self) -> float:
        """Gross concrete area (ignoring reinforcement)."""
        return sum(lay.area for lay in self.concrete_layers)

    @property
    def centroid_y(self) -> float:
        """Y-coordinate of gross concrete centroid from section bottom."""
        total_Ay = sum(lay.area * lay.y_mid for lay in self.concrete_layers)
        total_A = self.gross_area
        if total_A == 0:
            return 0.0
        return total_Ay / total_A

    @property
    def gross_moment_of_inertia(self) -> float:
        """Gross (uncracked, unreinforced) moment of inertia about centroid."""
        yc = self.centroid_y
        Ig = 0.0
        for lay in self.concrete_layers:
            # Parallel axis theorem per layer
            Ig += lay.width * lay.thickness ** 3 / 12.0
            Ig += lay.area * (lay.y_mid - yc) ** 2
        return Ig

    # ------------------------------------------------------------------
    # Transformed section properties
    # ------------------------------------------------------------------
    @property
    def transformed_area(self) -> float:
        """Transformed area (concrete + n*As)."""
        Ag = self.gross_area
        # Use first layer's Ec as reference
        if not self.concrete_layers:
            return 0.0
        Ec = self.concrete_layers[0].material.Ec
        for bar in self.rebars:
            n = bar.material.Es / Ec
            Ag += (n - 1.0) * bar.area
        for t in self.tendons:
            n = t.material.Ep / Ec
            Ag += (n - 1.0) * t.area
        return Ag

    # ------------------------------------------------------------------
    # Force/moment integration for a given strain profile
    # ------------------------------------------------------------------
    def integrate_forces(
        self, eps_0: float, phi: float, y_ref: float
    ) -> tuple:
        """Compute axial force and moment for a linear strain profile.

        Strain at elevation y:  eps(y) = eps_0 - phi * (y - y_ref)

        Positive curvature = sagging (compression at top, tension at bottom).
        This matches the R2K convention where positive phi curves the
        beam concave-up.

        Parameters
        ----------
        eps_0 : float
            Strain at the reference axis.
        phi : float
            Curvature (1/mm).  Positive = sagging.
        y_ref : float
            Y-coordinate of the reference axis (typically centroid).

        Returns
        -------
        N : float
            Axial force (positive = tension).  Units: N if stress in MPa and area in mm^2.
        M : float
            Bending moment about y_ref (positive = sagging / tension at bottom).
        """
        N = 0.0
        M = 0.0

        # Concrete layers
        for lay in self.concrete_layers:
            dy = lay.y_mid - y_ref
            eps = eps_0 - phi * dy
            sig = lay.material.stress(eps)
            f = sig * lay.area
            N += f
            M -= f * dy  # M = -sum(f * dy) so tension at bottom → positive M

        # Reinforcing bars
        for bar in self.rebars:
            dy = bar.y - y_ref
            eps = eps_0 - phi * dy
            sig = bar.material.stress(eps)
            f = sig * bar.area
            N += f
            M -= f * dy

        # Tendons (add prestrain)
        for t in self.tendons:
            dy = t.y - y_ref
            eps = eps_0 - phi * dy + t.prestrain
            sig = t.material.stress(eps)
            f = sig * t.area
            N += f
            M -= f * dy

        return N, M

    def integrate_stiffness(
        self, eps_0: float, phi: float, y_ref: float
    ) -> tuple:
        """Compute tangent stiffness [EA, ES, EI] for Newton-Raphson.

        Consistent with strain convention:  eps(y) = eps_0 - phi * (y - y_ref)

        Returns
        -------
        EA : float  – dN/d(eps_0)
        ES : float  – coupling: dN/d(phi)
        EI : float  – dM/d(phi)
        """
        EA = 0.0
        ES = 0.0
        EI = 0.0

        for lay in self.concrete_layers:
            dy = lay.y_mid - y_ref
            eps = eps_0 - phi * dy
            Et = lay.material.tangent(eps)
            ea = Et * lay.area
            EA += ea
            ES -= ea * dy       # dN/dphi = sum(Et*A * d(eps)/d(phi)) = sum(Et*A*(-dy))
            EI += ea * dy * dy  # dM/dphi = sum(Et*A*dy * d(eps)/d(phi)*(-dy)/(-1)) = sum(Et*A*dy^2)

        for bar in self.rebars:
            dy = bar.y - y_ref
            eps = eps_0 - phi * dy
            Et = bar.material.tangent(eps)
            ea = Et * bar.area
            EA += ea
            ES -= ea * dy
            EI += ea * dy * dy

        for t in self.tendons:
            dy = t.y - y_ref
            eps = eps_0 - phi * dy + t.prestrain
            Et = t.material.tangent(eps)
            ea = Et * t.area
            EA += ea
            ES -= ea * dy
            EI += ea * dy * dy

        return EA, ES, EI

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------
    def to_dict(self) -> dict:
        return {
            "concrete_layers": [
                {
                    "y_bot": l.y_bot,
                    "y_top": l.y_top,
                    "width": l.width,
                    "material": l.material.to_dict(),
                }
                for l in self.concrete_layers
            ],
            "rebars": [
                {"y": b.y, "area": b.area, "material": b.material.to_dict()}
                for b in self.rebars
            ],
            "tendons": [
                {
                    "y": t.y,
                    "area": t.area,
                    "material": t.material.to_dict(),
                    "prestrain": t.prestrain,
                }
                for t in self.tendons
            ],
        }
