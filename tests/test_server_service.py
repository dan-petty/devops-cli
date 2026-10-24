"""Unit tests for service mode, webhook verification, and each repository's lane queues."""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging
import queue
import sys
import threading
from collections.abc import Callable, Mapping
from datetime import UTC, datetime, timedelta
from functools import partial
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from prometheus_client.parser import text_string_to_metric_families
from pydantic import ValidationError, create_model

from devops_cli.config.constants import (
    CONST_GH_RATE_LIMIT_CLOCK_SKEW_BOUND_SECONDS,
    CONST_GH_WEBHOOK_DELIVERY_HEADER,
    CONST_GH_WEBHOOK_EVENT_HEADER,
    CONST_GH_WEBHOOK_SIGNATURE_HEADER,
    CONST_MAX_ERROR_DETAIL_LENGTH,
    CONST_ROADMAP_INTAKE_BATCH_KEYS,
    CONST_SERVICE_LANE_DEFAULT,
    CONST_SERVICE_LANE_MODEL,
    CONST_SERVICE_LANE_STATUS,
    CONST_SERVICE_METRIC_JOB_SECONDS,
    CONST_SERVICE_METRIC_JOB_START_TIMESTAMP,
    CONST_SERVICE_METRIC_JOBS,
    CONST_SERVICE_METRIC_QUEUE_DEPTH,
    CONST_SERVICE_METRIC_TRIGGERS,
    CONST_SERVICE_METRIC_WEBHOOK_DELIVERIES,
    WebhookProviderName,
)
from devops_cli.config.settings import ServiceConfig, Settings
from devops_cli.exceptions import RoadmapRunError
from devops_cli.exceptions.git import GitHubRateLimitError
from devops_cli.roadmap.board_read import GraphQLBudget, require_budget, require_write_floor
from devops_cli.roadmap.memory_store import InMemoryRoadmapStore
from devops_cli.roadmap.run import JobOutcome, build_stub_table, run_due_jobs, service_pause_until
from devops_cli.server.json_logs import JsonLogFormatter
from devops_cli.server.routes.webhooks import (
    HmacSha256,
    WebhookConsumer,
    create_webhook_router,
    invalid_payload_detail,
    roadmap_consumer,
)
from devops_cli.server.service import (
    PauseReader,
    RepoWorker,
    ServiceManager,
    TriggerBatch,
    create_service_app,
)
from devops_cli.telemetry.instruments import AI_REQUESTS_TOTAL, emit
from devops_cli.telemetry.metrics import GLOBAL_METRICS
from devops_cli.telemetry.tracer import (
    OTelTelemetryClient,
    _from_otlp_any_value,
    get_tracer,
    reset_tracer,
)
from tests.support.telemetry_capture import Captured
from tests.support.waits import THREAD_HANDOFF_BOUND_SECONDS, wait_until

LANE = CONST_SERVICE_LANE_DEFAULT
"""The one lane of the tests that run one job per repository."""


def _sign(payload: bytes, secret: str) -> str:
    """Generate X-Hub-Signature-256 header value for given payload and secret."""
    digest = hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


def _make_settings(
    repos: list[str] | None = None,
    machine_account: str | None = "bot-account",
    poll_interval: int = 300,
    drain_timeout: int = 120,
) -> Settings:
    """Helper creating Settings with configured ServiceConfig."""
    service_conf = ServiceConfig(
        repos=repos or ["example-org/repo1", "example-org/repo2"],
        machine_account=machine_account,
        poll_interval_seconds=poll_interval,
        drain_timeout_seconds=drain_timeout,
    )
    return Settings(service=service_conf)


@pytest.fixture(autouse=True)
def _reset_metrics() -> None:
    """Reset global metrics registry and tracer before each test."""
    GLOBAL_METRICS.reset()
    reset_tracer()
    yield
    reset_tracer()


def test_hmac_sha256_verifier_checks_the_header_digest_against_each_subjects_secret() -> None:
    """The verifier accepts only the digest of the body under a subject's own secret, compared
    in constant time, and names every subject whose secret matches."""
    verifier = HmacSha256(header=CONST_GH_WEBHOOK_SIGNATURE_HEADER, prefix="sha256=")
    payload = b'{"hello":"world"}'
    secret = "test-secret-key"
    sig = _sign(payload, secret)

    checks = (
        verifier.verify(payload, sig, secret),
        verifier.verify(payload, "sha256=invalidhash", secret),
        verifier.verify(payload, "invalid_format", secret),
        verifier.verify(payload, sig, ""),
        verifier.verify(payload, None, secret),
        verifier.verify(payload, "sha256=\u00e9", secret),
    )
    secrets = {"example-org/repo1": secret, "example-org/repo2": "other-secret", "no-secret": ""}

    assert (checks, verifier.signers(payload, sig, secrets)) == (
        (True, False, False, False, False, False),
        frozenset({"example-org/repo1"}),
    )


def test_webhook_delivery_and_batch_coalescing() -> None:
    """Test that incoming deliveries queue and coalesce into a TriggerBatch while job is active."""
    settings = _make_settings(repos=["example-org/repo1"])
    secrets = {"example-org/repo1": "secret-1"}
    job_started = threading.Event()
    job_unblock = threading.Event()
    job_2_done = threading.Event()
    received_batches: list[TriggerBatch] = []
    unblocked: list[bool] = []

    def test_job(batch: TriggerBatch) -> None:
        if ("poll", "", "") in batch.counts and len(batch.counts) == 1:
            return
        received_batches.append(batch)
        if ("webhook", "issues", "opened") in batch.counts:
            job_started.set()
            unblocked.append(job_unblock.wait(timeout=THREAD_HANDOFF_BOUND_SECONDS))
        elif ("webhook", "issues", "labeled") in batch.counts:
            job_2_done.set()

    app = create_service_app(jobs={LANE: test_job}, settings=settings, secrets=secrets)

    with TestClient(app) as client:
        # First delivery: triggers the job
        payload_1 = json.dumps(
            {
                "repository": {"full_name": "example-org/repo1"},
                "action": "opened",
                "sender": {"login": "human-user"},
            }
        ).encode("utf-8")
        headers_1 = {
            "Content-Type": "application/json",
            CONST_GH_WEBHOOK_EVENT_HEADER: "issues",
            CONST_GH_WEBHOOK_DELIVERY_HEADER: "delivery-1",
            CONST_GH_WEBHOOK_SIGNATURE_HEADER: _sign(payload_1, "secret-1"),
        }
        res_1 = client.post("/webhooks/github", content=payload_1, headers=headers_1)
        assert (res_1.status_code, res_1.json()["status"]) == (202, "accepted")

        # Wait until the job starts and is blocked
        assert job_started.wait(timeout=THREAD_HANDOFF_BOUND_SECONDS) is True

        # Second delivery arriving while job 1 is running: must coalesce
        payload_2 = json.dumps(
            {
                "repository": {"full_name": "example-org/repo1"},
                "action": "labeled",
                "sender": {"login": "human-user"},
            }
        ).encode("utf-8")
        headers_2 = {
            "Content-Type": "application/json",
            CONST_GH_WEBHOOK_EVENT_HEADER: "issues",
            CONST_GH_WEBHOOK_DELIVERY_HEADER: "delivery-2",
            CONST_GH_WEBHOOK_SIGNATURE_HEADER: _sign(payload_2, "secret-1"),
        }
        res_2 = client.post("/webhooks/github", content=payload_2, headers=headers_2)
        assert (res_2.status_code, res_2.json()["status"]) == (202, "accepted")

        # Unblock first job and wait for worker to pick up coalesced batch
        job_unblock.set()
        assert job_2_done.wait(timeout=THREAD_HANDOFF_BOUND_SECONDS) is True

    assert (len(received_batches), unblocked) == (2, [True])
    b1, b2 = received_batches[0], received_batches[1]
    assert (
        b1.repo,
        b1.counts[("webhook", "issues", "opened")],
        b2.repo,
        b2.counts[("webhook", "issues", "labeled")],
    ) == ("example-org/repo1", 1, "example-org/repo1", 1)


def test_webhook_authentication_rejections(caplog: pytest.LogCaptureFixture) -> None:
    """Test 401 rejections for missing/invalid signatures, wrong repos, and unmanaged repos."""
    settings = _make_settings(
        repos=["example-org/repo1", "example-org/repo2", "example-org/no-secret-repo"]
    )
    secrets = {"example-org/repo1": "secret-1", "example-org/repo2": "secret-2"}

    with caplog.at_level(logging.WARNING):
        app = create_service_app(settings=settings, secrets=secrets)
    assert any(
        "No webhook secret configured for managed repository" in rec.message
        for rec in caplog.records
    )

    with TestClient(app) as client:
        payload = json.dumps(
            {
                "repository": {"full_name": "example-org/repo1"},
                "action": "opened",
            }
        ).encode("utf-8")
        base_headers = {
            "Content-Type": "application/json",
            CONST_GH_WEBHOOK_EVENT_HEADER: "issues",
            CONST_GH_WEBHOOK_DELIVERY_HEADER: "deliv-auth",
        }

        # 1. Missing signature
        res_missing = client.post("/webhooks/github", content=payload, headers=base_headers)
        # 2. Wrong signature
        h_wrong = dict(base_headers, **{CONST_GH_WEBHOOK_SIGNATURE_HEADER: "sha256=badhash"})
        res_wrong = client.post("/webhooks/github", content=payload, headers=h_wrong)
        # 3. Signature from another managed repo
        h_other = dict(
            base_headers, **{CONST_GH_WEBHOOK_SIGNATURE_HEADER: _sign(payload, "secret-2")}
        )
        res_other = client.post("/webhooks/github", content=payload, headers=h_other)
        # 4. Unmanaged repo payload
        payload_unmanaged = json.dumps(
            {
                "repository": {"full_name": "example-org/unmanaged"},
                "action": "opened",
            }
        ).encode("utf-8")
        h_unmanaged = dict(
            base_headers,
            **{CONST_GH_WEBHOOK_SIGNATURE_HEADER: _sign(payload_unmanaged, "secret-1")},
        )
        res_unmanaged = client.post(
            "/webhooks/github", content=payload_unmanaged, headers=h_unmanaged
        )
        # 5. Managed repo with no secret
        payload_nosecret = json.dumps(
            {
                "repository": {"full_name": "example-org/no-secret-repo"},
                "action": "opened",
            }
        ).encode("utf-8")
        h_nosecret = dict(base_headers, **{CONST_GH_WEBHOOK_SIGNATURE_HEADER: "sha256=any"})
        res_nosecret = client.post("/webhooks/github", content=payload_nosecret, headers=h_nosecret)

        assert (
            res_missing.status_code,
            res_wrong.status_code,
            res_other.status_code,
            res_unmanaged.status_code,
            res_nosecret.status_code,
        ) == (401, 401, 401, 401, 401)


