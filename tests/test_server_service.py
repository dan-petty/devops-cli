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
import time
from collections.abc import Callable, Mapping
from datetime import UTC, datetime, timedelta
from functools import partial
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from devops_cli.config import Settings
from devops_cli.config.constants import (
    CONST_GH_RATE_LIMIT_CLOCK_SKEW_BOUND_SECONDS,
    CONST_GH_WEBHOOK_DELIVERY_HEADER,
    CONST_GH_WEBHOOK_EVENT_HEADER,
    CONST_GH_WEBHOOK_SIGNATURE_HEADER,
    CONST_ROADMAP_INTAKE_BATCH_KEYS,
    CONST_SERVICE_LANE_DEFAULT,
    CONST_SERVICE_LANE_MODEL,
    CONST_SERVICE_LANE_RELEASE,
    CONST_SERVICE_METRIC_JOB_SECONDS,
    CONST_SERVICE_METRIC_JOB_START_TIMESTAMP,
    CONST_SERVICE_METRIC_JOBS,
    CONST_SERVICE_METRIC_QUEUE_DEPTH,
    CONST_SERVICE_METRIC_TRIGGERS,
    CONST_SERVICE_METRIC_WEBHOOK_DELIVERIES,
)
from devops_cli.config.settings import ServiceConfig
from devops_cli.exceptions import RoadmapRunError
from devops_cli.exceptions.git import GitHubRateLimitError
from devops_cli.roadmap.board_read import GraphQLBudget, require_budget, require_write_floor
from devops_cli.roadmap.memory_store import InMemoryRoadmapStore
from devops_cli.roadmap.run import JobOutcome, build_stub_table, run_due_jobs, service_pause_until
from devops_cli.server.json_logs import JsonLogFormatter
from devops_cli.server.routes.webhooks import verify_webhook_signature
from devops_cli.server.service import (
    PauseReader,
    RepoWorker,
    ServiceManager,
    TriggerBatch,
    create_service_app,
)
from devops_cli.telemetry.metrics import GLOBAL_METRICS
from devops_cli.telemetry.tracer import _from_otlp_any_value, get_tracer, reset_tracer

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


def test_verify_webhook_signature_canonical() -> None:
    """Test verify_webhook_signature constant-time comparison against expected HMAC."""
    payload = b'{"hello":"world"}'
    secret = "test-secret-key"
    sig = _sign(payload, secret)

    valid_res = verify_webhook_signature(payload, sig, secret)
    bad_sig_res = verify_webhook_signature(payload, "sha256=invalidhash", secret)
    bad_header_res = verify_webhook_signature(payload, "invalid_format", secret)
    empty_secret_res = verify_webhook_signature(payload, sig, "")
    none_sig_res = verify_webhook_signature(payload, None, secret)

    assert (valid_res, bad_sig_res, bad_header_res, empty_secret_res, none_sig_res) == (
        True,
        False,
        False,
        False,
        False,
    )


