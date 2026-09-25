"""Backend activity in review profiles and benchmarks (#557).

Profiles counted calls per backend, not how long each backend was busy or how many calls it had
in flight at once, so #545's imbalance was measured with a script sampling `nvidia-smi` and the
vLLM queues, and a benchmark could not show whether a routing change spread the load.
"""

from __future__ import annotations

import itertools
from pathlib import Path
from typing import Any

import pytest
from pydantic_ai.models.test import TestModel
from typer.testing import CliRunner

from devops_cli.ai.direct import direct_model_request_sync
from devops_cli.ai.review import profile as profile_module
from devops_cli.ai.review import runner
from devops_cli.ai.review.profile import (
    BackendActivity,
    ReviewProfile,
    StageProfile,
    backend_activity,
    profiling,
    report_profile,
    review_stage,
    summarize_profiles,
)
from devops_cli.ai.spend.ledger import observe_llm_calls
from devops_cli.commands import review as review_commands
from devops_cli.main import app

cli = CliRunner(env={"COLUMNS": "250", "NO_COLOR": "1", "TERM": "dumb"})

VLLM = "http://vllm.example.com:8000/v1"
OLLAMA = "http://ollama-0.example.com:11434"


def test_busy_time_is_the_union_of_calls_and_peak_their_overlap() -> None:
    """Verify overlapping calls count once toward busy time and back-to-back calls never overlap."""
    overlapping = backend_activity([(0.0, 4.0), (1.0, 3.0), (2.0, 6.0)])
    back_to_back = backend_activity([(0.0, 2.0), (2.0, 5.0), (8.0, 9.0)])

    assert (
        (overlapping.busy_seconds, overlapping.call_seconds, overlapping.peak_concurrency),
        round(overlapping.mean_concurrency, 2),
        (back_to_back.busy_seconds, back_to_back.peak_concurrency, back_to_back.mean_concurrency),
        BackendActivity().mean_concurrency,
    ) == ((6.0, 10.0, 3), 1.67, (6.0, 1, 1.0), 0.0)


def test_profiles_record_each_backends_activity_per_stage(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify each call, observed as it finishes, is placed on its backend's timeline by stage."""
    finished = iter([10.0, 11.0, 20.0, 30.0])
    calls = [(VLLM, 4.0), (VLLM, 2.0), (OLLAMA, 1.0), (None, 0.5)]

    with profiling() as profiler, review_stage("persona_review"):
        monkeypatch.setattr(profile_module.time, "monotonic", lambda: next(finished, 40.0))
        for served_by, duration in calls:
            profiler.observe(
                {"served_by": served_by, "duration_seconds": duration, "completion_tokens": 1}
            )
    stage = profiler.build(session_id="s", target="t").stages[0]

    assert {
        backend: (a.calls, a.busy_seconds, a.call_seconds, a.peak_concurrency)
        for backend, a in stage.activity.items()
    } == {VLLM: (2, 5.0, 6.0, 2), OLLAMA: (1, 1.0, 1.0, 1)}


def _run(persona_wall: float, vllm_busy: float, vllm_peak: int) -> ReviewProfile:
    activity = {
        VLLM: BackendActivity(calls=4, busy_seconds=vllm_busy, peak_concurrency=vllm_peak),
        OLLAMA: BackendActivity(calls=1, busy_seconds=10.0, peak_concurrency=1),
    }
    stage = StageProfile(
        name="persona_review",
        wall_seconds=persona_wall,
        llm_calls=5,
        backends={VLLM: 4, OLLAMA: 1},
        activity=activity,
    )
    return ReviewProfile(
        session_id="s", target="t", total_wall_seconds=persona_wall, llm_calls=5, stages=[stage]
    )


def test_benchmarks_show_each_backends_median_busy_share_and_peak() -> None:
    """Verify a benchmark takes each backend's median busy share and its highest peak."""
    summary = summarize_profiles([_run(100, 80, 2), _run(100, 40, 4), _run(200, 100, 3)])
    stage = summary.stages[0]

    assert (stage.backend_busy_share, stage.backend_peak_concurrency) == (
        {OLLAMA: 0.1, VLLM: 0.5},
        {OLLAMA: 1, VLLM: 4},
    )


def test_busy_share_is_capped_and_absent_without_activity() -> None:
    """Verify a backend busier than a rounded stage time reads as fully busy, never above it."""
    stage = StageProfile(
        name="verification",
        wall_seconds=10.0,
        activity={VLLM: BackendActivity(calls=1, busy_seconds=10.2)},
    )

    assert (stage.busy_share(VLLM), stage.busy_share(OLLAMA)) == (1.0, 0.0)


def test_benchmark_table_shows_busy_share_and_peak(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify the benchmark table gives each backend's share of the stage and its peak."""
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    (corpus / "site.yaml").write_text("- hosts: all\n", encoding="utf-8")
    runs = itertools.cycle([_run(100, 80, 2), _run(100, 40, 4)])

    def fake_review(**_: Any) -> None:
        report_profile(next(runs))

    monkeypatch.setattr(review_commands, "path", fake_review)
    monkeypatch.setattr(runner, "_get_reviews_base_dir", lambda: tmp_path / "reviews")

    result = cli.invoke(app, ["review", "benchmark", str(corpus), "-n", "2"])

    assert (
        result.exit_code,
        "vllm.example.com 60% ×4, ollama-0.example.com 10% ×1" in result.output,
    ) == (0, True)


def test_direct_requests_report_how_long_they_took() -> None:
    """Verify direct model requests give observers their duration like gateway calls do."""
    seen: list[dict[str, Any]] = []

    with observe_llm_calls(seen.append):
        direct_model_request_sync(model=TestModel(), prompt_or_messages="Run diagnostic check")

    assert [(c["request_type"], c["duration_seconds"] >= 0.0) for c in seen] == [
        ("direct_sync", True)
    ]
