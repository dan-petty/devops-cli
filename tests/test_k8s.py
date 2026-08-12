"""Unit tests for Kubernetes CLI commands (devops_cli.commands.k8s)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from devops_cli.commands.k8s import app
from devops_cli.core.dry_run import set_dry_run

runner = CliRunner()


def test_k8s_contexts_dry_run() -> None:
    """k8s contexts with dry-run active must print dry-run Pydantic model notice."""
    set_dry_run(True)
    try:
        result = runner.invoke(app, ["contexts"])
        assert result.exit_code == 0
        assert "devops k8s contexts" in result.output
    finally:
        set_dry_run(False)


def test_k8s_status_dry_run() -> None:
    """k8s status with dry-run active must print dry-run Pydantic model notice."""
    set_dry_run(True)
    try:
        result = runner.invoke(app, ["status"])
        assert result.exit_code == 0
        assert "devops k8s status" in result.output
    finally:
        set_dry_run(False)


def test_k8s_bootstrap_dry_run() -> None:
    """k8s bootstrap with dry-run active must print dry-run Pydantic model notice."""
    set_dry_run(True)
    try:
        result = runner.invoke(app, ["bootstrap"])
        assert result.exit_code == 0
        assert "devops k8s bootstrap" in result.output
    finally:
        set_dry_run(False)


def test_k8s_deploy_stack_dry_run() -> None:
    """k8s deploy-stack with dry-run active must print dry-run Pydantic model notice."""
    set_dry_run(True)
    try:
        result = runner.invoke(app, ["deploy-stack"])
        assert result.exit_code == 0
        assert "devops k8s deploy-stack" in result.output
    finally:
        set_dry_run(False)


def test_k8s_teardown_stack_dry_run() -> None:
    """k8s teardown-stack with dry-run active must print dry-run Pydantic model notice."""
    set_dry_run(True)
    try:
        result = runner.invoke(app, ["teardown-stack"])
        assert result.exit_code == 0
        assert "devops k8s teardown-stack" in result.output
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


def test_k8s_configure_urls_dry_run() -> None:
    """k8s configure-urls with dry-run active must print dry-run notice."""
    set_dry_run(True)
    try:
        result = runner.invoke(app, ["configure-urls"])
        assert result.exit_code == 0
        assert "devops k8s configure-urls" in result.output
    finally:
        set_dry_run(False)


@patch("devops_cli.commands.k8s._detect_service_url")
@patch("devops_cli.commands.k8s._minikube_running", return_value=True)
def test_k8s_configure_urls_success(
    mock_running: MagicMock,
    mock_detect: MagicMock,
) -> None:
    """k8s configure-urls must query service URLs and update configuration."""

    def fake_detect(service: str, ns: str) -> str | None:
        return f"http://192.168.49.2:{30000 + len(service)}"

    mock_detect.side_effect = fake_detect
    result = runner.invoke(app, ["configure-urls"])
    assert result.exit_code == 0
    assert "Configured Monitoring Service Targets" in result.output


@patch("devops_cli.commands.k8s._verify_url_reachability")
def test_resolve_accessible_url_fallback(mock_verify: MagicMock) -> None:
    """_resolve_accessible_url falls back to localhost when minikube IP is unreachable."""
    from devops_cli.commands.k8s import _resolve_accessible_url

    def fake_verify(url: str, timeout: float = 0.8) -> bool:
        return "localhost" in url

    mock_verify.side_effect = fake_verify
    res = _resolve_accessible_url("http://192.168.49.2:30080")
    assert res == "http://localhost:30080"
