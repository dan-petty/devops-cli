"""Tests for the attempt context tracking efficiency metrics and first-pass rules (#5168)."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import pytest

from devops_cli import __version__
from tests.support.roadmap_job_result import result_lines

if TYPE_CHECKING:
    pass


def test_first_pass_table_and_boundary_values() -> None:
    """Verify that FIRST_PASS is defined and covers all 8 roadmap jobs at boundary values."""
    from devops_cli.roadmap import job_result

    assert hasattr(job_result, "FIRST_PASS"), "job_result must define FIRST_PASS table"
    first_pass_table = getattr(job_result, "FIRST_PASS")
    assert hasattr(job_result, "RoadmapJob")
    roadmap_job = job_result.RoadmapJob

    expected_jobs = {
        roadmap_job.STAGE,
        roadmap_job.IMPLEMENT,
        roadmap_job.FIX_PLAN,
        roadmap_job.REFINE,
        roadmap_job.REFINE_JUDGE,
        roadmap_job.ALTERNATIVES,
        roadmap_job.INTAKE,
    }
    assert hasattr(roadmap_job, "RETITLE"), "RoadmapJob must have RETITLE"
    expected_jobs.add(roadmap_job.RETITLE)
    expected_jobs.add(roadmap_job.FIX_CHECKS)

    assert set(first_pass_table.keys()) == expected_jobs

    assert hasattr(job_result, "is_first_pass"), "job_result must define is_first_pass"
    is_fp = getattr(job_result, "is_first_pass")

    # 1. stage: staged, plan_calls <= 1, gate_returns = 0, verify_rounds <= 1
    assert (
        is_fp(roadmap_job.STAGE, "staged", {"plan_calls": 1, "gate_returns": 0, "verify_rounds": 1})
        is True
    )
    assert (
        is_fp(roadmap_job.STAGE, "staged", {"plan_calls": 0, "gate_returns": 0, "verify_rounds": 1})
        is True
    )
    assert (
        is_fp(roadmap_job.STAGE, "staged", {"plan_calls": 2, "gate_returns": 0, "verify_rounds": 1})
        is False
    )
    assert (
        is_fp(roadmap_job.STAGE, "staged", {"plan_calls": 1, "gate_returns": 1, "verify_rounds": 1})
        is False
    )
    assert (
        is_fp(roadmap_job.STAGE, "staged", {"plan_calls": 1, "gate_returns": 0, "verify_rounds": 2})
        is False
    )
    assert (
        is_fp(roadmap_job.STAGE, "staged", {"gate_returns": 0, "verify_rounds": 1}) is False
    )  # missing plan_calls
    assert (
        is_fp(
            roadmap_job.STAGE,
            "needs_split",
            {"plan_calls": 1, "gate_returns": 0, "verify_rounds": 1},
        )
        is False
    )

    # 2. implement: ready, repair_rounds = 0, extensions = 0
    assert is_fp(roadmap_job.IMPLEMENT, "ready", {"repair_rounds": 0, "extensions": 0}) is True
    assert (
        is_fp(roadmap_job.IMPLEMENT, "ready", {"repair_rounds": 0}) is True
    )  # omitted extensions = 0
    assert is_fp(roadmap_job.IMPLEMENT, "ready", {"repair_rounds": 1, "extensions": 0}) is False
    assert is_fp(roadmap_job.IMPLEMENT, "ready", {"repair_rounds": 0, "extensions": 1}) is False
    assert is_fp(roadmap_job.IMPLEMENT, "stopped", {"repair_rounds": 0, "extensions": 0}) is False

    # 3. fix_plan: revised or cleared, gate_returns = 0, verify_rounds <= 1, after = 0
    assert (
        is_fp(roadmap_job.FIX_PLAN, "revised", {"gate_returns": 0, "verify_rounds": 1, "after": 0})
        is True
    )
    assert (
        is_fp(roadmap_job.FIX_PLAN, "cleared", {"gate_returns": 0, "verify_rounds": 1, "after": 0})
        is True
    )
    assert (
        is_fp(roadmap_job.FIX_PLAN, "revised", {"gate_returns": 0, "verify_rounds": 0}) is True
    )  # omitted after = 0
    assert (
        is_fp(roadmap_job.FIX_PLAN, "revised", {"gate_returns": 1, "verify_rounds": 1, "after": 0})
        is False
    )
    assert (
        is_fp(roadmap_job.FIX_PLAN, "revised", {"gate_returns": 0, "verify_rounds": 2, "after": 0})
        is False
    )
    assert (
        is_fp(roadmap_job.FIX_PLAN, "revised", {"gate_returns": 0, "verify_rounds": 1, "after": 1})
        is False
    )
    assert (
        is_fp(
            roadmap_job.FIX_PLAN, "unchanged", {"gate_returns": 0, "verify_rounds": 1, "after": 0}
        )
        is False
    )

    # 4. refine: success with tries = 1
    assert is_fp(roadmap_job.REFINE, "ready", {"tries": 1}) is True
    assert is_fp(roadmap_job.REFINE, "person", {"tries": 1}) is True
    assert is_fp(roadmap_job.REFINE, "split", {"tries": 1}) is True
    assert is_fp(roadmap_job.REFINE, "blocked", {"tries": 1}) is True
    assert is_fp(roadmap_job.REFINE, "ready", {"tries": 2}) is False
    assert is_fp(roadmap_job.REFINE, "error", {"tries": 1}) is False

    # 5. refine_judge: approved with round = 1 and findings = 0
    assert is_fp(roadmap_job.REFINE_JUDGE, "approved", {"round": 1, "findings": 0}) is True
    assert is_fp(roadmap_job.REFINE_JUDGE, "approved", {"round": 2, "findings": 0}) is False
    assert is_fp(roadmap_job.REFINE_JUDGE, "approved", {"round": 1, "findings": 1}) is False
    assert is_fp(roadmap_job.REFINE_JUDGE, "refused", {"round": 1, "findings": 0}) is False

    # 6. alternatives: a verdict with returns = 0
    assert is_fp(roadmap_job.ALTERNATIVES, "covers", {"returns": 0}) is True
    assert is_fp(roadmap_job.ALTERNATIVES, "in-use", {"returns": 0}) is True
    assert is_fp(roadmap_job.ALTERNATIVES, "covers", {"returns": 1}) is False
    assert is_fp(roadmap_job.ALTERNATIVES, "failed", {"returns": 0}) is False

    # 7. intake: placed or duplicate with no model fallback (fallbacks = 0)
    assert is_fp(roadmap_job.INTAKE, "placed", {"fallbacks": 0}) is True
    assert is_fp(roadmap_job.INTAKE, "duplicate", {"fallbacks": 0}) is True
    assert is_fp(roadmap_job.INTAKE, "placed", {"fallbacks": 1}) is False
    assert is_fp(roadmap_job.INTAKE, "skipped", {"fallbacks": 0}) is False

    # 8. fix_checks: a repair or a ready mark on the first attempt (#5027)
    assert is_fp(roadmap_job.FIX_CHECKS, "repaired", {"attempt": 1}) is True
    assert is_fp(roadmap_job.FIX_CHECKS, "ready", {"attempt": 1}) is True
    assert is_fp(roadmap_job.FIX_CHECKS, "repaired", {"attempt": 2}) is False
    assert is_fp(roadmap_job.FIX_CHECKS, "planned", {"attempt": 1}) is False

    # 8. retitle: retitled or kept on first reply (model_calls <= 1)
    assert is_fp(roadmap_job.RETITLE, "retitled", {"model_calls": 1}) is True
    assert is_fp(roadmap_job.RETITLE, "retitled", {"model_calls": 0}) is True
    assert is_fp(roadmap_job.RETITLE, "kept", {"model_calls": 1}) is True
    assert is_fp(roadmap_job.RETITLE, "retitled", {"model_calls": 2}) is False
    assert is_fp(roadmap_job.RETITLE, "failed", {"model_calls": 1}) is False


def test_attempt_context_tallies_model_calls_tokens_cost_and_gh_requests() -> None:
    """Verify that AttemptContext records model calls, tokens, integer micro-dollars, and GH requests."""
    from devops_cli.roadmap import job_result

    assert hasattr(job_result, "attempt_context"), "job_result must define attempt_context"
    attempt_context = getattr(job_result, "attempt_context")

    assert hasattr(job_result, "record_attempt_ai")
    assert hasattr(job_result, "record_attempt_gh")
    record_ai = getattr(job_result, "record_attempt_ai")
    record_gh = getattr(job_result, "record_attempt_gh")

    with attempt_context() as ctx:
        # Before recording
        assert ctx.model_calls == 0
        assert ctx.tokens == 0
        assert ctx.cost_usd_micros == 0
        assert ctx.gh_requests == 0
        assert ctx.seconds >= 0

        # Record AI call: 150 tokens, $0.0025 -> 2500 micros
        record_ai(150, 0.0025)
        assert ctx.model_calls == 1
        assert ctx.tokens == 150
        assert ctx.cost_usd_micros == 2500

        # Record local model call: 50 tokens, $0.0 -> 0 micros added
        record_ai(50, 0.0)
        assert ctx.model_calls == 2
        assert ctx.tokens == 200
        assert ctx.cost_usd_micros == 2500

        # Record GitHub requests
        record_gh()
        record_gh()
        assert ctx.gh_requests == 2


def test_log_job_result_in_attempt_context_emits_first_pass_and_efficiency_fields(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Verify that log_job_result outputs first_pass after infra, and includes context counts."""
    from devops_cli.roadmap import job_result

    assert hasattr(job_result, "attempt_context")
    attempt_context = getattr(job_result, "attempt_context")
    record_ai = getattr(job_result, "record_attempt_ai")
    record_gh = getattr(job_result, "record_attempt_gh")
    log_job_result = job_result.log_job_result
    roadmap_job = job_result.RoadmapJob

    with caplog.at_level(logging.INFO), attempt_context():
        record_ai(300, 0.005)  # 300 tokens, 5000 micros
        record_gh()
        log_job_result(
            roadmap_job.STAGE,
            "owner/repo",
            42,
            "staged",
            counts={"plan_calls": 1, "gate_returns": 0, "verify_rounds": 1},
        )

    lines = result_lines(caplog)
    assert len(lines) == 1
    line = lines[0]

    # Verify first_pass position is immediately after infra=false
    assert " infra=false first_pass=true " in line
    assert "model_calls=1" in line
    assert "tokens=300" in line
    assert "cost_usd_micros=5000" in line
    assert "gh_requests=1" in line
    assert "seconds=" in line
    assert "plan_calls=1" in line
    assert "gate_returns=0" in line
    assert "verify_rounds=1" in line
    assert f"version={__version__}" in line


