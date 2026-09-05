"""Tests for Kubernetes context management."""

from __future__ import annotations

from pathlib import Path

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


def test_k8s_bootstrap_auto_start_failure() -> None:
    from unittest.mock import MagicMock, patch

    with (
        patch("devops_cli.commands.k8s._minikube_running", return_value=False),
        patch("shutil.which", return_value=None),
        patch(
            "devops_cli.commands.k8s._run_cmd",
            return_value=MagicMock(returncode=1, stdout="", stderr="error"),
        ),
    ):
        result = runner.invoke(app, ["bootstrap", "--auto-start"])
        assert result.exit_code == 1
        assert "Failed to start minikube" in result.output


def test_k8s_bootstrap_no_auto_start() -> None:
    from unittest.mock import patch

    with patch("devops_cli.commands.k8s._minikube_running", return_value=False):
        result = runner.invoke(app, ["bootstrap", "--no-auto-start"])
        assert result.exit_code == 1
        assert "minikube is not running" in result.output.lower()


def test_k8s_bootstrap_success(tmp_path: Path) -> None:
    from unittest.mock import patch

    manifest_dir = tmp_path / "k8s"
    manifest_dir.mkdir()

    with (
        patch("devops_cli.commands.k8s._minikube_running", return_value=True),
        patch("devops_cli.commands.k8s._run_cmd"),
        patch("devops_cli.commands.k8s.deploy_stack") as mock_deploy,
    ):
        result = runner.invoke(app, ["bootstrap", "--dir", str(manifest_dir), "--stack", "infra"])
        assert result.exit_code == 0
        assert mock_deploy.called


def test_k8s_apply_rejects_ssrf_and_private_metadata_urls() -> None:
    import pytest
    import typer

    from devops_cli.commands.k8s.cluster_context import apply

    with pytest.raises((ValueError, typer.Exit)):
        apply("http://169.254.169.254/latest/meta-data/")

    with pytest.raises((ValueError, typer.Exit)):
        apply("http://127.0.0.1:8080/manifest.yaml")


def test_k8s_apply_rejects_path_traversal() -> None:
    import pytest
    import typer

    from devops_cli.commands.k8s.cluster_context import apply

    with pytest.raises((ValueError, typer.Exit)):
        apply("../../sensitive/secret.yaml")
