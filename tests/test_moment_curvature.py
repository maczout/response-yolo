"""Tests for moment-curvature analysis.

Benchmark: 300x500mm rectangular beam, fc'=35 MPa, fy=400 MPa
Bottom steel: 3-25M = 1500 mm^2 at d=450mm (y=50mm from bottom)
Top steel: 2-15M = 400 mm^2 at d'=50mm (y=450mm from bottom)

Expected values (from R2K and hand calculations):
  - Cracking moment: ~30-40 kN-m  (Mcr = fr*Ig/yt)
  - Yield moment:    ~230-260 kN-m (My ~ As*fy*(d-a/2))
  - Ultimate moment: ~280-310 kN-m
"""

import pytest
import math

from response_yolo.materials.concrete import Concrete
from response_yolo.materials.steel import ReinforcingSteel
from response_yolo.section.geometry import RectangularSection
from response_yolo.section.rebar import RebarBar
from response_yolo.section.cross_section import CrossSection
from response_yolo.analysis.moment_curvature import MomentCurvatureAnalysis


@pytest.fixture
def simple_beam():
    """300x500 mm beam with 1500mm^2 bottom steel, 400mm^2 top steel."""
    shape = RectangularSection(b=300, h=500)
    concrete = Concrete(fc=35)
    steel = ReinforcingSteel(fy=400, fu=600, esh=0.01, esu=0.05)

    xs = CrossSection.from_shape(shape, concrete, n_layers=100)
    xs.add_rebar(RebarBar(y=50, area=1500, material=steel))
    xs.add_rebar(RebarBar(y=450, area=400, material=steel))
    return xs


