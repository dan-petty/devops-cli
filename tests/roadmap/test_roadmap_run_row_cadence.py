"""The cadence of the rows intake, stage, fix_plan, refine and alternatives: each row is due by the
interval of its settings, and by its backlog interval while the queue that its last round recorded
holds the threshold or more items; each runner gives its queue, and the round keeps it in
`queues.json` (#5470)."""

from __future__ import annotations

import json
from datetime import timedelta
from typing import TYPE_CHECKING, Any

import pytest

from devops_cli.exceptions import RoadmapRunError
from devops_cli.roadmap.alternatives import AlternativesPlan, Coverage
from devops_cli.roadmap.run import JobOutcome, JobRow, build_stub_table, run_due_jobs
from devops_cli.roadmap.stage.stage_verify import PLAN_NEEDS_FIX_LABEL
from tests.support.roadmap_jobs import due_job_runner
from tests.support.roadmap_run import (
    NOW,
    POLL_KEY,
    REPO,
    REPO_DIR,
    IntakeModel,
    make_candidates,
    recorded,
    run_intake_adapter,
    stamp_successes,
)

if TYPE_CHECKING:
    from collections.abc import Callable
    from datetime import datetime
    from pathlib import Path

    from tests.support.fakes.roadmap_store import InMemoryRoadmapStore

pytestmark = pytest.mark.usefixtures("keyring_store")

QUEUES = "queues.json"


@pytest.fixture
def backlog_stage(monkeypatch: pytest.MonkeyPatch) -> None:
    """The backlog rule that the issue proposes for stage: 13 minutes at 50 or more Ready items."""
    monkeypatch.setenv("DEVOPS_CLI_ROADMAP_STAGE_BACKLOG_INTERVAL_MINUTES", "13")
    monkeypatch.setenv("DEVOPS_CLI_ROADMAP_STAGE_BACKLOG_THRESHOLD", "50")


def _write_queues(tmp_path: Path, text: str) -> None:
    path = tmp_path / REPO_DIR / QUEUES
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _read_queues(tmp_path: Path) -> Any:
    return json.loads((tmp_path / REPO_DIR / QUEUES).read_text(encoding="utf-8"))


def _stage_due(store: InMemoryRoadmapStore, tmp_path: Path, minutes: int) -> bool:
    """Whether a dry round lists stage when its last success was `minutes` ago, and intake ran a
    minute ago."""
    stamp_successes(
        tmp_path, intake=NOW - timedelta(minutes=1), stage=NOW - timedelta(minutes=minutes)
    )
    table = build_stub_table(include_stage=True)
    due = run_due_jobs(REPO, store, table=table, data_dir=tmp_path, dry_run=True, now=NOW)
    return "stage" in due


def _round(
    store: InMemoryRoadmapStore,
    tmp_path: Path,
    table: tuple[JobRow, ...],
    *,
    now: datetime = NOW,
) -> tuple[str, ...]:
    return run_due_jobs(REPO, store, {POLL_KEY: 1}, table=table, data_dir=tmp_path, now=now)


# ── The interval from the settings ────────────────────────────────────────────


