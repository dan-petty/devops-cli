"""The lanes of the service: each lane runs its own rows, keeps its own schedule and uses its own
clone (#981, #5553). The lane of intake reads every issue through the listing snapshot (#3670),
and each other lane through a snapshot of its own (#4854).
"""

from __future__ import annotations

import asyncio
import threading
from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, datetime, timedelta
from functools import partial
from pathlib import Path
from typing import Any

import pytest

from devops_cli.config.constants import CONST_SERVICE_METRIC_QUEUE_DEPTH
from devops_cli.config.settings import ServiceConfig
from devops_cli.roadmap.run import (
    MODEL_LANE_ROWS,
    STATUS_LANE_ROWS,
    TRIAGE_LANE_ROWS,
    JobOutcome,
    JobRow,
    run_due_jobs,
    service_job,
    service_jobs,
)
from devops_cli.roadmap.stores.github_store import GitHubRoadmapStore
from devops_cli.roadmap.stores.listing_snapshot import (
    FileSnapshotStore,
    IncrementalListing,
    SnapshotStore,
)
from devops_cli.roadmap.stores.store import RoadmapStore, install_roadmap_store
from devops_cli.server.service import ServiceManager, TriggerBatch
from devops_cli.telemetry.metrics import GLOBAL_METRICS
from tests.support.fakes.github import RunnerSession
from tests.support.fakes.roadmap_store import InMemoryRoadmapStore
from tests.support.roadmap_run import (
    NOW,
    OPENED,
    POLL,
    POLL_KEY,
    REPO,
    bare_remote,
    commit_to_bare,
    head_of_clone,
    labeled_changes,
    lane_table,
    poll_round,
    read_schedule,
    recorded,
    serve_as,
    serve_over,
    service_github,
    stamp_successes,
)
from tests.support.waits import THREAD_HANDOFF_BOUND_SECONDS

pytestmark = pytest.mark.usefixtures("keyring_store")


def _rows_of(job: Any) -> set[str]:
    """The names of the rows that the lane job `job` of `service_jobs` runs."""
    return {row.name for row in job.keywords["table"]}


def _lanes_within(jobs: Mapping[str, Any], rows: Sequence[JobRow]) -> list[str]:
    """The lanes of `jobs` that run only rows of `rows`."""
    names = {row.name for row in rows}
    return [lane for lane, job in jobs.items() if _rows_of(job) <= names]


def _lane_of(jobs: Mapping[str, Any], row: str) -> str:
    """The lane of `jobs` that runs the row `row`."""
    (lane,) = (lane for lane, job in jobs.items() if row in _rows_of(job))
    return lane


