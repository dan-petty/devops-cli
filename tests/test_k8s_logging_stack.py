"""Unit tests for Kubernetes logging stack lifecycle, manifests, and CLI integration."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from devops_cli.commands.k8s import app
from devops_cli.commands.k8s.stack_lifecycle import (
    _HELM_RELEASES_BY_STACK,
    _HELM_REPOS_BY_STACK,
    _MANIFESTS_BY_STACK,
    VALID_STACKS,
)

runner = CliRunner()


def test_logging_stack_definitions() -> None:
    """Verify logging stack is registered in Helm repos, releases, and manifests."""
    assert "logging" in VALID_STACKS
    assert "logging" in _HELM_REPOS_BY_STACK
    assert "grafana" in _HELM_REPOS_BY_STACK["logging"]
    assert "fluent" in _HELM_REPOS_BY_STACK["logging"]

    assert "logging" in _HELM_RELEASES_BY_STACK
    release_names = [r["name"] for r in _HELM_RELEASES_BY_STACK["logging"]]
    assert "loki" in release_names
    assert "fluent-bit" in release_names

    assert "logging" in _MANIFESTS_BY_STACK
    manifest_paths = [str(p) for p in _MANIFESTS_BY_STACK["logging"]]
    assert any("networkpolicy.yaml" in p for p in manifest_paths)


def test_deploy_logging_stack_dry_run() -> None:
    """Verify deploy-stack --stack logging with dry run."""
    with patch("devops_cli.commands.k8s.stack_lifecycle.is_dry_run", return_value=True):
        result = runner.invoke(app, ["deploy-stack", "--stack", "logging"])
        assert result.exit_code == 0
        assert "deploy-stack" in result.output
        assert "logging" in result.output


def test_teardown_logging_stack_dry_run() -> None:
    """Verify teardown-stack --stack logging with dry run."""
    with patch("devops_cli.commands.k8s.stack_lifecycle.is_dry_run", return_value=True):
        result = runner.invoke(app, ["teardown-stack", "--stack", "logging"])
        assert result.exit_code == 0
        assert "teardown-stack" in result.output
        assert "logging" in result.output


def test_deploy_logging_stack_live() -> None:
    """Verify deploy-stack --stack logging execution."""
    mock_proc = MagicMock(returncode=0, stdout="success", stderr="")
    with (
        patch("devops_cli.commands.k8s.shutil.which", return_value="/usr/local/bin/helm"),
        patch("devops_cli.commands.k8s._cluster_reachable", return_value=True),
        patch("devops_cli.commands.k8s._minikube_running", return_value=True),
        patch("devops_cli.commands.k8s.run_subprocess", return_value=mock_proc),
        patch("devops_cli.commands.k8s._run_cmd", return_value=mock_proc),
    ):
        result = runner.invoke(app, ["deploy-stack", "--stack", "logging"])
        assert result.exit_code == 0


def test_teardown_logging_stack_live() -> None:
    """Verify teardown-stack --stack logging execution."""
    mock_proc = MagicMock(returncode=0, stdout="success", stderr="")
    with (
        patch("devops_cli.commands.k8s.shutil.which", return_value="/usr/local/bin/helm"),
        patch("devops_cli.commands.k8s._cluster_reachable", return_value=True),
        patch("devops_cli.commands.k8s._minikube_running", return_value=True),
        patch("devops_cli.commands.k8s.run_subprocess", return_value=mock_proc),
        patch("devops_cli.commands.k8s._run_cmd", return_value=mock_proc),
    ):
        result = runner.invoke(app, ["teardown-stack", "--stack", "logging"])
        assert result.exit_code == 0


def test_k8s_logs_backward_compatibility() -> None:
    """Verify devops k8s logs <pod> continues to work as expected."""
    mock_proc = MagicMock(returncode=0, stdout="pod logs output", stderr="")
    with patch("devops_cli.commands.k8s._run_cmd", return_value=mock_proc) as mock_run:
        result = runner.invoke(app, ["logs", "my-legacy-pod", "-n", "default", "--tail", "25"])
        assert result.exit_code == 0
        mock_run.assert_called_once()


def test_k8s_logs_logql_query_dispatch() -> None:
    """Verify devops k8s logs '{app=\"foo\"}' routes to LogQL query engine."""
    with patch("devops_cli.k8s.logql.execute_logql_query") as mock_query:
        mock_query.return_value = MagicMock(
            source="mock",
            entries=[],
            duration_ms=5.0,
        )
        result = runner.invoke(
            app,
            ["logs", '{app="frontend"} |= "error"', "--since", "30m", "--limit", "20"],
        )
        assert result.exit_code == 0
        mock_query.assert_called_once()


def test_k8s_logs_subcommand_query_dispatch() -> None:
    """Verify devops k8s logs query '{app=\"foo\"}' routes to LogQL query engine."""
    with patch("devops_cli.k8s.logql.execute_logql_query") as mock_query:
        mock_query.return_value = MagicMock(
            source="mock",
            entries=[],
            duration_ms=5.0,
        )
        result = runner.invoke(
            app,
            ["logs", "query", '{app="backend"}', "--limit", "10"],
        )
        assert result.exit_code == 0
        mock_query.assert_called_once()
