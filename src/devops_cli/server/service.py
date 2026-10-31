"""Continuous background service mode engine for devops-cli."""

from __future__ import annotations

import asyncio
import json
import logging
import math
import threading
import time
from collections import deque
from collections.abc import AsyncIterator, Callable, Coroutine, Mapping, Sequence
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from pydantic import BaseModel, ConfigDict, TypeAdapter
from pydantic import ValidationError as MalformedRecordError

from devops_cli import __version__
from devops_cli.ai.client import network
from devops_cli.config.constants import (
    CONST_SERVICE_BUDGET_FILENAME,
    CONST_SERVICE_BUDGET_WINDOW_SECONDS,
    CONST_SERVICE_HALT_FILENAME,
    CONST_SERVICE_LANE_DEFAULT,
    CONST_SERVICE_METRIC_BUDGET_HOLDS,
    CONST_SERVICE_METRIC_BUDGET_LIMIT,
    CONST_SERVICE_METRIC_BUDGET_SPENT,
    CONST_SERVICE_METRIC_IDENTITY_REFUSED,
    CONST_SERVICE_METRIC_JOB_SECONDS,
    CONST_SERVICE_METRIC_JOB_START_TIMESTAMP,
    CONST_SERVICE_METRIC_JOBS,
    CONST_SERVICE_METRIC_QUEUE_DEPTH,
    CONST_SERVICE_METRIC_TRIGGERS,
    CONST_SERVICE_PROBE_PATHS,
    CONST_SERVICE_SOURCE_POLL,
)
from devops_cli.config.settings import (
    ServiceConfig,
    Settings,
    get_service_webhook_secrets,
    load_settings,
)
from devops_cli.exceptions import ConfigurationError, RoadmapRunError, ServiceStoppingError
from devops_cli.github.rate_limiter import set_request_gate
from devops_cli.github.request_scope import request_scope
from devops_cli.lang import MESSAGES
from devops_cli.server.routes.webhooks import (
    DeliveryLRUCache,
    WebhookConsumer,
    create_webhook_router,
)
from devops_cli.telemetry.metrics import GLOBAL_METRICS
from devops_cli.telemetry.tracer import get_tracer

logger = logging.getLogger(__name__)


class TriggerBatch(BaseModel):
    """Immutable batch of coalesced repository trigger events."""

    model_config = ConfigDict(frozen=True)

    repo: str
    counts: dict[tuple[str, str, str], int]
    first_at: datetime
    last_at: datetime


PauseReader = Callable[[Exception], datetime | None]
"""Reads the time a failed round's error names, before which no round starts, or None."""

IdentityReader = Callable[[Exception], bool]
"""Reads whether a failed round's error says GitHub refused the Service's identity."""

LaneJob = Callable[[TriggerBatch], None]
"""What one lane of a repository runs for each batch of its triggers."""


def default_service_job(batch: TriggerBatch) -> None:
    """Default fallback job executing for repository events when no custom handler is given."""
    logger.info(
        "Service job triggered for repository: %s with %d trigger types",
        batch.repo,
        len(batch.counts),
        extra={"repo": batch.repo},
    )


def no_round_pause(_exc: Exception) -> datetime | None:
    """A failed round names no time to wait for: how the engine reads an error when the
    service gives no other reader."""
    return None


def no_identity_refusal(_exc: Exception) -> bool:
    """A failed round never says GitHub refused the identity: how the engine reads an error when
    the service gives no other reader."""
    return False


_RequestsSent = TypeAdapter(list[tuple[datetime, int]])
"""A budget record: the time of each request in the window and the requests it counts."""

_BUDGET_WAIT_SLICE_SECONDS = 1.0
"""The longest a request waits before it reads the window again."""


def read_state_record[T](record: Path, adapter: TypeAdapter[T], empty: T) -> T:
    """What the Service kept in `record` before it last stopped, or `empty` when there is no
    record. A record that cannot be read raises, naming it and the remedy, rather than reading as
    empty: an empty one would let the Service send what the record holds back (#2474)."""
    if not record.exists():
        return empty
    try:
        return adapter.validate_json(record.read_bytes())
    except (OSError, MalformedRecordError) as exc:
        reason = str(exc).splitlines()[0][:200]
        raise RoadmapRunError(
            MESSAGES.serve.state_unreadable.format(record=record, reason=reason),
            details={"path": str(record)[:256]},
        ) from exc


