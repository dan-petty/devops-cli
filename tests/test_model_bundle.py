"""Tests for air-gapped model bundling."""

from __future__ import annotations

import json
from pathlib import Path

from devops_cli.ai.bundle import bundle_ollama_models


def test_bundle_ollama_models(tmp_path: Path) -> None:
    output_dir = tmp_path / "models"
    count, manifest_path = bundle_ollama_models(models=["qwen2.5-coder:7b"], output_dir=output_dir)

    assert count == 1
    assert manifest_path.exists()

    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert data["models"] == ["qwen2.5-coder:7b"]
    assert data["version"] == "0.1.4"
