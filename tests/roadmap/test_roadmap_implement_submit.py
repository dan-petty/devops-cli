"""The `implement` row of the Service's status lane: a round creates one runner Job for a Staged
item, creates no second one while a Job of the repository runs, and reports a Job that ended
(#2667).

Git runs for real on a clone with an `origin`, GitHub and the Kubernetes API are faked at their
edges, and the CronJob template is the committed manifest `k8s/devops/cronjob-runner.yaml`.
"""

from __future__ import annotations

import copy
import logging
from datetime import timedelta
from typing import Any

import pytest
import yaml
from kubernetes.client.rest import ApiException

from devops_cli.config.env import setting_variables
from devops_cli.exceptions.k8s import ClusterJobError
from devops_cli.lang import MESSAGES
from devops_cli.roadmap.implement import parse_implement_filters, plan_implement
from devops_cli.roadmap.memory_store import InMemoryRoadmapStore
from devops_cli.roadmap.run import MODEL_LANE_ROWS, STATUS_LANE_ROWS, JobOutcome
from devops_cli.roadmap.store import ImplementRecordKey, Item, ItemField
from tests.support.fakes.github import GitHubApiFake
from tests.support.fakes.kubernetes import FakeCluster, pod
from tests.support.paths import REPO_ROOT
from tests.support.roadmap_implement import (
    PULL,
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
    document = yaml.safe_load((REPO_ROOT / "k8s/devops/cronjob-runner.yaml").read_text("utf-8"))
    assert isinstance(document, dict)
    return document


@pytest.fixture
def kube(cluster: FakeCluster, template: dict[str, Any]) -> FakeCluster:
    cluster.custom_objects.objects[CRONJOBS] = [copy.deepcopy(template)]
    return cluster


def _round(store: InMemoryRoadmapStore, repo: StageRepo) -> JobOutcome:
    """One round of the row, as the Service runs it in its model clone."""
    return IMPLEMENT_ROW.runner(store=store, repo=STAGE_REPO, clone_path=repo.clone)


def _jobs(kube: FakeCluster) -> list[dict[str, Any]]:
    return kube.custom_objects.objects.get(JOBS, [])


def _creates(kube: FakeCluster) -> list[dict[str, Any]]:
    return [
        call[1]["body"]
        for call in kube.custom_objects.calls
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


def _end(kube: FakeCluster, condition: str, index: int = 0) -> None:
    """The Job controller marks Job `index` Complete or Failed."""
    _jobs(kube)[index]["status"] = {
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
        "implement" in [row.name for row in MODEL_LANE_ROWS],
        IMPLEMENT_ROW.needs_clone,
        IMPLEMENT_ROW.first_run_due,
        IMPLEMENT_ROW.interval,
    ) == (["metrics", "implement", "stage_ready"], False, True, True, timedelta(minutes=7))


def test_a_round_creates_one_job_for_a_staged_item_with_its_args_and_a_token_for_its_repository(
    store: InMemoryRoadmapStore, staged_repo: StageRepo, api: GitHubApiFake, kube: FakeCluster
) -> None:
    number = seed_staged(store)

    outcome = _round(store, staged_repo)

    (job,) = _jobs(kube)
    (container,) = job["spec"]["template"]["spec"]["containers"]
    env = {entry["name"]: entry["value"] for entry in container["env"]}
    record = _record(store, number)
    assert (
        outcome,
        container["name"],
        container["args"],
        env[setting_variables()["service.github_app.token_repository"]],
        env["DEVOPS_CLI_ROADMAP_IMPLEMENT_IN_RUNNER"],
        job["metadata"]["name"].startswith("devops-cli-runner-"),
        record["implement.job"] == job["metadata"]["name"],
        "implement.job_state" in record and record["implement.job_state"] is not None,
    ) == (
        JobOutcome(),
        "runner",
        ["roadmap", "implement", "--repo", STAGE_REPO, "--item", str(number), "--confirm"],
        STAGE_REPO,
        "true",
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

    monkeypatch.setattr("devops_cli.roadmap.implement_submit.plan_implement", plan_then_start)

    _round(store, staged_repo)

    assert (_creates(kube), _owner(store, number), _record(store, number).get("implement.job")) == (
        [],
        (None, []),
        None,
    )


def test_a_job_that_succeeded_is_reported_on_its_item_with_the_tail_of_its_log(
    store: InMemoryRoadmapStore, staged_repo: StageRepo, api: GitHubApiFake, kube: FakeCluster
) -> None:
    number = seed_staged(store)
    _round(store, staged_repo)
    name = _jobs(kube)[0]["metadata"]["name"]
    item = store.item(number)
    assert item is not None
    store.set_field(item, ItemField.STATUS, "In Review")
    _end(kube, "Complete")
    kube.core.answers["list_namespaced_pod"] = [pod(f"{name}-x1", namespace="devops")]
    kube.core.answers["read_namespaced_pod_log"] = f"Took 1 item(s).\nauthorization: {A_TOKEN}\n"

    _round(store, staged_repo)

    (comment,) = [c for c in _comments(store, number) if c.startswith(MARKER)]
    held = store.item(number)
    assert held is not None
    assert (
        held.status,
        _record(store, number)["implement.job_state"],
        _record(store, number).get("implement.stopped"),
        f"The runner Job {name} ended: succeeded." in comment,
        "    Took 1 item(s)." in comment,
        A_TOKEN in comment,
        len(_creates(kube)),
    ) == ("In Review", "succeeded", None, True, True, False, 1)
    log_call = next(c for c in kube.core.calls if c[0] == "read_namespaced_pod_log")
    pod_call = next(c for c in kube.core.calls if c[0] == "list_namespaced_pod")
    assert (log_call[1]["name"], log_call[1]["tail_lines"], pod_call[1]["label_selector"]) == (
        f"{name}-x1",
        40,
        f"batch.kubernetes.io/job-name={name}",
    )


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
    ) == ("Ready", "failed", "job", True, True, 1)


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
        "Ready",
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


def test_a_retry_comment_after_the_stop_makes_a_new_job_that_clears_the_report_of_the_old_one(
    store: InMemoryRoadmapStore, staged_repo: StageRepo, api: GitHubApiFake, kube: FakeCluster
) -> None:
    number = seed_staged(store)
    _round(store, staged_repo)
    _end(kube, "Failed")
    _round(store, staged_repo)
    first = _record(store, number)["implement.job"]
    store.seed_comment(number, "implement: retry", author_association="OWNER")

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

    monkeypatch.setattr("devops_cli.roadmap.implement_submit.plan_implement", plan_then_claim)

    with caplog.at_level(logging.INFO, logger="devops_cli.roadmap.run"):
        outcome = _round(store, staged_repo)

    assert f"Left #{number}: an agent or a person claimed it since the plan." in caplog.messages
    assert (outcome, _creates(kube), _owner(store, number), _record(store, number)) == (
        JobOutcome(),
        [],
        ("Human", ["owner/human"]),
        {"stage.branch": "fix/1-the-job-drops-a-comment", "stage.pr": "5"},
    )


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