def keep_state_record(record: Path, payload: object) -> None:
    """Write `payload` to `record` atomically. A record that cannot be written is one error log
    line: the Service goes on with what it holds in memory, which a restart does not keep."""
    from devops_cli.output.file_writer import write_json_file

    try:
        write_json_file(record, payload, indent=2, atomic=True)
    except OSError as exc:
        logger.error(
            MESSAGES.serve.state_unkept.format(record=record, kind=type(exc).__name__, error=exc)
        )


def _report_spent(spent: int) -> None:
    """Show the requests of the budget's window on the Service's /metrics."""
    GLOBAL_METRICS.set_gauge(CONST_SERVICE_METRIC_BUDGET_SPENT, float(spent))


class RequestBudget:
    """The GitHub requests the Service may send in any one hour, all repositories and lanes
    together (#2161, #2547).

    The budget is hard: each request asks `admit` for its place as the GitHub rate limiter lets
    it go, so no hour holds more than the limit, whatever a round costs. A request the window
    has no room for waits until the oldest request of the window leaves it. `admit` keeps the
    request in the window at once, and with a `record`, in that file, so a pod that stops in
    the middle of a round loses none, and a restart reads them back (#2474). Once `close` is
    called, a request that would wait ends with an error instead, so a stop does not wait for
    the window.

    The cost of a round sets the poll cadence: the Service polls no faster than the budget pays
    for. The Service's /metrics shows the limit, the requests of the window as of the last
    request or check, and a count of each hold when it begins (#2475).
    """

    def __init__(
        self,
        clock: Callable[[], datetime],
        limit: int,
        window_seconds: int = CONST_SERVICE_BUDGET_WINDOW_SECONDS,
        record: Path | None = None,
    ) -> None:
        self._clock = clock
        self._limit = limit
        self._window = timedelta(seconds=window_seconds)
        self._record = record
        self._lock = threading.Lock()
        self._closed = threading.Event()
        self._admitted = 0
        self._rounds = 0
        kept = [] if record is None else read_state_record(record, _RequestsSent, [])
        self._sent: deque[tuple[datetime, int]] = deque(kept)
        self._holding = False
        GLOBAL_METRICS.set_gauge(CONST_SERVICE_METRIC_BUDGET_LIMIT, float(limit))
        _report_spent(self.spent())

    @property
    def limit(self) -> int:
        """The most requests the Service sends in an hour."""
        return self._limit

    def admit(self) -> None:
        """Give one request its place in the window, and keep it in the record. Waits while the
        window is full; once the budget is closed, raises instead of waiting."""
        while True:
            with self._lock:
                spent = self._spent_locked()
                if spent < self._limit:
                    self._sent.append((self._clock(), 1))
                    self._admitted += 1
                    spent += 1
                    if self._record is not None:
                        kept = _RequestsSent.dump_python(list(self._sent), mode="json")
                        keep_state_record(self._record, kept)
                    break
                wait = (self._sent[0][0] + self._window - self._clock()).total_seconds()
            _report_spent(spent)
            if self._closed.is_set():
                raise ServiceStoppingError(
                    MESSAGES.serve.budget_closed.format(spent=spent, limit=self._limit),
                    details={"limit": self._limit},
                )
            self._closed.wait(min(max(wait, 0.0), _BUDGET_WAIT_SLICE_SECONDS))
        _report_spent(spent)

    def close(self) -> None:
        """End the waits of the requests that the window has no room for, and refuse the
        ones that come after."""
        self._closed.set()

    def count_round(self) -> None:
        """Count a round that ended, for the cost of a round."""
        with self._lock:
            self._rounds += 1

    def _spent_locked(self) -> int:
        cutoff = self._clock() - self._window
        while self._sent and self._sent[0][0] <= cutoff:
            self._sent.popleft()
        return sum(sent for _, sent in self._sent)

    def spent(self) -> int:
        """The requests the Service sent in the last hour."""
        with self._lock:
            return self._spent_locked()

    def holds(self) -> bool:
        """Whether the last hour's requests have used the budget, so no round may start. The
        hold is logged and counted once each time it begins."""
        with self._lock:
            spent = self._spent_locked()
            holding = spent >= self._limit
            began = holding and not self._holding
            self._holding = holding
        _report_spent(spent)
        if began:
            GLOBAL_METRICS.increment_counter(CONST_SERVICE_METRIC_BUDGET_HOLDS)
            logger.warning(MESSAGES.serve.budget_spent.format(spent=spent, limit=self._limit))
        return holding

    def poll_interval(self, configured: float, rounds_per_poll: int) -> float:
        """Seconds between polls: the configured interval, or longer when the rounds of a poll
        cost more than the budget pays for at that cadence."""
        with self._lock:
            if self._rounds == 0:
                return configured
            cost = self._admitted / self._rounds
        needed = self._window.total_seconds() * rounds_per_poll * cost / self._limit
        return max(configured, float(math.ceil(needed)))


