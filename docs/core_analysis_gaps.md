# Core Analysis Gaps — Quick Assessment

## Current State

Response-YOLO has a solid M-φ (moment-curvature) analysis engine with working material
models (Popovics/Hognestad/Collins-Mitchell concrete, trilinear steel, Ramberg-Osgood
prestressing) and layered section integration.  The M-φ solver uses Newton-Raphson on
εx₀ for each curvature increment, integrating forces and stiffness (EA, ES, EI) through
the section depth.  Cross-section geometry supports rectangular, Tee, circular, and
generic shapes.  **Prior to this work, the entire shear analysis pipeline was stubbed
out — no MCFT biaxial solver, no shear strain DOF, no shear stress distribution, and
no V-γ response.**

## Critical Gaps (Now Addressed)

### Gap 1: No MCFT Biaxial Node Solver
- **What was wrong**: Each layer computed uniaxial σx = f(εx).  No (εx, εy, γxy) → (σx, σy, τxy) with the σy = 0 constraint.
- **What it should be**: Full MCFT at each layer per Bentz Ch 3 (Sections 3-1 to 3-4). Mohr's circle for principal strains, softened compression on ε₂, tension stiffening on ε₁, iterate εy until σy = 0.
- **Fix**: New `analysis/mcft.py` — `solve_mcft_node()` with Newton-Raphson on εy, condensed 2×2 tangent output.

### Gap 2: No Compression Softening
- **What was wrong**: `Concrete.stress()` used unsoftened compression curves regardless of biaxial state.
- **What it should be**: β = 1/(0.8 + 170·ε₁) ≤ 1.0 reduces compressive strength when transverse tension is present (Vecchio & Collins 1986).
- **Fix**: Added `Concrete.compression_stress_softened()` method. Existing `stress()` untouched for backward compatibility.

### Gap 3: No Shear Strain in Global State
- **What was wrong**: Strain state was 2-DOF (ε₀, φ) — no γxy₀ or shear strain profile.
- **What it should be**: 3 DOFs (ε₀, φ, γxy₀) with γ(z) = γxy₀·s(z), parabolic s(z) averaging to 1.0 (Bentz Ch 7, Section 7-2).
- **Fix**: New `CrossSection.integrate_forces_shear()` and `integrate_stiffness_3x3()` with parabolic `shear_strain_profile()`.

### Gap 4: No Longitudinal Stiffness Method
- **What was wrong**: No shear stress distribution computation existed.
- **What it should be**: Bentz Eq 6-9: Δq = j·(dεx + z·dφ) + k·dγxy.  Assemble 3×3 J, solve for virtual strains, integrate shear flow (Bentz Ch 6, Section 6-5).
- **Fix**: New `analysis/longitudinal_stiffness.py` with `compute_shear_stress_distribution()`.

### Gap 5: No Transverse Reinforcement Data
- **What was wrong**: `ConcreteLayer` had no rho_y or stirrup material — MCFT couldn't know about transverse steel.
- **What it should be**: Each layer carries its transverse reinforcement ratio.
- **Fix**: Added `rho_y` and `stirrup_material` fields to `ConcreteLayer`, plus `CrossSection.set_stirrups()`.

## Working Features (Preserved)

- All material models (concrete compression curves, MCFT tension stiffening, steel bilinear/trilinear, prestressing Ramberg-Osgood)
- Section geometry and discretization (shapes, layer generation)
- M-φ analysis (Newton-Raphson solver, event detection for cracking/yielding/failure)
- Force and stiffness integration for 2-DOF case (`integrate_forces`, `integrate_stiffness`)
- I/O (R2T parser, JSON, CSV output)
- All 73 existing tests pass without modification

## Prototype Implementation Summary

| Component | File | Lines | Status |
|-----------|------|-------|--------|
| MCFT node solver | `analysis/mcft.py` | ~270 | New |
| Compression softening | `materials/concrete.py` | +40 | Added method |
| Transverse reinforcement | `section/geometry.py` | +10 | Added fields |
| Stirrup assignment | `section/cross_section.py` | +25 | Added method |
| 3-DOF section integration | `section/cross_section.py` | +100 | Added methods |
| Longitudinal Stiffness Method | `analysis/longitudinal_stiffness.py` | ~200 | New |
| V-γ shear analysis | `analysis/shear_analysis.py` | ~170 | New (replaces stub) |
| Tests | `tests/test_mcft.py`, `tests/test_shear_analysis.py` | ~180 | New |

## Notes & Future Work

- **Shear strain profile**: Currently parabolic (rectangular sections). T-sections need width-adjusted distribution.
- **Aggregate interlock crack check**: Not implemented (Vecchio-Collins crack slip limit). Add as failure criterion.
- **Dynamic layering**: Currently uses uniform layers (50-100). Adaptive refinement for high curvature regions is deferred.
- **Longitudinal Stiffness Method**: Returns relative shear stress distribution shape. The direct MCFT integration (`integrate_forces_shear`) provides absolute V values.
- **Pre-existing issue**: `test_elastic_stiffness` in M-φ tests has ~10% discrepancy vs analytical EI — unrelated to this work.
