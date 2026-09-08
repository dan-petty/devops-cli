"""AI benchmarking, peer-grading, and embedding evaluation subpackage."""

from __future__ import annotations

from devops_cli.ai.benchmark.embedding_runner import EmbeddingBenchmarkRunner
from devops_cli.ai.benchmark.embedding_tasks import (
    EMBEDDING_DISTRACTORS,
    EMBEDDING_EVAL_PAIRS,
    EmbeddingEvalPair,
    get_embedding_eval_dataset,
)
from devops_cli.ai.benchmark.runner import BenchmarkRunner
from devops_cli.ai.benchmark.suite import (
    BenchmarkSuiteRunner,
    calculate_suite_metrics,
    evaluate_architectural_compliance,
    get_baseline_suite_cases,
    load_feedback_benchmark_dataset,
)
from devops_cli.ai.benchmark.tasks import BENCHMARK_TASKS, get_benchmark_tasks

__all__ = [
    "BENCHMARK_TASKS",
    "BenchmarkRunner",
    "BenchmarkSuiteRunner",
    "EMBEDDING_DISTRACTORS",
    "EMBEDDING_EVAL_PAIRS",
    "EmbeddingBenchmarkRunner",
    "EmbeddingEvalPair",
    "calculate_suite_metrics",
    "evaluate_architectural_compliance",
    "get_baseline_suite_cases",
    "get_benchmark_tasks",
    "get_embedding_eval_dataset",
    "load_feedback_benchmark_dataset",
]
