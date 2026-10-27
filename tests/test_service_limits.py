"""What stops the roadmap Service's GitHub requests: a refused identity, a spent hourly budget and
a job that fails every round (#2161).

All tests run in memory. The jobs and the request counter are the process edges the tests
replace; the engine, the budget and the ledger are real. A conditional read of an unchanged
listing is covered where the session keeps its ETags (`tests/test_github_session.py`).
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable, Mapping
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from devops_cli.config.constants import (
    CONST_SERVICE_BUDGET_WINDOW_SECONDS,
    CONST_SERVICE_METRIC_IDENTITY_REFUSED,
)
from devops_cli.config.defaults import DEFAULT_SERVICE_MAX_FAILED_ROUNDS
from devops_cli.config.settings import ServiceConfig
from devops_cli.exceptions import RoadmapRunError
from devops_cli.exceptions.git import GitHubOperationError, GitHubUnauthenticatedError
from devops_cli.roadmap.memory_store import InMemoryRoadmapStore
from devops_cli.roadmap.run import (
    FailureLedger,
    JobOutcome,
    build_stub_table,
    identity_refused,
    run_due_jobs,
)
from devops_cli.server.service import RequestBudget, ServiceManager, TriggerBatch
from devops_cli.telemetry.metrics import GLOBAL_METRICS
from devops_cli.telemetry.tracer import reset_tracer
from tests.support.waits import THREAD_HANDOFF_BOUND_SECONDS, wait_until

REPO_A, REPO_B = "example-org/repo1", "example-org/repo2"
START = datetime(2026, 10, 9, 12, tzinfo=UTC)
_QUIET_SECONDS = 0.5
"""How long a test waits to see that nothing more starts."""
SUSPENDED = "gh: Sorry. Your account was suspended. (HTTP 403)"


@pytest.fixture(autouse=True)
def _reset_metrics() -> Any:
    GLOBAL_METRICS.reset()
    reset_tracer()
    yield
    reset_tracer()


class _Clock:
    def __init__(self, now: datetime = START) -> None:
        self.now = now

    def __call__(self) -> datetime:
        return self.now


class _Requests:
    """The count of requests the process sent, set by the test."""

    def __init__(self) -> None:
        self.count = 0

    def __call__(self) -> int:
        return self.count


def _suspended() -> GitHubUnauthenticatedError:
    return GitHubUnauthenticatedError(SUSPENDED)


def _manager(
    jobs: Mapping[str, Callable[[TriggerBatch], None]],
    *,
    clock: _Clock,
    requests: _Requests | None = None,
    per_hour: int = 500,
    poll_interval: int = 300,
) -> ServiceManager:
    manager = ServiceManager(
        config=ServiceConfig(
            repos=[REPO_A, REPO_B],
            machine_account="bot-account",
            poll_interval_seconds=poll_interval,
            github_requests_per_hour=per_hour,
        ),
        secrets={},
        jobs=jobs,
        clock=clock,
        sleep_func=asyncio.sleep,
        identity_refused=identity_refused,
        request_counter=requests or _Requests(),
    )
    for worker in manager.workers.values():
        worker.start()
    return manager


def _stop(manager: ServiceManager) -> None:
    for worker in manager.workers.values():
        worker.stop()
        worker.join(THREAD_HANDOFF_BOUND_SECONDS)


def _refusal_metric() -> float:
    return GLOBAL_METRICS.get_counter_value(
        CONST_SERVICE_METRIC_IDENTITY_REFUSED, labels={"identity": "bot-account"}
    )


# ── The identity ────────────────────────────────────────────────────────────────────────────


def test_a_suspended_identity_stops_every_job_of_every_repository(
    caplog: pytest.LogCaptureFixture,
) -> None:
    sent: list[str] = []

    def job(batch: TriggerBatch) -> None:
        sent.append(batch.repo)
        if batch.repo == REPO_A:
            raise _suspended()

    manager = _manager({"lane": job}, clock=_Clock())
    caplog.set_level(logging.ERROR, logger="devops_cli.server.service")
    try:
        manager.enqueue_trigger(REPO_A, "webhook", "issues", "labeled")
        assert wait_until(manager.pause.halted)
        for _ in range(3):
            manager.enqueue_trigger(REPO_A, "poll", "", "")
            manager.enqueue_trigger(REPO_B, "poll", "", "")
        assert not wait_until(lambda: len(sent) > 1, _QUIET_SECONDS)
    finally:
        _stop(manager)

    assert sent == [REPO_A]
    assert _refusal_metric() == 1
    lines = [r.getMessage() for r in caplog.records if "refused the identity" in r.getMessage()]
    assert len(lines) == 1
    assert "bot-account" in lines[0]


def test_a_second_refusal_raises_no_second_alert(caplog: pytest.LogCaptureFixture) -> None:
    manager = _manager({"lane": lambda batch: None}, clock=_Clock())
    caplog.set_level(logging.ERROR, logger="devops_cli.server.service")
    try:
        manager.pause.after(_suspended(), REPO_A)
        manager.pause.after(_suspended(), REPO_B)
    finally:
        _stop(manager)

    assert _refusal_metric() == 1
    assert len([r for r in caplog.records if r.levelno == logging.ERROR]) == 1


def test_a_round_that_fails_for_another_reason_halts_nothing() -> None:
    manager = _manager({"lane": lambda batch: None}, clock=_Clock())
    try:
        manager.pause.after(GitHubOperationError("GitHub gave a 500"), REPO_A)
        assert not manager.pause.halted()
        assert not manager.pause.holds()
    finally:
        _stop(manager)


def test_the_refusal_is_found_in_the_failures_a_round_groups(tmp_path: Path) -> None:
    store = InMemoryRoadmapStore()

    def refused(**_: Any) -> JobOutcome:
        raise _suspended()

    table = build_stub_table({"intake": refused})
    with pytest.raises(RoadmapRunError) as raised:
        run_due_jobs(
            REPO_A,
            store,
            {("webhook", "issues", "opened"): 1},
            table=table,
            data_dir=tmp_path,
            failures=FailureLedger(),
        )
    assert identity_refused(raised.value)
    assert not identity_refused(RoadmapRunError("a job failed", failed_jobs=["intake"]))


def test_a_refusal_ends_the_round_before_the_next_job_sends_a_request(tmp_path: Path) -> None:
    ran: list[str] = []

    def refused(**_: Any) -> JobOutcome:
        ran.append("intake")
        raise _suspended()

    def later(**_: Any) -> JobOutcome:
        ran.append("refine")
        return JobOutcome()

    table = build_stub_table({"intake": refused, "refine": later})
    due = {("webhook", "issues", "opened"): 1, ("webhook", "issues", "labeled"): 1}
    with pytest.raises(RoadmapRunError):
        run_due_jobs(REPO_A, InMemoryRoadmapStore(), due, table=table, data_dir=tmp_path)

    assert ran == ["intake"]


# ── The budget ──────────────────────────────────────────────────────────────────────────────


def test_the_budget_holds_the_rounds_when_the_last_hour_spent_it_and_frees_them_as_it_slides() -> (
    None
):
    clock, requests = _Clock(), _Requests()
    budget = RequestBudget(clock, 100, requests)
    requests.count = 60
    clock.now += timedelta(minutes=10)
    budget.record_round()
    assert not budget.holds()

    requests.count = 130
    clock.now += timedelta(minutes=10)
    budget.record_round()
    assert budget.spent() == 130
    assert budget.holds()

    clock.now = START + timedelta(seconds=CONST_SERVICE_BUDGET_WINDOW_SECONDS + 15 * 60)
    assert budget.spent() == 70
    assert not budget.holds()


def test_a_round_stays_under_the_hourly_budget() -> None:
    clock, requests = _Clock(), _Requests()
    started: list[str] = []

    def job(batch: TriggerBatch) -> None:
        started.append(batch.repo)
        requests.count += 40

    manager = _manager({"lane": job}, clock=clock, requests=requests, per_hour=100)
    try:
        for expected in (1, 2, 3):
            manager.enqueue_trigger(REPO_A, "webhook", "issues", "labeled")
            assert wait_until(lambda expected=expected: len(started) == expected)
            assert wait_until(lambda: not manager.workers[(REPO_A, "lane")].is_active())
        # Three rounds sent 120 requests: the budget of 100 is spent, so nothing more starts.
        assert manager.pause.holds()
        manager.enqueue_trigger(REPO_A, "webhook", "issues", "labeled")
        manager.enqueue_trigger(REPO_B, "webhook", "issues", "labeled")
        assert not wait_until(lambda: len(started) > 3, _QUIET_SECONDS)

        # An hour on, the window has room and the held triggers run, one round per repository.
        clock.now += timedelta(seconds=CONST_SERVICE_BUDGET_WINDOW_SECONDS + 1)
        assert wait_until(lambda: len(started) == 5)
    finally:
        _stop(manager)

    assert sorted(started[3:]) == [REPO_A, REPO_B]


def test_the_poll_cadence_is_the_one_the_budget_pays_for() -> None:
    clock, requests = _Clock(), _Requests()
    budget = RequestBudget(clock, 360, requests)
    assert budget.poll_interval(300.0, rounds_per_poll=4) == 300.0

    requests.count = 40
    clock.now += timedelta(minutes=1)
    budget.record_round()
    # A round costs 40 requests, a poll runs 4 rounds, and 360 requests an hour pay for 2.25 polls.
    assert budget.poll_interval(300.0, rounds_per_poll=4) == 1600.0
    assert budget.poll_interval(3000.0, rounds_per_poll=4) == 3000.0


def test_the_manager_polls_at_the_derived_interval() -> None:
    clock, requests = _Clock(), _Requests()
    manager = _manager(
        {"lane": lambda batch: None}, clock=clock, requests=requests, per_hour=360, poll_interval=60
    )
    try:
        assert manager.poll_interval() == 60.0
        requests.count = 90
        manager.budget.record_round()
        assert manager.poll_interval() == 3600 * 2 * 90 / 360
    finally:
        _stop(manager)


# ── A job that fails each round ─────────────────────────────────────────────────────────────


def _failing_table(calls: list[str]) -> Any:
    def broken(**_: Any) -> JobOutcome:
        calls.append("intake")
        raise GitHubOperationError("the read failed")

    return build_stub_table({"intake": broken})


_POLL = {("poll", "", ""): 1}
_WEBHOOK = {("webhook", "issues", "opened"): 1}


def test_a_job_that_failed_its_limit_of_rounds_does_not_run_until_its_input_changes(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    calls: list[str] = []
    table = _failing_table(calls)
    ledger = FailureLedger()
    caplog.set_level(logging.WARNING, logger="devops_cli.roadmap.run")

    def round_of(batch: Mapping[tuple[str, str, str], int], at: datetime) -> None:
        run_due_jobs(
            REPO_A,
            InMemoryRoadmapStore(),
            batch,
            table=table,
            data_dir=tmp_path,
            now=at,
            failures=ledger,
        )

    for step in range(DEFAULT_SERVICE_MAX_FAILED_ROUNDS):
        with pytest.raises(RoadmapRunError):
            round_of(_WEBHOOK if step == 0 else _POLL, START + timedelta(minutes=step))
    assert len(calls) == DEFAULT_SERVICE_MAX_FAILED_ROUNDS
    assert len([r for r in caplog.records if "failed 3 rounds in a row" in r.getMessage()]) == 1

    # The poll that follows brings no new input: the job stays silent, and the round succeeds.
    round_of(_POLL, START + timedelta(minutes=10))
    round_of(_POLL, START + timedelta(minutes=15))
    assert len(calls) == DEFAULT_SERVICE_MAX_FAILED_ROUNDS

    # A webhook is new input, so the job runs again, and fails once more.
    with pytest.raises(RoadmapRunError):
        round_of(_WEBHOOK, START + timedelta(minutes=20))
    assert len(calls) == DEFAULT_SERVICE_MAX_FAILED_ROUNDS + 1


def test_a_success_clears_the_record_of_failed_rounds() -> None:
    ledger = FailureLedger(limit=2)
    ledger.failed(REPO_A, "intake", "a")
    ledger.succeeded(REPO_A, "intake")
    ledger.failed(REPO_A, "intake", "a")
    assert not ledger.suspended(REPO_A, "intake", "a")
    ledger.failed(REPO_A, "intake", "a")
    assert ledger.suspended(REPO_A, "intake", "a")
    assert not ledger.suspended(REPO_A, "intake", "b")
    assert not ledger.suspended(REPO_B, "intake", "a")
