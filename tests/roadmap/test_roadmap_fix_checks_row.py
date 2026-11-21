"""The fix-checks units that the watch row starts (#5027): one Job from CronJob
`devops-cli-runner` for each due head and check, a 409 for a second create, the shared limit of the
model Jobs with the fix Jobs first, the report of an ended Job, and the next attempt of a Job that
left no result line.

The Kubernetes API is faked at its edge, and the CronJob template is the committed manifest
`k8s/devops/cronjob-runner.yaml`.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from dataclasses import replace
from datetime import timedelta
from pathlib import Path
from typing import Any

import pytest
import yaml

from devops_cli.config.constants import (
    CONST_ROADMAP_FIX_CHECKS_RETRY_SECONDS,
    CONST_SERVICE_METRIC_FIX_CHECKS_JOBS,
)
from devops_cli.config.settings import RoadmapImplementConfig, load_settings
from devops_cli.exceptions import ConfigurationError
from devops_cli.exceptions.k8s import ClusterJobExistsError
from devops_cli.github.repo_ref import RepoRef, ServiceRow
from devops_cli.k8s.cluster_job import (
    COMPONENT_LABEL,
    JOB_NAME_LABEL,
    JOB_NAME_LABEL_VALUE,
    MANAGED_BY_LABEL,
    MANAGED_BY_LABEL_VALUE,
    OUTCOME_ANNOTATION,
    RUNNER_TEMPLATE,
    stage_job_labels,
)
from devops_cli.k8s.cluster_job_api import ClusterJobs
from devops_cli.roadmap.fix_checks_row import (
    FixDue,
    fix_checks_deadline,
    fix_unit,
    result_of,
    run_fix_checks_round,
)
from devops_cli.roadmap.job_launcher import launch, model_slots
from devops_cli.roadmap.stores.store import FixChecksRecordKey, ItemField
from devops_cli.telemetry.metrics import GLOBAL_METRICS
from tests.support.fakes.kubernetes import FakeCluster, pod, status, terminated
from tests.support.fakes.roadmap_store import InMemoryRoadmapStore
from tests.support.job_templates import cronjob_template
from tests.support.paths import REPO_ROOT
from tests.support.roadmap_run import NOW

JOBS = ("batch", "v1", "jobs")
CRONJOBS = ("batch", "v1", "cronjobs")
REPO = "example/project"
HEAD = "a" * 40
CHECK = "Static Analysis"
DUE = FixDue(pull=7, head=HEAD, check=CHECK, item=5)
PLANNED_LINE = json.dumps(
    {"job": "fix_checks", "repo": REPO, "pull": 7, "result": "planned", "reason": "Plan: repair"}
)


@pytest.fixture
def kube(cluster: FakeCluster) -> FakeCluster:
    cluster.custom_objects.objects[CRONJOBS] = [cronjob_template(RUNNER_TEMPLATE)]
    return cluster


def _jobs(kube: FakeCluster) -> list[dict[str, Any]]:
    return kube.custom_objects.objects.get(JOBS, [])


def _container(job: dict[str, Any]) -> dict[str, Any]:
    container: dict[str, Any] = job["spec"]["template"]["spec"]["containers"][0]
    return container


def _env(job: dict[str, Any]) -> dict[str, str]:
    return {entry["name"]: entry.get("value", "") for entry in _container(job).get("env", [])}


def _round(due: tuple[FixDue, ...] = (DUE,), *, at: Any = NOW) -> Any:
    return run_fix_checks_round(REPO, due, now=at, jobs=ClusterJobs())


def _end(job: dict[str, Any], condition: str = "Complete", *, at: Any = NOW) -> None:
    job["status"] = {
        "conditions": [{"type": condition, "status": "True", "lastTransitionTime": at.isoformat()}],
    }


def _model_job(name: str, component: str) -> dict[str, Any]:
    """A model Job of another row that has not ended."""
    return {
        "metadata": {
            "name": name,
            "namespace": "devops",
            "labels": {
                JOB_NAME_LABEL: JOB_NAME_LABEL_VALUE,
                MANAGED_BY_LABEL: MANAGED_BY_LABEL_VALUE,
                COMPONENT_LABEL: component,
            },
        },
        "spec": {},
        "status": {},
    }


def _count(result: str) -> float:
    return GLOBAL_METRICS.get_counter_value(
        CONST_SERVICE_METRIC_FIX_CHECKS_JOBS, labels={"repo": REPO, "result": result}
    )


# ── The unit ─────────────────────────────────────────────────────────────────────────────


def test_a_due_unit_in_mode_plan_gives_one_job_of_the_runner_template_with_no_confirm(
    kube: FakeCluster,
) -> None:
    result = _round()

    (job,) = _jobs(kube)
    labels = job["metadata"]["labels"]
    assert (result.created, job["metadata"]["name"]) == (
        (RepoRef(REPO).unit_name(ServiceRow.FIX_CHECKS, f"7:{HEAD}:{CHECK}", 5),),
        RepoRef(REPO).unit_name(ServiceRow.FIX_CHECKS, f"7:{HEAD}:{CHECK}", 5),
    )
    assert _container(job)["args"] == [
        "roadmap",
        "step",
        "fix-checks",
        "--repo",
        REPO,
        "--pull",
        "7",
        "--head",
        HEAD,
        "--check",
        CHECK,
    ]
    assert (
        labels[COMPONENT_LABEL],
        labels["roadmap.devops-cli/item"],
        "implement-repo" in labels,
        _env(job)["OTEL_SERVICE_NAME"],
        _env(job)["DEVOPS_CLI_SERVICE_GITHUB_APP_TOKEN_REPOSITORY"],
        _container(job)["resources"]["requests"]["cpu"],
        job["spec"]["activeDeadlineSeconds"],
        job["spec"].get("suspend", False),
    ) == (
        "roadmap-fix-checks",
        "5",
        False,
        "roadmap-fix-checks",
        REPO,
        "4",
        fix_checks_deadline(load_settings().roadmap.implement),
        False,
    )


def test_mode_on_runs_the_step_with_confirm(kube: FakeCluster, config: Callable[..., Path]) -> None:
    config(roadmap={"fix_checks": {"mode": "on"}})

    _round()

    (job,) = _jobs(kube)
    assert _container(job)["args"][-1] == "--confirm"


def test_mode_off_sends_no_request_to_the_cluster(
    kube: FakeCluster, config: Callable[..., Path]
) -> None:
    config(roadmap={"fix_checks": {"mode": "off"}})

    result = _round()

    assert (result.created, kube.custom_objects.calls) == ((), [])


def test_a_second_round_of_the_same_head_and_check_creates_no_second_job(
    kube: FakeCluster,
) -> None:
    _round()
    second = _round()

    assert (len(_jobs(kube)), second.created, second.queued) == (1, (), ())


def test_a_second_create_of_the_same_unit_gets_409(kube: FakeCluster) -> None:
    unit = fix_unit(REPO, DUE, attempt=1, confirm=False, suspend=False, now=NOW)
    launch(ClusterJobs(), unit)

    with pytest.raises(ClusterJobExistsError, match="exists"):
        launch(ClusterJobs(), unit)
    assert len(_jobs(kube)) == 1


def test_a_new_head_is_a_new_unit(kube: FakeCluster) -> None:
    """After the Job of the old head ends, the new head of the pull request gets its own unit."""
    _round()
    (job,) = _jobs(kube)
    _end(job)
    kube.core.answers["list_namespaced_pod"] = [pod(f"{job['metadata']['name']}-x1", "devops")]
    kube.core.answers["read_namespaced_pod_log"] = f"{PLANNED_LINE}\n"
    moved = FixDue(pull=7, head="b" * 40, check=CHECK, item=5)

    result = _round((moved,))

    assert (len(_jobs(kube)), len(result.created)) == (2, 1)


# ── The model limit ──────────────────────────────────────────────────────────────────────


def test_a_fix_job_with_no_free_place_waits_suspended_and_holds_the_place_of_a_new_job(
    kube: FakeCluster, config: Callable[..., Path]
) -> None:
    config(service={"repos": [REPO]})
    kube.custom_objects.objects[JOBS] = [
        _model_job("devops-cli-implement-project-1-abc123", "roadmap-implement"),
        _model_job("devops-cli-stage-project-2-0123456789", "roadmap-stage"),
    ]

    result = _round()

    fix = _jobs(kube)[-1]
    kube.custom_objects.objects[JOBS][0]["status"] = {
        "conditions": [{"type": "Complete", "status": "True"}]
    }
    slots = model_slots(ClusterJobs(), now=NOW)
    assert (result.queued, fix["spec"]["suspend"], slots.for_new, slots.for_fix) == (
        (fix["metadata"]["name"],),
        True,
        0,
        1,
    )


def test_the_round_resumes_the_waiting_fix_job_when_a_place_frees(kube: FakeCluster) -> None:
    kube.custom_objects.objects[JOBS] = [
        _model_job("devops-cli-implement-project-1-abc123", "roadmap-implement"),
        _model_job("devops-cli-stage-project-2-0123456789", "roadmap-stage"),
    ]
    _round()
    _end(_jobs(kube)[0])

    result = _round()

    fix = _jobs(kube)[-1]
    assert (result.resumed, fix["spec"]["suspend"], result.created) == (
        (fix["metadata"]["name"],),
        False,
        (),
    )


def test_a_waiting_fix_job_holds_no_place_in_mode_off(
    kube: FakeCluster, config: Callable[..., Path]
) -> None:
    config(service={"repos": [REPO]})
    kube.custom_objects.objects[JOBS] = [
        _model_job("devops-cli-implement-project-1-abc123", "roadmap-implement"),
        _model_job("devops-cli-stage-project-2-0123456789", "roadmap-stage"),
    ]
    _round()
    _end(_jobs(kube)[0])
    config(roadmap={"fix_checks": {"mode": "off"}})

    assert model_slots(ClusterJobs(), now=NOW).for_new == 1


def test_a_stage_job_counts_against_the_model_limit(kube: FakeCluster) -> None:
    other = RepoRef("example/other")
    job = _model_job("devops-cli-stage-other-3-0000000000", "roadmap-stage")
    job["metadata"]["labels"].update(stage_job_labels(other, 3))
    kube.custom_objects.objects[JOBS] = [job]

    slots = model_slots(ClusterJobs())

    assert (slots.limit, slots.running, slots.for_new) == (2, 1, 1)


# ── The report and the next attempt ──────────────────────────────────────────────────────


def test_an_ended_job_is_reported_once_with_the_result_of_its_result_line(
    kube: FakeCluster, caplog: pytest.LogCaptureFixture
) -> None:
    _round()
    (job,) = _jobs(kube)
    _end(job)
    kube.core.answers["list_namespaced_pod"] = [pod(f"{job['metadata']['name']}-x1", "devops")]
    kube.core.answers["read_namespaced_pod_log"] = f"Reading the checks\n{PLANNED_LINE}\n"
    before = _count("planned")

    with caplog.at_level(logging.INFO, logger="devops_cli.roadmap.job_result"):
        first = _round()
        second = _round()

    lines = [r.getMessage() for r in caplog.records if "job=fix_checks" in r.getMessage()]
    (held,) = _jobs(kube)
    assert (
        first.reported,
        second.reported,
        held["metadata"]["annotations"][OUTCOME_ANNOTATION],
        _count("planned") - before,
        len(lines),
        "result=planned" in lines[0],
        len(_jobs(kube)),
    ) == ({job["metadata"]["name"]: "planned"}, {}, "planned", 1, 1, True, 1)


@pytest.mark.parametrize("printed_by", ["publish", "prepare"])
def test_the_result_line_of_a_job_on_the_phases_is_read_from_publish_then_prepare(
    kube: FakeCluster, printed_by: str
) -> None:
    """`publish` prints the result of the round, and `prepare` prints it when it ended the round
    itself (#3700, #6690)."""
    _round()
    (job,) = _jobs(kube)
    _end(job)
    name = f"{job['metadata']['name']}-x1"
    kube.core.answers["list_namespaced_pod"] = [
        pod(
            name,
            "devops",
            init_containers=("prepare", "agent"),
            containers=("publish",),
            init_statuses=[status("prepare", terminated(0)), status("agent", terminated(0))],
            statuses=[status("publish", terminated(0))],
        )
    ]
    kube.core.answers["read_namespaced_pod_log"] = {
        ("devops", name, phase): f"{PLANNED_LINE}\n" if phase == printed_by else "a phase\n"
        for phase in ("prepare", "agent", "publish")
    }

    assert _round().reported == {job["metadata"]["name"]: "planned"}


def test_a_job_with_no_result_line_is_none_and_gets_the_next_attempt_after_its_wait(
    kube: FakeCluster,
) -> None:
    _round()
    (first,) = _jobs(kube)
    _end(first, "Failed")
    kube.core.answers["list_namespaced_pod"] = []
    before = _count("none")

    early = _round(at=NOW + timedelta(seconds=CONST_ROADMAP_FIX_CHECKS_RETRY_SECONDS - 1))
    later = _round(at=NOW + timedelta(seconds=CONST_ROADMAP_FIX_CHECKS_RETRY_SECONDS))

    second = _jobs(kube)[-1]
    assert (
        early.reported,
        early.created,
        _count("none") - before,
        later.created,
        second["metadata"]["annotations"]["roadmap.devops-cli/attempt"],
        second["metadata"]["name"],
    ) == (
        {first["metadata"]["name"]: "none"},
        (),
        1,
        (second["metadata"]["name"],),
        "2",
        RepoRef(REPO).unit_name(ServiceRow.FIX_CHECKS, f"7:{HEAD}:{CHECK}#2", 5),
    )


def test_the_attempts_after_the_first_stop_at_the_continuations_of_an_item(
    kube: FakeCluster, config: Callable[..., Path]
) -> None:
    config(roadmap={"implement": {"continuations_per_item": 1}})
    kube.core.answers["list_namespaced_pod"] = []
    at = NOW
    for _ in range(3):
        _round(at=at)
        _end(_jobs(kube)[-1], "Failed", at=at)
        at += timedelta(days=1)

    assert len(_jobs(kube)) == 2


def test_a_command_that_exited_1_is_an_error_and_gets_no_next_attempt(kube: FakeCluster) -> None:
    """A typed stop, such as a refused checkout, exits 1 with no result line: a next attempt would
    stop the same way (#5027)."""
    _round()
    (job,) = _jobs(kube)
    _end(job, "Failed")
    name = job["metadata"]["name"]
    kube.core.answers["list_namespaced_pod"] = [
        pod(f"{name}-x1", "devops", statuses=[status("runner", terminated(1, "Error"))])
    ]
    kube.core.answers["read_namespaced_pod_log"] = "Could not fix checks on PR #7: refused\n"
    before = _count("error")

    first = _round()
    later = _round(at=NOW + timedelta(days=1))

    assert (first.reported, _count("error") - before, later.created, len(_jobs(kube))) == (
        {name: "error"},
        1,
        (),
        1,
    )


def test_a_job_with_a_result_line_ends_its_unit(kube: FakeCluster) -> None:
    _round()
    (job,) = _jobs(kube)
    _end(job)
    kube.core.answers["list_namespaced_pod"] = [pod(f"{job['metadata']['name']}-x1", "devops")]
    kube.core.answers["read_namespaced_pod_log"] = f"{PLANNED_LINE}\n"

    _round(at=NOW + timedelta(days=1))

    assert len(_jobs(kube)) == 1


def test_the_result_line_is_the_last_line_of_the_step() -> None:
    other = json.dumps({"job": "other", "result": "x"})
    assert (result_of(f"{PLANNED_LINE}\n{other}\nnot json {{\n"), result_of("no line\n")) == (
        "planned",
        None,
    )


# ── The deadline ─────────────────────────────────────────────────────────────────────────


def _template_implement() -> RoadmapImplementConfig:
    document = yaml.safe_load((REPO_ROOT / "k8s/devops/configmap.example.yaml").read_text("utf-8"))
    text = document["data"]["devops-cli.yaml"]
    return RoadmapImplementConfig.model_validate(yaml.safe_load(text)["roadmap"]["implement"])


@pytest.mark.parametrize("implement", [RoadmapImplementConfig(), _template_implement()])
def test_the_limits_of_a_fix_job_nest_under_the_cap(implement: RoadmapImplementConfig) -> None:
    """request < command < step < unit <= 14400 s, and the unit at least 300 s above the step,
    for the code defaults and for the values of the ConfigMap template."""
    deadline = fix_checks_deadline(implement)

    assert (
        implement.request_timeout_seconds
        < implement.command_timeout_seconds
        < implement.step_time_limit_seconds
        < deadline
        <= 14400
    )
    assert deadline - implement.step_time_limit_seconds >= 300


@pytest.mark.parametrize(
    ("values", "named"),
    [
        ({"step_time_limit_seconds": 13000}, "cap"),
        ({"command_timeout_seconds": 6000}, "command_timeout_seconds"),
        (
            {"request_timeout_seconds": 1900, "command_timeout_seconds": 1800},
            "request_timeout_seconds",
        ),
    ],
)
def test_limits_that_break_the_order_are_refused(values: dict[str, int], named: str) -> None:
    with pytest.raises(ConfigurationError, match=named):
        fix_checks_deadline(RoadmapImplementConfig(**values))


# ── The queue stays bounded (#6018) ──────────────────────────────────────────────────────

STOPPED_LINE = json.dumps(
    {"job": "fix_checks", "repo": REPO, "pull": 7, "result": "stopped", "reason": "Out of scope"}
)


@pytest.fixture
def store() -> InMemoryRoadmapStore:
    return InMemoryRoadmapStore(repo=REPO)


def _stored_due(store: InMemoryRoadmapStore, due: FixDue | None = None) -> FixDue:
    """`due` of the item of the store, with the unit record that the watch row reads from it."""
    if due is None:
        number = store.seed_issue("Sample", fields={ItemField.PRIORITY: "P1-High"})
        return FixDue(pull=7, head=HEAD, check=CHECK, item=number)
    item = store.item(due.item)
    assert item is not None
    return replace(due, units=item.job_record.get(FixChecksRecordKey.UNITS))


def _stored_round(store: InMemoryRoadmapStore, due: FixDue, *, at: Any = NOW) -> Any:
    return run_fix_checks_round(
        REPO, (_stored_due(store, due),), now=at, jobs=ClusterJobs(), store=store
    )


def _fail_without_result(kube: FakeCluster, job: dict[str, Any], *, exit_status: int = 0) -> None:
    _end(job, "Failed")
    name = job["metadata"]["name"]
    statuses = [status("runner", terminated(exit_status, "Error"))] if exit_status else []
    kube.core.answers["list_namespaced_pod"] = [pod(f"{name}-x1", "devops", statuses=statuses)]
    kube.core.answers["read_namespaced_pod_log"] = "no result line\n"


def test_the_item_record_keeps_the_attempt_when_the_ttl_deletes_the_job(
    kube: FakeCluster, config: Callable[..., Path], store: InMemoryRoadmapStore
) -> None:
    """In mode `on`, the round writes the attempt, the outcome and the next allowed time of the
    unit in the item record, so the next attempt after the TTL of the Job is 2, not 1 again."""
    config(roadmap={"fix_checks": {"mode": "on"}})
    due = _stored_due(store)
    _stored_round(store, due)
    _fail_without_result(kube, _jobs(kube)[0])
    _stored_round(store, due, at=NOW + timedelta(seconds=1))
    kube.custom_objects.objects[JOBS] = []

    result = _stored_round(store, due, at=NOW + timedelta(days=1))

    (second,) = _jobs(kube)
    assert (result.created, second["metadata"]["annotations"]["roadmap.devops-cli/attempt"]) == (
        (RepoRef(REPO).unit_name(ServiceRow.FIX_CHECKS, f"7:{HEAD}:{CHECK}#2", due.item),),
        "2",
    )


def test_an_error_in_the_item_record_gets_no_job_after_the_ttl(
    kube: FakeCluster, config: Callable[..., Path], store: InMemoryRoadmapStore
) -> None:
    config(roadmap={"fix_checks": {"mode": "on"}})
    due = _stored_due(store)
    _stored_round(store, due)
    _fail_without_result(kube, _jobs(kube)[0], exit_status=1)
    _stored_round(store, due, at=NOW + timedelta(seconds=1))
    kube.custom_objects.objects[JOBS] = []

    result = _stored_round(store, due, at=NOW + timedelta(days=1))

    assert (result.created, result.queued, _jobs(kube)) == ((), (), [])


def test_mode_plan_writes_no_unit_record(kube: FakeCluster, store: InMemoryRoadmapStore) -> None:
    """Mode `plan` writes nothing to GitHub (ADR 0021, rule 5): the record stays empty."""
    due = _stored_due(store)
    _stored_round(store, due)
    _fail_without_result(kube, _jobs(kube)[0])

    reported = _stored_round(store, due, at=NOW + timedelta(seconds=1))

    item = store.item(due.item)
    assert item is not None
    assert (list(reported.reported.values()), item.job_record.get(FixChecksRecordKey.UNITS)) == (
        ["none"],
        None,
    )


def test_no_new_unit_while_a_fix_job_of_the_same_pull_request_lives(kube: FakeCluster) -> None:
    """A test shard that fails while the Job of the lint check of the same head runs gets no
    Job. It gets one after that Job ends with no repair."""
    shard = FixDue(pull=7, head=HEAD, check="Tests & Coverage (shard 1/4)", item=5)
    _round()
    held = _round((shard,))
    (job,) = _jobs(kube)
    _end(job)
    kube.core.answers["list_namespaced_pod"] = [pod(f"{job['metadata']['name']}-x1", "devops")]
    kube.core.answers["read_namespaced_pod_log"] = f"{STOPPED_LINE}\n"

    after = _round((shard,), at=NOW + timedelta(minutes=5))

    assert (held.created, held.queued, len(after.created), len(_jobs(kube))) == ((), (), 1, 2)


def _wait_limit() -> timedelta:
    return timedelta(minutes=load_settings().roadmap.fix_checks.max_wait_minutes)


def _waiting_job(repo: str, *, at: Any = NOW) -> str:
    """Create a fix Job of `repo` that waits suspended, created at `at`."""
    unit = fix_unit(repo, DUE, attempt=1, confirm=False, suspend=True, now=at)
    return launch(ClusterJobs(), unit)


@pytest.mark.parametrize(("repo", "waiting"), [(REPO, 1), ("example/other", 0)])
def test_a_waiting_fix_job_holds_a_place_only_while_its_repository_is_in_service_repos(
    kube: FakeCluster, config: Callable[..., Path], repo: str, waiting: int
) -> None:
    config(service={"repos": [REPO]})
    _waiting_job(repo)

    slots = model_slots(ClusterJobs(), now=NOW)

    assert (len(slots.waiting), slots.for_new) == (waiting, 2 - waiting)


def test_a_fix_job_that_waits_longer_than_the_limit_is_deleted_with_a_log_line(
    kube: FakeCluster, config: Callable[..., Path], caplog: pytest.LogCaptureFixture
) -> None:
    """The round of any repository deletes a waiting fix Job older than
    `roadmap.fix_checks.max_wait_minutes`, also the Job of a repository that left
    `service.repos`, and the Job holds no place."""
    config(service={"repos": [REPO]})
    name = _waiting_job("example/other")
    late = NOW + _wait_limit() + timedelta(seconds=1)
    before = _count("expired")

    with caplog.at_level(logging.WARNING, logger="devops_cli.roadmap.fix_checks_row"):
        result = _round((), at=late)

    lines = [r.getMessage() for r in caplog.records if name in r.getMessage()]
    assert (result.expired, _jobs(kube), len(lines), _count("expired") - before) == (
        (name,),
        [],
        1,
        1,
    )


def test_a_fix_job_within_the_wait_limit_is_kept(kube: FakeCluster) -> None:
    name = _waiting_job(REPO)

    result = _round((), at=NOW + _wait_limit())

    assert (result.expired, [job["metadata"]["name"] for job in _jobs(kube)]) == ((), [name])


def test_a_job_that_its_deadline_ended_has_its_own_outcome_and_no_next_attempt(
    kube: FakeCluster,
) -> None:
    _round()
    (job,) = _jobs(kube)
    job["status"] = {
        "conditions": [
            {
                "type": "Failed",
                "status": "True",
                "reason": "DeadlineExceeded",
                "lastTransitionTime": NOW.isoformat(),
            }
        ]
    }
    kube.core.answers["list_namespaced_pod"] = []
    before = _count("deadline")

    first = _round()
    later = _round(at=NOW + timedelta(days=1))

    assert (first.reported, _count("deadline") - before, later.created, len(_jobs(kube))) == (
        {job["metadata"]["name"]: "deadline"},
        1,
        (),
        1,
    )
