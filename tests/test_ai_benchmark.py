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

    b_runner = BenchmarkRunner(models=models, tasks=tasks, servers=["http://localhost:11434"])
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
    b_runner = BenchmarkRunner(
        models=["mock-model"], tasks=tasks, servers=["http://localhost:11434"]
    )

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
            "--servers",
            "http://localhost:11434",
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
    b_runner = BenchmarkRunner(
        models=models,
        tasks=tasks,
        is_dry_run=True,
        concurrency=2,
        servers=["http://server-a:11434", "http://server-b:11434"],
    )

    # Test client configuration for parsed endpoints
    client_a = b_runner._client_for_model("model-a@http://server-a:11434")
    assert client_a._config.model == "model-a"
    assert client_a._config.ollama_urls == ["http://server-a:11434"]

    report = b_runner.execute()
    assert report.is_dry_run is True
    # 2 models * 1 task * 2 servers = 4 responses
    assert len(report.responses) == 4
    # 2 evaluator models * 2 candidate models * 1 task * 2 servers = 8 peer grades
    assert len(report.peer_grades) == 8
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

    # Expert model has higher judge weight than weak model (1.0 vs 0.01)
    assert expert_sum.judge_weight == 1.0
    assert weak_sum.judge_weight == 0.01
    # Weak model's 0.0 evaluation was discarded as invalid
    assert weak_sum.valid_evaluations_count == 1
    assert weak_sum.overall_percentage == 40.0
    assert expert_sum.valid_evaluations_count == 2


def test_benchmark_scaled_judge_weights_and_self_assessment_incorporation() -> None:
    """Verify that bad models giving bad scores to good models are mitigated."""
    tasks = [BENCHMARK_TASKS[0]]
    models = ["top-model", "bad-model"]
    b_runner = BenchmarkRunner(models=models, tasks=tasks)

    responses = [
        TaskResponse(
            task_id=tasks[0].id, model="top-model", provider="ollama", response="Top code"
        ),
        TaskResponse(
            task_id=tasks[0].id, model="bad-model", provider="ollama", response="Bad code"
        ),
    ]

    grades = [
        # Top model grades itself 90%
        PeerGrade(
            task_id=tasks[0].id,
            candidate_model="top-model",
            evaluator_model="top-model",
            accuracy_score=9.0,
            security_score=9.0,
            completeness_score=9.0,
            clarity_score=9.0,
            total_score=36.0,
            percentage=90.0,
        ),
        # Bad model grades top model unfairly low (40%)
        PeerGrade(
            task_id=tasks[0].id,
            candidate_model="top-model",
            evaluator_model="bad-model",
            accuracy_score=4.0,
            security_score=4.0,
            completeness_score=4.0,
            clarity_score=4.0,
            total_score=16.0,
            percentage=40.0,
        ),
        # Top model grades bad model 30%
        PeerGrade(
            task_id=tasks[0].id,
            candidate_model="bad-model",
            evaluator_model="top-model",
            accuracy_score=3.0,
            security_score=3.0,
            completeness_score=3.0,
            clarity_score=3.0,
            total_score=12.0,
            percentage=30.0,
        ),
        # Bad model grades itself unfairly high (95%)
        PeerGrade(
            task_id=tasks[0].id,
            candidate_model="bad-model",
            evaluator_model="bad-model",
            accuracy_score=9.5,
            security_score=9.5,
            completeness_score=9.5,
            clarity_score=9.5,
            total_score=38.0,
            percentage=95.0,
        ),
    ]

    leaderboard = b_runner._compute_leaderboard(responses, grades)
    top_sum = next(m for m in leaderboard if m.model == "top-model")
    bad_sum = next(m for m in leaderboard if m.model == "bad-model")

    # Top model has full weight (1.0), bad model has almost no weight (0.01)
    assert top_sum.judge_weight == 1.0
    assert bad_sum.judge_weight == 0.01

    # Top model's score stays high (~89.5%) despite bad model giving it 40%
    assert top_sum.overall_percentage >= 89.0

    # Bad model's score stays low (~30.6%) despite giving itself 95%
    assert bad_sum.overall_percentage <= 31.0


