"""Tests for AI Bill of Materials (AIBOM) generator and devops scan aibom command."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from syrupy.assertion import SnapshotAssertion
from syrupy.matchers import path_type

from devops_cli.security.aibom import (
    ModelLicenseType,
    _classify_license,
    _compute_sha256,
    detect_trust_remote_code,
    estimate_hardware_requirements,
    extract_aibom_components,
    generate_aibom,
)

# The two fields of an AIBOM that change on each run: a random serial number and the time.
_RUN_FIELDS = path_type({"serialNumber": (str,), "metadata.timestamp": (str,)})


def _qwen_workspace(root: Path) -> Path:
    """A workspace with one Hugging Face model directory: a config with a license, and weights."""
    model_dir = root / "qwen-coder"
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
    return root


def _granite_workspace(root: Path) -> Path:
    """A workspace with one model directory whose config names a license but no weights."""
    model_dir = root / "granite-model"
    model_dir.mkdir()
    (model_dir / "config.json").write_text(
        json.dumps({"hidden_size": 2048, "num_hidden_layers": 24, "license": "apache-2.0"}),
        encoding="utf-8",
    )
    return root


def test_a_dense_model_needs_more_than_its_weights_in_vram_and_ram() -> None:
    """A 7B model at 16 bits needs more than 14 GB of disk, 15 GB of VRAM and 20 GB of RAM."""
    dense = estimate_hardware_requirements(7.0, quantization_bits=16, context_window=8192)

    assert (
        dense.parameters_billion,
        dense.estimated_disk_gb > 14.0,
        dense.estimated_vram_gb > 15.0,
        dense.estimated_ram_gb > 20.0,
    ) == (7.0, True, True, True)


def test_quantization_lowers_the_disk_and_vram_estimates() -> None:
    """The same 7B model at 4 bits needs less disk and less VRAM than at 16 bits."""
    dense = estimate_hardware_requirements(7.0, quantization_bits=16, context_window=8192)
    quantized = estimate_hardware_requirements(7.0, quantization_bits=4, context_window=8192)

    assert (
        quantized.estimated_disk_gb < dense.estimated_disk_gb,
        quantized.estimated_vram_gb < dense.estimated_vram_gb,
    ) == (True, True)


def test_a_mixture_of_experts_model_is_marked_and_needs_vram() -> None:
    """A mixture-of-experts estimate says so and needs VRAM."""
    moe = estimate_hardware_requirements(
        56.0,
        quantization_bits=16,
        context_window=8192,
        is_moe=True,
        active_experts=2,
        total_experts=8,
    )

    assert (moe.is_moe, moe.estimated_vram_gb > 0.0) == (True, True)


def test_a_model_with_no_parameters_needs_no_vram() -> None:
    """Zero parameters give a VRAM estimate of zero."""
    assert estimate_hardware_requirements(0.0).estimated_vram_gb == 0.0


@pytest.mark.parametrize(
    ("files", "expected"),
    [
        pytest.param({"config.json": '{"hidden_size": 4096}'}, False, id="plain-config"),
        pytest.param(
            {"config.json": '{"auto_map": {"AutoModel": "modeling_custom.CustomModel"}}'},
            True,
            id="auto-map",
        ),
        pytest.param({"config.json": '{"trust_remote_code": true}'}, True, id="config-flag"),
        pytest.param(
            {"config.json": '{"custom_pipelines": {"task": "custom"}}'}, True, id="custom-pipelines"
        ),
        pytest.param({"config.json": "INVALID JSON"}, False, id="config-not-json"),
        pytest.param(
            {
                "loader.py": "from transformers import AutoModel\n"
                "model = AutoModel.from_pretrained('x', trust_remote_code=True)\n"
            },
            True,
            id="python-argument",
        ),
        pytest.param({"script.py": "def broken_syntax( :"}, False, id="python-not-parseable"),
    ],
)
def test_trust_remote_code_is_detected_from_config_and_source(
    tmp_path: Path, files: dict[str, str], expected: bool
) -> None:
    """A model directory asks for remote code through its config or a Python call, and an
    unreadable file asks for nothing."""
    for name, text in files.items():
        (tmp_path / name).write_text(text, encoding="utf-8")

    assert detect_trust_remote_code(tmp_path) is expected


def test_a_directory_that_does_not_exist_asks_for_no_remote_code(tmp_path: Path) -> None:
    """A missing model directory is not a request for remote code."""
    assert detect_trust_remote_code(tmp_path / "does_not_exist") is False


def test_a_file_that_does_not_exist_has_no_digest(tmp_path: Path) -> None:
    """The digest of a missing file is empty, so it adds no hash to the document."""
    assert _compute_sha256(tmp_path / "ghost_file.bin") == ""


@pytest.mark.parametrize(
    ("license_name", "category"),
    [
        pytest.param("", ModelLicenseType.UNKNOWN, id="empty"),
        pytest.param(None, ModelLicenseType.UNKNOWN, id="none"),
        pytest.param("Apache 2.0", ModelLicenseType.PERMISSIVE_OPEN_WEIGHT, id="apache"),
        pytest.param("MIT", ModelLicenseType.PERMISSIVE_OPEN_WEIGHT, id="mit"),
        pytest.param("Llama-3-Community", ModelLicenseType.OPEN_WEIGHT_CAPPED, id="llama"),
        pytest.param("Falcon", ModelLicenseType.OPEN_WEIGHT_CAPPED, id="falcon"),
        pytest.param("OpenRAIL-M", ModelLicenseType.RAIL, id="openrail"),
        pytest.param("Gemma Terms of Use", ModelLicenseType.RAIL, id="gemma"),
        pytest.param("GPL-3.0", ModelLicenseType.OPEN_SOURCE, id="gpl"),
        pytest.param("Proprietary Commercial", ModelLicenseType.PROPRIETARY, id="proprietary"),
        pytest.param("Custom In-House", ModelLicenseType.UNKNOWN, id="custom"),
    ],
)
def test_a_license_name_falls_in_one_governance_category(
    license_name: Any, category: ModelLicenseType
) -> None:
    """Each license name maps to the category its governance terms put it in."""
    assert _classify_license(license_name)[0] == category


def test_a_model_directory_becomes_one_component(tmp_path: Path) -> None:
    """A config with a permissive license and safetensors weights gives one component."""
    components = extract_aibom_components(_qwen_workspace(tmp_path))

    assert [(c.name, c.license_type, c.has_safe_weights) for c in components] == [
        ("qwen-coder", ModelLicenseType.PERMISSIVE_OPEN_WEIGHT, True)
    ]


def test_a_modelfile_names_its_model_and_its_files_are_hashed(tmp_path: Path) -> None:
    """A Modelfile's FROM line names the component, and each model file gets a digest."""
    model_dir = tmp_path / "ollama_model"
    model_dir.mkdir()
    (model_dir / "Modelfile").write_text(
        "FROM mistral:7b\nPARAMETER temperature 0.7\n", encoding="utf-8"
    )
    (model_dir / "model_card.json").write_text('{"description": "Mistral 7B"}', encoding="utf-8")
    (model_dir / "weights.safetensors").write_bytes(b"mock_safetensors_binary_content")

    [component] = extract_aibom_components(tmp_path)

    assert (
        component.name,
        component.parameters_billion,
        component.has_safe_weights,
        "model_card.json" in component.file_digests,
    ) == ("mistral:7b", 7.0, True, True)


