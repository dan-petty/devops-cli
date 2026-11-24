"""Tests for launching infra-plan Job on pull_request synchronize webhooks (#5129)."""

from __future__ import annotations

import hashlib
import hmac
import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
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
from devops_cli.k8s.cluster_job_api import ClusterJobs
from devops_cli.roadmap.steps.infra_plan import infra_plan_unit
from devops_cli.server.routes.webhooks import (
    DeliveryLRUCache,
    create_webhook_router,
    launch_infra_plan,
    roadmap_consumer,
)
from tests.support.fakes.kubernetes import FakeCluster
from tests.support.job_templates import cronjob_template

pytestmark = pytest.mark.usefixtures("keyring_store", "cluster")

REPO = "owner/infra"
SECRET = "test-secret"
HEAD = "1234567890abcdef1234567890abcdef12345678"
PULL = 42

JOBS = ("batch", "v1", "jobs")
CRONJOBS = ("batch", "v1", "cronjobs")


@pytest.fixture
def kube(cluster: FakeCluster) -> FakeCluster:
    cluster.custom_objects.objects[CRONJOBS] = [cronjob_template(RUNNER_TEMPLATE)]
    return cluster


@dataclass
class _ServiceConfig:
    repos: tuple[str, ...] = (REPO,)
    lanes: Mapping[str, tuple[str, ...]] = field(default_factory=lambda: {"status": ("watch",)})


@dataclass
class _FakeServiceManager:
    state_dir: Path | None = None
    bot_login: str | None = None
    secrets: Mapping[str, str] = field(default_factory=lambda: {REPO: SECRET})
    managed_repos: set[str] = field(default_factory=lambda: {REPO})
    jobs: Mapping[str, str] = field(default_factory=lambda: {"status": "watch"})
    config: _ServiceConfig = field(default_factory=_ServiceConfig)
    delivery_cache: DeliveryLRUCache = field(default_factory=DeliveryLRUCache)

    def is_draining(self) -> bool:
        return False

    def enqueue_scoped(self, repo: str, lane: str, scoped: Callable[[], None]) -> bool:
        return True

    def enqueue_trigger(self, *args: Any, **kwargs: Any) -> bool:
        return True


def _sign(body: bytes, secret: str) -> str:
    digest = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return f"{CONST_GH_WEBHOOK_SIGNATURE_PREFIX}{digest}"


def _deliver_webhook(
    client: TestClient,
    delivery_id: str,
    payload: dict[str, Any],
) -> Any:
    body = json.dumps(payload).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        CONST_GH_WEBHOOK_EVENT_HEADER: "pull_request",
        CONST_GH_WEBHOOK_DELIVERY_HEADER: delivery_id,
        CONST_GH_WEBHOOK_SIGNATURE_HEADER: _sign(body, SECRET),
    }
    return client.post("/webhooks/github", content=body, headers=headers)


def test_two_synchronize_deliveries_create_one_job(
    kube: FakeCluster,
    isolate_devops_cli_config: Path,
) -> None:
    """Two synchronize deliveries for the same PR head create 1 Job; the second gets the existing unit."""
    # Write isolate config with infra repo
    with isolate_devops_cli_config.open("a", encoding="utf-8") as f:
        f.write(f"\ninfra:\n  repos:\n    - repo: '{REPO}'\n      agent_access: plan\n")

    from devops_cli.config.settings import reset_settings_cache

    reset_settings_cache()

    service_manager = _FakeServiceManager()
    app = FastAPI()
    app.include_router(
        create_webhook_router(service_manager, consumers=(roadmap_consumer(service_manager),))
    )
    client = TestClient(app)

    payload = {
        "repository": {"full_name": REPO, "default_branch": "main"},
        "action": "synchronize",
        "sender": {"login": "alice"},
        "pull_request": {
            "number": PULL,
            "state": "open",
            "head": {"sha": HEAD, "ref": "feat/pr-1"},
        },
    }

    # First delivery
    resp1 = _deliver_webhook(client, "deliv-1", payload)
    assert resp1.status_code == 202

    jobs_after_first = kube.custom_objects.objects.get(JOBS, [])
    assert len(jobs_after_first) == 1
    expected_unit = infra_plan_unit(REPO, PULL, HEAD)
    assert jobs_after_first[0]["metadata"]["name"] == expected_unit.name

    # Second delivery with different delivery_id but same PR head
    resp2 = _deliver_webhook(client, "deliv-2", payload)
    assert resp2.status_code == 202

    # Still only 1 Job created
    jobs_after_second = kube.custom_objects.objects.get(JOBS, [])
    assert len(jobs_after_second) == 1
    assert jobs_after_second[0]["metadata"]["name"] == expected_unit.name


def test_launch_infra_plan_returns_existing_unit_on_second_call(kube: FakeCluster) -> None:
    """Direct calls to launch_infra_plan return the same unit name and create 1 Job."""
    jobs = ClusterJobs()
    name1 = launch_infra_plan(REPO, PULL, HEAD, jobs=jobs)
    assert len(kube.custom_objects.objects.get(JOBS, [])) == 1

    name2 = launch_infra_plan(REPO, PULL, HEAD, jobs=jobs)
    assert name1 == name2
    assert len(kube.custom_objects.objects.get(JOBS, [])) == 1
