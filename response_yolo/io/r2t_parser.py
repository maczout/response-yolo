"""
Parser for Response-2000 *.r2t text input files.

R2T Format Overview (Bentz, Appendix A):
=========================================

R2T is a line-oriented text format.  Key sections:

  [UNITS]         - "SI" or "US"
  [SECTION]       - Section geometry definition
  [CONCRETE]      - Concrete material properties
  [LONG STEEL]    - Longitudinal reinforcing steel
  [TRANS STEEL]   - Transverse reinforcing steel (stirrups)
  [REBAR]         - Individual bar placements
  [TENDON]        - Prestressing tendons
  [LOADING]       - Applied loads (N, M, V)
  [ANALYSIS]      - Analysis type and parameters

Lines starting with '#' or ';' are comments.
Blank lines are ignored.
Section headers are in square brackets.

This parser reads the most common R2T constructs and builds
a CrossSection + analysis configuration.  Unsupported features
produce warnings rather than errors.
"""

from __future__ import annotations

import re
import warnings
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from response_yolo.materials.concrete import Concrete, CompressionModel, TensionModel
from response_yolo.materials.steel import ReinforcingSteel, SteelModel
from response_yolo.materials.prestressing import PrestressingSteel, PrestressModel
from response_yolo.section.geometry import RectangularSection, TeeSection, CircularSection
from response_yolo.section.rebar import RebarBar
from response_yolo.section.tendon import Tendon
from response_yolo.section.cross_section import CrossSection


def parse_r2t(filepath: str | Path) -> Dict[str, Any]:
    """Parse an R2T file and return a configuration dictionary.

    Returns
    -------
    dict with keys:
        "section" : CrossSection
        "analysis_type" : str  ("moment_curvature", "shear", etc.)
        "analysis_params" : dict
        "units" : str  ("SI" or "US")
        "metadata" : dict
    """
    filepath = Path(filepath)
    if not filepath.exists():
        raise FileNotFoundError(f"R2T file not found: {filepath}")

    text = filepath.read_text()
    lines = text.splitlines()

    # Parse into sections
    sections: Dict[str, list] = {}
    current_section = "_header"
    sections[current_section] = []

    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or stripped.startswith(";"):
            continue
        m = re.match(r"^\[(.+)\]$", stripped)
        if m:
            current_section = m.group(1).upper()
            sections.setdefault(current_section, [])
        else:
            sections.setdefault(current_section, []).append(stripped)

    # Determine units
    units = "SI"
    if "UNITS" in sections:
        for line in sections["UNITS"]:
            if "US" in line.upper():
                units = "US"

    # Parse concrete
    concrete = _parse_concrete(sections.get("CONCRETE", []))

    # Parse section geometry
    shape = _parse_section_geometry(sections.get("SECTION", []))

    # Build cross-section
    n_layers = 100
    analysis_params = _parse_analysis(sections.get("ANALYSIS", []))
    if "n_layers" in analysis_params:
        n_layers = analysis_params["n_layers"]

    xs = CrossSection.from_shape(shape, concrete, n_layers=n_layers)

    # Parse and add rebar
    steel = _parse_steel(sections.get("LONG STEEL", []))
    for bar_data in _parse_rebars(sections.get("REBAR", []), steel):
        xs.add_rebar(bar_data)

    # Parse and add tendons
    for tendon_data in _parse_tendons(sections.get("TENDON", []), sections):
        xs.add_tendon(tendon_data)

    # Parse and apply transverse steel (stirrups)
    trans = _parse_trans_steel(sections.get("TRANS STEEL", []), steel)
    if trans is not None:
        xs.set_stirrups(
            Av=trans["Av"],
            s=trans["s"],
            material=trans["material"],
            y_bot=trans.get("y_bot"),
            y_top=trans.get("y_top"),
        )

    # Parse loading
    loading = _parse_loading(sections.get("LOADING", []))

    return {
        "section": xs,
        "analysis_type": analysis_params.get("type", "moment_curvature"),
        "analysis_params": analysis_params,
        "loading": loading,
        "units": units,
        "metadata": {"source_file": str(filepath)},
    }


