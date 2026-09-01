"""Tests for AI Bill of Materials (AIBOM) generator and devops scan aibom command."""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from devops_cli.commands.scan import app as scan_app
from devops_cli.security.aibom import (
    ModelLicenseType,
    detect_trust_remote_code,
    estimate_hardware_requirements,
    extract_aibom_components,
    generate_aibom,
)

runner = CliRunner()


def test_estimate_hardware_requirements() -> None:
    """Estimate RAM, VRAM, and disk storage requirements for dense and MoE models."""
    # 1. Standard dense model (7B at 16-bit)
    dense_7b = estimate_hardware_requirements(7.0, quantization_bits=16, context_window=8192)
    assert dense_7b.parameters_billion == 7.0
    assert dense_7b.estimated_disk_gb > 14.0
    assert dense_7b.estimated_vram_gb > 15.0
    assert dense_7b.estimated_ram_gb > 20.0

    # 2. Quantized model (7B at 4-bit)
    quant_7b = estimate_hardware_requirements(7.0, quantization_bits=4, context_window=8192)
    assert quant_7b.estimated_disk_gb < dense_7b.estimated_disk_gb
    assert quant_7b.estimated_vram_gb < dense_7b.estimated_vram_gb

    # 3. MoE Model
    moe = estimate_hardware_requirements(
        56.0,
        quantization_bits=16,
        context_window=8192,
        is_moe=True,
        active_experts=2,
        total_experts=8,
    )
    assert moe.is_moe is True
    assert moe.estimated_vram_gb > 0.0

    # 4. Zero params
    zero_est = estimate_hardware_requirements(0.0)
    assert zero_est.estimated_vram_gb == 0.0


def test_detect_trust_remote_code(tmp_path: Path) -> None:
    """Detect trust_remote_code declarations across config.json and Python source files."""
    # Clean directory
    clean_dir = tmp_path / "clean_model"
    clean_dir.mkdir()
    (clean_dir / "config.json").write_text('{"hidden_size": 4096}', encoding="utf-8")
    assert detect_trust_remote_code(clean_dir) is False

    # Auto-map custom pipeline
    custom_dir = tmp_path / "custom_model"
    custom_dir.mkdir()
    (custom_dir / "config.json").write_text(
        '{"auto_map": {"AutoModel": "modeling_custom.CustomModel"}}', encoding="utf-8"
    )
    assert detect_trust_remote_code(custom_dir) is True

    # Python AST declaration
    py_dir = tmp_path / "py_model"
    py_dir.mkdir()
    (py_dir / "loader.py").write_text(
        "from transformers import AutoModel\nmodel = AutoModel.from_pretrained('x', trust_remote_code=True)\n",
        encoding="utf-8",
    )
    assert detect_trust_remote_code(py_dir) is True


def test_generate_aibom_payload(tmp_path: Path) -> None:
    """Generate CycloneDX AIBOM manifest from mock model workspace."""
    model_dir = tmp_path / "qwen-coder"
    model_dir.mkdir()
    (model_dir / "config.json").write_text(
        json.dumps(
            {
                "hidden_size": 4096,
                "num_hidden_layers": 32,
                "license": "apache-2.0",
                "_name_or_path": "Qwen/Qwen2.5-Coder-7B",
            }
        ),
        encoding="utf-8",
    )
    (model_dir / "model.safetensors").write_text("weights", encoding="utf-8")

    components = extract_aibom_components(tmp_path)
    assert len(components) == 1
    comp = components[0]
    assert comp.name == "qwen-coder"
    assert comp.license_type == ModelLicenseType.PERMISSIVE_OPEN_WEIGHT
    assert comp.has_safe_weights is True

    aibom = generate_aibom(tmp_path, project_name="test-repo", project_version="0.2.7")
    assert aibom["bomFormat"] == "CycloneDX"
    assert aibom["specVersion"] == "1.5"
    assert len(aibom["components"]) == 1
    assert aibom["components"][0]["name"] == "qwen-coder"


def test_scan_aibom_cli(tmp_path: Path) -> None:
    """Test devops scan aibom CLI command in stdout, file, and dry-run modes."""
    model_dir = tmp_path / "granite-model"
    model_dir.mkdir()
    (model_dir / "config.json").write_text(
        json.dumps(
            {
                "hidden_size": 2048,
                "num_hidden_layers": 24,
                "license": "apache-2.0",
            }
        ),
        encoding="utf-8",
    )

    # 1. Output to stdout
    res = runner.invoke(scan_app, ["aibom", str(tmp_path)])
    assert res.exit_code == 0
    assert "CycloneDX" in res.output
    assert "granite-model" in res.output

    # 2. Output to file
    out_file = tmp_path / "aibom.json"
    res_file = runner.invoke(scan_app, ["aibom", str(tmp_path), "--output", str(out_file)])
    assert res_file.exit_code == 0
    assert out_file.exists()
    data = json.loads(out_file.read_text(encoding="utf-8"))
    assert data["bomFormat"] == "CycloneDX"

    # 3. Invalid format rejection
    res_err = runner.invoke(scan_app, ["aibom", str(tmp_path), "--format", "unknown_fmt"])
    assert res_err.exit_code == 1
    assert "Unsupported AIBOM format" in res_err.output

    # 4. Dry run
    res_dry = runner.invoke(scan_app, ["aibom", str(tmp_path), "--dry-run"])
    assert res_dry.exit_code == 0
