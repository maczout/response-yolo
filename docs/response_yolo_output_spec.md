# Response-YOLO Output Format Specification

**Version:** 1.0.0  
**Date:** 2024-02-15  
**Status:** Draft

## Overview

This document specifies the JSON output format for Response-YOLO analysis results. This format is designed to:

1. Contain all data needed to recreate R2K-style dashboards and visualizations
2. Be self-documenting and human-readable
3. Support validation against reference solutions (e.g., R2K)
4. Be easily parseable by plotting/post-processing tools

## File Extension and Naming

- Extension: `.json`
- Naming convention: `{section_id}_{analysis_type}_results.json`
- Examples:
  - `rect_moment_curvature_results.json`
  - `tee_axial_moment_results.json`
  - `beam_service_check_results.json`

## Units System

All outputs use consistent units throughout the file:

| Quantity | Unit | Symbol |
|----------|------|--------|
| Length | mm | mm |
| Force | kN | kN |
| Stress | MPa | MPa |
| Moment | kNm | kNm |
| Strain | mm/m | mm/m |
| Curvature | mrad/m | mrad/m |
| Shear strain | mm/m | mm/m |
| Shear force | kN | kN |
| Crack width | mm | mm |
| Temperature | °C | °C |

## Top-Level Structure

```json
{
  "metadata": { },
  "units": { },
  "input_echo": { },
  "results": {
    "control_curves": { },
    "analysis_points": [ ],
    "summary": { }
  }
}
```

---

## Metadata Section

**Field:** `metadata`  
**Type:** Object  
**Required:** Yes

Contains file provenance and version information.

```json
{
  "metadata": {
    "version": "1.0.0",
    "timestamp": "2024-02-15T16:33:00Z",
    "generator": "response-yolo v0.1.0",
    "analysis_type": "moment_curvature",
    "input_source": {
      "format": "response_yolo_json",
      "file": "rect_input.json",
      "checksum": "a3f5e8b2..."
    },
    "computation_time": 2.347
  }
}
```

### Metadata Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `version` | String | Yes | Output format version (semantic versioning) |
| `timestamp` | String | Yes | Analysis completion time (ISO 8601 format) |
| `generator` | String | Yes | Software name and version |
| `analysis_type` | String | Yes | Type of analysis performed |
| `input_source` | Object | Yes | Information about input file |
| `computation_time` | Number | No | Total analysis time (seconds) |

**Analysis types:**
- `"moment_curvature"`: M-φ and M-εx curves at constant axial force
- `"shear"`: V-γ shear response curve (MCFT-based sectional shear)
- `"axial_moment"`: P-M interaction diagram
- `"service_check"`: Service limit state verification

**Input source formats:**
- `"response_yolo_json"`: Native JSON input
- `"r2t"`: Response-2000 R2T text input file

---

## Units Section

**Field:** `units`  
**Type:** Object  
**Required:** Yes

Explicit declaration of units for all quantities in the file.

```json
{
  "units": {
    "length": "mm",
    "force": "kN",
    "stress": "MPa",
    "moment": "kNm",
    "strain": "mm/m",
    "curvature": "mrad/m",
    "shear_strain": "mm/m",
    "crack_width": "mm",
    "temperature": "degC"
  }
}
```

---

## Input Echo Section

**Field:** `input_echo`  
**Type:** Object  
**Required:** Yes

Normalized representation of the input data, independent of source format. This allows the output file to be self-contained and traceable. Structure matches the Response-YOLO input format specification with addition of `computed_properties` for derived values.

```json
{
  "input_echo": {
    "section": {
      "id": "rect_validation",
      "description": "Simple rectangular section",
      "geometry": {
        "type": "rectangular",
        "width": 250.0,
        "depth": 600.0,
        "computed_properties": {
          "area": 150000.0,
          "inertia": 4500000.0,
          "centroid_y": 300.0
        }
      }
    },
    
    "materials": {
      "concrete": [
        {
          "id": "concrete_1",
          "model": "hognestad_parabola",
          "fc_prime": 35.0,
          "max_aggregate_size": 19.0,
          "computed_properties": {
            "ec": 31000.0,
            "epsilon_c": 0.00203,
            "ft": 1.89,
            "beta1": 0.85
          }
        }
      ],
      "steel": [
        {
          "id": "steel_main",
          "model": "elastic_perfectly_plastic",
          "fy": 400.0,
          "es": 200000.0,
          "epsilon_sh": 0.007,
          "epsilon_u": 0.100,
          "computed_properties": {
            "epsilon_y": 0.002
          }
        }
      ]
    },
    
    "reinforcement": {
      "longitudinal": [
        {
          "id": "bottom_bars",
          "material_id": "steel_main",
          "y_coordinate": -248.7,
          "bar_count": 3,
          "bar_size": "25M",
          "area_total": 1500.0,
          "diameter": 25.2
        }
      ],
      "transverse": [
        {
          "id": "stirrups",
          "material_id": "steel_trans",
          "bar_size": "10M",
          "area_per_leg": 100.0,
          "spacing": 250.0
        }
      ]
    },
    
    "loading": {
      "type": "moment_curvature",
      "axial_force": 0.0,
      "shear_force": 0.0,
      "sustained_moment": 0.0,
      "environmental": {
        "shrinkage_strain": 0.0,
        "thermal_gradient": 0.0
      }
    },
    
    "analysis_options": {
      "solver": {
        "tolerance": 1.0e-6,
        "max_iterations": 100,
        "convergence_criterion": "force_moment"
      },
      "output": {
        "detail_level": "full",
        "save_all_points": true,
        "profile_resolution": "adaptive"
      },
      "options": {
        "include_tension_stiffening": true,
        "include_shear_deformation": false,
        "crack_spacing_method": "bentz_2005"
      }
    }
  }
}
```

