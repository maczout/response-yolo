"""Tests for I/O: R2T parsing and JSON input/output."""

import json
import pytest
from pathlib import Path

from response_yolo.io.r2t_parser import parse_r2t
from response_yolo.io.json_io import load_json_input, save_json_output
from response_yolo.analysis.moment_curvature import MomentCurvatureAnalysis


EXAMPLES_DIR = Path(__file__).parent.parent / "examples"


class TestR2TParser:
    def test_parse_simple_beam(self):
        config = parse_r2t(EXAMPLES_DIR / "simple_beam.r2t")
        assert config["units"] == "SI"
        assert config["analysis_type"] == "moment_curvature"
        xs = config["section"]
        assert len(xs.rebars) == 2
        assert xs.rebars[0].y == 50
        assert xs.rebars[0].area == 1500

    def test_not_found(self):
        with pytest.raises(FileNotFoundError):
            parse_r2t("/nonexistent/file.r2t")


class TestJSONIO:
    def test_load_simple_beam(self):
        config = load_json_input(EXAMPLES_DIR / "simple_beam.json")
        assert config["units"] == "SI"
        xs = config["section"]
        assert len(xs.rebars) == 2
        assert xs.gross_area == pytest.approx(300 * 500, rel=0.01)

    def test_load_prestressed(self):
        config = load_json_input(EXAMPLES_DIR / "prestressed_beam.json")
        xs = config["section"]
        assert len(xs.tendons) == 1
        assert xs.tendons[0].prestrain == 0.006

    def test_save_and_reload(self, tmp_path):
        config = load_json_input(EXAMPLES_DIR / "simple_beam.json")
        xs = config["section"]
        analysis = MomentCurvatureAnalysis(xs, n_steps=10)
        result = analysis.run()

        out_path = tmp_path / "test_output.json"
        save_json_output(
            result.to_dict(),
            out_path,
            input_file="simple_beam.json",
            analysis_type="moment_curvature",
        )

        assert out_path.exists()
        with open(out_path) as f:
            data = json.load(f)
        assert data["analysis_type"] == "moment_curvature"
        assert len(data["result"]["response"]) == len(result.points)


class TestR2TvsJSON:
    """Verify that R2T and JSON inputs produce consistent results."""

    def test_same_section_properties(self):
        config_r2t = parse_r2t(EXAMPLES_DIR / "simple_beam.r2t")
        config_json = load_json_input(EXAMPLES_DIR / "simple_beam.json")

        xs_r2t = config_r2t["section"]
        xs_json = config_json["section"]

        assert xs_r2t.gross_area == pytest.approx(xs_json.gross_area, rel=0.01)
        assert xs_r2t.centroid_y == pytest.approx(xs_json.centroid_y, rel=0.01)
        assert len(xs_r2t.rebars) == len(xs_json.rebars)
