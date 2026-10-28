"""What stops the roadmap Service's GitHub requests: a refused identity, a spent hourly budget, a
job that fails every round (#2161), and a rate limit that one worker meets (#2474). A restart
keeps the halt, the budget window and the failure ledger, which the Service keeps on its volume
(#2474). The Service's /metrics shows the budget, each hold and each suspended job, and each
GitHub request names the worker's repository and the job row that sent it (#2475).

The jobs and the request counter are the process edges the tests replace; the engine, the
budget and the ledger are real, and the volume is a directory under `tmp_path`. A job that sends
a GitHub request sends it through the real session and `run_gh`, to the fake GitHub API and the
process fake. A conditional read of an unchanged listing is covered where the session keeps its
ETags (`tests/test_github_session.py`).
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Callable, Mapping
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from devops_cli.config.constants import (
    CONST_SERVICE_BUDGET_FILENAME,
    CONST_SERVICE_BUDGET_WINDOW_SECONDS,
    CONST_SERVICE_FAILURES_FILENAME,
    CONST_SERVICE_METRIC_BUDGET_HOLDS,
    CONST_SERVICE_METRIC_BUDGET_LIMIT,
    CONST_SERVICE_METRIC_BUDGET_SPENT,
    CONST_SERVICE_METRIC_IDENTITY_REFUSED,
    CONST_SERVICE_METRIC_JOB_SUSPENDED,
)
from devops_cli.config.defaults import DEFAULT_GH_MAX_RETRIES, DEFAULT_SERVICE_MAX_FAILED_ROUNDS
from devops_cli.config.settings import GitHubAppConfig, ServiceConfig
from devops_cli.exceptions import RoadmapRunError
from devops_cli.exceptions.git import GitHubOperationError, GitHubUnauthenticatedError
from devops_cli.github import rate_limiter, session_transport
from devops_cli.github.request_scope import request_labels
from devops_cli.github.session import get_github_session
from devops_cli.roadmap.github_store import GitHubRoadmapStore
from devops_cli.roadmap.memory_store import InMemoryRoadmapStore
from devops_cli.roadmap.run import (
    FailureLedger,
    JobOutcome,
    build_stub_table,
    identity_refused,
    run_due_jobs,
    service_jobs,
    service_state_dir,
)
from devops_cli.server.service import RequestBudget, ServiceManager, TriggerBatch
from devops_cli.telemetry.metrics import GLOBAL_METRICS
from devops_cli.telemetry.tracer import reset_tracer
from tests.support.fakes.clock import ClockFake
from tests.support.fakes.github import GitHubApiFake, github_json, quota_headers
from tests.support.fakes.process import ProcessAnswer, ProcessFake
from tests.support.waits import THREAD_HANDOFF_BOUND_SECONDS, wait_until

REPO_A, REPO_B = "example-org/repo1", "example-org/repo2"
START = datetime(2026, 10, 9, 12, tzinfo=UTC)
_QUIET_SECONDS = 0.5
"""How long a test waits to see that nothing more starts."""
SUSPENDED = "gh: Sorry. Your account was suspended. (HTTP 403)"
SECONDARY = (
    "gh: You have exceeded a secondary rate limit. Please wait a few minutes before you try "
    "again. (HTTP 403)"
)


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
    volume: Path | None = None,
) -> ServiceManager:
    manager = ServiceManager(
        config=ServiceConfig(
            repos=[REPO_A, REPO_B],
            github_app=GitHubAppConfig(app_id=1001, installation_id=42, slug="bot-account"),
            poll_interval_seconds=poll_interval,
            github_requests_per_hour=per_hour,
        ),
        secrets={},
        jobs=jobs,
        clock=clock,
        sleep_func=asyncio.sleep,
        identity_refused=identity_refused,
        request_counter=requests or _Requests(),
        state_dir=volume,
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
        CONST_SERVICE_METRIC_IDENTITY_REFUSED, labels={"identity": "bot-account[bot]"}
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


def _comment_through_gh(batch: TriggerBatch) -> None:
    """A round that writes one comment through `gh`, as the roadmap store writes."""
    GitHubRoadmapStore(batch.repo).comment(1, "A note.")


def _comment_through_the_session(batch: TriggerBatch) -> None:
    """A round that writes one comment through the GitHub session."""
    get_github_session().rest("POST", f"/repos/{batch.repo}/issues/1/comments", body={"body": "x"})


@pytest.mark.parametrize(
    "job",
    [
        pytest.param(_comment_through_gh, id="gh-says-the-installation-is-suspended"),
        pytest.param(_comment_through_the_session, id="a-write-refused-with-no-quota-headers"),
    ],
)
def test_a_suspended_installation_halts_the_service(
    github_api_and_gh: tuple[GitHubApiFake, ProcessFake],
    job: Callable[[TriggerBatch], None],
) -> None:
    """GitHub refuses a suspended installation's token with HTTP 403 "This installation has been
    suspended", which gh relays on stderr. GitHub counts a refused identity's request against no
    quota, so its 403 to a write carries no `x-ratelimit-*` header (#2474)."""
    api, gh = github_api_and_gh
    gh.answer(
        lambda call: "POST" in call.argv,
        ProcessAnswer(returncode=1, stderr="gh: This installation has been suspended (HTTP 403)"),
    )
    api.route(
        "POST",
        f"/repos/{REPO_A}/issues/1/comments",
        github_json({"message": "Forbidden"}, status=403),
    )
    manager = _manager({"lane": job}, clock=_Clock())
    try:
        manager.enqueue_trigger(REPO_A, "webhook", "issues", "labeled")
        assert wait_until(manager.pause.halted)
    finally:
        _stop(manager)

    assert _refusal_metric() == 1


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


# ── A rate limit ────────────────────────────────────────────────────────────────────────────


def test_a_secondary_limit_one_worker_meets_holds_the_requests_of_every_worker_until_it_ends(
    github_api: GitHubApiFake, clock: ClockFake
) -> None:
    """The worker of REPO_A meets a secondary limit that asks for 60 s. The worker of REPO_B
    sends its request after that, and it waits too, until the 60 s end (#2474). The clock stands
    still, so each pause the rate limiter asks for is the time to its turn."""
    secondary = github_json(
        {"message": "You have exceeded a secondary rate limit."},
        status=403,
        headers={"retry-after": "60", **quota_headers(4000)},
    )
    github_api.route("GET", f"/repos/{REPO_A}/issues", secondary, github_json([]))
    github_api.route("GET", f"/repos/{REPO_B}/issues", github_json([]))

    def job(batch: TriggerBatch) -> None:
        get_github_session().rest("GET", f"/repos/{batch.repo}/issues")

    manager = _manager({"lane": job}, clock=_Clock())
    try:
        for repo in (REPO_A, REPO_B):
            manager.enqueue_trigger(repo, "webhook", "issues", "labeled")
            assert manager.workers[(repo, "lane")].wait_active(THREAD_HANDOFF_BOUND_SECONDS)
    finally:
        _stop(manager)

    assert github_api.waits == [60.0]
    assert github_api.paced[-1] == pytest.approx(60.0, abs=0.5)
    assert len(github_api.sent) == 3


def _read_through_the_session(batch: TriggerBatch) -> None:
    """A round that reads one listing through the GitHub session."""
    get_github_session().rest("GET", f"/repos/{batch.repo}/issues")


@pytest.mark.parametrize(
    "job",
    [
        pytest.param(_read_through_the_session, id="the-session"),
        pytest.param(_comment_through_gh, id="gh"),
    ],
)
def test_the_last_rate_limit_of_a_request_holds_every_worker_until_its_wait_ends(
    github_api_and_gh: tuple[GitHubApiFake, ProcessFake],
    clock: ClockFake,
    monkeypatch: pytest.MonkeyPatch,
    job: Callable[[TriggerBatch], None],
) -> None:
    """The worker of REPO_A meets a secondary limit at each attempt of its request, through the
    session or through gh, so its round fails when its retries are spent. GitHub asked for at
    least 60 s with no request, so the request of REPO_B's worker that comes next waits too
    (#2523). Each wait moves the clock, as in production, so only the wait that the last refusal
    asks for can hold the request of REPO_B."""
    api, gh = github_api_and_gh
    api.route(
        "GET",
        f"/repos/{REPO_A}/issues",
        github_json(
            {"message": "You have exceeded a secondary rate limit."},
            status=403,
            headers={"retry-after": "60", **quota_headers(4000)},
        ),
    )
    api.route("GET", f"/repos/{REPO_B}/issues", github_json([]))
    gh.answer(lambda call: "POST" in call.argv, ProcessAnswer(returncode=1, stderr=SECONDARY))

    async def wait(_api: object, seconds: float) -> None:
        clock.sleep(seconds)

    monkeypatch.setattr(rate_limiter, "time", time)
    monkeypatch.setattr(session_transport.SessionGitHubAPI, "sleep", wait)
    held: list[float] = []

    def lane(batch: TriggerBatch) -> None:
        if batch.repo == REPO_A:
            job(batch)
            return
        start = time.time()
        _read_through_the_session(batch)
        held.append(time.time() - start)

    manager = _manager({"lane": lane}, clock=_Clock())
    try:
        for repo in (REPO_A, REPO_B):
            manager.enqueue_trigger(repo, "webhook", "issues", "labeled")
            assert manager.workers[(repo, "lane")].wait_active(THREAD_HANDOFF_BOUND_SECONDS)
    finally:
        _stop(manager)

    attempts = [r for r in api.sent if r.url.path == f"/repos/{REPO_A}/issues"]
    attempts += [call for call in gh.calls if "POST" in call.argv]
    assert len(attempts) == DEFAULT_GH_MAX_RETRIES + 1
    assert len(held) == 1
    assert held[0] >= 59.0


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


# ── A restart ───────────────────────────────────────────────────────────────────────────────


def test_a_restart_keeps_the_halt_the_budget_window_and_the_failure_ledger(
    tmp_path: Path,
) -> None:
    """The first Service sends 60 requests in a round that GitHub refuses, and a job fails its
    limit of rounds. The pod restarts over the same volume: the new process counts its requests
    from zero, and it still holds the halt, the 60 requests of the window and the suspended job
    (#2474). It counts the kept refusal once, so the alert on the counter holds through the
    restart."""
    clock, requests = _Clock(), _Requests()
    volume = service_state_dir(tmp_path)

    def refused(batch: TriggerBatch) -> None:
        requests.count += 60
        raise _suspended()

    first = _manager({"lane": refused}, clock=clock, requests=requests, volume=volume)
    try:
        first.enqueue_trigger(REPO_A, "webhook", "issues", "labeled")
        assert first.workers[(REPO_A, "lane")].wait_active(THREAD_HANDOFF_BOUND_SECONDS)
    finally:
        _stop(first)

    calls: list[str] = []
    table = _failing_table(calls)
    ledger = volume / CONST_SERVICE_FAILURES_FILENAME
    for step in range(DEFAULT_SERVICE_MAX_FAILED_ROUNDS):
        with pytest.raises(RoadmapRunError):
            run_due_jobs(
                REPO_A,
                InMemoryRoadmapStore(),
                _WEBHOOK if step == 0 else _POLL,
                table=table,
                data_dir=tmp_path,
                now=START + timedelta(minutes=step),
                failures=FailureLedger(record=ledger),
            )

    # The new process's metrics start empty.
    GLOBAL_METRICS.reset()
    restarted = _manager({"lane": refused}, clock=clock, requests=_Requests(), volume=volume)
    _stop(restarted)
    run_due_jobs(
        REPO_A,
        InMemoryRoadmapStore(),
        _POLL,
        table=table,
        data_dir=tmp_path,
        now=START + timedelta(minutes=10),
        failures=FailureLedger(record=ledger),
    )

    assert (
        restarted.pause.halted(),
        _refusal_metric(),
        restarted.budget.spent(),
        len(calls),
        _gauge(CONST_SERVICE_METRIC_BUDGET_SPENT),
        _suspended_metric(),
    ) == (True, 1, 60, DEFAULT_SERVICE_MAX_FAILED_ROUNDS, 60, 1)


@pytest.mark.parametrize(
    ("name", "start"),
    [
        pytest.param(
            CONST_SERVICE_BUDGET_FILENAME,
            lambda volume: _manager({"lane": lambda batch: None}, clock=_Clock(), volume=volume),
            id="budget",
        ),
        pytest.param(CONST_SERVICE_FAILURES_FILENAME, service_jobs, id="ledger"),
    ],
)
def test_a_record_that_cannot_be_read_stops_the_start_and_names_the_file(
    tmp_path: Path, name: str, start: Callable[[Path], object]
) -> None:
    """Read as empty, the record would let the Service send again what it held back (#2474)."""
    volume = service_state_dir(tmp_path)
    volume.mkdir(parents=True)
    (volume / name).write_text("{not json", encoding="utf-8")

    with pytest.raises(RoadmapRunError) as raised:
        start(volume)

    assert raised.value.details == {"path": str(volume / name)}


# ── What the Service reports (#2475) ────────────────────────────────────────────────────────


def _gauge(name: str, labels: dict[str, str] | None = None) -> float:
    return GLOBAL_METRICS.get_gauge_value(name, labels=labels)


def _suspended_metric() -> float:
    return _gauge(CONST_SERVICE_METRIC_JOB_SUSPENDED, {"repo": REPO_A, "row": "intake"})


def _budget_report() -> tuple[float, float, float]:
    """The budget's limit and the requests of the window, as gauges, and the holds counted."""
    return (
        _gauge(CONST_SERVICE_METRIC_BUDGET_LIMIT),
        _gauge(CONST_SERVICE_METRIC_BUDGET_SPENT),
        GLOBAL_METRICS.get_counter_value(CONST_SERVICE_METRIC_BUDGET_HOLDS),
    )


def test_the_budget_reports_its_limit_the_requests_of_the_window_and_each_hold_once() -> None:
    """The gauges follow the window as it slides, and a hold counts once when it begins, so a
    held Service shows on /metrics and not only in its log."""
    clock, requests = _Clock(), _Requests()
    budget = RequestBudget(clock, 100, requests)
    reports = [_budget_report()]

    requests.count = 130
    clock.now += timedelta(minutes=10)
    budget.record_round()
    budget.holds()
    budget.holds()
    reports.append(_budget_report())

    clock.now = START + timedelta(seconds=CONST_SERVICE_BUDGET_WINDOW_SECONDS + 15 * 60)
    budget.holds()
    reports.append(_budget_report())

    requests.count = 260
    clock.now += timedelta(minutes=1)
    budget.record_round()
    budget.holds()
    reports.append(_budget_report())

    assert reports == [(100, 0, 0), (100, 130, 1), (100, 0, 1), (100, 130, 2)]


def test_a_job_reports_its_suspension_until_new_input_or_a_success_ends_it() -> None:
    """The gauge of a job is 1 once it failed its limit of rounds in a row, 0 when it fails on
    new input, whose count starts again at 1, and 0 after a success."""
    ledger = FailureLedger(limit=2)
    seen: list[float] = []
    for current in ("a", "a", "b", "b"):
        ledger.failed(REPO_A, "intake", current)
        seen.append(_suspended_metric())
    ledger.succeeded(REPO_A, "intake")
    seen.append(_suspended_metric())

    assert seen == [0, 1, 0, 1, 0]


def test_each_github_request_of_a_round_names_the_workers_repository_and_its_job_row(
    tmp_path: Path,
) -> None:
    """A worker's round runs in the scope of its repository, one of `service.repos`, and each
    job row in the scope of its row. A request outside a worker names neither (#2475)."""
    seen: list[dict[str, str]] = []

    def row(**_: Any) -> JobOutcome:
        seen.append(request_labels())
        return JobOutcome()

    table = build_stub_table({"intake": row, "refine": row})

    def lane(batch: TriggerBatch) -> None:
        seen.append(request_labels())
        run_due_jobs(batch.repo, InMemoryRoadmapStore(), batch, table=table, data_dir=tmp_path)

    manager = _manager({"lane": lane}, clock=_Clock())
    try:
        manager.enqueue_trigger(REPO_A, "webhook", "issues", "labeled")
        assert wait_until(lambda: len(seen) == 3)
        assert manager.workers[(REPO_A, "lane")].wait_active(THREAD_HANDOFF_BOUND_SECONDS)
    finally:
        _stop(manager)

    assert (seen, request_labels()) == (
        [
            {"repo": REPO_A, "row": "other"},
            {"repo": REPO_A, "row": "intake"},
            {"repo": REPO_A, "row": "refine"},
        ],
        {"repo": "other", "row": "other"},
    )
