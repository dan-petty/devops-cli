"""Unit tests for AI multi-model benchmarking and peer-grading system."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from devops_cli.ai.benchmark.runner import BenchmarkRunner
from devops_cli.ai.benchmark.tasks import BENCHMARK_TASKS, get_benchmark_tasks
from devops_cli.commands.ai import app as ai_app
from devops_cli.models.benchmark import (
    BenchmarkReport,
    BenchmarkTask,
    ModelBenchmarkSummary,
    PeerGrade,
    TaskResponse,
)

runner = CliRunner()


def test_benchmark_tasks_structure() -> None:
    """Verify built-in tasks contain valid rubrics, weights, and categories."""
    tasks = get_benchmark_tasks()
    assert len(tasks) >= 4

    categories = {t.category for t in tasks}
    assert "security" in categories
    assert "kubernetes" in categories
    assert "architecture" in categories
    assert "ci_cd" in categories

    for t in tasks:
        assert t.id
        assert t.title
        assert len(t.prompt) > 20
        assert len(t.expected_solution) > 20
        assert len(t.evaluation_rubric) > 20
        assert 0.1 <= t.weight <= 5.0


def test_get_benchmark_tasks_filtering() -> None:
    """Verify filtering tasks by category or ID."""
    sec_tasks = get_benchmark_tasks(["security"])
    assert len(sec_tasks) >= 1
    assert all(t.category == "security" for t in sec_tasks)

    specific = get_benchmark_tasks(["sec-ssrf-remediation"])
    assert len(specific) == 1
    assert specific[0].id == "sec-ssrf-remediation"


def test_benchmark_models_serialization() -> None:
    """Verify benchmark data models serialise and deserialise cleanly."""
    task = BENCHMARK_TASKS[0]
    assert isinstance(task, BenchmarkTask)
    resp = TaskResponse(
        task_id=task.id,
        model="test-model",
        provider="ollama",
        response="Hardened code response",
        duration_seconds=1.2,
    )
    grade = PeerGrade(
        task_id=task.id,
        candidate_model="test-model",
        evaluator_model="judge-model",
        accuracy_score=9.0,
        security_score=9.5,
        completeness_score=8.5,
        clarity_score=9.0,
        total_score=36.0,
        percentage=90.0,
        strengths=["Robust regex"],
        weaknesses=[],
        feedback="Excellent security rigor",
    )
    summary = ModelBenchmarkSummary(
        model="test-model",
        provider="ollama",
        overall_percentage=90.0,
        accuracy_avg=9.0,
        security_avg=9.5,
        completeness_avg=8.5,
        clarity_avg=9.0,
        average_duration_seconds=1.2,
    )
    report = BenchmarkReport(
        session_id="20260821-test",
        models_evaluated=["test-model"],
        tasks_run=[task],
        responses=[resp],
        peer_grades=[grade],
        leaderboard=[summary],
        is_dry_run=True,
    )

    data = report.model_dump()
    reconstructed = BenchmarkReport.model_validate(data)
    assert reconstructed.session_id == "20260821-test"
    assert reconstructed.leaderboard[0].overall_percentage == 90.0


def test_benchmark_runner_dry_run(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify BenchmarkRunner end-to-end execution in dry-run mode."""
    monkeypatch.setenv("DEVOPS_CLI_DRY_RUN", "true")
    models = ["model-a", "model-b"]
    tasks = get_benchmark_tasks(["security"])

    b_runner = BenchmarkRunner(models=models, tasks=tasks)
    report = b_runner.execute()

    assert report.is_dry_run is True
    assert len(report.responses) == len(models) * len(tasks)
    # Each model evaluates all candidate models including itself
    assert len(report.peer_grades) == len(models) * len(models) * len(tasks)
    assert len(report.leaderboard) == len(models)
    assert report.leaderboard[0].overall_percentage > 0.0


def test_benchmark_runner_mock_evaluation() -> None:
    """Verify BenchmarkRunner LLM chat parsing and score aggregation."""
    mock_client = MagicMock()
    # First response: candidate answer; second response: JSON grade
    mock_client.chat.side_effect = [
        "Candidate answer from model",
        json.dumps(
            {
                "accuracy_score": 9.0,
                "security_score": 9.5,
                "completeness_score": 8.0,
                "clarity_score": 9.5,
                "total_score": 36.0,
                "percentage": 90.0,
                "strengths": ["Strong defense"],
                "weaknesses": [],
                "feedback": "Great job",
            }
        ),
    ]

    tasks = [BENCHMARK_TASKS[0]]
    b_runner = BenchmarkRunner(models=["mock-model"], tasks=tasks)

    with patch.object(b_runner, "_client_for_model", return_value=mock_client):
        report = b_runner.execute()

    assert len(report.responses) == 1
    assert len(report.peer_grades) == 1
    assert report.peer_grades[0].percentage == 90.0
    assert report.leaderboard[0].overall_percentage == 90.0


