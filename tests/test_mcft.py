"""Tests for the MCFT biaxial node solver."""

import math

import pytest

from response_yolo.materials.concrete import Concrete
from response_yolo.materials.steel import ReinforcingSteel
from response_yolo.analysis.mcft import solve_mcft_node, _principal_strains


# --------------------------------------------------------------------------
# Fixtures
# --------------------------------------------------------------------------
@pytest.fixture
def concrete():
    return Concrete(fc=35)


@pytest.fixture
def stirrup_steel():
    return ReinforcingSteel(fy=400)


# --------------------------------------------------------------------------
# Principal strains (Mohr's circle)
# --------------------------------------------------------------------------
class TestPrincipalStrains:
    def test_uniaxial_tension(self):
        eps_1, eps_2, theta = _principal_strains(0.001, 0.0, 0.0)
        assert eps_1 == pytest.approx(0.001, abs=1e-10)
        assert eps_2 == pytest.approx(0.0, abs=1e-10)

    def test_uniaxial_compression(self):
        eps_1, eps_2, theta = _principal_strains(-0.002, 0.0, 0.0)
        assert eps_1 == pytest.approx(0.0, abs=1e-10)
        assert eps_2 == pytest.approx(-0.002, abs=1e-10)

    def test_pure_shear(self):
        eps_1, eps_2, theta = _principal_strains(0.0, 0.0, 0.002)
        assert eps_1 == pytest.approx(0.001, abs=1e-10)
        assert eps_2 == pytest.approx(-0.001, abs=1e-10)
        assert theta == pytest.approx(math.pi / 4, abs=1e-6)

    def test_biaxial_equal(self):
        eps_1, eps_2, theta = _principal_strains(0.001, 0.001, 0.0)
        assert eps_1 == pytest.approx(0.001, abs=1e-10)
        assert eps_2 == pytest.approx(0.001, abs=1e-10)


# --------------------------------------------------------------------------
# MCFT node solver
# --------------------------------------------------------------------------
class TestMCFTNode:
    def test_pure_uniaxial_no_shear(self, concrete):
        """With gamma=0, MCFT should return the same as uniaxial concrete.stress()."""
        for eps_x in [-0.001, -0.0005, 0.0001, 0.0005, 0.001]:
            state = solve_mcft_node(eps_x=eps_x, gamma_xy=0.0, concrete=concrete)
            expected = concrete.stress(eps_x)
            assert state.sigma_x == pytest.approx(expected, rel=1e-4, abs=0.01)
            assert abs(state.tau_xy) < 0.01
            assert state.converged

    def test_shear_produces_tau(self, concrete, stirrup_steel):
        """Non-zero gamma should produce non-zero tau_xy."""
        state = solve_mcft_node(
            eps_x=0.0005,
            gamma_xy=0.001,
            concrete=concrete,
            rho_y=0.005,
            stirrup_material=stirrup_steel,
        )
        assert state.converged
        assert abs(state.tau_xy) > 0.1  # should have meaningful shear stress

    def test_gamma_sign_symmetry(self, concrete, stirrup_steel):
        """Flipping gamma sign should flip tau sign but not sigma_x magnitude."""
        state_pos = solve_mcft_node(
            eps_x=0.0005, gamma_xy=0.001, concrete=concrete,
            rho_y=0.005, stirrup_material=stirrup_steel,
        )
        state_neg = solve_mcft_node(
            eps_x=0.0005, gamma_xy=-0.001, concrete=concrete,
            rho_y=0.005, stirrup_material=stirrup_steel,
        )
        assert state_pos.tau_xy == pytest.approx(-state_neg.tau_xy, rel=0.05, abs=0.01)
        assert state_pos.sigma_x == pytest.approx(state_neg.sigma_x, rel=0.05, abs=0.1)

    def test_transverse_equilibrium(self, concrete, stirrup_steel):
        """sigma_y should be approximately zero (free surface)."""
        state = solve_mcft_node(
            eps_x=0.001, gamma_xy=0.002, concrete=concrete,
            rho_y=0.005, stirrup_material=stirrup_steel,
        )
        assert abs(state.sigma_y) < 1.0  # tolerance in MPa

    def test_tangent_nonzero_with_shear(self, concrete, stirrup_steel):
        """Condensed tangent should have non-zero values when shear is present."""
        state = solve_mcft_node(
            eps_x=0.0005, gamma_xy=0.001, concrete=concrete,
            rho_y=0.005, stirrup_material=stirrup_steel,
        )
        assert abs(state.tangent_gg) > 1.0  # dtau/dgamma should be significant


# --------------------------------------------------------------------------
# Compression softening
# --------------------------------------------------------------------------
class TestCompressionSoftening:
    def test_no_tension_no_softening(self, concrete):
        """With eps_1=0, beta=1/(0.8) > 1 → clamped to 1.0 → no softening."""
        unsoftened = concrete._popovics(0.002)
        softened = concrete.compression_stress_softened(0.002, 0.0)
        assert softened == pytest.approx(unsoftened, rel=0.01)

    def test_tension_reduces_compression(self, concrete):
        """Softened stress should be less than unsoftened when eps_1 > 0."""
        unsoftened = concrete._popovics(0.002)
        softened = concrete.compression_stress_softened(0.002, 0.005)
        assert softened < unsoftened * 0.9  # significant reduction

    def test_large_tension_floor(self, concrete):
        """Even with very large eps_1, beta should not go below 0.15."""
        softened = concrete.compression_stress_softened(0.002, 0.1)
        assert softened > 0  # should still carry some stress
