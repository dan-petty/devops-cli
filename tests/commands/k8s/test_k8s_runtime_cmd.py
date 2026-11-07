"""Unit tests for Kubernetes cluster runtime and subprocess execution helpers."""

from __future__ import annotations

import subprocess
from collections.abc import Callable
from pathlib import Path

import pytest
import typer

from devops_cli.commands.k8s.cluster_runtime import (
    _cluster_reachable,
    _minikube_running,
    _run_cmd,
    _validate_k8s_identifier,
)
from tests.support.fakes.process import ProcessAnswer, ProcessFake


def test_validate_k8s_identifier() -> None:
    _validate_k8s_identifier("my-pod-1", "pod")
    _validate_k8s_identifier("default", "namespace", namespace=True)

    with pytest.raises(typer.Exit) as raised:
        _validate_k8s_identifier("INVALID_POD_NAME!", "pod")
    assert raised.value.exit_code == 1


def test_run_cmd(process_fake: ProcessFake) -> None:
    process_fake.answer("kubectl get pods", ProcessAnswer(stdout="ok"))

    res = _run_cmd(["kubectl", "get", "pods"], check=True, capture=True)

    assert (res.returncode, res.stdout, [call.argv for call in process_fake.calls]) == (
        0,
        "ok",
        [("kubectl", "get", "pods")],
    )


def test_minikube_running_true(process_fake: ProcessFake) -> None:
    process_fake.answer("minikube status", ProcessAnswer(stdout="Running\n"))

    assert _minikube_running() is True


def test_minikube_running_false(process_fake: ProcessFake) -> None:
    process_fake.answer("minikube status", ProcessAnswer(returncode=1, stdout="Stopped\n"))

    assert _minikube_running() is False


def test_minikube_running_exception(process_fake: ProcessFake) -> None:
    process_fake.answer("minikube status", ProcessAnswer(side_effect=FileNotFoundError))

    assert _minikube_running() is False


def test_cluster_reachable_kubectl_success(process_fake: ProcessFake) -> None:
    process_fake.answer(
        "kubectl cluster-info", ProcessAnswer(stdout="Kubernetes control plane is running")
    )

    assert _cluster_reachable("custom-context") is True
    assert [call.argv for call in process_fake.calls] == [
        ("kubectl", "cluster-info", "--request-timeout=5s", "--context", "custom-context")
    ]


def test_cluster_reachable_fallback_minikube_true(
    process_fake: ProcessFake, config: Callable[..., Path]
) -> None:
    config(k8s={"context": "minikube"})
    process_fake.answer(
        "kubectl cluster-info", ProcessAnswer(side_effect=subprocess.SubprocessError)
    )
    process_fake.answer("minikube status", ProcessAnswer(stdout="Running\n"))

    assert _cluster_reachable() is True
    assert _cluster_reachable("minikube") is True


def test_cluster_reachable_fallback_minikube_false(
    process_fake: ProcessFake, config: Callable[..., Path]
) -> None:
    config(k8s={"context": "minikube"})
    process_fake.answer("kubectl cluster-info", ProcessAnswer(returncode=1))
    process_fake.answer("minikube status", ProcessAnswer(returncode=1, stdout="Stopped\n"))

    assert _cluster_reachable(None) is False
    assert _cluster_reachable("external-cluster") is False
