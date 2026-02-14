"""Tests for concrete and steel material models."""

import math
import unittest

from response_yolo.materials import Concrete, Steel


class TestConcrete(unittest.TestCase):
    def test_defaults(self):
        c = Concrete(fc=40)
        self.assertAlmostEqual(c._Ec, 4500 * math.sqrt(40), places=1)
        self.assertAlmostEqual(c._ft, 0.33 * math.sqrt(40), places=4)
        self.assertLess(c._ec0, 0)

    def test_zero_strain_zero_stress(self):
        c = Concrete(fc=30)
        self.assertEqual(c.stress(0.0), 0.0)

    def test_compression_peak(self):
        c = Concrete(fc=40)
        sigma = c.stress(c._ec0)
        self.assertAlmostEqual(sigma, -40.0, delta=0.1)

    def test_compression_is_negative(self):
        c = Concrete(fc=30)
        for eps in [-0.0005, -0.001, -0.002]:
            self.assertLess(c.stress(eps), 0.0)

    def test_tension_linear_before_cracking(self):
        c = Concrete(fc=40)
        eps = c._ecr * 0.5
        expected = c._Ec * eps
        self.assertAlmostEqual(c.stress(eps), expected, places=3)

    def test_tension_stiffening_decays(self):
        c = Concrete(fc=40)
        s1 = c.stress(c._ecr * 2)
        s2 = c.stress(c._ecr * 10)
        self.assertGreater(s1, s2)
        self.assertGreater(s2, 0)

    def test_no_tension_stiffening(self):
        c = Concrete(fc=40, tension_stiffening=False)
        self.assertEqual(c.stress(c._ecr * 2), 0.0)

    def test_invalid_fc_raises(self):
        with self.assertRaises(ValueError):
            Concrete(fc=-10)


class TestSteel(unittest.TestCase):
    def test_elastic_range(self):
        s = Steel(fy=400, Es=200_000)
        self.assertAlmostEqual(s.stress(0.001), 200.0, places=1)

    def test_yield_plateau(self):
        s = Steel(fy=400, Es=200_000)
        self.assertAlmostEqual(s.stress(0.005), 400.0, places=1)

    def test_symmetric(self):
        s = Steel(fy=400, Es=200_000)
        self.assertAlmostEqual(s.stress(0.003), -s.stress(-0.003), places=6)

    def test_strain_hardening(self):
        s = Steel(fy=400, Es=200_000, fu=600, esh=0.01, esu=0.10)
        self.assertAlmostEqual(s.stress(0.01), 400.0, places=1)
        mid_eps = (0.01 + 0.10) / 2.0
        mid_stress = s.stress(mid_eps)
        self.assertGreater(mid_stress, 400)
        self.assertLess(mid_stress, 600)
        self.assertAlmostEqual(s.stress(0.10), 600.0, places=1)

    def test_invalid_fy_raises(self):
        with self.assertRaises(ValueError):
            Steel(fy=0)


if __name__ == "__main__":
    unittest.main()