def test_webhook_delivery_and_batch_coalescing() -> None:
    """Test that incoming deliveries queue and coalesce into a TriggerBatch while job is active."""
    settings = _make_settings(repos=["example-org/repo1"])
    secrets = {"example-org/repo1": "secret-1"}
    job_started = threading.Event()
    job_unblock = threading.Event()
    job_2_done = threading.Event()
    received_batches: list[TriggerBatch] = []

    def test_job(batch: TriggerBatch) -> None:
        if ("poll", "", "") in batch.counts and len(batch.counts) == 1:
            return
        received_batches.append(batch)
        if ("webhook", "issues", "opened") in batch.counts:
            job_started.set()
            job_unblock.wait(timeout=2.0)
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
        assert job_started.wait(timeout=1.0) is True

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
        assert job_2_done.wait(timeout=1.0) is True

    assert len(received_batches) == 2
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
                repo1_release.wait(timeout=2.0)
            elif sum(batch.counts.values()) == 10:
                bulk_done.set()
            with concurrency_lock:
                repo1_concurrency -= 1
        else:
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
        assert repo1_blocked.wait(timeout=1.0) is True

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
        assert (res_r2.status_code, repo2_done.wait(timeout=1.0)) == (202, True)
        assert len(batches_by_repo["example-org/repo2"]) == 1

        # While Repo 1 is still blocked, send 10 concurrent triggers to Repo 1
        for i in range(10):
            p_bulk = json.dumps(
                {"repository": {"full_name": "example-org/repo1"}, "action": f"act-{i}"}
            ).encode("utf-8")
            h_bulk = {
                "Content-Type": "application/json",
                CONST_GH_WEBHOOK_EVENT_HEADER: "push",
                CONST_GH_WEBHOOK_DELIVERY_HEADER: f"bulk-{i}",
                CONST_GH_WEBHOOK_SIGNATURE_HEADER: _sign(p_bulk, "secret-1"),
            }
            res_bulk = client.post("/webhooks/github", content=p_bulk, headers=h_bulk)
            assert res_bulk.status_code == 202

        # Release Repo 1
        repo1_release.set()
        assert bulk_done.wait(timeout=1.0) is True

    assert (len(batches_by_repo["example-org/repo1"]), max_repo1_concurrency) == (2, 1)
    coalesced_batch = batches_by_repo["example-org/repo1"][1]
    assert sum(coalesced_batch.counts.values()) == 10


def test_polling_tick_advances_with_injected_fixtures() -> None:
    """Test polling tick loop schedules poll trigger at startup and after interval."""
    settings = _make_settings(repos=["example-org/repo1"], poll_interval=60)
    secrets = {"example-org/repo1": "secret-1"}
    tick_batches: list[TriggerBatch] = []
    tick_event = threading.Event()

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

    app = create_service_app(
        jobs={LANE: tick_job},
        settings=settings,
        secrets=secrets,
        clock=fake_clock,
        sleep_func=fake_sleep,
    )

    with TestClient(app):
        # Startup tick triggers immediately
        time.sleep(0.1)
        assert len(tick_batches) >= 1
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
        assert (res1.status_code, job_failed.wait(timeout=1.0)) == (202, True)

        # Run 2: will succeed
        h2 = dict(headers, **{CONST_GH_WEBHOOK_DELIVERY_HEADER: "deliv-err-2"})
        res2 = client.post("/webhooks/github", content=payload, headers=h2)
        assert (res2.status_code, job_succeeded.wait(timeout=1.0)) == (202, True)

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
    """Test that only the 4 service routes are served and unmounted routes return 404."""
    settings = _make_settings(repos=["example-org/repo1"])
    secrets = {"example-org/repo1": "secret-1"}
    app = create_service_app(settings=settings, secrets=secrets)

    with TestClient(app) as client:
        res_root = client.get("/")
        res_docs = client.get("/docs")
        res_cfg = client.get("/api/v1/config")
        res_ready = client.get("/readyz")
        res_health = client.get("/healthz")
        res_metrics = client.get("/metrics")

        assert (
            res_root.status_code,
            res_docs.status_code,
            res_cfg.status_code,
            res_ready.status_code,
            res_health.status_code,
            res_metrics.status_code,
        ) == (404, 404, 404, 200, 200, 200)


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
        time.sleep(0.1)

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
    settings = _make_settings(repos=["example-org/repo1"], drain_timeout=5)
    secrets = {"example-org/repo1": "secret-1"}
    batch1_started = threading.Event()
    batch1_release = threading.Event()
    received_batches: list[TriggerBatch] = []

    def draining_job(batch: TriggerBatch) -> None:
        if ("poll", "", "") in batch.counts and len(batch.counts) == 1:
            return
        received_batches.append(batch)
        if ("webhook", "issues", "first") in batch.counts:
            batch1_started.set()
            batch1_release.wait(timeout=2.0)

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
        assert batch1_started.wait(timeout=1.0) is True

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
    assert ("first" in actions, "second" in actions, len(received_batches)) == (True, True, 2)


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
        finished = sorted(self.done.get(timeout=1.0) for _ in range(count))
        assert all(worker.wait_active(1.0) for worker in manager.workers.values())
        return finished

    def held(self, manager: ServiceManager) -> bool:
        """Whether no round started for the triggers just enqueued: a worker whose batch may run
        is waited for until it has run, so an idle worker and no finished round mean the pause
        held every batch."""
        assert all(worker.wait_active(1.0) for worker in manager.workers.values())
        return self.done.empty()

    def triggers(self) -> dict[str, list[int]]:
        return {repo: [sum(b.counts.values()) for b in done] for repo, done in self.batches.items()}


