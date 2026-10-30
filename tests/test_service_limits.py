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
import json
import logging
import threading
import time
from collections.abc import Callable, Mapping
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from pydantic import TypeAdapter

from devops_cli.ai.client import network
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
from devops_cli.exceptions import RoadmapRefineError, RoadmapRunError, ServiceStoppingError
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


def _send(budget: RequestBudget, count: int) -> None:
    """Send `count` requests through the budget, as the rate limiter does for each one."""
    for _ in range(count):
        budget.admit()


def _suspended() -> GitHubUnauthenticatedError:
    return GitHubUnauthenticatedError(SUSPENDED)


def _manager(
    jobs: Mapping[str, Callable[[TriggerBatch], None]],
    *,
    clock: _Clock,
    per_hour: int = 500,
    poll_interval: int = 300,
    volume: Path | None = None,
    model_call_concurrency: int = 1,
) -> ServiceManager:
    manager = ServiceManager(
        config=ServiceConfig(
            repos=[REPO_A, REPO_B],
            github_app=GitHubAppConfig(app_id=1001, installation_id=42, slug="bot-account"),
            poll_interval_seconds=poll_interval,
            github_requests_per_hour=per_hour,
            model_call_concurrency=model_call_concurrency,
        ),
        secrets={},
        jobs=jobs,
        clock=clock,
        sleep_func=asyncio.sleep,
        identity_refused=identity_refused,
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


# ── The model call slot ──────────────────────────────────────────────────────────────────────


def test_the_service_keeps_one_model_call_in_flight_by_default() -> None:
    """Verify the Service keeps one model call in flight by default, so a lane that waits does so
    in the Service, where no stall timer runs (#2564)."""
    assert ServiceConfig().model_call_concurrency == 1


def test_the_service_installs_its_model_call_limit() -> None:
    """Verify the Service admits two model calls at once and holds a third, from its setting,
    rather than queueing at the gateway's stall timer (#2564)."""
    _manager({"lane": lambda batch: None}, clock=_Clock(), model_call_concurrency=2)

    admitted = False

    def third() -> None:
        nonlocal admitted
        with network.model_call_slot():
            admitted = True

    with network.model_call_slot(), network.model_call_slot():
        thread = threading.Thread(target=third)
        thread.start()
        # Two of the Service's two slots are held, so the third waits and takes no slot.
        assert not wait_until(lambda: admitted, 0.2)

    thread.join(timeout=5)
    assert admitted
    assert not thread.is_alive()


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
    clock = _Clock()
    budget = RequestBudget(clock, 100)
    _send(budget, 60)
    clock.now += timedelta(minutes=10)
    _send(budget, 30)
    assert not budget.holds()

    _send(budget, 10)
    assert budget.spent() == 100
    assert budget.holds()

    clock.now = START + timedelta(seconds=CONST_SERVICE_BUDGET_WINDOW_SECONDS + 5 * 60)
    assert budget.spent() == 40
    assert not budget.holds()


def test_a_round_that_would_pass_the_hourly_budget_waits_for_the_window() -> None:
    """The budget is checked for each request, where the request goes, so a round that starts
    under it waits when it would pass it, and goes on when the window has room (#2547)."""
    clock = _Clock()
    started: list[str] = []
    finished: list[str] = []

    def job(batch: TriggerBatch) -> None:
        started.append(batch.repo)
        _send(manager.budget, 60)
        finished.append(batch.repo)

    manager = _manager({"lane": job}, clock=clock, per_hour=100)
    try:
        manager.enqueue_trigger(REPO_A, "webhook", "issues", "labeled")
        assert wait_until(lambda: len(finished) == 1)
        manager.enqueue_trigger(REPO_B, "webhook", "issues", "labeled")
        assert wait_until(lambda: manager.budget.spent() == 100)
        # The round of REPO_B sent 40 requests, and its 41st waits.
        assert not wait_until(lambda: len(finished) == 2, _QUIET_SECONDS)
        assert (started, manager.budget.spent(), manager.pause.holds()) == (
            [REPO_A, REPO_B],
            100,
            True,
        )

        clock.now += timedelta(seconds=CONST_SERVICE_BUDGET_WINDOW_SECONDS + 1)
        assert wait_until(lambda: len(finished) == 2)
    finally:
        _stop(manager)

    assert manager.budget.spent() == 20


def test_each_request_is_in_the_record_when_it_is_sent(tmp_path: Path) -> None:
    """A pod that stops in the middle of a round loses none of its requests (#2547)."""
    record = tmp_path / CONST_SERVICE_BUDGET_FILENAME
    budget = RequestBudget(_Clock(), 100, record=record)
    kept: list[int] = []

    for _ in range(3):
        budget.admit()
        kept.append(sum(count for _, count in json.loads(record.read_text(encoding="utf-8"))))

    assert kept == [1, 2, 3]
    assert RequestBudget(_Clock(), 100, record=record).spent() == 3


def test_a_request_the_budget_has_no_room_for_ends_when_the_budget_is_closed() -> None:
    budget = RequestBudget(_Clock(), 2)
    _send(budget, 2)
    budget.close()

    with pytest.raises(ServiceStoppingError) as raised:
        budget.admit()

    assert (raised.value.details, budget.spent()) == ({"limit": 2}, 2)


def test_the_requests_of_a_session_are_admitted_by_the_service_budget(
    github_api: GitHubApiFake,
) -> None:
    """The rate limiter asks the budget for each request it lets go, so a request is counted
    where it is sent, and not at the end of a round (#2547)."""
    from devops_cli.github.rate_limiter import set_request_gate

    github_api.route("GET", f"/repos/{REPO_A}/issues", github_json([]))
    budget = RequestBudget(_Clock(), 100)
    set_request_gate(budget.admit)
    try:
        get_github_session().rest("GET", f"/repos/{REPO_A}/issues")
    finally:
        set_request_gate(None)

    assert budget.spent() == 1


def test_the_poll_cadence_is_the_one_the_budget_pays_for() -> None:
    clock = _Clock()
    budget = RequestBudget(clock, 360)
    assert budget.poll_interval(300.0, rounds_per_poll=4) == 300.0

    _send(budget, 40)
    budget.count_round()
    # A round costs 40 requests, a poll runs 4 rounds, and 360 requests an hour pay for 2.25 polls.
    assert budget.poll_interval(300.0, rounds_per_poll=4) == 1600.0
    assert budget.poll_interval(3000.0, rounds_per_poll=4) == 3000.0


def test_the_manager_polls_at_the_derived_interval() -> None:
    manager = _manager({"lane": lambda batch: None}, clock=_Clock(), per_hour=360, poll_interval=60)
    try:
        assert manager.poll_interval() == 60.0
        _send(manager.budget, 90)
        manager.budget.count_round()
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


_CAUSE = "GitHubOperationError"
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
    ledger.failed(REPO_A, "intake", "a", _CAUSE)
    ledger.succeeded(REPO_A, "intake")
    ledger.failed(REPO_A, "intake", "a", _CAUSE)
    assert not ledger.suspended(REPO_A, "intake", "a")
    ledger.failed(REPO_A, "intake", "a", _CAUSE)
    assert ledger.suspended(REPO_A, "intake", "a")
    assert not ledger.suspended(REPO_A, "intake", "b")
    assert not ledger.suspended(REPO_B, "intake", "a")


# ── A stop is not a failed round (#2753) ───────────────────────────────────────────────────


def _stopping() -> ServiceStoppingError:
    return ServiceStoppingError("the request does not wait: the Service is stopping")


class _Rounds:
    """Rounds of one `intake` row over one ledger. The row raises the next error of `errors`
    and succeeds when none is left; `calls` counts each time the row ran."""

    def __init__(self, *errors: Exception, limit: int = DEFAULT_SERVICE_MAX_FAILED_ROUNDS) -> None:
        self.errors = list(errors)
        self.calls = 0
        self.ledger = FailureLedger(limit=limit)
        self._minutes = 0

    def _intake(self, **_: Any) -> JobOutcome:
        self.calls += 1
        if self.errors:
            raise self.errors.pop(0)
        return JobOutcome()

    def poll(self, tmp_path: Path) -> None:
        """One round that a poll starts, where the input of the job is the same each time."""
        self._minutes += 1
        run_due_jobs(
            REPO_A,
            InMemoryRoadmapStore(),
            _POLL,
            table=build_stub_table({"intake": self._intake}),
            data_dir=tmp_path,
            now=START + timedelta(minutes=self._minutes),
            failures=self.ledger,
        )

    def fail(self, tmp_path: Path) -> None:
        """One round that is meant to end with its error."""
        with pytest.raises(RoadmapRunError):
            self.poll(tmp_path)


def test_three_rounds_that_a_stop_ends_do_not_suspend_the_row_and_the_next_round_runs(
    tmp_path: Path,
) -> None:
    rounds = _Rounds(*(_stopping() for _ in range(DEFAULT_SERVICE_MAX_FAILED_ROUNDS)))
    for _ in range(DEFAULT_SERVICE_MAX_FAILED_ROUNDS):
        rounds.fail(tmp_path)

    rounds.poll(tmp_path)

    assert rounds.calls == DEFAULT_SERVICE_MAX_FAILED_ROUNDS + 1
    assert _suspended_metric() == 0


def _caused_by(cause: Exception) -> Exception:
    wrapped = RoadmapRefineError("the round ended")
    wrapped.__cause__ = cause
    return wrapped


@pytest.mark.parametrize(
    ("error", "counts"),
    [
        pytest.param(_caused_by(_stopping()), False, id="the stop is the cause"),
        pytest.param(ExceptionGroup("g", [_stopping(), _stopping()]), False, id="stops only"),
        pytest.param(
            ExceptionGroup("g", [_stopping(), GitHubOperationError("read")]),
            True,
            id="a stop and a real failure",
        ),
        pytest.param(_caused_by(GitHubOperationError("read")), True, id="a real cause"),
    ],
)
def test_a_stop_in_the_cause_chain_or_in_a_group_is_a_stop_only_when_no_real_failure_is_with_it(
    tmp_path: Path, error: Exception, counts: bool
) -> None:
    """With a limit of 1, a failure that counts suspends the row at once."""
    rounds = _Rounds(error, limit=1)
    rounds.fail(tmp_path)

    rounds.poll(tmp_path)

    assert rounds.calls == (1 if counts else 2)


def test_a_stop_between_two_failures_keeps_the_count_of_the_row(tmp_path: Path) -> None:
    """With a limit of 2: the count is 1, the stop leaves it, and the next failure makes 2 and
    suspends the row. Counted, the stop would suspend it a round sooner; cleared, a round later."""
    rounds = _Rounds(
        GitHubOperationError("read"), _stopping(), GitHubOperationError("read"), limit=2
    )
    for _ in range(3):
        rounds.fail(tmp_path)

    rounds.poll(tmp_path)

    assert rounds.calls == 3
    assert _suspended_metric() == 1


def test_the_line_that_suspends_a_row_names_the_cause_of_each_round(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.WARNING, logger="devops_cli.roadmap.run")
    rounds = _Rounds(
        GitHubOperationError("read"), RoadmapRefineError("model"), GitHubOperationError("write")
    )
    for _ in range(DEFAULT_SERVICE_MAX_FAILED_ROUNDS):
        rounds.fail(tmp_path)

    (line,) = [r.getMessage() for r in caplog.records if "rounds in a row" in r.getMessage()]
    assert "(causes: GitHubOperationError, RoadmapRefineError, GitHubOperationError)" in line


def test_a_round_that_an_earlier_process_counted_has_the_cause_unknown(tmp_path: Path) -> None:
    record = tmp_path / CONST_SERVICE_FAILURES_FILENAME
    before = FailureLedger(record=record)
    for _ in range(2):
        before.failed(REPO_A, "intake", "a", _CAUSE)

    after = FailureLedger(record=record)
    after.failed(REPO_A, "intake", "a", "RoadmapRefineError")

    assert after.causes(REPO_A, "intake") == ("unknown", "unknown", "RoadmapRefineError")


def test_a_failure_on_new_input_starts_the_causes_again_and_a_success_clears_them() -> None:
    ledger = FailureLedger(limit=2)
    ledger.failed(REPO_A, "intake", "a", "GitHubOperationError")
    ledger.failed(REPO_A, "intake", "a", "GitHubOperationError")
    ledger.failed(REPO_A, "intake", "b", "RoadmapRefineError")
    new_input = ledger.causes(REPO_A, "intake")
    ledger.succeeded(REPO_A, "intake")

    assert (new_input, ledger.causes(REPO_A, "intake")) == (("RoadmapRefineError",), ())


_RUNNING_VERSION_RECORD = TypeAdapter(list[tuple[str, str, int, str]])
"""The type with which the version that runs now reads `service-failures.json`: a record of
another shape would stop that version from starting after a rollback."""


def test_the_failure_file_keeps_the_format_that_the_running_version_reads(tmp_path: Path) -> None:
    record = tmp_path / CONST_SERVICE_FAILURES_FILENAME
    record.write_text(json.dumps([[REPO_A, "refine", 3, "abc"]]), encoding="utf-8")

    kept = FailureLedger(record=record)
    assert kept.suspended(REPO_A, "refine", "abc")
    assert _gauge(CONST_SERVICE_METRIC_JOB_SUSPENDED, {"repo": REPO_A, "row": "refine"}) == 1

    kept.failed(REPO_B, "implement", "x", "ServiceStoppingError")
    assert _RUNNING_VERSION_RECORD.validate_json(record.read_bytes()) == [
        (REPO_A, "refine", 3, "abc"),
        (REPO_B, "implement", 1, "x"),
    ]


# ── A restart ───────────────────────────────────────────────────────────────────────────────


def test_a_restart_keeps_the_halt_the_budget_window_and_the_failure_ledger(
    tmp_path: Path,
) -> None:
    """The first Service sends 60 requests in a round that GitHub refuses, and a job fails its
    limit of rounds. The pod restarts over the same volume: the new process counts its requests
    from zero, and it still holds the halt, the 60 requests of the window and the suspended job
    (#2474). It counts the kept refusal once, so the alert on the counter holds through the
    restart."""
    clock = _Clock()
    volume = service_state_dir(tmp_path)

    def refused(batch: TriggerBatch) -> None:
        _send(first.budget, 60)
        raise _suspended()

    first = _manager({"lane": refused}, clock=clock, volume=volume)
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
    restarted = _manager({"lane": refused}, clock=clock, volume=volume)
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
    clock = _Clock()
    budget = RequestBudget(clock, 100)
    reports = [_budget_report()]

    _send(budget, 100)
    clock.now += timedelta(minutes=10)
    budget.holds()
    budget.holds()
    reports.append(_budget_report())

    clock.now = START + timedelta(seconds=CONST_SERVICE_BUDGET_WINDOW_SECONDS + 15 * 60)
    budget.holds()
    reports.append(_budget_report())

    _send(budget, 100)
    clock.now += timedelta(minutes=1)
    budget.holds()
    reports.append(_budget_report())

    assert reports == [(100, 0, 0), (100, 100, 1), (100, 0, 1), (100, 100, 2)]


def test_a_job_reports_its_suspension_until_new_input_or_a_success_ends_it() -> None:
    """The gauge of a job is 1 once it failed its limit of rounds in a row, 0 when it fails on
    new input, whose count starts again at 1, and 0 after a success."""
    ledger = FailureLedger(limit=2)
    seen: list[float] = []
    for current in ("a", "a", "b", "b"):
        ledger.failed(REPO_A, "intake", current, _CAUSE)
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
