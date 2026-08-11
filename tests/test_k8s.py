"""Unit tests for Kubernetes CLI commands (devops_cli.commands.k8s)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from devops_cli.commands.k8s import app
from devops_cli.core.dry_run import set_dry_run

runner = CliRunner()


def test_k8s_contexts_dry_run() -> None:
    """k8s contexts with dry-run active must print dry-run notice."""
    set_dry_run(True)
    try:
        result = runner.invoke(app, ["contexts"])
        assert result.exit_code == 0
        assert "Would list Kubernetes contexts" in result.output
    finally:
        set_dry_run(False)


def test_k8s_status_dry_run() -> None:
    """k8s status with dry-run active must print dry-run notice."""
    set_dry_run(True)
    try:
        result = runner.invoke(app, ["status"])
        assert result.exit_code == 0
        assert "Would query Kubernetes node and pod status" in result.output
    finally:
        set_dry_run(False)


def test_k8s_bootstrap_dry_run() -> None:
    """k8s bootstrap with dry-run active must print dry-run notice."""
    set_dry_run(True)
    try:
        result = runner.invoke(app, ["bootstrap"])
        assert result.exit_code == 0
        assert "Would bootstrap minikube Kubernetes cluster" in result.output
    finally:
        set_dry_run(False)


def test_k8s_deploy_stack_dry_run() -> None:
    """k8s deploy-stack with dry-run active must print dry-run notice."""
    set_dry_run(True)
    try:
        result = runner.invoke(app, ["deploy-stack"])
        assert result.exit_code == 0
        assert "Would deploy k8s infrastructure stack" in result.output
    finally:
        set_dry_run(False)


def test_k8s_teardown_stack_dry_run() -> None:
    """k8s teardown-stack with dry-run active must print dry-run notice."""
    set_dry_run(True)
    try:
        result = runner.invoke(app, ["teardown-stack"])
        assert result.exit_code == 0
        assert "Would teardown k8s infrastructure stack" in result.output
    finally:
        set_dry_run(False)


@patch("devops_cli.commands.k8s._minikube_running", return_value=False)
def test_k8s_bootstrap_fails_when_minikube_stopped_and_no_auto_start(
    mock_running: MagicMock,
) -> None:
    """k8s bootstrap --no-auto-start must fail when minikube is not running."""
    result = runner.invoke(app, ["bootstrap", "--no-auto-start"])
    assert result.exit_code == 1
    assert "minikube is not running" in result.output
