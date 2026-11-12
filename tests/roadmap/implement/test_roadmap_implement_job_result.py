"""The `implement` row logs one result line for each runner Job that ended (#4845)."""

from __future__ import annotations

import copy
import json
import logging
from typing import Any

import pytest
import yaml

from devops_cli.roadmap.run import STATUS_LANE_ROWS
from devops_cli.roadmap.stores.store import ImplementRecordKey, Item, ItemField
from tests.support.fakes.github import GitHubApiFake
from tests.support.fakes.kubernetes import FakeCluster, pod
from tests.support.fakes.roadmap_store import InMemoryRoadmapStore
from tests.support.paths import REPO_ROOT
from tests.support.roadmap_implement import route_pull_status, seed_staged
from tests.support.roadmap_job_result import result_fields
from tests.support.roadmap_stage import STAGE_REPO, StageRepo

pytestmark = pytest.mark.usefixtures("keyring_store", "app_slug")

IMPLEMENT_ROW = next(row for row in STATUS_LANE_ROWS if row.name == "implement")
JOBS = ("batch", "v1", "jobs")
CRONJOBS = ("batch", "v1", "cronjobs")
STARTED = "2026-11-12T10:00:00Z"
ENDED = "2026-11-12T10:20:00Z"


@pytest.fixture
def store() -> InMemoryRoadmapStore:
    return InMemoryRoadmapStore(repo=STAGE_REPO)


@pytest.fixture
def api(github_api: GitHubApiFake) -> GitHubApiFake:
    route_pull_status(github_api)
    return github_api


@pytest.fixture
def kube(cluster: FakeCluster) -> FakeCluster:
    template = yaml.safe_load((REPO_ROOT / "k8s/devops/cronjob-runner.yaml").read_text("utf-8"))
    cluster.custom_objects.objects[CRONJOBS] = [copy.deepcopy(template)]
    return cluster


def _held(store: InMemoryRoadmapStore, number: int) -> Item:
    item = store.item(number)
    assert item is not None
    return item


def _ended_job(
    store: InMemoryRoadmapStore, repo: StageRepo, kube: FakeCluster, condition: str
) -> tuple[int, str]:
    """One round makes the Job of a Staged item, and the Job controller then ends it: it started
    at `STARTED` and got `condition` at `ENDED`."""
    number = seed_staged(store)
    IMPLEMENT_ROW.runner(store=store, repo=STAGE_REPO, clone_path=repo.clone)
    job: dict[str, Any] = kube.custom_objects.objects[JOBS][0]
    job["status"] = {
        "startTime": STARTED,
        "conditions": [{"type": condition, "status": "True", "lastTransitionTime": ENDED}],
    }
    kube.core.answers["list_namespaced_pod"] = [
        pod(f"{job['metadata']['name']}-x1", namespace="devops")
    ]
    return number, job["metadata"]["name"]


def test_a_job_that_the_kernel_killed_logs_a_stopped_attempt_with_its_class_and_seconds(
    store: InMemoryRoadmapStore,
    staged_repo: StageRepo,
    api: GitHubApiFake,
    kube: FakeCluster,
    caplog: pytest.LogCaptureFixture,
) -> None:
    number, _ = _ended_job(store, staged_repo, kube, "Failed")
    store.set_field(_held(store, number), ItemField.STATUS, "In Progress")
    kube.core.answers["read_namespaced_pod_log"] = "MemoryError: Cannot allocate memory\n"

    with caplog.at_level(logging.INFO):
        IMPLEMENT_ROW.runner(store=store, repo=STAGE_REPO, clone_path=staged_repo.clone)

    assert result_fields(caplog) == [
        {
            "job": "implement",
            "repo": STAGE_REPO,
            "item": f"#{number}",
            "result": "stopped",
            "success": "false",
            "class": "oom",
            "infra": "true",
            "repair_rounds": "0",
            "tokens": "0",
            "seconds": "1200",
        }
    ]


def test_a_job_whose_runner_marked_its_pull_request_ready_logs_a_success(
    store: InMemoryRoadmapStore,
    staged_repo: StageRepo,
    api: GitHubApiFake,
    kube: FakeCluster,
    caplog: pytest.LogCaptureFixture,
) -> None:
    number, _ = _ended_job(store, staged_repo, kube, "Complete")
    store.set_field(
        _held(store, number),
        ItemField.STATUS,
        "In Review",
        marks={
            ImplementRecordKey.RESULT: "ready",
            ImplementRecordKey.REPAIR_ROUNDS: "2",
            ImplementRecordKey.SPEND: json.dumps({"input_tokens": 800, "output_tokens": 200}),
        },
    )
    kube.core.answers["read_namespaced_pod_log"] = "The pull request is ready.\n"

    with caplog.at_level(logging.INFO):
        IMPLEMENT_ROW.runner(store=store, repo=STAGE_REPO, clone_path=staged_repo.clone)

    assert result_fields(caplog) == [
        {
            "job": "implement",
            "repo": STAGE_REPO,
            "item": f"#{number}",
            "result": "ready",
            "success": "true",
            "class": "none",
            "infra": "false",
            "repair_rounds": "2",
            "tokens": "1000",
            "seconds": "1200",
        }
    ]
