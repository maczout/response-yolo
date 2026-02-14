"""Command-line interface for Response-YOLO."""

from __future__ import annotations

import argparse
import json
import sys

from . import __version__
from .analysis import MomentCurvatureAnalysis
from .io import format_output, load_input, write_output
from .section import DiscretisedSection


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="response-yolo",
        description=(
            "Response-YOLO: command-line reinforced concrete sectional analysis.  "
            "Inspired by Response-2000 (Bentz & Collins)."
        ),
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    sub = parser.add_subparsers(dest="command")

    # --- moment-curvature --------------------------------------------------
    mk = sub.add_parser(
        "moment-curvature",
        aliases=["mk"],
        help="Run a moment-curvature analysis (pure bending, N=0).",
    )
    mk.add_argument(
        "input",
        help="Path to the JSON input file.",
    )
    mk.add_argument(
        "-o", "--output",
        help="Path to write JSON results.  If omitted, results go to stdout.",
    )
    mk.add_argument(
        "-n", "--n-steps",
        type=int,
        default=100,
        help="Number of curvature increments (default 100).",
    )
    mk.add_argument(
        "--max-curvature",
        type=float,
        default=None,
        help="Maximum curvature in 1/mm (default: auto).",
    )
    mk.add_argument(
        "--n-fibres",
        type=int,
        default=100,
        help="Number of concrete fibres for discretisation (default 100).",
    )

    # --- stubs -------------------------------------------------------------
    for name, desc in [
        ("axial", "Axial force–deformation analysis (stub – not yet implemented)"),
        ("shear", "Shear analysis via MCFT (stub – not yet implemented)"),
        ("full", "Combined N+M+V sectional analysis (stub – not yet implemented)"),
    ]:
        stub = sub.add_parser(name, help=desc)
        stub.add_argument("input", nargs="?", help="Path to the JSON input file.")

    return parser


def _run_moment_curvature(args: argparse.Namespace) -> None:
    section, analysis_params = load_input(args.input)

    n_steps = analysis_params.get("n_steps", args.n_steps)
    max_curv = analysis_params.get("max_curvature", args.max_curvature)
    n_fibres = analysis_params.get("n_fibres", args.n_fibres)

    dsec = DiscretisedSection.from_section(section, n_fibres=n_fibres)

    analysis = MomentCurvatureAnalysis(
        section=dsec,
        max_curvature=max_curv,
        n_steps=n_steps,
    )
    result = analysis.run()

    if args.output:
        write_output(result, args.output)
        print(f"Results written to {args.output}", file=sys.stderr)
    else:
        print(json.dumps(format_output(result), indent=2))


def _run_stub(name: str) -> None:
    print(
        f"Error: '{name}' analysis is not yet implemented in Response-YOLO.",
        file=sys.stderr,
    )
    sys.exit(1)


def main(argv: list[str] | None = None) -> None:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command in ("moment-curvature", "mk"):
        _run_moment_curvature(args)
    elif args.command == "axial":
        _run_stub("axial")
    elif args.command == "shear":
        _run_stub("shear")
    elif args.command == "full":
        _run_stub("full")
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
