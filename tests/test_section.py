"""Tests for section geometry and discretisation."""

import unittest

from response_yolo.materials import Concrete, Steel
from response_yolo.section import DiscretisedSection, RebarGroup, Section


class TestSectionGeometry(unittest.TestCase):
    def test_rectangle_basic(self):
        c = Concrete(fc=30)
        s = Section.rectangle(300, 500, c)
        self.assertEqual(s.height, 500)
        self.assertEqual(s.y_top, 0.0)
        self.assertEqual(s.y_bot, 500.0)

    def test_gross_area(self):
        c = Concrete(fc=30)
        s = Section.rectangle(300, 500, c)
        self.assertAlmostEqual(s.gross_area(), 300 * 500)

    def test_centroid_rectangle(self):
        c = Concrete(fc=30)
        s = Section.rectangle(300, 500, c)
        self.assertAlmostEqual(s.gross_centroid(), 250.0)

    def test_moment_of_inertia_rectangle(self):
        c = Concrete(fc=30)
        s = Section.rectangle(300, 500, c)
        expected = 300 * 500**3 / 12.0
        self.assertAlmostEqual(s.gross_moment_of_inertia(), expected, delta=expected * 0.01)


class TestDiscretisation(unittest.TestCase):
    def test_fibre_count(self):
        c = Concrete(fc=30)
        s = Section.rectangle(300, 500, c)
        ds = DiscretisedSection.from_section(s, n_fibres=50)
        self.assertEqual(len(ds.concrete_fibres), 50)

    def test_total_area_matches(self):
        c = Concrete(fc=30)
        s = Section.rectangle(300, 500, c)
        ds = DiscretisedSection.from_section(s, n_fibres=80)
        total_a = sum(f.area for f in ds.concrete_fibres)
        self.assertAlmostEqual(total_a, 300 * 500, places=1)

    def test_rebar_passed_through(self):
        c = Concrete(fc=30)
        steel = Steel(fy=400)
        rebar = [RebarGroup(area=1000, depth=450, steel=steel, label="bot")]
        s = Section.rectangle(300, 500, c, rebar=rebar)
        ds = DiscretisedSection.from_section(s)
        self.assertEqual(len(ds.steel_fibres), 1)
        self.assertEqual(ds.steel_fibres[0].area, 1000)


if __name__ == "__main__":
    unittest.main()
