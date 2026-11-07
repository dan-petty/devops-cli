"""The lanes of the service: the status, triage and model lanes run their own rows, keep their own
schedule and use their own clone (#981).
"""

from __future__ import annotations

import asyncio
import threading
from collections.abc import Callable, Sequence
from datetime import UTC, datetime, timedelta
from functools import partial
from pathlib import Path
from typing import Any

import pytest

from devops_cli.config.constants import (
    CONST_ROADMAP_RUN_CLONE_DIRNAME,
    CONST_ROADMAP_RUN_MODEL_CLONE_DIRNAME,
    CONST_ROADMAP_RUN_TRIAGE_CLONE_DIRNAME,
    CONST_SERVICE_LANE_MODEL,
    CONST_SERVICE_LANE_STATUS,
    CONST_SERVICE_LANE_TRIAGE,
    CONST_SERVICE_METRIC_QUEUE_DEPTH,
)
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
from devops_cli.server.service import ServiceManager
from devops_cli.telemetry.metrics import GLOBAL_METRICS
from tests.support.fakes.roadmap_store import InMemoryRoadmapStore
from tests.support.roadmap_run import (
    NOW,
    OPENED,
    POLL,
    POLL_KEY,
    REPO,
    REPO_DIR,
    bare_remote,
    commit_to_bare,
    head_of_clone,
    labeled_changes,
    lane_table,
    poll_round,
    read_schedule,
    recorded,
    serve_over,
    service_github,
    stamp_successes,
)
from tests.support.waits import THREAD_HANDOFF_BOUND_SECONDS

pytestmark = pytest.mark.usefixtures("keyring_store")