def _service(
    jobs: Mapping[str, Callable[[TriggerBatch], None]],
    clock: _Clock,
    reader: PauseReader = service_pause_until,
) -> ServiceManager:
    """The Service over both repositories, one worker per lane each, the workers started, with no
    poll loop."""
    manager = ServiceManager(
        config=_make_settings(repos=[REPO_A, REPO_B]).service,
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
    refusals = iter([RESET, RESET, RESET + timedelta(hours=1)])
    rounds = _Rounds(lambda: _refuse_read(next(refusals)), {REPO_A: 2, REPO_B: 1})
    clock = _Clock(RESET - timedelta(minutes=20))
    with caplog.at_level(logging.INFO, logger="devops_cli.server.service"):
        manager = _service({LANE: rounds}, clock)
        _trigger(manager, REPO_A, REPO_B)
        first = rounds.wait(2, manager)
        clock.now = RESUME
        _trigger(manager, REPO_A)
        second = rounds.wait(1, manager)
        asyncio.run(manager.drain_and_stop())
    assert (first, second, [line.split(",")[0] for line in _wait_lines(caplog)]) == (
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
    """A rollout during a pause doesn't wait out the 120 s drain timeout for rounds the pause
    holds: the drain returns well within it, the workers stop, and the held rounds never run;
    the next pod's start-up poll reads the changes they were for."""
    rounds, clock = _Rounds(_refuse_read, {REPO_A: 1}), _Clock(RESET - timedelta(minutes=20))
    manager = _service({LANE: rounds}, clock)
    _trigger(manager, REPO_A)
    rounds.wait(1, manager)
    _trigger(manager, REPO_A, REPO_B)
    started = time.perf_counter()
    asyncio.run(manager.drain_and_stop())
    drained = time.perf_counter() - started
    assert (
        drained < 1.0,
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


# ── A release-lane round never waits for a model-lane round (#1532) ───────────

RELEASE_LANE, MODEL_LANE = CONST_SERVICE_LANE_RELEASE, CONST_SERVICE_LANE_MODEL


class _Lanes:
    """One repository's two lane jobs: the model lane's first round blocks, as on a slow model,
    until the test lets it go; every round is recorded by lane."""

    def __init__(self) -> None:
        self.model_started = threading.Event()
        self.model_answers = threading.Event()
        self.batches: dict[str, list[TriggerBatch]] = {RELEASE_LANE: [], MODEL_LANE: []}
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
                self.model_answers.wait(timeout=5.0)
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


def test_a_webhook_runs_the_release_lane_while_the_model_lanes_round_is_blocked() -> None:
    """The model lane's start-up round blocks on a slow model. A merged pull request's webhook
    still runs a release-lane round at once, and the triggers that arrive meanwhile wait as one
    model-lane batch, which runs once the model answers. Each lane runs one round at a time, and
    each trigger counts once for the repository, whatever the lanes."""
    lanes = _Lanes()
    app = _lanes_app(lanes)
    deliveries = [("pull_request", "closed"), ("issues", "opened"), ("issues", "opened")]
    with TestClient(app) as client:
        workers = app.state.service_manager.workers
        release, model = workers[(REPO_A, RELEASE_LANE)], workers[(REPO_A, MODEL_LANE)]
        assert lanes.model_started.wait(timeout=1.0)
        statuses = [
            _post(client, event, action, f"lane-{n}")
            for n, (event, action) in enumerate(deliveries)
        ]
        release_done, model_blocked = release.wait_active(1.0), model.is_active()
        lanes.model_answers.set()
        model_done = model.wait_active(1.0)
    pull_request_closed = ("webhook", "pull_request", "closed")
    triggers = {
        source: GLOBAL_METRICS.get_counter_value(
            CONST_SERVICE_METRIC_TRIGGERS, labels={"repo": REPO_A, "source": source}
        )
        for source in ("poll", "webhook")
    }
    assert (
        statuses,
        release_done,
        model_blocked,
        model_done,
        any(pull_request_closed in batch.counts for batch in lanes.batches[RELEASE_LANE]),
        sum(sum(batch.counts.values()) for batch in lanes.batches[RELEASE_LANE]),
        [batch.counts for batch in lanes.batches[MODEL_LANE]],
        lanes.most_at_once,
        triggers,
    ) == (
        [202, 202, 202],
        True,
        True,
        True,
        True,
        4,
        [
            {("poll", "", ""): 1},
            {pull_request_closed: 1, ("webhook", "issues", "opened"): 2},
        ],
        {RELEASE_LANE: 1, MODEL_LANE: 1},
        {"poll": 1.0, "webhook": 3.0},
    )


def test_metrics_show_a_stalled_model_lane_by_its_queue_depth() -> None:
    """While the model lane's round is blocked with a trigger waiting behind it, /metrics shows
    the model lane's queue depth at 1 and the release lane's at 0, and each lane's rounds under
    its own label."""
    lanes = _Lanes()
    app = _lanes_app(lanes)
    with TestClient(app) as client:
        release = app.state.service_manager.workers[(REPO_A, RELEASE_LANE)]
        assert lanes.model_started.wait(timeout=1.0)
        _post(client, "pull_request", "closed", "stalled-1")
        assert release.wait_active(1.0)
        exported = client.get("/metrics").text.splitlines()
        lanes.model_answers.set()
    repo = f'repo="{REPO_A}"'

    def exported_as(metric: str, labels: str) -> bool:
        return any(line.startswith(f"{metric}{{{labels}}} ") for line in exported)

    assert (
        f'{CONST_SERVICE_METRIC_QUEUE_DEPTH}{{lane="model",{repo}}} 1.0' in exported,
        f'{CONST_SERVICE_METRIC_QUEUE_DEPTH}{{lane="release",{repo}}} 0.0' in exported,
        exported_as(CONST_SERVICE_METRIC_JOBS, f'lane="release",{repo},result="success"'),
        exported_as(CONST_SERVICE_METRIC_JOB_SECONDS, f'lane="release",{repo}'),
        exported_as(CONST_SERVICE_METRIC_JOB_START_TIMESTAMP, f'lane="model",{repo}'),
        exported_as(CONST_SERVICE_METRIC_JOBS, f'lane="model",{repo},result="success"'),
    ) == (True, True, True, True, True, False)


def test_a_budget_refusal_in_the_model_lane_holds_the_release_lane_too() -> None:
    """Both lanes spend the machine account's one GraphQL budget: the model lane's refused round
    holds the release lane's next round through the shared pause until 5 s after the reset, and
    then each lane runs one round with the trigger that waited (#1400)."""
    model, release = _Rounds(_refuse_read, {REPO_A: 1}), _Rounds(lambda: None, {})
    clock = _Clock(RESET - timedelta(minutes=20))
    manager = _service({RELEASE_LANE: release, MODEL_LANE: model}, clock)
    _trigger(manager, REPO_A)
    first = (release.wait(1, manager), model.wait(1, manager))
    clock.now = RESET - timedelta(minutes=10)
    _trigger(manager, REPO_A)
    held = (release.held(manager), model.held(manager))
    clock.now = RESUME
    resumed = (release.wait(1, manager), model.wait(1, manager))
    asyncio.run(manager.drain_and_stop())
    assert (first, held, resumed, release.triggers(), model.triggers()) == (
        ([REPO_A], [REPO_A]),
        (True, True),
        ([REPO_A], [REPO_A]),
        {REPO_A: [1, 1], REPO_B: []},
        {REPO_A: [1, 1], REPO_B: []},
    )