def test_benchmark_to_markdown_and_print_report(tmp_path: Path) -> None:
    """Verify Markdown generation and terminal table formatting for multi-task multi-server reports."""
    from devops_cli.models.benchmark import ServerBenchmarkSummary

    tasks = BENCHMARK_TASKS[:2]
    models = ["model-a", "model-b"]
    b_runner = BenchmarkRunner(
        models=models, tasks=tasks, servers=["http://node1:11434", "http://node2:11434"]
    )

    sum_a = ModelBenchmarkSummary(
        model="model-a",
        provider="ollama",
        overall_percentage=92.0,
        peer_only_percentage=90.0,
        accuracy_avg=9.2,
        security_avg=9.5,
        completeness_avg=9.0,
        clarity_avg=9.1,
        judge_weight=1.0,
        average_duration_seconds=1.5,
        self_preference_bias=2.0,
        category_scores={"security": 95.0, "kubernetes": 89.0},
    )
    sum_b = ModelBenchmarkSummary(
        model="model-b",
        provider="ollama",
        overall_percentage=85.0,
        peer_only_percentage=84.0,
        accuracy_avg=8.5,
        security_avg=8.0,
        completeness_avg=8.7,
        clarity_avg=8.8,
        judge_weight=0.9,
        average_duration_seconds=2.1,
        self_preference_bias=1.0,
        category_scores={"security": 80.0, "kubernetes": 90.0},
    )

    srv_1 = ServerBenchmarkSummary(
        server="http://node1:11434",
        generation_duration_avg=1.5,
        total_duration_seconds=3.0,
        tasks_generated_count=2,
        avg_score_awarded=88.0,
        server_score_bias=1.0,
        model_latencies={"model-a": 1.5},
    )
    srv_2 = ServerBenchmarkSummary(
        server="http://node2:11434",
        generation_duration_avg=2.1,
        total_duration_seconds=4.2,
        tasks_generated_count=2,
        avg_score_awarded=87.0,
        server_score_bias=-1.0,
        model_latencies={"model-b": 2.1},
    )

    grade = PeerGrade(
        task_id=tasks[0].id,
        candidate_model="model-a",
        evaluator_model="model-b",
        accuracy_score=9.0,
        security_score=9.0,
        completeness_score=9.0,
        clarity_score=9.0,
        total_score=36.0,
        percentage=90.0,
        strengths=["Clear logic"],
        weaknesses=["None"],
        feedback="Great work",
    )

    report = BenchmarkReport(
        session_id="20260826-test",
        models_evaluated=models,
        tasks_run=tasks,
        responses=[],
        peer_grades=[grade],
        leaderboard=[sum_a, sum_b],
        server_benchmarks=[srv_1, srv_2],
    )

    # Markdown export
    md = b_runner.to_markdown(report)
    assert "# AI Benchmark Report" in md
    assert "Leaderboard" in md
    assert "Domain Category Breakdown" in md
    assert "Server Performance & Score Bias" in md
    assert "Model Strengths & Improvement Areas" in md

    # Render results and save
    b_runner.render_results(report)
    saved_path = b_runner._save_report(report)
    assert saved_path.exists()


def test_embedding_benchmark_runner_and_metrics(tmp_path: Path) -> None:
    """Verify embedding math functions, dry run execution, markdown rendering, and reports."""
    from devops_cli.ai.benchmark.embedding_runner import (
        EmbeddingBenchmarkRunner,
        compute_ndcg_at_k,
        cosine_similarity,
    )

    # 1. cosine_similarity edge cases
    assert cosine_similarity([1.0, 0.0], [1.0, 0.0]) == pytest.approx(1.0)
    assert cosine_similarity([1.0, 0.0], [0.0, 1.0]) == pytest.approx(0.0)
    assert cosine_similarity([0.0, 0.0], [1.0, 1.0]) == 0.0
    assert cosine_similarity([1.0], [1.0, 2.0]) == 0.0
    assert cosine_similarity([], []) == 0.0

    # 2. compute_ndcg_at_k
    assert compute_ndcg_at_k([0, 1, 2], target_idx=0, k=3) == pytest.approx(1.0)
    assert compute_ndcg_at_k([1, 2, 0], target_idx=0, k=3) > 0.0
    assert compute_ndcg_at_k([1, 2, 3], target_idx=0, k=3) == 0.0

    # 3. EmbeddingBenchmarkRunner in dry-run mode
    emb_runner = EmbeddingBenchmarkRunner(
        models=["nomic-embed-text", "all-minilm"],
        servers=["http://server1:11434", "http://server2:11434"],
        is_dry_run=True,
    )
    report = emb_runner.run()
    assert report.is_dry_run is True
    assert len(report.models) >= 2

    md = emb_runner.generate_markdown(report)
    assert "# Embedding Model Benchmark Report" in md
    assert "Leaderboard Summary" in md
    assert "Server Hardware Comparison" in md

    emb_runner.print_report(report)
    emb_runner.print_report(report, format_type="json")
    emb_runner.print_report(report, format_type="markdown")
    emb_runner._save_report(report)