@pytest.mark.usefixtures("roadmap_bot")
def test_a_status_lane_poll_reads_no_change_and_sends_no_request(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """No status-lane row has a due rule, so its poll reads no change: with nothing due by its
    interval, the round sends no request, and reads no roadmap file as it opens the store."""
    github = service_github(labeled_changes(2, "alice"))
    serve_over(tmp_path, monkeypatch, github)
    service_jobs(tmp_path)[CONST_SERVICE_LANE_STATUS](POLL)
    assert [args for args in github.calls if "rate_limit" not in " ".join(args)] == []


@pytest.mark.usefixtures("roadmap_bot")
def test_a_model_lane_poll_when_not_due_reads_no_change_and_sends_no_request(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """No model-lane row has a due rule, so its poll reads no change: with nothing due by its
    interval, the round sends no request, and reads no roadmap file as it opens the store (#1534)."""
    github = service_github(labeled_changes(2, "alice"))
    serve_over(tmp_path, monkeypatch, github)
    recent = datetime.now(UTC) - timedelta(minutes=1)
    stamp_successes(
        tmp_path,
        refine=recent,
        retitle=recent,
        stage=recent,
        alternatives=recent,
    )
    service_jobs(tmp_path)[CONST_SERVICE_LANE_MODEL](POLL)
    assert [args for args in github.calls if "rate_limit" not in " ".join(args)] == []


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
        CONST_SERVICE_LANE_STATUS: partial(
            service_job,
            table=lane_table(
                STATUS_LANE_ROWS,
                metrics=recorded(measured, "metrics"),
                implement=recorded(measured, "implement", implement),
            ),
            clone_dirname=CONST_ROADMAP_RUN_CLONE_DIRNAME,
        ),
        CONST_SERVICE_LANE_MODEL: partial(
            service_job,
            table=lane_table(MODEL_LANE_ROWS, refine=refine),
            clone_dirname=CONST_ROADMAP_RUN_MODEL_CLONE_DIRNAME,
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
        CONST_SERVICE_LANE_TRIAGE: partial(
            service_job,
            table=lane_table(TRIAGE_LANE_ROWS, intake=intake),
            clone_dirname=CONST_ROADMAP_RUN_TRIAGE_CLONE_DIRNAME,
        ),
        CONST_SERVICE_LANE_MODEL: partial(
            service_job,
            table=lane_table(MODEL_LANE_ROWS, refine=refine),
            clone_dirname=CONST_ROADMAP_RUN_MODEL_CLONE_DIRNAME,
        ),
    }
    manager = ServiceManager(
        ServiceConfig(repos=[REPO]), {}, lanes, lambda: datetime.now(UTC), asyncio.sleep
    )
    triage_worker = manager.workers[(REPO, CONST_SERVICE_LANE_TRIAGE)]
    model_worker = manager.workers[(REPO, CONST_SERVICE_LANE_MODEL)]
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
        CONST_SERVICE_METRIC_QUEUE_DEPTH, labels={"lane": CONST_SERVICE_LANE_TRIAGE, "repo": REPO}
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
        "release_comments": NOW - timedelta(minutes=1),
    }
    first = ran({POLL_KEY: 1})
    too_soon = ran({POLL_KEY: 1}, **fresh, implement=NOW - timedelta(minutes=6, seconds=59))
    seven_minutes = ran({POLL_KEY: 1}, **fresh, implement=NOW - timedelta(minutes=7))
    hinted = ran({OPENED: 1}, **fresh, implement=NOW - timedelta(minutes=2))

    assert (first, too_soon, seven_minutes, hinted) == (
        ("metrics", "implement", "stage_ready", "release_comments"),
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
            ("refine", "retitle", "stage", "alternatives"),
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
        ("metrics", "implement", "stage_ready", "release_comments"),
        {
            "intake": later.isoformat(),
            "refine": later.isoformat(),
            "retitle": later.isoformat(),
            "stage": later.isoformat(),
            "alternatives": later.isoformat(),
            "metrics": NOW.isoformat(),
            "implement": NOW.isoformat(),
            "stage_ready": NOW.isoformat(),
            "release_comments": NOW.isoformat(),
        },
    )


def test_each_lane_updates_only_its_own_clone(
    seeded_store: InMemoryRoadmapStore, tmp_path: Path, child_argvs: list[list[str]]
) -> None:
    """The status lane's metrics works in `clone` and the model lane's refine in `model-clone`,
    each at origin's tip of the default branch. A model-lane round leaves a change in `clone`
    alone, where a checkout of that clone would discard it."""
    bare = bare_remote(tmp_path)
    main_tip = commit_to_bare(bare, "main", "main\n")
    data_dir = tmp_path / "data"
    seen: dict[str, tuple[Path, tuple[str, str]]] = {}

    def record(job: str) -> Callable[..., JobOutcome]:
        def run_job(*, clone_path: Path | None = None, **_: Any) -> JobOutcome:
            assert clone_path is not None
            seen[job] = (clone_path, head_of_clone(clone_path))
            return JobOutcome()

        return run_job

    def lane_round(table: Sequence[JobRow], clone_dirname: str) -> tuple[str, ...]:
        return run_due_jobs(
            REPO,
            seeded_store,
            batch={OPENED: 1},
            table=table,
            data_dir=data_dir,
            remote_url=str(bare),
            now=NOW,
            clone_dirname=clone_dirname,
        )

    lane_round(
        lane_table(STATUS_LANE_ROWS, needs_clone=True, metrics=record("metrics")),
        CONST_ROADMAP_RUN_CLONE_DIRNAME,
    )
    in_progress = seen["metrics"][0] / "f.txt"
    in_progress.write_text("work in progress\n")
    lane_round(
        lane_table(MODEL_LANE_ROWS, needs_clone=True, refine=record("refine")),
        CONST_ROADMAP_RUN_MODEL_CLONE_DIRNAME,
    )
    repo_dir = data_dir / REPO_DIR
    assert (seen, in_progress.read_text()) == (
        {
            "metrics": (repo_dir / "clone", (main_tip, "main")),
            "refine": (repo_dir / "model-clone", (main_tip, "main")),
        },
        "work in progress\n",
    )
