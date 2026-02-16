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
            computation_time=1.23,
        )

        assert out_path.exists()
        with open(out_path) as f:
            data = json.load(f)

        # New spec-compliant envelope
        assert data["metadata"]["analysis_type"] == "moment_curvature"
        assert data["metadata"]["computation_time"] == 1.23
        assert "units" in data
        assert data["units"]["moment"] == "kNm"

        # Results block
        results = data["results"]
        assert len(results["response"]) == len(result.points)
        assert "control_curves" in results
        assert "moment_curvature" in results["control_curves"]
        assert "moment_axial_strain" in results["control_curves"]
        assert "summary" in results

    def test_save_input_format_detection(self, tmp_path):
        """Verify the input source format is detected from file extension."""
        config = load_json_input(EXAMPLES_DIR / "simple_beam.json")
        xs = config["section"]
        analysis = MomentCurvatureAnalysis(xs, n_steps=5)
        result = analysis.run()

        out_json = tmp_path / "out_json.json"
        save_json_output(result.to_dict(), out_json, input_file="beam.json")
        with open(out_json) as f:
            data = json.load(f)
        assert data["metadata"]["input_source"]["format"] == "response_yolo_json"

        out_r2t = tmp_path / "out_r2t.json"
        save_json_output(result.to_dict(), out_r2t, input_file="beam.r2t")
        with open(out_r2t) as f:
            data = json.load(f)
        assert data["metadata"]["input_source"]["format"] == "r2t"


class TestTransSteel:
    """Test transverse steel (stirrup) parsing."""

    def test_json_trans_steel(self):
        """JSON input with trans_steel should set stirrups on the section."""
        config = load_json_input(EXAMPLES_DIR / "shear_beam.json")
        xs = config["section"]
        assert config["analysis_type"] == "shear"
        # Stirrups should be applied — at least some layers have rho_y > 0
        assert any(lay.rho_y > 0 for lay in xs.concrete_layers)

    def test_json_trans_steel_inline(self, tmp_path):
        """Verify trans_steel parsing with explicit data."""
        inp = {
            "section": {"shape": "rectangular", "b": 300, "h": 500},
            "concrete": {"fc": 35},
            "long_steel": {"fy": 400},
            "rebars": [{"y": 50, "area": 1500}],
            "trans_steel": {"fy": 300, "Es": 200000, "Av": 200, "s": 150},
            "analysis": {"type": "shear"},
        }
        p = tmp_path / "shear_input.json"
        with open(p, "w") as f:
            json.dump(inp, f)

        config = load_json_input(p)
        xs = config["section"]
        assert any(lay.rho_y > 0 for lay in xs.concrete_layers)
        assert config["analysis_type"] == "shear"

    def test_r2t_trans_steel(self, tmp_path):
        """R2T input with [TRANS STEEL] should set stirrups."""
        r2t_text = """\
[UNITS]
SI

[CONCRETE]
fc = 35

[SECTION]
b = 300
h = 500

[LONG STEEL]
fy = 400
Es = 200000

[REBAR]
50  1500
450 400

[TRANS STEEL]
fy = 400
Av = 157
s = 200

[LOADING]
N = 0

[ANALYSIS]
shear
gamma_max = 0.005
n_steps = 20
"""
        p = tmp_path / "shear_test.r2t"
        p.write_text(r2t_text)

        config = parse_r2t(p)
        xs = config["section"]
        assert config["analysis_type"] == "shear"
        assert any(lay.rho_y > 0 for lay in xs.concrete_layers)

    def test_json_no_trans_steel(self):
        """JSON input without trans_steel should have all rho_y == 0."""
        config = load_json_input(EXAMPLES_DIR / "simple_beam.json")
        xs = config["section"]
        assert all(lay.rho_y == 0 for lay in xs.concrete_layers)


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