class TestMomentCurvature:
    def test_runs_without_error(self, simple_beam):
        analysis = MomentCurvatureAnalysis(simple_beam)
        result = analysis.run()
        assert len(result.points) > 0

    def test_monotonic_curvature(self, simple_beam):
        analysis = MomentCurvatureAnalysis(simple_beam, n_steps=100)
        result = analysis.run()
        for i in range(1, len(result.points)):
            assert result.points[i].curvature >= result.points[i-1].curvature

    def test_cracking_detected(self, simple_beam):
        analysis = MomentCurvatureAnalysis(simple_beam)
        result = analysis.run()
        assert result.cracking_index is not None
        # Cracking moment for 300x500 beam with ft~1.9 MPa:
        # Mcr = ft * bh^2/6 ~ 1.9 * 300 * 500^2 / 6 ~ 23.75e6 N-mm ~ 24 kN-m
        mcr_kNm = result.cracking_moment / 1e6
        assert 15 < mcr_kNm < 60, f"Mcr = {mcr_kNm:.1f} kN-m"

    def test_yield_detected(self, simple_beam):
        analysis = MomentCurvatureAnalysis(simple_beam)
        result = analysis.run()
        assert result.yield_index is not None
        my_kNm = result.yield_moment / 1e6
        # As*fy*(d - a/2) with a = As*fy/(0.85*fc'*b)
        # a = 1500*400/(0.85*35*300) = 67.2 mm
        # My ~ 1500 * 400 * (450 - 67.2/2) = 249.6e6 N-mm ~ 250 kN-m
        assert 150 < my_kNm < 350, f"My = {my_kNm:.1f} kN-m"

    def test_ultimate_moment(self, simple_beam):
        analysis = MomentCurvatureAnalysis(simple_beam)
        result = analysis.run()
        assert result.ultimate_index is not None
        mu_kNm = result.ultimate_moment / 1e6
        assert mu_kNm > 200, f"Mu = {mu_kNm:.1f} kN-m"

    def test_failure_reason(self, simple_beam):
        analysis = MomentCurvatureAnalysis(simple_beam)
        result = analysis.run()
        assert result.failure_reason in (
            "concrete_crushing", "rebar_fracture", ""
        )

    def test_with_axial_compression(self, simple_beam):
        # 500 kN compression should increase moment capacity
        analysis_0 = MomentCurvatureAnalysis(simple_beam, axial_load=0)
        result_0 = analysis_0.run()

        analysis_c = MomentCurvatureAnalysis(simple_beam, axial_load=-500e3)
        result_c = analysis_c.run()

        # Moderate compression should increase moment capacity
        mu_0 = result_0.ultimate_moment
        mu_c = result_c.ultimate_moment
        assert mu_c > mu_0 * 0.8  # shouldn't be drastically less

    def test_with_axial_tension(self, simple_beam):
        analysis = MomentCurvatureAnalysis(simple_beam, axial_load=200e3)
        result = analysis.run()
        assert len(result.points) > 0

    def test_convergence(self, simple_beam):
        analysis = MomentCurvatureAnalysis(simple_beam, tol_force=0.1)
        result = analysis.run()
        for p in result.points:
            assert p.converged, f"Not converged at phi={p.curvature}"

    def test_result_serialization(self, simple_beam):
        analysis = MomentCurvatureAnalysis(simple_beam, n_steps=20)
        result = analysis.run()
        d = result.to_dict()
        assert "response" in d
        assert len(d["response"]) == len(result.points)
        assert "moment_kNm" in d["response"][0]

    def test_to_dict_spec_structure(self, simple_beam):
        """to_dict should produce the spec-compliant output structure."""
        analysis = MomentCurvatureAnalysis(simple_beam, n_steps=20)
        result = analysis.run()
        d = result.to_dict()

        # Top-level keys
        assert "control_curves" in d
        assert "analysis_points" in d
        assert "summary" in d
        assert "response" in d

        # M-phi control curve
        assert "moment_curvature" in d["control_curves"]
        mphi = d["control_curves"]["moment_curvature"]
        assert mphi["x_axis"] == "curvature"
        assert mphi["y_axis"] == "moment"
        assert len(mphi["data"]) > 0
        assert "curvature" in mphi["data"][0]
        assert "moment" in mphi["data"][0]

        # M-ex control curve
        assert "moment_axial_strain" in d["control_curves"]
        mex = d["control_curves"]["moment_axial_strain"]
        assert mex["x_axis"] == "axial_strain"
        assert mex["y_axis"] == "moment"
        assert len(mex["data"]) > 0
        assert "axial_strain" in mex["data"][0]
        assert "moment" in mex["data"][0]

        # Both curves should have the same number of converged points
        assert len(mphi["data"]) == len(mex["data"])

    def test_to_dict_unit_conversions(self, simple_beam):
        """Control curve units should match the output spec."""
        analysis = MomentCurvatureAnalysis(simple_beam, n_steps=10)
        result = analysis.run()
        d = result.to_dict()

        # Pick the first converged point from raw response
        raw = d["response"][0]
        # Curvature: raw 1/mm -> mrad/m (x1e6)
        mphi_data = d["control_curves"]["moment_curvature"]["data"][0]
        assert mphi_data["curvature"] == pytest.approx(
            raw["curvature_1_per_mm"] * 1e6
        )
        # Moment: raw N-mm -> kNm (/ 1e6)
        assert mphi_data["moment"] == pytest.approx(
            raw["moment_Nmm"] / 1e6
        )
        # Axial strain: raw -> mm/m (x1e3)
        mex_data = d["control_curves"]["moment_axial_strain"]["data"][0]
        assert mex_data["axial_strain"] == pytest.approx(
            raw["eps_0"] * 1e3
        )

    def test_summary_section(self, simple_beam):
        """Summary should contain section_behavior, failure, convergence."""
        analysis = MomentCurvatureAnalysis(simple_beam, n_steps=50)
        result = analysis.run()
        d = result.to_dict()

        summary = d["summary"]
        assert "section_behavior" in summary
        assert "failure" in summary
        assert "convergence" in summary
        assert summary["convergence"]["total_points"] == len(result.points)


class TestMomentCurvatureHandCalc:
    """Cross-check against simple hand calculations."""

    def test_elastic_stiffness(self):
        """Check that initial M/phi matches E*Ig (approximately)."""
        shape = RectangularSection(b=300, h=500)
        concrete = Concrete(fc=30)
        steel = ReinforcingSteel(fy=400)
        xs = CrossSection.from_shape(shape, concrete, n_layers=200)
        # No rebar — pure concrete
        analysis = MomentCurvatureAnalysis(xs, n_steps=50, max_curvature=1e-6)
        result = analysis.run()

        # First point (small curvature, elastic)
        p = result.points[0]
        EI_numerical = p.moment / p.curvature if p.curvature > 0 else 0
        EI_analytical = concrete.Ec * 300 * 500 ** 3 / 12.0

        assert EI_numerical == pytest.approx(EI_analytical, rel=0.05)
