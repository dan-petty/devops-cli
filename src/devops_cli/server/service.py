"""Continuous background service mode engine for devops-cli."""

from __future__ import annotations

import asyncio
import json
import logging
import threading
import time
from collections.abc import AsyncIterator, Callable, Coroutine
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Any

from fastapi import FastAPI, Response
from fastapi.responses import JSONResponse, PlainTextResponse
from pydantic import BaseModel, ConfigDict

from devops_cli.config.constants import (
    CONST_SERVICE_METRIC_JOB_SECONDS,
    CONST_SERVICE_METRIC_JOB_START_TIMESTAMP,
    CONST_SERVICE_METRIC_JOBS,
    CONST_SERVICE_METRIC_QUEUE_DEPTH,
    CONST_SERVICE_METRIC_TRIGGERS,
    CONST_SERVICE_SOURCE_POLL,
)
from devops_cli.config.settings import (
    ServiceConfig,
    Settings,
    get_service_webhook_secrets,
    load_settings,
)
from devops_cli.server.routes.webhooks import DeliveryLRUCache, create_webhook_router
from devops_cli.telemetry.metrics import GLOBAL_METRICS

logger = logging.getLogger(__name__)


class TriggerBatch(BaseModel):
    """Immutable batch of coalesced repository trigger events."""

    model_config = ConfigDict(frozen=True)

    repo: str
    counts: dict[tuple[str, str, str], int]
    first_at: datetime
    last_at: datetime


def default_service_job(batch: TriggerBatch) -> None:
    """Default fallback job executing for repository events when no custom handler is given."""
    logger.info(
        "Service job triggered for repository: %s with %d trigger types",
        batch.repo,
        len(batch.counts),
        extra={"repo": batch.repo},
    )


