# response-yolo User Guide

**Python clone of Response-2000 (R2K) for reinforced concrete sectional analysis**

*Based on the Modified Compression Field Theory (MCFT) by Vecchio & Collins (1986).*
*Original Response-2000 by Evan Bentz, University of Toronto, 2000.*

---

## Table of Contents

1. [Overview](#overview)
2. [Installation](#installation)
3. [Quick Start](#quick-start)
4. [Command-Line Interface](#command-line-interface)
5. [Input Formats](#input-formats)
6. [Output Format](#output-format)
7. [Material Models](#material-models)
8. [Section Types](#section-types)
9. [Analysis Types](#analysis-types)
10. [Python API](#python-api)
11. [Theory](#theory)
12. [Examples](#examples)
13. [Limitations and Future Work](#limitations-and-future-work)

---

## Overview

`response-yolo` is a Python implementation of the Response-2000 reinforced concrete
analysis program.  It is built around a **command-line kernel** allowing for automated
workflows (parametric studies, optimisation loops, etc.).

Currently implemented:
**- Define**
  **- Materials**
    - Rebar Details:
      - Elasto-plastic with strain hardening model
      - Predefined types: CSA G30.12 400 MPa, CSA G30.16 400 MPa Weldable, 1080 MPa Dywidag Bars
    - Concrete Details:
      - Base curve: Linear, Parabolic, Popovics/Thorenfeldt/Collins, Elasto-plastic 
      - Compression softening: Collins-Bentz 2011, none
      - Tension stiffening: Bentz 1999, none
    - Prestressing Steel Details:
      - Ramberg-Osgood model
      - Predefined types: 1860 MPa Low Relaxation, 1860 MPa Stress Relieved
  **- Concrete Cross Section**
    - Basic shapes: Rectangle, Circular, T-beam, I-Beam
  **- Transverse Reinforcement**
    - Stirrup spacing
    - Bar type: Single Leg, Open Stirrup, Closed Stirrup, Hoop
    - Select by bar area or designation
  **- Longitudinal Reinforcement**
    - Individual Layers: number of bars, distance from bottom
    - Circular Patterns: number of bars, height of centre, diameter on centres, alinged/offset
    - Select by bar area or designation
  **- Tendons**
    - Tendon Layers: number of strands, distance from bottom, prestrain, slope of tendon
    - Select by strand area or designation
  

- - **Sectional response** for reinforced and prestressed concrete sections


- R2T text file input (compatible with Response-2000 format)
- JSON input/output for automation

## Installation

```bash
# From the repository root
pip install -e .

# Or with development dependencies
pip install -e ".[dev]"
```

Requirements: Python >= 3.10. No external dependencies (pure Python + stdlib).

## Quick Start

```bash
# Run a moment-curvature analysis
response-yolo run examples/simple_beam.json

# View section properties
response-yolo info examples/simple_beam.json

# Specify output file
response-yolo run examples/simple_beam.json -o my_results.json

# Use R2T format
response-yolo run examples/simple_beam.r2t

# Quiet mode (JSON only to stdout-compat file, no banner)
response-yolo run examples/simple_beam.json -q
```

## Command-Line Interface

### `response-yolo run <input_file>`

Run an analysis and write results.

| Flag | Description |
|------|-------------|
| `-o`, `--output` | Output file path (default: `<input>_results.json`) |
| `--format` | Output format: `json` (default) or `csv` |
| `-q`, `--quiet` | Suppress banner and progress output |

### `response-yolo info <input_file>`

Display section properties without running an analysis.

### `response-yolo --version`

Print version string.

## Input Formats

### JSON Input

The JSON input is the recommended format for automation:

```json
{
  "units": "SI",
  "section": {
    "shape": "rectangular",
    "b": 300,
    "h": 500
  },
  "concrete": {
    "fc": 35,
    "ecu": 0.0035,
    "compression_model": "popovics",
    "tension_model": "mcft",
    "aggregate_size": 19
  },
  "long_steel": {
    "fy": 400,
    "Es": 200000,
    "fu": 600,
    "esh": 0.01,
    "esu": 0.05,
    "model": "trilinear"
  },
  "rebars": [
    {"y": 50, "area": 1500},
    {"y": 450, "area": 500}
  ],
  "tendons": [
    {
      "y": 150,
      "area": 1000,
      "fpu": 1860,
      "Ep": 196500,
      "prestrain": 0.006
    }
  ],
  "loading": {
    "N": 0
  },
  "analysis": {
    "type": "moment_curvature",
    "n_steps": 300,
    "n_layers": 100
  }
}
```

#### Section Shapes

| Shape | Required Fields |
|-------|----------------|
| `rectangular` | `b` (width), `h` (height) |
| `tee` | `bw` (web width), `hw` (web height), `bf` (flange width), `hf` (flange thickness) |
| `circular` | `diameter` or `d` |

#### Concrete Properties

| Field | Description | Default |
|-------|-------------|---------|
| `fc` | Compressive strength (MPa) | **required** |
| `Ec` | Elastic modulus (MPa) | `3320*sqrt(fc) + 6900` |
| `ft` | Tensile strength (MPa) | `0.33*sqrt(fc)` |
| `ec` | Strain at peak stress | `2*fc/Ec` |
| `ecu` | Ultimate compressive strain | `0.0035` |
| `compression_model` | `popovics`, `hognestad`, `collins_mitchell` | `popovics` |
| `tension_model` | `mcft`, `linear_cutoff`, `no_tension` | `mcft` |
| `aggregate_size` | Max aggregate size (mm) | `19` |

#### Steel Properties

| Field | Description | Default |
|-------|-------------|---------|
| `fy` | Yield stress (MPa) | **required** |
| `Es` | Elastic modulus (MPa) | `200000` |
| `fu` | Ultimate stress (MPa) | `= fy` |
| `esh` | Strain-hardening onset | `5 * ey` |
| `esu` | Ultimate strain | `0.05` |
| `model` | `trilinear` or `bilinear` | `trilinear` |

#### Rebar Specification

Each rebar entry needs:
- `y`: elevation from section bottom (mm)
- `area`: total steel area (mm^2) at that elevation

Or alternatively:
- `y`, `n_bars`, `diameter`: auto-computes area as `n_bars * pi/4 * d^2`

#### Tendon Specification

| Field | Description | Default |
|-------|-------------|---------|
| `y` | Elevation from bottom (mm) | **required** |
| `area` | Strand area (mm^2) | **required** |
| `fpu` | Ultimate stress (MPa) | `1860` |
| `Ep` | Elastic modulus (MPa) | `196500` |
| `fpy` | Yield stress (MPa) | `0.9*fpu` |
| `epu` | Ultimate strain | `0.04` |
| `prestrain` | Initial prestrain | `0.005` |

#### Loading

| Field | Description |
|-------|-------------|
| `N` | Applied axial load (N). Positive = tension, negative = compression. |

#### Analysis Parameters

| Field | Description | Default |
|-------|-------------|---------|
| `type` | Analysis type (currently only `moment_curvature`) | `moment_curvature` |
| `n_steps` | Number of curvature increments | `200` |
| `n_layers` | Number of concrete layers for discretisation | `100` |
| `max_curvature` | Maximum curvature (1/mm) | auto |
| `tol_force` | Force equilibrium tolerance (N) | `1.0` |
| `max_iter` | Max Newton-Raphson iterations | `50` |

### R2T Input

R2T is a text-based format compatible with the original Response-2000.
Lines starting with `#` or `;` are comments. Sections are delimited by
`[SECTION_NAME]` headers.

```
# Example R2T input
[UNITS]
SI

[CONCRETE]
fc = 35
ecu = 0.0035

[SECTION]
b = 300
h = 500

[LONG STEEL]
fy = 400
Es = 200000
fu = 600

[REBAR]
# y_mm  area_mm2
50    1500
450   500

[LOADING]
N = 0

[ANALYSIS]
moment_curvature
n_steps = 300
```

Supported R2T sections: `[UNITS]`, `[CONCRETE]`, `[SECTION]`, `[LONG STEEL]`,
`[TRANS STEEL]`, `[REBAR]`, `[TENDON]`, `[PRESTRESSING STEEL]`, `[LOADING]`,
`[ANALYSIS]`.

## Output Format

(see output specification)

## Material Models

### Concrete Compression

**Popovics / Thorenfeldt / Collins** (default):
```
f = fc * (eps/ec) * n / (n - 1 + (eps/ec)^(n*k))
```
where `n = 0.8 + fc/17` and `k = 1.0` pre-peak, `k = 0.67 + fc/62` post-peak
(for fc > 67 MPa).

**Hognestad** parabola:
```
Pre-peak:   f = fc * [2*(eps/ec) - (eps/ec)^2]
Post-peak:  linear descent to 0.85*fc at ecu
```

**Collins & Mitchell**: Same as Popovics with k = 1.0 (no post-peak decay).

### Concrete Tension

**MCFT tension stiffening** (default):
```
f_t = f_cr / (1 + sqrt(500 * eps))
```
Per Vecchio & Collins (1986).

**Linear cutoff**: Stress drops to zero immediately after cracking.

**No tension**: Concrete carries zero tensile stress.

### Reinforcing Steel

**Trilinear** (default):
1. Elastic: `f = Es * eps` for `eps <= ey`
2. Yield plateau: `f = fy` for `ey < eps <= esh`
3. Strain hardening: parabolic curve from `fy` to `fu` between `esh` and `esu`

**Bilinear**: Linear elastic to yield, then linear hardening to `(esu, fu)`.

Both models are symmetric in tension and compression. Steel is assumed
fractured (stress = 0) beyond `esu`.

### Prestressing Steel

**Power formula** (default, Ramberg-Osgood):
```
eps = f/Ep + k * (f/fpu)^N
```
Solved iteratively for f given eps. Parameters `k` and `N` are fitted
to pass through the 0.1% offset yield point.

**Bilinear**: Simple elastic-plastic with hardening.

Prestressing steel is tension-only (returns zero for compressive strain).

## Section Types

### Rectangular
Standard rectangular cross-section. Defined by width `b` and height `h`.

### Tee Section
T-shaped section (or inverted-T). Defined by web width `bw`, web height `hw`,
flange width `bf`, and flange thickness `hf`. The flange sits on top of the web.

### Circular
Circular cross-section defined by `diameter`. Width varies as
`w(y) = 2 * sqrt(r^2 - (y-r)^2)`.

### Generic
User-defined section via a width-vs-depth profile (list of `(y, width)` points).
Linear interpolation between control points.

## Analysis Types

### Moment-Curvature (implemented)

Performs a layered fibre analysis with plane-sections-remain-plane assumption.
For each curvature increment:
1. Iterates the centroidal strain (Newton-Raphson) to satisfy axial equilibrium
2. Integrates stresses to obtain the moment
3. Detects cracking, yielding, and failure

Outputs the complete M-phi response curve with key points identified.

### Shear Analysis (stub)

Will implement MCFT-based V-gamma sectional analysis.

### Moment-Shear Interaction (stub)

Will produce M-V failure envelopes.

### Full Member Response (stub)

Will model complete beam/column with distributed plasticity.

### Pushover Analysis (stub)

Will perform incremental lateral load analysis with P-delta effects.

## Python API

```python
from response_yolo.materials import Concrete, ReinforcingSteel
from response_yolo.section import RectangularSection, CrossSection, RebarBar
from response_yolo.analysis import MomentCurvatureAnalysis

# Define materials
concrete = Concrete(fc=35)
steel = ReinforcingSteel(fy=400, fu=600, esh=0.01, esu=0.05)

# Build section
shape = RectangularSection(b=300, h=500)
section = CrossSection.from_shape(shape, concrete, n_layers=100)
section.add_rebar(RebarBar(y=50, area=1500, material=steel))
section.add_rebar(RebarBar(y=450, area=400, material=steel))

# Section properties
print(f"Area: {section.gross_area} mm^2")
print(f"Centroid: {section.centroid_y} mm")
print(f"Ig: {section.gross_moment_of_inertia:.3e} mm^4")

# Run analysis
analysis = MomentCurvatureAnalysis(
    section,
    axial_load=0,       # N (positive = tension)
    n_steps=200,
)
result = analysis.run()

# Access results
print(f"Mcr = {result.cracking_moment/1e6:.1f} kN-m")
print(f"My  = {result.yield_moment/1e6:.1f} kN-m")
print(f"Mu  = {result.ultimate_moment/1e6:.1f} kN-m")
print(f"Failure: {result.failure_reason}")

# Iterate over response points
for point in result.points:
    phi = point.curvature       # 1/mm
    M = point.moment_kNm        # kN-m
    na = point.neutral_axis_y   # mm from bottom

# Export to dict (for JSON serialisation)
output = result.to_dict()
```

### Working with Prestressed Sections

```python
from response_yolo.materials import PrestressingSteel
from response_yolo.section import Tendon

ps = PrestressingSteel(fpu=1860, Ep=196500)
section.add_tendon(Tendon(y=100, area=1000, material=ps, prestrain=0.006))
```

### Working with I/O

```python
from response_yolo.io import parse_r2t, load_json_input, save_json_output

# Load from R2T
config = parse_r2t("beam.r2t")
section = config["section"]

# Load from JSON
config = load_json_input("beam.json")

# Save results
save_json_output(result.to_dict(), "results.json")
```

## Theory

### Modified Compression Field Theory (MCFT)

The MCFT (Vecchio & Collins, 1986) treats cracked reinforced concrete as a
new material with its own stress-strain characteristics. Key principles:

1. **Compatibility**: Strains in concrete and reinforcement are related
   through equilibrium and geometric conditions at cracks.

2. **Equilibrium**: Average stresses in concrete and reinforcement must
   satisfy equilibrium with applied loads.

3. **Constitutive relationships**: Average stress-strain relationships
   account for the effects of cracking:
   - Compression softening (concrete is weaker when cracked in the
     transverse direction)
   - Tension stiffening (concrete between cracks carries tensile stress)

### Moment-Curvature Analysis

The analysis uses the plane-sections-remain-plane assumption (Bernoulli
hypothesis). The cross-section is discretised into horizontal layers (fibres).

For a given curvature phi, the strain at any elevation y is:
```
eps(y) = eps_0 - phi * (y - y_ref)
```

where:
- `eps_0` = strain at the reference axis (iterated for equilibrium)
- `phi` = curvature (positive = sagging)
- `y_ref` = reference axis elevation (typically centroid)

The Newton-Raphson method is used to find `eps_0` such that the resultant
axial force equals the applied axial load:
```
N_applied = integral[ sigma(eps(y)) * b(y) dy ] + sum[ sigma_s * As ]
```

The moment is then:
```
M = -integral[ sigma(eps(y)) * b(y) * (y - y_ref) dy ] - sum[ sigma_s * As * (y_s - y_ref) ]
```

### Sign Convention

- **Y-axis**: measured from section bottom (y = 0 at bottom)
- **Curvature**: positive = sagging (concave up, compression at top)
- **Moment**: positive = sagging (tension at bottom)
- **Axial load**: positive = tension
- **Strain**: positive = tension, negative = compression
- **Stress**: positive = tension, negative = compression

### References

1. Vecchio, F.J. and Collins, M.P. (1986). "The Modified Compression-Field
   Theory for Reinforced Concrete Elements Subjected to Shear." *ACI Journal*,
   83(2), 219-231.

2. Collins, M.P. and Mitchell, D. (1991). *Prestressed Concrete Structures*.
   Prentice-Hall.

3. Bentz, E.C. (2000). "Sectional Analysis of Reinforced Concrete Members."
   PhD Thesis, University of Toronto.

4. Thorenfeldt, E., Tomaszewicz, A., and Jensen, J.J. (1987). "Mechanical
   Properties of High-Strength Concrete and Application in Design."
   *Proc. Symposium on Utilization of High-Strength Concrete*, Stavanger.

## Examples

Three example input files are provided in the `examples/` directory:

| File | Description |
|------|-------------|
| `simple_beam.json` | 300x500 mm rectangular beam, fc'=35, 3-25M bottom |
| `simple_beam.r2t` | Same beam in R2T format |
| `prestressed_beam.json` | 400x800 mm prestressed beam with bonded tendons |
| `column_with_axial.json` | 400x400 mm column under 1500 kN compression |

## Limitations and Future Work

### Current Limitations

- Only moment-curvature analysis is implemented; shear, member response,
  and pushover analyses are stubbed
- Monotonic loading only (no cyclic or reversed loading)
- No graphical interface (by design: this is a CLI kernel)
- Concrete compression softening due to transverse cracking is not yet
  applied (relevant for shear analysis, not pure flexure)
- No confinement models (Mander, etc.)
- US customary units require manual conversion (input always in MPa/mm)

### Planned Features

- MCFT-based sectional shear analysis (V-gamma)
- Moment-shear interaction (M-V) failure envelopes
- Full member response with integration of sectional responses
- Confinement models for columns
- Menegotto-Pinto cyclic steel model
- Crack spacing and crack width calculations
- Compression softening factor (beta_d)
- Support for US customary units in input files

---

*response-yolo: You Only Layer Once.*
