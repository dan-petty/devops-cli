"""Tests for the item cohort funnel report (`devops roadmap eval funnel`, #5494)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from devops_cli.github.repo_ref import RepoRef
from devops_cli.roadmap.job_funnel import (
    FunnelItem,
    FunnelPath,
    FunnelPull,
    build_funnel_report,
    parse_issue_timeline,
    plan_funnel_queries,
    render_funnel_report,
)
from devops_cli.roadmap.job_result import RoadmapJob, log_job_result
from tests.support.fakes.http import WebFake
from tests.support.fakes.loki import LokiFake
from tests.support.roadmap_job_grades import LOKI_URL, SERVICE_STREAM, STAGE_STREAM

_REPO = "example/app"
_SINCE = datetime(2026, 11, 1, tzinfo=UTC)
_NOW = datetime(2026, 11, 24, 12, 0, tzinfo=UTC)


def _ts(year: int, month: int, day: int, hour: int = 12, minute: int = 0) -> datetime:
    return datetime(year, month, day, hour, minute, tzinfo=UTC)


def _labeled(at: datetime, name: str) -> dict[str, Any]:
    return {"event": "labeled", "created_at": at.isoformat(), "label": {"name": name}}


def _unlabeled(at: datetime, name: str) -> dict[str, Any]:
    return {"event": "unlabeled", "created_at": at.isoformat(), "label": {"name": name}}


def _cross_ref_pr(
    number: int,
    title: str,
    *,
    created_at: datetime,
    head_ref: str,
    state: str = "closed",
    draft: bool = False,
    merged_at: datetime | None = None,
    ready_at: datetime | None = None,
) -> dict[str, Any]:
    return {
        "event": "cross-referenced",
        "created_at": created_at.isoformat(),
        "source": {
            "type": "issue",
            "issue": {
                "number": number,
                "title": title,
                "state": state,
                "draft": draft,
                "created_at": created_at.isoformat(),
                "head": {"ref": head_ref},
                "ready_at": ready_at.isoformat() if ready_at is not None else None,
                "pull_request": {
                    "url": f"https://api.github.com/repos/{_REPO}/pulls/{number}",
                    "merged_at": merged_at.isoformat() if merged_at is not None else None,
                },
            },
        },
    }


def _step(cohort: Any, name: str, *, path: FunnelPath | None = None) -> Any:
    return next(s for s in cohort.steps if s.step == name and s.path == path)


def test_latest_ready_after_unlabeled_cancellation_uses_new_iso_week() -> None:
    """An unlabeled `status/ready` cancels an earlier Ready event; re-readying in week 47 places
    the item once in week 47 and never in week 45."""
    events = [
        _labeled(_ts(2026, 11, 3, 9), "status/new"),
        _labeled(_ts(2026, 11, 3, 12), "status/ready"),  # ISO week 45
        _unlabeled(_ts(2026, 11, 9, 10), "status/ready"),
        _labeled(_ts(2026, 11, 17, 10), "status/new"),
        _labeled(_ts(2026, 11, 17, 14), "status/ready"),  # ISO week 47
    ]
    item = parse_issue_timeline(
        _REPO, 101, created_at=_ts(2026, 11, 3, 8), state="open", events=events
    )
    assert item is not None
    assert item.cohort == "2026-W47"

    report = build_funnel_report([item], since=_SINCE, until=_NOW, loki_url=LOKI_URL, repos=[_REPO])

    assert [c.cohort for c in report.cohorts] == ["2026-W47"]
    assert report.cohorts[0].items_count == 1
    step1 = _step(report.cohorts[0], "New (placed) to Ready")
    assert step1.n == 1
    assert step1.median_seconds == 4 * 3600.0


def test_forward_status_transition_keeps_ready_cohort() -> None:
    """When `write_status` replaces `status/ready` with `status/in-progress`, the unlabel is a
    forward progression rather than cancellation."""
    events = [
        _labeled(_ts(2026, 11, 18, 8), "status/new"),
        _labeled(_ts(2026, 11, 18, 9), "status/ready"),  # ISO week 47
        _unlabeled(_ts(2026, 11, 18, 10), "status/ready"),
        _labeled(_ts(2026, 11, 18, 10), "status/in-progress"),
    ]
    item = parse_issue_timeline(
        _REPO, 102, created_at=_ts(2026, 11, 18, 7), state="open", events=events
    )
    assert item is not None
    assert (item.cohort, item.ready_at) == ("2026-W47", _ts(2026, 11, 18, 9))


def test_continue_path_uses_plan_open_step_not_g1_merged_step() -> None:
    """Same head branch on plan and delivery PR selects path `continue`."""
    branch = "docs/openspec/5494-eval-funnel"
    events = [
        _labeled(_ts(2026, 11, 17, 10), "status/new"),
        _labeled(_ts(2026, 11, 17, 11), "status/ready"),
        _cross_ref_pr(
            200,
            "docs(openspec): plan #5494 eval funnel",
            created_at=_ts(2026, 11, 17, 12),
            head_ref=branch,
            state="closed",
            merged_at=None,
        ),
        _cross_ref_pr(
            201,
            "feat(roadmap): eval funnel",
            created_at=_ts(2026, 11, 17, 13),
            head_ref=branch,
            state="closed",
            draft=False,
            ready_at=_ts(2026, 11, 17, 14),
            merged_at=_ts(2026, 11, 17, 16),
        ),
    ]
    item = parse_issue_timeline(
        _REPO, 5494, created_at=_ts(2026, 11, 17, 9), state="closed", events=events
    )
    assert item is not None
    assert item.path is FunnelPath.CONTINUE

    report = build_funnel_report([item], since=_SINCE, until=_NOW, loki_url=LOKI_URL, repos=[_REPO])
    cohort = report.cohorts[0]
    cont_step = _step(cohort, "plan PR open to ready delivery PR", path=FunnelPath.CONTINUE)
    g1_step = _step(cohort, "plan PR merged to ready delivery PR", path=FunnelPath.G1)
    assert (cont_step.n, cont_step.passed, cont_step.median_seconds) == (1, 1, 2 * 3600.0)
    assert (g1_step.n, g1_step.passed, g1_step.in_progress) == (0, 0, 0)


def test_g1_path_tracks_plan_merged_to_ready_delivery_pr() -> None:
    """Distinct branches with merged plan PR select path `G1`."""
    events = [
        _labeled(_ts(2026, 11, 17, 10), "status/new"),
        _labeled(_ts(2026, 11, 17, 11), "status/ready"),
        _cross_ref_pr(
            300,
            "docs(openspec): plan #5494 eval funnel",
            created_at=_ts(2026, 11, 17, 12),
            head_ref="docs/openspec/5494-eval-funnel",
            merged_at=_ts(2026, 11, 17, 13),
        ),
        _cross_ref_pr(
            301,
            "feat(roadmap): eval funnel",
            created_at=_ts(2026, 11, 17, 14),
            head_ref="feat/5494-eval-funnel",
            draft=False,
            ready_at=_ts(2026, 11, 17, 15),
            merged_at=_ts(2026, 11, 17, 17),
        ),
    ]
    item = parse_issue_timeline(
        _REPO, 5495, created_at=_ts(2026, 11, 17, 9), state="closed", events=events
    )
    assert item is not None
    assert item.path is FunnelPath.G1

    report = build_funnel_report([item], since=_SINCE, until=_NOW, loki_url=LOKI_URL, repos=[_REPO])
    cohort = report.cohorts[0]
    g1_step = _step(cohort, "plan PR merged to ready delivery PR", path=FunnelPath.G1)
    merge_step = _step(cohort, "ready delivery PR to merge", path=FunnelPath.G1)
    assert (g1_step.n, g1_step.passed, g1_step.median_seconds) == (1, 1, 2 * 3600.0)
    assert (merge_step.n, merge_step.passed, merge_step.median_seconds) == (1, 1, 2 * 3600.0)


def _item_ready_to_plan(
    number: int, *, passed_seconds: float | None, state: str = "open"
) -> FunnelItem:
    ready_at = _ts(2026, 11, 17, 10)
    plan_pr = (
        FunnelPull(
            number=1000 + number,
            title=f"docs(openspec): plan #{number} item",
            head_ref=f"docs/openspec/{number}-item",
            state="open",
            draft=False,
            created_at=ready_at + timedelta(seconds=passed_seconds),
        )
        if passed_seconds is not None
        else None
    )
    return FunnelItem(
        repo=_REPO,
        number=number,
        created_at=ready_at - timedelta(hours=1),
        new_at=ready_at - timedelta(minutes=30),
        ready_at=ready_at,
        cohort="2026-W47",
        state=state,
        plan_pr=plan_pr,
    )


def test_step_measures_wilson_bounds_smallest_change_and_quantiles() -> None:
    """Eight passes out of ten completed items yield known Wilson interval, MDE, median, and p90."""
    durations = [100.0, 200.0, 300.0, 400.0, 500.0, 600.0, 700.0, 800.0]
    items = [
        _item_ready_to_plan(i + 1, passed_seconds=d, state="closed")
        for i, d in enumerate(durations)
    ]
    items += [_item_ready_to_plan(9, passed_seconds=None, state="closed")]
    items += [_item_ready_to_plan(10, passed_seconds=None, state="closed")]

    report = build_funnel_report(items, since=_SINCE, until=_NOW, loki_url=LOKI_URL, repos=[_REPO])
    step = _step(report.cohorts[0], "Ready to plan PR open")

    assert (step.n, step.passed, step.in_progress) == (10, 8, 0)
    assert step.share == pytest.approx(0.8)
    assert step.wilson_lower == pytest.approx(0.490, abs=0.001)
    assert step.wilson_upper == pytest.approx(0.943, abs=0.001)
    assert step.smallest_change == pytest.approx(0.227, abs=0.001)
    assert step.median_seconds == pytest.approx(450.0)
    assert step.p90_seconds == pytest.approx(730.0)


def test_young_open_item_counts_as_in_progress_outside_share() -> None:
    """An open item younger than window p90 increments `in_progress` and stays out of `n`."""
    passed_ready = _ts(2026, 11, 10, 10)  # ISO week 46: sets window p90 = 1000s
    passed = FunnelItem(
        repo=_REPO,
        number=1,
        created_at=passed_ready - timedelta(hours=1),
        new_at=passed_ready - timedelta(hours=1),
        ready_at=passed_ready,
        cohort="2026-W46",
        state="open",
        plan_pr=FunnelPull(
            number=50,
            title="docs(openspec): plan #1 passed",
            head_ref="docs/openspec/1-passed",
            state="open",
            draft=False,
            created_at=passed_ready + timedelta(seconds=1000),
        ),
    )
    now = _ts(2026, 11, 18, 12)
    young = FunnelItem(
        repo=_REPO,
        number=2,
        created_at=now - timedelta(seconds=500),
        new_at=now - timedelta(seconds=500),
        ready_at=now - timedelta(seconds=300),  # age 300s < p90 1000s (week 47)
        cohort="2026-W47",
        state="open",
    )
    stale = FunnelItem(
        repo=_REPO,
        number=3,
        created_at=now - timedelta(seconds=3000),
        new_at=now - timedelta(seconds=3000),
        ready_at=now - timedelta(seconds=2000),  # age 2000s >= p90 1000s (week 47)
        cohort="2026-W47",
        state="open",
    )

    report = build_funnel_report(
        [passed, young, stale], since=_SINCE, until=now, loki_url=LOKI_URL, repos=[_REPO]
    )
    w47 = next(c for c in report.cohorts if c.cohort == "2026-W47")
    step = _step(w47, "Ready to plan PR open")

    assert (step.in_progress, step.n, step.passed, step.failed) == (1, 1, 0, 1)
    assert step.share == 0.0


def test_loki_tokens_cost_and_missing_result_line_counts(
    caplog: pytest.LogCaptureFixture, web: WebFake
) -> None:
    """Loki sums divide by step passes; an item with no result line stays in n with 0 tokens and
    increments `missing_result_lines`."""
    loki = LokiFake()
    with caplog.at_level("INFO", logger="devops_cli.roadmap.job_result"):
        caplog.clear()
        log_job_result(
            RoadmapJob.STAGE,
            _REPO,
            11,
            "staged",
            counts={"tokens": 1000, "cost_usd_micros": 2000},
        )
        log_job_result(
            RoadmapJob.STAGE,
            _REPO,
            12,
            "staged",
            counts={"tokens": 1000, "cost_usd_micros": 2000},
        )
    lines = [r.getMessage() for r in caplog.records if "roadmap job result:" in r.getMessage()]
    loki.push(SERVICE_STREAM, f'{{"message": "{lines[0]}"}}')
    loki.push(STAGE_STREAM, lines[1])
    loki.serve(web)

    items = [
        _item_ready_to_plan(11, passed_seconds=60.0),
        _item_ready_to_plan(12, passed_seconds=120.0),
        _item_ready_to_plan(13, passed_seconds=None, state="closed"),
    ]
    from devops_cli.roadmap.job_funnel import read_loki_funnel_totals

    totals = read_loki_funnel_totals(RepoRef(_REPO), since=_SINCE, until=_NOW, loki_url=LOKI_URL)
    report = build_funnel_report(
        items, since=_SINCE, until=_NOW, loki_url=LOKI_URL, repos=[_REPO], loki_totals=totals
    )
    cohort = report.cohorts[0]
    step_ready = _step(cohort, "Ready to plan PR open")

    assert cohort.missing_result_lines == 1
    assert report.missing_result_lines == 1
    assert (cohort.total_tokens, cohort.total_cost_usd_micros) == (2000, 4000)
    assert step_ready.n == 3
    assert step_ready.passed == 2
    assert step_ready.tokens_per_success == pytest.approx(1000.0)
    assert step_ready.cost_usd_micros_per_success == pytest.approx(2000.0)
    assert {item.item: item.new_to_staged_tokens for item in cohort.items} == {
        11: 1000,
        12: 1000,
        13: 0,
    }
    text = render_funnel_report(report)
    assert "no result line: 1" in text.lower() or "missing result line" in text.lower()


def test_plan_funnel_queries_use_result_lines_and_repo_filter() -> None:
    """Planned LogQL queries build cleanly over `RESULT_LINES` with optional repo filter."""
    queries = plan_funnel_queries(RepoRef(_REPO), window="24h")
    assert len(queries) == 3
    assert all("sum by (repo, roadmap_job, item)" in q.expr for q in queries)
    assert all("example/app" in q.expr for q in queries)
