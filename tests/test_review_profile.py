"""Review profiles: wall time, LLM calls, tokens and serving backends per stage."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest
from typer.testing import CliRunner

from devops_cli.ai.review import runner
from devops_cli.ai.review.profile import (
    BenchmarkSummary,
    ReviewProfile,
    ReviewProfiler,
    StageProfile,
    active_profiler,
    collect_profiles,
    profiling,
    report_profile,
    review_stage,
    summarize_profiles,
)
from devops_cli.ai.review.runner import (
    _corpus_digest,
    _run_orchestrator_review,
    _write_review_profile,
)
from devops_cli.ai.spend.ledger import SpendLedger, observe_llm_calls, track_request_spend
from devops_cli.commands import review as review_commands
from devops_cli.commands.review import _backend_host
from devops_cli.main import app

cli = CliRunner(env={"COLUMNS": "250", "NO_COLOR": "1", "TERM": "dumb"})

VLLM = "http://vllm.example.com:8000/v1"
OLLAMA = "http://ollama-0.example.com:11434"


def _call(
    ledger: SpendLedger, served_by: str | None, completion: int = 10, *, cached: bool = False
) -> None:
    track_request_spend(
        provider="gateway",
        model="devops-review",
        server="gateway.example.com:4000",
        served_by=served_by,
        prompt_tokens=100,
        completion_tokens=completion,
        cached=cached,
        duration_seconds=1.0,
        ledger=ledger,
    )


def test_every_llm_call_reaches_the_observers(tmp_path: Path) -> None:
    """Verify observers see each recorded call, and only inside the block."""
    ledger = SpendLedger(db_path=tmp_path / "spend.db")
    seen: list[dict[str, Any]] = []

    with observe_llm_calls(seen.append):
        _call(ledger, VLLM, completion=7)
    _call(ledger, OLLAMA)

    assert [(c["served_by"], c["prompt_tokens"], c["completion_tokens"]) for c in seen] == [
        (VLLM, 100, 7)
    ]


def test_profiler_attributes_calls_to_stages_across_worker_threads(tmp_path: Path) -> None:
    """Verify calls are credited to the running stage, including calls made in worker threads."""
    ledger = SpendLedger(db_path=tmp_path / "spend.db")

    async def persona_calls() -> None:
        await asyncio.gather(
            asyncio.to_thread(_call, ledger, VLLM), asyncio.to_thread(_call, ledger, OLLAMA)
        )

    with profiling() as profiler:
        with review_stage("persona_review"):
            asyncio.run(persona_calls())
        with review_stage("verification"):
            _call(ledger, VLLM, completion=40)
        profiler.set_findings(candidates=10, verified=4, reported=3)
        profile = profiler.build(session_id="s1", target="playbooks")

    assert (
        [(s.name, s.llm_calls, s.completion_tokens, s.backends) for s in profile.stages],
        (profile.llm_calls, profile.candidate_findings, profile.reported_findings),
        active_profiler() is None,
    ) == (
        [
            ("persona_review", 2, 20, {VLLM: 1, OLLAMA: 1}),
            ("verification", 1, 40, {VLLM: 1}),
        ],
        (3, 10, 3),
        True,
    )


def test_cached_replies_are_counted_apart_from_backend_calls(tmp_path: Path) -> None:
    """Verify a cached reply adds no backend call or tokens, only a cached-call count."""
    ledger = SpendLedger(db_path=tmp_path / "spend.db")

    with profiling() as profiler:
        with review_stage("persona_review"):
            _call(ledger, VLLM)
            _call(ledger, None, cached=True)
        profile = profiler.build(session_id="s", target="t")

    assert (profile.llm_calls, profile.cached_calls, profile.completion_tokens) == (1, 1, 10)


def test_stage_is_a_no_op_without_a_profiler() -> None:
    """Verify stage markers cost nothing when no review is being profiled."""
    with review_stage("persona_review"):
        pass

    assert active_profiler() is None


def _profile(wall: float, persona: float, calls: int, candidates: int) -> ReviewProfile:
    return ReviewProfile(
        session_id="s",
        target="t",
        total_wall_seconds=wall,
        llm_calls=calls,
        candidate_findings=candidates,
        stages=[StageProfile(name="persona_review", wall_seconds=persona, llm_calls=calls)],
    )


def test_benchmark_summary_takes_medians_across_runs() -> None:
    """Verify repeated runs are summarised by their medians, stage by stage."""
    summary = summarize_profiles(
        [_profile(300, 200, 80, 50), _profile(200, 150, 60, 40), _profile(250, 180, 70, 70)]
    )

    assert (
        summary.runs,
        summary.median_wall_seconds,
        summary.median_candidate_findings,
        summary.median_seconds_per_candidate,
        [(s.name, s.median_wall_seconds, s.median_llm_calls) for s in summary.stages],
    ) == (3, 250.0, 50.0, 5.0, [("persona_review", 180.0, 70.0)])


def test_orchestrated_review_profiles_each_stage_and_its_findings() -> None:
    """Verify the review marks its stages and records candidate, verified and reported counts."""
    finding = MagicMock(verified=True, reportable=True)
    payload = MagicMock(findings=[finding, MagicMock(verified=False, reportable=False)])
    orchestrator = MagicMock()
    orchestrator.init_per_file_payloads.return_value = [payload]
    orchestrator.generate_consolidated_report.return_value = ({}, "report")

    with profiling() as profiler:
        _run_orchestrator_review(orchestrator, ["a.yaml"], {}, None, ["a.yaml"], ["qa"], None)
        profile = profiler.build(session_id="s", target="t")

    assert (
        [s.name for s in profile.stages],
        (profile.candidate_findings, profile.verified_findings, profile.reported_findings),
    ) == (
        ["payloads", "persona_review", "verification", "reranking", "report"],
        (2, 1, 1),
    )


def test_profile_is_written_as_json(tmp_path: Path) -> None:
    """Verify a profile round-trips through the session's profile.json."""
    profile = _profile(120, 90, 12, 8)
    path = profile.write(tmp_path)

    assert (path.name, ReviewProfile(**json.loads(path.read_text())).llm_calls) == (
        "profile.json",
        12,
    )


