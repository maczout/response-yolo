"""Tests for the sectional shear analysis (V-gamma)."""

import pytest

from response_yolo.materials.concrete import Concrete
from response_yolo.materials.steel import ReinforcingSteel
from response_yolo.section.geometry import RectangularSection
from response_yolo.section.cross_section import CrossSection
from response_yolo.section.rebar import RebarBar
from response_yolo.analysis.shear_analysis import ShearAnalysis
from response_yolo.analysis.longitudinal_stiffness import (
    compute_shear_stress_distribution,
)


# --------------------------------------------------------------------------
# Fixtures
# --------------------------------------------------------------------------
@pytest.fixture
def beam_section():
    """Standard rectangular beam: 300×500mm, fc=35, fy=400, stirrups 10mm@200."""
    concrete = Concrete(fc=35)
    steel = ReinforcingSteel(fy=400)
    stirrup_steel = ReinforcingSteel(fy=400)

    shape = RectangularSection(b=300, h=500)
    xs = CrossSection.from_shape(shape, concrete, n_layers=50)

    # Bottom tension rebar: 3-25M (1500 mm²)
    xs.add_rebar(RebarBar(y=50, area=1500, material=steel))
    # Top compression rebar: 2-15M (400 mm²)
    xs.add_rebar(RebarBar(y=450, area=400, material=steel))

    # Stirrups: 2 legs of 10mm bar = 2 * 78.5 = 157 mm²
    xs.set_stirrups(Av=157, s=200, material=stirrup_steel)

    return xs


# --------------------------------------------------------------------------
# Basic V-gamma tests
# --------------------------------------------------------------------------
class TestVGammaBasic:
    def test_zero_shear_at_zero_gamma(self, beam_section):
        """V should be zero (or near-zero) when gamma_xy0 = 0."""
        analysis = ShearAnalysis(
            section=beam_section,
            gamma_max=0.0001,
            n_steps=1,
        )
        result = analysis.run()
        assert len(result.points) >= 1
        # First point at gamma=0 should have ~zero shear
        assert abs(result.points[0].shear_force) < 100  # small tolerance (N)

    def test_shear_increases_with_gamma(self, beam_section):
        """V should increase as gamma increases (at least initially)."""
        analysis = ShearAnalysis(
            section=beam_section,
            gamma_max=0.002,
            n_steps=10,
        )
        result = analysis.run()
        assert len(result.points) >= 5

        # Check that V increases from the first few steps
        converged_pts = [p for p in result.points if p.converged and p.gamma_xy0 > 0]
        if len(converged_pts) >= 2:
            v_values = [abs(p.shear_force) for p in converged_pts[:5]]
            # At least the first few should be increasing
            assert v_values[-1] > v_values[0]

    def test_produces_result(self, beam_section):
        """ShearAnalysis should run without errors and produce results."""
        analysis = ShearAnalysis(
            section=beam_section,
            gamma_max=0.003,
            n_steps=15,
        )
        result = analysis.run()
        assert len(result.points) > 0
        assert result.peak_shear > 0

    def test_peak_shear_reasonable(self, beam_section):
        """Peak V should be in a reasonable range for this beam.

        Simplified ACI-like estimate:
          Vc = 0.17 * sqrt(fc) * b * d = 0.17 * sqrt(35) * 300 * 450 ≈ 136 kN
          Vs = Av * fy * d / s = 157 * 400 * 450 / 200 ≈ 141 kN
          V_total ≈ 277 kN = 277,000 N

        The MCFT result should be in the same ballpark (±50%).
        """
        analysis = ShearAnalysis(
            section=beam_section,
            gamma_max=0.005,
            n_steps=25,
        )
        result = analysis.run()

        v_peak = result.peak_shear
        # Accept a wide range for prototype: 100 kN to 600 kN
        assert v_peak > 100_000, f"Peak V too low: {v_peak/1000:.0f} kN"
        assert v_peak < 600_000, f"Peak V too high: {v_peak/1000:.0f} kN"


# --------------------------------------------------------------------------
# Longitudinal Stiffness Method tests
# --------------------------------------------------------------------------
class TestLongitudinalStiffness:
    def test_returns_points(self, beam_section):
        """Should return a shear stress point for each concrete layer."""
        results = compute_shear_stress_distribution(
            section=beam_section,
            eps_0=0.0005,
            phi=1e-6,
            gamma_xy0=0.001,
            y_ref=beam_section.centroid_y,
        )
        assert len(results) == len(beam_section.concrete_layers)

    def test_shear_stress_nonzero(self, beam_section):
        """Should produce non-zero shear stress distribution when gamma is non-zero.

        The LSM returns the shear stress distribution shape for a virtual unit
        moment increment.  The absolute values are small; we just verify the
        distribution is non-trivial (not all zeros).
        """
        results = compute_shear_stress_distribution(
            section=beam_section,
            eps_0=0.0005,
            phi=1e-6,
            gamma_xy0=0.001,
            y_ref=beam_section.centroid_y,
        )
        # At least some layers should have non-zero shear stress
        max_tau = max(abs(pt.tau) for pt in results)
        assert max_tau > 1e-8  # non-trivial distribution


# --------------------------------------------------------------------------
# 3-DOF section integration tests
# --------------------------------------------------------------------------
class TestSectionIntegrationShear:
    def test_forces_shear_at_zero_gamma(self, beam_section):
        """With gamma=0, integrate_forces_shear should give V≈0 and
        N, M matching integrate_forces."""
        y_ref = beam_section.centroid_y
        eps_0 = 0.0
        phi = 1e-6

        N_old, M_old = beam_section.integrate_forces(eps_0, phi, y_ref)
        N_new, M_new, V_new = beam_section.integrate_forces_shear(
            eps_0, phi, 0.0, y_ref
        )

        assert N_new == pytest.approx(N_old, rel=0.01, abs=10)
        assert M_new == pytest.approx(M_old, rel=0.01, abs=100)
        assert abs(V_new) < 100  # essentially zero

    def test_stiffness_3x3_shape(self, beam_section):
        """3×3 stiffness matrix should be a 3×3 list of lists."""
        y_ref = beam_section.centroid_y
        J = beam_section.integrate_stiffness_3x3(0.0, 1e-6, 0.001, y_ref)
        assert len(J) == 3
        for row in J:
            assert len(row) == 3

    def test_shear_strain_profile(self, beam_section):
        """Parabolic profile should be 1.5 at mid-depth and 0 at edges."""
        yb = beam_section.y_bottom
        yt = beam_section.y_top
        mid = 0.5 * (yb + yt)

        s_mid = CrossSection.shear_strain_profile(mid, yb, yt)
        s_bot = CrossSection.shear_strain_profile(yb, yb, yt)
        s_top = CrossSection.shear_strain_profile(yt, yb, yt)

        assert s_mid == pytest.approx(1.5, abs=0.01)
        assert s_bot == pytest.approx(0.0, abs=0.01)
        assert s_top == pytest.approx(0.0, abs=0.01)