def _parse_concrete(lines: list) -> Concrete:
    """Parse [CONCRETE] section."""
    props: Dict[str, float] = {}
    for line in lines:
        parts = re.split(r"[=,\s]+", line, maxsplit=1)
        if len(parts) == 2:
            key = parts[0].strip().lower()
            try:
                val = float(parts[1].strip())
            except ValueError:
                continue
            props[key] = val

    fc = props.get("fc", props.get("f'c", props.get("fpc", 30.0)))
    return Concrete(
        fc=fc,
        ec=props.get("ec"),
        Ec=props.get("ec_mod", props.get("e_c")),
        ft=props.get("ft"),
        ecu=props.get("ecu", 0.0035),
        aggregate_size=props.get("agg", props.get("aggregate", 19.0)),
    )


def _parse_section_geometry(lines: list):
    """Parse [SECTION] and return a shape object."""
    props: Dict[str, float] = {}
    shape_type = "rectangular"

    for line in lines:
        low = line.lower()
        if "circular" in low or "circle" in low:
            shape_type = "circular"
        elif "tee" in low or "t-section" in low:
            shape_type = "tee"

        parts = re.split(r"[=,\s]+", line, maxsplit=1)
        if len(parts) == 2:
            key = parts[0].strip().lower()
            try:
                val = float(parts[1].strip())
            except ValueError:
                continue
            props[key] = val

    if shape_type == "circular":
        return CircularSection(diameter=props.get("d", props.get("diameter", 500)))
    elif shape_type == "tee":
        return TeeSection(
            bw=props.get("bw", 300),
            hw=props.get("hw", 400),
            bf=props.get("bf", 600),
            hf=props.get("hf", 100),
        )
    else:
        return RectangularSection(
            b=props.get("b", props.get("width", 300)),
            h=props.get("h", props.get("height", props.get("d", 500))),
        )


def _parse_steel(lines: list) -> ReinforcingSteel:
    """Parse [LONG STEEL] section."""
    props: Dict[str, float] = {}
    for line in lines:
        parts = re.split(r"[=,\s]+", line, maxsplit=1)
        if len(parts) == 2:
            key = parts[0].strip().lower()
            try:
                val = float(parts[1].strip())
            except ValueError:
                continue
            props[key] = val

    return ReinforcingSteel(
        fy=props.get("fy", 400.0),
        Es=props.get("es", props.get("e_s", 200_000.0)),
        fu=props.get("fu"),
        esh=props.get("esh"),
        esu=props.get("esu", 0.05),
    )


def _parse_rebars(lines: list, default_steel: ReinforcingSteel) -> list:
    """Parse [REBAR] section.

    Expected format per line:  y_mm  area_mm2  [fy]
    or:  y_mm  n_bars  diameter_mm
    """
    bars = []
    for line in lines:
        parts = line.split()
        if len(parts) < 2:
            continue
        try:
            vals = [float(p) for p in parts]
        except ValueError:
            continue

        if len(vals) == 2:
            bars.append(RebarBar(y=vals[0], area=vals[1], material=default_steel))
        elif len(vals) >= 3:
            # Could be (y, area, fy) or (y, n_bars, diameter)
            # Heuristic: if third value > 100, it's fy; else it's diameter
            if vals[2] > 100:
                mat = ReinforcingSteel(fy=vals[2], Es=default_steel.Es,
                                       fu=default_steel.fu, esu=default_steel.esu)
                bars.append(RebarBar(y=vals[0], area=vals[1], material=mat))
            else:
                import math
                n_bars = int(vals[1])
                dia = vals[2]
                area = n_bars * math.pi / 4 * dia ** 2
                bars.append(RebarBar(y=vals[0], area=area, material=default_steel))

    return bars


