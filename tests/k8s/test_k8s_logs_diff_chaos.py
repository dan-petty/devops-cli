"""Unit tests for Kubernetes stream-logs, diff-helm, and chaos commands."""

from __future__ import annotations

import shutil
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from devops_cli.k8s.chaos import execute_chaos_experiment
from devops_cli.k8s.diff import diff_helm_release
from devops_cli.k8s.logs import stream_multi_pod_logs
from tests.support.fakes.process import ProcessAnswer, ProcessFake


def test_stream_multi_pod_logs_dry_run() -> None:
    rc = stream_multi_pod_logs("test-app", dry_run=True)
    assert rc == 0


def test_stream_multi_pod_logs_stern(process_fake: ProcessFake) -> None:
    process_fake.answer(
        lambda call: "stern" in call.argv[0],
        ProcessAnswer(returncode=0, stdout=""),
    )
    rc = stream_multi_pod_logs("test-app", namespace="prod", follow=False)
    assert rc == 0
    assert len(process_fake.calls) > 0


def test_stream_multi_pod_logs_kubectl_fallback(
    process_fake: ProcessFake, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(shutil, "which", lambda _cmd: None)
    process_fake.answer(
        lambda call: "kubectl" in call.argv[0],
        ProcessAnswer(returncode=0, stdout=""),
    )
    rc = stream_multi_pod_logs("test-app", namespace="default", follow=False)
    assert rc == 0
    assert len(process_fake.calls) > 0


def test_diff_helm_release_dry_run(tmp_path: Path) -> None:
    chart = tmp_path / "mychart"
    chart.mkdir()
    rc, output = diff_helm_release("my-rel", chart, dry_run=True)
    assert rc == 0
    assert "Deployment" in output


def test_diff_helm_release_live(process_fake: ProcessFake, tmp_path: Path) -> None:
    process_fake.answer(
        lambda call: "helm" in call.argv[0],
        ProcessAnswer(returncode=0, stdout="No changes"),
    )
    chart = tmp_path / "mychart"
    chart.mkdir()
    rc, output = diff_helm_release("my-rel", chart)
    assert rc == 0
    assert output == "No changes"


def test_execute_chaos_experiment_dry_run() -> None:
    result = execute_chaos_experiment("pod-kill", "web-app", dry_run=True)
    assert result.recovered_successfully is True
    assert result.pods_affected == 1


def test_execute_chaos_experiment_live(process_fake: ProcessFake) -> None:
    process_fake.answer(
        lambda call: "get" in call.argv,
        ProcessAnswer(returncode=0, stdout="pod/web-app-123\n"),
    )
    process_fake.answer(
        lambda call: "delete" in call.argv,
        ProcessAnswer(returncode=0, stdout=""),
    )
    process_fake.answer(
        lambda call: "rollout" in call.argv,
        ProcessAnswer(returncode=0, stdout="deployment successfully rolled out\n"),
    )
    result = execute_chaos_experiment("pod-kill", "web-app", duration_seconds=1)
    assert result.recovered_successfully is True
    assert result.pods_affected == 1


def test_cli_k8s_subcommands_dry_run(cli: Callable[..., Any]) -> None:
    res_logs = cli("k8s", "stream-logs", "test-app", "--dry-run")
    assert res_logs.exit_code == 0

    res_diff = cli("k8s", "diff-helm", "my-release", "--dry-run")
    assert res_diff.exit_code == 0

    res_chaos = cli("k8s", "chaos", "pod-kill", "--dry-run")
    assert res_chaos.exit_code == 0

    res_pods = cli("k8s", "pods", "--dry-run", "-n", "kube-system")
    assert res_pods.exit_code == 0
    assert "list_namespaced_pod" in res_pods.output


def test_execute_chaos_experiment_rejects_injection_arguments() -> None:
    from devops_cli.exceptions import ValidationError

    with pytest.raises(ValidationError, match="Invalid Kubernetes namespace identifier"):
        execute_chaos_experiment("pod-kill", "web-app", namespace="--all-namespaces")

    with pytest.raises(ValidationError, match="Invalid Kubernetes deployment identifier"):
        execute_chaos_experiment("pod-kill", "web-app; rm -rf", namespace="default")


def test_execute_chaos_experiment_rejects_invalid_target_pod(process_fake: ProcessFake) -> None:
    from devops_cli.exceptions import ValidationError

    process_fake.answer(
        lambda call: "get" in call.argv,
        ProcessAnswer(returncode=0, stdout="pod/--flag-injection\n"),
    )
    with pytest.raises(ValidationError, match="Invalid Kubernetes pod identifier"):
        execute_chaos_experiment("pod-kill", "web-app", duration_seconds=1)
