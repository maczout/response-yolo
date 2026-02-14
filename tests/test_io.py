"""Tests for JSON I/O and CLI."""

import json
import subprocess
import sys
import unittest
from pathlib import Path

from response_yolo.io import format_output, load_input, parse_input


EXAMPLES_DIR = Path(__file__).resolve().parent.parent / "examples"


class TestParsing(unittest.TestCase):
    def test_load_example_input(self):
        section, params = load_input(EXAMPLES_DIR / "example_input.json")
        self.assertEqual(section.height, 500)
        self.assertEqual(len(section.rebar), 2)
        self.assertEqual(params["n_steps"], 80)

    def test_load_minimal_input(self):
        section, params = load_input(EXAMPLES_DIR / "minimal_input.json")
        self.assertEqual(section.height, 400)
        self.assertEqual(len(section.rebar), 1)

    def test_parse_multiple_steels(self):
        data = {
            "concrete": {"fc": 30},
            "steel": {
                "mild": {"fy": 300},
                "high": {"fy": 500},
            },
            "section": {"type": "rectangle", "width": 300, "height": 500},
            "rebar": [
                {"area": 500, "depth": 50, "steel": "mild"},
                {"area": 1000, "depth": 450, "steel": "high"},
            ],
        }
        section, _ = parse_input(data)
        self.assertEqual(len(section.rebar), 2)
        self.assertEqual(section.rebar[0].steel.fy, 300)
        self.assertEqual(section.rebar[1].steel.fy, 500)


class TestCLI(unittest.TestCase):
    def test_version(self):
        result = subprocess.run(
            [sys.executable, "-m", "response_yolo.cli", "--version"],
            capture_output=True,
            text=True,
        )
        self.assertIn("0.1.0", result.stdout)

    def test_moment_curvature_stdout(self):
        result = subprocess.run(
            [
                sys.executable, "-m", "response_yolo.cli",
                "moment-curvature",
                str(EXAMPLES_DIR / "minimal_input.json"),
                "-n", "5",
            ],
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0)
        output = json.loads(result.stdout)
        self.assertEqual(output["analysis"], "moment_curvature")
        self.assertEqual(len(output["results"]["points"]), 6)

    def test_stub_exits_nonzero(self):
        for cmd in ["axial", "shear", "full"]:
            result = subprocess.run(
                [sys.executable, "-m", "response_yolo.cli", cmd],
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("not yet implemented", result.stderr)


if __name__ == "__main__":
    unittest.main()
