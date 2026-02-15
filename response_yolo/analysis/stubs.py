"""
Stubs for analysis types not yet implemented.

These mirror the full analysis capabilities of Response-2000:
  - Shear analysis (V-gamma sectional response)
  - Moment-shear interaction (M-V failure envelope)
  - Full member response (load-deflection with shear)
  - Pushover / load-deformation

Each stub raises NotImplementedError with a description of what
the analysis would do when implemented.
"""

from __future__ import annotations

from response_yolo.section.cross_section import CrossSection


class ShearAnalysis:
    """Sectional shear analysis using the Modified Compression Field Theory.

    When implemented, this will:
    - Discretise the section into biaxial layers
    - For each layer, solve the MCFT equilibrium/compatibility/constitutive
      equations to find the shear stress distribution
    - Integrate to get total V for a given gamma (shear strain)
    - Produce V-gamma response curves
    - Check aggregate interlock (crack-check) per Vecchio & Collins (1986)

    Reference: Vecchio & Collins (1986); Bentz (2000), Chapters 2-4.
    """

    def __init__(self, section: CrossSection, **kwargs) -> None:
        self.section = section
        self.kwargs = kwargs

    def run(self):
        raise NotImplementedError(
            "ShearAnalysis is not yet implemented. "
            "This will implement the MCFT-based V-gamma sectional analysis "
            "as described in Bentz (2000), Chapter 4."
        )


class MomentShearInteraction:
    """Moment-shear (M-V) interaction analysis.

    When implemented, this will:
    - For a grid of (M, V) combinations, run the full MCFT sectional analysis
    - Determine if the section can sustain each (M, V) combination
    - Produce the M-V failure envelope
    - Identify failure modes (flexure, shear, combined)

    Reference: Bentz (2000), Chapter 4.
    """

    def __init__(self, section: CrossSection, **kwargs) -> None:
        self.section = section
        self.kwargs = kwargs

    def run(self):
        raise NotImplementedError(
            "MomentShearInteraction is not yet implemented. "
            "This will produce M-V failure envelopes using iterative "
            "MCFT analysis at each (M,V) load point."
        )


class MemberResponseAnalysis:
    """Full member (beam/column) load-deflection analysis.

    When implemented, this will:
    - Model the member as a series of sections along its length
    - Apply loading (point loads, distributed, etc.)
    - At each load step, compute sectional response (M, V, N) at each section
    - Integrate curvatures to get deflections
    - Account for shear deformations via MCFT
    - Handle tension stiffening between cracks
    - Produce load-deflection response

    Reference: Bentz (2000), Chapter 5.
    """

    def __init__(self, section: CrossSection, length: float = 0.0, **kwargs) -> None:
        self.section = section
        self.length = length
        self.kwargs = kwargs

    def run(self):
        raise NotImplementedError(
            "MemberResponseAnalysis is not yet implemented. "
            "This will model the full member with distributed plasticity "
            "and MCFT-based shear, as described in Bentz (2000), Chapter 5."
        )


class PushoverAnalysis:
    """Pushover / load-deformation analysis for columns/frames.

    When implemented, this will:
    - Apply monotonically increasing lateral load
    - Track P-delta effects
    - Compute force-displacement response
    - Identify strength and ductility limits

    Reference: Bentz (2000), Chapter 5; R2K user manual.
    """

    def __init__(self, section: CrossSection, length: float = 0.0, **kwargs) -> None:
        self.section = section
        self.length = length
        self.kwargs = kwargs

    def run(self):
        raise NotImplementedError(
            "PushoverAnalysis is not yet implemented. "
            "This will perform incremental lateral load analysis with "
            "P-delta effects for column/frame assessment."
        )