def test_webhook_duplicate_and_ignored_deliveries() -> None:
    """Test 200 responses for duplicate deliveries, ping events, and machine account triggers."""
    settings = _make_settings(repos=["example-org/repo1"], machine_account="bot-account")
    secrets = {"example-org/repo1": "secret-1"}
    received_batches: list[TriggerBatch] = []

    app = create_service_app(
        jobs={LANE: received_batches.append}, settings=settings, secrets=secrets
    )

    with TestClient(app) as client:
        # Normal delivery
        payload = json.dumps(
            {
                "repository": {"full_name": "example-org/repo1"},
                "action": "opened",
                "sender": {"login": "human-user"},
            }
        ).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            CONST_GH_WEBHOOK_EVENT_HEADER: "issues",
            CONST_GH_WEBHOOK_DELIVERY_HEADER: "dup-delivery-id",
            CONST_GH_WEBHOOK_SIGNATURE_HEADER: _sign(payload, "secret-1"),
        }
        res_initial = client.post("/webhooks/github", content=payload, headers=headers)
        # Duplicate replay of same delivery id
        res_dup = client.post("/webhooks/github", content=payload, headers=headers)

        # Ping event
        ping_headers = dict(
            headers,
            **{
                CONST_GH_WEBHOOK_EVENT_HEADER: "ping",
                CONST_GH_WEBHOOK_DELIVERY_HEADER: "ping-delivery-id",
            },
        )
        res_ping = client.post("/webhooks/github", content=payload, headers=ping_headers)

        # Machine account event (case-insensitive check)
        bot_payload = json.dumps(
            {
                "repository": {"full_name": "example-org/repo1"},
                "action": "opened",
                "sender": {"login": "BOT-ACCOUNT"},
            }
        ).encode("utf-8")
        bot_headers = {
            "Content-Type": "application/json",
            CONST_GH_WEBHOOK_EVENT_HEADER: "issues",
            CONST_GH_WEBHOOK_DELIVERY_HEADER: "bot-delivery-id",
            CONST_GH_WEBHOOK_SIGNATURE_HEADER: _sign(bot_payload, "secret-1"),
        }
        res_bot = client.post("/webhooks/github", content=bot_payload, headers=bot_headers)

        assert (
            res_initial.status_code,
            res_dup.status_code,
            res_dup.json()["status"],
            res_ping.status_code,
            res_ping.json()["status"],
            res_bot.status_code,
            res_bot.json()["status"],
        ) == (202, 200, "duplicate", 200, "pong", 200, "ignored_machine_account")


def test_webhook_payload_size_and_bad_request() -> None:
    """Test 413 for oversized payloads, 415 for invalid content type, and 400 for bad headers/body."""
    settings = _make_settings(repos=["example-org/repo1"])
    secrets = {"example-org/repo1": "secret-1"}
    app = create_service_app(settings=settings, secrets=secrets)

    with TestClient(app) as client:
        base_headers = {
            "Content-Type": "application/json",
            CONST_GH_WEBHOOK_EVENT_HEADER: "issues",
            CONST_GH_WEBHOOK_DELIVERY_HEADER: "size-deliv",
            CONST_GH_WEBHOOK_SIGNATURE_HEADER: "sha256=dummy",
        }

        # 413 via Content-Length header
        res_413_header = client.post(
            "/webhooks/github",
            content=b"{}",
            headers=dict(base_headers, **{"Content-Length": str(26 * 1024 * 1024)}),
        )
        # 415 for non-json
        res_415 = client.post(
            "/webhooks/github",
            content=b"not json",
            headers=dict(base_headers, **{"Content-Type": "text/plain"}),
        )
        # 400 for missing event header
        h_no_event = dict(base_headers)
        del h_no_event[CONST_GH_WEBHOOK_EVENT_HEADER]
        res_400_no_event = client.post("/webhooks/github", content=b"{}", headers=h_no_event)

        # 400 for invalid JSON body with valid signature
        invalid_body = b"not a json object"
        h_valid_sig = dict(
            base_headers,
            **{
                CONST_GH_WEBHOOK_SIGNATURE_HEADER: _sign(invalid_body, "secret-1"),
            },
        )
        res_400_bad_json = client.post(
            "/webhooks/github", content=invalid_body, headers=h_valid_sig
        )

        assert (
            res_413_header.status_code,
            res_415.status_code,
            res_400_no_event.status_code,
            res_400_bad_json.status_code,
        ) == (413, 415, 400, 400)


def test_multi_concurrency_coalescing_and_multi_repo() -> None:
    """Test 10 concurrent triggers coalesce into one run and multi-repos execute concurrently."""
    settings = _make_settings(repos=["example-org/repo1", "example-org/repo2"])
    secrets = {"example-org/repo1": "secret-1", "example-org/repo2": "secret-2"}

    repo1_blocked = threading.Event()
    repo1_release = threading.Event()
    batches_by_repo: dict[str, list[TriggerBatch]] = {
        "example-org/repo1": [],
        "example-org/repo2": [],
    }
    repo1_concurrency = 0
    max_repo1_concurrency = 0
    concurrency_lock = threading.Lock()

    repo2_done = threading.Event()
    bulk_done = threading.Event()
    repo1_released: list[bool] = []
    repo1_running_beside_repo2: list[int] = []

    def concurrent_job(batch: TriggerBatch) -> None:
        nonlocal repo1_concurrency, max_repo1_concurrency
        if ("poll", "", "") in batch.counts and len(batch.counts) == 1:
            return
        if batch.repo == "example-org/repo1":
            with concurrency_lock:
                repo1_concurrency += 1
                if repo1_concurrency > max_repo1_concurrency:
                    max_repo1_concurrency = repo1_concurrency
            batches_by_repo[batch.repo].append(batch)
            if ("webhook", "issues", "initial") in batch.counts:
                repo1_blocked.set()
                repo1_released.append(repo1_release.wait(timeout=THREAD_HANDOFF_BOUND_SECONDS))
            elif sum(batch.counts.values()) == 10:
                bulk_done.set()
            with concurrency_lock:
                repo1_concurrency -= 1
        else:
            with concurrency_lock:
                repo1_running_beside_repo2.append(repo1_concurrency)
            batches_by_repo[batch.repo].append(batch)
            repo2_done.set()

    app = create_service_app(jobs={LANE: concurrent_job}, settings=settings, secrets=secrets)

    with TestClient(app) as client:
        # Trigger Repo 1 initial job
        p1 = json.dumps(
            {"repository": {"full_name": "example-org/repo1"}, "action": "initial"}
        ).encode("utf-8")
        h1 = {
            "Content-Type": "application/json",
            CONST_GH_WEBHOOK_EVENT_HEADER: "issues",
            CONST_GH_WEBHOOK_DELIVERY_HEADER: "r1-init",
            CONST_GH_WEBHOOK_SIGNATURE_HEADER: _sign(p1, "secret-1"),
        }
        client.post("/webhooks/github", content=p1, headers=h1)
        assert repo1_blocked.wait(timeout=THREAD_HANDOFF_BOUND_SECONDS) is True

        # While Repo 1 is blocked, trigger Repo 2 (proves no cross-blocking)
        p2 = json.dumps(
            {"repository": {"full_name": "example-org/repo2"}, "action": "r2-action"}
        ).encode("utf-8")
        h2 = {
            "Content-Type": "application/json",
            CONST_GH_WEBHOOK_EVENT_HEADER: "issues",
            CONST_GH_WEBHOOK_DELIVERY_HEADER: "r2-deliv",
            CONST_GH_WEBHOOK_SIGNATURE_HEADER: _sign(p2, "secret-2"),
        }
        res_r2 = client.post("/webhooks/github", content=p2, headers=h2)
        # Repo 2's round ran while Repo 1's was still running, not after it ended.
        assert (
            res_r2.status_code,
            repo2_done.wait(timeout=THREAD_HANDOFF_BOUND_SECONDS),
            repo1_running_beside_repo2,
        ) == (202, True, [1])
        assert len(batches_by_repo["example-org/repo2"]) == 1

        # While Repo 1 is still blocked, send 10 concurrent triggers to Repo 1
        for i in range(10):
            p_bulk = json.dumps(
                {"repository": {"full_name": "example-org/repo1"}, "action": f"act-{i}"}
            ).encode("utf-8")
            h_bulk = {
                "Content-Type": "application/json",
                CONST_GH_WEBHOOK_EVENT_HEADER: "issues",
                CONST_GH_WEBHOOK_DELIVERY_HEADER: f"bulk-{i}",
                CONST_GH_WEBHOOK_SIGNATURE_HEADER: _sign(p_bulk, "secret-1"),
            }
            res_bulk = client.post("/webhooks/github", content=p_bulk, headers=h_bulk)
            assert res_bulk.status_code == 202

        # Release Repo 1
        repo1_release.set()
        assert bulk_done.wait(timeout=THREAD_HANDOFF_BOUND_SECONDS) is True

    assert (len(batches_by_repo["example-org/repo1"]), max_repo1_concurrency, repo1_released) == (
        2,
        1,
        [True],
    )
    coalesced_batch = batches_by_repo["example-org/repo1"][1]
    assert sum(coalesced_batch.counts.values()) == 10


