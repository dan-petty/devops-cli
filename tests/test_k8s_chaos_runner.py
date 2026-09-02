"""Unit tests for the Local Kubernetes Chaos & Fault Injection Engine."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from devops_cli.k8s.chaos_runner import (
    ChaosExperiment,
    ChaosFaultRunner,
    ChaosFaultType,
    ChaosReportStatus,
)


def test_chaos_experiment_model_defaults() -> None:
    exp = ChaosExperiment(
        name="kill_api_pods",
        fault_type=ChaosFaultType.POD_KILL,
        target_label_selector="app=backend",
    )
    assert exp.name == "kill_api_pods"
    assert exp.fault_type == ChaosFaultType.POD_KILL
    assert exp.namespace == "default"
    assert exp.recovery_timeout_seconds == 30.0


@patch("devops_cli.k8s.chaos_runner.run_subprocess")
def test_chaos_runner_pod_kill_success(mock_subproc: MagicMock) -> None:
    # 1. Get pods
    # 2. Delete pod
    # 3. Wait for pod recovery
    mock_subproc.side_effect = [
        MagicMock(returncode=0, stdout="backend-pod-1\nbackend-pod-2\n"),
        MagicMock(returncode=0, stdout="pod deleted"),
        MagicMock(returncode=0, stdout="backend-pod-1  Running\nbackend-pod-3  Running\n"),
    ]

    runner = ChaosFaultRunner()
    exp = ChaosExperiment(
        name="test_kill",
        fault_type=ChaosFaultType.POD_KILL,
        target_label_selector="app=backend",
    )

    report = runner.run_experiment(exp)

    assert report.status == ChaosReportStatus.SUCCESS
    assert len(report.affected_pods) > 0
    assert report.error is None
    assert report.recovery_time_seconds >= 0.0


@patch("devops_cli.k8s.chaos_runner.run_subprocess")
def test_chaos_runner_no_matching_pods(mock_subproc: MagicMock) -> None:
    mock_subproc.return_value = MagicMock(returncode=0, stdout="")

    runner = ChaosFaultRunner()
    exp = ChaosExperiment(
        name="empty_kill",
        fault_type=ChaosFaultType.POD_KILL,
        target_label_selector="app=nonexistent",
    )

    report = runner.run_experiment(exp)

    assert report.status == ChaosReportStatus.SKIPPED
    assert "No pods matching selector" in (report.error or "")


@patch("devops_cli.k8s.chaos_runner.run_subprocess")
def test_chaos_runner_command_failure(mock_subproc: MagicMock) -> None:
    mock_subproc.return_value = MagicMock(returncode=1, stderr="kubectl error: unauthorized")

    runner = ChaosFaultRunner()
    exp = ChaosExperiment(
        name="fail_kill",
        fault_type=ChaosFaultType.POD_KILL,
        target_label_selector="app=backend",
    )

    report = runner.run_experiment(exp)

    assert report.status == ChaosReportStatus.FAILED
    assert "kubectl error" in (report.error or "")
