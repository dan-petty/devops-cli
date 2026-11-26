"""The `implement` row of the Service's status lane: a round creates one runner Job for a Staged
item, creates no second one while a Job of the repository runs, and reports a Job that ended
(#2667).

Git runs for real on a clone with an `origin`, GitHub and the Kubernetes API are faked at their
edges, and the CronJob template is the committed manifest `k8s/devops/cronjob-runner.yaml`.
"""

from __future__ import annotations

import copy
import json
import logging
import time
from collections.abc import Callable
from datetime import timedelta
from pathlib import Path
from typing import Any

import pytest
from kubernetes.client.rest import ApiException
from markdown_it import MarkdownIt

from devops_cli.ai.client import models
from devops_cli.config.constants import (
    CONST_SERVICE_METRIC_IMPLEMENT_CONSECUTIVE_FAILURES,
    CONST_SERVICE_METRIC_IMPLEMENT_FAILURES,
    CONST_SERVICE_METRIC_IMPLEMENT_JOBS,
    CONST_SERVICE_METRIC_IMPLEMENT_REPAIR_ROUNDS,
    CONST_SERVICE_METRIC_IMPLEMENT_TOKENS,
)
from devops_cli.config.env import setting_variables
from devops_cli.exceptions.k8s import ClusterJobError
from devops_cli.exceptions.roadmap import RoadmapImplementError
from devops_cli.github.repo_ref import RepoRef
from devops_cli.k8s.cluster_job import ITEM_LABEL, OWNER_LABEL, REPO_LABEL, RUNNER_TEMPLATE
from devops_cli.lang import MESSAGES
from devops_cli.roadmap.failure import FailureClass, failure_lines
from devops_cli.roadmap.implement.implement import parse_implement_filters, plan_implement
from devops_cli.roadmap.implement.implement_submit import run_implement_round
from devops_cli.roadmap.job_launcher import CREATED_AT_ANNOTATION
from devops_cli.roadmap.run import MODEL_LANE_ROWS, STATUS_LANE_ROWS, TRIAGE_LANE_ROWS, JobOutcome
from devops_cli.roadmap.stores.store import (
    CloseReason,
    ImplementRecordKey,
    ImplementResult,
    Item,
    ItemField,
)
from devops_cli.telemetry.metrics import GLOBAL_METRICS
from tests.support.fakes.github import GitHubApiFake
from tests.support.fakes.kubernetes import (
    FakeCluster,
    pod,
    running,
    status,
    terminated,
    waiting,
)
from tests.support.fakes.roadmap_store import InMemoryRoadmapStore
from tests.support.job_templates import cronjob_template
from tests.support.roadmap_implement import (
    NEEDS_FIX_DRAFT,
    PULL,
    TASKS,
    merge_plan,
    push_staged_branch,
    route_pull_status,
    seed_staged,
)
from tests.support.roadmap_stage import STAGE_REPO, StageRepo

pytestmark = pytest.mark.usefixtures("keyring_store", "app_slug")

IMPLEMENT_ROW = next(row for row in STATUS_LANE_ROWS if row.name == "implement")
JOBS = ("batch", "v1", "jobs")
CRONJOBS = ("batch", "v1", "cronjobs")
MARKER = "<!-- devops roadmap implement -->"
SECOND_PULL = 6
A_TOKEN = "ghs_" + "a1B2c3D4e5F6g7H8i9J0k1L2m3N4o5P6q7R8"  # a fake token for the masking test


@pytest.fixture
def store() -> InMemoryRoadmapStore:
    return InMemoryRoadmapStore(repo=STAGE_REPO)


@pytest.fixture
def api(github_api: GitHubApiFake) -> GitHubApiFake:
    route_pull_status(github_api)
    route_pull_status(github_api, pull=SECOND_PULL)
    return github_api


@pytest.fixture
def template() -> dict[str, Any]:
    return cronjob_template(RUNNER_TEMPLATE)


@pytest.fixture
def kube(cluster: FakeCluster, template: dict[str, Any]) -> FakeCluster:
    cluster.custom_objects.objects[CRONJOBS] = [copy.deepcopy(template)]
    return cluster


@pytest.fixture
def built(cluster: FakeCluster) -> FakeCluster:
    """The cluster with the runner CronJob that the test builds (#6082), so a test reads no
    committed manifest."""
    cluster.custom_objects.objects[CRONJOBS] = [cronjob_template(RUNNER_TEMPLATE)]
    return cluster


DIGEST_A = "sha256:" + "a" * 64
DIGEST_B = "sha256:" + "b" * 64


def _roll(cluster: FakeCluster, digest: str | None) -> None:
    """Image Updater puts `digest` into the image of the template, or takes it out."""
    cronjob = cluster.custom_objects.objects[CRONJOBS][0]
    (container,) = cronjob["spec"]["jobTemplate"]["spec"]["template"]["spec"]["containers"][:1]
    container["image"] = "ghcr.io/example/runner:latest" + (f"@{digest}" if digest else "")


def _round(store: InMemoryRoadmapStore, repo: StageRepo) -> JobOutcome:
    """One round of the row, as the Service runs it in its model clone."""
    return IMPLEMENT_ROW.runner(store=store, repo=STAGE_REPO, clone_path=repo.clone)


def _jobs(cluster: FakeCluster) -> list[dict[str, Any]]:
    return cluster.custom_objects.objects.get(JOBS, [])


def _creates(cluster: FakeCluster) -> list[dict[str, Any]]:
    return [
        call[1]["body"]
        for call in cluster.custom_objects.calls
        if call[0] == "create_namespaced_custom_object"
    ]


def _held(store: InMemoryRoadmapStore, number: int = 1) -> Item:
    item = store.item(number)
    assert item is not None
    return item


def _record(store: InMemoryRoadmapStore, number: int = 1) -> dict[str, str | None]:
    item = store.item(number)
    assert item is not None
    return {str(key): value for key, value in item.job_record.items()}


def _end(cluster: FakeCluster, condition: str, index: int = 0) -> None:
    """The Job controller marks Job `index` Complete or Failed."""
    _jobs(cluster)[index]["status"] = {
        "conditions": [{"type": condition, "status": "True"}],
    }


def _comments(store: InMemoryRoadmapStore, number: int = 1) -> list[str]:
    return [comment.body for comment in store.comments_on(number)]


def test_the_row_follows_metrics_on_the_status_lane_runs_on_a_clone_and_is_due_every_seven_minutes() -> (
    None
):
    """The row calls no model, so it is not on the model lane, where a long refine round would
    hold it back (#2757)."""
    names = [row.name for row in STATUS_LANE_ROWS]
    assert (
        names,
        [row.name for row in TRIAGE_LANE_ROWS],
        [row.name for row in MODEL_LANE_ROWS],
        IMPLEMENT_ROW.needs_clone,
        IMPLEMENT_ROW.first_run_due,
        IMPLEMENT_ROW.interval,
    ) == (
        [
            "metrics",
            "implement",
            "plan_drift",
            "watch",
            "stage",
            "open",
            "release_comments",
            "github_status",
            "cloudflare_status",
        ],
        ["intake"],
        ["retitle", "fix_plan", "refine", "alternatives"],
        True,
        True,
        timedelta(minutes=7),
    )


def test_a_round_creates_one_job_for_a_staged_item_with_its_args_and_a_token_for_its_repository(
    store: InMemoryRoadmapStore, staged_repo: StageRepo, api: GitHubApiFake, kube: FakeCluster
) -> None:
    number = seed_staged(store)

    outcome = _round(store, staged_repo)

    (job,) = _jobs(kube)
    (container,) = job["spec"]["template"]["spec"]["containers"]
    env = {entry["name"]: entry.get("value") for entry in container["env"]}
    record = _record(store, number)
    assert (
        outcome,
        container["name"],
        container["args"],
        env[setting_variables()["service.github_app.token_repository"]],
        job["metadata"]["name"].startswith("devops-cli-implement-"),
        record["implement.job"] == job["metadata"]["name"],
        "implement.job_state" in record and record["implement.job_state"] is not None,
    ) == (
        JobOutcome(),
        "runner",
        ["roadmap", "implement", "--repo", STAGE_REPO, "--item", str(number), "--confirm"],
        STAGE_REPO,
        True,
        True,
        False,
    )


def test_a_round_creates_one_job_for_a_planned_item_whose_branch_is_gone(
    store: InMemoryRoadmapStore, stage_repo: StageRepo, api: GitHubApiFake, kube: FakeCluster
) -> None:
    number = seed_staged(store)
    merge_plan(stage_repo, number)

    _round(store, stage_repo)

    (job,) = _jobs(kube)
    (container,) = job["spec"]["template"]["spec"]["containers"]
    assert container["args"] == [
        "roadmap",
        "implement",
        "--repo",
        STAGE_REPO,
        "--item",
        str(number),
        "--confirm",
    ]
    assert _record(store, number)["implement.job"] == job["metadata"]["name"]


def _plan_of(pages: int) -> str:
    """The `tasks.md` of the tests, with `pages` more new files in extra groups so each group
    stays under `MAX_GROUP_CHANGES` (5). It names 3 files without a page and 3 + `pages` with them."""
    if not pages:
        return TASKS
    groups = []
    chunk_size = 5
    page_numbers = list(range(1, pages + 1))
    for i, start in enumerate(range(0, len(page_numbers), chunk_size), start=3):
        chunk = page_numbers[start : start + chunk_size]
        changes = ", ".join(f"`docs/page{n}.md` (new)" for n in chunk)
        groups.append(
            f"\n## {i}. Extra group {i}\n\n"
            f"Reads: `CONTEXT.md`. Changes: {changes}.\n\n"
            f"- [ ] {i}.1 Add documentation files for part {i}\n"
            f"  - Verification: `$ uv run devops ci test tests/test_shout.py`\n"
        )
    return TASKS + "".join(groups)


def _sized(job: dict[str, Any]) -> tuple[Any, ...]:
    """The CPU request, the CPU limit, the worker count, the memory request and the memory limit
    of the Job's container."""
    (container,) = job["spec"]["template"]["spec"]["containers"]
    env = {entry["name"]: entry.get("value") for entry in container["env"]}
    resources = container["resources"]
    return (
        resources["requests"]["cpu"],
        resources["limits"]["cpu"],
        env["PYTEST_XDIST_AUTO_NUM_WORKERS"],
        resources["requests"]["memory"],
        resources["limits"]["memory"],
    )


@pytest.mark.usefixtures("no_continuation")
def test_a_plan_with_few_files_gets_a_smaller_job_than_a_plan_with_many(
    store: InMemoryRoadmapStore, stage_repo: StageRepo, api: GitHubApiFake, kube: FakeCluster
) -> None:
    push_staged_branch(stage_repo, tasks=_plan_of(0))
    seed_staged(store)
    _round(store, stage_repo)
    _end(kube, "Complete")
    push_staged_branch(stage_repo, tasks=_plan_of(9), number=2)
    seed_staged(store, pull=SECOND_PULL)

    _round(store, stage_repo)

    small, large = (_sized(job) for job in _jobs(kube))
    assert (small, large) == (
        ("1", "1", "1", "2Gi", "8Gi"),
        ("4", "4", "4", "6Gi", "8Gi"),
    )


def test_a_planned_item_is_sized_from_the_plan_on_the_default_branch(
    store: InMemoryRoadmapStore, stage_repo: StageRepo, api: GitHubApiFake, kube: FakeCluster
) -> None:
    number = seed_staged(store)
    merge_plan(stage_repo, number, tasks=_plan_of(8))

    _round(store, stage_repo)

    (job,) = _jobs(kube)
    assert _sized(job) == ("4", "4", "4", "6Gi", "8Gi")


def test_the_job_keeps_the_storage_and_the_other_values_of_the_template(
    store: InMemoryRoadmapStore,
    staged_repo: StageRepo,
    api: GitHubApiFake,
    kube: FakeCluster,
    template: dict[str, Any],
) -> None:
    seed_staged(store)

    _round(store, staged_repo)

    (job,) = _jobs(kube)
    (container,) = job["spec"]["template"]["spec"]["containers"]
    (kept,) = template["spec"]["jobTemplate"]["spec"]["template"]["spec"]["containers"]
    assert (
        container["resources"]["requests"]["ephemeral-storage"],
        container["resources"]["limits"]["ephemeral-storage"],
    ) == (
        kept["resources"]["requests"]["ephemeral-storage"],
        kept["resources"]["limits"]["ephemeral-storage"],
    )


def test_the_setting_raises_the_memory_limit_of_the_job(
    store: InMemoryRoadmapStore,
    staged_repo: StageRepo,
    api: GitHubApiFake,
    kube: FakeCluster,
    config: Callable[..., Path],
) -> None:
    config(roadmap={"implement": {"max_memory_limit": "12Gi"}})
    seed_staged(store)

    _round(store, staged_repo)

    (job,) = _jobs(kube)
    assert _sized(job)[4] == "12Gi"


