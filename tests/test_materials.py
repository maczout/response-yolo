"""Tests for material constitutive models."""

import math
import pytest

from response_yolo.materials.concrete import Concrete, CompressionModel, TensionModel
from response_yolo.materials.steel import ReinforcingSteel, SteelModel
from response_yolo.materials.prestressing import PrestressingSteel


class TestConcrete:
    def test_defaults(self):
        c = Concrete(fc=30)
        assert c.fc == 30
        assert c.Ec == pytest.approx(3320 * math.sqrt(30) + 6900, rel=1e-6)
        assert c.ft == pytest.approx(0.33 * math.sqrt(30), rel=1e-6)
        assert c.ecu == 0.0035

    def test_zero_strain(self):
        c = Concrete(fc=35)
        assert c.stress(0.0) == 0.0

    def test_compression_peak(self):
        c = Concrete(fc=35)
        # At peak strain, stress should be close to fc
        s = c.stress(-c.ec)
        assert abs(s + 35.0) < 2.0  # within ~2 MPa of fc

    def test_compression_is_negative(self):
        c = Concrete(fc=40)
        assert c.stress(-0.001) < 0

    def test_tension_elastic(self):
        c = Concrete(fc=30)
        eps = c.ecr * 0.5  # half of cracking strain
        s = c.stress(eps)
        assert s > 0
        assert s == pytest.approx(c.Ec * eps, rel=1e-3)

    def test_mcft_tension_stiffening(self):
        c = Concrete(fc=30)
        eps = 0.005  # well past cracking
        s = c.stress(eps)
        # MCFT: ft / (1 + sqrt(500*eps))
        expected = c.ft / (1 + math.sqrt(500 * 0.005))
        assert s == pytest.approx(expected, rel=1e-3)
        assert s < c.ft  # must be less than cracking stress

    def test_no_tension(self):
        c = Concrete(fc=30, tension_model=TensionModel.NO_TENSION)
        assert c.stress(0.001) == 0.0

    def test_crushed(self):
        c = Concrete(fc=30)
        assert c.stress(-0.01) == 0.0  # beyond ecu

    def test_hognestad(self):
        c = Concrete(fc=30, compression_model=CompressionModel.HOGNESTAD)
        s = c.stress(-c.ec)
        assert abs(s + 30.0) < 1.0  # peak should be ~fc

    def test_serialization(self):
        c = Concrete(fc=40, ecu=0.004)
        d = c.to_dict()
        c2 = Concrete.from_dict(d)
        assert c2.fc == 40
        assert c2.ecu == 0.004


class TestReinforcingSteel:
    def test_elastic(self):
        s = ReinforcingSteel(fy=400)
        eps = 0.001  # well within elastic
        stress = s.stress(eps)
        assert stress == pytest.approx(200000 * 0.001, rel=1e-3)

    def test_yield(self):
        s = ReinforcingSteel(fy=400, fu=400)  # perfectly plastic
        eps = 0.01  # past yield
        stress = s.stress(eps)
        assert stress == pytest.approx(400, rel=0.05)

    def test_symmetric(self):
        s = ReinforcingSteel(fy=400)
        eps = 0.001
        assert s.stress(eps) == pytest.approx(-s.stress(-eps), rel=1e-6)

    def test_fracture(self):
        s = ReinforcingSteel(fy=400, esu=0.05)
        assert s.stress(0.06) == 0.0

    def test_trilinear_hardening(self):
        s = ReinforcingSteel(fy=400, fu=600, esh=0.01, esu=0.05)
        stress_at_esh = s.stress(0.01)
        stress_at_middle = s.stress(0.03)
        assert stress_at_esh == pytest.approx(400, rel=0.02)
        assert stress_at_middle > 400
        assert stress_at_middle < 600

    def test_serialization(self):
        s = ReinforcingSteel(fy=500, fu=650)
        d = s.to_dict()
        s2 = ReinforcingSteel.from_dict(d)
        assert s2.fy == 500
        assert s2.fu == 650


class TestPrestressingSteel:
    def test_elastic(self):
        ps = PrestressingSteel(fpu=1860)
        eps = 0.001
        stress = ps.stress(eps)
        assert stress == pytest.approx(196500 * 0.001, rel=0.01)

    def test_no_compression(self):
        ps = PrestressingSteel(fpu=1860)
        assert ps.stress(-0.001) == 0.0

    def test_rupture(self):
        ps = PrestressingSteel(fpu=1860, epu=0.04)
        assert ps.stress(0.05) == 0.0

    def test_near_ultimate(self):
        ps = PrestressingSteel(fpu=1860)
        stress = ps.stress(0.035)
        # Should be close to fpu
        assert stress > 1700
        assert stress <= 1860