---

## Results Section

**Field:** `results`  
**Type:** Object  
**Required:** Yes

Contains all analysis results.

### Results Structure

```json
{
  "results": {
    "control_curves": { },
    "analysis_points": [ ],
    "summary": { }
  }
}
```

---

## Control Curves

**Field:** `results.control_curves`  
**Type:** Object  
**Required:** Yes

High-level response curves for plotting. These are the primary output for understanding section behavior.

```json
{
  "control_curves": {
    "moment_curvature": {
      "description": "Moment vs Curvature",
      "x_axis": "curvature",
      "y_axis": "moment",
      "data": [
        {"curvature": 0.0, "moment": 0.0},
        {"curvature": 0.056, "moment": 5.132},
        {"curvature": 0.122, "moment": 11.289}
      ]
    },
    
    "moment_axial_strain": {
      "description": "Moment vs Reference Axial Strain",
      "x_axis": "axial_strain",
      "y_axis": "moment",
      "data": [
        {"axial_strain": 0.0, "moment": 0.0},
        {"axial_strain": -0.001, "moment": 5.132},
        {"axial_strain": -0.002, "moment": 11.289}
      ]
    }
  }
}
```

**Available curves depend on analysis type:**

For `moment_curvature`:
- `moment_curvature`: M vs φ
- `moment_axial_strain`: M vs ε_ref (centroidal axial strain)

For `shear`:
- `shear_strain_response`: V vs γ (average shear strain)

```json
{
  "control_curves": {
    "shear_strain_response": {
      "description": "Shear Force vs Average Shear Strain",
      "x_axis": "shear_strain",
      "y_axis": "shear_force",
      "data": [
        {"shear_strain": 0.0, "shear_force": 0.0},
        {"shear_strain": 0.2, "shear_force": 85.3},
        {"shear_strain": 0.5, "shear_force": 195.7},
        {"shear_strain": 1.0, "shear_force": 278.2}
      ]
    }
  }
}
```

For `axial_moment`:
- `axial_moment`: P vs M (interaction diagram)

For `service_check`:
- May have multiple curves for different load cases

---

## Analysis Points

**Field:** `results.analysis_points`  
**Type:** Array  
**Required:** Yes

Complete section state at each computed point along the response curve. Each point contains all information needed to recreate detailed visualizations (strain profiles, stress diagrams, crack patterns, etc.).

