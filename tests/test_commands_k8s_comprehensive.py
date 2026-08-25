"""Comprehensive tests for Kubernetes CLI command implementations."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from devops_cli.commands.k8s import app

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


def test_k8s_apply_and_logs() -> None:
    with patch("devops_cli.commands.k8s._run_cmd") as mock_run:
        result = runner.invoke(app, ["apply", "k8s/infra.yaml", "--namespace", "default"])
        assert result.exit_code == 0
        mock_run.assert_called_once()

    with patch("devops_cli.commands.k8s._run_cmd") as mock_run:
        result = runner.invoke(app, ["logs", "my-pod", "-n", "default", "--tail", "50"])
        assert result.exit_code == 0
        mock_run.assert_called_once()


def test_k8s_contexts_and_switch() -> None:
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
