"""AI benchmarking, peer-grading, and embedding evaluation subpackage."""

from __future__ import annotations

import importlib
from typing import Any

__all__ = [
    "BENCHMARK_TASKS",
    "EMBEDDING_DISTRACTORS",
    "EMBEDDING_EVAL_PAIRS",
    "BenchmarkRunner",
    "EmbeddingBenchmarkRunner",
    "EmbeddingEvalPair",
    "get_benchmark_tasks",
    "get_embedding_eval_dataset",
]

_ATTR_MAP: dict[str, tuple[str, str]] = {
    "EmbeddingBenchmarkRunner": (
        "devops_cli.ai.benchmark.embedding_runner",
        "EmbeddingBenchmarkRunner",
    ),
    "EMBEDDING_DISTRACTORS": ("devops_cli.ai.benchmark.embedding_tasks", "EMBEDDING_DISTRACTORS"),
    "EMBEDDING_EVAL_PAIRS": ("devops_cli.ai.benchmark.embedding_tasks", "EMBEDDING_EVAL_PAIRS"),
    "EmbeddingEvalPair": ("devops_cli.ai.benchmark.embedding_tasks", "EmbeddingEvalPair"),
    "get_embedding_eval_dataset": (
        "devops_cli.ai.benchmark.embedding_tasks",
        "get_embedding_eval_dataset",
    ),
    "BenchmarkRunner": ("devops_cli.ai.benchmark.runner", "BenchmarkRunner"),
    "BENCHMARK_TASKS": ("devops_cli.ai.benchmark.tasks", "BENCHMARK_TASKS"),
    "get_benchmark_tasks": ("devops_cli.ai.benchmark.tasks", "get_benchmark_tasks"),
}


def __getattr__(name: str) -> Any:
    if name in _ATTR_MAP:
        mod_name, attr = _ATTR_MAP[name]
        val = getattr(importlib.import_module(mod_name), attr)
        globals()[name] = val
        return val
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
