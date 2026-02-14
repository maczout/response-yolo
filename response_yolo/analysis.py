"""Moment-curvature analysis engine.

Implements plane-sections-remain-plane (Bernoulli hypothesis) sectional
analysis for pure bending (M only).  Axial force and shear are stubbed.

Algorithm
---------
For each target curvature φ:
1.  Assume a trial top-fibre strain ε_top.
2.  Compute strain at every fibre from plane-sections:
        ε(y) = ε_top + φ · (y − y_ref)
    where y_ref is the reference axis (gross centroid) and φ is positive
    for sagging (tension at bottom).
3.  Evaluate stress in each fibre from its constitutive model.
4.  Compute the axial resultant N = Σ σ·A.
5.  Iterate ε_top (bisection) until N ≈ 0 (pure bending).
6.  Compute M = Σ σ·A·(y − y_ref).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .section import DiscretisedSection


# ---------------------------------------------------------------------------
# Result containers
# ---------------------------------------------------------------------------
@dataclass
class MomentCurvaturePoint:
    """A single point on the M-φ curve."""

    curvature: float   # 1/mm
    moment: float      # N·mm
    top_strain: float  # top fibre strain
    bot_strain: float  # bottom fibre strain (computed for info)


@dataclass
class MomentCurvatureResult:
    """Full moment-curvature response."""

    points: list[MomentCurvaturePoint] = field(default_factory=list)

    @property
    def curvatures(self) -> list[float]:
        return [p.curvature for p in self.points]

    @property
    def moments(self) -> list[float]:
        return [p.moment for p in self.points]

    def peak_moment(self) -> float:
        if not self.points:
            return 0.0
        return max(abs(p.moment) for p in self.points)

    def to_dict(self) -> dict:
        return {
            "points": [
                {
                    "curvature_1_per_mm": p.curvature,
                    "moment_kNm": p.moment / 1e6,
                    "top_strain": p.top_strain,
                    "bot_strain": p.bot_strain,
                }
                for p in self.points
            ],
            "peak_moment_kNm": self.peak_moment() / 1e6,
        }


# ---------------------------------------------------------------------------
# Sectional force integration helpers
# ---------------------------------------------------------------------------
def _compute_forces(
    dsec: DiscretisedSection,
    top_strain: float,
    curvature: float,
) -> tuple[float, float, float]:
    """Return (N, M, bot_strain) for a given top strain and curvature.

    N and M are about the centroidal reference axis.
    """
    y_ref = dsec.centroid_y
    y_top_min = min(f.y for f in dsec.concrete_fibres) if dsec.concrete_fibres else 0.0
    y_bot_max = max(f.y for f in dsec.concrete_fibres) if dsec.concrete_fibres else 0.0

    N = 0.0
    M = 0.0

    for f in dsec.concrete_fibres:
        eps = top_strain + curvature * (f.y - y_top_min)
        sigma = f.concrete.stress(eps)
        force = sigma * f.area
        N += force
        M += force * (f.y - y_ref)

    for f in dsec.steel_fibres:
        eps = top_strain + curvature * (f.y - y_top_min)
        sigma = f.steel.stress(eps)
        force = sigma * f.area
        N += force
        M += force * (f.y - y_ref)

    bot_strain = top_strain + curvature * (y_bot_max - y_top_min)
    return N, M, bot_strain


# ---------------------------------------------------------------------------
# Equilibrium solver – find top strain for N = 0
# ---------------------------------------------------------------------------
def _find_top_strain(
    dsec: DiscretisedSection,
    curvature: float,
    tol: float = 1.0,       # N tolerance (Newtons)
    max_iter: int = 200,
    strain_lo: float = -0.010,
    strain_hi: float = 0.010,
) -> tuple[float, float, float]:
    """Bisect on top_strain to find N ≈ 0.

    Returns (top_strain, moment, bot_strain).
    """
    # Ensure bracket captures a sign change in N
    N_lo, _, _ = _compute_forces(dsec, strain_lo, curvature)
    N_hi, _, _ = _compute_forces(dsec, strain_hi, curvature)

    # Widen bracket if needed
    for _ in range(20):
        if N_lo * N_hi < 0:
            break
        strain_lo *= 2.0
        strain_hi *= 2.0
        N_lo, _, _ = _compute_forces(dsec, strain_lo, curvature)
        N_hi, _, _ = _compute_forces(dsec, strain_hi, curvature)
    else:
        # Fallback: return midpoint (may not satisfy equilibrium perfectly)
        mid = (strain_lo + strain_hi) / 2.0
        _, M, bot = _compute_forces(dsec, mid, curvature)
        return mid, M, bot

    for _ in range(max_iter):
        mid = (strain_lo + strain_hi) / 2.0
        N_mid, M_mid, bot_mid = _compute_forces(dsec, mid, curvature)
        if abs(N_mid) < tol:
            return mid, M_mid, bot_mid
        if N_mid * N_lo < 0:
            strain_hi = mid
            N_hi = N_mid
        else:
            strain_lo = mid
            N_lo = N_mid

    return mid, M_mid, bot_mid  # type: ignore[possibly-undefined]


# ---------------------------------------------------------------------------
# Public API – moment-curvature analysis
# ---------------------------------------------------------------------------
@dataclass
class MomentCurvatureAnalysis:
    """Perform a moment-curvature analysis on a discretised section.

    Parameters
    ----------
    section : DiscretisedSection
        Fibre model of the cross-section.
    max_curvature : float | None
        Maximum curvature (1/mm) to analyse to.  If None, a sensible default
        is estimated from the section depth.
    n_steps : int
        Number of curvature increments.
    """

    section: DiscretisedSection
    max_curvature: float | None = None
    n_steps: int = 100

    def run(self) -> MomentCurvatureResult:
        dsec = self.section

        if self.max_curvature is not None:
            phi_max = self.max_curvature
        else:
            # Default: curvature giving ≈ 0.003 strain at the extreme fibre
            # φ ≈ 0.003 / (d/2) where d is the section depth.
            y_top = min(f.y for f in dsec.concrete_fibres)
            y_bot = max(f.y for f in dsec.concrete_fibres)
            depth = y_bot - y_top
            if depth <= 0:
                raise ValueError("Section has no depth")
            phi_max = 0.003 / (depth / 2.0) * 5.0  # go well past yield

        result = MomentCurvatureResult()
        # Include the origin
        result.points.append(MomentCurvaturePoint(0.0, 0.0, 0.0, 0.0))

        for i in range(1, self.n_steps + 1):
            phi = phi_max * i / self.n_steps
            top_strain, moment, bot_strain = _find_top_strain(dsec, phi)
            result.points.append(
                MomentCurvaturePoint(
                    curvature=phi,
                    moment=moment,
                    top_strain=top_strain,
                    bot_strain=bot_strain,
                )
            )

        return result


# ---------------------------------------------------------------------------
# Stubs for future analysis types
# ---------------------------------------------------------------------------
class AxialForceAnalysis:
    """Stub – axial force–strain analysis (N only).  Not yet implemented."""

    def __init__(self, *args, **kwargs) -> None:  # noqa: ANN002
        raise NotImplementedError(
            "Axial force analysis is not yet implemented in Response-YOLO.  "
            "Contributions welcome!"
        )


class ShearAnalysis:
    """Stub – shear analysis (V only, MCFT-based).  Not yet implemented."""

    def __init__(self, *args, **kwargs) -> None:  # noqa: ANN002
        raise NotImplementedError(
            "Shear analysis (MCFT) is not yet implemented in Response-YOLO.  "
            "Contributions welcome!"
        )


class FullSectionalAnalysis:
    """Stub – combined N + M + V sectional analysis.  Not yet implemented."""

    def __init__(self, *args, **kwargs) -> None:  # noqa: ANN002
        raise NotImplementedError(
            "Combined N+M+V sectional analysis is not yet implemented in "
            "Response-YOLO.  Contributions welcome!"
        )