def test_no_second_job_is_created_while_the_first_runs_also_for_another_staged_item(
    store: InMemoryRoadmapStore, staged_repo: StageRepo, api: GitHubApiFake, kube: FakeCluster
) -> None:
    seed_staged(store)
    _round(store, staged_repo)
    push_staged_branch(staged_repo, number=2)
    seed_staged(store, pull=SECOND_PULL)

    _round(store, staged_repo)
    _round(store, staged_repo)

    assert (len(_creates(kube)), _record(store, 2).get("implement.job")) == (1, None)


def test_a_running_job_of_another_repository_does_not_block_this_one(
    store: InMemoryRoadmapStore, staged_repo: StageRepo, api: GitHubApiFake, kube: FakeCluster
) -> None:
    kube.custom_objects.objects[JOBS] = [
        {
            "metadata": {
                "name": "devops-cli-runner-other",
                "namespace": "devops",
                "labels": {"implement-repo": "0000000000000000"},
            }
        }
    ]
    seed_staged(store)

    _round(store, staged_repo)

    assert len(_creates(kube)) == 1


def _fix_job(*, suspend: bool) -> dict[str, Any]:
    """A fix-checks Job of the watch row of the repository in the cluster, created now, waiting
    suspended or running (#5027). A waiting Job holds a place only while its repository is in
    `service.repos` and it waits within `roadmap.fix_checks.max_wait_minutes` (#6018)."""
    ref = RepoRef(STAGE_REPO)
    return {
        "metadata": {
            "name": "devops-cli-fix-checks-project-9-0123456789",
            "namespace": "devops",
            "labels": {
                "app.kubernetes.io/managed-by": "devops-cli",
                "app.kubernetes.io/component": "roadmap-fix-checks",
                OWNER_LABEL: ref.owner_label,
                REPO_LABEL: ref.repo_label,
            },
            "annotations": {CREATED_AT_ANNOTATION: str(int(time.time()))},
        },
        "spec": {"suspend": suspend},
    }


def test_a_waiting_fix_job_goes_before_a_new_implement_job(
    store: InMemoryRoadmapStore,
    staged_repo: StageRepo,
    api: GitHubApiFake,
    kube: FakeCluster,
    config: Callable[..., Path],
) -> None:
    """With one place for a model Job, a fix-checks Job that waits suspended holds it: the round
    creates no implement Job and waits. Once the fix Job runs and a place is free, it holds no
    implement lock: it has its own component and no label `implement-repo` (#5027)."""
    config(roadmap={"model_jobs": 1}, service={"repos": [STAGE_REPO]})
    kube.custom_objects.objects[JOBS] = [_fix_job(suspend=True)]
    seed_staged(store)

    waited = run_implement_round(store, repo=STAGE_REPO, source=staged_repo.clone)
    held = (_creates(kube), waited.waiting, _record(store).get("implement.job"))
    config(roadmap={"model_jobs": 2})
    kube.custom_objects.objects[JOBS] = [_fix_job(suspend=False)]
    _round(store, staged_repo)

    assert (held, len(_creates(kube))) == (([], True, None), 1)


def test_a_running_job_of_this_repository_that_no_item_records_blocks_a_new_one(
    store: InMemoryRoadmapStore, staged_repo: StageRepo, api: GitHubApiFake, kube: FakeCluster
) -> None:
    seed_staged(store)
    _round(store, staged_repo)
    store.set_marks(store.item(1), {ImplementRecordKey.JOB: None})  # type: ignore[arg-type]
    push_staged_branch(staged_repo, number=2)
    seed_staged(store, pull=SECOND_PULL)

    _round(store, staged_repo)

    assert len(_creates(kube)) == 1