```json
{
  "analysis_points": [
    {
      "index": 0,
      "converged": true,
      "iterations": 5,
      
      "controls": {
        "moment": 0.0,
        "curvature": 0.0,
        "axial_strain_ref": 0.0,
        "axial_force": 0.0
      },
      
      "section_state": {
        "neutral_axis_depth": 600.0,
        "compression_zone_depth": 0.0,
        "cracked": false,
        "yielded": false,
        
        "resultants": {
          "concrete_compression": {
            "force": 0.0,
            "y_location": 0.0
          },
          "steel_tension": {
            "force": 0.0,
            "y_location": 0.0
          },
          "steel_compression": {
            "force": 0.0,
            "y_location": 0.0
          }
        }
      },
      
      "distributions": {
        "longitudinal_strain": {
          "description": "Total mechanical strain in longitudinal direction",
          "reference": "y-coordinate from centroid",
          "data": [
            {"y": 300.0, "strain": 0.0},
            {"y": 287.175, "strain": -0.00024}
          ]
        },
        
        "shrinkage_thermal_strain": {
          "description": "Non-mechanical strains",
          "data": [
            {"y": 300.0, "epsilon_sh": 0.0, "epsilon_thermal": 0.0},
            {"y": -300.0, "epsilon_sh": 0.0, "epsilon_thermal": 0.0}
          ]
        },
        
        "concrete_stress": {
          "description": "Longitudinal stress in concrete",
          "data": [
            {"y": 300.0, "stress": -20.885},
            {"y": 287.175, "stress": -22.343}
          ]
        },
        
        "crack_spacing": {
          "description": "Crack spacing from MCFT elements",
          "method": "bentz_2005",
          "data": [
            {"y": 0.0, "spacing": 140.0, "width": 0.14, "element_id": "elem_10"},
            {"y": -50.0, "spacing": 154.0, "width": 1.54, "element_id": "elem_5"}
          ]
        }
      },
      
      "steel_state": [
        {
          "id": "bottom_bars",
          "material_id": "steel_main",
          "y": -248.7,
          "strain": 0.0017,
          "stress": 340.0,
          "stress_at_crack": 340.0,
          "yielded": true,
          "force": 510.0
        }
      ],
      
      "element_data": {
        "description": "MCFT element states (if shear analysis enabled)",
        "method": "mcft",
        "elements": [
          {
            "id": "elem_1",
            "y_location": 250.0,
            "height": 50.0,
            "epsilon_x": -0.002,
            "epsilon_y": 0.0001,
            "gamma_xy": 0.0,
            "sigma_x": -22.0,
            "sigma_y": 0.1,
            "tau_xy": 0.0,
            "principal_strain_1": -0.002,
            "principal_strain_2": 0.0001,
            "principal_stress_1": -22.0,
            "principal_stress_2": 0.1,
            "crack_angle": 0.0,
            "crack_spacing": 140.0,
            "crack_width": 0.0,
            "cracked": false
          }
        ]
      }
    }
  ]
}
```

### Analysis Point Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `index` | Number | Yes | Sequential point number (0-indexed) |
| `converged` | Boolean | Yes | Did solver converge for this point? |
| `iterations` | Number | No | Number of iterations to converge |
| `controls` | Object | Yes | Control parameters (M, φ, N, etc.) |
| `section_state` | Object | Yes | Overall section state |
| `distributions` | Object | Yes | Strain/stress profiles across section |
| `steel_state` | Array | Yes | State of each reinforcement layer |
| `element_data` | Object | No | MCFT element states (for shear analysis) |

### Controls Object

Current values of analysis control parameters.

```json
{
  "controls": {
    "moment": 250.2,
    "curvature": 53.758,
    "axial_strain_ref": 7.65,
    "axial_force": 0.0
  }
}
```

### Section State Object

Overall section behavior indicators and resultant forces.

```json
{
  "section_state": {
    "neutral_axis_depth": 254.0,
    "compression_zone_depth": 200.0,
    "cracked": true,
    "yielded": true,
    "crushing": false,
    
    "resultants": {
      "concrete_compression": {
        "force": 511.0,
        "y_location": 235.0
      },
      "steel_tension": {
        "force": 511.0,
        "y_location": -248.7
      },
      "steel_compression": {
        "force": 0.0,
        "y_location": 0.0
      }
    }
  }
}
```

| Field | Type | Description |
|-------|------|-------------|
| `neutral_axis_depth` | Number | Distance from centroid to neutral axis (mm) |
| `compression_zone_depth` | Number | Depth of compression zone from extreme fiber (mm) |
| `cracked` | Boolean | Has section cracked in tension? |
| `yielded` | Boolean | Has any steel yielded? |
| `crushing` | Boolean | Has concrete crushed? |
| `resultants` | Object | Resultant forces and locations |

### Distributions Object

Strain and stress profiles across the section depth. Resolution is adaptive based on analysis settings.

**Longitudinal Strain:**
```json
{
  "longitudinal_strain": {
    "description": "Total mechanical strain in longitudinal direction",
    "reference": "y-coordinate from centroid",
    "data": [
      {"y": 300.0, "strain": -0.00241},
      {"y": 287.175, "strain": -0.00215}
    ]
  }
}
```

**Shrinkage and Thermal Strain:**
```json
{
  "shrinkage_thermal_strain": {
    "description": "Non-mechanical strains",
    "data": [
      {"y": 300.0, "epsilon_sh": 0.0, "epsilon_thermal": 0.0}
    ]
  }
}
```

**Concrete Stress:**
```json
{
  "concrete_stress": {
    "description": "Longitudinal stress in concrete",
    "data": [
      {"y": 300.0, "stress": -22.6}
    ]
  }
}
```

**Crack Spacing:**
```json
{
  "crack_spacing": {
    "description": "Crack spacing from MCFT elements",
    "method": "bentz_2005",
    "data": [
      {
        "y": 0.0,
        "spacing": 140.0,
        "width": 0.14,
        "element_id": "elem_10"
      }
    ]
  }
}
```

### Steel State Array

State of each reinforcement layer.

```json
{
  "steel_state": [
    {
      "id": "bottom_bars",
      "material_id": "steel_main",
      "y": -248.7,
      "strain": 0.0017,
      "stress": 340.0,
      "stress_at_crack": 340.0,
      "yielded": true,
      "force": 510.0
    }
  ]
}
```