def test_benchmark_cli_command(tmp_path: Path) -> None:
    """Verify CLI invocation of `devops ai benchmark`."""
    out_file = tmp_path / "custom-benchmark.json"
    res = runner.invoke(
        ai_app,
        [
            "benchmark",
            "--models",
            "model-1@http://server1:11434,model-2@http://server2:11434",
            "--tasks",
            "security",
            "--concurrency",
            "2",
            "--output",
            str(out_file),
            "--dry-run",
        ],
    )
    assert res.exit_code == 0
    assert "AI Benchmark Leaderboard" in res.stdout or "Starting AI Benchmark" in res.stdout
    assert out_file.exists()
    report_data = json.loads(out_file.read_text(encoding="utf-8"))
    assert "leaderboard" in report_data


def test_benchmark_runner_concurrent_execution() -> None:
    """Verify concurrent execution across models with custom endpoint overrides."""
    tasks = [BENCHMARK_TASKS[0]]
    models = ["model-a@http://server-a:11434", "model-b@http://server-b:11434"]
    b_runner = BenchmarkRunner(models=models, tasks=tasks, is_dry_run=True, concurrency=2)

    # Test client configuration for parsed endpoints
    client_a = b_runner._client_for_model("model-a@http://server-a:11434")
    assert client_a._config.model == "model-a"
    assert client_a._config.ollama_urls == ["http://server-a:11434"]

    report = b_runner.execute()
    assert report.is_dry_run is True
    assert len(report.responses) == 2
    assert len(report.peer_grades) == 4
    assert len(report.leaderboard) == 2


def test_benchmark_filtering_invalid_defaults_and_judge_weighting() -> None:
    """Verify that 0-default evaluations are discarded and judge weighting applies."""
    tasks = [BENCHMARK_TASKS[0]]
    models = ["expert-model", "weak-model"]
    b_runner = BenchmarkRunner(models=models, tasks=tasks)

    responses = [
        TaskResponse(
            task_id=tasks[0].id, model="expert-model", provider="ollama", response="Expert answer"
        ),
        TaskResponse(
            task_id=tasks[0].id, model="weak-model", provider="ollama", response="Weak answer"
        ),
    ]

    grades = [
        # Expert model gets high score from weak judge (80%) and high score from expert judge (90%)
        PeerGrade(
            task_id=tasks[0].id,
            candidate_model="expert-model",
            evaluator_model="expert-model",
            accuracy_score=9.0,
            security_score=9.0,
            completeness_score=9.0,
            clarity_score=9.0,
            total_score=36.0,
            percentage=90.0,
        ),
        PeerGrade(
            task_id=tasks[0].id,
            candidate_model="expert-model",
            evaluator_model="weak-model",
            accuracy_score=8.0,
            security_score=8.0,
            completeness_score=8.0,
            clarity_score=8.0,
            total_score=32.0,
            percentage=80.0,
        ),
        # Weak model gets 40% from expert judge
        PeerGrade(
            task_id=tasks[0].id,
            candidate_model="weak-model",
            evaluator_model="expert-model",
            accuracy_score=4.0,
            security_score=4.0,
            completeness_score=4.0,
            clarity_score=4.0,
            total_score=16.0,
            percentage=40.0,
        ),
        # Weak model gets an invalid 0.0 default evaluation (e.g. parse error) from weak judge
        PeerGrade(
            task_id=tasks[0].id,
            candidate_model="weak-model",
            evaluator_model="weak-model",
            accuracy_score=0.0,
            security_score=0.0,
            completeness_score=0.0,
            clarity_score=0.0,
            total_score=0.0,
            percentage=0.0,
            feedback="Evaluation default due to parsing error",
        ),
    ]

    leaderboard = b_runner._compute_leaderboard(responses, grades)
    assert len(leaderboard) == 2
    expert_sum = next(m for m in leaderboard if m.model == "expert-model")
    weak_sum = next(m for m in leaderboard if m.model == "weak-model")

    # Expert model has higher judge weight than weak model
    assert expert_sum.judge_weight > weak_sum.judge_weight
    # Weak model's 0.0 evaluation was discarded as invalid
    assert weak_sum.valid_evaluations_count == 1
    assert weak_sum.overall_percentage == 40.0
    assert expert_sum.valid_evaluations_count == 2