@pytest.mark.usefixtures("roadmap_bot")
def test_a_poll_of_the_lanes_of_the_rows_that_call_no_model_reads_no_change_and_sends_no_request(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """No row that calls no model has a due rule, so the poll of their lanes reads no change: with
    nothing due by its interval, a round sends no request, and reads no roadmap file as it opens
    the store."""
    github = service_github(labeled_changes(2, "alice"))
    serve_over(tmp_path, monkeypatch, github)
    jobs = service_jobs(tmp_path)
    for lane in _lanes_within(jobs, STATUS_LANE_ROWS):
        jobs[lane](POLL)
    assert [args for args in github.calls if "rate_limit" not in " ".join(args)] == []


@pytest.mark.usefixtures("roadmap_bot")
def test_a_poll_of_the_lanes_of_the_model_rows_when_not_due_reads_no_change_and_sends_no_request(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """No model row but intake has a due rule, so the poll of their lanes reads no change: with
    nothing due by its interval, a round sends no request, and reads no roadmap file as it opens
    the store (#1534)."""
    github = service_github(labeled_changes(2, "alice"))
    serve_over(tmp_path, monkeypatch, github)
    recent = datetime.now(UTC) - timedelta(minutes=1)
    stamp_successes(
        tmp_path,
        refine=recent,
        retitle=recent,
        stage=recent,
        fix_plan=recent,
        alternatives=recent,
    )
    jobs = service_jobs(tmp_path)
    for lane in _lanes_within(jobs, MODEL_LANE_ROWS):
        jobs[lane](POLL)
    assert [args for args in github.calls if "rate_limit" not in " ".join(args)] == []


@pytest.mark.usefixtures("roadmap_bot")
def test_each_lane_reads_every_issue_through_its_own_snapshot(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test first for #3670, #4854 and #5553: the lane of intake opens its store with the listing
    snapshot that the Service keeps in its state directory, as the scoped intake does. Each other
    lane opens its store with a snapshot in a directory of its own, so each snapshot has one
    writer."""
    github = service_github([])
    serve_over(tmp_path, monkeypatch, github, stamped=False)
    rows = (*STATUS_LANE_ROWS, *TRIAGE_LANE_ROWS, *MODEL_LANE_ROWS)
    recent = datetime.now(UTC) - timedelta(minutes=1)
    stamp_successes(tmp_path, **{row.name: recent for row in rows})
    snapshots: list[SnapshotStore | None] = []

    def store(repo: str, *, listing: IncrementalListing | None = None, **_: Any) -> RoadmapStore:
        snapshots.append(None if listing is None else listing.snapshots)
        return GitHubRoadmapStore(repo, runner=github, session=RunnerSession(github))

    install_roadmap_store(store)
    jobs = service_jobs(tmp_path)
    for job in jobs.values():
        job(POLL)
    intake_lane = _lane_of(jobs, "intake")
    assert snapshots == [
        FileSnapshotStore(tmp_path / ("listing" if lane == intake_lane else f"listing-{lane}"))
        for lane in jobs
    ]


@pytest.mark.usefixtures("roadmap_bot")
def test_a_lane_round_with_a_kept_snapshot_reads_only_the_changed_issues(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test first for #4854: the first round of the lane of `stage_ready` reads the whole listing
    and keeps a snapshot. The next round reads only the issues changed since its watermark, one
    request, and not every page again."""
    github = service_github([])
    serve_over(tmp_path, monkeypatch, github, stamped=False)
    install_roadmap_store(
        lambda repo, *, listing=None, **_: GitHubRoadmapStore(
            repo, runner=github, session=RunnerSession(github), listing=listing
        )
    )
    recent = datetime.now(UTC) - timedelta(minutes=1)
    others = {row.name: recent for row in STATUS_LANE_ROWS if row.name != "stage_ready"}
    jobs = service_jobs(tmp_path)
    lane = jobs[_lane_of(jobs, "stage_ready")]
    for _ in range(2):
        stamp_successes(tmp_path, **others)
        lane(POLL)
    listings = [
        args[-1].partition("?")[2] for args in github.calls if f"repos/{REPO}/issues?" in args[-1]
    ]
    assert [query.partition("&since=")[0] for query in listings] == [
        "state=all&per_page=100",
        "state=all&sort=updated&direction=desc",
    ]


def test_a_blocked_model_lane_holds_back_none_of_the_status_lanes_rounds(
    seeded_store: InMemoryRoadmapStore, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A refine round blocks on a slow model. In the same repository the status lane still runs
    the metrics row and the implement row a poll makes due, while the refine round is still
    running (#2757)."""
    monkeypatch.setenv("DEVOPS_CLI_DATA_DIR", str(tmp_path))
    refining, model_answers = threading.Event(), threading.Event()
    refine_released: list[bool] = []
    measured: list[str] = []
    during_refine: list[bool] = []

    def implement(**_: Any) -> JobOutcome:
        # Records whether the model had not yet answered when the row ran.
        during_refine.append(not model_answers.is_set())
        return JobOutcome()

    def refine(**_: Any) -> JobOutcome:
        refining.set()
        # Records that the test, not the bound, ended each wait on the slow model.
        refine_released.append(model_answers.wait(timeout=THREAD_HANDOFF_BOUND_SECONDS))
        return JobOutcome()

    lanes = {
        "status": partial(
            service_job,
            table=lane_table(
                STATUS_LANE_ROWS,
                metrics=recorded(measured, "metrics"),
                implement=recorded(measured, "implement", implement),
            ),
            lane="status",
        ),
        "model": partial(
            service_job, table=lane_table(MODEL_LANE_ROWS, refine=refine), lane="model"
        ),
    }
    manager = ServiceManager(
        ServiceConfig(repos=[REPO]), {}, lanes, lambda: datetime.now(UTC), asyncio.sleep
    )
    status_lane, model_lane = (manager.workers[(REPO, lane)] for lane in lanes)
    for worker in manager.workers.values():
        worker.start()
    manager.enqueue_trigger(REPO, "poll", "", "")
    assert refining.wait(timeout=THREAD_HANDOFF_BOUND_SECONDS)
    measured_while_refining = status_lane.wait_active(THREAD_HANDOFF_BOUND_SECONDS)
    refine_still_running = model_lane.is_active()
    model_answers.set()
    asyncio.run(manager.drain_and_stop())
    assert (
        measured_while_refining,
        measured,
        during_refine,
        refine_still_running,
        bool(refine_released) and all(refine_released),
    ) == (True, ["metrics", "implement"], [True], True, True)


def test_a_blocked_stage_round_holds_back_no_refine_round_of_the_same_repository(
    seeded_store: InMemoryRoadmapStore, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test first for #5553: the lanes that `service_jobs` builds keep `stage` and `refine` apart.
    A stage round blocks on a slow model, and a poll makes `refine` due for the same repository:
    a refine round runs and ends while the stage round still runs."""
    monkeypatch.setenv("DEVOPS_CLI_DATA_DIR", str(tmp_path))
    staging, model_answers, refined = threading.Event(), threading.Event(), threading.Event()
    stage_released: list[bool] = []

    def stage(**_: Any) -> JobOutcome:
        staging.set()
        # Records that the test, not the bound, ended the wait on the slow model.
        stage_released.append(model_answers.wait(timeout=THREAD_HANDOFF_BOUND_SECONDS))
        return JobOutcome()

    def refine(**_: Any) -> JobOutcome:
        refined.set()
        return JobOutcome()

    built = service_jobs(tmp_path)
    tables = {lane: job.keywords["table"] for lane, job in built.items()}
    lanes = {
        lane: partial(job, table=lane_table(tables[lane], stage=stage, refine=refine))
        for lane, job in built.items()
    }
    manager = ServiceManager(
        ServiceConfig(repos=[REPO]), {}, lanes, lambda: datetime.now(UTC), asyncio.sleep
    )
    (stage_lane,) = (lane for lane, rows in tables.items() if "stage" in {r.name for r in rows})
    (refine_lane,) = (lane for lane, rows in tables.items() if "refine" in {r.name for r in rows})
    for worker in manager.workers.values():
        worker.start()
    manager.enqueue_trigger(REPO, "poll", "", "")
    assert staging.wait(timeout=THREAD_HANDOFF_BOUND_SECONDS)
    refine_ran = refined.wait(timeout=THREAD_HANDOFF_BOUND_SECONDS)
    refine_round_ended = manager.workers[(REPO, refine_lane)].wait_active(
        THREAD_HANDOFF_BOUND_SECONDS
    )
    stage_still_running = manager.workers[(REPO, stage_lane)].is_active()
    model_answers.set()
    asyncio.run(manager.drain_and_stop())
    assert (
        refine_ran,
        refine_round_ended,
        stage_still_running,
        bool(stage_released) and all(stage_released),
    ) == (True, True, True, True)


def test_opened_issue_webhook_runs_triage_lane_while_model_lane_blocked_and_reports_queue_depth(
    seeded_store: InMemoryRoadmapStore, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A refine round blocks on a slow model in the model lane. In the same repository the triage
    lane runs intake for an opened issue without waiting, and reports its queue depth (#1534)."""
    monkeypatch.setenv("DEVOPS_CLI_DATA_DIR", str(tmp_path))
    refining, model_answers = threading.Event(), threading.Event()
    refine_released: list[bool] = []
    triage_ran: list[str] = []
    during_refine: list[bool] = []

    def intake(**_: Any) -> JobOutcome:
        during_refine.append(not model_answers.is_set())
        triage_ran.append("intake")
        return JobOutcome()

    def refine(**_: Any) -> JobOutcome:
        refining.set()
        refine_released.append(model_answers.wait(timeout=THREAD_HANDOFF_BOUND_SECONDS))
        return JobOutcome()

    lanes = {
        "triage": partial(
            service_job, table=lane_table(TRIAGE_LANE_ROWS, intake=intake), lane="triage"
        ),
        "model": partial(
            service_job, table=lane_table(MODEL_LANE_ROWS, refine=refine), lane="model"
        ),
    }
    manager = ServiceManager(
        ServiceConfig(repos=[REPO]), {}, lanes, lambda: datetime.now(UTC), asyncio.sleep
    )
    triage_worker = manager.workers[(REPO, "triage")]
    model_worker = manager.workers[(REPO, "model")]
    for worker in manager.workers.values():
        worker.start()

    manager.enqueue_trigger(REPO, "poll", "", "")
    assert refining.wait(timeout=THREAD_HANDOFF_BOUND_SECONDS)
    assert triage_worker.wait_active(THREAD_HANDOFF_BOUND_SECONDS)
    triage_ran.clear()
    during_refine.clear()

    manager.enqueue_trigger(REPO, "webhook", "issues", "opened")
    triage_finished = triage_worker.wait_active(THREAD_HANDOFF_BOUND_SECONDS)
    refine_still_running = model_worker.is_active()
    model_answers.set()
    asyncio.run(manager.drain_and_stop())

    triage_depth = GLOBAL_METRICS.get_gauge_value(
        CONST_SERVICE_METRIC_QUEUE_DEPTH, labels={"lane": "triage", "repo": REPO}
    )
    assert (
        triage_finished,
        triage_ran,
        during_refine,
        refine_still_running,
        triage_depth,
        bool(refine_released) and all(refine_released),
    ) == (True, ["intake"], [True], True, 0.0, True)


def test_the_implement_row_is_due_on_the_status_lane_by_its_interval_and_by_no_hint(
    seeded_store: InMemoryRoadmapStore, tmp_path: Path
) -> None:
    """A poll makes the row due on the status lane seven minutes after its last success and not
    before. A webhook batch reaches the lane too, and makes the row due no sooner, since the row
    has no batch key (#2757)."""

    def ran(batch: dict[tuple[str, str, str], int], **stamps: datetime) -> tuple[str, ...]:
        stamp_successes(tmp_path, **stamps)
        return poll_round(seeded_store, tmp_path, table=lane_table(STATUS_LANE_ROWS), batch=batch)

    fresh = {
        "metrics": NOW - timedelta(minutes=1),
        "stage_ready": NOW - timedelta(minutes=1),
        "stage": NOW - timedelta(minutes=1),
        "release_comments": NOW - timedelta(minutes=1),
        "github_status": NOW - timedelta(minutes=1),
        "cloudflare_status": NOW - timedelta(minutes=1),
        "pr_conflicts": NOW - timedelta(minutes=1),
    }
    first = ran({POLL_KEY: 1})
    too_soon = ran({POLL_KEY: 1}, **fresh, implement=NOW - timedelta(minutes=6, seconds=59))
    seven_minutes = ran({POLL_KEY: 1}, **fresh, implement=NOW - timedelta(minutes=7))
    hinted = ran({OPENED: 1}, **fresh, implement=NOW - timedelta(minutes=2))

    assert (first, too_soon, seven_minutes, hinted) == (
        (
            "metrics",
            "implement",
            "stage_ready",
            "stage",
            "release_comments",
            "github_status",
            "cloudflare_status",
            "pr_conflicts",
        ),
        (),
        ("implement",),
        (),
    )


def test_each_lanes_success_stays_in_schedule_json_when_their_rounds_interleave(
    seeded_store: InMemoryRoadmapStore, tmp_path: Path
) -> None:
    """A triage-lane round and a model-lane round record their jobs while a status-lane round
    is running metrics, which had read `schedule.json` before them: the success of metrics and the
    one of implement, which follows it, keep theirs (#1534)."""
    later = NOW + timedelta(seconds=1)

    def metrics(**_: Any) -> JobOutcome:
        triage_round = run_due_jobs(
            REPO,
            seeded_store,
            batch={POLL_KEY: 1},
            table=lane_table(TRIAGE_LANE_ROWS),
            data_dir=tmp_path,
            now=later,
        )
        model_round = run_due_jobs(
            REPO,
            seeded_store,
            batch={POLL_KEY: 1},
            table=lane_table(MODEL_LANE_ROWS),
            data_dir=tmp_path,
            now=later,
        )
        assert (triage_round, model_round) == (
            ("intake",),
            ("retitle", "fix_plan", "refine", "alternatives"),
        )
        return JobOutcome()

    ran = run_due_jobs(
        REPO,
        seeded_store,
        batch={POLL_KEY: 1},
        table=lane_table(STATUS_LANE_ROWS, metrics=metrics),
        data_dir=tmp_path,
        now=NOW,
    )
    assert (ran, read_schedule(tmp_path)) == (
        (
            "metrics",
            "implement",
            "stage_ready",
            "stage",
            "release_comments",
            "github_status",
            "cloudflare_status",
            "pr_conflicts",
        ),
        {
            "intake": later.isoformat(),
            "refine": later.isoformat(),
            "retitle": later.isoformat(),
            "fix_plan": later.isoformat(),
            "alternatives": later.isoformat(),
            "metrics": NOW.isoformat(),
            "implement": NOW.isoformat(),
            "stage_ready": NOW.isoformat(),
            "stage": NOW.isoformat(),
            "release_comments": NOW.isoformat(),
            "github_status": NOW.isoformat(),
            "cloudflare_status": NOW.isoformat(),
            "pr_conflicts": NOW.isoformat(),
        },
    )


def test_two_lanes_never_use_the_same_working_tree(
    seeded_store: InMemoryRoadmapStore,
    tmp_path: Path,
    child_argvs: list[list[str]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test first for #5553: the lanes of `stage` and `refine`, which `service_jobs` builds, each
    work in a clone of their own at origin's tip of the default branch. A round of the lane of
    `refine` leaves a change in the clone of `stage` alone, where a checkout of that clone would
    discard it."""
    data_dir = tmp_path / "data"
    monkeypatch.setenv("DEVOPS_CLI_DATA_DIR", str(data_dir))
    bare = bare_remote(tmp_path)
    serve_as(f"https://github.com/{REPO}.git", bare)
    main_tip = commit_to_bare(bare, "main", "main\n")
    seen: dict[str, tuple[Path, tuple[str, str]]] = {}

    def record(job: str) -> Callable[..., JobOutcome]:
        def run_job(*, clone_path: Path | None = None, **_: Any) -> JobOutcome:
            assert clone_path is not None
            seen[job] = (clone_path, head_of_clone(clone_path))
            return JobOutcome()

        return run_job

    built = service_jobs(data_dir / "roadmap")
    lanes = {
        row: partial(
            built[_lane_of(built, row)],
            table=lane_table(
                built[_lane_of(built, row)].keywords["table"],
                needs_clone=True,
                **{row: record(row)},
            ),
        )
        for row in ("stage", "refine")
    }
    batch = TriggerBatch(repo=REPO, counts={OPENED: 1}, first_at=NOW, last_at=NOW)
    lanes["stage"](batch)
    in_progress = seen["stage"][0] / "f.txt"
    in_progress.write_text("work in progress\n")
    lanes["refine"](batch)
    stage_tree, refine_tree = seen["stage"][0], seen["refine"][0]
    assert (
        stage_tree != refine_tree,
        stage_tree.parent == refine_tree.parent,
        seen["stage"][1][0],
        seen["refine"][1][0],
        in_progress.read_text(),
    ) == (True, True, main_tip, main_tip, "work in progress\n")
