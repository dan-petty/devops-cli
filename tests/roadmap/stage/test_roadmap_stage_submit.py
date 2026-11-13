"""The `stage` row of the Service's status lane: a round submits one stage Job for each Ready item
that has none, up to `roadmap.stage.jobs`, and recovers the check-out of a Job that is gone or
ended with no check-in (#4559).

Git runs for real on a clone with an `origin`, GitHub and the Kubernetes API are faked at their
edges, and the CronJob template is the committed manifest `k8s/devops/cronjob-stage.yaml`.
"""

from __future__ import annotations

import copy
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest
import yaml

from devops_cli.config.constants import (
    CONST_ROADMAP_OWNER_SERVICE,
    CONST_ROADMAP_STAGE_COMMENT_MARKER,
    CONST_SERVICE_METRIC_STAGE_JOBS,
)
from devops_cli.config.settings import RoadmapConfig
from devops_cli.exceptions import RoadmapStageError
from devops_cli.exceptions.k8s import ClusterJobError
from devops_cli.github.repo_ref import RepoRef
from devops_cli.k8s.cluster_job import JOB_NAME_LABEL, JOB_NAME_LABEL_VALUE, stage_job_labels
from devops_cli.roadmap import run
from devops_cli.roadmap.run import MODEL_LANE_ROWS, STATUS_LANE_ROWS, JobOutcome
from devops_cli.roadmap.stage.stage_job import recorded_check_in
from devops_cli.roadmap.stage.stage_submit import job_name_of, run_stage_round
from devops_cli.roadmap.stores.store import Item, StageRecordKey
from devops_cli.telemetry.metrics import GLOBAL_METRICS
from tests.support.fakes.kubernetes import api_exception
from tests.support.fakes.roadmap_store import InMemoryRoadmapStore
from tests.support.paths import REPO_ROOT
from tests.support.roadmap_stage import STAGE_NAME, STAGE_REPO, StageRepo, seed_stageable

if TYPE_CHECKING:
    from collections.abc import Callable

    from tests.support.fakes.kubernetes import FakeCluster

pytestmark = pytest.mark.usefixtures("keyring_store")

STAGE_ROW = next(row for row in STATUS_LANE_ROWS if row.name == "stage")
JOBS = ("batch", "v1", "jobs")
CRONJOBS = ("batch", "v1", "cronjobs")
REPO = RepoRef(STAGE_REPO)
NOW = datetime(2026, 11, 13, 12, 0, tzinfo=UTC)
BRANCH = "fix/1-the-job-drops-a-comment"
OTHER_KEY_JOB = "devops-cli-stage-roadmap-1-0000000000"


@pytest.fixture(autouse=True)
def counters() -> None:
    """Each test reads the counters of its own round."""
    GLOBAL_METRICS.reset()


@pytest.fixture
def store() -> InMemoryRoadmapStore:
    return InMemoryRoadmapStore(repo=STAGE_REPO)


@pytest.fixture
def kube(cluster: FakeCluster) -> FakeCluster:
    """The fake cluster with CronJob roadmap-stage of the committed manifest."""
    manifest = yaml.safe_load((REPO_ROOT / "k8s/devops/cronjob-stage.yaml").read_text("utf-8"))
    cluster.custom_objects.objects[CRONJOBS] = [copy.deepcopy(manifest)]
    return cluster


def _item(store: InMemoryRoadmapStore, number: int = 1) -> Item:
    item = store.item(number)
    assert item is not None
    return item


def _record(store: InMemoryRoadmapStore, number: int = 1) -> dict[str, str]:
    return {
        str(key): value
        for key, value in _item(store, number).job_record.items()
        if value is not None
    }


def _name(store: InMemoryRoadmapStore, number: int = 1) -> str:
    return job_name_of(STAGE_REPO, _item(store, number))


def _jobs(kube: FakeCluster) -> list[dict[str, Any]]:
    return kube.custom_objects.objects.get(JOBS, [])


def _creates(kube: FakeCluster) -> list[dict[str, Any]]:
    return [
        call[1]["body"]
        for call in kube.custom_objects.calls
        if call[0] == "create_namespaced_custom_object"
    ]


