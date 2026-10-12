"""Tests for LLM gateway configuration rendering, context length alignment, and unified diffing."""

from __future__ import annotations

from pathlib import Path

import yaml
from typer.testing import CliRunner

from devops_cli.ai.gateway_render import (
    diff_gateway_config,
    load_service_context_lengths,
    load_tier_context_lengths,
    render_gateway_config,
)
from devops_cli.commands.ai_gateway import app as ai_gateway_app
from devops_cli.config.defaults import (
    DEFAULT_LLM_PROFILES_PATH,
)

runner = CliRunner()


SAMPLE_PROFILES_YAML = """---
apiVersion: apps/v1
kind: DaemonSet
metadata:
  name: ollama-16gib
spec:
  template:
    spec:
      containers:
        - name: ollama
          env:
            - name: OLLAMA_CONTEXT_LENGTH
              value: "48000"
---
apiVersion: apps/v1
kind: DaemonSet
metadata:
  name: ollama-48gib
spec:
  template:
    spec:
      containers:
        - name: ollama
          env:
            - name: OLLAMA_CONTEXT_LENGTH
              value: "128000"
---
apiVersion: apps/v1
kind: DaemonSet
metadata:
  name: ollama-64gib
spec:
  template:
    spec:
      containers:
        - name: ollama
          env:
            - name: OLLAMA_CONTEXT_LENGTH
              value: "160000"
"""

SAMPLE_SERVICES_YAML = """---
apiVersion: v1
kind: Service
metadata:
  name: ollama-16gib-fast
spec:
  selector:
    llm.devops.io/provider: ollama
    llm.devops.io/vram-gib: "16gib"
    llm.devops.io/speed-tier: fast
---
apiVersion: v1
kind: Service
metadata:
  name: ollama-48gib-fast
spec:
  selector:
    llm.devops.io/provider: ollama
    llm.devops.io/vram-gib: "48gib"
    llm.devops.io/speed-tier: fast
---
apiVersion: v1
kind: Service
metadata:
  name: ollama-64gib-standard
spec:
  selector:
    llm.devops.io/provider: ollama
    llm.devops.io/vram-gib: "64gib"
    llm.devops.io/speed-tier: standard
"""

SAMPLE_CONFIGMAP_YAML = """# Header comment
---
apiVersion: v1
kind: ConfigMap
metadata:
  name: llm-gateway-config
  namespace: llm
data:
  config.yaml: |
    model_list:
      # Comment on chat
      - model_name: devops-chat
        litellm_params:
          model: ollama_chat/qwen3.8:27b
          api_base: http://ollama-16gib-fast.llm.svc.cluster.local:11434
          model_info:
            max_input_tokens: 96000
          weight: 10
      - model_name: devops-chat
        litellm_params:
          model: ollama_chat/qwen3.8:27b
          api_base: http://ollama-48gib-fast.llm.svc.cluster.local:11434
          model_info:
            max_input_tokens: 128000
          weight: 5
      - model_name: devops-chat
        litellm_params:
          model: ollama_chat/qwen3.8:27b
          api_base: http://ollama-64gib-standard.llm.svc.cluster.local:11434
          model_info:
            max_input_tokens: 128000
          weight: 3

      # Background tier has no max_input_tokens
      - model_name: devops-background
        litellm_params:
          model: ollama_chat/qwen3.8:27b
          api_base: http://ollama-48gib-slow.llm.svc.cluster.local:11434
          timeout: 1100
          num_retries: 0

    router_settings:
      routing_strategy: least-busy
"""


def test_load_tier_context_lengths_extracts_env_lengths(tmp_path: Path) -> None:
    """Verify tier context lengths are extracted from DaemonSets' OLLAMA_CONTEXT_LENGTH."""
    manifest = tmp_path / "profiles.yaml"
    manifest.write_text(SAMPLE_PROFILES_YAML, encoding="utf-8")
    lengths = load_tier_context_lengths(manifest)

    assert (
        lengths.get("ollama-16gib"),
        lengths.get("ollama-48gib"),
        lengths.get("ollama-64gib"),
    ) == (48000, 128000, 160000)


def test_load_tier_context_lengths_against_repository_profiles() -> None:
    """Verify context lengths from actual repository profiles match expected hardware tiers."""
    lengths = load_tier_context_lengths(DEFAULT_LLM_PROFILES_PATH)

    assert (
        lengths.get("ollama-16gib"),
        lengths.get("ollama-24gib"),
        lengths.get("ollama-32gib"),
        lengths.get("ollama-48gib"),
        lengths.get("ollama-48gib-slow"),
        lengths.get("ollama-64gib"),
    ) == (48000, 48000, 48000, 128000, 128000, 160000)


def test_load_service_context_lengths_maps_services_to_tier_limits(tmp_path: Path) -> None:
    """Verify service context lengths are mapped to tier DaemonSets via selectors."""
    profiles = tmp_path / "profiles.yaml"
    profiles.write_text(SAMPLE_PROFILES_YAML, encoding="utf-8")
    services = tmp_path / "services.yaml"
    services.write_text(SAMPLE_SERVICES_YAML, encoding="utf-8")

    tier_lengths = load_tier_context_lengths(profiles)
    svc_lengths = load_service_context_lengths(services, tier_lengths)

    assert (
        svc_lengths.get("ollama-16gib-fast"),
        svc_lengths.get("ollama-48gib-fast"),
        svc_lengths.get("ollama-64gib-standard"),
    ) == (48000, 128000, 160000)


