"""
Moment-Curvature (M-phi) sectional analysis — the core of Response-2000.

Algorithm (faithful to Bentz 2000, Chapter 4):
==============================================

For each curvature increment phi_i:

  1. Assume a strain profile:  eps(y) = eps_0 + phi * (y - y_ref)
     where eps_0 is the strain at the reference axis and phi is curvature.

  2. For each concrete layer and reinforcement location, compute strain
     from the assumed linear profile (plane sections remain plane).

  3. Compute stress from the material constitutive model.

  4. Integrate stresses over the section to get axial force N and moment M.

  5. Iterate eps_0 using Newton-Raphson so that N = N_applied
     (for pure bending, N_applied = 0; for combined loading, N_applied is given).

  6. Record the converged (phi, M) point.

  7. Check failure criteria:
     - Any concrete layer exceeds ecu (crushing)
     - Any rebar exceeds esu (fracture)
     - Any tendon exceeds epu (rupture)

  8. Increment phi and repeat until failure or user-defined limit.

The analysis also tracks:
  - Cracking moment and curvature
  - Yield moment and curvature (first rebar yield)
  - Ultimate moment and curvature
  - Neutral axis depth at each step
  - Strain profiles at each step

Sign convention:
  - Positive curvature = sagging (tension at bottom)
  - Positive moment = sagging
  - Positive axial force = tension
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import List, Optional

from response_yolo.section.cross_section import CrossSection


@dataclass
class MPhiPoint:
    """A single point on the moment-curvature response."""

    curvature: float  # 1/mm
    moment: float  # N-mm
    eps_0: float  # strain at reference axis
    neutral_axis_y: float  # y-coordinate of zero strain (from bottom)
    converged: bool = True

    @property
    def moment_kNm(self) -> float:
        """Moment in kN-m."""
        return self.moment / 1.0e6


@dataclass
class MPhiResult:
    """Full moment-curvature analysis result."""

    points: List[MPhiPoint] = field(default_factory=list)
    axial_load: float = 0.0  # applied axial load (N)
    y_ref: float = 0.0  # reference axis y

    # Key points (indices into self.points)
    cracking_index: Optional[int] = None
    yield_index: Optional[int] = None
    ultimate_index: Optional[int] = None
    failure_reason: str = ""

    @property
    def curvatures(self) -> List[float]:
        return [p.curvature for p in self.points]

    @property
    def moments(self) -> List[float]:
        return [p.moment for p in self.points]

    @property
    def moments_kNm(self) -> List[float]:
        return [p.moment_kNm for p in self.points]

    @property
    def cracking_moment(self) -> Optional[float]:
        if self.cracking_index is not None:
            return self.points[self.cracking_index].moment
        return None

    @property
    def yield_moment(self) -> Optional[float]:
        if self.yield_index is not None:
            return self.points[self.yield_index].moment
        return None

    @property
    def ultimate_moment(self) -> Optional[float]:
        if self.ultimate_index is not None:
            return self.points[self.ultimate_index].moment
        return None

    def to_dict(self) -> dict:
        """Serialize to dictionary matching the output spec format.

        Units in control curves follow the output spec:
        - curvature: mrad/m (raw 1/mm × 1e6)
        - moment: kNm (raw N·mm ÷ 1e6)
        - axial_strain: mm/m (raw × 1e3)
        """
        converged_pts = [p for p in self.points if p.converged]
        return {
            "control_curves": {
                "moment_curvature": {
                    "description": "Moment vs Curvature",
                    "x_axis": "curvature",
                    "y_axis": "moment",
                    "data": [
                        {
                            "curvature": p.curvature * 1e6,   # mrad/m
                            "moment": p.moment / 1e6,         # kNm
                        }
                        for p in self.points
                        if p.converged
                    ],
                },
                "moment_axial_strain": {
                    "description": "Moment vs Reference Axial Strain",
                    "x_axis": "axial_strain",
                    "y_axis": "moment",
                    "data": [
                        {
                            "axial_strain": p.eps_0 * 1e3,    # mm/m
                            "moment": p.moment / 1e6,         # kNm
                        }
                        for p in self.points
                        if p.converged
                    ],
                },
            },
            "analysis_points": [],  # stub — to be populated in future phases
            "summary": {
                "section_behavior": {
                    "cracking_moment": self.cracking_moment / 1e6 if self.cracking_moment else None,
                    "yield_moment": self.yield_moment / 1e6 if self.yield_moment else None,
                    "ultimate_moment": self.ultimate_moment / 1e6 if self.ultimate_moment else None,
                },
                "failure": {
                    "mode": self.failure_reason or None,
                },
                "convergence": {
                    "total_points": len(self.points),
                    "converged_points": len(converged_pts),
                },
            },
            "response": [
                {
                    "curvature_1_per_mm": p.curvature,
                    "curvature_1_per_m": p.curvature * 1000.0,
                    "moment_Nmm": p.moment,
                    "moment_kNm": p.moment_kNm,
                    "eps_0": p.eps_0,
                    "neutral_axis_y_mm": p.neutral_axis_y,
                    "converged": p.converged,
                }
                for p in self.points
            ],
        }


class MomentCurvatureAnalysis:
    """Perform a sectional moment-curvature analysis (R2K-style).

    Parameters
    ----------
    section : CrossSection
        The composite cross-section to analyse.
    axial_load : float
        Applied axial load in N (positive = tension). Default 0.
    max_curvature : float, optional
        Maximum curvature (1/mm) to analyse to. Default: auto-detect.
    n_steps : int
        Number of curvature increments. Default 200.
    curvature_step : float, optional
        If given, overrides n_steps.
    y_ref : float, optional
        Reference axis. Default: section centroid.
    tol_force : float
        Convergence tolerance on axial force equilibrium (N). Default 1.0.
    max_iter : int
        Max Newton-Raphson iterations per step. Default 50.
    """

    def __init__(
        self,
        section: CrossSection,
        axial_load: float = 0.0,
        max_curvature: Optional[float] = None,
        n_steps: int = 200,
        curvature_step: Optional[float] = None,
        y_ref: Optional[float] = None,
        tol_force: float = 1.0,
        max_iter: int = 50,
    ) -> None:
        self.section = section
        self.axial_load = axial_load
        self.n_steps = n_steps
        self.curvature_step = curvature_step
        self.tol_force = tol_force
        self.max_iter = max_iter

        # Reference axis defaults to centroid
        self.y_ref = y_ref if y_ref is not None else section.centroid_y

        # Auto-detect reasonable max curvature if not given
        if max_curvature is not None:
            self.max_curvature = max_curvature
        else:
            # Rough estimate: ecu / (0.1 * h)
            h = section.height
            if h > 0:
                self.max_curvature = 0.0035 / (0.1 * h)
            else:
                self.max_curvature = 1.0e-4

    def run(self) -> MPhiResult:
        """Execute the moment-curvature analysis.

        Returns
        -------
        MPhiResult
            The complete M-phi response.
        """
        result = MPhiResult(axial_load=self.axial_load, y_ref=self.y_ref)

        # Build curvature vector
        if self.curvature_step is not None:
            n = int(self.max_curvature / self.curvature_step) + 1
            phis = [i * self.curvature_step for i in range(1, n + 1)]
        else:
            dphi = self.max_curvature / self.n_steps
            phis = [i * dphi for i in range(1, self.n_steps + 1)]

        eps_0 = 0.0  # initial guess for centroidal strain
        prev_cracked = False
        prev_yielded = False

        for phi in phis:
            # Newton-Raphson to find eps_0 that satisfies N = N_applied
            converged = False
            for iteration in range(self.max_iter):
                N, M = self.section.integrate_forces(eps_0, phi, self.y_ref)
                residual = N - self.axial_load

                if abs(residual) < self.tol_force:
                    converged = True
                    break

                EA, ES, EI = self.section.integrate_stiffness(eps_0, phi, self.y_ref)
                if abs(EA) < 1e-6:
                    # Section has lost all stiffness — failure
                    break
                eps_0 -= residual / EA

            # Re-compute final forces
            N, M = self.section.integrate_forces(eps_0, phi, self.y_ref)

            # Compute neutral axis location
            # eps(y) = eps_0 - phi*(y - y_ref) = 0  =>  y = y_ref + eps_0/phi
            if abs(phi) > 1e-20:
                na_y = self.y_ref + eps_0 / phi
            else:
                na_y = float('inf')

            point = MPhiPoint(
                curvature=phi,
                moment=M,
                eps_0=eps_0,
                neutral_axis_y=na_y,
                converged=converged,
            )
            result.points.append(point)

            # --- Detect key events ---

            # Cracking detection
            if result.cracking_index is None and not prev_cracked:
                cracked = self._check_cracking(eps_0, phi)
                if cracked:
                    result.cracking_index = len(result.points) - 1
                    prev_cracked = True

            # Yield detection
            if result.yield_index is None and not prev_yielded:
                yielded = self._check_yield(eps_0, phi)
                if yielded:
                    result.yield_index = len(result.points) - 1
                    prev_yielded = True

            # Failure detection
            failure = self._check_failure(eps_0, phi)
            if failure:
                result.ultimate_index = len(result.points) - 1
                result.failure_reason = failure
                break

            if not converged:
                result.ultimate_index = len(result.points) - 1
                result.failure_reason = "convergence_failure"
                break

        # If we reached max curvature without failure, ultimate = last point
        if result.ultimate_index is None and result.points:
            result.ultimate_index = len(result.points) - 1

        return result

    # ------------------------------------------------------------------
    # Event detection helpers
    # ------------------------------------------------------------------
    def _check_cracking(self, eps_0: float, phi: float) -> bool:
        """Check if any concrete layer has cracked (tensile strain > ecr)."""
        for lay in self.section.concrete_layers:
            eps = eps_0 - phi * (lay.y_mid - self.y_ref)
            if eps > lay.material.ecr:
                return True
        return False

    def _check_yield(self, eps_0: float, phi: float) -> bool:
        """Check if any rebar has yielded."""
        for bar in self.section.rebars:
            eps = eps_0 - phi * (bar.y - self.y_ref)
            if abs(eps) >= bar.material.ey:
                return True
        return False

    def _check_failure(self, eps_0: float, phi: float) -> str:
        """Check failure criteria. Returns failure reason or empty string."""
        # Concrete crushing
        for lay in self.section.concrete_layers:
            eps = eps_0 - phi * (lay.y_mid - self.y_ref)
            if eps < -lay.material.ecu:
                return "concrete_crushing"

        # Rebar fracture
        for bar in self.section.rebars:
            eps = eps_0 - phi * (bar.y - self.y_ref)
            if abs(eps) >= bar.material.esu:
                return "rebar_fracture"

        # Tendon rupture
        for t in self.section.tendons:
            eps = eps_0 - phi * (t.y - self.y_ref) + t.prestrain
            if eps >= t.material.epu:
                return "tendon_rupture"

        return ""