def _parse_tendons(lines: list, all_sections: dict) -> list:
    """Parse [TENDON] section."""
    tendons = []
    ps_lines = all_sections.get("PRESTRESSING STEEL", [])
    ps_mat = _parse_prestressing_steel(ps_lines)

    for line in lines:
        parts = line.split()
        if len(parts) < 2:
            continue
        try:
            vals = [float(p) for p in parts]
        except ValueError:
            continue

        y = vals[0]
        area = vals[1]
        prestrain = vals[2] if len(vals) > 2 else 0.005
        tendons.append(Tendon(y=y, area=area, material=ps_mat, prestrain=prestrain))

    return tendons


def _parse_prestressing_steel(lines: list) -> PrestressingSteel:
    props: Dict[str, float] = {}
    for line in lines:
        parts = re.split(r"[=,\s]+", line, maxsplit=1)
        if len(parts) == 2:
            key = parts[0].strip().lower()
            try:
                val = float(parts[1].strip())
            except ValueError:
                continue
            props[key] = val

    return PrestressingSteel(
        fpu=props.get("fpu", 1860.0),
        Ep=props.get("ep", 196_500.0),
        fpy=props.get("fpy"),
        epu=props.get("epu", 0.04),
    )


def _parse_trans_steel(
    lines: list, default_steel: ReinforcingSteel
) -> Optional[Dict[str, Any]]:
    """Parse [TRANS STEEL] section.

    Expected format (key=value or whitespace-delimited)::

        fy = 400
        Es = 200000
        Av = 157
        s = 200
        y_bot = 50    (optional)
        y_top = 450   (optional)

    Returns None if the section is empty or missing Av/s.
    """
    if not lines:
        return None

    props: Dict[str, float] = {}
    for line in lines:
        parts = re.split(r"[=,\s]+", line, maxsplit=1)
        if len(parts) == 2:
            key = parts[0].strip().lower()
            try:
                val = float(parts[1].strip())
            except ValueError:
                continue
            props[key] = val

    if "av" not in props or "s" not in props:
        warnings.warn(
            "[TRANS STEEL] section found but missing Av or s; ignoring."
        )
        return None

    stirrup_mat = ReinforcingSteel(
        fy=props.get("fy", default_steel.fy),
        Es=props.get("es", default_steel.Es),
    )
    return {
        "material": stirrup_mat,
        "Av": props["av"],
        "s": props["s"],
        "y_bot": props.get("y_bot"),
        "y_top": props.get("y_top"),
    }


def _parse_loading(lines: list) -> Dict[str, float]:
    props: Dict[str, float] = {}
    for line in lines:
        parts = re.split(r"[=,\s]+", line, maxsplit=1)
        if len(parts) == 2:
            key = parts[0].strip().lower()
            try:
                val = float(parts[1].strip())
            except ValueError:
                continue
            props[key] = val
    return {
        "N": props.get("n", props.get("axial", 0.0)),
        "M": props.get("m", props.get("moment", 0.0)),
        "V": props.get("v", props.get("shear", 0.0)),
    }


def _parse_analysis(lines: list) -> Dict[str, Any]:
    params: Dict[str, Any] = {}
    for line in lines:
        low = line.lower()
        if "moment" in low and "curvature" in low:
            params["type"] = "moment_curvature"
        elif "shear" in low:
            params["type"] = "shear"
        elif "member" in low:
            params["type"] = "member_response"
        elif "pushover" in low:
            params["type"] = "pushover"
        elif "interaction" in low:
            params["type"] = "moment_shear_interaction"

        parts = re.split(r"[=,\s]+", line, maxsplit=1)
        if len(parts) == 2:
            key = parts[0].strip().lower()
            try:
                val = float(parts[1].strip())
                if val == int(val):
                    val = int(val)
            except ValueError:
                val = parts[1].strip()
            params[key] = val

    params.setdefault("type", "moment_curvature")
    return params