def test_profiler_is_isolated_per_block() -> None:
    """Verify each profiling block gets its own profiler."""
    with profiling() as first:
        pass
    with profiling() as second:
        pass

    assert (isinstance(first, ReviewProfiler), first is second) == (True, False)


def test_written_profiles_reach_the_collecting_benchmark(tmp_path: Path) -> None:
    """Verify a review's profile is written to its session and handed to a collecting benchmark."""
    orchestrator = MagicMock(session_id="20260924-120000", session_dir=tmp_path)

    with collect_profiles() as profiles:
        with profiling() as profiler:
            _write_review_profile(profiler, orchestrator, "playbooks", 15)
    report_profile(_profile(1, 1, 1, 1))

    assert (
        [(p.session_id, p.target, p.files) for p in profiles],
        (tmp_path / "profile.json").exists(),
    ) == ([("20260924-120000", "playbooks", 15)], True)


def test_benchmark_summary_is_saved_under_the_reviews_directory(tmp_path: Path) -> None:
    """Verify each benchmark is saved as its own JSON file, which loads back unchanged."""
    summary = summarize_profiles([_profile(300, 200, 80, 50)])
    saved = summary.write(tmp_path)

    assert (saved.parent.name, BenchmarkSummary(**json.loads(saved.read_text()))) == (
        "benchmarks",
        summary,
    )


def test_benchmark_command_reviews_each_run_without_the_cache(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify the benchmark runs the review N times uncached and saves the median summary."""
    corpus, reviews = tmp_path / "corpus", tmp_path / "reviews"
    corpus.mkdir()
    (corpus / "site.yaml").write_text("- hosts: all\n", encoding="utf-8")
    calls: list[dict[str, Any]] = []

    def fake_review(**kwargs: Any) -> None:
        calls.append(kwargs)
        report_profile(_profile(100.0 * len(calls), 60, 10, 5))

    monkeypatch.setattr(review_commands, "path", fake_review)
    monkeypatch.setattr(runner, "_get_reviews_base_dir", lambda: reviews)

    result = cli.invoke(app, ["review", "benchmark", str(corpus), "-n", "3", "--all"])
    saved = list((reviews / "benchmarks").glob("*.json"))
    summary = BenchmarkSummary(**json.loads(saved[0].read_text()))

    assert (
        result.exit_code,
        [(c["no_cache"], c["all_personas"], c["targets"]) for c in calls],
        (summary.runs, summary.median_wall_seconds, summary.corpus_digest),
        "Median per Stage" in result.output,
    ) == (0, [(True, True, [corpus])] * 3, (3, 200.0, _corpus_digest([corpus], "*")), True)


def test_corpus_digest_changes_only_with_the_reviewed_files(tmp_path: Path) -> None:
    """Verify the corpus fingerprint is stable for the same files and changes with their content."""
    playbook = tmp_path / "site.yaml"
    playbook.write_text("- hosts: all\n", encoding="utf-8")
    first = _corpus_digest([tmp_path], "*.yaml")
    (tmp_path / "notes.txt").write_text("not reviewed", encoding="utf-8")
    unmatched = _corpus_digest([tmp_path], "*.yaml")
    playbook.write_text("- hosts: web\n", encoding="utf-8")

    assert (unmatched == first, _corpus_digest([tmp_path], "*.yaml") == first) == (True, False)


def test_benchmark_fails_when_no_review_was_profiled(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify a benchmark whose runs reviewed nothing exits non-zero and saves nothing."""
    monkeypatch.setattr(review_commands, "path", lambda **kwargs: None)
    monkeypatch.setattr(runner, "_get_reviews_base_dir", lambda: tmp_path)

    result = cli.invoke(app, ["review", "benchmark", str(tmp_path), "-n", "2"])

    assert (result.exit_code, (tmp_path / "benchmarks").exists()) == (1, False)


def test_backend_labels_drop_the_cluster_dns_suffix() -> None:
    """Verify in-cluster backends are labelled by pod or service, other backends by host."""
    assert [
        _backend_host("http://ollama-0.ollama-nodes.llm.svc.cluster.local:11434"),
        _backend_host("http://vllm-single.llm.svc.cluster.local:8000/v1"),
        _backend_host(VLLM),
    ] == ["ollama-0", "vllm-single", "vllm.example.com"]