def test_the_aibom_document_of_a_workspace(tmp_path: Path, snapshot: SnapshotAssertion) -> None:
    """The CycloneDX document of a Hugging Face model and an Ollama model, with their licenses,
    hardware estimates and hashes."""
    _qwen_workspace(tmp_path)
    ollama_dir = tmp_path / "ollama_model"
    ollama_dir.mkdir()
    (ollama_dir / "Modelfile").write_text("FROM mistral:7b\n", encoding="utf-8")
    (ollama_dir / "weights.safetensors").write_bytes(b"mock_safetensors_binary_content")

    document = generate_aibom(tmp_path, project_name="test-repo", project_version="0.2.7")

    assert document == snapshot(matcher=_RUN_FIELDS)


def test_scan_aibom_prints_the_document(tmp_path: Path, cli: Callable[..., Any]) -> None:
    """`devops scan aibom` prints the CycloneDX document of the workspace."""
    result = cli("scan", "aibom", str(_granite_workspace(tmp_path)))

    assert (result.exit_code, "CycloneDX" in result.output, "granite-model" in result.output) == (
        0,
        True,
        True,
    )


def test_scan_aibom_writes_the_document_to_a_file(tmp_path: Path, cli: Callable[..., Any]) -> None:
    """`--output` writes the document as JSON to the file it names."""
    out_file = tmp_path / "aibom.json"

    result = cli("scan", "aibom", str(_granite_workspace(tmp_path)), "--output", str(out_file))

    assert (result.exit_code, json.loads(out_file.read_text(encoding="utf-8"))["bomFormat"]) == (
        0,
        "CycloneDX",
    )


def test_scan_aibom_refuses_an_unknown_format(tmp_path: Path, cli: Callable[..., Any]) -> None:
    """An unknown `--format` stops the command with exit status 1 and names the problem."""
    result = cli("scan", "aibom", str(_granite_workspace(tmp_path)), "--format", "unknown_fmt")

    assert (result.exit_code, "Unsupported AIBOM format" in result.output) == (1, True)


def test_scan_aibom_dry_run_succeeds(tmp_path: Path, cli: Callable[..., Any]) -> None:
    """`--dry-run` previews the command and exits 0."""
    assert cli("--dry-run", "scan", "aibom", str(_granite_workspace(tmp_path))).exit_code == 0
