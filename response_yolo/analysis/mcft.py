"""
MCFT biaxial node solver — Modified Compression Field Theory at a single point.

Given the strain state (eps_x, gamma_xy) at a layer centroid plus transverse
reinforcement data, solve for the complete stress state (sigma_x, tau_xy) while
enforcing the free-surface condition sigma_y_total = 0.

This implements the MCFT formulation from Vecchio & Collins (1986) as applied
in Response-2000 (Bentz 2000, Chapter 3, Sections 3-1 to 3-4).

Key assumptions:
  - Plane sections remain plane  →  eps_x is prescribed by the section
  - Free transverse surface      →  sigma_y = 0  (no net transverse stress)
  - Average stress–strain        →  concrete uses smeared/average curves
  - Rotating cracks              →  crack angle follows principal compression
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional

from response_yolo.materials.concrete import Concrete
from response_yolo.materials.steel import ReinforcingSteel


@dataclass
class MCFTState:
    """Converged state at an MCFT node.

    All stresses are in the global x-y coordinate system.
    """

    # Input strains
    eps_x: float
    eps_y: float        # solved (transverse strain satisfying sigma_y = 0)
    gamma_xy: float

    # Principal strains
    eps_1: float        # principal tensile strain (positive)
    eps_2: float        # principal compressive strain (negative)
    theta: float        # crack angle (radians), from x-axis to principal tension

    # Stresses in x-y frame
    sigma_x: float      # total longitudinal stress (concrete + rebar_x)
    sigma_y: float      # total transverse stress (should be ~0)
    tau_xy: float        # shear stress

    # Concrete principal stresses
    fc1: float          # principal tensile stress in concrete (positive)
    fc2: float          # principal compressive stress in concrete (negative)

    # Condensed tangent (2×2): maps (deps_x, dgamma_xy) → (dsigma_x, dtau_xy)
    # after eliminating eps_y via the sigma_y = 0 constraint.
    tangent_xx: float   # dsigma_x / deps_x
    tangent_xg: float   # dsigma_x / dgamma_xy
    tangent_gx: float   # dtau_xy  / deps_x
    tangent_gg: float   # dtau_xy  / dgamma_xy

    converged: bool = True


def _principal_strains(eps_x: float, eps_y: float, gamma_xy: float):
    """Mohr's circle compatibility: compute principal strains and angle.

    Returns (eps_1, eps_2, theta) where eps_1 >= eps_2.
    theta is the angle from x-axis to the direction of eps_1 (radians).
    """
    avg = 0.5 * (eps_x + eps_y)
    diff = 0.5 * (eps_x - eps_y)
    R = math.sqrt(diff * diff + (0.5 * gamma_xy) ** 2)
    eps_1 = avg + R
    eps_2 = avg - R

    if abs(eps_x - eps_y) < 1e-15 and abs(gamma_xy) < 1e-15:
        theta = 0.0
    else:
        theta = 0.5 * math.atan2(gamma_xy, eps_x - eps_y)

    return eps_1, eps_2, theta


def _concrete_stresses_xy(
    concrete: Concrete,
    eps_1: float,
    eps_2: float,
    theta: float,
):
    """Compute concrete stresses in x-y frame from principal strains.

    Returns (sigma_cx, sigma_cy, tau_cxy, fc1, fc2).
    """
    # Principal tensile stress
    if eps_1 > 0:
        if eps_1 <= concrete.ecr:
            fc1 = concrete.Ec * eps_1
        else:
            # MCFT tension stiffening on principal tensile strain
            fc1 = concrete.ft / (1.0 + math.sqrt(500.0 * eps_1))
    else:
        fc1 = 0.0

    # Principal compressive stress (with softening for biaxial tension)
    if eps_2 < 0:
        eps_1_for_softening = max(eps_1, 0.0)
        fc2_mag = concrete.compression_stress_softened(
            abs(eps_2), eps_1_for_softening
        )
        fc2 = -fc2_mag  # negative = compression
    else:
        # Both principal strains tensile
        if eps_2 <= concrete.ecr:
            fc2 = concrete.Ec * eps_2
        else:
            fc2 = concrete.ft / (1.0 + math.sqrt(500.0 * eps_2))

    # Transform to x-y via Mohr's circle
    cos_t = math.cos(theta)
    sin_t = math.sin(theta)
    c2 = cos_t * cos_t
    s2 = sin_t * sin_t
    cs = cos_t * sin_t

    sigma_cx = fc1 * c2 + fc2 * s2
    sigma_cy = fc1 * s2 + fc2 * c2
    tau_cxy = (fc1 - fc2) * cs

    return sigma_cx, sigma_cy, tau_cxy, fc1, fc2


def _evaluate_transverse_residual(
    eps_x: float,
    eps_y: float,
    gamma_xy: float,
    concrete: Concrete,
    rho_y: float,
    stirrup_material: Optional[ReinforcingSteel],
    rho_x: float = 0.0,
    long_material: Optional[ReinforcingSteel] = None,
):
    """Compute sigma_y_total for a trial eps_y.

    Returns (sigma_y_total, sigma_cx, sigma_cy, tau_cxy, fc1, fc2,
             eps_1, eps_2, theta).
    """
    eps_1, eps_2, theta = _principal_strains(eps_x, eps_y, gamma_xy)
    sigma_cx, sigma_cy, tau_cxy, fc1, fc2 = _concrete_stresses_xy(
        concrete, eps_1, eps_2, theta
    )

    # Transverse steel contribution
    fy_steel = 0.0
    if rho_y > 0 and stirrup_material is not None:
        fy_steel = rho_y * stirrup_material.stress(eps_y)

    sigma_y_total = sigma_cy + fy_steel

    return sigma_y_total, sigma_cx, sigma_cy, tau_cxy, fc1, fc2, eps_1, eps_2, theta


def solve_mcft_node(
    eps_x: float,
    gamma_xy: float,
    concrete: Concrete,
    rho_y: float = 0.0,
    stirrup_material: Optional[ReinforcingSteel] = None,
    rho_x: float = 0.0,
    long_material: Optional[ReinforcingSteel] = None,
    max_iter: int = 40,
    tol: float = 1e-3,
) -> MCFTState:
    """Solve the MCFT equations at a single biaxial node.

    Iterates on eps_y (transverse strain) until the free-surface condition
    sigma_y_total = 0 is satisfied.

    Parameters
    ----------
    eps_x : float
        Longitudinal strain (prescribed by the section strain profile).
    gamma_xy : float
        Shear strain at this location.
    concrete : Concrete
        Concrete material model.
    rho_y : float
        Transverse reinforcement ratio Av/(b*s).
    stirrup_material : ReinforcingSteel or None
        Stirrup material.
    rho_x : float
        Longitudinal reinforcement ratio (for smeared contribution).
        Usually 0 because rebar forces are tracked separately.
    long_material : ReinforcingSteel or None
        Longitudinal reinforcement material (if smeared).
    max_iter : int
        Maximum Newton-Raphson iterations.
    tol : float
        Convergence tolerance on sigma_y (MPa).

    Returns
    -------
    MCFTState
        Converged biaxial state including stresses and condensed tangent.
    """
    # Special case: no shear → uniaxial
    if abs(gamma_xy) < 1e-14:
        sigma_cx = concrete.stress(eps_x)
        fx_steel = 0.0
        if rho_x > 0 and long_material is not None:
            fx_steel = rho_x * long_material.stress(eps_x)

        Et = concrete.tangent(eps_x)
        if rho_x > 0 and long_material is not None:
            Et += rho_x * long_material.tangent(eps_x)

        return MCFTState(
            eps_x=eps_x, eps_y=0.0, gamma_xy=0.0,
            eps_1=max(eps_x, 0.0), eps_2=min(eps_x, 0.0),
            theta=0.0,
            sigma_x=sigma_cx + fx_steel, sigma_y=0.0, tau_xy=0.0,
            fc1=max(sigma_cx, 0.0), fc2=min(sigma_cx, 0.0),
            tangent_xx=Et, tangent_xg=0.0,
            tangent_gx=0.0, tangent_gg=0.0,
            converged=True,
        )

    # Initial guess for eps_y: start at eps_x (isotropic) or zero
    eps_y = eps_x * 0.5

    converged = False
    for _it in range(max_iter):
        res, sigma_cx, sigma_cy, tau_cxy, fc1, fc2, eps_1, eps_2, theta = (
            _evaluate_transverse_residual(
                eps_x, eps_y, gamma_xy, concrete, rho_y, stirrup_material,
                rho_x, long_material,
            )
        )

        if abs(res) < tol:
            converged = True
            break

        # Numerical derivative d(sigma_y)/d(eps_y) via finite difference
        deps_y = max(abs(eps_y) * 1e-6, 1e-10)
        res_plus = _evaluate_transverse_residual(
            eps_x, eps_y + deps_y, gamma_xy, concrete, rho_y, stirrup_material,
            rho_x, long_material,
        )[0]

        d_res = (res_plus - res) / deps_y
        if abs(d_res) < 1e-12:
            # Tangent is flat — try bisection step
            eps_y -= 0.001 * (1.0 if res > 0 else -1.0)
            continue

        delta = -res / d_res
        # Limit step size to prevent divergence
        max_step = 0.01
        if abs(delta) > max_step:
            delta = max_step * (1.0 if delta > 0 else -1.0)

        eps_y += delta

        # Keep eps_y bounded
        eps_y = max(-0.05, min(0.05, eps_y))

    # Final evaluation at converged eps_y
    res, sigma_cx, sigma_cy, tau_cxy, fc1, fc2, eps_1, eps_2, theta = (
        _evaluate_transverse_residual(
            eps_x, eps_y, gamma_xy, concrete, rho_y, stirrup_material,
            rho_x, long_material,
        )
    )

    # Total x-stress: concrete + smeared longitudinal steel
    sigma_x_total = sigma_cx
    if rho_x > 0 and long_material is not None:
        sigma_x_total += rho_x * long_material.stress(eps_x)

    # Compute condensed 2×2 tangent by finite differences
    # The condensed tangent maps (deps_x, dgamma) → (dsigma_x, dtau_xy)
    # at the converged sigma_y = 0 state.
    h_fd = 1e-7  # finite-difference step

    tangent_xx, tangent_xg = 0.0, 0.0
    tangent_gx, tangent_gg = 0.0, 0.0

    # Perturb eps_x
    state_px = _solve_for_sigma_x_tau(
        eps_x + h_fd, gamma_xy, concrete, rho_y, stirrup_material,
        rho_x, long_material, eps_y_init=eps_y,
    )
    tangent_xx = (state_px[0] - sigma_x_total) / h_fd
    tangent_gx = (state_px[1] - tau_cxy) / h_fd

    # Perturb gamma_xy
    state_pg = _solve_for_sigma_x_tau(
        eps_x, gamma_xy + h_fd, concrete, rho_y, stirrup_material,
        rho_x, long_material, eps_y_init=eps_y,
    )
    tangent_xg = (state_pg[0] - sigma_x_total) / h_fd
    tangent_gg = (state_pg[1] - tau_cxy) / h_fd

    return MCFTState(
        eps_x=eps_x, eps_y=eps_y, gamma_xy=gamma_xy,
        eps_1=eps_1, eps_2=eps_2, theta=theta,
        sigma_x=sigma_x_total, sigma_y=res, tau_xy=tau_cxy,
        fc1=fc1, fc2=fc2,
        tangent_xx=tangent_xx, tangent_xg=tangent_xg,
        tangent_gx=tangent_gx, tangent_gg=tangent_gg,
        converged=converged,
    )


def _solve_for_sigma_x_tau(
    eps_x: float,
    gamma_xy: float,
    concrete: Concrete,
    rho_y: float,
    stirrup_material: Optional[ReinforcingSteel],
    rho_x: float,
    long_material: Optional[ReinforcingSteel],
    eps_y_init: float = 0.0,
    max_iter: int = 20,
    tol: float = 1e-3,
):
    """Quick inner solve for eps_y → return (sigma_x_total, tau_xy).

    Used for finite-difference tangent computation.
    """
    eps_y = eps_y_init
    for _ in range(max_iter):
        res, sigma_cx, sigma_cy, tau_cxy, fc1, fc2, eps_1, eps_2, theta = (
            _evaluate_transverse_residual(
                eps_x, eps_y, gamma_xy, concrete, rho_y, stirrup_material,
                rho_x, long_material,
            )
        )
        if abs(res) < tol:
            break

        deps_y = max(abs(eps_y) * 1e-6, 1e-10)
        res_plus = _evaluate_transverse_residual(
            eps_x, eps_y + deps_y, gamma_xy, concrete, rho_y, stirrup_material,
            rho_x, long_material,
        )[0]
        d_res = (res_plus - res) / deps_y
        if abs(d_res) < 1e-12:
            break
        delta = -res / d_res
        max_step = 0.01
        if abs(delta) > max_step:
            delta = max_step * (1.0 if delta > 0 else -1.0)
        eps_y += delta
        eps_y = max(-0.05, min(0.05, eps_y))

    sigma_x_total = sigma_cx
    if rho_x > 0 and long_material is not None:
        sigma_x_total += rho_x * long_material.stress(eps_x)

    return sigma_x_total, tau_cxy
