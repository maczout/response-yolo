"""
JSON input/output for response-yolo.

The JSON format is designed for inclusion in automated workflows
(CI/CD, parameter studies, optimisation loops).

Input JSON schema:
==================
{
  "units": "SI",
  "section": {
    "shape": "rectangular",
    "b": 300, "h": 500
  },
  "concrete": {
    "fc": 35, "ecu": 0.0035,
    "compression_model": "popovics",
    "tension_model": "mcft"
  },
  "long_steel": {
    "fy": 400, "Es": 200000, "fu": 600, "esu": 0.05
  },
  "rebars": [
    {"y": 50, "area": 1500},
    {"y": 450, "area": 1500}
  ],
  "tendons": [],
  "loading": {"N": 0},
  "analysis": {
    "type": "moment_curvature",
    "n_steps": 200,
    "max_curvature": null
  }
}

Output JSON schema:
===================
{
  "version": "0.1.0",
  "analysis_type": "moment_curvature",
  "input_file": "...",
  "section_properties": { ... },
  "result": { ... }   // from MPhiResult.to_dict()
}
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Dict

from response_yolo.materials.concrete import Concrete, CompressionModel, TensionModel
from response_yolo.materials.steel import ReinforcingSteel, SteelModel
from response_yolo.materials.prestressing import PrestressingSteel, PrestressModel
from response_yolo.section.geometry import (
    RectangularSection,
    TeeSection,
    CircularSection,
)
from response_yolo.section.rebar import RebarBar
from response_yolo.section.tendon import Tendon
from response_yolo.section.cross_section import CrossSection


def load_json_input(filepath: str | Path) -> Dict[str, Any]:
    """Load a JSON input file and return a configuration dictionary.

    Returns dict with same structure as parse_r2t():
      "section", "analysis_type", "analysis_params", "loading", "units", "metadata"
    """
    filepath = Path(filepath)
    with open(filepath) as f:
        data = json.load(f)

    # Parse concrete
    cd = data.get("concrete", {})
    concrete = Concrete(
        fc=cd.get("fc", 30.0),
        ec=cd.get("ec"),
        Ec=cd.get("Ec"),
        ft=cd.get("ft"),
        ecu=cd.get("ecu", 0.0035),
        compression_model=CompressionModel(cd.get("compression_model", "popovics")),
        tension_model=TensionModel(cd.get("tension_model", "mcft")),
        aggregate_size=cd.get("aggregate_size", 19.0),
    )

    # Parse section shape
    sd = data.get("section", {})
    shape_type = sd.get("shape", "rectangular").lower()
    n_layers = data.get("analysis", {}).get("n_layers", 100)

    if shape_type == "circular":
        shape = CircularSection(diameter=sd.get("diameter", sd.get("d", 500)))
    elif shape_type in ("tee", "t"):
        shape = TeeSection(
            bw=sd.get("bw", 300),
            hw=sd.get("hw", 400),
            bf=sd.get("bf", 600),
            hf=sd.get("hf", 100),
        )
    else:
        shape = RectangularSection(
            b=sd.get("b", 300),
            h=sd.get("h", 500),
        )

    xs = CrossSection.from_shape(shape, concrete, n_layers=n_layers)

    # Parse steel
    steel_d = data.get("long_steel", {})
    steel = ReinforcingSteel(
        fy=steel_d.get("fy", 400.0),
        Es=steel_d.get("Es", 200_000.0),
        fu=steel_d.get("fu"),
        esh=steel_d.get("esh"),
        esu=steel_d.get("esu", 0.05),
        model=SteelModel(steel_d.get("model", "trilinear")),
    )

    # Add rebars
    for rd in data.get("rebars", []):
        bar_steel = steel
        if "fy" in rd:
            bar_steel = ReinforcingSteel(
                fy=rd["fy"],
                Es=rd.get("Es", steel.Es),
                fu=rd.get("fu", steel.fu),
                esu=rd.get("esu", steel.esu),
            )
        if "n_bars" in rd and "diameter" in rd:
            area = rd["n_bars"] * math.pi / 4 * rd["diameter"] ** 2
        else:
            area = rd["area"]
        xs.add_rebar(RebarBar(y=rd["y"], area=area, material=bar_steel))

    # Add tendons
    for td in data.get("tendons", []):
        ps_mat = PrestressingSteel(
            fpu=td.get("fpu", 1860.0),
            Ep=td.get("Ep", 196_500.0),
            fpy=td.get("fpy"),
            epu=td.get("epu", 0.04),
        )
        xs.add_tendon(Tendon(
            y=td["y"],
            area=td["area"],
            material=ps_mat,
            prestrain=td.get("prestrain", 0.005),
        ))

    # Parse transverse steel (stirrups)
    ts = data.get("trans_steel", None)
    if ts is not None:
        stirrup_mat = ReinforcingSteel(
            fy=ts.get("fy", steel.fy),
            Es=ts.get("Es", steel.Es),
        )
        xs.set_stirrups(
            Av=ts["Av"],
            s=ts["s"],
            material=stirrup_mat,
            y_bot=ts.get("y_bot"),
            y_top=ts.get("y_top"),
        )

    # Analysis params
    analysis = data.get("analysis", {})
    loading = data.get("loading", {})

    return {
        "section": xs,
        "analysis_type": analysis.get("type", "moment_curvature"),
        "analysis_params": analysis,
        "loading": {
            "N": loading.get("N", 0.0),
            "M": loading.get("M", 0.0),
            "V": loading.get("V", 0.0),
        },
        "units": data.get("units", "SI"),
        "metadata": {"source_file": str(filepath)},
    }


def save_json_output(
    result_dict: Dict[str, Any],
    filepath: str | Path,
    input_file: str = "",
    analysis_type: str = "moment_curvature",
    section_props: Dict[str, Any] | None = None,
    computation_time: float | None = None,
) -> None:
    """Save analysis results to a JSON file.

    Produces the spec-compliant output envelope with metadata, units,
    section_properties, and results.
    """
    import datetime
    from response_yolo import __version__

    # Determine input format from file extension
    input_format = "response_yolo_json"
    if input_file.endswith(".r2t"):
        input_format = "r2t"

    output = {
        "metadata": {
            "version": "1.0.0",
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "generator": f"response-yolo v{__version__}",
            "analysis_type": analysis_type,
            "input_source": {
                "format": input_format,
                "file": input_file,
            },
        },
        "units": {
            "length": "mm",
            "force": "kN",
            "stress": "MPa",
            "moment": "kNm",
            "strain": "mm/m",
            "curvature": "mrad/m",
        },
        "section_properties": section_props or {},
        "results": result_dict,
    }

    if computation_time is not None:
        output["metadata"]["computation_time"] = computation_time

    filepath = Path(filepath)
    with open(filepath, "w") as f:
        json.dump(output, f, indent=2, default=_json_default)


def _json_default(obj):
    """Handle non-serializable types."""
    if hasattr(obj, "to_dict"):
        return obj.to_dict()
    if isinstance(obj, float) and (math.isnan(obj) or math.isinf(obj)):
        return str(obj)
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")
