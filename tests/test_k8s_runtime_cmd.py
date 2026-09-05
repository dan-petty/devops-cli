"""Unit tests for Kubernetes cluster runtime and subprocess execution helpers."""

from __future__ import annotations

import subprocess
from typing import Any
from unittest.mock import patch

import pytest
import typer

from devops_cli.commands.k8s.cluster_runtime import (
    _cluster_reachable,
    _k8s_clients,
    _minikube_running,
    _run_cmd,
    _validate_k8s_identifier,
)


def test_validate_k8s_identifier() -> None:
    _validate_k8s_identifier("my-pod-1", "pod")
    _validate_k8s_identifier("default", "namespace", namespace=True)

    with pytest.raises(Exception):
        _validate_k8s_identifier("INVALID_POD_NAME!", "pod")


def test_k8s_clients_import_error() -> None:
    import builtins

    orig_import = builtins.__import__

    def mock_import(name: str, *args: Any, **kwargs: Any) -> Any:
        if "kubernetes" in name:
            raise ImportError("No module named 'kubernetes'")
        return orig_import(name, *args, **kwargs)

    with patch("builtins.__import__", side_effect=mock_import):
        with pytest.raises(typer.Exit) as exc_info:
            _k8s_clients()
        assert exc_info.value.exit_code == 1


def test_k8s_clients_success() -> None:
    cfg, cli = _k8s_clients()
    assert cfg is not None
    assert cli is not None


def test_run_cmd() -> None:
    with patch("devops_cli.commands.k8s.run_subprocess") as mock_sub:
        mock_sub.return_value = subprocess.CompletedProcess(
            args=["kubectl"], returncode=0, stdout="ok"
        )
        res = _run_cmd(["kubectl", "get", "pods"], check=True, capture=True)
        assert res.returncode == 0
        assert res.stdout == "ok"
        mock_sub.assert_called_once()


def test_minikube_running_true() -> None:
    with patch("devops_cli.commands.k8s._run_cmd") as mock_cmd:
        mock_cmd.return_value = subprocess.CompletedProcess(
            args=["minikube"], returncode=0, stdout="Running\n"
        )
        assert _minikube_running() is True


def test_minikube_running_false() -> None:
    with patch("devops_cli.commands.k8s._run_cmd") as mock_cmd:
        mock_cmd.return_value = subprocess.CompletedProcess(
            args=["minikube"], returncode=1, stdout="Stopped\n"
        )
        assert _minikube_running() is False


def test_minikube_running_exception() -> None:
    with patch("devops_cli.commands.k8s._run_cmd", side_effect=FileNotFoundError):
        assert _minikube_running() is False


def test_cluster_reachable_kubectl_success() -> None:
    with patch("devops_cli.commands.k8s._run_cmd") as mock_cmd:
        mock_cmd.return_value = subprocess.CompletedProcess(
            args=["kubectl"], returncode=0, stdout="Kubernetes control plane is running"
        )
        assert _cluster_reachable("custom-context") is True
        mock_cmd.assert_called_once_with(
            ["kubectl", "cluster-info", "--request-timeout=5s", "--context", "custom-context"],
            check=False,
            capture=True,
        )


def test_cluster_reachable_fallback_minikube_true() -> None:
    with (
        patch("devops_cli.commands.k8s._run_cmd", side_effect=subprocess.SubprocessError),
        patch("devops_cli.commands.k8s._minikube_running", return_value=True),
    ):
        assert _cluster_reachable() is True
        assert _cluster_reachable("minikube") is True


def test_cluster_reachable_fallback_minikube_false() -> None:
    with (
        patch("devops_cli.commands.k8s._run_cmd") as mock_cmd,
        patch("devops_cli.commands.k8s._minikube_running", return_value=False),
    ):
        mock_cmd.return_value = subprocess.CompletedProcess(
            args=["kubectl"], returncode=1, stdout=""
        )
        assert _cluster_reachable(None) is False
        assert _cluster_reachable("external-cluster") is False