def test_polling_tick_advances_with_injected_fixtures() -> None:
    """Test polling tick loop schedules poll trigger at startup and after interval."""
    settings = _make_settings(repos=["example-org/repo1"], poll_interval=60)
    secrets = {"example-org/repo1": "secret-1"}
    tick_batches: list[TriggerBatch] = []
    tick_event = threading.Event()
    job_ran = threading.Event()

    simulated_now = datetime(2026, 10, 4, 12, 0, 0, tzinfo=UTC)

    def fake_clock() -> datetime:
        return simulated_now

    async def fake_sleep(seconds: float) -> None:
        nonlocal simulated_now
        simulated_now += timedelta(seconds=seconds)
        tick_event.set()
        await asyncio.sleep(0.01)

    def tick_job(batch: TriggerBatch) -> None:
        tick_batches.append(batch)
        job_ran.set()

    app = create_service_app(
        jobs={LANE: tick_job},
        settings=settings,
        secrets=secrets,
        clock=fake_clock,
        sleep_func=fake_sleep,
    )

    with TestClient(app):
        # The startup tick runs the job on the lane's worker thread at once, and the loop then
        # sleeps an interval. Both are awaited, not timed: a loaded machine overruns any fixed
        # pause before the worker thread is scheduled.
        assert (
            job_ran.wait(timeout=THREAD_HANDOFF_BOUND_SECONDS),
            tick_event.wait(timeout=THREAD_HANDOFF_BOUND_SECONDS),
        ) == (True, True)
        assert tick_batches[0].counts[("poll", "", "")] >= 1


def test_job_error_handling_and_metrics() -> None:
    """Test that job exceptions record jobs_total error metric and allow subsequent runs."""
    settings = _make_settings(repos=["example-org/repo1"])
    secrets = {"example-org/repo1": "secret-1"}
    should_fail = True

    job_failed = threading.Event()
    job_succeeded = threading.Event()

    def flake_job(batch: TriggerBatch) -> None:
        nonlocal should_fail
        if ("poll", "", "") in batch.counts and len(batch.counts) == 1:
            return
        if should_fail:
            should_fail = False
            job_failed.set()
            raise RuntimeError("Deliberate test failure")
        job_succeeded.set()

    app = create_service_app(jobs={LANE: flake_job}, settings=settings, secrets=secrets)

    with TestClient(app) as client:
        payload = json.dumps(
            {"repository": {"full_name": "example-org/repo1"}, "action": "test"}
        ).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            CONST_GH_WEBHOOK_EVENT_HEADER: "issues",
            CONST_GH_WEBHOOK_DELIVERY_HEADER: "deliv-err-1",
            CONST_GH_WEBHOOK_SIGNATURE_HEADER: _sign(payload, "secret-1"),
        }
        # Run 1: will fail
        res1 = client.post("/webhooks/github", content=payload, headers=headers)
        assert (res1.status_code, job_failed.wait(timeout=THREAD_HANDOFF_BOUND_SECONDS)) == (
            202,
            True,
        )

        # Run 2: will succeed
        h2 = dict(headers, **{CONST_GH_WEBHOOK_DELIVERY_HEADER: "deliv-err-2"})
        res2 = client.post("/webhooks/github", content=payload, headers=h2)
        assert (res2.status_code, job_succeeded.wait(timeout=THREAD_HANDOFF_BOUND_SECONDS)) == (
            202,
            True,
        )

    err_count = GLOBAL_METRICS.get_counter_value(
        CONST_SERVICE_METRIC_JOBS,
        labels={"repo": "example-org/repo1", "lane": LANE, "result": "error"},
    )
    succ_count = GLOBAL_METRICS.get_counter_value(
        CONST_SERVICE_METRIC_JOBS,
        labels={"repo": "example-org/repo1", "lane": LANE, "result": "success"},
    )
    assert (err_count, succ_count >= 1.0) == (1.0, True)


def test_readyz_and_healthz_lifecycle() -> None:
    """Test /readyz (503 pre-start, 200 ready, 503 draining) and /healthz status."""
    settings = _make_settings(repos=["example-org/repo1"])
    secrets = {"example-org/repo1": "secret-1"}
    app = create_service_app(settings=settings, secrets=secrets)

    # 1. Prior to startup completion
    client_raw = TestClient(app)
    res_pre_ready = client_raw.get("/readyz")
    assert (res_pre_ready.status_code, res_pre_ready.json()["status"]) == (503, "not_ready")

    # 2. While ready in lifespan
    with TestClient(app) as client:
        res_ready = client.get("/readyz")
        res_health = client.get("/healthz")
        assert (
            res_ready.status_code,
            res_ready.json()["status"],
            res_health.status_code,
            res_health.json()["status"],
        ) == (200, "ready", 200, "healthy")

        # Simulate crash of worker
        worker = app.state.service_manager.workers[("example-org/repo1", LANE)]
        worker._error = RuntimeError("Worker thread died")
        res_unhealthy = client.get("/healthz")
        assert (res_unhealthy.status_code, res_unhealthy.json()["status"]) == (503, "unhealthy")


def test_service_app_strict_routes() -> None:
    """Test that only the service routes are served: the probes, the metrics and one webhook
    route for each declared provider. Any other route, and a provider nothing declares, is 404."""
    settings = _make_settings(repos=["example-org/repo1"])
    secrets = {"example-org/repo1": "secret-1"}
    app = create_service_app(settings=settings, secrets=secrets)
    served = set(app.openapi()["paths"])

    with TestClient(app) as client:
        res_root = client.get("/")
        res_docs = client.get("/docs")
        res_cfg = client.get("/api/v1/config")
        res_ready = client.get("/readyz")
        res_health = client.get("/healthz")
        res_metrics = client.get("/metrics")
        res_undeclared = _github_post(
            client, "issues", _event_payload(), "undeclared-1", route="gitlab"
        )

        assert (
            served,
            res_root.status_code,
            res_docs.status_code,
            res_cfg.status_code,
            res_ready.status_code,
            res_health.status_code,
            res_metrics.status_code,
            res_undeclared.status_code,
        ) == (
            {
                "/readyz",
                "/healthz",
                "/metrics",
                *(f"/webhooks/{name}" for name in WebhookProviderName),
            },
            404,
            404,
            404,
            200,
            200,
            200,
            404,
        )


def test_prometheus_metrics_export() -> None:
    """Test GET /metrics output contains all required service metric families."""
    settings = _make_settings(repos=["example-org/repo1"])
    secrets = {"example-org/repo1": "secret-1"}
    app = create_service_app(settings=settings, secrets=secrets)

    with TestClient(app) as client:
        payload = json.dumps(
            {"repository": {"full_name": "example-org/repo1"}, "action": "test"}
        ).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            CONST_GH_WEBHOOK_EVENT_HEADER: "issues",
            CONST_GH_WEBHOOK_DELIVERY_HEADER: "metric-deliv",
            CONST_GH_WEBHOOK_SIGNATURE_HEADER: _sign(payload, "secret-1"),
        }
        client.post("/webhooks/github", content=payload, headers=headers)
        # The delivery's round has run once every worker is idle, not after a fixed pause.
        workers = app.state.service_manager.workers.values()
        assert all(worker.wait_active(THREAD_HANDOFF_BOUND_SECONDS) for worker in workers)

        res = client.get("/metrics")
        assert (res.status_code, res.headers["content-type"].startswith("text/plain")) == (
            200,
            True,
        )
        body = res.text
        assert (
            CONST_SERVICE_METRIC_WEBHOOK_DELIVERIES in body,
            CONST_SERVICE_METRIC_TRIGGERS in body,
            CONST_SERVICE_METRIC_JOBS in body,
            CONST_SERVICE_METRIC_JOB_SECONDS in body,
            CONST_SERVICE_METRIC_JOB_START_TIMESTAMP in body,
            CONST_SERVICE_METRIC_QUEUE_DEPTH in body,
        ) == (True, True, True, True, True, True)


def test_json_log_formatter_zero_leakage() -> None:
    """Test JsonLogFormatter emits valid single-line JSON without secret/signature leakage."""
    formatter = JsonLogFormatter()
    try:
        raise RuntimeError("Service exception with key gcp_abcdefghijklmnopqrstuvwxyz")
    except RuntimeError:
        exc_info = sys.exc_info()

    record = logging.LogRecord(
        name="test_logger",
        level=logging.INFO,
        pathname="service.py",
        lineno=42,
        msg="Service delivery failed with token glpat-abcdefghijklmnopqrstuvwxyz",
        args=(),
        exc_info=exc_info,
    )
    record.repo = "example-org/repo1"
    record.source = "webhook"
    record.event = "issues"
    record.action = "opened"
    record.delivery = "deliv-xyz"
    record.outcome = "accepted"
    record.duration_s = 0.045
    record.result = "success"
    record.lane = "model"
    # Unallowed/secret fields that must never appear in log output:
    record.secret = "SUPER_SECRET_KEY"
    record.signature = "sha256=abcdef123456"

    line = formatter.format(record)
    assert "\n" not in line
    data = json.loads(line)

    assert (
        data["level"],
        data["logger"],
        "glpat-abcdefghijklmnopqrstuvwxyz" in data["message"],
        "<masked-token>" in data["message"],
        "gcp_abcdefghijklmnopqrstuvwxyz" in data["exception"],
        "<masked-gcp-service-account>" in data["exception"],
        data["repo"],
        data["lane"],
        "secret" in data,
        "signature" in data,
    ) == (
        "INFO",
        "test_logger",
        False,
        True,
        False,
        True,
        "example-org/repo1",
        "model",
        False,
        False,
    )