def test_for_each_job_writes_attempt_with_efficiency_counts(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """For each job, verify that an attempt in context logs first_pass, model_calls, tokens, seconds, cost_usd_micros, and gh_requests."""
    from devops_cli.roadmap import job_result

    assert hasattr(job_result, "attempt_context")
    attempt_context = getattr(job_result, "attempt_context")
    record_ai = getattr(job_result, "record_attempt_ai")
    record_gh = getattr(job_result, "record_attempt_gh")
    log_job_result = job_result.log_job_result
    roadmap_job = job_result.RoadmapJob

    jobs = [
        (
            roadmap_job.STAGE,
            "staged",
            {"plan_calls": 1, "gate_returns": 0, "verify_rounds": 1},
        ),
        (roadmap_job.IMPLEMENT, "ready", {"repair_rounds": 0, "extensions": 0}),
        (
            roadmap_job.FIX_PLAN,
            "revised",
            {"gate_returns": 0, "verify_rounds": 1, "after": 0},
        ),
        (roadmap_job.REFINE, "ready", {"tries": 1}),
        (roadmap_job.REFINE_JUDGE, "approved", {"round": 1, "findings": 0}),
        (roadmap_job.ALTERNATIVES, "covers", {"returns": 0}),
        (roadmap_job.INTAKE, "placed", {"fallbacks": 0}),
        (roadmap_job.RETITLE, "retitled", {}),
    ]

    with caplog.at_level(logging.INFO):
        for job, result, extra_counts in jobs:
            with attempt_context():
                record_ai(100, 0.001)
                record_gh()
                log_job_result(job, "owner/repo", 1, result, counts=extra_counts)

    lines = result_lines(caplog)
    assert len(lines) == len(jobs)
    for line in lines:
        assert "first_pass=true" in line
        assert "model_calls=1" in line
        assert "tokens=100" in line
        assert "cost_usd_micros=1000" in line
        assert "gh_requests=1" in line
        assert "seconds=" in line


def test_model_call_in_job_pod_adds_to_counters_with_row_label(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A model call in a Job pod adds to the counters with the row label of its job (#5168)."""
    from devops_cli.ai.spend.ledger import track_request_spend
    from devops_cli.github.request_scope import request_scope

    emitted_records: list[tuple[object, object, dict[str, str]]] = []

    import devops_cli.telemetry.instruments as inst

    monkeypatch.setattr(
        inst,
        "emit",
        lambda instrument, value, labels: emitted_records.append((instrument, value, labels)),
    )

    for job_row in ("stage", "fix_plan", "implement"):
        emitted_records.clear()
        with request_scope(repo="owner/repo", row=job_row):
            track_request_spend(
                provider="openai",
                model="gpt-4o",
                server="https://api.openai.com",
                prompt_tokens=10,
                completion_tokens=5,
                cached=False,
            )

        rows = [labels.get("row") for _, _, labels in emitted_records]
        assert len(rows) > 0
        assert all(row == job_row for row in rows)