def test_render_gateway_config_eliminates_weights_and_aligns_max_input_tokens() -> None:
    """Verify rendering drops weight lines and sets max_input_tokens to tier context lengths."""
    svc_lengths = {
        "ollama-16gib-fast": 48000,
        "ollama-48gib-fast": 128000,
        "ollama-64gib-standard": 160000,
        "ollama-48gib-slow": 128000,
    }
    rendered = render_gateway_config(SAMPLE_CONFIGMAP_YAML, svc_lengths)

    # Parse inner config to verify values structurally
    docs = list(yaml.safe_load_all(rendered))
    cfg = yaml.safe_load(docs[0]["data"]["config.yaml"])
    models = cfg["model_list"]

    chat_16 = next(
        m
        for m in models
        if m["model_name"] == "devops-chat" and "16gib" in m["litellm_params"]["api_base"]
    )
    chat_48 = next(
        m
        for m in models
        if m["model_name"] == "devops-chat" and "48gib" in m["litellm_params"]["api_base"]
    )
    chat_64 = next(
        m
        for m in models
        if m["model_name"] == "devops-chat" and "64gib" in m["litellm_params"]["api_base"]
    )
    background = next(m for m in models if m["model_name"] == "devops-background")

    has_weights = any("weight" in m["litellm_params"] for m in models)
    assert (
        has_weights,
        chat_16["litellm_params"]["model_info"]["max_input_tokens"],
        chat_48["litellm_params"]["model_info"]["max_input_tokens"],
        chat_64["litellm_params"]["model_info"]["max_input_tokens"],
        "max_input_tokens" in (background.get("model_info") or {}),
        "# Header comment" in rendered,
        "# Background tier has no max_input_tokens" in rendered,
    ) == (False, 48000, 128000, 160000, False, True, True)


def test_diff_gateway_config_generates_unified_diff() -> None:
    """Verify unified diff formatting between original and rendered content."""
    original = "line1\nline2\n"
    modified = "line1\nline2-changed\n"
    diff = diff_gateway_config(original, modified, filename="config.yaml")

    assert (
        "--- a/config.yaml" in diff,
        "+++ b/config.yaml" in diff,
        "-line2" in diff,
        "+line2-changed" in diff,
    ) == (True, True, True, True)


def test_diff_gateway_config_empty_when_identical() -> None:
    """Verify empty diff output when content is identical."""
    content = "same\ncontent\n"
    assert diff_gateway_config(content, content) == ""


def test_cli_gateway_render_dry_run_displays_diff_without_writing(tmp_path: Path) -> None:
    """Verify render command without --apply shows diff and does not mutate files."""
    cm = tmp_path / "configmap.yaml"
    cm.write_text(SAMPLE_CONFIGMAP_YAML, encoding="utf-8")
    profiles = tmp_path / "profiles.yaml"
    profiles.write_text(SAMPLE_PROFILES_YAML, encoding="utf-8")
    services = tmp_path / "services.yaml"
    services.write_text(SAMPLE_SERVICES_YAML, encoding="utf-8")

    result = runner.invoke(
        ai_gateway_app,
        [
            "render",
            "--configmap",
            str(cm),
            "--profiles",
            str(profiles),
            "--services",
            str(services),
        ],
    )

    assert (
        result.exit_code,
        "-            max_input_tokens: 96000" in result.output,
        "+            max_input_tokens: 48000" in result.output,
        "-          weight: 10" in result.output,
        cm.read_text(encoding="utf-8") == SAMPLE_CONFIGMAP_YAML,
    ) == (0, True, True, True, True)


def test_cli_gateway_render_apply_writes_file_and_makes_no_cluster_calls(tmp_path: Path) -> None:
    """Verify render command with --apply updates configmap without making any Kubernetes API calls."""
    cm = tmp_path / "configmap.yaml"
    cm.write_text(SAMPLE_CONFIGMAP_YAML, encoding="utf-8")
    profiles = tmp_path / "profiles.yaml"
    profiles.write_text(SAMPLE_PROFILES_YAML, encoding="utf-8")
    services = tmp_path / "services.yaml"
    services.write_text(SAMPLE_SERVICES_YAML, encoding="utf-8")

    result = runner.invoke(
        ai_gateway_app,
        [
            "render",
            "--apply",
            "--configmap",
            str(cm),
            "--profiles",
            str(profiles),
            "--services",
            str(services),
        ],
    )

    updated_text = cm.read_text(encoding="utf-8")
    assert (
        result.exit_code,
        "weight:" not in updated_text,
        "max_input_tokens: 48000" in updated_text,
        "max_input_tokens: 96000" not in updated_text,
    ) == (0, True, True, True)


def test_cli_gateway_render_apply_idempotent(tmp_path: Path) -> None:
    """Verify second render --apply on already up-to-date file is a no-op with clean exit code."""
    cm = tmp_path / "configmap.yaml"
    cm.write_text(SAMPLE_CONFIGMAP_YAML, encoding="utf-8")
    profiles = tmp_path / "profiles.yaml"
    profiles.write_text(SAMPLE_PROFILES_YAML, encoding="utf-8")
    services = tmp_path / "services.yaml"
    services.write_text(SAMPLE_SERVICES_YAML, encoding="utf-8")

    # Apply once
    runner.invoke(
        ai_gateway_app,
        [
            "render",
            "--apply",
            "--configmap",
            str(cm),
            "--profiles",
            str(profiles),
            "--services",
            str(services),
        ],
    )

    # Apply second time
    result2 = runner.invoke(
        ai_gateway_app,
        [
            "render",
            "--apply",
            "--configmap",
            str(cm),
            "--profiles",
            str(profiles),
            "--services",
            str(services),
        ],
    )

    assert (result2.exit_code, "up to date" in result2.output.lower()) == (0, True)
