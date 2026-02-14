# Response-YOLO User Guide

**Command-line reinforced concrete sectional analysis inspired by
[Response-2000](http://www.ecf.utoronto.ca/~bentz/r2k.htm) (Bentz & Collins,
University of Toronto).**

Response-YOLO is a pure-Python tool designed for automated structural design
workflows.  It reads JSON, writes JSON, and runs entirely from the command
line — no GUI.

---

## Table of Contents

1. [Installation](#installation)
2. [Quick Start](#quick-start)
3. [Input File Reference](#input-file-reference)
4. [CLI Reference](#cli-reference)
5. [Output Format](#output-format)
6. [Material Models](#material-models)
7. [Analysis Method](#analysis-method)
8. [Roadmap / Stubs](#roadmap)
9. [Differences from Response-2000](#differences-from-response-2000)

---

## Installation

Response-YOLO requires **Python 3.10+** and has **no runtime dependencies**
outside the standard library.

```bash
# Clone and install in development mode
git clone <repo-url> response-yolo
cd response-yolo
pip install -e .

# Verify
response-yolo --version
```

To run the test suite (requires `pytest`):

```bash
pip install -e ".[dev]"
python -m pytest tests/ -v

# Or with unittest (no extra dependencies)
python -m unittest discover -s tests -v
```

---

## Quick Start

1. Create an input file (or use one of the examples in `examples/`):

```json
{
  "concrete": { "fc": 35 },
  "steel":    { "fy": 400 },
  "section":  { "type": "rectangle", "width": 300, "height": 500 },
  "rebar": [
    { "label": "top",    "area": 400,  "depth": 50  },
    { "label": "bottom", "area": 1500, "depth": 450 }
  ]
}
```

2. Run the analysis:

```bash
# Print results to stdout
response-yolo moment-curvature input.json

# Write results to a file
response-yolo moment-curvature input.json -o results.json

# Short alias
response-yolo mk input.json -o results.json
```

3. The output is a JSON object containing the full moment-curvature curve.

---

## Input File Reference

The input is a single JSON object with the following top-level keys:

### `concrete` (required)

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `fc` | float | *(required)* | Compressive strength, f'c (MPa, positive) |
| `ec0` | float | auto | Strain at peak stress (negative). Default: `-fc / (5000 * sqrt(fc))` |
| `ft` | float | auto | Tensile strength (MPa). Default: `0.33 * sqrt(fc)` |
| `Ec` | float | auto | Initial tangent modulus (MPa). Default: `4500 * sqrt(fc)` |
| `tension_stiffening` | bool | `true` | Use Collins & Mitchell post-cracking model |

### `steel` (optional)

Can be either a **single object** (applied to all rebar) or a **dict of
named steel types** that rebar groups reference by label.

**Single steel:**

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `fy` | float | *(required)* | Yield strength (MPa) |
| `Es` | float | `200000` | Elastic modulus (MPa) |
| `fu` | float | `null` | Ultimate strength (MPa). Enables strain hardening |
| `esh` | float | `0.01` | Strain at onset of hardening |
| `esu` | float | `0.10` | Ultimate strain |

If omitted entirely, a default of `fy = 400 MPa` is assumed.

**Multiple steels:**

```json
"steel": {
  "mild":  { "fy": 300 },
  "high":  { "fy": 500, "fu": 650 }
}
```

Each rebar group then references a steel by its key name (see below).

### `section` (required)

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `type` | string | `"rectangle"` | Section shape. Only `"rectangle"` is currently supported |
| `width` | float | *(required)* | Section width (mm) |
| `height` | float | *(required)* | Section height (mm) |

Depths are measured from the **top** of the section (y = 0 at top, increasing
downward).

### `rebar` (optional)

A list of reinforcing bar groups:

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `area` | float | *(required)* | Total bar area for this group (mm²) |
| `depth` | float | *(required)* | Depth from section top to bar centroid (mm) |
| `steel` | string | `"default"` | Steel label (references a key in `steel` dict) |
| `label` | string | `""` | Optional identifier for this bar group |

### `analysis` (optional)

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `n_steps` | int | `100` | Number of curvature increments |
| `max_curvature` | float | auto | Maximum curvature to analyse to (1/mm) |
| `n_fibres` | int | `100` | Number of concrete fibres for discretisation |

### Complete example

```json
{
  "concrete": {
    "fc": 40,
    "tension_stiffening": true
  },
  "steel": {
    "fy": 400,
    "Es": 200000,
    "fu": 600,
    "esh": 0.01,
    "esu": 0.10
  },
  "section": {
    "type": "rectangle",
    "width": 300,
    "height": 500
  },
  "rebar": [
    { "label": "top",    "area": 600,  "depth": 50  },
    { "label": "bottom", "area": 1500, "depth": 450 }
  ],
  "analysis": {
    "n_steps": 80,
    "n_fibres": 120
  }
}
```

---

## CLI Reference

```
response-yolo [--version] <command> [options]
```

### `moment-curvature` (alias: `mk`)

Run a moment-curvature analysis for pure bending (N = 0).

```
response-yolo moment-curvature INPUT [-o OUTPUT] [-n N_STEPS]
                                [--max-curvature PHI] [--n-fibres N]
```

| Flag | Description |
|------|-------------|
| `INPUT` | Path to JSON input file |
| `-o`, `--output` | Write results to this file instead of stdout |
| `-n`, `--n-steps` | Number of curvature increments (default 100) |
| `--max-curvature` | Maximum curvature in 1/mm (default: automatic) |
| `--n-fibres` | Concrete fibre count for discretisation (default 100) |

Note: values in the `analysis` block of the input file override CLI defaults,
but explicit CLI flags override both.

### `axial` / `shear` / `full`

These are **stubs** for future analysis types.  They will exit with an error
explaining that they are not yet implemented.

---

## Output Format

All output is JSON.  When using `-o`, results are written to the specified
file; otherwise they are printed to stdout (diagnostic messages go to stderr).

```json
{
  "analysis": "moment_curvature",
  "units": {
    "curvature": "1/mm",
    "moment": "kN·m",
    "strain": "mm/mm"
  },
  "results": {
    "points": [
      {
        "curvature_1_per_mm": 0.0,
        "moment_kNm": 0.0,
        "top_strain": 0.0,
        "bot_strain": 0.0
      },
      {
        "curvature_1_per_mm": 6.0e-07,
        "moment_kNm": 12.34,
        "top_strain": -0.00012,
        "bot_strain": 0.00018
      }
    ],
    "peak_moment_kNm": 185.6
  }
}
```

Each point contains:

| Field | Description |
|-------|-------------|
| `curvature_1_per_mm` | Curvature (1/mm) |
| `moment_kNm` | Moment about the centroidal axis (kN·m) |
| `top_strain` | Strain at the extreme top fibre (compression is negative) |
| `bot_strain` | Strain at the extreme bottom fibre |

---

## Material Models

### Concrete in compression — Popovics / Thorenfeldt / Collins

The stress-strain curve in compression uses the model from Collins & Mitchell
(1991), based on Popovics (1973) with modifications by Thorenfeldt et al.
(1987):

```
σ = -f'c · (n · η) / (n - 1 + η^(nk))
```

where:
- `η = ε / ε_c0` (ratio of strain to peak strain)
- `n = 0.8 + f'c / 17` (curve-shape parameter)
- `k = 1.0` for `ε ≥ ε_c0` (ascending branch)
- `k = 0.67 + f'c / 62` for `ε < ε_c0` (descending branch)

This model captures the brittle descending branch of high-strength concrete
and the more ductile behaviour of normal-strength concrete.

### Concrete in tension — Collins & Mitchell tension stiffening

Before cracking (ε ≤ ε_cr), concrete is linear elastic:

```
σ = E_c · ε
```

After cracking, the tension-stiffening model from Collins & Mitchell (1991)
is used:

```
σ = f_t / (1 + √(200 · ε))
```

This models the average tensile stress carried by concrete between cracks due
to bond with the reinforcement.  It can be disabled by setting
`"tension_stiffening": false` in the input.

### Reinforcing steel — elastic-perfectly-plastic with optional hardening

The default model is elastic-perfectly-plastic (bilinear).  If `fu` is
specified, a linear strain-hardening branch is added between `ε_sh` and
`ε_su`.  The model is symmetric in tension and compression.

---

## Analysis Method

Response-YOLO uses a **fibre-based sectional analysis** under the
plane-sections-remain-plane (Bernoulli) hypothesis:

1. The cross-section is discretised into horizontal concrete fibres and
   discrete steel fibres at the rebar locations.

2. For each target curvature φ (from 0 to φ_max in `n_steps` increments):
   - A trial top-fibre strain ε_top is assumed.
   - The strain at each fibre is computed:
     `ε(y) = ε_top + φ · (y - y_top)`
   - The stress in each fibre is evaluated from its constitutive model.
   - The axial resultant `N = Σ(σ · A)` is computed.
   - ε_top is iterated via bisection until `N ≈ 0` (pure bending).
   - The moment `M = Σ(σ · A · (y - y_ref))` is computed about the
     gross-section centroid.

3. The full M-φ curve is returned as a list of (curvature, moment) points.

This approach is consistent with the sectional analysis described in Bentz
(2000) *"Sectional Analysis of Reinforced Concrete Members"*, simplified to
pure bending without axial force or shear.

---

## Roadmap

The following analysis types are planned but **not yet implemented** (calling
them will produce an error):

| Command | Description | Status |
|---------|-------------|--------|
| `moment-curvature` | M-φ analysis (pure bending) | **Implemented** |
| `axial` | Axial force–deformation (N only) | Stub |
| `shear` | Shear analysis via MCFT | Stub |
| `full` | Combined N + M + V sectional analysis | Stub |

Future enhancements under consideration:
- T-section and arbitrary polygon geometry
- Prestressing strand support
- Confinement models (Mander et al.)
- Member-level (integration along span) analysis
- CSV output option

---

## Differences from Response-2000

| Aspect | Response-2000 | Response-YOLO |
|--------|--------------|---------------|
| Interface | Windows GUI | Command-line + JSON |
| Shear (MCFT) | Full implementation | Stub (not yet) |
| Axial load | Supported | Stub (not yet) |
| Section shapes | Arbitrary polygons | Rectangle only (for now) |
| Prestressing | Supported | Not yet |
| Load stages | Multiple | Single M-φ sweep |
| Platform | Windows | Any (Python 3.10+) |
| Dependencies | None (standalone .exe) | None (pure Python) |
| Automation | Limited (COM interface) | First-class (JSON in/out) |

Response-YOLO is **not** a port of Response-2000.  It is a new implementation
inspired by the same theoretical foundations (Collins, Mitchell, Bentz) and
designed from the ground up for scriptability and integration into automated
design pipelines.
