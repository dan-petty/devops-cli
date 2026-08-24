"""Standard built-in benchmark tasks, evaluation rubrics, and reference criteria."""

from __future__ import annotations

from pathlib import Path

from devops_cli.models.benchmark import BenchmarkTask

_TASKS_DIR = Path(__file__).resolve().parent.parent / "tasks"


def _load_md(filename: str) -> str:
    path = _TASKS_DIR / filename
    return path.read_text(encoding="utf-8").strip() if path.exists() else ""


BENCHMARK_TASKS: list[BenchmarkTask] = [
    BenchmarkTask(
        id="sec-ssrf-remediation",
        title="Zero-Trust SSRF Validation & Webhook Dispatcher Remediation",
        category="security",
        prompt=_load_md("benchmark_sec_ssrf_prompt.md"),
        expected_solution=_load_md("benchmark_sec_ssrf_expected.md"),
        evaluation_rubric=_load_md("benchmark_sec_ssrf_rubric.md"),
        weight=1.5,
    ),
    BenchmarkTask(
        id="k8s-pod-security-standards",
        title="Kubernetes Deployment Hardening for Restricted Pod Security Standards",
        category="kubernetes",
        prompt=_load_md("benchmark_k8s_pss_prompt.md"),
        expected_solution=_load_md("benchmark_k8s_pss_expected.md"),
        evaluation_rubric=_load_md("benchmark_k8s_pss_rubric.md"),
        weight=1.2,
    ),
    BenchmarkTask(
        id="arch-pydantic-v2-migration",
        title="Modern Python 3.14+ & Pydantic v2 Architectural Migration",
        category="architecture",
        prompt=_load_md("benchmark_arch_pydantic_prompt.md"),
        expected_solution=_load_md("benchmark_arch_pydantic_expected.md"),
        evaluation_rubric=_load_md("benchmark_arch_pydantic_rubric.md"),
        weight=1.0,
    ),
    BenchmarkTask(
        id="ci-concurrency-triage",
        title="GitHub Actions Workflow Race Condition & Multi-Job Triage",
        category="ci_cd",
        prompt=_load_md("benchmark_ci_concurrency_prompt.md"),
        expected_solution=_load_md("benchmark_ci_concurrency_expected.md"),
        evaluation_rubric=_load_md("benchmark_ci_concurrency_rubric.md"),
        weight=1.1,
    ),
]


def get_benchmark_tasks(categories: list[str] | None = None) -> list[BenchmarkTask]:
    """Retrieve benchmark tasks optionally filtered by category name."""
    if not categories:
        return list(BENCHMARK_TASKS)
    cat_set = {c.lower() for c in categories}
    return [t for t in BENCHMARK_TASKS if t.category.lower() in cat_set or t.id.lower() in cat_set]
