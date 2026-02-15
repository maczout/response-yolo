"""Tests verifying stubs raise NotImplementedError."""

import pytest

from response_yolo.materials.concrete import Concrete
from response_yolo.section.geometry import RectangularSection
from response_yolo.section.cross_section import CrossSection
from response_yolo.analysis.stubs import (
    MomentShearInteraction,
    MemberResponseAnalysis,
    PushoverAnalysis,
)


@pytest.fixture
def section():
    shape = RectangularSection(b=300, h=500)
    concrete = Concrete(fc=30)
    return CrossSection.from_shape(shape, concrete)


def test_moment_shear_stub(section):
    with pytest.raises(NotImplementedError, match="MomentShearInteraction"):
        MomentShearInteraction(section).run()


def test_member_response_stub(section):
    with pytest.raises(NotImplementedError, match="MemberResponseAnalysis"):
        MemberResponseAnalysis(section, length=5000).run()


def test_pushover_stub(section):
    with pytest.raises(NotImplementedError, match="PushoverAnalysis"):
        PushoverAnalysis(section, length=3000).run()
