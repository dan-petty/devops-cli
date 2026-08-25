"""Unit tests for Kubernetes CLI commands (devops_cli.commands.k8s)."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from devops_cli.commands.k8s import app
from devops_cli.dry_run import set_dry_run

runner = CliRunner()


def _mock_proc(
    returncode: int = 0, stdout: str = "", stderr: str = ""
) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(
        args=["kubectl"],
        returncode=returncode,
        stdout=stdout,
        stderr=stderr,
    )


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


def test_k8s_apply_and_logs() -> None:
    """Verify k8s apply and logs commands."""
    with patch("devops_cli.commands.k8s._run_cmd") as mock_run:
        result = runner.invoke(app, ["apply", "k8s/infra.yaml", "--namespace", "default"])
        assert result.exit_code == 0
        mock_run.assert_called_once()

    with patch("devops_cli.commands.k8s._run_cmd") as mock_run:
        result = runner.invoke(app, ["logs", "my-pod", "-n", "default", "--tail", "50"])
        assert result.exit_code == 0
        mock_run.assert_called_once()


def test_k8s_contexts_and_switch() -> None:
    """Verify k8s contexts and switch-context commands."""
    mock_config = MagicMock()
    mock_config.list_kube_config_contexts.return_value = (
        [{"name": "minikube", "context": {"cluster": "minikube", "user": "minikube"}}],
        {"name": "minikube"},
    )
    with patch("devops_cli.commands.k8s._k8s_clients", return_value=(mock_config, MagicMock())):
        result = runner.invoke(app, ["contexts"])
        assert result.exit_code == 0
        assert "minikube" in result.output

    with patch("devops_cli.commands.k8s._run_cmd") as mock_run:
        result = runner.invoke(app, ["switch-context", "minikube"])
        assert result.exit_code == 0
        mock_run.assert_called_once()


def test_k8s_status() -> None:
    """Verify k8s status command with cluster nodes and pods."""
    mock_config = MagicMock()
    mock_client = MagicMock()
    core_api = MagicMock()
    node_mock = MagicMock()
    node_mock.metadata.name = "node-1"
    node_mock.metadata.labels = {}
    node_mock.status.conditions = []
    node_mock.status.node_info.kubelet_version = "v1.28.0"
    core_api.list_node.return_value.items = [node_mock]

    pod_mock = MagicMock()
    pod_mock.metadata.name = "pod-1"
    pod_mock.metadata.namespace = "default"
    pod_mock.status.phase = "Running"
    pod_mock.status.container_statuses = []
    core_api.list_pod_for_all_namespaces.return_value.items = [pod_mock]
    mock_client.CoreV1Api.return_value = core_api

    with patch("devops_cli.commands.k8s._k8s_clients", return_value=(mock_config, mock_client)):
        result = runner.invoke(app, ["status"])
        assert result.exit_code == 0
        assert "node-1" in result.output


def test_k8s_bootstrap_and_stacks(tmp_path: Path) -> None:
    """Verify k8s bootstrap, deploy-stack, and teardown-stack execution."""
    with (
        patch("devops_cli.commands.k8s.shutil.which", return_value="/usr/local/bin/minikube"),
        patch("devops_cli.commands.k8s._minikube_running", return_value=True),
        patch(
            "devops_cli.commands.k8s.run_subprocess",
            return_value=_mock_proc(0, "minikube is running"),
        ),
        patch("devops_cli.commands.k8s._run_cmd", return_value=_mock_proc(0, "success")),
    ):
        result = runner.invoke(app, ["bootstrap", "--no-auto-start", "--stack", "infra"])
        assert result.exit_code == 0

    with (
        patch("devops_cli.commands.k8s.shutil.which", return_value="/usr/local/bin/helm"),
        patch("devops_cli.commands.k8s._run_cmd", return_value=_mock_proc(0, "success")),
    ):
        result = runner.invoke(app, ["deploy-stack", "--stack", "infra"])
        assert result.exit_code == 0

    with (
        patch("devops_cli.commands.k8s.shutil.which", return_value="/usr/local/bin/helm"),
        patch("devops_cli.commands.k8s._run_cmd", return_value=_mock_proc(0, "success")),
    ):
        result = runner.invoke(app, ["teardown-stack", "--stack", "infra"])
        assert result.exit_code == 0


def test_k8s_tls_secret_and_audit(tmp_path: Path) -> None:
    """Verify create-tls-secret and enable-tls commands."""
    cert_file = tmp_path / "tls.crt"
    key_file = tmp_path / "tls.key"
    cert_file.write_text("cert", encoding="utf-8")
    key_file.write_text("key", encoding="utf-8")

    with patch("devops_cli.commands.k8s._run_cmd", return_value=_mock_proc(0, "success")):
        result = runner.invoke(
            app,
            [
                "create-tls-secret",
                "my-tls-secret",
                "--cert",
                str(cert_file),
                "--key",
                str(key_file),
            ],
        )
        assert result.exit_code == 0

    with patch("devops_cli.commands.k8s._run_cmd", return_value=_mock_proc(0, "success")):
        result = runner.invoke(app, ["enable-tls", "--stack", "all"])
        assert result.exit_code == 0