class RoundPause:
    """The time before which no worker starts a round, shared by every repository's worker in
    every lane (#1400, #1532).

    A round that fails with a refusal of the identity (#2161) halts every worker for good, and
    the halt is one error log line and one count of the refusal metric. With a `halt_record`, the
    halt is also that file, and a restart that finds the file starts halted, with one error log
    line and one count of the metric, so the metric's alert holds through the restart (#2474):
    no round starts again until a person removes the file and restarts the Service. An hourly
    request budget holds the rounds too.

    A failed round can name a time to wait for, which `reader` reads from its error: the roadmap
    Service names a GraphQL budget refusal's reset, because the budget is the identity's, the
    GitHub App's installation, and every repository's rounds spend it. Triggers keep coalescing meanwhile, so each lane of
    each repository runs one round with all of them once the time passes.
    """

    def __init__(
        self,
        clock: Callable[[], datetime],
        reader: PauseReader = no_round_pause,
        refusal: IdentityReader = no_identity_refusal,
        budget: RequestBudget | None = None,
        identity: str = "unknown",
        halt_record: Path | None = None,
    ) -> None:
        self._clock = clock
        self._reader = reader
        self._refusal = refusal
        self._budget = budget
        self._identity = identity
        self._halt_record = halt_record
        self._lock = threading.Lock()
        self._until: datetime | None = None
        self._halted = halt_record is not None and halt_record.exists()
        if self._halted:
            logger.error(
                MESSAGES.serve.identity_refused_kept.format(identity=identity, record=halt_record),
                extra={"identity": identity},
            )
            GLOBAL_METRICS.increment_counter(
                CONST_SERVICE_METRIC_IDENTITY_REFUSED, labels={"identity": identity}
            )

    def round_ended(self) -> None:
        """Count a round that ended, for the cost of a round."""
        if self._budget is not None:
            self._budget.count_round()

    def halted(self) -> bool:
        """Whether GitHub refused the identity, so no round starts again."""
        with self._lock:
            return self._halted

    def _halt(self, exc: Exception, repo: str) -> None:
        """Stop every round for good, keep the halt in the record, and report the refusal
        once."""
        with self._lock:
            first = not self._halted
            self._halted = True
        if first:
            logger.error(
                MESSAGES.serve.identity_refused.format(
                    identity=self._identity, repo=repo, kind=type(exc).__name__, error=exc
                ),
                extra={"repo": repo, "identity": self._identity},
            )
            GLOBAL_METRICS.increment_counter(
                CONST_SERVICE_METRIC_IDENTITY_REFUSED, labels={"identity": self._identity}
            )
            if self._halt_record is not None:
                halt = {
                    "identity": self._identity,
                    "repo": repo,
                    "kind": type(exc).__name__,
                    "at": self._clock().isoformat(),
                }
                keep_state_record(self._halt_record, halt)

    def after(self, exc: Exception, repo: str) -> None:
        """Hold every round until the time `exc`, the error of `repo`'s round, names, and log
        each new time once; a time not after the clock, or not after the time held already,
        changes nothing. A time that can't be read is a warning naming its class: nothing is
        held, and the worker carries on."""
        try:
            if self._refusal(exc):
                self._halt(exc, repo)
                return
            until = self._reader(exc)
            fresh = until if until is not None and self._hold(until) else None
        except Exception as failure:
            unread = MESSAGES.serve.rounds_pause_unread.format(
                repo=repo, kind=type(failure).__name__, error=failure
            )
            logger.warning(unread, extra={"repo": repo})
            return
        if fresh is not None:
            shown = fresh.astimezone(UTC).isoformat(timespec="seconds")
            logger.info(
                MESSAGES.serve.rounds_paused.format(until=shown, repo=repo), extra={"repo": repo}
            )

    def _hold(self, until: datetime) -> bool:
        """Hold rounds until `until` when it is after the clock and after the time held already;
        whether it is a new time."""
        with self._lock:
            if until <= self._clock() or (self._until is not None and until <= self._until):
                return False
            self._until = until
            return True

    def holds(self) -> bool:
        """Whether no round may start now."""
        with self._lock:
            if self._halted or (self._until is not None and self._clock() < self._until):
                return True
        return self._budget is not None and self._budget.holds()


