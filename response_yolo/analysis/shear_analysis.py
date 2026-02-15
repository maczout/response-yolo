"""
Sectional shear analysis using the Modified Compression Field Theory.

Produces V-gamma (shear force vs. average shear strain) response curves
by incrementing the average shear strain γ_xy0 and solving for equilibrium
at each step using Newton-Raphson iteration.

At each load step:
  1. Prescribe gamma_xy0 (the shear strain DOF)
  2. Newton-Raphson on (eps_0, phi) to satisfy N = N_applied, M = M_applied
  3. Compute V from MCFT-integrated shear stresses
  4. Record the converged (gamma_xy0, V) point
  5. Check for failure (concrete crushing, crack slip, etc.)

Reference: Bentz (2000), Chapter 7; Vecchio & Collins (1986).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from response_yolo.section.cross_section import CrossSection


@dataclass
class VGammaPoint:
    """A single point on the V-gamma response curve."""

    gamma_xy0: float     # average shear strain
    shear_force: float   # V (N)
    moment: float        # M at this step (N·mm)
    eps_0: float         # converged centroidal strain
    curvature: float     # converged curvature (1/mm)
    converged: bool = True


@dataclass
class VGammaResult:
    """Result of a V-gamma shear analysis."""

    points: List[VGammaPoint] = field(default_factory=list)

    @property
    def peak_shear(self) -> float:
        """Maximum shear force achieved."""
        if not self.points:
            return 0.0
        return max(abs(p.shear_force) for p in self.points)

    @property
    def gamma_at_peak(self) -> float:
        """Shear strain at peak shear force."""
        if not self.points:
            return 0.0
        peak_pt = max(self.points, key=lambda p: abs(p.shear_force))
        return peak_pt.gamma_xy0


class ShearAnalysis:
    """Sectional shear analysis using MCFT.

    Discretises the section into biaxial layers, solves the MCFT
    equilibrium/compatibility/constitutive equations at each layer,
    and integrates to get total V for a given gamma (shear strain).

    Reference: Vecchio & Collins (1986); Bentz (2000), Chapters 3-4, 6-7.
    """

    def __init__(
        self,
        section: CrossSection,
        axial_load: float = 0.0,
        moment: float = 0.0,
        y_ref: Optional[float] = None,
        gamma_max: float = 0.01,
        n_steps: int = 50,
        max_iter: int = 30,
        tol_force: float = 1.0,
        tol_moment: float = 100.0,
    ) -> None:
        """
        Parameters
        ----------
        section : CrossSection
            The cross-section (must have stirrups set via set_stirrups).
        axial_load : float
            Applied axial force N (positive = tension), in Newtons.
        moment : float
            Applied bending moment M (positive = sagging), in N·mm.
        y_ref : float, optional
            Reference axis. Defaults to section centroid.
        gamma_max : float
            Maximum shear strain to sweep to.
        n_steps : int
            Number of shear strain increments.
        max_iter : int
            Max Newton-Raphson iterations per step.
        tol_force : float
            Convergence tolerance on axial force residual (N).
        tol_moment : float
            Convergence tolerance on moment residual (N·mm).
        """
        self.section = section
        self.axial_load = axial_load
        self.moment = moment
        self.y_ref = y_ref if y_ref is not None else section.centroid_y
        self.gamma_max = gamma_max
        self.n_steps = n_steps
        self.max_iter = max_iter
        self.tol_force = tol_force
        self.tol_moment = tol_moment

    def run(self) -> VGammaResult:
        """Run the V-gamma analysis.

        Returns
        -------
        VGammaResult
            The complete V-gamma response curve.
        """
        result = VGammaResult()
        sec = self.section
        y_ref = self.y_ref

        # Start from zero shear strain
        eps_0 = 0.0
        phi = 0.0

        d_gamma = self.gamma_max / self.n_steps

        for step in range(self.n_steps + 1):
            gamma_xy0 = step * d_gamma

            # Newton-Raphson to find (eps_0, phi) satisfying N and M equilibrium
            converged = False
            for _it in range(self.max_iter):
                N, M, V = sec.integrate_forces_shear(
                    eps_0, phi, gamma_xy0, y_ref
                )

                res_N = N - self.axial_load
                res_M = M - self.moment

                if abs(res_N) < self.tol_force and abs(res_M) < self.tol_moment:
                    converged = True
                    break

                # Get 3×3 stiffness, extract 2×2 sub-block for [eps_0, phi]
                J = sec.integrate_stiffness_3x3(eps_0, phi, gamma_xy0, y_ref)

                # 2×2 system: [dN/de0, dN/dphi; dM/de0, dM/dphi]
                a11 = J[0][0]
                a12 = J[0][1]
                a21 = J[1][0]
                a22 = J[1][1]

                det = a11 * a22 - a12 * a21
                if abs(det) < 1e-20:
                    break  # Singular — section has failed

                # Solve 2×2: [de0, dphi] = inv(J_2x2) * [-res_N, -res_M]
                d_eps0 = (-a22 * res_N + a12 * res_M) / det
                d_phi = (a21 * res_N - a11 * res_M) / det

                # Limit step size
                max_de = 0.001
                max_dp = 1e-4  # 1/mm
                if abs(d_eps0) > max_de:
                    d_eps0 = max_de * (1.0 if d_eps0 > 0 else -1.0)
                if abs(d_phi) > max_dp:
                    d_phi = max_dp * (1.0 if d_phi > 0 else -1.0)

                eps_0 += d_eps0
                phi += d_phi

            # Record this step
            if converged:
                N, M, V = sec.integrate_forces_shear(
                    eps_0, phi, gamma_xy0, y_ref
                )
            result.points.append(VGammaPoint(
                gamma_xy0=gamma_xy0,
                shear_force=V,
                moment=M,
                eps_0=eps_0,
                curvature=phi,
                converged=converged,
            ))

            # Check for failure: if we lost convergence, stop
            if not converged and step > 0:
                break

        return result
