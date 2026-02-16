"""
Command-line interface for response-yolo.

Usage:
  response-yolo run <input_file> [-o <output_file>] [--format json|csv]
  response-yolo info <input_file>
  response-yolo --version

Examples:
  # Run M-phi analysis from R2T file
  response-yolo run beam.r2t -o results.json

  # Run from JSON input
  response-yolo run beam.json -o results.json

  # Run V-gamma shear analysis
  response-yolo run shear_beam.json -o shear_results.json

  # Print section info
  response-yolo info beam.json
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Dict, Any

from response_yolo import __version__, __codename__
from response_yolo.analysis.moment_curvature import MomentCurvatureAnalysis
from response_yolo.analysis.shear_analysis import ShearAnalysis
from response_yolo.io.r2t_parser import parse_r2t
from response_yolo.io.json_io import load_json_input, save_json_output


BANNER = f"""\
 ╔══════════════════════════════════════════════════════╗
 ║  response-yolo v{__version__} ("{__codename__}")                    ║
 ║  Python clone of Response-2000                       ║
 ║  Based on MCFT — Vecchio & Collins (1986)            ║
 ║  Original R2K by Evan Bentz (U of T, 2000)           ║
 ╚══════════════════════════════════════════════════════╝
"""


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="response-yolo",
        description="Reinforced concrete sectional analysis (Response-2000 clone)",
    )
    parser.add_argument("--version", action="version", version=f"response-yolo {__version__}")

    subparsers = parser.add_subparsers(dest="command")

    # --- run ---
    run_parser = subparsers.add_parser("run", help="Run an analysis")
    run_parser.add_argument("input_file", help="Input file (.r2t or .json)")
    run_parser.add_argument("-o", "--output", help="Output JSON file", default=None)
    run_parser.add_argument(
        "--format", choices=["json", "csv"], default="json",
        help="Output format (default: json)"
    )
    run_parser.add_argument("--quiet", "-q", action="store_true", help="Suppress banner")

    # --- info ---
    info_parser = subparsers.add_parser("info", help="Show section information")
    info_parser.add_argument("input_file", help="Input file (.r2t or .json)")

    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_help()
        return 0

    if args.command == "info":
        return _cmd_info(args)

    if args.command == "run":
        return _cmd_run(args)

    return 0


def _load_input(filepath: str) -> Dict[str, Any]:
    """Load input from R2T or JSON."""
    p = Path(filepath)
    if not p.exists():
        print(f"Error: file not found: {filepath}", file=sys.stderr)
        sys.exit(1)

    ext = p.suffix.lower()
    if ext == ".r2t":
        return parse_r2t(p)
    elif ext == ".json":
        return load_json_input(p)
    else:
        # Try JSON first, fall back to R2T
        try:
            return load_json_input(p)
        except (json.JSONDecodeError, KeyError):
            return parse_r2t(p)


def _cmd_info(args) -> int:
    """Print section information."""
    config = _load_input(args.input_file)
    xs = config["section"]

    print(BANNER)
    print(f"Input file: {args.input_file}")
    print(f"Units: {config['units']}")
    print()
    print("Section Properties:")
    print(f"  Height:           {xs.height:.1f} mm")
    print(f"  Gross area:       {xs.gross_area:.1f} mm^2")
    print(f"  Centroid y:       {xs.centroid_y:.1f} mm (from bottom)")
    print(f"  Gross Ig:         {xs.gross_moment_of_inertia:.3e} mm^4")
    print(f"  Concrete layers:  {len(xs.concrete_layers)}")
    print(f"  Rebar locations:  {len(xs.rebars)}")
    print(f"  Tendons:          {len(xs.tendons)}")

    if xs.rebars:
        total_as = sum(b.area for b in xs.rebars)
        rho = total_as / xs.gross_area * 100.0
        print(f"  Total As:         {total_as:.1f} mm^2")
        print(f"  Reinf. ratio:     {rho:.2f}%")

    # Show transverse reinforcement status
    has_stirrups = any(lay.rho_y > 0 for lay in xs.concrete_layers)
    print(f"  Stirrups:         {'Yes' if has_stirrups else 'No'}")

    print()
    print(f"Analysis type: {config['analysis_type']}")
    return 0


def _build_section_props(xs) -> Dict[str, Any]:
    """Build section properties dict for output."""
    return {
        "height_mm": xs.height,
        "gross_area_mm2": xs.gross_area,
        "centroid_y_mm": xs.centroid_y,
        "gross_Ig_mm4": xs.gross_moment_of_inertia,
        "n_concrete_layers": len(xs.concrete_layers),
        "n_rebars": len(xs.rebars),
        "n_tendons": len(xs.tendons),
    }


def _cmd_run(args) -> int:
    """Run the analysis — dispatches to the appropriate analysis runner."""
    if not args.quiet:
        print(BANNER, file=sys.stderr)

    config = _load_input(args.input_file)
    analysis_type = config["analysis_type"]

    if analysis_type == "moment_curvature":
        return _run_moment_curvature(args, config)
    elif analysis_type == "shear":
        return _run_shear(args, config)
    else:
        print(
            f"Error: analysis type '{analysis_type}' is not yet implemented.\n"
            f"Currently supported: moment_curvature, shear",
            file=sys.stderr,
        )
        return 1


def _run_moment_curvature(args, config: Dict[str, Any]) -> int:
    """Run M-phi / M-ex moment-curvature analysis."""
    xs = config["section"]
    analysis_params = config.get("analysis_params", {})
    loading = config.get("loading", {})

    axial_load = loading.get("N", 0.0)
    mphi = MomentCurvatureAnalysis(
        section=xs,
        axial_load=axial_load,
        max_curvature=analysis_params.get("max_curvature"),
        n_steps=analysis_params.get("n_steps", 200),
        tol_force=analysis_params.get("tol_force", 1.0),
        max_iter=analysis_params.get("max_iter", 50),
    )

    if not args.quiet:
        print("Running moment-curvature analysis...", file=sys.stderr)
        print(f"  Section height: {xs.height:.1f} mm", file=sys.stderr)
        print(f"  Concrete layers: {len(xs.concrete_layers)}", file=sys.stderr)
        print(f"  Rebar locations: {len(xs.rebars)}", file=sys.stderr)
        print(f"  Axial load: {axial_load:.1f} N", file=sys.stderr)

    t0 = time.perf_counter()
    result = mphi.run()
    elapsed = time.perf_counter() - t0

    if not args.quiet:
        print(f"  Completed in {elapsed:.3f}s ({len(result.points)} points)", file=sys.stderr)
        if result.cracking_moment:
            print(f"  Cracking moment: {result.cracking_moment/1e6:.2f} kN-m", file=sys.stderr)
        if result.yield_moment:
            print(f"  Yield moment:    {result.yield_moment/1e6:.2f} kN-m", file=sys.stderr)
        if result.ultimate_moment:
            print(f"  Ultimate moment: {result.ultimate_moment/1e6:.2f} kN-m", file=sys.stderr)
        if result.failure_reason:
            print(f"  Failure mode:    {result.failure_reason}", file=sys.stderr)

    # Output
    output_file = args.output
    if output_file is None:
        output_file = Path(args.input_file).stem + "_results.json"

    if args.format == "csv":
        _write_csv(result, output_file)
    else:
        save_json_output(
            result.to_dict(),
            output_file,
            input_file=args.input_file,
            analysis_type="moment_curvature",
            section_props=_build_section_props(xs),
            computation_time=elapsed,
        )

    if not args.quiet:
        print(f"  Results written to: {output_file}", file=sys.stderr)

    return 0


def _run_shear(args, config: Dict[str, Any]) -> int:
    """Run V-gamma shear analysis."""
    xs = config["section"]
    analysis_params = config.get("analysis_params", {})
    loading = config.get("loading", {})

    axial_load = loading.get("N", 0.0)
    moment = loading.get("M", 0.0)

    # Warn if no transverse reinforcement
    has_stirrups = any(lay.rho_y > 0 for lay in xs.concrete_layers)
    if not has_stirrups and not args.quiet:
        print(
            "  Warning: no transverse reinforcement defined. "
            "Shear results will have zero stirrup contribution.",
            file=sys.stderr,
        )

    shear = ShearAnalysis(
        section=xs,
        axial_load=axial_load,
        moment=moment,
        gamma_max=analysis_params.get("gamma_max", 0.01),
        n_steps=analysis_params.get("n_steps", 50),
        tol_force=analysis_params.get("tol_force", 1.0),
        tol_moment=analysis_params.get("tol_moment", 100.0),
        max_iter=analysis_params.get("max_iter", 30),
    )

    if not args.quiet:
        print("Running V-gamma shear analysis...", file=sys.stderr)
        print(f"  Section height: {xs.height:.1f} mm", file=sys.stderr)
        print(f"  Concrete layers: {len(xs.concrete_layers)}", file=sys.stderr)
        print(f"  Rebar locations: {len(xs.rebars)}", file=sys.stderr)
        print(f"  Stirrups: {'Yes' if has_stirrups else 'No'}", file=sys.stderr)
        print(f"  Axial load: {axial_load:.1f} N", file=sys.stderr)
        print(f"  Applied moment: {moment:.1f} N-mm", file=sys.stderr)
        print(f"  gamma_max: {shear.gamma_max}", file=sys.stderr)
        print(f"  n_steps: {shear.n_steps}", file=sys.stderr)

    t0 = time.perf_counter()
    result = shear.run()
    elapsed = time.perf_counter() - t0

    if not args.quiet:
        n_conv = sum(1 for p in result.points if p.converged)
        print(
            f"  Completed in {elapsed:.3f}s "
            f"({len(result.points)} points, {n_conv} converged)",
            file=sys.stderr,
        )
        print(f"  Peak shear: {result.peak_shear/1e3:.1f} kN", file=sys.stderr)
        print(f"  Gamma at peak: {result.gamma_at_peak:.6f}", file=sys.stderr)

    # Output
    output_file = args.output
    if output_file is None:
        output_file = Path(args.input_file).stem + "_results.json"

    if args.format == "csv":
        _write_csv_shear(result, output_file)
    else:
        save_json_output(
            result.to_dict(),
            output_file,
            input_file=args.input_file,
            analysis_type="shear",
            section_props=_build_section_props(xs),
            computation_time=elapsed,
        )

    if not args.quiet:
        print(f"  Results written to: {output_file}", file=sys.stderr)

    return 0


def _write_csv(result, filepath: str) -> None:
    """Write M-phi results as CSV."""
    with open(filepath, "w") as f:
        f.write("curvature_1/mm,curvature_1/m,moment_Nmm,moment_kNm,eps_0,neutral_axis_y_mm\n")
        for p in result.points:
            f.write(
                f"{p.curvature:.10e},{p.curvature*1000:.10e},"
                f"{p.moment:.6e},{p.moment_kNm:.6f},"
                f"{p.eps_0:.10e},{p.neutral_axis_y:.3f}\n"
            )


def _write_csv_shear(result, filepath: str) -> None:
    """Write V-gamma results as CSV."""
    with open(filepath, "w") as f:
        f.write(
            "gamma_xy0,shear_force_N,shear_force_kN,"
            "moment_Nmm,moment_kNm,eps_0,curvature_1_per_mm,converged\n"
        )
        for p in result.points:
            f.write(
                f"{p.gamma_xy0:.10e},{p.shear_force:.6e},{p.shear_force/1e3:.6f},"
                f"{p.moment:.6e},{p.moment/1e6:.6f},"
                f"{p.eps_0:.10e},{p.curvature:.10e},{p.converged}\n"
            )


if __name__ == "__main__":
    sys.exit(main())