def _deletes(kube: FakeCluster) -> list[str]:
    return [
        call[1]["name"]
        for call in kube.custom_objects.calls
        if call[0] == "delete_namespaced_custom_object"
    ]


def _listed(
    name: str,
    item: int,
    *conditions: str,
    reason: str = "",
    message: str = "",
    labels: bool = True,
) -> dict[str, Any]:
    """A stage Job as the API lists it: the labels of its item, and the conditions that are True.
    With no condition the Job has not ended."""
    metadata: dict[str, Any] = {"name": name, "namespace": "devops"}
    if labels:
        metadata["labels"] = {JOB_NAME_LABEL: JOB_NAME_LABEL_VALUE, **stage_job_labels(REPO, item)}
    status = {
        "conditions": [
            {"type": kind, "status": "True", "reason": reason, "message": message}
            for kind in conditions
        ]
    }
    return {"metadata": metadata, "status": status}


def _hold(kube: FakeCluster, job: dict[str, Any]) -> None:
    kube.custom_objects.objects.setdefault(JOBS, []).append(job)


def _check_out(
    store: InMemoryRoadmapStore,
    number: int,
    job: str,
    *,
    deadline: datetime = NOW + timedelta(hours=3),
    marks: dict[StageRecordKey, str] | None = None,
) -> None:
    store.set_marks(
        _item(store, number),
        {
            StageRecordKey.JOB: job,
            StageRecordKey.JOB_AT: (NOW - timedelta(minutes=30)).isoformat(),
            StageRecordKey.JOB_DEADLINE: deadline.isoformat(),
            **(marks or {}),
        },
    )


def _round(store: InMemoryRoadmapStore, repo: StageRepo, *, now: datetime = NOW) -> Any:
    return run_stage_round(store, repo=STAGE_REPO, source=repo.clone, now=now)


def _counted(result: str, failure: str = "none") -> float:
    return GLOBAL_METRICS.get_counter(
        CONST_SERVICE_METRIC_STAGE_JOBS,
        labels={"repo": STAGE_REPO, "result": result, "class": failure},
    )


# ── The row ───────────────────────────────────────────────────────────────────


def test_the_row_is_a_status_lane_submit_on_the_status_clone_and_no_model_lane_row() -> None:
    """The row calls no model: the stage Job does. It runs on the status lane, after implement
    and stage_ready, so a long model-lane round never holds back a submit (#4559)."""
    cadence = STAGE_ROW.cadence
    assert (
        [row.name for row in STATUS_LANE_ROWS],
        [row.name for row in MODEL_LANE_ROWS],
        STAGE_ROW.needs_clone,
        STAGE_ROW.first_run_due,
        None if cadence is None else cadence(RoadmapConfig()).interval_minutes,
    ) == (
        [
            "metrics",
            "implement",
            "stage_ready",
            "stage",
            "release_comments",
            "github_status",
            "cloudflare_status",
            "pr_conflicts",
        ],
        ["retitle", "fix_plan", "refine", "alternatives"],
        True,
        True,
        37,
    )