class RepoWorker:
    """Dedicated daemon worker thread running one lane of one repository: a single-concurrency
    queue whose triggers coalesce into the lane's next round (#1532)."""

    def __init__(
        self,
        repo: str,
        lane: str,
        job_func: LaneJob,
        clock: Callable[[], datetime],
        pause: RoundPause | None = None,
    ) -> None:
        self.repo = repo
        self.lane = lane
        self._labels = {"repo": repo, "lane": lane}
        self.job_func = job_func
        self.clock = clock
        self.pause = pause or RoundPause(clock)
        self._cond = threading.Condition()
        self._stop_event = threading.Event()
        self._is_active = False
        self._pending_counts: dict[tuple[str, str, str], int] = {}
        self._pending_scoped: deque[Callable[[], None]] = deque()
        self._first_at: datetime | None = None
        self._last_at: datetime | None = None
        self._thread: threading.Thread | None = None
        self._error: Exception | None = None

    def start(self) -> None:
        """Start the daemon worker thread. The job start of the lane is the time the worker
        starts until its first job starts, so a lane of a new pod that starts no job has a series
        (#2505)."""
        GLOBAL_METRICS.set_gauge(
            CONST_SERVICE_METRIC_JOB_START_TIMESTAMP, self.clock().timestamp(), labels=self._labels
        )
        self._thread = threading.Thread(
            target=self._run,
            name=f"service-worker-{self.repo}-{self.lane}",
            daemon=True,
        )
        self._thread.start()

    def enqueue(self, source: str, event: str, action: str) -> None:
        """Enqueue an incoming trigger event, coalescing into the pending batch."""
        key = (source, event, action)
        now = self.clock()
        with self._cond:
            if not self._pending_counts:
                self._first_at = now
            self._last_at = now
            self._pending_counts[key] = self._pending_counts.get(key, 0) + 1
            GLOBAL_METRICS.set_gauge(CONST_SERVICE_METRIC_QUEUE_DEPTH, 1.0, labels=self._labels)
            self._cond.notify()

    def enqueue_scoped(self, scoped_func: Callable[[], None]) -> None:
        """Enqueue a scoped update task, running sequentially with the lane's rounds."""
        with self._cond:
            self._pending_scoped.append(scoped_func)
            GLOBAL_METRICS.set_gauge(CONST_SERVICE_METRIC_QUEUE_DEPTH, 1.0, labels=self._labels)
            self._cond.notify()

    def is_alive(self) -> bool:
        """Return True if the underlying worker thread is alive and healthy."""
        return self._thread is not None and self._thread.is_alive() and self._error is None

    def is_active(self) -> bool:
        """Return True if a job is currently executing."""
        with self._cond:
            return self._is_active

    def stop(self) -> None:
        """Signal worker thread to stop."""
        self._stop_event.set()
        with self._cond:
            self._cond.notify_all()

    def join(self, timeout: float) -> bool:
        """Wait up to `timeout` seconds for the worker thread to end; whether it has."""
        if self._thread is not None:
            self._thread.join(timeout)
        return self._thread is None or not self._thread.is_alive()

    def wait_active(self, timeout: float) -> bool:
        """Wait until the active job completes and the pending queue drains, or timeout expires;
        a batch the pause holds is not waited for."""
        deadline = time.perf_counter() + timeout
        with self._cond:
            while self._is_active or self._has_runnable_batch():
                remaining = deadline - time.perf_counter()
                if remaining <= 0:
                    break
                self._cond.wait(timeout=min(remaining, 0.05))
            return not self._is_active and not self._has_runnable_batch()

    def _has_runnable_batch(self) -> bool:
        """Whether events or scoped tasks are pending and the pause lets a round start; the caller
        holds the condition."""
        return (bool(self._pending_scoped) or bool(self._pending_counts)) and not self.pause.holds()

    def _wait_for_next_batch(
        self,
    ) -> tuple[dict[tuple[str, str, str], int], datetime, datetime] | Callable[[], None] | None:
        """Wait for pending events or scoped tasks the pause lets run and pop them."""
        with self._cond:
            while not self._has_runnable_batch() and not self._stop_event.is_set():
                self._cond.wait(timeout=0.2)
            if not self._has_runnable_batch():
                return None
            if self._pending_scoped:
                scoped = self._pending_scoped.popleft()
                self._is_active = True
                remaining = len(self._pending_scoped) + len(self._pending_counts)
                GLOBAL_METRICS.set_gauge(
                    CONST_SERVICE_METRIC_QUEUE_DEPTH, 1.0 if remaining else 0.0, labels=self._labels
                )
                return scoped
            counts = dict(self._pending_counts)
            first_at = self._first_at or self.clock()
            last_at = self._last_at or self.clock()
            self._pending_counts.clear()
            self._first_at = None
            self._last_at = None
            self._is_active = True
            remaining = len(self._pending_scoped)
            GLOBAL_METRICS.set_gauge(
                CONST_SERVICE_METRIC_QUEUE_DEPTH, 1.0 if remaining else 0.0, labels=self._labels
            )
            return counts, first_at, last_at

    def _execute_scoped(self, scoped_func: Callable[[], None]) -> None:
        """Execute a scoped update task and record Prometheus metrics and execution duration."""
        start_time = time.perf_counter()
        start_epoch = time.time()
        GLOBAL_METRICS.set_gauge(
            CONST_SERVICE_METRIC_JOB_START_TIMESTAMP, start_epoch, labels=self._labels
        )
        result = "success"
        tracer = get_tracer()
        with tracer.span(
            f"service.scoped {self.repo}",
            kind="internal",
            attributes={
                "service.repo": self.repo,
                "service.lane": self.lane,
            },
        ) as span:
            try:
                with request_scope(repo=self.repo):
                    scoped_func()
            except Exception as exc:
                result = "error"
                span.set_status("ERROR", str(exc)[:256])
                span.set_attribute("error", True)
                span.set_attribute("error.message", str(exc)[:256])
                is_config_only = isinstance(exc, ConfigurationError) or (
                    isinstance(exc, RoadmapRunError) and exc.is_configuration_only
                )
                logger.error(
                    "Service scoped update failed for %s: %s",
                    self.repo,
                    exc,
                    extra={**self._labels, "result": "error"},
                    exc_info=True if not is_config_only else None,
                )
                self.pause.after(exc, self.repo)
            finally:
                span.set_attribute("service.result", result)
                duration = time.perf_counter() - start_time
                GLOBAL_METRICS.increment_counter(
                    CONST_SERVICE_METRIC_JOBS, labels={**self._labels, "result": result}
                )
                GLOBAL_METRICS.increment_counter(
                    CONST_SERVICE_METRIC_JOB_SECONDS, value=duration, labels=self._labels
                )
                self.pause.round_ended()
                try:
                    tracer.flush()
                finally:
                    with self._cond:
                        self._is_active = False
                        self._cond.notify_all()

    def _execute_batch(self, batch: TriggerBatch) -> None:
        """Execute the job function and record Prometheus metrics and execution duration."""
        start_time = time.perf_counter()
        start_epoch = time.time()
        GLOBAL_METRICS.set_gauge(
            CONST_SERVICE_METRIC_JOB_START_TIMESTAMP, start_epoch, labels=self._labels
        )
        result = "success"
        tracer = get_tracer()
        with tracer.span(
            f"service.job {self.repo}",
            kind="internal",
            attributes={
                "service.repo": self.repo,
                "service.lane": self.lane,
                "service.triggers": sum(batch.counts.values()),
                "service.trigger_types": len(batch.counts),
            },
        ) as span:
            try:
                with request_scope(repo=self.repo):
                    self.job_func(batch)
            except Exception as exc:
                result = "error"
                span.set_status("ERROR", str(exc)[:256])
                span.set_attribute("error", True)
                span.set_attribute("error.message", str(exc)[:256])
                is_config_only = isinstance(exc, ConfigurationError) or (
                    isinstance(exc, RoadmapRunError) and exc.is_configuration_only
                )
                logger.error(
                    "Service job execution failed for %s: %s",
                    self.repo,
                    exc,
                    extra={**self._labels, "result": "error"},
                    exc_info=True if not is_config_only else None,
                )
                self.pause.after(exc, self.repo)
            finally:
                span.set_attribute("service.result", result)
                duration = time.perf_counter() - start_time
                GLOBAL_METRICS.increment_counter(
                    CONST_SERVICE_METRIC_JOBS, labels={**self._labels, "result": result}
                )
                GLOBAL_METRICS.increment_counter(
                    CONST_SERVICE_METRIC_JOB_SECONDS, value=duration, labels=self._labels
                )
                self.pause.round_ended()
                try:
                    # The Service is one long process, and the exit hook sends the OTLP counters
                    # only when the pod stops. So each batch sends what it recorded, such as its
                    # AI requests, before its worker is idle (#1629).
                    tracer.flush()
                finally:
                    with self._cond:
                        self._is_active = False
                        self._cond.notify_all()

    def _run(self) -> None:
        """Main loop of daemon worker thread."""
        try:
            while True:
                work = self._wait_for_next_batch()
                if work is None:
                    if self._stop_event.is_set():
                        break
                    continue
                if callable(work):
                    self._execute_scoped(work)
                    continue
                counts, first_at, last_at = work
                batch = TriggerBatch(
                    repo=self.repo,
                    counts=counts,
                    first_at=first_at,
                    last_at=last_at,
                )
                self._execute_batch(batch)
        except Exception as exc:
            self._error = exc
            logger.error(
                "Service worker thread crashed for %s: %s",
                self.repo,
                exc,
                extra=self._labels,
                exc_info=True,
            )


