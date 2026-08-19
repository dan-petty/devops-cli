"""Unit tests for Jaeger deployment manifest and k8s command integration."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

from devops_cli.main import app as main_app


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


def test_jaeger_manifest_valid() -> None:
    jaeger_manifest = Path("k8s/otel/jaeger.yaml")
    assert jaeger_manifest.exists()

    docs = list(yaml.safe_load_all(jaeger_manifest.read_text(encoding="utf-8")))
    assert len(docs) == 2

    deployment, service = docs[0], docs[1]
    assert deployment["kind"] == "Deployment"
    assert deployment["metadata"]["name"] == "jaeger"
    assert deployment["metadata"]["namespace"] == "otel"

    assert service["kind"] == "Service"
    assert service["metadata"]["name"] == "jaeger"
    assert service["metadata"]["namespace"] == "otel"


def test_k8s_port_forward_jaeger_dry_run(runner: CliRunner) -> None:
    result = runner.invoke(
        main_app,
        ["--dry-run", "k8s", "port-forward", "--stack", "infra"],
    )
    assert result.exit_code == 0
    assert "Would run delegated command: devops k8s port-forward" in result.output