def test_the_row_makes_no_model_call_and_no_model_clone(
    store: InMemoryRoadmapStore,
    stage_repo: StageRepo,
    kube: FakeCluster,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seed_stageable(store)

    def refused(*_: Any, **__: Any) -> Any:
        raise AssertionError("the stage row reached the model")

    monkeypatch.setattr(run, "get_task_model", refused)
    monkeypatch.setattr(run, "model_clone", refused)

    outcome = STAGE_ROW.runner(store=store, repo=STAGE_REPO, clone_path=stage_repo.clone)

    assert (outcome, len(_jobs(kube))) == (JobOutcome(queue=1), 1)


def test_a_round_with_no_repository_is_refused_before_any_request(
    store: InMemoryRoadmapStore, stage_repo: StageRepo, kube: FakeCluster
) -> None:
    with pytest.raises(RoadmapStageError, match="no repository"):
        run_stage_round(store, repo="", source=stage_repo.clone, now=NOW)

    assert kube.custom_objects.calls == []


def test_the_jobs_setting_defaults_to_1_refuses_0_and_is_in_the_example_configmap() -> None:
    example = yaml.safe_load((REPO_ROOT / "k8s/devops/configmap.example.yaml").read_text("utf-8"))
    configured = yaml.safe_load(example["data"]["devops-cli.yaml"])
    with pytest.raises(ValueError, match="jobs"):
        RoadmapConfig.model_validate({"stage": {"jobs": 0}})
    assert (RoadmapConfig().stage.jobs, configured["roadmap"]["stage"]["jobs"]) == (1, 1)


# ── The submit ────────────────────────────────────────────────────────────────


def test_a_round_with_2_jobs_creates_one_for_the_item_with_none_and_none_for_a_running_item(
    store: InMemoryRoadmapStore,
    stage_repo: StageRepo,
    kube: FakeCluster,
    config: Callable[..., Path],
) -> None:
    """Item A has a running Job of another plan key, item B has none: the Job list is the lock."""
    config(roadmap={"stage": {"jobs": 2}})
    seed_stageable(store)
    seed_stageable(store, "fix(roadmap): the job drops a label")
    _hold(kube, _listed(OTHER_KEY_JOB, 1))

    result = _round(store, stage_repo)

    (created,) = _creates(kube)
    assert (
        result.created,
        created["metadata"]["name"],
        _record(store, 2)["stage.job"],
        "stage.job" in _record(store, 1),
        _deletes(kube),
    ) == ((_name(store, 2),), _name(store, 2), _name(store, 2), False, [])


def test_a_round_with_1_job_and_a_running_job_creates_none(
    store: InMemoryRoadmapStore, stage_repo: StageRepo, kube: FakeCluster
) -> None:
    seed_stageable(store)
    seed_stageable(store, "fix(roadmap): the job drops a label")
    _hold(kube, _listed(OTHER_KEY_JOB, 1))

    result = _round(store, stage_repo)

    assert (result.created, _creates(kube), "stage.job" in _record(store, 2)) == ((), [], False)


def test_a_repeated_submit_of_the_same_item_and_plan_key_gets_409_and_makes_no_second_job(
    store: InMemoryRoadmapStore, stage_repo: StageRepo, kube: FakeCluster
) -> None:
    """A Job of the same name that the list did not show, as a create between the list and the
    create makes: the API refuses the create, and the round takes the Job as its own."""
    seed_stageable(store)
    _hold(kube, _listed(_name(store), 1, labels=False))

    result = _round(store, stage_repo)

    assert (
        result.created,
        result.existed,
        len(_jobs(kube)),
        _record(store)["stage.job"],
        _counted("existed"),
    ) == ((), (_name(store),), 1, _name(store), 1.0)


def test_the_check_out_is_written_before_the_create(
    store: InMemoryRoadmapStore, stage_repo: StageRepo, kube: FakeCluster
) -> None:
    seed_stageable(store)
    seen: list[tuple[str | None, str | None, bool, str | None]] = []
    create = kube.custom_objects.create_namespaced_custom_object

    def spy(*args: Any, **kwargs: Any) -> Any:
        item = _item(store)
        record = item.job_record
        seen.append(
            (
                record.get(StageRecordKey.JOB),
                record.get(StageRecordKey.JOB_AT),
                record.get(StageRecordKey.JOB_DEADLINE) is not None,
                item.owner,
            )
        )
        return create(*args, **kwargs)

    kube.custom_objects.create_namespaced_custom_object = spy  # type: ignore[method-assign]

    _round(store, stage_repo)

    assert seen == [(_name(store), NOW.isoformat(), True, CONST_ROADMAP_OWNER_SERVICE)]


def test_a_failed_create_releases_the_check_out_and_the_claim(
    store: InMemoryRoadmapStore, stage_repo: StageRepo, kube: FakeCluster
) -> None:
    seed_stageable(store)
    kube.custom_objects.fail("create_namespaced_custom_object", api_exception(403, "Forbidden"))

    with pytest.raises(ClusterJobError, match="HTTP 403"):
        _round(store, stage_repo)

    record = _record(store)
    assert (
        [key for key in ("stage.job", "stage.job_at", "stage.job_deadline") if key in record],
        _item(store).owner,
    ) == ([], None)


def test_the_created_job_has_no_owner_reference_and_names_its_item_and_itself(
    store: InMemoryRoadmapStore, stage_repo: StageRepo, kube: FakeCluster
) -> None:
    seed_stageable(store)

    _round(store, stage_repo)

    (job,) = _creates(kube)
    (container,) = job["spec"]["template"]["spec"]["containers"]
    env = {entry["name"]: entry.get("value") for entry in container["env"]}
    assert (
        "ownerReferences" in job["metadata"],
        job["metadata"]["labels"]["roadmap.devops-cli/item"],
        container["args"],
        env["DEVOPS_CLI_ROADMAP_STAGE_JOB"],
        env["DEVOPS_CLI_ROADMAP_STAGE_JOB_DEADLINE"],
        _counted("created"),
    ) == (
        False,
        "1",
        ["roadmap", "stage", "--repo", STAGE_REPO, "--job-item", "1", "--confirm"],
        _name(store),
        _record(store)["stage.job_deadline"],
        1.0,
    )


def test_a_round_with_a_running_job_inside_its_deadline_deletes_nothing_and_keeps_the_check_out(
    store: InMemoryRoadmapStore, stage_repo: StageRepo, kube: FakeCluster
) -> None:
    seed_stageable(store)
    _check_out(store, 1, _name(store))
    _hold(kube, _listed(_name(store), 1))

    result = _round(store, stage_repo)

    assert (result.recovered, _deletes(kube), _creates(kube), _record(store)["stage.job"]) == (
        (),
        [],
        [],
        _name(store),
    )


def test_the_orphan_rule_runs_before_any_create(
    store: InMemoryRoadmapStore, stage_repo: StageRepo, kube: FakeCluster
) -> None:
    """An old orphan of item A goes in the same round, and A gets its Job."""
    seed_stageable(store)
    store.set_marks(
        _item(store),
        {
            StageRecordKey.PENDING: json.dumps(
                {"branch": BRANCH, "time": (NOW - timedelta(hours=2)).isoformat()}
            )
        },
    )
    stage_repo.push_branch(BRANCH, author=STAGE_NAME)

    result = _round(store, stage_repo)

    assert (
        stage_repo.origin_git("branch", "--format=%(refname:short)").split(),
        "stage.pending" in _record(store),
        result.created,
    ) == (["main"], False, (_name(store),))


# ── The poll recovery ─────────────────────────────────────────────────────────


def _end(store: InMemoryRoadmapStore) -> tuple[str | None, str | None]:
    check_in = recorded_check_in(_item(store))
    return (None, None) if check_in is None else (check_in.job, check_in.result)


def test_a_missing_job_is_evicted_freed_and_submitted_again_at_once(
    store: InMemoryRoadmapStore, stage_repo: StageRepo, kube: FakeCluster
) -> None:
    seed_stageable(store)
    _check_out(store, 1, _name(store))

    result = _round(store, stage_repo)

    record = _record(store)
    assert (
        [(r.number, r.end) for r in result.recovered],
        _end(store),
        "stage.failed_at" in record,
        json.loads(record["stage.evictions"])["count"],
        result.created,
        record["stage.job"],
        _counted("evicted"),
    ) == ([(1, "evicted")], (_name(store), "evicted"), False, 1, (_name(store),), _name(store), 1.0)


def test_the_fourth_eviction_on_one_body_counts_as_a_failure(
    store: InMemoryRoadmapStore, stage_repo: StageRepo, kube: FakeCluster
) -> None:
    seed_stageable(store)
    first = _round(store, stage_repo)
    for _ in range(4):
        _jobs(kube).clear()
        _round(store, stage_repo)

    record = _record(store)
    assert (
        first.created,
        record["stage.failed_class"],
        record["stage.plan_defects"],
        "stage.job" in record,
        _counted("evicted"),
        _counted("evicted", "ci_infra"),
    ) == ((_name(store),), "ci_infra", "1", False, 3.0, 1.0)


def test_a_job_failed_by_its_deadline_records_deadline_and_counts(
    store: InMemoryRoadmapStore, stage_repo: StageRepo, kube: FakeCluster
) -> None:
    seed_stageable(store)
    _check_out(store, 1, _name(store))
    _hold(kube, _listed(_name(store), 1, "Failed", reason="DeadlineExceeded"))

    result = _round(store, stage_repo)

    record = _record(store)
    assert (
        _end(store),
        record["stage.failed_class"],
        record["stage.failed_error"],
        record["stage.plan_defects"],
        _deletes(kube),
        result.created,
        _counted("deadline", "timeout"),
    ) == ((_name(store), "deadline"), "timeout", "deadline", "1", [], (), 1.0)


def test_a_job_that_runs_past_its_recorded_deadline_is_deleted_and_records_deadline(
    store: InMemoryRoadmapStore, stage_repo: StageRepo, kube: FakeCluster
) -> None:
    seed_stageable(store)
    _check_out(store, 1, _name(store), deadline=NOW - timedelta(minutes=20))
    _hold(kube, _listed(_name(store), 1))

    _round(store, stage_repo)

    assert (_deletes(kube), _end(store), _record(store)["stage.failed_class"]) == (
        [_name(store)],
        (_name(store), "deadline"),
        "timeout",
    )


def test_a_job_failed_by_its_pod_failure_policy_with_no_check_in_is_failed_by_its_exit_code(
    store: InMemoryRoadmapStore, stage_repo: StageRepo, kube: FakeCluster
) -> None:
    seed_stageable(store)
    _check_out(store, 1, _name(store))
    message = (
        f"Container stage for pod devops/{_name(store)}-x failed with exit code 137 matching"
        " FailJob rule at index 1"
    )
    _hold(kube, _listed(_name(store), 1, "Failed", reason="PodFailurePolicy", message=message))

    _round(store, stage_repo)

    assert (_end(store), _record(store)["stage.failed_class"], _counted("failed", "oom")) == (
        (_name(store), "failed"),
        "oom",
        1.0,
    )


def test_a_succeeded_job_with_a_lost_check_in_is_freed_with_no_failure(
    store: InMemoryRoadmapStore, stage_repo: StageRepo, kube: FakeCluster
) -> None:
    seed_stageable(store)
    _check_out(store, 1, _name(store))
    _hold(kube, _listed(_name(store), 1, "Complete"))
    stage_repo.push_branch(BRANCH, author=STAGE_NAME)

    _round(store, stage_repo)

    record = _record(store)
    assert (
        _end(store),
        [key for key in record if key.startswith("stage.failed")],
        "stage.job" in record,
        _item(store).owner,
    ) == ((_name(store), "succeeded"), [], False, None)


def test_a_failed_job_is_deleted_only_when_the_failure_wait_of_its_item_ended(
    store: InMemoryRoadmapStore, stage_repo: StageRepo, kube: FakeCluster
) -> None:
    seed_stageable(store)
    _check_out(store, 1, _name(store))
    message = "Container stage for pod devops/x failed with exit code 1 matching FailJob rule"
    _hold(kube, _listed(_name(store), 1, "Failed", reason="PodFailurePolicy", message=message))

    _round(store, stage_repo)
    waiting = _round(store, stage_repo, now=NOW + timedelta(minutes=30))
    deleted_while_waiting = list(_deletes(kube))
    after = _round(store, stage_repo, now=NOW + timedelta(hours=2))

    (job,) = _jobs(kube)
    assert (
        waiting.created,
        deleted_while_waiting,
        _deletes(kube),
        after.created,
        job.get("status"),
    ) == ((), [], [_name(store)], (_name(store),), None)


def test_the_third_counted_end_on_one_body_returns_the_item_to_new_and_asks_for_a_split(
    store: InMemoryRoadmapStore, stage_repo: StageRepo, kube: FakeCluster
) -> None:
    from devops_cli.roadmap.stage.stage import plan_body_hash

    seed_stageable(store)
    _check_out(
        store,
        1,
        _name(store),
        marks={
            StageRecordKey.PLAN_DEFECTS: "2",
            StageRecordKey.PLAN_DEFECTS_BODY: plan_body_hash(_item(store)),
        },
    )
    _hold(kube, _listed(_name(store), 1, "Failed", reason="DeadlineExceeded"))

    _round(store, stage_repo)

    record = _record(store)
    (comment,) = [c.body for c in store.comments_on(1)]
    assert (
        _item(store).status,
        "stage.plan_defects" in record,
        "stage.job" in record,
        comment.startswith(CONST_ROADMAP_STAGE_COMMENT_MARKER),
        "split" in comment,
        _creates(kube),
    ) == ("New", False, False, True, True, [])
