"""Tests for Kubernetes context management."""

from __future__ import annotations

from typer.testing import CliRunner

from devops_cli.commands.k8s import app

runner = CliRunner()


def test_k8s_contexts_dry_run() -> None:
    result = runner.invoke(app, ["contexts"], env={"DEVOPS_CLI_DRY_RUN": "true"})
    assert result.exit_code == 0
    assert "devops k8s contexts" in result.output


def test_k8s_switch_context_dry_run() -> None:
    result = runner.invoke(app, ["switch-context", "minikube"], env={"DEVOPS_CLI_DRY_RUN": "true"})
    assert result.exit_code == 0
    assert "switch_kube_config_context" in result.output
    assert "minikube" in result.output