class ServiceManager:
    """Coordinates the background workers, one per lane of each repository, the polling loop,
    and the lifecycle. Every trigger goes to each lane of its repository, so a round in one lane
    never waits for another lane's (#1532). With a `state_dir`, the halt and the budget window
    are kept there, and a restart reads them back (#2474)."""

    def __init__(
        self,
        config: ServiceConfig,
        secrets: dict[str, str],
        jobs: Mapping[str, LaneJob],
        clock: Callable[[], datetime],
        sleep_func: Callable[[float], Coroutine[Any, Any, None]],
        pause_until: PauseReader = no_round_pause,
        identity_refused: IdentityReader = no_identity_refusal,
        state_dir: Path | None = None,
    ) -> None:
        self.config = config
        self.secrets = secrets
        self.jobs = jobs
        network.set_model_call_limit(config.model_call_concurrency)
        self.clock = clock
        self.sleep_func = sleep_func
        self.managed_repos: set[str] = set(config.repos)
        self.state_dir: Path | None = state_dir
        self.bot_login: str | None = config.github_app.bot_login
        self.delivery_cache = DeliveryLRUCache()
        self.budget = RequestBudget(
            clock,
            config.github_requests_per_hour,
            record=None if state_dir is None else state_dir / CONST_SERVICE_BUDGET_FILENAME,
        )
        self.pause = RoundPause(
            clock,
            pause_until,
            identity_refused,
            self.budget,
            identity=config.github_app.bot_login or "unknown",
            halt_record=None if state_dir is None else state_dir / CONST_SERVICE_HALT_FILENAME,
        )
        self.workers: dict[tuple[str, str], RepoWorker] = {
            (repo, lane): RepoWorker(repo, lane, job, clock, self.pause)
            for repo in config.repos
            for lane, job in jobs.items()
        }
        self._stop_event = threading.Event()
        self._ready = False
        self._draining = False
        self._tick_task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        """Start worker threads and background polling loop."""
        set_request_gate(self.budget.admit)
        for worker in self.workers.values():
            worker.start()
        self._tick_task = asyncio.create_task(self._tick_loop(), name="service-poll-tick")
        self._ready = True

    async def _tick_loop(self) -> None:
        """Polling tick loop advancing time and scheduling periodic repository syncs."""
        self._poll()
        while not self._stop_event.is_set():
            await self.sleep_func(self.poll_interval())
            if self._stop_event.is_set():
                break
            self._poll()

    def poll_interval(self) -> float:
        """Seconds to the next poll: the configured interval, or the one the hourly request
        budget pays for, whichever is longer (#2161)."""
        return self.budget.poll_interval(
            float(self.config.poll_interval_seconds), rounds_per_poll=len(self.workers)
        )

    def _poll(self) -> None:
        """Enqueue a poll trigger on every lane of every repository, counted once per
        repository."""
        for repo in self.managed_repos:
            self.enqueue_trigger(repo, CONST_SERVICE_SOURCE_POLL, "", "")
            GLOBAL_METRICS.increment_counter(
                CONST_SERVICE_METRIC_TRIGGERS,
                labels={"repo": repo, "source": CONST_SERVICE_SOURCE_POLL},
            )

    def enqueue_trigger(self, repo: str, source: str, event: str, action: str) -> bool:
        """Enqueue a trigger on every lane of the repository; False for an unmanaged one."""
        if repo not in self.managed_repos:
            return False
        for lane in self.jobs:
            self.workers[(repo, lane)].enqueue(source=source, event=event, action=action)
        return True

    def enqueue_scoped(self, repo: str, lane: str, scoped_func: Callable[[], None]) -> bool:
        """Enqueue a scoped update task on the specified lane worker of the repository; False for
        an unmanaged repository or unknown lane."""
        if repo not in self.managed_repos:
            return False
        worker = self.workers.get((repo, lane))
        if worker is None:
            return False
        worker.enqueue_scoped(scoped_func)
        return True

    def is_ready(self) -> bool:
        """Return True when service startup is complete and service is not draining."""
        return self._ready and not self._draining and not self._stop_event.is_set()

    def is_draining(self) -> bool:
        """Return True during shutdown drain."""
        return self._draining

    def is_healthy(self) -> bool:
        """Return True when all worker threads and the polling loop are operating normally."""
        if self._stop_event.is_set():
            return False
        for worker in self.workers.values():
            if not worker.is_alive():
                return False
        if self._tick_task is not None and self._tick_task.done():
            return False
        return True

    async def drain_and_stop(self) -> bool:
        """Initiate graceful shutdown, drain active jobs and stop each worker within configured
        timeout; the rounds a pause holds are not run. Returns whether every worker drained and
        stopped before the timeout."""
        self._draining = True
        self._stop_event.set()
        self.budget.close()
        if self._tick_task is not None and not self._tick_task.done():
            self._tick_task.cancel()
            try:
                await self._tick_task
            except asyncio.CancelledError, Exception:
                pass

        timeout = float(self.config.drain_timeout_seconds)
        deadline = time.perf_counter() + timeout
        cleanly_stopped = True
        for worker in self.workers.values():
            remaining = max(0.0, deadline - time.perf_counter())
            drained = worker.wait_active(remaining)
            worker.stop()
            joined = worker.join(max(0.0, deadline - time.perf_counter()))
            cleanly_stopped = cleanly_stopped and drained and joined
        set_request_gate(None)
        return cleanly_stopped