class RepoWorker:
    """Dedicated daemon worker thread maintaining a single-concurrency queue for one repository."""

    def __init__(
        self,
        repo: str,
        job_func: Callable[[TriggerBatch], None],
        clock: Callable[[], datetime],
    ) -> None:
        self.repo = repo
        self.job_func = job_func
        self.clock = clock
        self._cond = threading.Condition()
        self._stop_event = threading.Event()
        self._is_active = False
        self._pending_counts: dict[tuple[str, str, str], int] = {}
        self._first_at: datetime | None = None
        self._last_at: datetime | None = None
        self._thread: threading.Thread | None = None
        self._error: Exception | None = None

    def start(self) -> None:
        """Start the daemon worker thread."""
        self._thread = threading.Thread(
            target=self._run,
            name=f"service-worker-{self.repo}",
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
            GLOBAL_METRICS.set_gauge(
                CONST_SERVICE_METRIC_QUEUE_DEPTH, 1.0, labels={"repo": self.repo}
            )
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

    def wait_active(self, timeout: float) -> bool:
        """Wait until currently active job completes or timeout expires."""
        deadline = time.perf_counter() + timeout
        while time.perf_counter() < deadline:
            with self._cond:
                if not self._is_active:
                    return True
            time.sleep(0.02)
        with self._cond:
            return not self._is_active

    def _wait_for_next_batch(
        self,
    ) -> tuple[dict[tuple[str, str, str], int], datetime, datetime] | None:
        """Wait for pending events and pop them into a batch tuple."""
        with self._cond:
            while not self._pending_counts and not self._stop_event.is_set():
                self._cond.wait(timeout=0.2)
            if self._stop_event.is_set() and not self._pending_counts:
                return None
            if not self._pending_counts:
                return None
            counts = dict(self._pending_counts)
            first_at = self._first_at or self.clock()
            last_at = self._last_at or self.clock()
            self._pending_counts.clear()
            self._first_at = None
            self._last_at = None
            self._is_active = True
            GLOBAL_METRICS.set_gauge(
                CONST_SERVICE_METRIC_QUEUE_DEPTH, 0.0, labels={"repo": self.repo}
            )
            return counts, first_at, last_at

    def _execute_batch(self, batch: TriggerBatch) -> None:
        """Execute the job function and record Prometheus metrics and execution duration."""
        start_time = time.perf_counter()
        start_epoch = time.time()
        GLOBAL_METRICS.set_gauge(
            CONST_SERVICE_METRIC_JOB_START_TIMESTAMP, start_epoch, labels={"repo": self.repo}
        )
        result = "success"
        try:
            self.job_func(batch)
        except Exception as exc:
            result = "error"
            logger.error(
                "Service job execution failed for %s: %s",
                self.repo,
                exc,
                extra={"repo": self.repo, "result": "error"},
                exc_info=True,
            )
        finally:
            duration = time.perf_counter() - start_time
            GLOBAL_METRICS.increment_counter(
                CONST_SERVICE_METRIC_JOBS,
                labels={"repo": self.repo, "result": result},
            )
            GLOBAL_METRICS.increment_counter(
                CONST_SERVICE_METRIC_JOB_SECONDS,
                value=duration,
                labels={"repo": self.repo},
            )
            with self._cond:
                self._is_active = False

    def _run(self) -> None:
        """Main loop of daemon worker thread."""
        try:
            while not self._stop_event.is_set():
                batch_data = self._wait_for_next_batch()
                if batch_data is None:
                    if self._stop_event.is_set():
                        break
                    continue
                counts, first_at, last_at = batch_data
                batch = TriggerBatch(
                    repo=self.repo,
                    counts=counts,
                    first_at=first_at,
                    last_at=last_at,
                )
                self._execute_batch(batch)
        except Exception as exc:
            self._error = exc
            logger.error("Service worker thread crashed for %s: %s", self.repo, exc, exc_info=True)


class ServiceManager:
    """Coordinates per-repo queues, background workers, polling loop, and lifecycle."""

    def __init__(
        self,
        config: ServiceConfig,
        secrets: dict[str, str],
        job_func: Callable[[TriggerBatch], None],
        clock: Callable[[], datetime],
        sleep_func: Callable[[float], Coroutine[Any, Any, None]],
    ) -> None:
        self.config = config
        self.secrets = secrets
        self.job_func = job_func
        self.clock = clock
        self.sleep_func = sleep_func
        self.managed_repos: set[str] = set(config.repos)
        self.machine_account: str | None = config.machine_account
        self.delivery_cache = DeliveryLRUCache()
        self.workers: dict[str, RepoWorker] = {
            repo: RepoWorker(repo, job_func, clock) for repo in config.repos
        }
        self._stop_event = threading.Event()
        self._ready = False
        self._draining = False
        self._tick_task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        """Start worker threads and background polling loop."""
        for worker in self.workers.values():
            worker.start()
        self._tick_task = asyncio.create_task(self._tick_loop(), name="service-poll-tick")
        self._ready = True

    async def _tick_loop(self) -> None:
        """Polling tick loop advancing time and scheduling periodic repository syncs."""
        for repo, worker in self.workers.items():
            worker.enqueue(source=CONST_SERVICE_SOURCE_POLL, event="", action="")
            GLOBAL_METRICS.increment_counter(
                CONST_SERVICE_METRIC_TRIGGERS,
                labels={"repo": repo, "source": CONST_SERVICE_SOURCE_POLL},
            )

        interval = float(self.config.poll_interval_seconds)
        while not self._stop_event.is_set():
            await self.sleep_func(interval)
            if self._stop_event.is_set():
                break
            for repo, worker in self.workers.items():
                worker.enqueue(source=CONST_SERVICE_SOURCE_POLL, event="", action="")
                GLOBAL_METRICS.increment_counter(
                    CONST_SERVICE_METRIC_TRIGGERS,
                    labels={"repo": repo, "source": CONST_SERVICE_SOURCE_POLL},
                )

    def enqueue_trigger(self, repo: str, source: str, event: str, action: str) -> bool:
        """Enqueue a trigger to the specified repository worker queue."""
        worker = self.workers.get(repo)
        if worker is None:
            return False
        worker.enqueue(source=source, event=event, action=action)
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

    async def drain_and_stop(self) -> None:
        """Initiate graceful shutdown and drain active jobs within configured timeout."""
        self._draining = True
        self._stop_event.set()
        if self._tick_task is not None and not self._tick_task.done():
            self._tick_task.cancel()
            try:
                await self._tick_task
            except asyncio.CancelledError, Exception:
                pass

        timeout = float(self.config.drain_timeout_seconds)
        deadline = time.perf_counter() + timeout
        for worker in self.workers.values():
            remaining = max(0.0, deadline - time.perf_counter())
            worker.wait_active(remaining)
            worker.stop()


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


def create_service_app(
    job: Callable[[TriggerBatch], None] | None = None,
    settings: Settings | None = None,
    secrets: dict[str, str] | None = None,
    clock: Callable[[], datetime] | None = None,
    sleep_func: Callable[[float], Coroutine[Any, Any, None]] | None = None,
) -> FastAPI:
    """Construct production FastAPI service application."""
    active_settings = settings or load_settings()
    service_secrets = _resolve_service_secrets(active_settings, secrets)
    service_clock = clock or (lambda: datetime.now(UTC))
    service_sleep = sleep_func or asyncio.sleep
    job_handler = job or default_service_job

    for repo in active_settings.service.repos:
        if repo not in service_secrets:
            logger.warning(
                "No webhook secret configured for managed repository: %s",
                repo,
                extra={"repo": repo},
            )

    manager = ServiceManager(
        config=active_settings.service,
        secrets=service_secrets,
        job_func=job_handler,
        clock=service_clock,
        sleep_func=service_sleep,
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
    app.state.job = job_handler

    app.include_router(create_webhook_router(manager))

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
        return PlainTextResponse(
            GLOBAL_METRICS.export_prometheus_text(),
            media_type="text/plain; version=0.0.4; charset=utf-8",
        )

    return app
