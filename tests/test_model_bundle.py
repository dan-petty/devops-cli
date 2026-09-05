"""Tests for air-gapped model bundling."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from devops_cli import __version__
from devops_cli.ai.model_bundler import bundle_ollama_models


def test_bundle_ollama_models(tmp_path: Path) -> None:
    output_dir = tmp_path / "models"
    count, manifest_path = bundle_ollama_models(models=["qwen2.5-coder:7b"], output_dir=output_dir)

    assert count == 1
    assert manifest_path.exists()

    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert data["models"] == ["qwen2.5-coder:7b"]
    assert data["version"] == __version__


def test_model_bundler_validates_output_directory(tmp_path: Path) -> None:
    # Traversal outside root directory is rejected
    with pytest.raises(ValueError, match="traversal|outside|invalid"):
        bundle_ollama_models(output_dir=Path("/../../etc"))
