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
@patch("devops_cli.commands.k8s._cluster_reachable", return_value=True)
@patch("devops_cli.commands.k8s._minikube_running", return_value=True)
def test_k8s_configure_urls_success(
    mock_running: MagicMock,
    mock_cluster: MagicMock,
    mock_detect: MagicMock,
) -> None:
    """k8s configure-urls must query service URLs and update configuration."""

    def fake_detect(service: str, ns: str, context: str | None = None) -> str | None:
        return f"http://192.168.49.2:{30000 + len(service)}"

    set_dry_run(False)
    mock_detect.side_effect = fake_detect
    result = runner.invoke(app, ["configure-urls"])
    assert result.exit_code == 0
    assert "Configured Service Targets" in result.output


@patch("devops_cli.commands.k8s._cluster_reachable", return_value=False)
def test_k8s_deploy_stack_fails_when_cluster_unreachable(
    mock_cluster: MagicMock,
) -> None:
    """k8s deploy-stack must fail gracefully when cluster is unreachable."""
    set_dry_run(False)
    result = runner.invoke(app, ["deploy-stack", "--context", "homelab-k3s"])
    assert result.exit_code == 1
    assert "Kubernetes cluster is not reachable" in result.output


@patch("devops_cli.commands.k8s._verify_url_reachability")
def test_resolve_accessible_url_fallback(mock_verify: MagicMock) -> None:
    """_resolve_accessible_url falls back to localhost when minikube IP is unreachable."""
    from devops_cli.commands.k8s import _resolve_accessible_url

    def fake_verify(url: str, timeout: float = 0.8) -> bool:
        return "localhost" in url

    mock_verify.side_effect = fake_verify
    res = _resolve_accessible_url("http://192.168.49.2:30080")
    assert res == "http://localhost:30080"


def test_k8s_deploy_stack_llm_dry_run() -> None:
    """k8s deploy-stack --stack llm must include Ollama, Open-WebUI, Qdrant, and Valkey."""
    set_dry_run(True)
    try:
        result = runner.invoke(app, ["deploy-stack", "--stack", "llm"])
        assert result.exit_code == 0
        assert "ollama" in result.output
        assert "open-webui" in result.output
        assert "qdrant" in result.output
        assert "valkey.yaml" in result.output
    finally:
        set_dry_run(False)


def test_k8s_deploy_stack_all_dry_run() -> None:
    """k8s deploy-stack --stack all must include both infra and llm components."""
    set_dry_run(True)
    try:
        result = runner.invoke(app, ["deploy-stack", "--stack", "all"])
        assert result.exit_code == 0
        assert "argocd" in result.output
        assert "kube-prometheus" in result.output
        assert "ollama" in result.output
        assert "valkey.yaml" in result.output
    finally:
        set_dry_run(False)


def test_k8s_teardown_stack_llm_dry_run() -> None:
    """k8s teardown-stack --stack llm must include LLM uninstalls and deletions."""
    set_dry_run(True)
    try:
        result = runner.invoke(app, ["teardown-stack", "--stack", "llm"])
        assert result.exit_code == 0
        assert "ollama" in result.output
        assert "valkey.yaml" in result.output
    finally:
        set_dry_run(False)


def test_k8s_deploy_stack_invalid_stack() -> None:
    """k8s deploy-stack with invalid stack option must exit code 1."""
    set_dry_run(True)
    try:
        result = runner.invoke(app, ["deploy-stack", "--stack", "unknown-stack"])
        assert result.exit_code == 1
        assert "Invalid stack" in result.output
    finally:
        set_dry_run(False)


def test_k8s_port_forward_llm_dry_run() -> None:
    """k8s port-forward --stack llm must print LLM port forward targets."""
    set_dry_run(True)
    try:
        result = runner.invoke(app, ["port-forward", "--stack", "llm"])
        assert result.exit_code == 0
        assert "ollama.url" in result.output
        assert "valkey.url" in result.output
    finally:
        set_dry_run(False)


def test_k8s_configure_urls_llm_dry_run() -> None:
    """k8s configure-urls --stack llm must print LLM target URLs."""
    set_dry_run(True)
    try:
        result = runner.invoke(app, ["configure-urls", "--stack", "llm"])
        assert result.exit_code == 0
        assert "ai.ollama_urls" in result.output
        assert "valkey.url" in result.output
    finally:
        set_dry_run(False)


@patch("devops_cli.commands.k8s._run_cmd")
def test_adopt_helm_resource_if_conflict(mock_run: MagicMock) -> None:
    """_adopt_helm_resource_if_conflict annotates and labels pre-existing K8s resources."""
    from devops_cli.commands.k8s import _adopt_helm_resource_if_conflict

    err = (
        'Error: unable to continue with install: Service "ollama" in namespace "llm" exists '
        "and cannot be imported into the current release: invalid ownership metadata; "
        'label validation error: missing key "app.kubernetes.io/managed-by": must be set to "Helm"'
    )
    res = _adopt_helm_resource_if_conflict(err, "ollama", "llm", context="homelab-k3s")
    assert res is True
    assert mock_run.call_count == 2
