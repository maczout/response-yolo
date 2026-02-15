"""Tests for cross-section geometry and properties."""

import math
import pytest

from response_yolo.materials.concrete import Concrete
from response_yolo.materials.steel import ReinforcingSteel
from response_yolo.section.geometry import (
    RectangularSection,
    TeeSection,
    CircularSection,
)
from response_yolo.section.rebar import RebarBar, RebarLayer
from response_yolo.section.cross_section import CrossSection


class TestRectangularSection:
    def test_area(self):
        s = RectangularSection(b=300, h=500)
        c = Concrete(fc=30)
        layers = s.discretise(c, n_layers=100)
        total_area = sum(l.area for l in layers)
        assert total_area == pytest.approx(300 * 500, rel=1e-3)

    def test_width(self):
        s = RectangularSection(b=300, h=500)
        assert s.width_at(250) == 300
        assert s.width_at(0) == 300
        assert s.width_at(500) == 300
        assert s.width_at(-1) == 0

    def test_height(self):
        s = RectangularSection(b=300, h=500)
        assert s.height == 500


class TestTeeSection:
    def test_area(self):
        s = TeeSection(bw=300, hw=400, bf=800, hf=100)
        c = Concrete(fc=30)
        layers = s.discretise(c, n_layers=200)
        total_area = sum(l.area for l in layers)
        expected = 300 * 400 + 800 * 100  # web + flange
        assert total_area == pytest.approx(expected, rel=0.02)

    def test_width_web(self):
        s = TeeSection(bw=300, hw=400, bf=800, hf=100)
        assert s.width_at(200) == 300

    def test_width_flange(self):
        s = TeeSection(bw=300, hw=400, bf=800, hf=100)
        assert s.width_at(450) == 800


class TestCircularSection:
    def test_area(self):
        d = 500
        s = CircularSection(diameter=d)
        c = Concrete(fc=30)
        layers = s.discretise(c, n_layers=200)
        total_area = sum(l.area for l in layers)
        expected = math.pi / 4 * d ** 2
        assert total_area == pytest.approx(expected, rel=0.01)


class TestCrossSection:
    def test_centroid_rectangular(self):
        shape = RectangularSection(b=300, h=500)
        c = Concrete(fc=30)
        xs = CrossSection.from_shape(shape, c)
        assert xs.centroid_y == pytest.approx(250, rel=0.01)

    def test_gross_area(self):
        shape = RectangularSection(b=300, h=500)
        c = Concrete(fc=30)
        xs = CrossSection.from_shape(shape, c)
        assert xs.gross_area == pytest.approx(150000, rel=0.01)

    def test_moment_of_inertia(self):
        shape = RectangularSection(b=300, h=500)
        c = Concrete(fc=30)
        xs = CrossSection.from_shape(shape, c, n_layers=200)
        expected = 300 * 500 ** 3 / 12.0
        assert xs.gross_moment_of_inertia == pytest.approx(expected, rel=0.01)

    def test_add_rebar(self):
        shape = RectangularSection(b=300, h=500)
        c = Concrete(fc=30)
        steel = ReinforcingSteel(fy=400)
        xs = CrossSection.from_shape(shape, c)
        xs.add_rebar(RebarBar(y=50, area=1500, material=steel))
        assert len(xs.rebars) == 1
        assert xs.rebars[0].area == 1500

    def test_force_integration_zero_strain(self):
        shape = RectangularSection(b=300, h=500)
        c = Concrete(fc=30)
        xs = CrossSection.from_shape(shape, c)
        N, M = xs.integrate_forces(0.0, 0.0, 250.0)
        assert abs(N) < 1.0
        assert abs(M) < 1.0

    def test_rebar_layer(self):
        steel = ReinforcingSteel(fy=400)
        layer = RebarLayer(y=50, n_bars=3, bar_diameter=25, material=steel)
        assert layer.total_area == pytest.approx(3 * math.pi / 4 * 25**2, rel=1e-6)
        bar = layer.to_bar()
        assert bar.area == pytest.approx(layer.total_area, rel=1e-6)