def _resolve_service_secrets(
    settings: Settings, explicit_secrets: dict[str, str] | None
) -> dict[str, str]:
    """Resolve and parse webhook secrets dictionary for managed repositories."""
    if explicit_secrets is not None:
        return explicit_secrets
    raw_secrets = get_service_webhook_secrets(settings)
    if not raw_secrets:
        return {}
    try:
        parsed = json.loads(raw_secrets)
        if isinstance(parsed, dict):
            return {str(k): str(v) for k, v in parsed.items()}
    except Exception:
        pass
    return {}


def _warn_missing_secrets(repos: list[str], secrets: dict[str, str]) -> None:
    """Warn for managed repositories lacking configured webhook secrets."""
    for repo in repos:
        if repo not in secrets:
            logger.warning(
                "No webhook secret configured for managed repository: %s",
                repo,
                extra={"repo": repo},
            )


def _append_trace_headers(response: Response, tracer: Any, start_time: float) -> Response:
    """Attach process timing and W3C distributed trace context headers to HTTP response."""
    process_time = time.perf_counter() - start_time
    response.headers["X-Process-Time"] = f"{process_time:.4f}s"
    response.headers["X-DevOps-Version"] = __version__
    curr_trace = tracer.current_trace_id
    curr_span = tracer.current_span_id
    if curr_trace:
        response.headers["X-Trace-ID"] = curr_trace
        if curr_span:
            response.headers["traceparent"] = f"00-{curr_trace}-{curr_span}-01"
    return response