def test_embedding_benchmark_runner_mock_engine() -> None:
    """Verify embedding benchmark evaluation with mocked EmbeddingsEngine."""
    from devops_cli.ai.benchmark.embedding_runner import EmbeddingBenchmarkRunner, EmbeddingEvalPair

    mock_engine = MagicMock()
    # 2 docs in corpus, 2 queries
    mock_engine.embed_texts.side_effect = [
        [[1.0, 0.0]],  # latency query 1
        [[0.0, 1.0]],  # latency query 2
        [[1.0, 0.0], [0.0, 1.0]],  # corpus vectors
        [[1.0, 0.0], [0.0, 1.0]],  # query vectors
    ]

    emb_runner = EmbeddingBenchmarkRunner(
        models=["custom-model@http://localhost:11434"],
        is_dry_run=False,
    )
    with patch.object(emb_runner, "_engine_for_model", return_value=mock_engine):
        pairs = [
            EmbeddingEvalPair(
                id="eval-1", query="query 1", target_passage="doc 1", category="security"
            ),
            EmbeddingEvalPair(
                id="eval-2", query="query 2", target_passage="doc 2", category="kubernetes"
            ),
        ]
        corpus = ["doc 1", "doc 2"]
        res = emb_runner.evaluate_model("custom-model", pairs, corpus)
        assert res.model == "custom-model"
        assert res.recall_at_1 > 0.0
        assert res.dimension == 2


def test_embedding_benchmark_runner_full_run() -> None:
    """Verify full embedding benchmark suite orchestration with multiple models."""
    from devops_cli.ai.benchmark.embedding_runner import EmbeddingBenchmarkRunner
    from devops_cli.models.benchmark import EmbeddingBenchmarkResult

    mock_res_1 = EmbeddingBenchmarkResult(
        model="model-a",
        server="http://server1:11434",
        dimension=384,
        recall_at_1=90.0,
        recall_at_3=95.0,
        recall_at_5=98.0,
        mrr=0.92,
        ndcg_at_5=0.94,
        mean_cosine_margin=0.3,
        separation_score=0.4,
        latency_ms_p50=12.5,
        latency_ms_p95=25.0,
        throughput_items_per_sec=150.0,
        throughput_chars_per_sec=50000.0,
        overall_score=92.5,
        is_normalized=True,
    )
    mock_res_2 = EmbeddingBenchmarkResult(
        model="model-b",
        server="http://server2:11434",
        dimension=768,
        recall_at_1=80.0,
        recall_at_3=88.0,
        recall_at_5=92.0,
        mrr=0.85,
        ndcg_at_5=0.87,
        mean_cosine_margin=0.25,
        separation_score=0.35,
        latency_ms_p50=20.0,
        latency_ms_p95=35.0,
        throughput_items_per_sec=100.0,
        throughput_chars_per_sec=35000.0,
        overall_score=84.0,
        is_normalized=True,
    )

    runner = EmbeddingBenchmarkRunner(
        models=["model-a", "model-b"],
        servers=["http://server1:11434", "http://server2:11434"],
        is_dry_run=False,
    )
    mock_task = MagicMock()
    mock_chunk = MagicMock(token_count=10)
    with (
        patch(
            "devops_cli.ai.benchmark.embedding_runner.load_test_document_corpus",
            return_value=([mock_task], ["c1"], [mock_chunk]),
        ),
        patch.object(
            runner,
            "evaluate_model_on_server",
            side_effect=[mock_res_1, mock_res_2, mock_res_1, mock_res_2],
        ),
    ):
        report = runner.run()
        assert len(report.models) == 4
        assert len(report.recommendations) >= 3
        assert len(report.server_benchmarks) >= 2


def test_embedding_eval_dataset_parsers() -> None:
    """Verify parsing embedding eval pairs and distractors."""
    from devops_cli.ai.benchmark.embedding_tasks import (
        _parse_embedding_distractors,
        _parse_embedding_eval_pairs,
        get_embedding_eval_dataset,
    )

    sample_md = """## pair-1
- **Category:** test_cat
- **Query:** how to configure ingress?
- **Target Passage:** ingress configuration requires annotations and rules.

## pair-2
- **Category:** test_sec
- **Query:** how to prevent ssrf?
- **Target Passage:** validate all egress IPs against private network ranges.
"""
    pairs = _parse_embedding_eval_pairs(sample_md)
    assert len(pairs) == 2
    assert pairs[0].id == "pair-1"
    assert pairs[1].category == "test_sec"

    distractor_md = """- Distractor passage 1
- Distractor passage 2
"""
    distractors = _parse_embedding_distractors(distractor_md)
    assert len(distractors) == 2

    all_pairs, corpus = get_embedding_eval_dataset()
    assert len(all_pairs) > 0
    assert len(corpus) >= len(all_pairs)
