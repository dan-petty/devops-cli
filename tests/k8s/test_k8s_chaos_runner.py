"""Unit tests for the Local Kubernetes Chaos & Fault Injection Engine."""

from __future__ import annotations

from devops_cli.k8s.chaos_runner import (
    ChaosExperiment,
    ChaosFaultRunner,
    ChaosFaultType,
    ChaosReportStatus,
)
from tests.support.fakes.process import ProcessAnswer, ProcessFake


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


def test_chaos_runner_kills_pod_and_waits_for_recovery(process_fake: ProcessFake) -> None:
    process_fake.answer(
        lambda call: "get" in call.argv,
        ProcessAnswer(returncode=0, stdout="backend-pod-1\nbackend-pod-2\n"),
    )
    process_fake.answer(
        lambda call: "delete" in call.argv,
        ProcessAnswer(returncode=0, stdout="pod deleted"),
    )

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


def test_chaos_runner_skips_when_no_pods_match_selector(process_fake: ProcessFake) -> None:
    process_fake.answer(
        lambda call: "get" in call.argv,
        ProcessAnswer(returncode=0, stdout=""),
    )

    runner = ChaosFaultRunner()
    exp = ChaosExperiment(
        name="empty_kill",
        fault_type=ChaosFaultType.POD_KILL,
        target_label_selector="app=nonexistent",
    )

    report = runner.run_experiment(exp)

    assert report.status == ChaosReportStatus.SKIPPED
    assert "No pods matching selector" in (report.error or "")


def test_chaos_runner_reports_failure_on_command_error(process_fake: ProcessFake) -> None:
    process_fake.answer(
        lambda call: "get" in call.argv,
        ProcessAnswer(returncode=1, stderr="kubectl error: unauthorized"),
    )

    runner = ChaosFaultRunner()
    exp = ChaosExperiment(
        name="fail_kill",
        fault_type=ChaosFaultType.POD_KILL,
        target_label_selector="app=backend",
    )

    report = runner.run_experiment(exp)

    assert report.status == ChaosReportStatus.FAILED
    assert "kubectl error" in (report.error or "")
