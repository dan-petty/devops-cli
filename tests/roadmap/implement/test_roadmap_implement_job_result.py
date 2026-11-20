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
            "first_pass": "false",
            "repair_rounds": "0",
            "tokens": "0",
            "seconds": "1200",
        }
    ]


def test_a_job_whose_runner_ended_at_the_draft_logs_a_success(
    store: InMemoryRoadmapStore,
    staged_repo: StageRepo,
    api: GitHubApiFake,
    kube: FakeCluster,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The line of a Job that ended at the draft names the draft (`pull`), so the job grade scores
    the lines of one pull request by that pull request (#6559)."""
    number, _ = _ended_job(store, staged_repo, kube, "Complete")
    store.set_field(
        _held(store, number),
        ItemField.STATUS,
        "In Review",
        marks={
            ImplementRecordKey.RESULT: "drafted",
            ImplementRecordKey.PR: "42",
            ImplementRecordKey.REPAIR_ROUNDS: "2",
            ImplementRecordKey.SPEND: json.dumps({"input_tokens": 800, "output_tokens": 200}),
        },
    )
    kube.core.answers["read_namespaced_pod_log"] = "The draft pull request is open.\n"

    with caplog.at_level(logging.INFO):
        IMPLEMENT_ROW.runner(store=store, repo=STAGE_REPO, clone_path=staged_repo.clone)

    assert result_fields(caplog) == [
        {
            "job": "implement",
            "repo": STAGE_REPO,
            "item": f"#{number}",
            "result": "drafted",
            "success": "true",
            "class": "none",
            "infra": "false",
            "first_pass": "false",
            "repair_rounds": "2",
            "tokens": "1000",
            "seconds": "1200",
            "pull": "42",
        }
    ]


def test_a_job_whose_runner_returned_the_item_logs_its_tokens_and_clears_the_spend(
    store: InMemoryRoadmapStore,
    staged_repo: StageRepo,
    api: GitHubApiFake,
    kube: FakeCluster,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A return keeps the spend of the run, so the line counts the tokens of the Job: the spend
    less the part that the report of an earlier Job counted. The report then clears the spend, so
    the next plan of the item starts with none (#5881)."""
    number, _ = _ended_job(store, staged_repo, kube, "Complete")
    store.set_field(
        _held(store, number),
        ItemField.STATUS,
        "New",
        marks={
            ImplementRecordKey.RESULT: "returned",
            ImplementRecordKey.SPEND: json.dumps({"input_tokens": 800, "output_tokens": 200}),
            ImplementRecordKey.SPEND_COUNTED: "400",
        },
    )
    kube.core.answers["read_namespaced_pod_log"] = "The item went back to New.\n"

    with caplog.at_level(logging.INFO):
        IMPLEMENT_ROW.runner(store=store, repo=STAGE_REPO, clone_path=staged_repo.clone)

    record = _held(store, number).job_record
    assert [(line["result"], line["tokens"]) for line in result_fields(caplog)] == [
        ("returned", "600")
    ]
    assert (
        record.get(ImplementRecordKey.SPEND),
        record.get(ImplementRecordKey.SPEND_COUNTED),
    ) == (None, None)