def test_shutdown_drains_pending_delivery_enqueued_during_active_job() -> None:
    """Test that graceful shutdown drains follow-up deliveries enqueued while active batch was running."""
    settings = _make_settings(
        repos=["example-org/repo1"], drain_timeout=int(THREAD_HANDOFF_BOUND_SECONDS)
    )
    secrets = {"example-org/repo1": "secret-1"}
    batch1_started = threading.Event()
    batch1_release = threading.Event()
    received_batches: list[TriggerBatch] = []
    released: list[bool] = []

    def draining_job(batch: TriggerBatch) -> None:
        if ("poll", "", "") in batch.counts and len(batch.counts) == 1:
            return
        received_batches.append(batch)
        if ("webhook", "issues", "first") in batch.counts:
            batch1_started.set()
            released.append(batch1_release.wait(timeout=THREAD_HANDOFF_BOUND_SECONDS))

    app = create_service_app(jobs={LANE: draining_job}, settings=settings, secrets=secrets)

    with TestClient(app) as client:
        # 1. Enqueue first webhook to make worker active
        p1 = json.dumps(
            {"repository": {"full_name": "example-org/repo1"}, "action": "first"}
        ).encode("utf-8")
        h1 = {
            "Content-Type": "application/json",
            CONST_GH_WEBHOOK_EVENT_HEADER: "issues",
            CONST_GH_WEBHOOK_DELIVERY_HEADER: "deliv-1",
            CONST_GH_WEBHOOK_SIGNATURE_HEADER: _sign(p1, "secret-1"),
        }
        res1 = client.post("/webhooks/github", content=p1, headers=h1)
        assert res1.status_code == 202
        assert batch1_started.wait(timeout=THREAD_HANDOFF_BOUND_SECONDS) is True

        # 2. Enqueue second webhook while first batch is executing
        p2 = json.dumps(
            {"repository": {"full_name": "example-org/repo1"}, "action": "second"}
        ).encode("utf-8")
        h2 = {
            "Content-Type": "application/json",
            CONST_GH_WEBHOOK_EVENT_HEADER: "issues",
            CONST_GH_WEBHOOK_DELIVERY_HEADER: "deliv-2",
            CONST_GH_WEBHOOK_SIGNATURE_HEADER: _sign(p2, "secret-1"),
        }
        res2 = client.post("/webhooks/github", content=p2, headers=h2)
        assert res2.status_code == 202

        # 3. Unblock batch 1 to allow execution to proceed to batch 2 during shutdown
        batch1_release.set()

    # 4. Context exit runs drain_and_stop(). Verify both batches were executed without loss
    actions = [action for batch in received_batches for (_, _, action) in batch.counts]
    assert ("first" in actions, "second" in actions, len(received_batches), released) == (
        True,
        True,
        2,
        [True],
    )


def test_service_tracing_middleware_adds_headers_and_skips_probes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test HTTP tracing middleware attaches trace headers to endpoints but skips trace spans for probe paths."""
    sent_payloads: list[tuple[str, dict[str, Any]]] = []
    tracer = get_tracer()
    tracer.enabled = True
    monkeypatch.setattr(tracer, "_send_payload", lambda path, p: sent_payloads.append((path, p)))

    settings = _make_settings(repos=["example-org/repo1"])
    secrets = {"example-org/repo1": "secret-1"}
    app = create_service_app(settings=settings, secrets=secrets)

    with TestClient(app) as client:
        res_health = client.get("/healthz")
        res_ready = client.get("/readyz")
        res_metrics = client.get("/metrics")

        payload = json.dumps(
            {"repository": {"full_name": "example-org/repo1"}, "action": "opened"}
        ).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            CONST_GH_WEBHOOK_EVENT_HEADER: "issues",
            CONST_GH_WEBHOOK_DELIVERY_HEADER: "deliv-trace-1",
            CONST_GH_WEBHOOK_SIGNATURE_HEADER: _sign(payload, "secret-1"),
        }
        res_webhook = client.post("/webhooks/github", content=payload, headers=headers)

    assert (
        res_health.status_code,
        "X-Process-Time" in res_health.headers,
        "X-Trace-ID" in res_health.headers,
        res_ready.status_code,
        "X-Process-Time" in res_ready.headers,
        "X-Trace-ID" in res_ready.headers,
        res_metrics.status_code,
        "X-Process-Time" in res_metrics.headers,
        "X-Trace-ID" in res_metrics.headers,
        res_webhook.status_code,
        "X-Process-Time" in res_webhook.headers,
        "X-Trace-ID" in res_webhook.headers,
        "traceparent" in res_webhook.headers,
    ) == (
        200,
        True,
        False,
        200,
        True,
        False,
        200,
        True,
        False,
        202,
        True,
        True,
        True,
    )


def test_repo_worker_executes_batch_with_span(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test RepoWorker._execute_batch records tracer span with metadata, triggers, and error attributes."""
    sent_payloads: list[tuple[str, dict[str, Any]]] = []
    tracer = get_tracer()
    tracer.enabled = True
    monkeypatch.setattr(tracer, "_send_payload", lambda path, p: sent_payloads.append((path, p)))

    now = datetime.now(UTC)
    batch = TriggerBatch(
        repo="example-org/repo1",
        counts={("webhook", "issues", "opened"): 3, ("poll", "", ""): 1},
        first_at=now,
        last_at=now,
    )

    worker = RepoWorker(
        repo="example-org/repo1",
        lane=LANE,
        job_func=lambda b: None,
        clock=lambda: now,
    )
    worker._execute_batch(batch)

    def failing_job(b: TriggerBatch) -> None:
        raise RuntimeError("simulated job failure")

    failing_worker = RepoWorker(
        repo="example-org/repo1",
        lane=LANE,
        job_func=failing_job,
        clock=lambda: now,
    )
    failing_worker._execute_batch(batch)

    assert len(sent_payloads) == 2
    span_ok = sent_payloads[0][1]["resourceSpans"][0]["scopeSpans"][0]["spans"][0]
    span_err = sent_payloads[1][1]["resourceSpans"][0]["scopeSpans"][0]["spans"][0]

    attrs_ok = {a["key"]: _from_otlp_any_value(a["value"]) for a in span_ok["attributes"]}
    attrs_err = {a["key"]: _from_otlp_any_value(a["value"]) for a in span_err["attributes"]}

    assert (
        span_ok["name"],
        attrs_ok["service.repo"],
        attrs_ok["service.lane"],
        attrs_ok["service.triggers"],
        attrs_ok["service.trigger_types"],
        attrs_ok["service.result"],
        span_err["name"],
        attrs_err["service.repo"],
        attrs_err["service.result"],
        attrs_err["error"],
        attrs_err["error.message"],
    ) == (
        "service.job example-org/repo1",
        "example-org/repo1",
        LANE,
        4,
        2,
        "success",
        "service.job example-org/repo1",
        "example-org/repo1",
        "error",
        True,
        "simulated job failure",
    )


