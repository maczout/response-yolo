"""JSON input parsing and output serialisation.

Input schema
------------
See ``examples/example_input.json`` and the user guide for the full schema.
The top-level keys are:

* ``"concrete"`` – concrete material properties
* ``"steel"``    – steel material properties (may be a dict keyed by label)
* ``"section"``  – section geometry (``"type": "rectangle"`` for now)
* ``"rebar"``    – list of reinforcing bar groups
* ``"analysis"`` – analysis control parameters
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .analysis import MomentCurvatureAnalysis, MomentCurvatureResult
from .materials import Concrete, Steel
from .section import DiscretisedSection, RebarGroup, Section


# ---------------------------------------------------------------------------
# Input parsing
# ---------------------------------------------------------------------------

def _parse_concrete(data: dict[str, Any]) -> Concrete:
    return Concrete(
        fc=data["fc"],
        ec0=data.get("ec0"),
        ft=data.get("ft"),
        Ec=data.get("Ec"),
        tension_stiffening=data.get("tension_stiffening", True),
    )


def _parse_steels(data: Any) -> dict[str, Steel]:
    """Parse steel definitions.

    Accepts either a single dict (applied to all bars) or a dict-of-dicts
    keyed by label.
    """
    if "fy" in data:
        # Single steel definition
        s = Steel(
            fy=data["fy"],
            Es=data.get("Es", 200_000.0),
            fu=data.get("fu"),
            esh=data.get("esh", 0.01),
            esu=data.get("esu", 0.10),
        )
        return {"default": s}

    steels: dict[str, Steel] = {}
    for label, sdata in data.items():
        steels[label] = Steel(
            fy=sdata["fy"],
            Es=sdata.get("Es", 200_000.0),
            fu=sdata.get("fu"),
            esh=sdata.get("esh", 0.01),
            esu=sdata.get("esu", 0.10),
        )
    return steels


def _parse_section(
    sec_data: dict[str, Any],
    concrete: Concrete,
    rebar_data: list[dict[str, Any]],
    steels: dict[str, Steel],
) -> Section:
    sec_type = sec_data.get("type", "rectangle")
    if sec_type != "rectangle":
        raise ValueError(f"Unsupported section type: {sec_type!r}. Only 'rectangle' is supported.")

    width = sec_data["width"]
    height = sec_data["height"]

    rebar_groups: list[RebarGroup] = []
    for rd in rebar_data:
        steel_label = rd.get("steel", "default")
        steel = steels.get(steel_label)
        if steel is None:
            raise ValueError(
                f"Rebar group references undefined steel label {steel_label!r}"
            )
        rebar_groups.append(
            RebarGroup(
                area=rd["area"],
                depth=rd["depth"],
                steel=steel,
                label=rd.get("label", ""),
            )
        )

    return Section.rectangle(width, height, concrete, rebar_groups)


def parse_input(data: dict[str, Any]) -> tuple[Section, dict[str, Any]]:
    """Parse a full input dict and return (Section, analysis_params)."""
    concrete = _parse_concrete(data["concrete"])
    steels = _parse_steels(data.get("steel", {"fy": 400}))
    section = _parse_section(
        data["section"],
        concrete,
        data.get("rebar", []),
        steels,
    )
    analysis_params = data.get("analysis", {})
    return section, analysis_params


def load_input(path: str | Path) -> tuple[Section, dict[str, Any]]:
    """Load a JSON input file and return (Section, analysis_params)."""
    with open(path) as f:
        data = json.load(f)
    return parse_input(data)


# ---------------------------------------------------------------------------
# Output serialisation
# ---------------------------------------------------------------------------

def format_output(result: MomentCurvatureResult) -> dict[str, Any]:
    """Convert analysis results to a JSON-serialisable dict."""
    return {
        "analysis": "moment_curvature",
        "units": {
            "curvature": "1/mm",
            "moment": "kN·m",
            "strain": "mm/mm",
        },
        "results": result.to_dict(),
    }


def write_output(result: MomentCurvatureResult, path: str | Path) -> None:
    """Write analysis results to a JSON file."""
    with open(path, "w") as f:
        json.dump(format_output(result), f, indent=2)
    # stderr message handled by CLI


def results_to_json(result: MomentCurvatureResult) -> str:
    """Return analysis results as a JSON string."""
    return json.dumps(format_output(result), indent=2)
