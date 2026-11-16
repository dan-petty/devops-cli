"""The fix-checks units that the watch row starts (#5027): one Job from CronJob
`devops-cli-runner` for each due head and check, a 409 for a second create, the shared limit of the
model Jobs with the fix Jobs first, the report of an ended Job, and the next attempt of a Job that
left no result line.

The Kubernetes API is faked at its edge, and the CronJob template is the committed manifest
`k8s/devops/cronjob-runner.yaml`.
"""

from __future__ import annotations

import copy
import json
import logging
from collections.abc import Callable
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
from devops_cli.telemetry.metrics import GLOBAL_METRICS
from tests.support.fakes.kubernetes import FakeCluster, pod, status, terminated
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
    template = yaml.safe_load((REPO_ROOT / "k8s/devops/cronjob-runner.yaml").read_text("utf-8"))
    cluster.custom_objects.objects[CRONJOBS] = [copy.deepcopy(template)]
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
    _round()
    moved = FixDue(pull=7, head="b" * 40, check=CHECK, item=5)

    result = _round((moved,))

    assert (len(_jobs(kube)), len(result.created)) == (2, 1)


# ── The model limit ──────────────────────────────────────────────────────────────────────


def test_a_fix_job_with_no_free_place_waits_suspended_and_holds_the_place_of_a_new_job(
    kube: FakeCluster,
) -> None:
    kube.custom_objects.objects[JOBS] = [
        _model_job("devops-cli-implement-project-1-abc123", "roadmap-implement"),
        _model_job("devops-cli-stage-project-2-0123456789", "roadmap-stage"),
    ]

    result = _round()

    fix = _jobs(kube)[-1]
    kube.custom_objects.objects[JOBS][0]["status"] = {
        "conditions": [{"type": "Complete", "status": "True"}]
    }
    slots = model_slots(ClusterJobs())
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
    kube.custom_objects.objects[JOBS] = [
        _model_job("devops-cli-implement-project-1-abc123", "roadmap-implement"),
        _model_job("devops-cli-stage-project-2-0123456789", "roadmap-stage"),
    ]
    _round()
    _end(_jobs(kube)[0])
    config(roadmap={"fix_checks": {"mode": "off"}})

    assert model_slots(ClusterJobs()).for_new == 1


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
