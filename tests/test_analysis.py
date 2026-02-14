"""Tests for moment-curvature analysis."""

import unittest

from response_yolo.analysis import (
    AxialForceAnalysis,
    FullSectionalAnalysis,
    MomentCurvatureAnalysis,
    ShearAnalysis,
)
from response_yolo.materials import Concrete, Steel
from response_yolo.section import DiscretisedSection, RebarGroup, Section


def _make_typical_section() -> DiscretisedSection:
    """300x500 beam with 3-20M bottom bars (As=900mm2), 2-15M top (As=400mm2)."""
    c = Concrete(fc=35)
    steel = Steel(fy=400, Es=200_000, fu=600, esh=0.01, esu=0.10)
    rebar = [
        RebarGroup(area=400, depth=50, steel=steel, label="top"),
        RebarGroup(area=900, depth=450, steel=steel, label="bot"),
    ]
    section = Section.rectangle(300, 500, c, rebar=rebar)
    return DiscretisedSection.from_section(section, n_fibres=80)


class TestMomentCurvature(unittest.TestCase):
    def test_origin_is_zero(self):
        ds = _make_typical_section()
        analysis = MomentCurvatureAnalysis(section=ds, n_steps=10)
        result = analysis.run()
        self.assertEqual(result.points[0].curvature, 0.0)
        self.assertEqual(result.points[0].moment, 0.0)

    def test_positive_moment_for_positive_curvature(self):
        ds = _make_typical_section()
        analysis = MomentCurvatureAnalysis(section=ds, n_steps=20)
        result = analysis.run()
        positive_count = sum(1 for p in result.points if p.moment > 0)
        self.assertGreaterEqual(positive_count, len(result.points) - 2)

    def test_moment_increases_initially(self):
        ds = _make_typical_section()
        analysis = MomentCurvatureAnalysis(section=ds, n_steps=100)
        result = analysis.run()
        # The first few increments should show increasing moment (elastic range)
        for i in range(1, min(5, len(result.points))):
            self.assertGreater(result.points[i].moment, result.points[i - 1].moment)

    def test_peak_moment_reasonable(self):
        ds = _make_typical_section()
        analysis = MomentCurvatureAnalysis(section=ds, n_steps=50)
        result = analysis.run()
        peak_kNm = result.peak_moment() / 1e6
        self.assertGreater(peak_kNm, 100)
        self.assertLess(peak_kNm, 250)

    def test_result_to_dict(self):
        ds = _make_typical_section()
        analysis = MomentCurvatureAnalysis(section=ds, n_steps=5)
        result = analysis.run()
        d = result.to_dict()
        self.assertIn("points", d)
        self.assertIn("peak_moment_kNm", d)
        self.assertEqual(len(d["points"]), 6)

    def test_custom_max_curvature(self):
        ds = _make_typical_section()
        phi_max = 5e-5
        analysis = MomentCurvatureAnalysis(section=ds, max_curvature=phi_max, n_steps=10)
        result = analysis.run()
        self.assertAlmostEqual(result.points[-1].curvature, phi_max, places=10)


class TestStubs(unittest.TestCase):
    def test_axial_not_implemented(self):
        with self.assertRaises(NotImplementedError):
            AxialForceAnalysis()

    def test_shear_not_implemented(self):
        with self.assertRaises(NotImplementedError):
            ShearAnalysis()

    def test_full_not_implemented(self):
        with self.assertRaises(NotImplementedError):
            FullSectionalAnalysis()


if __name__ == "__main__":
    unittest.main()