async def _service_trace_middleware(request: Request, call_next: Any) -> Any:
    """HTTP tracing and timing middleware for service application."""
    start_time = time.perf_counter()
    if request.url.path in CONST_SERVICE_PROBE_PATHS:
        response = await call_next(request)
        response.headers["X-Process-Time"] = f"{time.perf_counter() - start_time:.4f}s"
        response.headers["X-DevOps-Version"] = __version__
        return response

    tracer = get_tracer()
    span_name = f"HTTP {request.method} {request.url.path}"
    headers_dict = dict(request.headers)
    safe_url = str(request.url.replace(query=""))
    with tracer.span(
        span_name,
        kind="server",
        attributes={
            "http.request.method": request.method,
            "url.full": safe_url,
            "url.path": request.url.path,
            "url.scheme": request.url.scheme,
            "server.address": request.url.hostname or "localhost",
            "server.port": request.url.port or 8000,
            "user_agent.original": request.headers.get("user-agent", ""),
        },
        parent_context=headers_dict,
    ) as handle:
        response = await call_next(request)
        _append_trace_headers(response, tracer, start_time)
        handle.set_attribute("http.response.status_code", response.status_code)
        handle.set_attribute("http.status_code", response.status_code)
        return response


def create_service_app(
    jobs: Mapping[str, LaneJob] | None = None,
    settings: Settings | None = None,
    secrets: dict[str, str] | None = None,
    clock: Callable[[], datetime] | None = None,
    sleep_func: Callable[[float], Coroutine[Any, Any, None]] | None = None,
    pause_until: PauseReader | None = None,
    identity_refused: IdentityReader | None = None,
    consumers: Sequence[WebhookConsumer] | None = None,
    state_dir: Path | None = None,
) -> FastAPI:
    """Construct production FastAPI service application. `jobs` is each lane's job, run by one
    worker per lane of each repository, the default logging job in one lane when none is given;
    `pause_until` reads the time a failed round's error names, before which no lane of any
    repository starts a round; `identity_refused` reads whether that error says GitHub refused
    the Service's identity, which stops every round for good; `consumers` take the webhook
    events, the roadmap consumer when none are given; `state_dir` keeps the halt and the budget
    window across a restart, which then keeps the halt until a person removes its record."""
    active_settings = settings or load_settings()
    service_secrets = _resolve_service_secrets(active_settings, secrets)
    service_clock = clock or (lambda: datetime.now(UTC))
    service_sleep = sleep_func or asyncio.sleep
    lane_jobs = jobs or {CONST_SERVICE_LANE_DEFAULT: default_service_job}
    pause_reader = pause_until or no_round_pause

    _warn_missing_secrets(active_settings.service.repos, service_secrets)
    for http_logger_name in ("httpx", "httpx2", "httpcore"):
        logging.getLogger(http_logger_name).setLevel(logging.WARNING)

    manager = ServiceManager(
        config=active_settings.service,
        secrets=service_secrets,
        jobs=lane_jobs,
        clock=service_clock,
        sleep_func=service_sleep,
        pause_until=pause_reader,
        identity_refused=identity_refused or no_identity_refusal,
        state_dir=state_dir,
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        await manager.start()
        try:
            yield
        finally:
            await manager.drain_and_stop()

    app = FastAPI(
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        lifespan=lifespan,
    )
    app.state.service_manager = manager
    app.state.jobs = lane_jobs
    app.state.pause_until = pause_reader

    app.middleware("http")(_service_trace_middleware)
    app.include_router(create_webhook_router(manager, consumers))

    @app.get("/readyz")
    async def readyz() -> Response:
        if not manager.is_ready():
            return JSONResponse(status_code=503, content={"status": "not_ready"})
        return JSONResponse(status_code=200, content={"status": "ready"})

    @app.get("/healthz")
    async def healthz() -> Response:
        if not manager.is_healthy():
            return JSONResponse(status_code=503, content={"status": "unhealthy"})
        return JSONResponse(status_code=200, content={"status": "healthy"})

    @app.get("/metrics")
    async def metrics() -> Response:
        return Response(
            content=generate_latest(GLOBAL_METRICS.registry),
            media_type=CONTENT_TYPE_LATEST,
        )

    return app
