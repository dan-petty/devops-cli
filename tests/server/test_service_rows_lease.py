"""The rows of the Service run only in the pod that holds the Lease `roadmap-service-rows` (#6058).

Each test runs the Service app over the `cluster` fake of the Lease API. A pod that waits for the
Lease reports ready, keeps each delivery in the queue of its lanes, and reads the state of the
volume only when it takes the Lease. SIGTERM goes through the exit handler that uvicorn installs
for it, on a real server in a thread.
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging
import signal
import threading
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
import uvicorn
from fastapi import FastAPI
from fastapi.testclient import TestClient

from devops_cli.config.constants import (
    CONST_GH_WEBHOOK_DELIVERY_HEADER,
    CONST_GH_WEBHOOK_EVENT_HEADER,
    CONST_GH_WEBHOOK_SIGNATURE_HEADER,
    CONST_SERVICE_BUDGET_FILENAME,
    CONST_SERVICE_LANE_DEFAULT,
    CONST_SERVICE_ROWS_LEASE_NAME,
    CONST_SERVICE_SOURCE_WEBHOOK,
)
from devops_cli.config.settings import GitHubAppConfig, ServiceConfig, Settings
from devops_cli.exceptions import ServiceStoppingError
from devops_cli.k8s.lease import LEASE_GROUP, LEASE_PLURAL, LEASE_VERSION, LeaseHolder, LeaseTiming
from devops_cli.lang import MESSAGES
from devops_cli.server.service import TriggerBatch, create_service_app
from tests.support.fakes.kubernetes import FakeCluster, api_exception
from tests.support.waits import THREAD_HANDOFF_BOUND_SECONDS, wait_until

pytestmark = pytest.mark.usefixtures("keyring_store")

REPO = "example-org/repo1"
SECRET = "secret-1"
NAMESPACE = "devops"
LANE = CONST_SERVICE_LANE_DEFAULT
OPENED = (CONST_SERVICE_SOURCE_WEBHOOK, "issues", "opened")
# Real seconds, short for a test, with each time inside the one after it.
FAST = LeaseTiming(duration=1, renew_deadline=0.5, retry=0.05, call_timeout=0.4)


def _settings() -> Settings:
    return Settings(
        service=ServiceConfig(
            repos=[REPO],
            github_app=GitHubAppConfig(app_id=1001, installation_id=42, slug="bot-account"),
        )
    )


def _lease(identity: str, timing: LeaseTiming = FAST) -> LeaseHolder:
    return LeaseHolder(CONST_SERVICE_ROWS_LEASE_NAME, NAMESPACE, identity, timing=timing)


def _app(job: Any, lease: LeaseHolder, state_dir: Path | None = None, **kwargs: Any) -> FastAPI:
    return create_service_app(
        jobs={LANE: job},
        settings=_settings(),
        secrets={REPO: SECRET},
        state_dir=state_dir,
        rows_lease=lease,
        **kwargs,
    )


def _stored(cluster: FakeCluster) -> dict[str, Any]:
    """The spec of the Lease that the fake holds."""
    (lease,) = cluster.custom_objects.objects[(LEASE_GROUP, LEASE_VERSION, LEASE_PLURAL)]
    spec: dict[str, Any] = lease["spec"]
    return spec


def _holder(cluster: FakeCluster) -> str | None:
    leases = cluster.custom_objects.objects.get((LEASE_GROUP, LEASE_VERSION, LEASE_PLURAL))
    return _stored(cluster).get("holderIdentity") if leases else None


def _deliver(client: TestClient, delivery: str) -> int:
    """Deliver a signed `issues` `opened` event of REPO; the status of the answer."""
    body = json.dumps(
        {"repository": {"full_name": REPO}, "action": "opened", "sender": {"login": "alice"}}
    ).encode("utf-8")
    digest = hmac.new(SECRET.encode("utf-8"), body, hashlib.sha256).hexdigest()
    headers = {
        "Content-Type": "application/json",
        CONST_GH_WEBHOOK_EVENT_HEADER: "issues",
        CONST_GH_WEBHOOK_DELIVERY_HEADER: delivery,
        CONST_GH_WEBHOOK_SIGNATURE_HEADER: f"sha256={digest}",
    }
    return client.post("/webhooks/github", content=body, headers=headers).status_code


def test_a_pod_that_waits_for_the_lease_keeps_its_deliveries_and_reads_the_state_when_it_takes_it(
    cluster: FakeCluster, tmp_path: Path
) -> None:
    """The old pod holds the Lease. The new pod reports ready and healthy, and the queue of its
    lane keeps a delivery. It runs no round and reads no state file, so it does not see the 60
    requests that the old pod keeps in the budget window. When the old pod gives the Lease back,
    the new pod takes it, reads the window and the state of the jobs, and then runs the round of
    the delivery."""
    old = _lease("pod-old", LeaseTiming(duration=3600, renew_deadline=0.5, retry=0.05))
    asyncio.run(old.acquire())
    batches: list[TriggerBatch] = []
    reads: list[int] = []
    app = _app(
        batches.append,
        _lease("pod-new"),
        tmp_path,
        read_row_state=lambda: reads.append(len(batches)),
    )
    manager = app.state.service_manager

    with TestClient(app) as client:
        window = [[(datetime.now(UTC) - timedelta(minutes=5)).isoformat(), 60]]
        (tmp_path / CONST_SERVICE_BUDGET_FILENAME).write_text(json.dumps(window), encoding="utf-8")
        waiting = (
            client.get("/readyz").status_code,
            client.get("/healthz").status_code,
            _deliver(client, "delivery-1"),
        )
        queued = (
            manager.workers[(REPO, LANE)].pending_triggers,
            list(batches),
            list(reads),
            manager.budget.spent(),
            _holder(cluster),
        )
        asyncio.run(old.release())
        ran = wait_until(lambda: any(OPENED in batch.counts for batch in batches))
        taken = (ran, reads, manager.budget.spent(), _holder(cluster))

    assert (waiting, queued, taken) == (
        (200, 200, 202),
        (1, [], [], 0, "pod-old"),
        (True, [0], 60, "pod-new"),
    )


def test_a_pod_that_cannot_renew_the_lease_stops_its_rows_and_reports_unhealthy(
    cluster: FakeCluster, caplog: pytest.LogCaptureFixture
) -> None:
    """When no renewal works for the renew deadline, another pod can soon take the Lease. So the
    pod stops its workers and its poll at once, the budget refuses each GitHub request, and
    /healthz and /readyz fail until the container starts again."""
    app = _app(lambda batch: None, _lease("pod-a"))
    manager = app.state.service_manager
    worker = manager.workers[(REPO, LANE)]

    with caplog.at_level(logging.ERROR), TestClient(app) as client:
        assert wait_until(lambda: _holder(cluster) == "pod-a" and worker.is_alive())
        cluster.custom_objects.fail(
            "replace_namespaced_custom_object", api_exception(503, "Service Unavailable")
        )
        assert wait_until(lambda: client.get("/healthz").status_code == 503)
        stopped = (client.get("/readyz").status_code, wait_until(lambda: not worker.is_alive()))
        with pytest.raises(ServiceStoppingError, match="does not go to GitHub"):
            manager.budget.admit()

    lost = MESSAGES.serve.rows_lease_lost.format(lease=CONST_SERVICE_ROWS_LEASE_NAME, seconds="0.5")
    assert (stopped, lost in caplog.messages) == ((503, True), True)


def test_a_pod_that_takes_the_lease_and_cannot_read_its_state_reports_unhealthy(
    cluster: FakeCluster, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """A record of the volume that cannot be read stops the start of the rows, as it stops the
    start of a Service with no Lease (#2474): /healthz fails, so the kubelet starts the container
    again, and no worker runs. The stop of the container gives the Lease back."""
    (tmp_path / CONST_SERVICE_BUDGET_FILENAME).write_text("{not json", encoding="utf-8")
    app = _app(lambda batch: None, _lease("pod-a"), tmp_path)
    worker = app.state.service_manager.workers[(REPO, LANE)]

    with caplog.at_level(logging.ERROR), TestClient(app) as client:
        assert wait_until(lambda: client.get("/healthz").status_code == 503)
        unhealthy = (worker.is_alive(), _holder(cluster))

    failed = [message for message in caplog.messages if "could not start its rows" in message]
    assert (unhealthy, len(failed), _holder(cluster)) == ((False, "pod-a"), 1, None)


def test_sigterm_fails_readyz_renews_the_lease_through_the_drain_and_then_gives_it_back(
    cluster: FakeCluster,
) -> None:
    """uvicorn's SIGTERM handler starts the stop. /readyz fails at once, and the round in flight
    runs on. The event loop keeps renewing the Lease while the drain waits for the round, so the
    next pod does not take the rows. When the round ends, the pod gives the Lease back."""
    started, finish = threading.Event(), threading.Event()
    finished: list[bool] = []

    def job(batch: TriggerBatch) -> None:
        if OPENED in batch.counts:
            started.set()
            finished.append(finish.wait(timeout=THREAD_HANDOFF_BOUND_SECONDS))

    app = _app(job, _lease("pod-a"))
    manager = app.state.service_manager
    worker = manager.workers[(REPO, LANE)]
    server = uvicorn.Server(
        uvicorn.Config(app, host="127.0.0.1", port=0, lifespan="on", log_config=None)
    )
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    # The probe calls the app as the kubelet does, also after uvicorn closes its socket.
    probe = TestClient(app)
    try:
        assert wait_until(
            lambda: server.started and _holder(cluster) == "pod-a" and worker.is_alive()
        )
        manager.enqueue_trigger(REPO, *OPENED)
        assert started.wait(timeout=THREAD_HANDOFF_BOUND_SECONDS)
        before = probe.get("/readyz").status_code
        server.handle_exit(signal.SIGTERM, None)
        assert wait_until(manager.is_draining)
        during = probe.get("/readyz").status_code
        renewed = _stored(cluster)["renewTime"]
        renewing = wait_until(lambda: _stored(cluster)["renewTime"] != renewed)
        holder_during = _holder(cluster)
    finally:
        finish.set()
        thread.join(THREAD_HANDOFF_BOUND_SECONDS)

    assert (before, during, renewing, holder_during, finished, thread.is_alive()) == (
        200,
        503,
        True,
        "pod-a",
        [True],
        False,
    )
    assert _holder(cluster) is None