def test_a_variable_changes_the_interval_of_the_next_round(
    seeded_store: InMemoryRoadmapStore, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The round reads the settings at its start, so the next round uses a new interval with no
    restart of the Service."""
    before = _stage_due(seeded_store, tmp_path, 20)
    monkeypatch.setenv("DEVOPS_CLI_ROADMAP_STAGE_INTERVAL_MINUTES", "20")

    assert (
        before,
        _stage_due(seeded_store, tmp_path, 20),
        _stage_due(seeded_store, tmp_path, 19),
    ) == (
        False,
        True,
        False,
    )


# ── The backlog rule ──────────────────────────────────────────────────────────


@pytest.mark.usefixtures("backlog_stage")
def test_a_recorded_queue_at_the_threshold_makes_stage_due_at_the_backlog_interval(
    seeded_store: InMemoryRoadmapStore, tmp_path: Path
) -> None:
    _write_queues(tmp_path, json.dumps({"stage": 50}))

    assert (_stage_due(seeded_store, tmp_path, 13), _stage_due(seeded_store, tmp_path, 12)) == (
        True,
        False,
    )


@pytest.mark.usefixtures("backlog_stage")
def test_a_queue_below_the_threshold_or_no_record_keeps_the_interval(
    seeded_store: InMemoryRoadmapStore, tmp_path: Path
) -> None:
    """A queue of 49 keeps 37 minutes, and so does a repository whose record holds no stage
    queue."""
    _write_queues(tmp_path, json.dumps({"stage": 49}))
    below = (_stage_due(seeded_store, tmp_path, 36), _stage_due(seeded_store, tmp_path, 37))
    _write_queues(tmp_path, json.dumps({"refine": 500}))
    unknown = (_stage_due(seeded_store, tmp_path, 13), _stage_due(seeded_store, tmp_path, 37))

    assert (below, unknown) == ((False, True), (False, True))


# ── The record of the queue ───────────────────────────────────────────────────


@pytest.mark.usefixtures("backlog_stage")
def test_a_success_records_its_queue_and_the_next_round_uses_it(
    seeded_store: InMemoryRoadmapStore, tmp_path: Path
) -> None:
    """A first round runs stage, which gives a queue of 177: the record holds it, and stage is due
    again 13 minutes later, not 12. The intake stub gives no queue, so the record holds none for
    it."""
    ran: list[str] = []
    table = build_stub_table({"stage": recorded(ran, "stage", lambda **_: JobOutcome(queue=177))})

    first = _round(seeded_store, tmp_path, table)
    recorded_queues = _read_queues(tmp_path)
    at_12 = _round(seeded_store, tmp_path, table, now=NOW + timedelta(minutes=12))
    at_13 = _round(seeded_store, tmp_path, table, now=NOW + timedelta(minutes=13))

    assert (first, recorded_queues, at_12, at_13) == (
        ("intake", "stage"),
        {"stage": 177},
        (),
        ("stage",),
    )


def test_a_failed_row_and_an_outcome_with_no_queue_keep_the_record(
    seeded_store: InMemoryRoadmapStore, tmp_path: Path
) -> None:
    """A stage round that gives no queue and a refine round that fails leave both queues as the
    last rounds recorded them."""
    _write_queues(tmp_path, json.dumps({"stage": 177, "refine": 583}))

    def fails(**_: Any) -> JobOutcome:
        raise RuntimeError("the model is down")

    table = build_stub_table({"stage": lambda **_: JobOutcome(), "refine": fails})

    with pytest.raises(RoadmapRunError, match="refine"):
        _round(seeded_store, tmp_path, table)

    assert _read_queues(tmp_path) == {"stage": 177, "refine": 583}


def test_an_unreadable_record_stops_the_round_and_names_the_file(
    seeded_store: InMemoryRoadmapStore, tmp_path: Path
) -> None:
    ran: list[str] = []
    _write_queues(tmp_path, "{not json")
    table = build_stub_table({"stage": recorded(ran, "stage")})

    with pytest.raises(RoadmapRunError, match=QUEUES):
        _round(seeded_store, tmp_path, table)

    assert ran == []


def test_a_lane_with_no_cadence_row_reads_no_record(
    seeded_store: InMemoryRoadmapStore, tmp_path: Path
) -> None:
    """The status lane has no row with a cadence, so an unreadable record does not stop it."""
    ran: list[str] = []
    _write_queues(tmp_path, "{not json")
    table = (JobRow(name="metrics", batch_keys=(POLL_KEY,), runner=recorded(ran, "metrics")),)

    assert (_round(seeded_store, tmp_path, table), ran) == (("metrics",), ["metrics"])


# ── The queue of each runner ──────────────────────────────────────────────────


def test_the_intake_row_counts_every_candidate_of_its_round(tmp_path: Path) -> None:
    """Twelve candidates and a limit of five: the round decides five and leaves seven, and its
    queue is twelve."""
    store, _, _ = make_candidates(12)

    outcome = run_intake_adapter(
        store, repo=REPO, repo_dir=tmp_path, now=NOW, model=IntakeModel(), limit=5
    )

    assert outcome.queue == 12


@pytest.mark.parametrize(("mode", "queue"), [("off", None), ("plan", 2)])
def test_the_fix_plan_row_counts_the_open_plans_with_the_label_unless_it_is_off(
    mode: str,
    queue: int | None,
    seeded_store: InMemoryRoadmapStore,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """In the mode `off` the row reads nothing and gives no queue. In the mode `plan` it gives
    the open pull requests that hold `plan/needs-fix`."""
    monkeypatch.setenv("DEVOPS_CLI_ROADMAP_FIX_PLAN_MODE", mode)
    for title in ("plan one", "plan two"):
        seeded_store.seed_issue(title, pull_request=True, labels=(PLAN_NEEDS_FIX_LABEL,))
    seeded_store.seed_issue("plan three", pull_request=True)
    run: Callable[..., JobOutcome] = due_job_runner("fix_plan")

    outcome = run(store=seeded_store, repo=REPO, clone_path=tmp_path)

    assert outcome.queue == queue


def test_the_alternatives_queue_is_the_count_of_unchecked_items_or_none() -> None:
    """A plan with coverage gives its unchecked items; a plan of a check that is off has no
    coverage and gives no queue."""
    covered = AlternativesPlan(repo=REPO, coverage=Coverage(unchecked=57, oldest_age=None))
    off = AlternativesPlan(repo=REPO, off_reason="no search provider")

    assert (covered.queue, off.queue) == (57, None)