def test_each_batch_exports_its_ai_requests_before_the_workers_next_batch_starts(
    tracer: OTelTelemetryClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The Service runs every lane job in one long process, so each batch exports the counters
    it recorded when it ends, also when its job raises, and not only when the pod stops (#1629).
    Each export holds only its batch's delta, so the collector's running total is the sum of the
    requests recorded."""
    sink = Captured()
    monkeypatch.setattr(tracer, "_send_payload", sink)
    exported_at_start: list[int] = []

    def job(batch: TriggerBatch) -> None:
        exported_at_start.append(len(sink.payloads))
        emit(AI_REQUESTS_TOTAL, 1.0, {"operation": "chat", "model": "devops-background"})
        if len(exported_at_start) == 1:
            raise RuntimeError("the round failed after one model call")

    worker = RepoWorker(
        repo="example-org/repo1", lane=LANE, job_func=job, clock=lambda: datetime.now(UTC)
    )
    worker.start()
    for _ in range(2):
        worker.enqueue("webhook", "issues", "opened")
        assert worker.wait_active(THREAD_HANDOFF_BOUND_SECONDS)
    worker.stop()

    assert (
        worker.join(THREAD_HANDOFF_BOUND_SECONDS),
        exported_at_start,
        len(sink.payloads),
        [value for _, value in sink.points(AI_REQUESTS_TOTAL.name)],
    ) == (True, [0, 1], 2, [1.0, 1.0])


# ── A GraphQL budget refusal holds every repository's rounds (#1400) ──────────

REPO_A, REPO_B = "example-org/repo1", "example-org/repo2"
RESET = datetime(2026, 10, 8, 13, tzinfo=UTC)
RESUME = RESET + timedelta(seconds=CONST_GH_RATE_LIMIT_CLOCK_SKEW_BOUND_SECONDS)
"""The reset plus the bound on how late GitHub still reports the window that ended (#1364): when
rounds start again."""
WAIT_LINE = (
    "No repository starts a Service round before 2026-10-08T13:00:05+00:00, the time the failed "
    "round for {repo} named; the triggers that arrive until then run as one round per lane of "
    "each repository."
)


class _Clock:
    """The Service's clock, set by the test."""

    def __init__(self, now: datetime) -> None:
        self.now = now

    def __call__(self) -> datetime:
        return self.now


def _low_budget(reset: datetime = RESET) -> GraphQLBudget:
    return GraphQLBudget(cost=1, limit=5000, remaining=40, used=4960, reset_at=reset)


def _refuse_read(reset: datetime = RESET) -> None:
    """What a refused board read raises, as `changes_since` does outside any job."""
    require_budget(_low_budget(reset), 12, "board #1 items")


def _refuse_jobs_write(store: InMemoryRoadmapStore, data_dir: Path) -> None:
    """A round whose intake job's card write is refused: `run_due_jobs` raises the
    `RoadmapRunError` that carries the reset."""

    def write(**_: Any) -> JobOutcome:
        require_write_floor(_low_budget(), "#7")
        return JobOutcome()

    run_due_jobs(
        REPO_A,
        store,
        batch={CONST_ROADMAP_INTAKE_BATCH_KEYS[0]: 1},
        table=build_stub_table({"intake": write}),
        data_dir=data_dir,
        now=RESET - timedelta(minutes=20),
    )


class _Rounds:
    """The jobs each repository's worker ran, the first `refusing` rounds raising `refusal`."""

    def __init__(self, refusal: Callable[[], None], refusing: dict[str, int]) -> None:
        self.refusal = refusal
        self.refusing = dict(refusing)
        self.batches: dict[str, list[TriggerBatch]] = {REPO_A: [], REPO_B: []}
        self.done: queue.Queue[str] = queue.Queue()

    def __call__(self, batch: TriggerBatch) -> None:
        self.batches[batch.repo].append(batch)
        try:
            if self.refusing.get(batch.repo, 0) >= len(self.batches[batch.repo]):
                self.refusal()
        finally:
            self.done.put(batch.repo)

    def wait(self, count: int, manager: ServiceManager) -> list[str]:
        """The repositories of the next `count` rounds to finish, once every worker is idle, so
        a failed round's pause is in place."""
        finished = sorted(self.done.get(timeout=THREAD_HANDOFF_BOUND_SECONDS) for _ in range(count))
        assert all(
            worker.wait_active(THREAD_HANDOFF_BOUND_SECONDS) for worker in manager.workers.values()
        )
        return finished

    def held(self, manager: ServiceManager) -> bool:
        """Whether no round started for the triggers just enqueued: a worker whose batch may run
        is waited for until it has run, so an idle worker and no finished round mean the pause
        held every batch."""
        assert all(
            worker.wait_active(THREAD_HANDOFF_BOUND_SECONDS) for worker in manager.workers.values()
        )
        return self.done.empty()

    def triggers(self) -> dict[str, list[int]]:
        return {repo: [sum(b.counts.values()) for b in done] for repo, done in self.batches.items()}


def _service(
    jobs: Mapping[str, Callable[[TriggerBatch], None]],
    clock: _Clock,
    reader: PauseReader = service_pause_until,
    *,
    drain_timeout: int = 120,
) -> ServiceManager:
    """The Service over both repositories, one worker per lane each, the workers started, with no
    poll loop."""
    manager = ServiceManager(
        config=_make_settings(repos=[REPO_A, REPO_B], drain_timeout=drain_timeout).service,
        secrets={},
        jobs=jobs,
        clock=clock,
        sleep_func=asyncio.sleep,
        pause_until=reader,
    )
    for worker in manager.workers.values():
        worker.start()
    return manager


def _trigger(manager: ServiceManager, *repos: str) -> None:
    for repo in repos:
        manager.enqueue_trigger(repo, "webhook", "issues", "labeled")


def _wait_lines(caplog: pytest.LogCaptureFixture) -> list[str]:
    return [
        r.getMessage()
        for r in caplog.records
        if r.name == "devops_cli.server.service" and r.getMessage().startswith("No repository")
    ]


@pytest.mark.parametrize("source", ["changes_since", "job"])
def test_a_budget_refusal_holds_every_repositorys_rounds_until_the_reset(
    source: str,
    tmp_path: Path,
    roadmap_store: InMemoryRoadmapStore,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Repository A's round is refused, by a board read outside any job or by a job's write.
    Until 5 s after the reset no round starts, B's included, though triggers arrive for both
    10 minutes before the reset and 4 s after it, past the 0.72-2.07 s GitHub took to report the
    new window (#1364). Then each runs one round holding all of them. The wait is logged once."""
    refusal = {
        "changes_since": _refuse_read,
        "job": lambda: _refuse_jobs_write(roadmap_store, tmp_path),
    }[source]
    rounds, clock = _Rounds(refusal, {REPO_A: 1}), _Clock(RESET - timedelta(minutes=20))
    with caplog.at_level(logging.INFO, logger="devops_cli.server.service"):
        manager = _service({LANE: rounds}, clock)
        _trigger(manager, REPO_A)
        refused = rounds.wait(1, manager)
        held: list[bool] = []
        for now in (RESET - timedelta(minutes=10), RESET + timedelta(seconds=4)):
            clock.now = now
            _trigger(manager, REPO_A, REPO_B)
            held.append(rounds.held(manager))
        clock.now = RESUME
        resumed = rounds.wait(2, manager)
        asyncio.run(manager.drain_and_stop())
    assert (refused, held, resumed, rounds.triggers(), _wait_lines(caplog)) == (
        [REPO_A],
        [True, True],
        [REPO_A, REPO_B],
        {REPO_A: [1, 2], REPO_B: [2]},
        [WAIT_LINE.format(repo=REPO_A)],
    )


def test_every_worker_refused_for_one_reset_logs_one_wait_line(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Both repositories' rounds are refused for the same reset: one line. A's next round,
    refused for the next hour's reset, logs its own."""
    resets = iter([RESET, RESET, RESET + timedelta(hours=1)])
    # A refusal holds every round that has not started yet, so the first two refusals wait until
    # both repositories' rounds have started; otherwise the first could hold the other's round.
    both_started = threading.Barrier(2, timeout=THREAD_HANDOFF_BOUND_SECONDS)

    def refuse() -> None:
        reset = next(resets)
        if reset == RESET:
            both_started.wait()
        _refuse_read(reset)

    rounds = _Rounds(refuse, {REPO_A: 2, REPO_B: 1})
    clock = _Clock(RESET - timedelta(minutes=20))
    with caplog.at_level(logging.INFO, logger="devops_cli.server.service"):
        manager = _service({LANE: rounds}, clock)
        _trigger(manager, REPO_A, REPO_B)
        first = rounds.wait(2, manager)
        clock.now = RESUME
        _trigger(manager, REPO_A)
        second = rounds.wait(1, manager)
        asyncio.run(manager.drain_and_stop())
    assert (
        both_started.broken,
        first,
        second,
        [line.split(",")[0] for line in _wait_lines(caplog)],
    ) == (
        False,
        [REPO_A, REPO_B],
        [REPO_A],
        [
            "No repository starts a Service round before 2026-10-08T13:00:05+00:00",
            "No repository starts a Service round before 2026-10-08T14:00:05+00:00",
        ],
    )


@pytest.mark.parametrize(
    "error",
    [
        GitHubRateLimitError(
            "Rate limit state for subcommand 'core' is in an unknown or broken state",
            details={"reset_epoch": str(RESET.timestamp())},
        ),
        GitHubRateLimitError(
            "GitHub reported the core reset well before the local clock",
            details={
                "reported_reset": "2026-10-08T13:00:00Z",
                "local_clock": "2026-10-08T13:01:00Z",
                "gap_seconds": "60.00",
            },
        ),
        GitHubRateLimitError(
            "GitHub's rate limit answer has no core resource",
            details={"reported_resources": "graphql, search"},
        ),
        RoadmapRunError("Roadmap jobs failed: intake", failed_jobs=("intake",)),
        RuntimeError("model down"),
    ],
    ids=["rate-limiter-state", "clocks-disagree", "resource-unreported", "job-failure", "other"],
)
def test_an_error_that_names_no_reset_holds_no_round(
    error: Exception, caplog: pytest.LogCaptureFixture
) -> None:
    """The rate limiter's own errors carry `reset_epoch`, or #1364's `reported_reset`,
    `local_clock`, `gap_seconds` and `reported_resources`, never a refusal's reset, and a job that
    failed for another reason carries none: B's round runs at once, and nothing is logged."""

    def fail() -> None:
        raise error

    rounds, clock = _Rounds(fail, {REPO_A: 1}), _Clock(RESET - timedelta(minutes=20))
    with caplog.at_level(logging.INFO, logger="devops_cli.server.service"):
        manager = _service({LANE: rounds}, clock)
        _trigger(manager, REPO_A)
        refused = rounds.wait(1, manager)
        _trigger(manager, REPO_B)
        ran = rounds.wait(1, manager)
        asyncio.run(manager.drain_and_stop())
    assert (refused, ran, _wait_lines(caplog)) == ([REPO_A], [REPO_B], [])


def test_a_refusal_whose_reset_has_passed_holds_no_round(caplog: pytest.LogCaptureFixture) -> None:
    """A refusal read while GitHub still reports the window that just ended names a reset more
    than the bound behind the clock: nothing is held, and B's round runs at once."""
    rounds = _Rounds(_refuse_read, {REPO_A: 1})
    clock = _Clock(RESUME + timedelta(seconds=1))
    with caplog.at_level(logging.INFO, logger="devops_cli.server.service"):
        manager = _service({LANE: rounds}, clock)
        _trigger(manager, REPO_A)
        refused = rounds.wait(1, manager)
        _trigger(manager, REPO_B)
        ran = rounds.wait(1, manager)
        asyncio.run(manager.drain_and_stop())
    assert (refused, ran, _wait_lines(caplog)) == ([REPO_A], [REPO_B], [])


def test_a_drain_during_a_pause_stops_the_workers_without_running_the_held_rounds() -> None:
    """A rollout during a pause doesn't wait out the drain timeout for rounds the pause
    holds: the drain completes cleanly, the workers stop, and the held rounds never run;
    the next pod's start-up poll reads the changes they were for."""
    rounds, clock = _Rounds(_refuse_read, {REPO_A: 1}), _Clock(RESET - timedelta(minutes=20))
    manager = _service({LANE: rounds}, clock, drain_timeout=1)
    _trigger(manager, REPO_A)
    rounds.wait(1, manager)
    _trigger(manager, REPO_A, REPO_B)
    drained = asyncio.run(manager.drain_and_stop())
    assert (
        drained,
        [w.is_alive() for w in manager.workers.values()],
        rounds.triggers(),
    ) == (True, [False, False], {REPO_A: [1], REPO_B: []})


def test_a_pause_reader_that_fails_holds_nothing_and_the_worker_carries_on(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The time a failed round names can't be read: a warning names the class, nothing is held,
    and the worker that ran the round lives on to run its next one, as B's runs at once."""

    def unreadable(_exc: Exception) -> datetime | None:
        raise ValueError("no reset in this error")

    rounds = _Rounds(_refuse_read, {REPO_A: 1})
    clock = _Clock(RESET - timedelta(minutes=20))
    with caplog.at_level(logging.INFO, logger="devops_cli.server.service"):
        manager = _service({LANE: rounds}, clock, unreadable)
        _trigger(manager, REPO_A)
        refused = rounds.wait(1, manager)
        _trigger(manager, REPO_A, REPO_B)
        ran = rounds.wait(2, manager)
        alive = [worker.is_alive() for worker in manager.workers.values()]
        asyncio.run(manager.drain_and_stop())
    warnings = [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]
    assert (refused, ran, alive, warnings, _wait_lines(caplog)) == (
        [REPO_A],
        [REPO_A, REPO_B],
        [True, True],
        [
            f"Could not read the time the failed Service round for {REPO_A} names, so no round "
            "waits for it: ValueError: no reset in this error"
        ],
        [],
    )


# ── A status-lane round never waits for a model-lane round (#1532) ────────────

STATUS_LANE, MODEL_LANE = CONST_SERVICE_LANE_STATUS, CONST_SERVICE_LANE_MODEL


class _Lanes:
    """One repository's two lane jobs: the model lane's first round blocks, as on a slow model,
    until the test lets it go; every round is recorded by lane."""

    def __init__(self) -> None:
        self.model_started = threading.Event()
        self.model_answers = threading.Event()
        self.model_released: bool | None = None
        self.batches: dict[str, list[TriggerBatch]] = {STATUS_LANE: [], MODEL_LANE: []}
        self.most_at_once = dict.fromkeys(self.batches, 0)
        self._running = dict.fromkeys(self.batches, 0)
        self._lock = threading.Lock()

    def jobs(self) -> dict[str, Callable[[TriggerBatch], None]]:
        return {lane: partial(self._round, lane) for lane in self.batches}

    def _round(self, lane: str, batch: TriggerBatch) -> None:
        with self._lock:
            self.batches[lane].append(batch)
            self._running[lane] += 1
            self.most_at_once[lane] = max(self.most_at_once[lane], self._running[lane])
        try:
            if lane == MODEL_LANE and len(self.batches[lane]) == 1:
                self.model_started.set()
                self.model_released = self.model_answers.wait(timeout=THREAD_HANDOFF_BOUND_SECONDS)
        finally:
            with self._lock:
                self._running[lane] -= 1


def _lanes_app(lanes: _Lanes) -> FastAPI:
    """The Service over one repository with the two lanes' jobs."""
    return create_service_app(
        jobs=lanes.jobs(), settings=_make_settings(repos=[REPO_A]), secrets={REPO_A: "secret-1"}
    )


def _post(client: TestClient, event: str, action: str, delivery: str) -> int:
    """Deliver a signed webhook for repository A; the response's status."""
    payload = json.dumps(
        {"repository": {"full_name": REPO_A}, "action": action, "sender": {"login": "alice"}}
    ).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        CONST_GH_WEBHOOK_EVENT_HEADER: event,
        CONST_GH_WEBHOOK_DELIVERY_HEADER: delivery,
        CONST_GH_WEBHOOK_SIGNATURE_HEADER: _sign(payload, "secret-1"),
    }
    return client.post("/webhooks/github", content=payload, headers=headers).status_code


def test_a_webhook_runs_the_status_lane_while_the_model_lanes_round_is_blocked() -> None:
    """The model lane's start-up round blocks on a slow model. A reopened issue's webhook still
    runs a status-lane round at once, and the triggers that arrive meanwhile wait as one
    model-lane batch, which runs once the model answers. Each lane runs one round at a time, and
    each trigger counts once for the repository, whatever the lanes."""
    lanes = _Lanes()
    app = _lanes_app(lanes)
    deliveries = [("issues", "reopened"), ("issues", "opened"), ("issues", "opened")]
    with TestClient(app) as client:
        workers = app.state.service_manager.workers
        status, model = workers[(REPO_A, STATUS_LANE)], workers[(REPO_A, MODEL_LANE)]
        assert lanes.model_started.wait(timeout=THREAD_HANDOFF_BOUND_SECONDS)
        statuses = [
            _post(client, event, action, f"lane-{n}")
            for n, (event, action) in enumerate(deliveries)
        ]
        status_done, model_blocked = (
            status.wait_active(THREAD_HANDOFF_BOUND_SECONDS),
            model.is_active(),
        )
        lanes.model_answers.set()
        model_done = model.wait_active(THREAD_HANDOFF_BOUND_SECONDS)
    reopened = ("webhook", "issues", "reopened")
    triggers = {
        source: GLOBAL_METRICS.get_counter_value(
            CONST_SERVICE_METRIC_TRIGGERS, labels={"repo": REPO_A, "source": source}
        )
        for source in ("poll", "webhook")
    }
    assert (
        statuses,
        status_done,
        model_blocked,
        lanes.model_released,
        model_done,
        any(reopened in batch.counts for batch in lanes.batches[STATUS_LANE]),
        sum(sum(batch.counts.values()) for batch in lanes.batches[STATUS_LANE]),
        [batch.counts for batch in lanes.batches[MODEL_LANE]],
        lanes.most_at_once,
        triggers,
    ) == (
        [202, 202, 202],
        True,
        True,
        True,
        True,
        True,
        4,
        [
            {("poll", "", ""): 1},
            {reopened: 1, ("webhook", "issues", "opened"): 2},
        ],
        {STATUS_LANE: 1, MODEL_LANE: 1},
        {"poll": 1.0, "webhook": 3.0},
    )


def test_metrics_show_a_stalled_model_lane_by_its_queue_depth() -> None:
    """While the model lane's round is blocked with a trigger waiting behind it, /metrics shows
    the model lane's queue depth at 1 and the status lane's at 0, and each lane's rounds under
    its own label."""
    lanes = _Lanes()
    app = _lanes_app(lanes)
    with TestClient(app) as client:
        status = app.state.service_manager.workers[(REPO_A, STATUS_LANE)]
        assert lanes.model_started.wait(timeout=THREAD_HANDOFF_BOUND_SECONDS)
        _post(client, "issues", "reopened", "stalled-1")
        assert status.wait_active(THREAD_HANDOFF_BOUND_SECONDS)
        exported = client.get("/metrics").text.splitlines()
        lanes.model_answers.set()
    repo = f'repo="{REPO_A}"'

    def exported_as(metric: str, labels: str) -> bool:
        return any(line.startswith(f"{metric}{{{labels}}} ") for line in exported)

    assert (
        f'{CONST_SERVICE_METRIC_QUEUE_DEPTH}{{lane="model",{repo}}} 1.0' in exported,
        f'{CONST_SERVICE_METRIC_QUEUE_DEPTH}{{lane="status",{repo}}} 0.0' in exported,
        exported_as(CONST_SERVICE_METRIC_JOBS, f'lane="status",{repo},result="success"'),
        exported_as(CONST_SERVICE_METRIC_JOB_SECONDS, f'lane="status",{repo}'),
        exported_as(CONST_SERVICE_METRIC_JOB_START_TIMESTAMP, f'lane="model",{repo}'),
        exported_as(CONST_SERVICE_METRIC_JOBS, f'lane="model",{repo},result="success"'),
        lanes.model_released,
    ) == (True, True, True, True, True, False, True)


def test_a_budget_refusal_in_the_model_lane_holds_the_status_lane_too() -> None:
    """Both lanes spend the machine account's one GraphQL budget: the model lane's refused round
    holds the status lane's next round through the shared pause until 5 s after the reset, and
    then each lane runs one round with the trigger that waited (#1400)."""
    status = _Rounds(lambda: None, {})
    status_started_first: list[bool] = []

    def refuse_once_the_status_lane_started() -> None:
        # A refusal holds every round that has not started yet, so it waits until the status
        # lane's first round has started; otherwise it could hold that round too.
        status_started_first.append(wait_until(lambda: bool(status.batches[REPO_A])))
        _refuse_read()

    model = _Rounds(refuse_once_the_status_lane_started, {REPO_A: 1})
    clock = _Clock(RESET - timedelta(minutes=20))
    manager = _service({STATUS_LANE: status, MODEL_LANE: model}, clock)
    _trigger(manager, REPO_A)
    first = (status.wait(1, manager), model.wait(1, manager))
    clock.now = RESET - timedelta(minutes=10)
    _trigger(manager, REPO_A)
    held = (status.held(manager), model.held(manager))
    clock.now = RESUME
    resumed = (status.wait(1, manager), model.wait(1, manager))
    asyncio.run(manager.drain_and_stop())
    assert (
        status_started_first,
        first,
        held,
        resumed,
        status.triggers(),
        model.triggers(),
    ) == (
        [True],
        ([REPO_A], [REPO_A]),
        (True, True),
        ([REPO_A], [REPO_A]),
        {REPO_A: [1, 1], REPO_B: []},
        {REPO_A: [1, 1], REPO_B: []},
    )


def test_service_app_quiets_httpx_loggers() -> None:
    """`create_service_app` and `service_log_config` keep `httpx`, `httpx2`, and `httpcore` at
    `WARNING` so every GitHub and Gateway request is not logged at `INFO` (#792)."""
    from devops_cli.server.json_logs import service_log_config

    for name in ("httpx", "httpx2", "httpcore"):
        logging.getLogger(name).setLevel(logging.INFO)
    create_service_app(settings=_make_settings(repos=[REPO_A]), secrets={REPO_A: "secret-1"})
    log_cfg = service_log_config("INFO")["loggers"]
    assert (
        logging.getLogger("httpx").getEffectiveLevel() >= logging.WARNING,
        logging.getLogger("httpx2").getEffectiveLevel() >= logging.WARNING,
        logging.getLogger("httpcore").getEffectiveLevel() >= logging.WARNING,
        log_cfg["httpx"]["level"],
        log_cfg["httpx2"]["level"],
        log_cfg["httpcore"]["level"],
    ) == (True, True, True, logging.WARNING, logging.WARNING, logging.WARNING)


# ── One router verifies each provider its own way and delivers to its consumers (#1386) ──────

ROUTER_LOGGER = "devops_cli.server.routes.webhooks"


def _event_payload(
    action: str | None = "opened", *, sender: str = "alice", **extra: Any
) -> dict[str, Any]:
    """What GitHub sends for repository A, with the fields the Service reads and the rest it
    ignores."""
    return {
        "repository": {"full_name": REPO_A, "default_branch": "main"},
        "action": action,
        "sender": {"login": sender},
        **extra,
    }


def _github_post(
    client: TestClient,
    event: str,
    payload: dict[str, Any],
    delivery: str,
    *,
    route: str = "github",
    secret: str = "secret-1",
    headers: Mapping[str, str | bytes] | None = None,
) -> Any:
    """Deliver `payload` as `event`, signed with `secret`; the response."""
    body = json.dumps(payload).encode("utf-8")
    sent = {
        "Content-Type": "application/json",
        CONST_GH_WEBHOOK_EVENT_HEADER: event,
        CONST_GH_WEBHOOK_DELIVERY_HEADER: delivery,
        CONST_GH_WEBHOOK_SIGNATURE_HEADER: _sign(body, secret),
        **(headers or {}),
    }
    return client.post(f"/webhooks/{route}", content=body, headers=sent)


def _lanes_settled(app: FastAPI) -> bool:
    """Whether every worker has run what was enqueued for it."""
    return all(
        worker.wait_active(THREAD_HANDOFF_BOUND_SECONDS)
        for worker in app.state.service_manager.workers.values()
    )


def _webhook_keys(lanes: _Lanes) -> dict[str, list[tuple[str, str, str]]]:
    """The webhook trigger keys each lane's rounds ran, the start-up poll left out."""
    return {
        lane: [key for batch in batches for key in batch.counts if key[0] == "webhook"]
        for lane, batches in lanes.batches.items()
    }


def _unblocked_lanes() -> _Lanes:
    """Lane jobs that record their rounds, the model lane's start-up round answering at once."""
    lanes = _Lanes()
    lanes.model_answers.set()
    return lanes


def _delivery_series(client: TestClient) -> dict[tuple[str, str, str], float]:
    """The deliveries counter as /metrics exports it: {(provider, event, outcome): count}."""
    return {
        (sample.labels["provider"], sample.labels["event"], sample.labels["outcome"]): sample.value
        for family in text_string_to_metric_families(client.get("/metrics").text)
        for sample in family.samples
        if sample.name == CONST_SERVICE_METRIC_WEBHOOK_DELIVERIES
    }


@pytest.mark.parametrize(
    ("event", "payload"),
    [
        ("issue_comment", _event_payload("created")),
        ("create", _event_payload(None, ref="v1", ref_type="tag")),
        ("push", _event_payload(None, ref="refs/heads/main", deleted=False)),
        ("workflow_run", _event_payload("completed")),
        ("pull_request", _event_payload("closed")),
        ("milestone", _event_payload("closed")),
        ("release", _event_payload("published")),
    ],
)
def test_an_event_no_consumer_subscribes_to_gets_no_subscriber_and_starts_no_round(
    event: str, payload: dict[str, Any]
) -> None:
    """Comments, branch and tag creations, pushes (a default-branch push included), pull
    requests, milestones, GitHub Releases and every other event the roadmap's jobs read nothing
    from are acknowledged and run nothing. A repeat
    of such a delivery is acknowledged again, since the delivery cache holds only deliveries a
    consumer took."""
    lanes = _unblocked_lanes()
    app = _lanes_app(lanes)
    with TestClient(app) as client:
        responses = [_github_post(client, event, payload, "unsubscribed-1") for _ in range(2)]
        settled = _lanes_settled(app)
    assert ([(r.status_code, r.json()) for r in responses], settled, _webhook_keys(lanes)) == (
        [(200, {"status": "no_subscriber"})] * 2,
        True,
        {STATUS_LANE: [], MODEL_LANE: []},
    )


@pytest.mark.parametrize("event", ["issues"])
def test_the_roadmap_consumer_takes_the_events_its_jobs_read_into_both_lanes(event: str) -> None:
    """Each event a roadmap job's batch keys name, the issues events alone, reaches the status
    lane and the model lane as a ("webhook", <event>, <action>) trigger, whatever its action."""
    lanes = _unblocked_lanes()
    app = _lanes_app(lanes)
    with TestClient(app) as client:
        response = _github_post(client, event, _event_payload("labeled"), "roadmap-1")
        settled = _lanes_settled(app)
    key = ("webhook", event, "labeled")
    assert (response.status_code, response.json(), settled, _webhook_keys(lanes)) == (
        202,
        {"status": "accepted"},
        True,
        {STATUS_LANE: [key], MODEL_LANE: [key]},
    )


def test_the_machine_accounts_own_event_reaches_neither_lane() -> None:
    """The roadmap's own writes come back as webhooks from the machine account. The roadmap
    consumer refuses them, and answers with the reason."""
    lanes = _unblocked_lanes()
    app = _lanes_app(lanes)
    with TestClient(app) as client:
        response = _github_post(
            client, "issues", _event_payload("opened", sender="BOT-ACCOUNT"), "own-write-1"
        )
        settled = _lanes_settled(app)
    assert (response.status_code, response.json(), settled, _webhook_keys(lanes)) == (
        200,
        {"status": "ignored_machine_account"},
        True,
        {STATUS_LANE: [], MODEL_LANE: []},
    )


def test_a_consumer_receives_only_the_events_it_subscribes_to() -> None:
    """A consumer a test declares, with a recording delivery target, takes the events it names
    from its provider. The roadmap consumer is not among the consumers given, so an event it
    would take has no subscriber."""
    received: list[tuple[str, str, str]] = []
    recorder = _recording_consumer(frozenset({"issue_comment"}), received)
    app = create_service_app(
        settings=_make_settings(repos=[REPO_A]), secrets={REPO_A: "secret-1"}, consumers=[recorder]
    )
    with TestClient(app) as client:
        answers = [
            _github_post(client, event, _event_payload(action), f"recorder-{n}").json()
            for n, (event, action) in enumerate(
                [("issue_comment", "created"), ("issues", "opened"), ("push", "")]
            )
        ]
    assert (answers, received) == (
        [{"status": "accepted"}, {"status": "no_subscriber"}, {"status": "no_subscriber"}],
        [(REPO_A, "issue_comment", "created")],
    )


@pytest.mark.parametrize(
    ("payload", "field"),
    [
        ({"action": "opened"}, "repository"),
        ({"action": "opened", "repository": {}}, "repository.full_name"),
        (
            {"action": 7, "repository": {"full_name": REPO_A}, "sender": {}},
            "action: Input should be a valid string; sender.login",
        ),
    ],
)
def test_a_payload_missing_a_field_the_service_reads_gets_400_naming_the_field(
    payload: dict[str, Any], field: str
) -> None:
    """A body that is signed but does not validate gets 400 naming the failing fields' paths,
    within the bound on error details. An unsigned one gets 401 before validation, so the
    schema can't be probed without a secret."""
    app = create_service_app(settings=_make_settings(repos=[REPO_A]), secrets={REPO_A: "secret-1"})
    with TestClient(app) as client:
        invalid = _github_post(client, "issues", payload, "invalid-1")
        unsigned = _github_post(client, "issues", payload, "invalid-2", secret="wrong")
    detail = invalid.json()["error"]
    assert (
        invalid.status_code,
        field in detail,
        len(detail) <= CONST_MAX_ERROR_DETAIL_LENGTH,
        unsigned.status_code,
        unsigned.json(),
    ) == (400, True, True, 401, {"error": "invalid signature"})


def test_whole_error_text_for_a_payload_without_a_repository_name() -> None:
    """The 400 names the field and why, and nothing from the body."""
    app = create_service_app(settings=_make_settings(repos=[REPO_A]), secrets={REPO_A: "secret-1"})
    with TestClient(app) as client:
        response = _github_post(client, "issues", {"repository": {}, "zen": "x" * 500}, "bare-1")
    assert (response.status_code, response.json()) == (
        400,
        {"error": "invalid payload: repository.full_name: Field required"},
    )


def test_a_signature_header_with_non_ascii_text_is_refused_with_401() -> None:
    """A digest is hex, so a header that carries other text can't match, and the check says so
    rather than failing the request (the header's bytes, which HTTP does not limit to ASCII)."""
    app = create_service_app(settings=_make_settings(repos=[REPO_A]), secrets={REPO_A: "secret-1"})
    with TestClient(app) as client:
        response = _github_post(
            client,
            "issues",
            _event_payload(),
            "non-ascii-1",
            headers={CONST_GH_WEBHOOK_SIGNATURE_HEADER: "sha256=é".encode()},
        )
    assert (response.status_code, response.json()) == (401, {"error": "invalid signature"})


def test_one_delivery_writes_one_record_with_its_six_keys_and_no_secret(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A delivery's record carries the provider, event, action, delivery, repository and outcome.
    It never carries the body, the signature or an Authorization header's value."""
    app = create_service_app(settings=_make_settings(repos=[REPO_A]), secrets={REPO_A: "secret-1"})
    payload = _event_payload("opened", issue={"body": "body-marker-5678"})
    signature = _sign(json.dumps(payload).encode("utf-8"), "secret-1")
    with caplog.at_level(logging.INFO, logger=ROUTER_LOGGER), TestClient(app) as client:
        _github_post(
            client,
            "issues",
            payload,
            "record-1",
            headers={"Authorization": "Bearer token-marker-1234"},
        )
    records = [record for record in caplog.records if record.name == ROUTER_LOGGER]
    line = JsonLogFormatter().format(records[0])
    written = {key: value for key, value in json.loads(line).items() if key != "time"}
    assert (len(records), written) == (
        1,
        {
            "level": "INFO",
            "logger": ROUTER_LOGGER,
            "message": "Webhook delivery handled.",
            "provider": "github",
            "event": "issues",
            "action": "opened",
            "delivery": "record-1",
            "repo": REPO_A,
            "outcome": "accepted",
        },
    )
    leaked = [text for text in (signature, "token-marker-1234", "body-marker-5678") if text in line]
    assert leaked == []


def test_header_values_in_the_record_and_the_counter_are_bounded(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The event and delivery headers are text any sender can choose. The record keeps their
    first 256 characters, and the counter files an event no consumer subscribes to under
    "other", so a flood of event names grows no series."""
    app = create_service_app(settings=_make_settings(repos=[REPO_A]), secrets={REPO_A: "secret-1"})
    with caplog.at_level(logging.INFO, logger=ROUTER_LOGGER), TestClient(app) as client:
        response = _github_post(client, "e" * 1000, _event_payload(), "d" * 1000)
        series = _delivery_series(client)
    record = next(record for record in caplog.records if record.name == ROUTER_LOGGER)
    assert (response.json(), record.event, record.delivery, series) == (
        {"status": "no_subscriber"},
        "e" * 256,
        "d" * 256,
        {("github", "other", "no_subscriber"): 1.0},
    )


def test_every_path_counts_its_delivery_by_provider_event_and_outcome() -> None:
    """Accepted, repeated, pong, machine-account, no-subscriber, refused and draining deliveries
    all count under the provider, the event (an undeclared one as "other") and the outcome."""
    app = create_service_app(settings=_make_settings(repos=[REPO_A]), secrets={REPO_A: "secret-1"})
    with TestClient(app) as client:
        statuses = [
            _github_post(client, "issues", _event_payload(), "count-1").status_code,
            _github_post(client, "issues", _event_payload(), "count-1").status_code,
            _github_post(
                client, "issues", _event_payload(sender="bot-account"), "count-2"
            ).status_code,
            _github_post(client, "ping", _event_payload(None), "count-3").status_code,
            _github_post(client, "issue_comment", _event_payload(), "count-4").status_code,
            _github_post(client, "made-up-1", _event_payload(), "count-5").status_code,
            _github_post(client, "made-up-2", _event_payload(), "count-6").status_code,
            _github_post(client, "issues", _event_payload(), "count-7", secret="wrong").status_code,
            _github_post(
                client,
                "issues",
                _event_payload(),
                "count-8",
                headers={"Content-Type": "text/plain"},
            ).status_code,
            client.post(
                "/webhooks/github",
                content=b"{}",
                headers={
                    "Content-Type": "application/json",
                    CONST_GH_WEBHOOK_EVENT_HEADER: "issues",
                },
            ).status_code,
            _github_post(client, "issues", {"action": "opened"}, "count-9").status_code,
        ]
    statuses.append(_github_post(client, "issues", _event_payload(), "count-10").status_code)
    assert (statuses, _delivery_series(client)) == (
        [202, 200, 200, 200, 200, 200, 200, 401, 415, 400, 400, 503],
        {
            ("github", "issues", "accepted"): 1.0,
            ("github", "issues", "ignored"): 2.0,
            ("github", "ping", "ignored"): 1.0,
            ("github", "other", "no_subscriber"): 3.0,
            ("github", "issues", "rejected"): 5.0,
        },
    )


@pytest.mark.parametrize("digits", [5000, 4301, 4300, 20])
def test_a_content_length_over_the_cap_gets_413_whatever_its_number_of_digits(
    digits: int, caplog: pytest.LogCaptureFixture
) -> None:
    """A declared length above the cap is refused before the body is read, however many digits it
    has: it writes its one record and counts once. Python converts no more than 4300 digits to an
    integer, so the digits are counted first."""
    app = create_service_app(settings=_make_settings(repos=[REPO_A]), secrets={REPO_A: "secret-1"})
    with caplog.at_level(logging.INFO, logger=ROUTER_LOGGER), TestClient(app) as client:
        response = _github_post(
            client, "issues", _event_payload(), "length-1", headers={"Content-Length": "9" * digits}
        )
        series = _delivery_series(client)
    outcomes = [record.outcome for record in caplog.records if record.name == ROUTER_LOGGER]
    assert (response.status_code, response.json(), outcomes, series) == (
        413,
        {"error": "payload too large"},
        ["rejected"],
        {("github", "issues", "rejected"): 1.0},
    )


def test_a_content_length_padded_with_zeros_is_judged_by_its_value() -> None:
    """Leading zeros are part of a valid Content-Length, so a small number written with thousands
    of them is no larger than the cap."""
    app = create_service_app(settings=_make_settings(repos=[REPO_A]), secrets={REPO_A: "secret-1"})
    with TestClient(app) as client:
        response = _github_post(
            client,
            "issues",
            _event_payload(),
            "length-2",
            headers={"Content-Length": "0" * 5000 + "2"},
        )
    assert (response.status_code, response.json()) == (202, {"status": "accepted"})


def test_the_detail_of_an_invalid_payload_is_cut_to_the_bound_on_error_details() -> None:
    """A payload model's failed fields can add up to more than the bound on error details, as a
    model with long field names does, and the text that names them is cut to it."""
    wide_model = create_model("WidePayload", **{"f" * 300: (str, ...)})
    with pytest.raises(ValidationError) as failure:
        wide_model.model_validate_json("{}")
    prefix = "invalid payload: "
    assert invalid_payload_detail(failure.value) == prefix + "f" * (
        CONST_MAX_ERROR_DETAIL_LENGTH - len(prefix)
    )


def _recording_consumer(
    events: frozenset[str], received: list[tuple[str, str, str]]
) -> WebhookConsumer:
    """A consumer of GitHub's `events` that takes every payload and records what it receives."""
    return WebhookConsumer(
        name="recorder",
        provider=WebhookProviderName.GITHUB,
        events=events,
        deliver=lambda repo, event, action: received.append((repo, event, action)),
    )


def _refusing_consumer(name: str, refusal: str, delivered: list[str]) -> WebhookConsumer:
    """A consumer of `issues` that refuses every payload with the status `refusal`."""
    return WebhookConsumer(
        name=name,
        provider=WebhookProviderName.GITHUB,
        events=frozenset({"issues"}),
        deliver=lambda repo, event, action: delivered.append(name),
        refusal=lambda payload: refusal,
    )


def test_the_machine_accounts_event_is_refused_by_the_roadmap_consumer_alone() -> None:
    """The roadmap consumer refuses the machine account's own writes, and the refusal is its own:
    a consumer subscribed beside it still receives the event, while neither lane runs a round for
    it. Another sender's event reaches the recorder and both lanes."""
    lanes = _unblocked_lanes()
    received: list[tuple[str, str, str]] = []
    manager = ServiceManager(
        config=_make_settings(repos=[REPO_A]).service,
        secrets={REPO_A: "secret-1"},
        jobs=lanes.jobs(),
        clock=lambda: datetime.now(UTC),
        sleep_func=asyncio.sleep,
    )
    app = FastAPI()
    app.include_router(
        create_webhook_router(
            manager,
            [_recording_consumer(frozenset({"issues"}), received), roadmap_consumer(manager)],
        )
    )
    for worker in manager.workers.values():
        worker.start()
    try:
        with TestClient(app) as client:
            answers = [
                _github_post(client, "issues", _event_payload("opened"), "shared-1"),
                _github_post(
                    client, "issues", _event_payload("closed", sender="BOT-ACCOUNT"), "shared-2"
                ),
            ]
        settled = all(
            worker.wait_active(THREAD_HANDOFF_BOUND_SECONDS) for worker in manager.workers.values()
        )
    finally:
        asyncio.run(manager.drain_and_stop())
    key = ("webhook", "issues", "opened")
    assert (
        [(answer.status_code, answer.json()) for answer in answers],
        received,
        settled,
        _webhook_keys(lanes),
    ) == (
        [(202, {"status": "accepted"})] * 2,
        [(REPO_A, "issues", "opened"), (REPO_A, "issues", "closed")],
        True,
        {STATUS_LANE: [key], MODEL_LANE: [key]},
    )


@pytest.mark.parametrize("order", [("first", "second"), ("second", "first")])
def test_when_every_subscribed_consumer_refuses_the_first_refusals_status_answers(
    order: tuple[str, str],
) -> None:
    """A payload that every consumer subscribed to its event refuses is delivered to none, and
    the answer carries the status of the consumer declared first."""
    delivered: list[str] = []
    consumers = [_refusing_consumer(name, f"refused_by_{name}", delivered) for name in order]
    app = create_service_app(
        settings=_make_settings(repos=[REPO_A]), secrets={REPO_A: "secret-1"}, consumers=consumers
    )
    with TestClient(app) as client:
        response = _github_post(client, "issues", _event_payload(), "refused-1")
        series = _delivery_series(client)
    assert (response.status_code, response.json(), delivered, series) == (
        200,
        {"status": f"refused_by_{order[0]}"},
        [],
        {("github", "issues", "ignored"): 1.0},
    )


def test_a_consumer_whose_refusal_is_empty_text_still_refuses_the_payload() -> None:
    """Only None takes a payload: a refusal that is the empty text is a refusal, which the
    answer carries, and the delivery is neither taken nor lost to a failed request."""
    delivered: list[str] = []
    app = create_service_app(
        settings=_make_settings(repos=[REPO_A]),
        secrets={REPO_A: "secret-1"},
        consumers=[_refusing_consumer("empty", "", delivered)],
    )
    with TestClient(app) as client:
        response = _github_post(client, "issues", _event_payload(), "refused-2")
        series = _delivery_series(client)
    assert (response.status_code, response.json(), delivered, series) == (
        200,
        {"status": ""},
        [],
        {("github", "issues", "ignored"): 1.0},
    )