| Field | Type | Description |
|-------|------|-------------|
| `id` | String | Reinforcement layer identifier |
| `material_id` | String | Material reference |
| `y` | Number | y-coordinate from centroid (mm) |
| `strain` | Number | Average strain in steel (mm/m) |
| `stress` | Number | Average stress in steel (MPa) |
| `stress_at_crack` | Number | Steel stress at crack location (MPa) |
| `yielded` | Boolean | Has this layer yielded? |
| `force` | Number | Total force in this layer (kN) |

---

## Summary Section

**Field:** `results.summary`  
**Type:** Object  
**Required:** Yes

High-level summary statistics and key results.

```json
{
  "summary": {
    "section_behavior": {
      "cracking_moment": 29.54,
      "yield_moment": 265.6,
      "ultimate_moment": 295.6,
      "peak_moment": 250.2,
      "curvature_at_cracking": 0.056,
      "curvature_at_yield": 4.962,
      "curvature_at_peak": 53.758,
      "ductility_curvature": 10.83,
      "ductility_displacement": 8.5
    },
    
    "failure": {
      "mode": "steel_yield",
      "description": "Tension steel yielded, analysis stopped at large deformation",
      "controlling_strain": 0.100,
      "controlling_location": -248.7
    },
    
    "neutral_axis_evolution": {
      "at_cracking": 300.0,
      "at_yield": 275.0,
      "at_peak": 254.0
    },
    
    "convergence": {
      "total_points": 53,
      "converged_points": 53,
      "failed_points": 0,
      "average_iterations": 4.2,
      "max_iterations": 12
    },
    
    "computation": {
      "total_time_seconds": 2.347,
      "time_per_point_ms": 44.3
    }
  }
}
```

### Summary Fields

| Field | Type | Description |
|-------|------|-------------|
| `section_behavior` | Object | Key response metrics |
| `failure` | Object | Failure mode information |
| `neutral_axis_evolution` | Object | Neutral axis depth at key points |
| `convergence` | Object | Solver convergence statistics |
| `computation` | Object | Performance metrics |

**Failure modes:**
- `"concrete_crushing"`: Concrete strain exceeded ultimate
- `"steel_yield"`: Reinforcement yielded (ductile)
- `"steel_fracture"`: Steel strain exceeded ultimate
- `"rebar_fracture"`: Reinforcing bar strain exceeded ultimate
- `"tendon_rupture"`: Prestressing tendon strain exceeded ultimate
- `"tension_controlled"`: Large tensile strains before failure
- `"compression_controlled"`: Compression failure before yield
- `"balanced"`: Simultaneous concrete crushing and steel yield
- `"convergence_failure"`: Solver failed to converge

### Shear Summary (for `shear` analysis type)

When `analysis_type` is `"shear"`, the summary includes a `shear_behavior` block:

```json
{
  "summary": {
    "shear_behavior": {
      "peak_shear_kN": 285.3,
      "shear_strain_at_peak": 1.24,
      "failure_reason": "convergence_failure"
    },
    "convergence": {
      "total_points": 51,
      "converged_points": 48
    }
  }
}
```

| Field | Type | Description |
|-------|------|-------------|
| `peak_shear_kN` | Number | Peak shear force (kN) |
| `shear_strain_at_peak` | Number | Average shear strain at peak (mm/m) |
| `failure_reason` | String | Reason analysis terminated |

**Note:** `analysis_points` is currently a stub (empty array `[]`) for shear analyses. Detailed per-step MCFT element states will be added in a future version.

---

## Validation Against R2K

To validate response-yolo results against R2K:

1. **Extract R2K data**: Use the provided data tables from R2K output
2. **Compare control curves**: Plot M-φ and M-ε curves side-by-side
3. **Check key points**: Compare cracking moment, yield moment, peak moment
4. **Verify profiles**: Compare strain and stress distributions at selected points
5. **Validate steel states**: Check yielding status and stresses at each layer

Acceptable tolerances:
- Moment values: ±2%
- Curvature values: ±5%
- Strain/stress profiles: visual agreement, key features match

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | 2024-02-15 | Initial specification |

---

## Notes for Implementers

1. **All arrays in `analysis_points`** should use the same ordering and indexing throughout
2. **Coordinate system**: y-axis up from centroid (centroid = 0), consistent with input
3. **Profile resolution**: Use `profile_resolution` setting to determine number of points
4. **Computed properties**: Calculate all derived values (Ec, ε_y, etc.) in parser, echo in output
5. **Failed points**: If solver fails to converge, still include point with `converged: false`
6. **Crack data**: Only populated when MCFT shear analysis is enabled
7. **Element data**: Optional, only for shear analysis cases
8. **Units**: Maintain consistency throughout file as specified in units section
