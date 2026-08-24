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
from devops_cli.ai.benchmark.tasks import BENCHMARK_TASKS, get_benchmark_tasks

__all__ = [
    "BENCHMARK_TASKS",
    "BenchmarkRunner",
    "EMBEDDING_DISTRACTORS",
    "EMBEDDING_EVAL_PAIRS",
    "EmbeddingBenchmarkRunner",
    "EmbeddingEvalPair",
    "get_benchmark_tasks",
    "get_embedding_eval_dataset",
]
