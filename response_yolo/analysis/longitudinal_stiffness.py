"""
Longitudinal Stiffness Method for computing shear stress distribution.

This implements the key innovation from Bentz (2000), Chapter 6, Section 6-5.
Instead of the older dual-section method, this takes the derivative as dx → 0
and uses the tangent stiffness at each layer to directly compute how shear
stress (shear flow) varies through the section depth.

Key equation (Bentz Eq 6-9):
    Δq_i = j_i * (dε_x_i) + k_i * dγ_xy_i

where j_i, k_i are tangent stiffness terms at layer i, and dε_x_i, dγ_xy_i
are "virtual strains" derived from the global tangent stiffness matrix.

Algorithm:
    1. At each layer, compute condensed tangent [j, k] from MCFT
    2. Assemble global 3×3 Jacobian J by summing layer contributions
    3. Solve J · [dε₀, dφ, dγ] = [0, V·1m, 0] for virtual strains
    4. Compute Δq at each depth using virtual strains
    5. Integrate Δq from top or bottom to get shear stress profile

Reference: Bentz (2000), Chapter 6, Section 6-5, pages 84-88.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List

from response_yolo.analysis.mcft import solve_mcft_node
from response_yolo.section.cross_section import CrossSection


@dataclass
class ShearStressPoint:
    """Shear stress at a specific depth."""

    y: float          # elevation from section bottom (mm)
    tau: float        # shear stress (MPa)
    delta_q: float    # rate of change of shear flow (N/mm per mm depth)


def compute_shear_stress_distribution(
    section: CrossSection,
    eps_0: float,
    phi: float,
    gamma_xy0: float,
    y_ref: float,
) -> List[ShearStressPoint]:
    """Compute the shear stress distribution through the section depth.

    Uses the Longitudinal Stiffness Method (Bentz Eq 6-9) to find how
    shear stress varies with depth, based on the tangent stiffness at
    each layer.

    Parameters
    ----------
    section : CrossSection
        The cross-section with concrete layers and reinforcement.
    eps_0 : float
        Strain at the reference axis.
    phi : float
        Curvature (1/mm).
    gamma_xy0 : float
        Average shear strain.
    y_ref : float
        Reference axis y-coordinate.

    Returns
    -------
    list of ShearStressPoint
        Shear stress at each layer centroid, ordered bottom to top.
    """
    layers = section.concrete_layers
    if not layers:
        return []

    yb = section.y_bottom
    yt = section.y_top

    # Step 1: Compute MCFT tangent at each layer
    # Each layer contributes to the global stiffness.
    # The condensed tangent maps (deps_x, dgamma) → (dsigma_x, dtau_xy).
    layer_data = []
    for lay in layers:
        dy = lay.y_mid - y_ref
        eps_x = eps_0 - phi * dy
        s = CrossSection.shear_strain_profile(lay.y_mid, yb, yt)
        gamma = gamma_xy0 * s

        state = solve_mcft_node(
            eps_x=eps_x,
            gamma_xy=gamma,
            concrete=lay.material,
            rho_y=lay.rho_y,
            stirrup_material=lay.stirrup_material,
        )

        layer_data.append({
            "lay": lay,
            "dy": dy,
            "s": s,
            "state": state,
            # j = dsigma_x/deps_x * area, k = dsigma_x/dgamma * area
            # These are the Bentz "j" and "k" terms for shear flow rate
            "j": state.tangent_xx * lay.area,
            "k_g": state.tangent_xg * lay.area,
        })

    # Step 2: Assemble global 3×3 Jacobian J
    # J maps [dε₀, dφ, dγ₀] → [dN, dM, dV]
    # Row 0 (dN): sum over layers of j*(deps_x/deps_0) + k*(dgamma/dgamma_0)
    #   deps_x/deps_0 = 1,  deps_x/dphi = -dy,  dgamma/dgamma_0 = s(y)
    # Row 1 (dM): sum of -dy * [j*(1) + ...], etc.
    # Row 2 (dV): sum of tau tangent terms
    J = [[0.0, 0.0, 0.0],
         [0.0, 0.0, 0.0],
         [0.0, 0.0, 0.0]]

    for ld in layer_data:
        dy = ld["dy"]
        s = ld["s"]
        j = ld["j"]
        k_g = ld["k_g"]
        lay = ld["lay"]
        st = ld["state"]

        # dN/d(eps_0): j * d(eps_x)/d(eps_0) = j * 1
        J[0][0] += j
        # dN/d(phi): j * d(eps_x)/d(phi) = j * (-dy)
        J[0][1] += j * (-dy)
        # dN/d(gamma_0): k * d(gamma)/d(gamma_0) = k * s
        J[0][2] += k_g * s

        # dM/d(eps_0): -dy * [j * 1]
        J[1][0] += -dy * j
        # dM/d(phi): -dy * [j * (-dy)] = dy^2 * j
        J[1][1] += dy * dy * j
        # dM/d(gamma_0): -dy * [k * s]
        J[1][2] += -dy * k_g * s

        # dV contributions from shear tangent
        tau_gx = st.tangent_gx * lay.area  # dtau/deps_x * area
        tau_gg = st.tangent_gg * lay.area  # dtau/dgamma * area
        J[2][0] += tau_gx
        J[2][1] += tau_gx * (-dy)
        J[2][2] += tau_gg * s

    # Also add rebar/tendon stiffness to J (uniaxial, no shear contribution)
    for bar in section.rebars:
        dy = bar.y - y_ref
        eps_x = eps_0 - phi * dy
        Et = bar.material.tangent(eps_x)
        ea = Et * bar.area
        J[0][0] += ea
        J[0][1] -= ea * dy
        J[1][0] -= ea * dy
        J[1][1] += ea * dy * dy

    for t in section.tendons:
        dy = t.y - y_ref
        eps_x = eps_0 - phi * dy + t.prestrain
        Et = t.material.tangent(eps_x)
        ea = Et * t.area
        J[0][0] += ea
        J[0][1] -= ea * dy
        J[1][0] -= ea * dy
        J[1][1] += ea * dy * dy

    # Step 3: Solve J * [dε₀, dφ, dγ₀] = [0, 1.0, 0]
    # This represents a virtual unit shear increment while maintaining
    # N = const and V_external = const.
    rhs = [0.0, 1.0, 0.0]
    virtual_strains = _solve_3x3(J, rhs)

    if virtual_strains is None:
        # Singular matrix — return zero shear stress
        return [
            ShearStressPoint(y=lay.y_mid, tau=0.0, delta_q=0.0)
            for lay in layers
        ]

    d_eps0, d_phi, d_gamma0 = virtual_strains

    # Step 4: Compute Δq (shear flow rate) at each layer
    # Bentz Eq 6-9: Δq_i = j_i * (d_eps_x_i) + k_i * d_gamma_i
    # where d_eps_x_i = d_eps0 - d_phi * dy_i
    #       d_gamma_i = d_gamma0 * s(y_i)
    for ld in layer_data:
        dy = ld["dy"]
        s = ld["s"]
        d_eps_x = d_eps0 - d_phi * dy
        d_gamma = d_gamma0 * s
        ld["delta_q"] = ld["j"] * d_eps_x + ld["k_g"] * d_gamma

    # Step 5: Integrate Δq from top to get shear stress
    # q(y) = cumulative sum of Δq * thickness from top
    # tau(y) = q(y) / width(y)
    results = []
    q_cumulative = 0.0

    # Integrate from top to bottom (reversed order)
    for ld in reversed(layer_data):
        lay = ld["lay"]
        q_cumulative += ld["delta_q"] * lay.thickness
        tau = q_cumulative / lay.width if lay.width > 0 else 0.0
        results.append(ShearStressPoint(
            y=lay.y_mid,
            tau=tau,
            delta_q=ld["delta_q"],
        ))

    # Reverse so results are bottom-to-top
    results.reverse()

    return results


def _solve_3x3(A: list, b: list):
    """Solve a 3×3 linear system A·x = b using Cramer's rule.

    Returns None if the matrix is singular.
    """
    # Copy to avoid mutation
    a = [[A[i][j] for j in range(3)] for i in range(3)]

    det = (
        a[0][0] * (a[1][1] * a[2][2] - a[1][2] * a[2][1])
        - a[0][1] * (a[1][0] * a[2][2] - a[1][2] * a[2][0])
        + a[0][2] * (a[1][0] * a[2][1] - a[1][1] * a[2][0])
    )

    if abs(det) < 1e-30:
        return None

    # Cramer's rule
    x = [0.0, 0.0, 0.0]
    for col in range(3):
        # Replace column col with b
        m = [[a[i][j] for j in range(3)] for i in range(3)]
        for i in range(3):
            m[i][col] = b[i]
        det_col = (
            m[0][0] * (m[1][1] * m[2][2] - m[1][2] * m[2][1])
            - m[0][1] * (m[1][0] * m[2][2] - m[1][2] * m[2][0])
            + m[0][2] * (m[1][0] * m[2][1] - m[1][1] * m[2][0])
        )
        x[col] = det_col / det

    return x
