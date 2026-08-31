"""Unit tests for Jaeger deployment manifest and k8s command integration."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner


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
    pod_spec = deployment["spec"]["template"]["spec"]
    assert pod_spec["automountServiceAccountToken"] is False
    assert pod_spec["securityContext"]["seccompProfile"]["type"] == "RuntimeDefault"
    assert any(v["name"] == "tmp" for v in pod_spec.get("volumes", []))

    assert service["kind"] == "Service"
    assert service["metadata"]["name"] == "jaeger"
    assert service["metadata"]["namespace"] == "otel"
    assert service["spec"]["type"] == "ClusterIP"


def test_k8s_port_forward_jaeger_dry_run(runner: CliRunner) -> None:
    from devops_cli.dry_run import set_dry_run

    set_dry_run(True)
    try:
        from devops_cli.commands.k8s import app as k8s_app

        result = runner.invoke(
            k8s_app,
            ["port-forward", "--stack", "infra"],
        )
        assert result.exit_code == 0
        assert "jaeger.url" in result.output
        assert "16686" in result.output
    finally:
        set_dry_run(False)


def test_k8s_configure_urls_jaeger_dry_run(runner: CliRunner) -> None:
    from devops_cli.dry_run import set_dry_run

    set_dry_run(True)
    try:
        from devops_cli.commands.k8s import app as k8s_app

        result = runner.invoke(
            k8s_app,
            ["configure-urls", "--stack", "infra"],
        )
        assert result.exit_code == 0
        assert "jaeger.url" in result.output
    finally:
        set_dry_run(False)


def test_k8s_deploy_stack_shows_jaeger_connection_info(runner: CliRunner) -> None:
    from unittest.mock import MagicMock, patch

    from devops_cli.commands.k8s import app as k8s_app
    from devops_cli.dry_run import set_dry_run

    set_dry_run(False)
    with (
        patch("devops_cli.commands.k8s._cluster_reachable", return_value=True),
        patch("devops_cli.commands.k8s._run_cmd") as mock_run,
        patch("devops_cli.commands.k8s.port_forward"),
    ):
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.stdout = ""
        mock_proc.stderr = ""
        mock_run.return_value = mock_proc

        result = runner.invoke(k8s_app, ["deploy-stack", "--stack", "infra"])
        assert result.exit_code == 0
        assert "Jaeger Query UI: http://localhost:16686 (namespace: otel)" in result.output
        assert "Jaeger OTLP Traces: localhost:4317 (gRPC) / localhost:4318 (HTTP)" in result.output
