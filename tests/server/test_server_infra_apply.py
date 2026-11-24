"""Tests for infra-apply webhook delivery handling (#5130)."""

from __future__ import annotations

import hashlib
import hmac
import json
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from devops_cli.config.constants import (
    CONST_GH_WEBHOOK_DELIVERY_HEADER,
    CONST_GH_WEBHOOK_EVENT_HEADER,
    CONST_GH_WEBHOOK_SIGNATURE_HEADER,
    CONST_GH_WEBHOOK_SIGNATURE_PREFIX,
)
from devops_cli.k8s.cluster_job import RUNNER_TEMPLATE
from devops_cli.server.routes.webhooks import (
    DeliveryLRUCache,
    create_webhook_router,
    roadmap_consumer,
)
from tests.support.fakes.kubernetes import FakeCluster
from tests.support.job_templates import cronjob_template

pytestmark = pytest.mark.usefixtures("keyring_store")

REPO = "dan-petty/homelab"
SECRET = "test-secret"
COMMIT = "a" * 40
PULL = 101
CRONJOBS = ("batch", "v1", "cronjobs")
JOBS = ("batch", "v1", "jobs")


def _sign(payload: bytes, secret: str = SECRET) -> str:
    digest = hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()
    return f"{CONST_GH_WEBHOOK_SIGNATURE_PREFIX}{digest}"


@pytest.fixture
def fake_cluster(cluster: FakeCluster) -> FakeCluster:
    cluster.custom_objects.objects[CRONJOBS] = [cronjob_template(RUNNER_TEMPLATE)]
    return cluster


class _ServiceConfig:
    def __init__(self) -> None:
        self.lanes: dict[str, tuple[str, ...]] = {}


class _FakeServiceManager:
    def __init__(self) -> None:
        self.bot_login = None
        self.managed_repos = {REPO}
        self.secrets = {REPO: SECRET}
        self.delivery_cache = DeliveryLRUCache()
        self.config = _ServiceConfig()

    def is_draining(self) -> bool:
        return False

    def enqueue_trigger(self, *args: Any, **kwargs: Any) -> bool:
        return True

    def enqueue_scoped(self, *args: Any, **kwargs: Any) -> bool:
        return True


def test_two_merged_deliveries_create_one_job(
    tmp_path: Path,
    fake_cluster: FakeCluster,
    isolate_devops_cli_config: Path,
) -> None:
    with isolate_devops_cli_config.open("a") as f:
        f.write(
            f"""
infra:
  repos:
    - repo: {REPO}
      path: {tmp_path}
      agent_access: safe
      kube_context: fake
"""
        )

    service_manager = _FakeServiceManager()
    consumer = roadmap_consumer(service_manager)
    router = create_webhook_router(service_manager, [consumer])
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)

    payload = {
        "action": "closed",
        "repository": {"name": "homelab", "full_name": REPO, "owner": {"login": "dan-petty"}},
        "pull_request": {
            "number": PULL,
            "merged": True,
            "merge_commit_sha": COMMIT,
        },
    }
    body = json.dumps(payload).encode("utf-8")

    # Delivery 1
    resp1 = client.post(
        "/webhooks/github",
        content=body,
        headers={
            CONST_GH_WEBHOOK_EVENT_HEADER: "pull_request",
            CONST_GH_WEBHOOK_DELIVERY_HEADER: "deliv-1",
            CONST_GH_WEBHOOK_SIGNATURE_HEADER: _sign(body),
            "Content-Type": "application/json",
        },
    )
    assert resp1.status_code == 202
    created_jobs = fake_cluster.custom_objects.objects.get(JOBS, [])
    assert len(created_jobs) == 1
    job_name = created_jobs[0]["metadata"]["name"]
    assert "infra-apply-homelab" in job_name

    # Delivery 2 (duplicate replay)
    resp2 = client.post(
        "/webhooks/github",
        content=body,
        headers={
            CONST_GH_WEBHOOK_EVENT_HEADER: "pull_request",
            CONST_GH_WEBHOOK_DELIVERY_HEADER: "deliv-2",
            CONST_GH_WEBHOOK_SIGNATURE_HEADER: _sign(body),
            "Content-Type": "application/json",
        },
    )
    assert resp2.status_code == 202
    created_jobs = fake_cluster.custom_objects.objects.get(JOBS, [])
    assert len(created_jobs) == 1


def test_unmerged_closed_delivery_creates_no_job(
    tmp_path: Path,
    fake_cluster: FakeCluster,
    isolate_devops_cli_config: Path,
) -> None:
    with isolate_devops_cli_config.open("a") as f:
        f.write(
            f"""
infra:
  repos:
    - repo: {REPO}
      path: {tmp_path}
      agent_access: safe
      kube_context: fake
"""
        )

    service_manager = _FakeServiceManager()
    consumer = roadmap_consumer(service_manager)
    router = create_webhook_router(service_manager, [consumer])
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)

    payload = {
        "action": "closed",
        "repository": {"name": "homelab", "full_name": REPO, "owner": {"login": "dan-petty"}},
        "pull_request": {
            "number": PULL,
            "merged": False,
            "merge_commit_sha": None,
        },
    }
    body = json.dumps(payload).encode("utf-8")

    resp = client.post(
        "/webhooks/github",
        content=body,
        headers={
            CONST_GH_WEBHOOK_EVENT_HEADER: "pull_request",
            CONST_GH_WEBHOOK_DELIVERY_HEADER: "deliv-closed-unmerged",
            CONST_GH_WEBHOOK_SIGNATURE_HEADER: _sign(body),
            "Content-Type": "application/json",
        },
    )
    assert resp.status_code == 202
    created_jobs = fake_cluster.custom_objects.objects.get(JOBS, [])
    assert len(created_jobs) == 0
