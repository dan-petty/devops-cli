"""Tests for Kubernetes GPU configuration matrix, service aliases, and CLI command."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

from devops_cli.commands.k8s import app as k8s_app
from devops_cli.k8s.gpu_matrix import (
    VALID_BACKENDS,
    VALID_GPU_COUNTS,
    VALID_VRAM_SIZES,
    get_gateway_routing_entries,
    get_gpu_profile,
    get_service_aliases,
    list_gpu_profiles,
)

runner = CliRunner()

PROFILES_DIR = Path("k8s/llm/profiles")
GATEWAY_DIR = Path("k8s/llm/gateway")


def test_gpu_matrix_entries_completeness() -> None:
    """Verify matrix contains exactly 24 valid and unique hardware profiles."""
    profiles = list_gpu_profiles()
    combos = {(p.gpu_count, p.vram_per_gpu_gib, p.backend) for p in profiles}
    vram_checks = [p.total_vram_gib == p.gpu_count * p.vram_per_gpu_gib for p in profiles]

    assert (
        len(profiles),
        len(combos),
        all(vram_checks),
        sorted(dict.fromkeys(p.gpu_count for p in profiles)),
        sorted(dict.fromkeys(p.vram_per_gpu_gib for p in profiles)),
        sorted(dict.fromkeys(p.backend for p in profiles)),
    ) == (
        24,
        24,
        True,
        list(VALID_GPU_COUNTS),
        list(VALID_VRAM_SIZES),
        list(VALID_BACKENDS),
    )


def test_gpu_profile_model_allocation_boundaries() -> None:
    """Verify sizing thresholds allocate appropriate model classes."""
    p_1_16_ollama = get_gpu_profile(1, 16, "ollama")
    p_1_16_vllm = get_gpu_profile(1, 16, "vllm")
    p_1_24_ollama = get_gpu_profile(1, 24, "ollama")
    p_1_24_vllm = get_gpu_profile(1, 24, "vllm")
    p_2_16_vllm = get_gpu_profile(2, 16, "vllm")
    p_2_24_vllm = get_gpu_profile(2, 24, "vllm")
    p_4_32_vllm = get_gpu_profile(4, 32, "vllm")

    assert (
        (p_1_16_ollama.model_id, p_1_16_ollama.quantization),
        (p_1_16_vllm.model_id, p_1_16_vllm.quantization),
        (p_1_24_ollama.model_id, p_1_24_ollama.quantization),
        (p_1_24_vllm.model_id, p_1_24_vllm.quantization),
        (p_2_16_vllm.model_id, p_2_16_vllm.tensor_parallel_size),
        (p_2_24_vllm.model_id, p_2_24_vllm.max_model_len),
        (p_4_32_vllm.model_id, p_4_32_vllm.tensor_parallel_size),
    ) == (
        ("qwen2.5-coder:7b", "Q4_K_M"),
        ("qwen2.5-coder-14b-instruct", "AWQ"),
        ("qwen2.5-coder:14b", "Q8_0"),
        ("qwen2.5-coder-14b-instruct", "AWQ"),
        ("qwen3-coder:30b", 2),
        ("qwen3-coder:30b", 65536),
        ("deepseek-r1:70b", 4),
    )


def test_gpu_profile_query_filtering() -> None:
    """Verify list_gpu_profiles correctly applies count, vram, and backend filters."""
    two_gpu = list_gpu_profiles(gpu_count=2)
    vram_24 = list_gpu_profiles(vram_per_gpu_gib=24)
    vllm_only = list_gpu_profiles(backend="vllm")
    exact = list_gpu_profiles(gpu_count=1, vram_per_gpu_gib=16, backend="ollama")

    assert (
        len(two_gpu),
        len(vram_24),
        len(vllm_only),
        len(exact),
        exact[0].model_id,
    ) == (
        6,
        8,
        12,
        1,
        "qwen2.5-coder:7b",
    )


def test_gpu_profile_invalid_combination_raises() -> None:
    """Verify get_gpu_profile raises ValueError for unsupported configuration."""
    with pytest.raises(ValueError, match="Unsupported GPU configuration: 8x64GiB"):
        get_gpu_profile(8, 64, "vllm")  # type: ignore[arg-type]


def test_service_aliases_definition_and_ports() -> None:
    """Verify service aliases define expected provider classes and ports."""
    aliases = get_service_aliases()
    keys = sorted(aliases.keys())

    assert (
        len(keys),
        "ollama-16gib" in aliases,
        "vllm-48gib" in aliases,
        aliases["ollama-16gib"]["ports"]["ollama"],
        aliases["vllm-48gib"]["ports"]["vllm"],
    ) == (
        16,
        True,
        True,
        11434,
        8000,
    )


def test_gateway_routing_entries_generation() -> None:
    """Verify LiteLLM routing entries match k8s gateway configmap model list."""
    entries = get_gateway_routing_entries()
    unique_models = list(dict.fromkeys(e["model_name"] for e in entries))
    api_bases = [e["litellm_params"]["api_base"] for e in entries]

    cm_path = GATEWAY_DIR / "configmap.yaml"
    cm_docs = list(yaml.safe_load_all(cm_path.read_text(encoding="utf-8")))
    cm = next(d for d in cm_docs if d and d.get("kind") == "ConfigMap")
    cm_model_list = yaml.safe_load(cm["data"]["config.yaml"])["model_list"]

    assert (
        len(entries),
        unique_models,
        all(".llm.svc.cluster.local" in base for base in api_bases),
        entries == cm_model_list,
    ) == (
        19,
        [
            "devops-chat",
            "devops-coder",
            "devops-reasoning",
            "bge-m3:latest",
            "devops-background",
            "devops-review",
            "qwen3-coder:30b",
            "gpt-oss:20b",
            "gemma4:31b",
            "qwen3.8:27b",
            "deepseek-r1:70b",
        ],
        True,
        True,
    )


def test_k8s_manifests_service_aliases_consistency() -> None:
    """Verify profiles/services.yaml defines all 8 Ollama Service aliases with expected labels."""
    services_path = PROFILES_DIR / "services.yaml"
    docs = list(yaml.safe_load_all(services_path.read_text(encoding="utf-8")))
    services = [d for d in docs if d and d.get("kind") == "Service"]
    names = [s["metadata"]["name"] for s in services]
    ollama_16 = next(s for s in services if s["metadata"]["name"] == "ollama-16gib")

    assert (
        len(services),
        "ollama-16gib" in names,
        "ollama-fast" in names,
        "ollama-standard" in names,
        "ollama-slow" in names,
        "ollama-16gib-fast" in names,
        "ollama-24gib-slow" in names,
        "ollama-48gib-fast" in names,
        "ollama-48gib-slow" in names,
        "ollama-64gib-standard" in names,
        ollama_16["spec"]["selector"],
    ) == (
        16,
        True,
        True,
        True,
        True,
        True,
        True,
        True,
        True,
        True,
        {"llm.devops.io/provider": "ollama", "llm.devops.io/vram-gib": "16gib"},
    )


def test_k8s_manifests_profiles_files_exist() -> None:
    """Verify profile manifest files and kustomization exist and are valid."""
    ollama_path = PROFILES_DIR / "ollama-profiles.yaml"
    kust_path = PROFILES_DIR / "kustomization.yaml"

    ollama_docs = list(yaml.safe_load_all(ollama_path.read_text(encoding="utf-8")))
    kust = yaml.safe_load(kust_path.read_text(encoding="utf-8"))

    assert (
        len(ollama_docs) == 9,
        "services.yaml" in kust.get("resources", []),
    ) == (
        True,
        True,
    )


def test_cli_gpu_matrix_table_output() -> None:
    """Verify CLI devops k8s gpu-matrix outputs structured table by default."""
    result = runner.invoke(k8s_app, ["gpu-matrix"])

    assert (
        result.exit_code,
        "Homelab GPU Inference Matrix" in result.output,
        "qwen2.5-coder:7b" in result.output,
        "qwen3-coder:30b" in result.output,
        "deepseek-r1:70b" in result.output,
    ) == (
        0,
        True,
        True,
        True,
        True,
    )


def test_cli_gpu_matrix_json_filter() -> None:
    """Verify CLI devops k8s gpu-matrix --format json with hardware filters."""
    result = runner.invoke(
        k8s_app,
        ["gpu-matrix", "--gpus", "2", "--vram", "24", "--backend", "vllm", "--format", "json"],
    )

    data = json.loads(result.output)
    profile = data[0]

    assert (
        result.exit_code,
        len(data),
        profile["gpu_count"],
        profile["vram_per_gpu_gib"],
        profile["backend"],
        profile["model_id"],
        profile["tensor_parallel_size"],
    ) == (
        0,
        1,
        2,
        24,
        "vllm",
        "qwen3-coder:30b",
        2,
    )


def test_cli_gpu_matrix_yaml_and_aliases() -> None:
    """Verify CLI devops k8s gpu-matrix --format yaml --aliases outputs both sections."""
    result = runner.invoke(k8s_app, ["gpu-matrix", "--gpus", "1", "--format", "yaml", "--aliases"])

    data = yaml.safe_load(result.output)

    assert (
        result.exit_code,
        "profiles" in data,
        "service_aliases" in data,
        len(data["profiles"]),
        "ollama-16gib" in data["service_aliases"]["ollama-16gib"]["service_name"],
    ) == (
        0,
        True,
        True,
        6,
        True,
    )


def test_cli_gpu_matrix_invalid_filter_options() -> None:
    """Verify CLI rejects invalid filter options with exit code 1."""
    res_gpu = runner.invoke(k8s_app, ["gpu-matrix", "--gpus", "99"])
    res_vram = runner.invoke(k8s_app, ["gpu-matrix", "--vram", "99"])
    res_backend = runner.invoke(k8s_app, ["gpu-matrix", "--backend", "invalid"])

    assert (
        res_gpu.exit_code,
        "Invalid --gpus" in res_gpu.output,
        res_vram.exit_code,
        "Invalid --vram" in res_vram.output,
        res_backend.exit_code,
        "Invalid --backend" in res_backend.output,
    ) == (
        1,
        True,
        1,
        True,
        1,
        True,
    )