def test_a_job_that_a_person_starts_after_the_plan_gets_no_second_job_from_the_round(
    store: InMemoryRoadmapStore,
    staged_repo: StageRepo,
    api: GitHubApiFake,
    kube: FakeCluster,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The round plans with git and network reads. A runner Job that `devops roadmap implement
    --item` starts in that time is seen when the round lists the Jobs again before it creates."""
    from devops_cli.k8s.cluster_job import repository_label

    number = seed_staged(store)
    real_plan = plan_implement

    def plan_then_start(*args: Any, **kwargs: Any) -> Any:
        plan = real_plan(*args, **kwargs)
        kube.custom_objects.objects[JOBS] = [
            {
                "metadata": {
                    "name": "devops-cli-runner-by-hand",
                    "namespace": "devops",
                    "labels": {"implement-repo": repository_label(STAGE_REPO)},
                }
            }
        ]
        return plan

    monkeypatch.setattr(
        "devops_cli.roadmap.implement.implement_submit.plan_implement", plan_then_start
    )

    _round(store, staged_repo)

    assert (_creates(kube), _owner(store, number), _record(store, number).get("implement.job")) == (
        [],
        (None, []),
        None,
    )


def test_a_job_that_finished_its_item_is_recorded_with_no_second_report(
    store: InMemoryRoadmapStore, staged_repo: StageRepo, api: GitHubApiFake, kube: FakeCluster
) -> None:
    """The finished comment of the runner is the report of the run: the round records the state
    of the Job and posts no comment that repeats the end of its log (#6194). The round still reads
    the log first, so a stop that the runner writes in that time keeps its class (#3476)."""
    number = seed_staged(store)
    _round(store, staged_repo)
    name = _jobs(kube)[0]["metadata"]["name"]
    item = store.item(number)
    assert item is not None
    store.set_field(
        item,
        ItemField.STATUS,
        "In Review",
        marks={ImplementRecordKey.RESULT: ImplementResult.DRAFTED.value},
    )
    _end(kube, "Complete")
    kube.core.answers["list_namespaced_pod"] = [pod(f"{name}-x1", namespace="devops")]
    kube.core.answers["read_namespaced_pod_log"] = f"Took 1 item(s).\nauthorization: {A_TOKEN}\n"

    _round(store, staged_repo)

    held = store.item(number)
    assert held is not None
    assert (
        held.status,
        _record(store, number)["implement.job_state"],
        _record(store, number).get("implement.stopped"),
        [c for c in _comments(store, number) if c.startswith(MARKER)],
        len(_creates(kube)),
    ) == ("In Review", "succeeded", None, [], 1)
    log_call = next(c for c in kube.core.calls if c[0] == "read_namespaced_pod_log")
    pod_call = next(c for c in kube.core.calls if c[0] == "list_namespaced_pod")
    assert (log_call[1]["name"], log_call[1]["tail_lines"], pod_call[1]["label_selector"]) == (
        f"{name}-x1",
        40,
        f"batch.kubernetes.io/job-name={name}",
    )


def test_a_job_whose_runner_wrote_its_stop_is_recorded_with_no_second_report(
    store: InMemoryRoadmapStore, staged_repo: StageRepo, api: GitHubApiFake, built: FakeCluster
) -> None:
    """The stop comment of the runner is the one copy of the stop report: the round records the
    state of the Job and posts no comment that repeats the end lines of its log (#6194)."""
    number = seed_staged(store)
    _round(store, staged_repo)
    name = _jobs(built)[0]["metadata"]["name"]
    store.set_field(
        _held(store, number),
        ItemField.STATUS,
        "Blocked",
        marks={
            ImplementRecordKey.STOPPED: "group 2",
            ImplementRecordKey.FAILURE: FailureClass.PROVIDER.value,
            ImplementRecordKey.RESULT: ImplementResult.STOPPED.value,
        },
    )
    _end(built, "Failed")
    built.core.answers["list_namespaced_pod"] = [pod(f"{name}-x1", namespace="devops")]
    built.core.answers["read_namespaced_pod_log"] = "Failure class provider. Action left: retry.\n"

    _round(store, staged_repo)

    assert (
        [c for c in _comments(store, number) if c.startswith(MARKER)],
        _record(store, number)["implement.job_state"],
        _record(store, number)["implement.stopped"],
    ) == ([], "failed", "group 2")


@pytest.mark.usefixtures("no_continuation")
def test_a_retry_after_a_stop_of_the_runner_clears_one_stop_and_never_loops(
    store: InMemoryRoadmapStore, staged_repo: StageRepo, api: GitHubApiFake, built: FakeCluster
) -> None:
    """The round posts no Job report after a stop that the runner wrote (#6194), so the comment of
    the clear ends the retry of a person: `implement: retry` clears one stop, and the next stop
    waits for a new retry, with no new Job."""
    number = seed_staged(store)
    _round(store, staged_repo)

    def runner_stops(job: int) -> None:
        """The runner of Job `job` writes its stop and its stop comment, and its Job fails."""
        store.set_field(
            _held(store, number),
            ItemField.STATUS,
            "Blocked",
            marks={
                ImplementRecordKey.STOPPED: "group 2",
                ImplementRecordKey.FAILURE: FailureClass.PROVIDER.value,
                ImplementRecordKey.RESULT: ImplementResult.STOPPED.value,
            },
        )
        store.comment(
            number,
            MESSAGES.roadmap.implement_comment_stopped.format(
                marker=MARKER,
                step="group 2",
                check="",
                failure=failure_lines(FailureClass.PROVIDER),
                table="",
                extensions="",
                reason="    The provider broke.",
                last="none.",
                diff="",
                note="",
            ),
        )
        _end(built, "Failed", job)

    runner_stops(0)
    _round(store, staged_repo)
    store.as_actor("owner").comment(number, "implement: retry")
    _round(store, staged_repo)
    runner_stops(1)
    _round(store, staged_repo)
    _round(store, staged_repo)

    assert (
        len([c for c in _comments(store, number) if "rule `retry`" in c]),
        len(_creates(built)),
        _held(store, number).status,
        _record(store, number)["implement.stopped"],
    ) == (1, 2, "Blocked", "group 2")


def test_a_record_naming_another_items_job_is_skipped_and_reads_no_log(
    store: InMemoryRoadmapStore, staged_repo: StageRepo, api: GitHubApiFake, kube: FakeCluster
) -> None:
    """The record block is text of the issue, which its author can edit. A record on item A that
    names the runner Job of item B leaves that Job alone: the round acts on a Job only for the
    item that its item label names (#5551)."""
    number_b = seed_staged(store)
    _round(store, staged_repo)
    name_b = _jobs(kube)[0]["metadata"]["name"]
    item_b = store.item(number_b)
    assert item_b is not None
    store.set_field(item_b, ItemField.STATUS, "In Review")
    _end(kube, "Complete")
    kube.core.answers["list_namespaced_pod"] = [pod(f"{name_b}-x1", namespace="devops")]
    kube.core.answers["read_namespaced_pod_log"] = "Finished successfully.\n"

    number_a = store.seed_issue(
        "fix(roadmap): hostile edit of record",
        fields={ItemField.STATUS: "In Progress", ItemField.PRIORITY: "P1-High"},
        labels=("type/bug", "effort/low"),
    )
    item_a = store.item(number_a)
    assert item_a is not None
    store.set_marks(item_a, {ImplementRecordKey.JOB: name_b})

    kube.core.calls.clear()
    _round(store, staged_repo)

    assert (
        [c for c in _comments(store, number_a) if c.startswith(MARKER)],
        "implement.job_state" in _record(store, number_a),
        _record(store, number_b)["implement.job_state"],
        len([c for c in kube.core.calls if c[0] == "read_namespaced_pod_log"]),
    ) == ([], False, "succeeded", 1)

    kube.core.calls.clear()
    _round(store, staged_repo)

    assert (
        [c for c in _comments(store, number_a) if c.startswith(MARKER)],
        "implement.job_state" in _record(store, number_a),
        [c for c in kube.core.calls if c[0] == "read_namespaced_pod_log"],
    ) == ([], False, [])


def _fences_of_the_report(
    store: InMemoryRoadmapStore, staged_repo: StageRepo, kube: FakeCluster, written: bytes
) -> tuple[str, list[Any]]:
    """Run a Job that ended with the log `written`, and give its report comment and the fenced
    blocks that a CommonMark reader finds in it."""
    number = seed_staged(store)
    _round(store, staged_repo)
    name = _jobs(kube)[0]["metadata"]["name"]
    _end(kube, "Failed")
    kube.core.answers["list_namespaced_pod"] = [pod(f"{name}-x1", namespace="devops")]
    kube.core.answers["read_namespaced_pod_log"] = written

    _round(store, staged_repo)

    (comment,) = [c for c in _comments(store, number) if c.startswith(MARKER)]
    return comment, [t for t in MarkdownIt("commonmark").parse(comment) if t.type == "fence"]


@pytest.mark.usefixtures("no_continuation")
def test_the_log_of_an_ended_job_is_decoded_text_in_one_fenced_block_with_the_secret_masked(
    store: InMemoryRoadmapStore, staged_repo: StageRepo, api: GitHubApiFake, kube: FakeCluster
) -> None:
    written = f"Tool call: ok.\n\N{CHECK MARK} Took 1 item(s).\nauthorization: {A_TOKEN}\n".encode()

    comment, fences = _fences_of_the_report(store, staged_repo, kube, written)

    assert (
        len(fences),
        fences[0].content.splitlines()[:2],
        "b'" in comment,
        "\\n" in comment,
        "\\x" in comment,
        A_TOKEN in comment,
        "<masked-github-token>" in fences[0].content,
    ) == (1, ["Tool call: ok.", "\N{CHECK MARK} Took 1 item(s)."], False, False, False, False, True)


@pytest.mark.usefixtures("no_continuation")
def test_the_fence_of_the_log_of_an_ended_job_is_longer_than_a_run_of_backticks_in_it(
    store: InMemoryRoadmapStore, staged_repo: StageRepo, api: GitHubApiFake, kube: FakeCluster
) -> None:
    written = b"before\n```\nafter the line that tries to close the block\n"

    _, fences = _fences_of_the_report(store, staged_repo, kube, written)

    assert (len(fences), fences[0].markup, fences[0].content) == (
        1,
        "````",
        "before\n```\nafter the line that tries to close the block\n",
    )


@pytest.mark.usefixtures("no_continuation")
def test_a_job_that_failed_stops_an_item_that_is_in_progress_and_no_job_is_made_again(
    store: InMemoryRoadmapStore, staged_repo: StageRepo, api: GitHubApiFake, kube: FakeCluster
) -> None:
    number = seed_staged(store)
    _round(store, staged_repo)
    item = store.item(number)
    assert item is not None
    store.set_field(item, ItemField.STATUS, "In Progress")
    _end(kube, "Failed")

    _round(store, staged_repo)
    _round(store, staged_repo)

    held = store.item(number)
    assert held is not None
    (comment,) = [c for c in _comments(store, number) if c.startswith(MARKER)]
    assert (
        held.status,
        _record(store, number)["implement.job_state"],
        _record(store, number)["implement.stopped"],
        "ended: failed." in comment,
        "implement: retry" in comment,
        len(_creates(kube)),
    ) == ("Blocked", "failed", "job", True, True, 1)


def _failures(failure_class: str, repo: str = STAGE_REPO) -> float:
    """The count of the Service's counter of failures for `failure_class` in `repo` (#3495)."""
    return GLOBAL_METRICS.get_counter(
        CONST_SERVICE_METRIC_IMPLEMENT_FAILURES, labels={"class": failure_class, "repo": repo}
    )


def _implement_jobs(item_class: str, result: str, repo: str = STAGE_REPO) -> float:
    """The count of runner Jobs reported with `item_class` and `result` in `repo` (#3069)."""
    return GLOBAL_METRICS.get_counter(
        CONST_SERVICE_METRIC_IMPLEMENT_JOBS,
        labels={"repo": repo, "item_class": item_class, "result": result},
    )


def _repair_rounds_count(item_class: str, repo: str = STAGE_REPO) -> float:
    """The count of repair rounds for `item_class` in `repo` (#3069)."""
    return GLOBAL_METRICS.get_counter(
        CONST_SERVICE_METRIC_IMPLEMENT_REPAIR_ROUNDS,
        labels={"repo": repo, "item_class": item_class},
    )


def _tokens_count(item_class: str, repo: str = STAGE_REPO) -> float:
    """The count of tokens for `item_class` in `repo` (#3069)."""
    return GLOBAL_METRICS.get_counter(
        CONST_SERVICE_METRIC_IMPLEMENT_TOKENS,
        labels={"repo": repo, "item_class": item_class},
    )


def _consecutive_failures_count(failure_class: str, repo: str = STAGE_REPO) -> float:
    """The consecutive failures gauge for `failure_class` in `repo` (#3069)."""
    return GLOBAL_METRICS.get_gauge(
        CONST_SERVICE_METRIC_IMPLEMENT_CONSECUTIVE_FAILURES,
        labels={"repo": repo, "class": failure_class},
    )


def test_a_stop_that_the_runner_wrote_is_counted_once_under_its_class(
    store: InMemoryRoadmapStore, staged_repo: StageRepo, api: GitHubApiFake, kube: FakeCluster
) -> None:
    number = seed_staged(store)
    _round(store, staged_repo)
    store.set_field(
        _held(store, number),
        ItemField.STATUS,
        "Blocked",
        marks={ImplementRecordKey.STOPPED: "group 2", ImplementRecordKey.FAILURE: "parser"},
    )
    _end(kube, "Failed")
    before = (_failures("parser"), _failures("oom"))

    _round(store, staged_repo)
    _round(store, staged_repo)

    assert (_failures("parser") - before[0], _failures("oom") - before[1]) == (1, 0)
    assert _record(store, number)["implement.failure"] == "parser"


def test_a_job_that_left_no_result_gets_the_class_of_its_log_in_the_record_the_comment_and_the_count(
    store: InMemoryRoadmapStore, staged_repo: StageRepo, api: GitHubApiFake, kube: FakeCluster
) -> None:
    number = seed_staged(store)
    _round(store, staged_repo)
    name = _jobs(kube)[0]["metadata"]["name"]
    store.set_field(_held(store, number), ItemField.STATUS, "In Progress")
    _end(kube, "Failed")
    kube.core.answers["list_namespaced_pod"] = [pod(f"{name}-x1", namespace="devops")]
    kube.core.answers["read_namespaced_pod_log"] = (
        "Traceback (most recent call last):\nMemoryError: Cannot allocate memory\n"
    )
    before = _failures("oom")

    _round(store, staged_repo)

    (comment,) = [c for c in _comments(store, number) if c.startswith(MARKER)]
    assert _failures("oom") - before == 1
    assert _record(store, number)["implement.failure"] == "oom"
    assert "Failure class: `oom`.\nAction taken: none.\nAction left: `raise_limit`:" in comment


def test_a_job_that_a_spent_provider_key_stopped_counts_spend_limit_and_waits_for_a_person(
    store: InMemoryRoadmapStore, staged_repo: StageRepo, api: GitHubApiFake, kube: FakeCluster
) -> None:
    """The Job stops for a spent key as for a refused key, and leaves no result, so the class
    comes from the error line of its log (#6821)."""
    number = seed_staged(store)
    _round(store, staged_repo)
    name = _jobs(kube)[0]["metadata"]["name"]
    store.set_field(_held(store, number), ItemField.STATUS, "In Progress")
    _end(kube, "Failed")
    kube.core.answers["list_namespaced_pod"] = [pod(f"{name}-x1", namespace="devops")]
    spent = models.spend_limit_error(403, "Key limit exceeded")
    kube.core.answers["read_namespaced_pod_log"] = f"✗ Could not run the job: {spent}\n"
    before = _failures("spend_limit")

    _round(store, staged_repo)

    (comment,) = [c for c in _comments(store, number) if c.startswith(MARKER)]
    assert (
        _failures("spend_limit") - before,
        _record(store, number)["implement.failure"],
        "Failure class: `spend_limit`.\nAction taken: none.\nAction left: `wait`:" in comment,
    ) == (1, "spend_limit", True)


@pytest.mark.usefixtures("no_continuation")
def test_a_pod_killed_for_memory_with_no_log_stops_the_item_as_oom(
    store: InMemoryRoadmapStore, staged_repo: StageRepo, api: GitHubApiFake, kube: FakeCluster
) -> None:
    """A kernel kill leaves exit status 137 and no log text (#3727)."""
    number = seed_staged(store)
    _round(store, staged_repo)
    name = _jobs(kube)[0]["metadata"]["name"]
    store.set_field(_held(store, number), ItemField.STATUS, "In Progress")
    _end(kube, "Failed")
    kube.core.answers["list_namespaced_pod"] = [
        pod(
            f"{name}-x1",
            namespace="devops",
            statuses=[status("runner", terminated(137, "OOMKilled"))],
        )
    ]
    kube.core.answers["read_namespaced_pod_log"] = b""

    _round(store, staged_repo)
    _round(store, staged_repo)

    assert (
        _record(store, number)["implement.failure"],
        _record(store, number)["implement.stopped"],
        len(_creates(kube)),
    ) == ("oom", "job", 1)


@pytest.mark.usefixtures("no_continuation")
def test_an_agent_container_killed_for_memory_stops_the_item_as_oom(
    store: InMemoryRoadmapStore, staged_repo: StageRepo, api: GitHubApiFake, kube: FakeCluster
) -> None:
    """On the phases (#3700), the init container `agent` ends the pod with exit status 137, and
    `publish` never starts. The report reads the init containers first (#6690)."""
    number = seed_staged(store)
    _round(store, staged_repo)
    name = _jobs(kube)[0]["metadata"]["name"]
    store.set_field(_held(store, number), ItemField.STATUS, "In Progress")
    _end(kube, "Failed")
    kube.core.answers["list_namespaced_pod"] = [
        pod(
            f"{name}-x1",
            namespace="devops",
            init_containers=("prepare", "agent"),
            containers=("publish",),
            init_statuses=[
                status("prepare", terminated(0)),
                status("agent", terminated(137, "OOMKilled")),
            ],
            statuses=[status("publish", waiting("PodInitializing"))],
        )
    ]
    kube.core.answers["read_namespaced_pod_log"] = {("devops", f"{name}-x1", "agent"): b""}

    _round(store, staged_repo)
    _round(store, staged_repo)

    assert (
        _record(store, number)["implement.failure"],
        _record(store, number)["implement.stopped"],
        len(_creates(kube)),
    ) == ("oom", "job", 1)


@pytest.mark.usefixtures("no_continuation")
def test_a_pod_evicted_for_its_home_volume_stops_as_limit_reached_and_names_the_volume(
    store: InMemoryRoadmapStore, staged_repo: StageRepo, api: GitHubApiFake, kube: FakeCluster
) -> None:
    """The kubelet evicted the runner of #3648 for its home volume and killed it at the end of the
    grace period: exit status 137 with the container reason `Error` (#5960). More memory does not
    help, so the class is not `oom`, and the comment names the volume and its limit."""
    message = 'Usage of EmptyDir volume "home" exceeds the limit "4Gi". '
    number = seed_staged(store)
    _round(store, staged_repo)
    name = _jobs(kube)[0]["metadata"]["name"]
    store.set_field(_held(store, number), ItemField.STATUS, "In Progress")
    _end(kube, "Failed")
    kube.core.answers["list_namespaced_pod"] = [
        pod(
            f"{name}-x1",
            namespace="devops",
            phase="Failed",
            reason="Evicted",
            message=message,
            statuses=[status("runner", terminated(137, "Error"))],
        )
    ]
    kube.core.answers["read_namespaced_pod_log"] = b""

    _round(store, staged_repo)
    _round(store, staged_repo)

    (comment,) = [c for c in _comments(store, number) if c.startswith(MARKER)]
    assert (
        _record(store, number)["implement.failure"],
        _record(store, number)["implement.stopped"],
        len(_creates(kube)),
    ) == ("limit_reached", "job", 1)
    assert message.strip() in comment
    assert "Failure class: `limit_reached`." in comment


def test_the_last_state_of_a_restarted_container_gives_the_exit_status(
    store: InMemoryRoadmapStore, staged_repo: StageRepo, api: GitHubApiFake, kube: FakeCluster
) -> None:
    """The state holds no termination, and the last state holds exit status 137 (#3727)."""
    number = seed_staged(store)
    _round(store, staged_repo)
    name = _jobs(kube)[0]["metadata"]["name"]
    store.set_field(_held(store, number), ItemField.STATUS, "In Progress")
    _end(kube, "Failed")
    kube.core.answers["list_namespaced_pod"] = [
        pod(
            f"{name}-x1",
            namespace="devops",
            statuses=[status("runner", running(), restarts=1, last=terminated(137, "OOMKilled"))],
        )
    ]
    kube.core.answers["read_namespaced_pod_log"] = b""

    _round(store, staged_repo)

    assert _record(store, number)["implement.failure"] == "oom"


def test_a_pod_with_no_terminated_container_keeps_the_class_of_the_log(
    store: InMemoryRoadmapStore, staged_repo: StageRepo, api: GitHubApiFake, kube: FakeCluster
) -> None:
    """No terminated state means no exit status, so only the log classifies the failure (#3727)."""
    number = seed_staged(store)
    _round(store, staged_repo)
    name = _jobs(kube)[0]["metadata"]["name"]
    store.set_field(_held(store, number), ItemField.STATUS, "In Progress")
    _end(kube, "Failed")
    kube.core.answers["list_namespaced_pod"] = [
        pod(f"{name}-x1", namespace="devops", statuses=[status("runner", running())])
    ]
    kube.core.answers["read_namespaced_pod_log"] = "MemoryError: Cannot allocate memory"

    _round(store, staged_repo)

    assert _record(store, number)["implement.failure"] == "oom"


def test_a_stop_that_the_runner_writes_while_the_report_reads_the_log_keeps_its_class(
    store: InMemoryRoadmapStore,
    staged_repo: StageRepo,
    api: GitHubApiFake,
    kube: FakeCluster,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The listing of the round shows the item In Progress. The runner writes its stop with the
    class `timeout` while the report reads the log, and the log alone would read as `oom`."""
    number = seed_staged(store)
    _round(store, staged_repo)
    name = _jobs(kube)[0]["metadata"]["name"]
    store.set_field(_held(store, number), ItemField.STATUS, "In Progress")
    _end(kube, "Failed")
    kube.core.answers["list_namespaced_pod"] = [pod(f"{name}-x1", namespace="devops")]
    kube.core.answers["read_namespaced_pod_log"] = (
        "Traceback (most recent call last):\nMemoryError: Cannot allocate memory\n"
    )
    read_log = kube.core.read_namespaced_pod_log

    def runner_stops_then_log(*args: Any, **kwargs: Any) -> Any:
        store.set_field(
            _held(store, number),
            ItemField.STATUS,
            "Blocked",
            marks={ImplementRecordKey.STOPPED: "group 2", ImplementRecordKey.FAILURE: "timeout"},
        )
        return read_log(*args, **kwargs)

    monkeypatch.setattr(kube.core, "read_namespaced_pod_log", runner_stops_then_log)
    before = (_failures("timeout"), _failures("oom"))

    _round(store, staged_repo)

    assert (_failures("timeout") - before[0], _failures("oom") - before[1]) == (1, 0)
    assert _record(store, number)["implement.failure"] == "timeout"
    assert _record(store, number)["implement.stopped"] == "group 2"
    assert "Failure class: `oom`" not in "".join(_comments(store, number))


def test_a_job_that_ended_with_a_result_is_no_failure(
    store: InMemoryRoadmapStore, staged_repo: StageRepo, api: GitHubApiFake, kube: FakeCluster
) -> None:
    number = seed_staged(store)
    _round(store, staged_repo)
    store.set_field(_held(store, number), ItemField.STATUS, "In Review")
    _end(kube, "Complete")
    before = sum(_failures(klass.value) for klass in FailureClass)

    _round(store, staged_repo)

    assert sum(_failures(klass.value) for klass in FailureClass) == before
    assert _record(store, number).get("implement.failure") is None


@pytest.mark.usefixtures("no_continuation")
def test_a_job_that_ended_and_left_the_item_ready_and_unstopped_stops_it_too(
    store: InMemoryRoadmapStore, staged_repo: StageRepo, api: GitHubApiFake, kube: FakeCluster
) -> None:
    """A Job that exits 0 having done nothing would otherwise be made again every round."""
    number = seed_staged(store)
    _round(store, staged_repo)
    _end(kube, "Complete")

    _round(store, staged_repo)

    held = store.item(number)
    assert held is not None
    assert (held.status, _record(store, number)["implement.stopped"], len(_creates(kube))) == (
        "Blocked",
        "job",
        1,
    )


def test_the_round_sets_in_progress_for_the_item_of_the_job_it_makes(
    store: InMemoryRoadmapStore, staged_repo: StageRepo, api: GitHubApiFake, kube: FakeCluster
) -> None:
    """The label shows the Job as soon as the record names it, and the Job finds its own item."""
    number = seed_staged(store)
    store.set_field(_held(store, number), ItemField.STATUS, "Ready")

    _round(store, staged_repo)

    plan = plan_implement(
        store,
        repo=STAGE_REPO,
        source=staged_repo.clone,
        filters=parse_implement_filters(()),
        item_number=number,
    )
    assert (_held(store, number).status, [t.item.number for t in plan.selected]) == (
        "In Progress",
        [number],
    )


@pytest.mark.usefixtures("no_continuation")
def test_a_job_that_ended_and_left_the_item_planned_and_unstopped_stops_it_too(
    store: InMemoryRoadmapStore, stage_repo: StageRepo, api: GitHubApiFake, kube: FakeCluster
) -> None:
    number = seed_staged(store, status="Planned")
    merge_plan(stage_repo, number)
    _round(store, stage_repo)
    _end(kube, "Complete")

    _round(store, stage_repo)

    assert (
        _record(store, number)["implement.stopped"],
        _record(store, number)["implement.job_state"],
        len(_creates(kube)),
    ) == ("job", "succeeded", 1)


@pytest.mark.usefixtures("no_continuation")
def test_a_job_that_no_longer_exists_is_recorded_gone_and_stops_the_item(
    store: InMemoryRoadmapStore, staged_repo: StageRepo, api: GitHubApiFake, kube: FakeCluster
) -> None:
    number = seed_staged(store)
    _round(store, staged_repo)
    kube.custom_objects.objects[JOBS] = []

    _round(store, staged_repo)

    (comment,) = [c for c in _comments(store, number) if c.startswith(MARKER)]
    assert (
        _record(store, number)["implement.job_state"],
        _record(store, number)["implement.stopped"],
        "no longer exists" in comment,
        len(_creates(kube)),
    ) == ("gone", "job", True, 1)


def test_a_job_of_an_item_that_is_blocked_keeps_the_status_of_the_item(
    store: InMemoryRoadmapStore, staged_repo: StageRepo, api: GitHubApiFake, kube: FakeCluster
) -> None:
    number = seed_staged(store)
    _round(store, staged_repo)
    item = store.item(number)
    assert item is not None
    store.set_field(item, ItemField.STATUS, "Blocked")
    _end(kube, "Failed")

    _round(store, staged_repo)

    held = store.item(number)
    assert held is not None
    assert (held.status, _record(store, number).get("implement.stopped")) == ("Blocked", None)


def test_a_missing_cronjob_fails_the_round_naming_it_and_creates_no_job(
    store: InMemoryRoadmapStore, staged_repo: StageRepo, api: GitHubApiFake, cluster: FakeCluster
) -> None:
    seed_staged(store)

    with pytest.raises(ClusterJobError, match="CronJob devops/devops-cli-runner not found"):
        _round(store, staged_repo)

    assert (_creates(cluster), _record(store).get("implement.job")) == ([], None)


def test_the_item_records_its_job_before_the_job_is_created(
    store: InMemoryRoadmapStore,
    staged_repo: StageRepo,
    api: GitHubApiFake,
    kube: FakeCluster,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A write that fails after the create would leave a Job that no record names. If it also
    dies early, its item stays eligible and every round makes another Job (#2667)."""
    number = seed_staged(store)
    seen: list[str | None] = []
    create = kube.custom_objects.create_namespaced_custom_object

    def peek(*args: Any, **kwargs: Any) -> Any:
        seen.append(_record(store, number).get("implement.job"))
        return create(*args, **kwargs)

    monkeypatch.setattr(kube.custom_objects, "create_namespaced_custom_object", peek)

    _round(store, staged_repo)

    (job,) = _jobs(kube)
    assert (seen, _record(store, number)["implement.job"]) == (
        [job["metadata"]["name"]],
        job["metadata"]["name"],
    )


def test_the_created_runner_job_carries_the_repository_and_item_labels_and_annotations(
    store: InMemoryRoadmapStore,
    staged_repo: StageRepo,
    api: GitHubApiFake,
    kube: FakeCluster,
) -> None:
    """The runner Job and its pod carry the repository labels, stack labels, and repository
    annotations of ADR 0022 (#4558)."""
    number = seed_staged(store)

    _round(store, staged_repo)

    (job,) = _jobs(kube)
    wanted_labels = {
        "app.kubernetes.io/name": "devops-cli-job",
        "app.kubernetes.io/component": "roadmap-implement",
        "app.kubernetes.io/part-of": "devops-cli-stack",
        "app.kubernetes.io/managed-by": "devops-cli",
        "roadmap.devops-cli/owner": "example",
        "roadmap.devops-cli/repo": "roadmap",
        "roadmap.devops-cli/item": str(number),
        "implement-repo": RepoRef(STAGE_REPO).id,
    }
    wanted_annotations = {
        "roadmap.devops-cli/repository": "example/roadmap",
    }
    assert (
        job["metadata"]["name"].startswith(f"devops-cli-implement-roadmap-{number}-"),
        len(job["metadata"]["name"]) <= 63,
        wanted_labels.items() <= job["metadata"]["labels"].items(),
        wanted_labels.items() <= job["spec"]["template"]["metadata"]["labels"].items(),
        wanted_annotations.items() <= job["metadata"].get("annotations", {}).items(),
        wanted_annotations.items()
        <= job["spec"]["template"]["metadata"].get("annotations", {}).items(),
    ) == (True, True, True, True, True, True)


def test_the_item_records_the_digest_of_the_template_before_the_job_is_created(
    store: InMemoryRoadmapStore,
    staged_repo: StageRepo,
    api: GitHubApiFake,
    kube: FakeCluster,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The stop that a Job leaves is compared with this digest (#2912)."""
    number = seed_staged(store)
    _roll(kube, DIGEST_A)
    seen: list[str | None] = []
    create = kube.custom_objects.create_namespaced_custom_object

    def peek(*args: Any, **kwargs: Any) -> Any:
        seen.append(_record(store, number).get("implement.job_digest"))
        return create(*args, **kwargs)

    monkeypatch.setattr(kube.custom_objects, "create_namespaced_custom_object", peek)

    _round(store, staged_repo)

    assert (seen, _record(store, number)["implement.job_digest"]) == ([DIGEST_A], DIGEST_A)


def test_an_image_that_rolls_during_the_create_is_recorded_as_the_image_the_job_runs(
    store: InMemoryRoadmapStore,
    staged_repo: StageRepo,
    api: GitHubApiFake,
    kube: FakeCluster,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The CronJob is read one time for each create. A second read could see a newer image than
    the record names, and the stop of that Job would clear at once: a second Job on one image."""
    number = seed_staged(store)
    _roll(kube, DIGEST_A)
    read = kube.custom_objects.get_namespaced_custom_object

    def rolls_after_the_read(*args: Any, **kwargs: Any) -> Any:
        cronjob = read(*args, **kwargs)
        _roll(kube, DIGEST_B)
        return cronjob

    monkeypatch.setattr(kube.custom_objects, "get_namespaced_custom_object", rolls_after_the_read)

    _round(store, staged_repo)

    (container,) = _creates(kube)[0]["spec"]["template"]["spec"]["containers"][:1]
    assert (
        container["image"].partition("@")[2],
        _record(store, number)["implement.job_digest"],
        len(_creates(kube)),
    ) == (DIGEST_A, DIGEST_A, 1)


def test_a_template_without_a_digest_leaves_no_digest_on_the_record(
    store: InMemoryRoadmapStore, staged_repo: StageRepo, api: GitHubApiFake, kube: FakeCluster
) -> None:
    number = seed_staged(store)
    store.set_marks(_held(store, number), {ImplementRecordKey.JOB_DIGEST: DIGEST_A})
    _roll(kube, None)

    _round(store, staged_repo)

    assert (len(_creates(kube)), _record(store, number).get("implement.job_digest")) == (1, None)


def test_the_report_of_a_job_names_the_digest_of_its_image(
    store: InMemoryRoadmapStore, staged_repo: StageRepo, api: GitHubApiFake, kube: FakeCluster
) -> None:
    number = seed_staged(store)
    _roll(kube, DIGEST_A)
    _round(store, staged_repo)
    _roll(kube, DIGEST_B)
    _end(kube, "Failed")

    _round(store, staged_repo)

    (comment,) = [c for c in _comments(store, number) if "ended: failed" in c]
    assert (f"Image digest: {DIGEST_A}" in comment, DIGEST_B in comment) == (True, False)


@pytest.mark.usefixtures("no_continuation")
def test_the_report_of_a_job_that_is_gone_names_the_digest_too(
    store: InMemoryRoadmapStore, staged_repo: StageRepo, api: GitHubApiFake, kube: FakeCluster
) -> None:
    number = seed_staged(store)
    _roll(kube, DIGEST_A)
    _round(store, staged_repo)
    kube.custom_objects.objects[JOBS] = []

    _round(store, staged_repo)

    (comment,) = [c for c in _comments(store, number) if c.startswith(MARKER)]
    assert f"Image digest: {DIGEST_A}" in comment


def test_a_create_that_the_api_refuses_leaves_no_record_of_a_job(
    store: InMemoryRoadmapStore,
    staged_repo: StageRepo,
    api: GitHubApiFake,
    kube: FakeCluster,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    number = seed_staged(store)

    def refuse(*_args: Any, **_kwargs: Any) -> Any:
        raise ApiException(status=403, reason="Forbidden")

    monkeypatch.setattr(kube.custom_objects, "create_namespaced_custom_object", refuse)

    with pytest.raises(ClusterJobError, match="403"):
        _round(store, staged_repo)

    assert (_jobs(kube), _record(store, number).get("implement.job")) == ([], None)


@pytest.mark.usefixtures("no_continuation")
def test_a_log_that_cannot_be_read_still_reports_the_job_and_records_its_state(
    store: InMemoryRoadmapStore, staged_repo: StageRepo, api: GitHubApiFake, kube: FakeCluster
) -> None:
    """The API refuses a log of a pod that was evicted or never started. The round would then
    fail on this row every time and report nothing, so the report goes out without the log."""
    number = seed_staged(store)
    _round(store, staged_repo)
    name = _jobs(kube)[0]["metadata"]["name"]
    _end(kube, "Failed")
    kube.core.answers["list_namespaced_pod"] = [pod(f"{name}-x1", namespace="devops")]
    kube.core.answers["read_namespaced_pod_log"] = ApiException(status=400, reason="Bad Request")

    _round(store, staged_repo)
    _round(store, staged_repo)

    (comment,) = [c for c in _comments(store, number) if c.startswith(MARKER)]
    assert (
        _record(store, number)["implement.job_state"],
        "ended: failed." in comment,
        MESSAGES.roadmap.implement_job_report_no_log in comment,
        len(_creates(kube)),
    ) == ("failed", True, True, 1)


def test_a_pull_request_that_is_not_an_open_draft_is_left_alone(
    store: InMemoryRoadmapStore,
    staged_repo: StageRepo,
    github_api: GitHubApiFake,
    kube: FakeCluster,
) -> None:
    route_pull_status(github_api, {"state": "open", "draft": False, "merged": False}, PULL)
    seed_staged(store)

    _round(store, staged_repo)

    assert _creates(kube) == []


@pytest.mark.usefixtures("no_continuation")
def test_a_retry_comment_after_the_stop_makes_a_new_job_that_clears_the_report_of_the_old_one(
    store: InMemoryRoadmapStore, staged_repo: StageRepo, api: GitHubApiFake, kube: FakeCluster
) -> None:
    number = seed_staged(store)
    _round(store, staged_repo)
    _end(kube, "Failed")
    _round(store, staged_repo)
    first = _record(store, number)["implement.job"]
    store.as_actor("owner").comment(number, "implement: retry")

    _round(store, staged_repo)

    record = _record(store, number)
    assert (
        len(_creates(kube)),
        record["implement.job"] != first,
        record["implement.job_state"],
    ) == (
        2,
        True,
        None,
    )


def _stop_with_a_failed_job(
    store: InMemoryRoadmapStore, repo: StageRepo, kube: FakeCluster, index: int = 0
) -> None:
    """The Job at `index` ends Failed while its item is In Progress, and a round reports it."""
    number = 1
    store.set_field(_held(store, number), ItemField.STATUS, "In Progress")
    _end(kube, "Failed", index)
    _round(store, repo)


@pytest.mark.usefixtures("no_continuation")
def test_a_stop_is_blocked_with_the_digest_of_the_failed_job_and_the_same_digest_makes_no_job(
    store: InMemoryRoadmapStore, staged_repo: StageRepo, api: GitHubApiFake, kube: FakeCluster
) -> None:
    """The Service creates one Job on one digest, however many rounds run (#2912)."""
    number = seed_staged(store)
    _roll(kube, DIGEST_A)
    _round(store, staged_repo)
    _stop_with_a_failed_job(store, staged_repo, kube)

    for _ in range(10):
        _round(store, staged_repo)

    assert (
        _held(store, number).status,
        _record(store, number)["implement.stopped"],
        _record(store, number)["implement.job_digest"],
        len(_creates(kube)),
    ) == ("Blocked", "job", DIGEST_A, 1)


@pytest.mark.usefixtures("no_continuation")
def test_a_new_digest_clears_the_stop_once_and_the_item_gets_a_new_job_on_that_digest(
    store: InMemoryRoadmapStore, staged_repo: StageRepo, api: GitHubApiFake, kube: FakeCluster
) -> None:
    number = seed_staged(store)
    _roll(kube, DIGEST_A)
    _round(store, staged_repo)
    _stop_with_a_failed_job(store, staged_repo, kube)
    _roll(kube, DIGEST_B)

    _round(store, staged_repo)

    record = _record(store, number)
    comment = _comments(store, number)[-1]
    assert (
        len(_creates(kube)),
        record["implement.job_digest"],
        record["implement.job_state"],
        record.get("implement.stopped"),
        "rule `digest`" in comment,
        _held(store, number).status,
    ) == (2, DIGEST_B, None, None, True, "In Progress")


@pytest.mark.usefixtures("no_continuation")
def test_a_second_stop_on_the_new_digest_makes_no_job_in_any_number_of_rounds(
    store: InMemoryRoadmapStore, staged_repo: StageRepo, api: GitHubApiFake, kube: FakeCluster
) -> None:
    """One automatic clear for each digest: the loop of Job, stop, clear, Job does not run."""
    number = seed_staged(store)
    _roll(kube, DIGEST_A)
    _round(store, staged_repo)
    _stop_with_a_failed_job(store, staged_repo, kube)
    _roll(kube, DIGEST_B)
    _round(store, staged_repo)
    _stop_with_a_failed_job(store, staged_repo, kube, index=1)

    for _ in range(10):
        _round(store, staged_repo)

    assert (
        _held(store, number).status,
        _record(store, number)["implement.job_digest"],
        len(_creates(kube)),
    ) == ("Blocked", DIGEST_B, 2)


@pytest.mark.usefixtures("no_continuation")
def test_a_retry_of_the_owner_clears_the_stop_on_the_same_digest_and_names_the_rule(
    store: InMemoryRoadmapStore, staged_repo: StageRepo, api: GitHubApiFake, kube: FakeCluster
) -> None:
    number = seed_staged(store)
    _roll(kube, DIGEST_A)
    _round(store, staged_repo)
    _stop_with_a_failed_job(store, staged_repo, kube)
    store.as_actor("owner").comment(number, "implement: retry")

    _round(store, staged_repo)

    comments = [c for c in _comments(store, number) if "rule `" in c]
    assert (len(_creates(kube)), len(comments), "rule `retry`" in comments[0]) == (2, 1, True)


# ── A Job that ended without a result is continued (#3721) ───────────────────────────────────


def _continuation_comments(store: InMemoryRoadmapStore, number: int) -> list[str]:
    return [c for c in _comments(store, number) if "rule `continue`" in c]


def test_a_job_that_ended_without_a_result_is_continued_twice_and_then_the_item_stays_blocked(
    store: InMemoryRoadmapStore, staged_repo: StageRepo, api: GitHubApiFake, kube: FakeCluster
) -> None:
    """Each round reports the Job, clears the stop by the rule `continue` and makes the next Job,
    two times. The third stop finds no continuation left, and no round makes a fourth Job."""
    number = seed_staged(store)
    _roll(kube, DIGEST_A)
    _round(store, staged_repo)
    seen: list[tuple[int, str | None, str | None]] = []

    _stop_with_a_failed_job(store, staged_repo, kube)
    seen.append((len(_creates(kube)), _record(store, number)["implement.continuations"], None))
    first = _continuation_comments(store, number)
    _stop_with_a_failed_job(store, staged_repo, kube, index=1)
    seen.append((len(_creates(kube)), _record(store, number)["implement.continuations"], None))
    second = _continuation_comments(store, number)
    _stop_with_a_failed_job(store, staged_repo, kube, index=2)
    for _ in range(10):
        _round(store, staged_repo)

    record = _record(store, number)
    assert (
        seen,
        len(first),
        "continuation 1 of 2" in first[0],
        "No continuation is left" in first[0],
        len(second),
        "continuation 2 of 2" in second[1],
        "No continuation is left" in second[1],
        _held(store, number).status,
        record["implement.stopped"],
        record["implement.continuations"],
        record.get("implement.digest_clears"),
        len(_creates(kube)),
        len(_continuation_comments(store, number)),
    ) == (
        [(2, "1", None), (3, "2", None)],
        1,
        True,
        False,
        2,
        True,
        True,
        "Blocked",
        "job",
        "2",
        None,
        3,
        2,
    )


def test_a_continuation_runs_the_same_item_on_the_same_branch_and_keeps_the_digest_budget(
    store: InMemoryRoadmapStore, staged_repo: StageRepo, api: GitHubApiFake, kube: FakeCluster
) -> None:
    number = seed_staged(store)
    _roll(kube, DIGEST_A)
    _round(store, staged_repo)
    _roll(kube, DIGEST_B)

    _stop_with_a_failed_job(store, staged_repo, kube)

    first, second = (
        job["spec"]["template"]["spec"]["containers"][0]["args"] for job in _jobs(kube)
    )
    record = _record(store, number)
    assert (
        first == second,
        record["implement.job_digest"],
        record.get("implement.digest_clears"),
        len(_continuation_comments(store, number)),
    ) == (True, DIGEST_B, None, 1)


def test_a_job_whose_log_reads_out_of_memory_is_not_continued(
    store: InMemoryRoadmapStore, staged_repo: StageRepo, api: GitHubApiFake, kube: FakeCluster
) -> None:
    """The class `oom` has the action `raise_limit`, and a second run on the same limit ends the
    same way. The item waits for a person. Only a sign in the log shows this: the Service reads
    no pod status, so a kill with no text in the log is continued as `ci_infra`."""
    number = seed_staged(store)
    _round(store, staged_repo)
    name = _jobs(kube)[0]["metadata"]["name"]
    kube.core.answers["list_namespaced_pod"] = [pod(f"{name}-x1", namespace="devops")]
    kube.core.answers["read_namespaced_pod_log"] = (
        "Traceback (most recent call last):\nMemoryError: Cannot allocate memory\n"
    )

    _stop_with_a_failed_job(store, staged_repo, kube)
    for _ in range(3):
        _round(store, staged_repo)

    assert (
        _held(store, number).status,
        _record(store, number)["implement.failure"],
        _record(store, number).get("implement.continuations"),
        _continuation_comments(store, number),
        len(_creates(kube)),
    ) == ("Blocked", "oom", None, [], 1)


def test_a_job_that_no_longer_exists_is_continued(
    store: InMemoryRoadmapStore, staged_repo: StageRepo, api: GitHubApiFake, kube: FakeCluster
) -> None:
    number = seed_staged(store)
    _round(store, staged_repo)
    store.set_field(_held(store, number), ItemField.STATUS, "In Progress")
    kube.custom_objects.objects[JOBS] = []

    _round(store, staged_repo)

    record = _record(store, number)
    assert (
        len(_continuation_comments(store, number)),
        record["implement.continuations"],
        len(_creates(kube)),
        _held(store, number).status,
    ) == (1, "1", 2, "In Progress")


def test_a_retry_of_the_owner_after_the_last_continuation_makes_a_new_job(
    store: InMemoryRoadmapStore, staged_repo: StageRepo, api: GitHubApiFake, kube: FakeCluster
) -> None:
    number = seed_staged(store)
    _round(store, staged_repo)
    for index in range(3):
        _stop_with_a_failed_job(store, staged_repo, kube, index=index)
    blocked = (_held(store, number).status, len(_creates(kube)))
    store.as_actor("owner").comment(number, "implement: retry")

    _round(store, staged_repo)

    assert (blocked, len(_creates(kube)), "rule `retry`" in _comments(store, number)[-1]) == (
        ("Blocked", 3),
        4,
        True,
    )


def test_a_stop_that_the_runner_wrote_is_no_continuation(
    store: InMemoryRoadmapStore, staged_repo: StageRepo, api: GitHubApiFake, kube: FakeCluster
) -> None:
    """The runner wrote the step and the class of its stop. Its rules decide, not the rule
    `continue`."""
    number = seed_staged(store)
    _round(store, staged_repo)
    store.set_field(
        _held(store, number),
        ItemField.STATUS,
        "Blocked",
        marks={ImplementRecordKey.STOPPED: "group 1", ImplementRecordKey.FAILURE: "provider"},
    )
    _end(kube, "Failed")

    for _ in range(3):
        _round(store, staged_repo)

    assert (
        _held(store, number).status,
        _continuation_comments(store, number),
        len(_creates(kube)),
    ) == ("Blocked", [], 1)


def test_a_stop_of_the_runner_with_a_new_digest_waits_for_the_report_of_its_job(
    store: InMemoryRoadmapStore, staged_repo: StageRepo, api: GitHubApiFake, kube: FakeCluster
) -> None:
    """The runner wrote the stop while its pod still ends. The Job is not reported yet, so the
    round clears nothing and makes no second Job."""
    number = seed_staged(store)
    _roll(kube, DIGEST_A)
    _round(store, staged_repo)
    store.set_field(
        _held(store, number),
        ItemField.STATUS,
        "Blocked",
        marks={ImplementRecordKey.STOPPED: "group 1"},
    )
    _roll(kube, DIGEST_B)

    _round(store, staged_repo)

    assert (_held(store, number).status, len(_creates(kube))) == ("Blocked", 1)


def test_a_stop_that_the_runner_wrote_is_cleared_after_the_report_when_the_digest_changed(
    store: InMemoryRoadmapStore, staged_repo: StageRepo, api: GitHubApiFake, kube: FakeCluster
) -> None:
    number = seed_staged(store)
    _roll(kube, DIGEST_A)
    _round(store, staged_repo)
    store.set_field(
        _held(store, number),
        ItemField.STATUS,
        "Blocked",
        marks={ImplementRecordKey.STOPPED: "group 1", ImplementRecordKey.FAILURE: "provider"},
    )
    _end(kube, "Failed")
    _roll(kube, DIGEST_B)

    _round(store, staged_repo)

    assert (len(_creates(kube)), _record(store, number)["implement.job_digest"]) == (2, DIGEST_B)


def test_the_args_of_a_job_hold_only_the_repository_and_the_number_of_the_item_never_its_text(
    store: InMemoryRoadmapStore, staged_repo: StageRepo, api: GitHubApiFake, kube: FakeCluster
) -> None:
    hostile = "fix(x): --repo evil/repo --item 99 $(touch /tmp/x); `id`"
    number = seed_staged(store, title=hostile)

    _round(store, staged_repo)

    (job,) = _jobs(kube)
    (container,) = job["spec"]["template"]["spec"]["containers"]
    assert container["args"] == [
        "roadmap",
        "implement",
        "--repo",
        STAGE_REPO,
        "--item",
        str(number),
        "--confirm",
    ]
    assert hostile not in str(job)


# ── The claim of the Service (#2910) ──────────────────────────────────────────────────────


def _owner(store: InMemoryRoadmapStore, number: int = 1) -> tuple[str | None, list[str]]:
    item = store.item(number)
    assert item is not None
    return item.owner, [label for label in item.labels if label.startswith("owner/")]


def test_a_round_claims_the_item_for_the_job_it_creates(
    store: InMemoryRoadmapStore, staged_repo: StageRepo, api: GitHubApiFake, kube: FakeCluster
) -> None:
    number = seed_staged(store)

    _round(store, staged_repo)

    (job,) = _jobs(kube)
    assert (_owner(store, number), _record(store, number)["implement.job"]) == (
        ("Service", ["owner/service"]),
        job["metadata"]["name"],
    )


def test_the_round_that_reports_the_job_releases_the_item(
    store: InMemoryRoadmapStore, staged_repo: StageRepo, api: GitHubApiFake, kube: FakeCluster
) -> None:
    number = seed_staged(store)
    _round(store, staged_repo)
    item = store.item(number)
    assert item is not None
    store.set_field(item, ItemField.STATUS, "In Review")
    _end(kube, "Complete")

    _round(store, staged_repo)

    assert (_owner(store, number), _record(store, number)["implement.job_state"]) == (
        (None, []),
        "succeeded",
    )


def test_a_create_that_the_api_refuses_leaves_the_item_with_no_owner(
    store: InMemoryRoadmapStore,
    staged_repo: StageRepo,
    api: GitHubApiFake,
    kube: FakeCluster,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    number = seed_staged(store)

    def refuse(*_args: Any, **_kwargs: Any) -> Any:
        raise ApiException(status=403, reason="Forbidden")

    monkeypatch.setattr(kube.custom_objects, "create_namespaced_custom_object", refuse)

    with pytest.raises(ClusterJobError, match="403"):
        _round(store, staged_repo)

    assert (_owner(store, number), _record(store, number).get("implement.job")) == (
        (None, []),
        None,
    )


def test_a_person_who_claims_after_the_plan_gets_no_job_and_the_round_does_not_fail(
    store: InMemoryRoadmapStore,
    staged_repo: StageRepo,
    api: GitHubApiFake,
    kube: FakeCluster,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    number = seed_staged(store)
    real_plan = plan_implement

    def plan_then_claim(*args: Any, **kwargs: Any) -> Any:
        plan = real_plan(*args, **kwargs)
        store.as_actor("alice").add_label(number, "owner/human")
        return plan

    monkeypatch.setattr(
        "devops_cli.roadmap.implement.implement_submit.plan_implement", plan_then_claim
    )

    with caplog.at_level(logging.INFO, logger="devops_cli.roadmap.run"):
        outcome = _round(store, staged_repo)

    assert f"Left #{number}: an agent or a person claimed it since the plan." in caplog.messages
    assert (outcome, _creates(kube), _owner(store, number), _record(store, number)) == (
        JobOutcome(),
        [],
        ("Human", ["owner/human"]),
        {"stage.branch": "fix/1-the-job-drops-a-comment", "stage.pr": "5"},
    )


def test_a_round_creates_no_job_while_the_draft_holds_the_label_plan_needs_fix_and_logs_it_once(
    store: InMemoryRoadmapStore,
    staged_repo: StageRepo,
    api: GitHubApiFake,
    kube: FakeCluster,
    caplog: pytest.LogCaptureFixture,
) -> None:
    route_pull_status(api, NEEDS_FIX_DRAFT)
    number = seed_staged(store)

    with caplog.at_level(logging.INFO, logger="devops_cli.roadmap.run"):
        _round(store, staged_repo)
        _round(store, staged_repo)

    assert [line for line in caplog.messages if line.startswith(f"Left #{number}")] == [
        f"Left #{number}: its pull request #{PULL} holds the label `verdict/fix-plan`. "
        "The row takes the item again when the label is gone."
    ]
    assert _creates(kube) == []
    assert _record(store, number) == {
        "stage.branch": "fix/1-the-job-drops-a-comment",
        "stage.pr": "5",
        "implement.needs_fix": "5",
    }


def test_a_round_creates_the_job_once_the_label_plan_needs_fix_is_gone_and_clears_its_note(
    store: InMemoryRoadmapStore, staged_repo: StageRepo, api: GitHubApiFake, kube: FakeCluster
) -> None:
    route_pull_status(api, NEEDS_FIX_DRAFT)
    number = seed_staged(store)
    _round(store, staged_repo)
    noted = _record(store, number)["implement.needs_fix"]
    route_pull_status(api)

    _round(store, staged_repo)

    (job,) = _jobs(kube)
    record = _record(store, number)
    assert (noted, record["implement.needs_fix"]) == ("5", None)
    assert record["implement.job"] == job["metadata"]["name"]


def test_a_round_logs_the_label_plan_needs_fix_again_when_it_comes_back_after_it_was_gone(
    store: InMemoryRoadmapStore,
    staged_repo: StageRepo,
    api: GitHubApiFake,
    kube: FakeCluster,
    caplog: pytest.LogCaptureFixture,
) -> None:
    route_pull_status(api, NEEDS_FIX_DRAFT)
    number = seed_staged(store)
    _round(store, staged_repo)
    route_pull_status(api)
    store.as_actor("alice").add_label(number, "owner/human")
    _round(store, staged_repo)
    store.as_actor("alice").remove_label(number, "owner/human")
    route_pull_status(api, NEEDS_FIX_DRAFT)

    with caplog.at_level(logging.INFO, logger="devops_cli.roadmap.run"):
        _round(store, staged_repo)

    assert [line for line in caplog.messages if line.startswith(f"Left #{number}")] == [
        f"Left #{number}: its pull request #{PULL} holds the label `verdict/fix-plan`. "
        "The row takes the item again when the label is gone."
    ]
    assert _creates(kube) == []


def test_the_report_of_a_job_keeps_the_claim_of_a_person_and_stops_nothing(
    store: InMemoryRoadmapStore, staged_repo: StageRepo, api: GitHubApiFake, kube: FakeCluster
) -> None:
    """The job ended its run at a group boundary because a person claimed the item: it leaves
    the item In Progress, which is the person's now, not a stop that nobody wrote."""
    number = seed_staged(store)
    _round(store, staged_repo)
    item = store.item(number)
    assert item is not None
    store.set_field(item, ItemField.STATUS, "In Progress")
    store.as_actor("alice").add_label(number, "owner/human")
    _end(kube, "Complete")

    _round(store, staged_repo)

    held = store.item(number)
    assert held is not None
    assert (held.status, _owner(store, number), _record(store, number)) == (
        "In Progress",
        ("Human", ["owner/human"]),
        {
            **_record(store, number),
            "implement.job_state": "succeeded",
        },
    )
    assert "implement.stopped" not in _record(store, number)


def test_a_round_that_creates_a_job_for_a_medium_effort_item_logs_the_fallback_pass(
    store: InMemoryRoadmapStore,
    staged_repo: StageRepo,
    api: GitHubApiFake,
    kube: FakeCluster,
    caplog: pytest.LogCaptureFixture,
) -> None:
    number = seed_staged(store, labels=("type/bug", "effort/medium"))

    with caplog.at_level(logging.INFO, logger="devops_cli.roadmap.run"):
        _round(store, staged_repo)

    assert (len(_creates(kube)), _record(store, number)["implement.job"] is not None) == (1, True)
    assert "The round selected an item in effort pass medium." in caplog.messages
    assert "The round uses the fallback pass." in caplog.messages


def test_job_reporting_emits_pipeline_outcome_metrics_and_repair_rounds_and_tokens(
    store: InMemoryRoadmapStore, staged_repo: StageRepo, api: GitHubApiFake, kube: FakeCluster
) -> None:
    number = seed_staged(store, title="fix(roadmap): test outcome metrics")
    _round(store, staged_repo)

    item = store.item(number)
    assert item is not None
    store.set_marks(
        item,
        {
            ImplementRecordKey.REPAIR_ROUNDS: 3,
            ImplementRecordKey.SPEND: '{"input_tokens": 1200, "output_tokens": 300}',
            ImplementRecordKey.RESULT: ImplementResult.DRAFTED.value,
        },
    )
    _end(kube, "Complete")

    before_jobs = _implement_jobs("fix", "succeeded")
    before_repairs = _repair_rounds_count("fix")
    before_tokens = _tokens_count("fix")

    _round(store, staged_repo)

    assert _implement_jobs("fix", "succeeded") - before_jobs == 1
    assert _repair_rounds_count("fix") - before_repairs == 3
    assert _tokens_count("fix") - before_tokens == 1500


def test_a_stop_that_the_runner_wrote_and_exited_zero_counts_once_as_a_failed_attempt(
    store: InMemoryRoadmapStore, staged_repo: StageRepo, api: GitHubApiFake, kube: FakeCluster
) -> None:
    """The runner writes its stop and exits 0, so the Job controller marks the Job Complete. The
    attempt failed: the jobs counter counts it as `failed`, and the failures counter counts its
    class, both with the repository of the round (#4703)."""
    number = seed_staged(store)
    _round(store, staged_repo)
    store.set_field(
        _held(store, number),
        ItemField.STATUS,
        "Blocked",
        marks={ImplementRecordKey.STOPPED: "group 2", ImplementRecordKey.FAILURE: "parser"},
    )
    _end(kube, "Complete")
    before = (_implement_jobs("fix", "failed"), _implement_jobs("fix", "succeeded"))
    before_failures = _failures("parser")

    _round(store, staged_repo)
    _round(store, staged_repo)

    assert (
        _implement_jobs("fix", "failed") - before[0],
        _implement_jobs("fix", "succeeded") - before[1],
        _failures("parser") - before_failures,
    ) == (1, 0, 1)


def test_the_job_of_an_item_that_closed_before_the_report_counts_once_and_stops_nothing(
    store: InMemoryRoadmapStore, staged_repo: StageRepo, api: GitHubApiFake, kube: FakeCluster
) -> None:
    """The pull request of the Job merges before the next round, so the item is closed when the
    round reads it. The cluster still holds the Job: the round reports it once (#4703)."""
    number = seed_staged(store)
    _round(store, staged_repo)
    store.close(number, CloseReason.COMPLETED)
    _end(kube, "Complete")
    before = _implement_jobs("fix", "succeeded")

    _round(store, staged_repo)
    _round(store, staged_repo)

    assert (
        _implement_jobs("fix", "succeeded") - before,
        _record(store, number)["implement.job_state"],
        _record(store, number).get("implement.stopped"),
    ) == (1, "succeeded", None)


def test_a_closed_item_whose_job_the_cluster_no_longer_holds_is_not_reported(
    store: InMemoryRoadmapStore, staged_repo: StageRepo, api: GitHubApiFake, kube: FakeCluster
) -> None:
    """A closed item of an earlier version can name a Job that is gone. The round does not report
    it, so a deploy does not count old Jobs again (#4703)."""
    number = seed_staged(store)
    _round(store, staged_repo)
    store.close(number, CloseReason.COMPLETED)
    kube.custom_objects.objects[JOBS] = []
    before = _implement_jobs("fix", "gone")

    _round(store, staged_repo)

    assert (
        _implement_jobs("fix", "gone") - before,
        _record(store, number)["implement.job_state"],
    ) == (
        0,
        None,
    )


def test_a_round_with_no_repository_is_refused_before_any_request(
    store: InMemoryRoadmapStore, staged_repo: StageRepo, kube: FakeCluster
) -> None:
    """An empty `repo` label makes a series that no rule of a repository reads (#4703)."""
    with pytest.raises(RoadmapImplementError) as raised:
        run_implement_round(store, repo="", source=staged_repo.clone)

    assert str(raised.value) == MESSAGES.roadmap.implement_round_no_repo

    assert kube.custom_objects.calls == []


def _spend_of(tokens: int) -> str:
    """The spend that the record holds after a Job: the SUM of the spend of all Jobs (#4070)."""
    return json.dumps({"input_tokens": tokens - tokens // 5, "output_tokens": tokens // 5})


def test_two_jobs_of_one_item_count_each_token_once(
    store: InMemoryRoadmapStore, staged_repo: StageRepo, api: GitHubApiFake, kube: FakeCluster
) -> None:
    """The record carries the spend of all Jobs, so the second report adds only the tokens that
    the second Job spent (#4200)."""
    number = seed_staged(store, title="fix(roadmap): count the tokens once")
    _roll(kube, DIGEST_A)
    _round(store, staged_repo)
    before = _tokens_count("fix")

    store.set_marks(_held(store, number), {ImplementRecordKey.SPEND: _spend_of(1500)})
    _stop_with_a_failed_job(store, staged_repo, kube)
    first = (_tokens_count("fix") - before, _record(store, number).get("implement.spend_counted"))
    store.set_marks(_held(store, number), {ImplementRecordKey.SPEND: _spend_of(4000)})
    _stop_with_a_failed_job(store, staged_repo, kube, index=1)
    second = (_tokens_count("fix") - before, _record(store, number).get("implement.spend_counted"))

    assert (first, second) == ((1500, "1500"), (4000, "4000"))


def test_a_spend_below_the_counted_spend_is_counted_whole_and_becomes_the_counted_spend(
    store: InMemoryRoadmapStore, staged_repo: StageRepo, api: GitHubApiFake, kube: FakeCluster
) -> None:
    """A spend that fell below the count means the record started again: the whole spend counts
    once, and the count follows it, so no later report goes negative (#4200)."""
    number = seed_staged(store, title="fix(roadmap): count the tokens once")
    _round(store, staged_repo)
    store.set_marks(
        _held(store, number),
        {ImplementRecordKey.SPEND: _spend_of(900), ImplementRecordKey.SPEND_COUNTED: "1500"},
    )
    before = _tokens_count("fix")
    _end(kube, "Complete")

    _round(store, staged_repo)

    assert (
        _tokens_count("fix") - before,
        _record(store, number).get("implement.spend_counted"),
    ) == (
        900,
        "900",
    )


def test_a_record_of_an_older_version_counts_its_whole_spend_once(
    store: InMemoryRoadmapStore, staged_repo: StageRepo, api: GitHubApiFake, kube: FakeCluster
) -> None:
    """A record with `implement.spend` and no `implement.spend_counted` has counted nothing yet
    (#4200)."""
    number = seed_staged(store, title="fix(roadmap): count the tokens once")
    _round(store, staged_repo)
    store.set_marks(_held(store, number), {ImplementRecordKey.SPEND: _spend_of(1500)})
    assert "implement.spend_counted" not in _record(store, number)
    before = _tokens_count("fix")
    _end(kube, "Complete")

    _round(store, staged_repo)

    assert (
        _tokens_count("fix") - before,
        _record(store, number).get("implement.spend_counted"),
    ) == (
        1500,
        "1500",
    )


def test_a_report_without_new_spend_counts_no_tokens(
    store: InMemoryRoadmapStore, staged_repo: StageRepo, api: GitHubApiFake, kube: FakeCluster
) -> None:
    """A Job that spent nothing (its pod died at the start) adds no tokens, however much the
    earlier Jobs spent (#4200)."""
    number = seed_staged(store, title="fix(roadmap): count the tokens once")
    _roll(kube, DIGEST_A)
    _round(store, staged_repo)
    store.set_marks(
        _held(store, number),
        {ImplementRecordKey.SPEND: _spend_of(1500), ImplementRecordKey.SPEND_COUNTED: "1500"},
    )
    before = _tokens_count("fix")

    _stop_with_a_failed_job(store, staged_repo, kube)

    assert (
        _tokens_count("fix") - before,
        _record(store, number).get("implement.spend_counted"),
    ) == (
        0,
        "1500",
    )


def test_job_reporting_handles_invalid_or_zero_repair_rounds_and_spend(
    store: InMemoryRoadmapStore, staged_repo: StageRepo, api: GitHubApiFake, kube: FakeCluster
) -> None:
    number = seed_staged(store, title="fix(roadmap): invalid values")
    _round(store, staged_repo)

    item = store.item(number)
    assert item is not None
    store.set_marks(
        item,
        {
            ImplementRecordKey.REPAIR_ROUNDS: "invalid",
            ImplementRecordKey.SPEND: "{invalid json",
        },
    )
    _end(kube, "Complete")
    before_repairs = _repair_rounds_count("fix")
    before_tokens = _tokens_count("fix")
    _round(store, staged_repo)

    assert _repair_rounds_count("fix") - before_repairs == 0
    assert _tokens_count("fix") - before_tokens == 0


def test_job_reporting_updates_and_resets_consecutive_failures_gauge(
    store: InMemoryRoadmapStore, staged_repo: StageRepo, api: GitHubApiFake, kube: FakeCluster
) -> None:
    # First item fails with "parser"
    n1 = seed_staged(store)
    _round(store, staged_repo)
    store.set_field(
        _held(store, n1),
        ItemField.STATUS,
        "Blocked",
        marks={ImplementRecordKey.STOPPED: "group 1", ImplementRecordKey.FAILURE: "parser"},
    )
    _end(kube, "Failed")
    _round(store, staged_repo)
    assert _consecutive_failures_count("parser") == 1

    # Second item succeeds and resets "parser" to 0
    push_staged_branch(staged_repo, number=2)
    seed_staged(store, pull=SECOND_PULL)
    _round(store, staged_repo)
    _end(kube, "Complete", index=1)
    _round(store, staged_repo)
    assert _consecutive_failures_count("parser") == 0


def test_each_ended_job_logs_one_attempt_line_with_its_counts_and_digest(
    store: InMemoryRoadmapStore,
    staged_repo: StageRepo,
    api: GitHubApiFake,
    kube: FakeCluster,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The line holds counts, the state, the class and the runner digest, and no log text
    (#4535)."""
    number = seed_staged(store)
    _roll(kube, DIGEST_A)
    _round(store, staged_repo)
    name = _jobs(kube)[0]["metadata"]["name"]
    store.set_field(_held(store, number), ItemField.STATUS, "In Progress")
    _end(kube, "Failed")
    kube.core.answers["list_namespaced_pod"] = [pod(f"{name}-x1", namespace="devops")]
    kube.core.answers["read_namespaced_pod_log"] = "MemoryError: Cannot allocate memory\n"

    with caplog.at_level(logging.INFO):
        _round(store, staged_repo)

    lines = [
        r.getMessage() for r in caplog.records if r.getMessage().startswith("implement attempt")
    ]
    assert [line.rsplit(" version=", 1)[0] for line in lines] == [
        f"implement attempt: repo={STAGE_REPO} item=#{number} state=failed class=oom "
        f"repair_rounds=0 tokens=0 digest={DIGEST_A}"
    ]


_PARALLEL_TASKS_ONE = """\
# Tasks

## 1. Group 1

Reads: `CONTEXT.md`. Changes: `src/devops_cli/foo.py` (new), `tests/test_foo.py` (new).

- [ ] 1.1 Add `src/devops_cli/foo.py`
  - Verification: `$ uv run devops ci test tests/test_foo.py`

## Criteria

- Group 1: The job keeps every comment.
"""

_PARALLEL_TASKS_TWO = """\
# Tasks

## 1. Group 1

Reads: `CONTEXT.md`. Changes: `src/devops_cli/bar.py` (new), `tests/test_bar.py` (new).

- [ ] 1.1 Add `src/devops_cli/bar.py`
  - Verification: `$ uv run devops ci test tests/test_bar.py`

## Criteria

- Group 1: The job keeps every comment.
"""

_PARALLEL_TASKS_SHARED_PATH = """\
# Tasks

## 1. Group 1

Reads: `CONTEXT.md`. Changes: `src/devops_cli/foo.py` (new), `tests/test_foo.py` (new).

- [ ] 1.1 Add `src/devops_cli/foo.py`
  - Verification: `$ uv run devops ci test tests/test_foo.py`

## Criteria

- Group 1: The job keeps every comment.
"""

_PARALLEL_TASKS_CAP_ONE = """\
# Tasks

## 1. Group 1

Reads: `CONTEXT.md`. Changes: `src/devops_cli/foo.py` (new), `tests/test_foo.py` (new), `specs/shared-cap/spec.md` (new).

- [ ] 1.1 Add `src/devops_cli/foo.py`
  - Verification: `$ uv run devops ci test tests/test_foo.py`

## Criteria

- Group 1: The job keeps every comment.
"""

_PARALLEL_TASKS_CAP_TWO = """\
# Tasks

## 1. Group 1

Reads: `CONTEXT.md`. Changes: `src/devops_cli/bar.py` (new), `tests/test_bar.py` (new), `specs/shared-cap/spec.md` (new).

- [ ] 1.1 Add `src/devops_cli/bar.py`
  - Verification: `$ uv run devops ci test tests/test_bar.py`

## Criteria

- Group 1: The job keeps every comment.
"""


def test_two_disjoint_items_of_one_repository_get_two_jobs(
    store: InMemoryRoadmapStore,
    stage_repo: StageRepo,
    api: GitHubApiFake,
    kube: FakeCluster,
    config: Callable[..., Path],
) -> None:
    config(roadmap={"implement": {"max_parallel_jobs": 2}})
    push_staged_branch(stage_repo, number=1, tasks=_PARALLEL_TASKS_ONE)
    push_staged_branch(stage_repo, number=2, tasks=_PARALLEL_TASKS_TWO)
    n1 = seed_staged(store)
    n2 = seed_staged(store, pull=SECOND_PULL)

    _round(store, stage_repo)

    jobs = _jobs(kube)
    assert len(jobs) == 2
    item_labels = {job["metadata"]["labels"].get(ITEM_LABEL) for job in jobs}
    assert item_labels == {str(n1), str(n2)}


def test_two_items_that_share_a_path_get_one_job(
    store: InMemoryRoadmapStore,
    stage_repo: StageRepo,
    api: GitHubApiFake,
    kube: FakeCluster,
    config: Callable[..., Path],
) -> None:
    config(roadmap={"implement": {"max_parallel_jobs": 2}})
    push_staged_branch(stage_repo, number=1, tasks=_PARALLEL_TASKS_ONE)
    push_staged_branch(stage_repo, number=2, tasks=_PARALLEL_TASKS_SHARED_PATH)
    n1 = seed_staged(store)
    seed_staged(store, pull=SECOND_PULL)

    _round(store, stage_repo)

    jobs = _jobs(kube)
    assert len(jobs) == 1
    assert jobs[0]["metadata"]["labels"].get(ITEM_LABEL) == str(n1)


def test_two_items_that_share_a_capability_spec_get_one_job(
    store: InMemoryRoadmapStore,
    stage_repo: StageRepo,
    api: GitHubApiFake,
    kube: FakeCluster,
    config: Callable[..., Path],
) -> None:
    config(roadmap={"implement": {"max_parallel_jobs": 2}})
    push_staged_branch(stage_repo, number=1, tasks=_PARALLEL_TASKS_CAP_ONE)
    push_staged_branch(stage_repo, number=2, tasks=_PARALLEL_TASKS_CAP_TWO)
    n1 = seed_staged(store)
    seed_staged(store, pull=SECOND_PULL)

    _round(store, stage_repo)

    jobs = _jobs(kube)
    assert len(jobs) == 1
    assert jobs[0]["metadata"]["labels"].get(ITEM_LABEL) == str(n1)


def test_running_job_does_not_starve_available_slot(
    store: InMemoryRoadmapStore,
    stage_repo: StageRepo,
    api: GitHubApiFake,
    kube: FakeCluster,
    config: Callable[..., Path],
) -> None:
    config(roadmap={"implement": {"max_parallel_jobs": 1}})
    push_staged_branch(stage_repo, number=1, tasks=_PARALLEL_TASKS_ONE)
    push_staged_branch(stage_repo, number=2, tasks=_PARALLEL_TASKS_TWO)
    n1 = seed_staged(store)
    n2 = seed_staged(store, pull=SECOND_PULL)

    _round(store, stage_repo)
    assert len(_jobs(kube)) == 1
    job1 = _jobs(kube)[0]
    job1["status"] = {"startTime": "2026-11-22T20:00:00Z", "active": 1}

    config(roadmap={"implement": {"max_parallel_jobs": 2}})
    _round(store, stage_repo)
    jobs = _jobs(kube)
    assert len(jobs) == 2
    item_labels = {job["metadata"]["labels"].get(ITEM_LABEL) for job in jobs}
    assert item_labels == {str(n1), str(n2)}


def test_pending_runner_pod_blocks_new_jobs(
    store: InMemoryRoadmapStore,
    stage_repo: StageRepo,
    api: GitHubApiFake,
    kube: FakeCluster,
    config: Callable[..., Path],
) -> None:
    config(roadmap={"implement": {"max_parallel_jobs": 1}})
    push_staged_branch(stage_repo, number=1, tasks=_PARALLEL_TASKS_ONE)
    push_staged_branch(stage_repo, number=2, tasks=_PARALLEL_TASKS_TWO)
    seed_staged(store)
    seed_staged(store, pull=SECOND_PULL)

    _round(store, stage_repo)
    assert len(_jobs(kube)) == 1
    job1 = _jobs(kube)[0]
    job1["status"] = {"active": 1}

    config(roadmap={"implement": {"max_parallel_jobs": 2}})
    _round(store, stage_repo)
    assert len(_jobs(kube)) == 1


def test_request_budget_and_model_lane_limits_hold(monkeypatch: pytest.MonkeyPatch) -> None:
    from unittest.mock import MagicMock

    from devops_cli.roadmap.implement import implement_run
    from devops_cli.roadmap.implement.implement_run import _ItemRun

    calls: list[str] = []
    monkeypatch.setattr(implement_run, "set_model_call_limit", lambda n: calls.append(f"limit:{n}"))
    monkeypatch.setattr(
        implement_run, "reset_model_call_limit", lambda: calls.append("reset_limit")
    )
    monkeypatch.setattr(
        implement_run, "install_request_budget", lambda limit: calls.append(f"budget:{limit}")
    )
    monkeypatch.setattr(
        implement_run, "set_request_gate", lambda gate: calls.append(f"gate:{gate}")
    )

    run = MagicMock(spec=_ItemRun)
    run.returned = None
    _ItemRun.execute(run)

    assert "limit:1" in calls
    assert any(c.startswith("budget:") for c in calls)
    assert "reset_limit" in calls
    assert "gate:None" in calls

    run_err = MagicMock(spec=_ItemRun)
    run_err._start.side_effect = RuntimeError("boom")
    with pytest.raises(RuntimeError, match="boom"):
        _ItemRun.execute(run_err)
    assert calls[-2:] == ["reset_limit", "gate:None"]


def test_claimed_item_sets_left_and_creates_no_job(
    store: InMemoryRoadmapStore,
    stage_repo: StageRepo,
    api: GitHubApiFake,
    kube: FakeCluster,
    config: Callable[..., Path],
) -> None:
    config(roadmap={"implement": {"max_parallel_jobs": 2}})
    push_staged_branch(stage_repo, number=1, tasks=_PARALLEL_TASKS_ONE)
    n1 = seed_staged(store)
    item1 = store.item(n1)
    assert item1 is not None
    store.set_field(item1, ItemField.OWNER, "Human")
    _round(store, stage_repo)
    assert len(_jobs(kube)) == 0


def test_running_job_without_digit_label_is_ignored(
    store: InMemoryRoadmapStore,
    stage_repo: StageRepo,
    api: GitHubApiFake,
    kube: FakeCluster,
    config: Callable[..., Path],
) -> None:
    config(roadmap={"implement": {"max_parallel_jobs": 2}})
    push_staged_branch(stage_repo, number=1, tasks=_PARALLEL_TASKS_ONE)
    n1 = seed_staged(store)
    _round(store, stage_repo)
    job1 = _jobs(kube)[0]
    job1["status"] = {"startTime": "2026-11-22T20:00:00Z", "active": 1}
    job1["metadata"]["labels"][ITEM_LABEL] = "not-a-digit"

    _round(store, stage_repo)
    jobs = _jobs(kube)
    assert len(jobs) == 2
    assert jobs[1]["metadata"]["labels"].get(ITEM_LABEL) == str(n1)


def test_target_change_files_error_returns_frozenset(monkeypatch: pytest.MonkeyPatch) -> None:
    from unittest.mock import MagicMock

    from devops_cli.exceptions.git import GitOperationError
    from devops_cli.roadmap.implement import implement_submit
    from devops_cli.roadmap.planned import PlannedChanges

    monkeypatch.setattr(
        implement_submit,
        "tree_files",
        MagicMock(side_effect=GitOperationError("err", operation="test")),
    )
    target = MagicMock()
    target.planned = False
    target.branch = "feat/1-foo"
    target.item.number = 1
    planned = MagicMock(spec=PlannedChanges)
    res = implement_submit._target_change_files(Path("."), planned, target)
    assert res == frozenset()


def test_collect_running_change_sets_error_returns_frozenset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from unittest.mock import MagicMock

    from devops_cli.exceptions.git import GitOperationError
    from devops_cli.k8s.cluster_job_api import ClusterJob
    from devops_cli.roadmap.implement import implement_submit
    from devops_cli.roadmap.planned import PlannedChanges

    job = MagicMock(spec=ClusterJob)
    job.labels = {ITEM_LABEL: "1"}
    monkeypatch.setattr(
        implement_submit,
        "tree_files",
        MagicMock(side_effect=GitOperationError("err", operation="test")),
    )
    store = MagicMock()
    store.item.return_value = None
    planned = MagicMock(spec=PlannedChanges)
    planned.default = "main"
    items, sets = implement_submit._collect_running_change_sets([job], store, planned, Path("."))
    assert items == {1}
    assert sets == [frozenset()]


def test_change_folder_for_target_unplanned() -> None:
    from unittest.mock import MagicMock

    from devops_cli.roadmap.implement import implement_submit
    from devops_cli.roadmap.planned import PlannedChanges

    target = MagicMock()
    target.planned = False
    target.branch = "feat/1-foo"
    target.item.number = 1
    planned = MagicMock(spec=PlannedChanges)
    folder = implement_submit._change_folder_for_target(Path("/root"), planned, target)
    assert folder == Path("/root/openspec/changes/1-foo")


def test_two_groups_of_an_item_share_one_conversation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Two groups of one item run through `_groups` pass one `StepConversation` so the second
    `run_step` gets the conversation that the first one left (#6527)."""
    from pydantic_ai.conversation import Conversation

    from devops_cli.roadmap.implement import implement_run
    from devops_cli.roadmap.implement.implement import ImplementTarget
    from devops_cli.roadmap.implement.implement_step import StepOutcome, StepStatus
    from devops_cli.roadmap.project_profile import ProjectProfile
    from devops_cli.roadmap.toolchains import DEVOPS_CLI_PRESET

    store = InMemoryRoadmapStore(repo=STAGE_REPO)
    number = seed_staged(store)
    item = store.item(number)
    assert item is not None
    change = tmp_path / "openspec" / "changes" / f"{number}-shared-conv"
    change.mkdir(parents=True)
    tasks_path = change / "tasks.md"
    tasks_path.write_text(TASKS, encoding="utf-8")

    sentinel = Conversation()
    seen: list[tuple[int, Any, Any]] = []

    def fake_run_step(store_arg: Any, *, item: int, group: int, **kwargs: Any) -> StepOutcome:
        conv = kwargs.get("conversation")
        seen.append((group, conv, None if conv is None else conv.current))
        if group == 1:
            tasks_path.write_text(TASKS.replace("- [ ] 1.1", "- [x] 1.1"), encoding="utf-8")
            if conv is not None:
                conv.current = sentinel
        else:
            tasks_path.write_text(
                TASKS.replace("- [ ] 1.1", "- [x] 1.1").replace("- [ ] 2.1", "- [x] 2.1"),
                encoding="utf-8",
            )
        return StepOutcome(item=item, group=group, title=f"group {group}", status=StepStatus.DONE)

    monkeypatch.setattr(implement_run, "run_step", fake_run_step)
    run = implement_run._ItemRun(
        store=store,
        repo=STAGE_REPO,
        path=tmp_path,
        target=ImplementTarget(item=item, branch="feat/1-shared", pull=PULL, retry=False),
        model=object(),
        window=128_000,
        default="main",
    )
    run._profile = ProjectProfile(preset=DEVOPS_CLI_PRESET)
    monkeypatch.setattr(run, "_hooks_config", lambda: None)
    monkeypatch.setattr(run, "_recorded_tests", frozenset)
    monkeypatch.setattr(run, "_check_premise", lambda _tasks: False)

    run._groups()

    assert [group for group, _, _ in seen] == [1, 2]
    assert seen[0][1] is not None
    assert seen[1][1] is seen[0][1]
    assert seen[1][2] is sentinel


def test_report_reads_live_issue_when_brain_cache_holds_stale_in_progress(
    process_fake: Any,
    built: FakeCluster,
    shared_valkey: Any,
    valkey_server: Any,
) -> None:
    """`_report` bypasses a fresh stale `brain-issue` cache entry when a runner Job published
    `status/in-review` and `implement.result="drafted"` without Valkey access (#7063)."""
    from datetime import UTC, datetime

    from devops_cli.k8s.cluster_job_api import ClusterJob, ClusterJobs, JobState
    from devops_cli.roadmap.implement import implement_submit
    from devops_cli.roadmap.stores.brain_issues import CachedIssue, remember_issue
    from devops_cli.roadmap.stores.github_store import GitHubRoadmapStore
    from devops_cli.roadmap.stores.store import (
        IssueRecord,
        encode_job_record,
        select_items,
        split_record,
        with_record,
    )
    from tests.support.fakes.github import RunnerSession
    from tests.support.fakes.github_repository import GitHubFake

    now = datetime.now(UTC)
    github = GitHubFake(STAGE_REPO)
    live_body = with_record(
        "Implement feature",
        encode_job_record(
            {},
            {
                ImplementRecordKey.JOB: "runner-job-1",
                ImplementRecordKey.RESULT: "drafted",
            },
        ),
    )
    github.seed_issue(
        1,
        "Track fix",
        body=live_body,
        labels=("priority/p1-high", "status/in-review", "owner/service"),
        updated_at=now,
    )
    github.install(process_fake)
    store = GitHubRoadmapStore(STAGE_REPO, runner=github, session=RunnerSession(github))

    stale_record = IssueRecord(
        number=1,
        title="Track fix",
        url=f"https://github.com/{STAGE_REPO}/issues/1",
        body="Implement feature",
        labels=("priority/p1-high", "status/in-progress", "owner/service"),
        updated_at=now,
        job_record={ImplementRecordKey.JOB.value: "runner-job-1"},
    )
    remember_issue(
        STAGE_REPO,
        CachedIssue(record=stale_record, etag='W/"1"', checked_at=now),
        private=False,
    )
    stale_item = select_items([stale_record])[0]

    implement_submit._report(
        store,
        ClusterJobs(),
        STAGE_REPO,
        stale_item,
        "runner-job-1",
        ClusterJob(name="runner-job-1", state=JobState.SUCCEEDED),
    )

    live_labels = {lbl["name"] for lbl in github.issues[1]["labels"]}
    _, live_marks = split_record(github.issues[1]["body"], issue="#1")
    assert github.comments.get(1, []) == []
    assert "status/in-review" in live_labels
    assert "status/blocked" not in live_labels
    assert "owner/service" not in live_labels
    assert live_marks.get(ImplementRecordKey.JOB_STATE.value) == "succeeded"
    assert ImplementRecordKey.STOPPED.value not in live_marks
    assert ImplementRecordKey.FAILURE.value not in live_marks


def test_report_skips_stop_write_when_service_release_sees_non_stop_status(
    built: FakeCluster, monkeypatch: pytest.MonkeyPatch
) -> None:
    """If the runner updates the issue to `In Review` after the initial read and before
    `write_status`, `_report` re-checks `_settles_as_stop` and keeps `In Review` (#7063)."""
    from devops_cli.k8s.cluster_job_api import ClusterJob, ClusterJobs, JobState
    from devops_cli.roadmap.implement import implement_submit

    store = InMemoryRoadmapStore(repo=STAGE_REPO)
    number = seed_staged(store, status="In Progress")
    held = _held(store, number)
    store.label_issue(number, "owner/service")
    store.set_marks(held, {ImplementRecordKey.JOB: "runner-job-1"})
    held = _held(store, number)

    original_set_field = store.set_field

    def race_on_release(item_arg: Any, field: Any, value: Any, **kwargs: Any) -> Any:
        result = original_set_field(item_arg, field, value, **kwargs)
        if field is ItemField.OWNER:
            live = _held(store, number)
            original_set_field(live, ItemField.STATUS, "In Review")
            store.set_marks(_held(store, number), {ImplementRecordKey.RESULT: "drafted"})
        return result

    monkeypatch.setattr(store, "set_field", race_on_release)

    implement_submit._report(
        store,
        ClusterJobs(),
        STAGE_REPO,
        held,
        "runner-job-1",
        ClusterJob(name="runner-job-1", state=JobState.SUCCEEDED),
    )

    final_item = _held(store, number)
    assert final_item.status == "In Review"
    assert final_item.job_record.get(ImplementRecordKey.STOPPED.value) is None
    assert final_item.job_record.get(ImplementRecordKey.FAILURE.value) is None
