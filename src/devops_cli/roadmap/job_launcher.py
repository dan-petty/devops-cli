"""The one seam that makes the Job of a Service row from the suspended CronJob
`devops-cli-runner` (#5027, ADR 0021 section 8).

A row gives a `RunnerUnit`: the row, the repository and the item, the args of the command, the
size of the pod, the name, the deadline, and its own labels and annotations. The seam builds the
Job with `build_job`: the runner image of the template, the args only, a row of `RUNNER_SIZES`,
the memory limit `roadmap.implement.max_memory_limit`, a GitHub token for the one repository, and
the labels of ADR 0022 with the component `roadmap-<row>`. The admission policy
`roadmap-service-jobs` admits that Job (`tests/gate/k8s_checks/job_admission_policy.py`). Only the
implement Job carries the label `implement-repo`, so the implement lock counts no Job of another
row. The Job of another row sends its telemetry as `roadmap-<row>`. A `WorkflowLauncher` takes
this place after the engine step (#4566).

**The model limit.** The implement, stage and fix-checks Jobs each run a model. At most
`roadmap.model_jobs` of them run at once in the cluster, for every repository together
(`model_slots`). A fix-checks Job that finds no free place is created suspended: the Job
controller starts no pod, and the Job waits in the cluster, so a restart of the Service loses
nothing. The implement and stage rows leave the place of each waiting fix Job free, and the watch
row resumes the waiting fix Jobs, oldest first, so a fix Job goes before a new implement or stage
Job. While `roadmap.fix_checks.mode` is `off`, a waiting fix Job holds no place.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Final

from devops_cli.config.constants import CONST_GITHUB_APP_TOKEN_REPOSITORY_SETTING
from devops_cli.config.env import setting_variables
from devops_cli.config.settings import load_settings
from devops_cli.github.repo_ref import RepoRef, ServiceRow
from devops_cli.k8s.cluster_job import (
    COMPONENT_LABEL,
    FIX_CHECKS_COMPONENT,
    MANAGED_BY_LABEL,
    MANAGED_BY_LABEL_VALUE,
    MODEL_COMPONENTS,
    RUNNER_TEMPLATE,
    build_job,
)
from devops_cli.k8s.cluster_job_api import ClusterJob, ClusterJobs, JobState
from devops_cli.roadmap.implement.implement_size import RunnerSize

# The variable of the OpenTelemetry service name. The template sets `roadmap-implement`.
_SERVICE_NAME_VARIABLE: Final[str] = "OTEL_SERVICE_NAME"
# The annotation of the time (epoch seconds) at which the Service created a Job of a row: the
# order of the fix Jobs that wait.
CREATED_AT_ANNOTATION: Final[str] = "roadmap.devops-cli/created-at"


@dataclass(frozen=True)
class RunnerUnit:
    """One Job of the row `row` from the runner template: the args of its command, its size, its
    name, its `activeDeadlineSeconds`, the labels and the annotations of the row, and whether it
    starts suspended."""

    row: ServiceRow
    repo: RepoRef
    item: int
    args: tuple[str, ...]
    size: RunnerSize
    name: str
    deadline: int
    labels: Mapping[str, str] = field(default_factory=dict[str, str])
    annotations: Mapping[str, str] = field(default_factory=dict[str, str])
    suspend: bool = False

    @property
    def env(self) -> dict[str, str]:
        """The plain environment values: a GitHub token for the one repository, the worker count of
        the size, and for a row other than implement the telemetry name `roadmap-<row>`."""
        env = {
            setting_variables()[CONST_GITHUB_APP_TOKEN_REPOSITORY_SETTING]: self.repo.display,
            **self.size.env,
        }
        if self.row is not ServiceRow.IMPLEMENT:
            env[_SERVICE_NAME_VARIABLE] = f"roadmap-{self.row}"
        return env


def _options(unit: RunnerUnit, memory_limit: str) -> dict[str, Any]:
    """The arguments of `build_job` for `unit`, but the CronJob, the args and the name."""
    return {
        "template": RUNNER_TEMPLATE,
        "env": unit.env,
        "labels": unit.labels,
        "deadline": unit.deadline,
        "annotations": unit.annotations,
        "resources": unit.size.resources(memory_limit),
        "repo": unit.repo,
        "item": unit.item,
        "row": unit.row,
        "suspend": unit.suspend,
    }


def runner_job(cronjob: dict[str, Any], unit: RunnerUnit, memory_limit: str) -> dict[str, Any]:
    """The Job that `launch` creates for `unit` from `cronjob`, with the memory limit
    `memory_limit`. Pure: the gate check of the admission policy reads it."""
    return build_job(cronjob, list(unit.args), unit.name, **_options(unit, memory_limit))


def launch(jobs: ClusterJobs, unit: RunnerUnit, *, cronjob: dict[str, Any] | None = None) -> str:
    """Create the Job of `unit` from CronJob `devops-cli-runner`, or from `cronjob` when the
    caller read it, and give its name.

    Raises ClusterJobExistsError when a Job of the name exists (409), and ClusterJobError when the
    CronJob is missing or the API refuses the create.
    """
    memory_limit = load_settings().roadmap.implement.max_memory_limit
    return jobs.create(
        list(unit.args), name=unit.name, cronjob=cronjob, **_options(unit, memory_limit)
    )


@dataclass(frozen=True)
class ModelSlots:
    """The model Jobs of the cluster against `roadmap.model_jobs`: the limit, the Jobs that run,
    and the fix-checks Jobs that wait suspended, oldest first."""

    limit: int
    running: int = 0
    waiting: tuple[ClusterJob, ...] = ()

    @property
    def for_fix(self) -> int:
        """The places that a fix Job may take: a waiting fix Job waits for no other Job."""
        return max(self.limit - self.running, 0)

    @property
    def for_new(self) -> int:
        """The places that a new implement or stage Job may take: each waiting fix Job holds
        one."""
        return max(self.limit - self.running - len(self.waiting), 0)


def _created_at(job: ClusterJob) -> int:
    text = job.annotations.get(CREATED_AT_ANNOTATION, "")
    return int(text) if text.isdecimal() else 0


def model_slots(jobs: ClusterJobs) -> ModelSlots:
    """The model Jobs that run and wait in the cluster, as the module says: the Jobs of the
    Service (`app.kubernetes.io/managed-by: devops-cli`) whose component is a model component and
    that have not ended. A suspended fix Job waits while `roadmap.fix_checks.mode` is not `off`.

    Raises ClusterJobError when the API refuses the list.
    """
    roadmap = load_settings().roadmap
    listed = jobs.list_jobs({MANAGED_BY_LABEL: MANAGED_BY_LABEL_VALUE})
    live = [
        job
        for job in listed
        if job.labels.get(COMPONENT_LABEL) in MODEL_COMPONENTS and job.state is JobState.RUNNING
    ]
    waiting = (
        sorted(
            (
                job
                for job in live
                if job.suspended and job.labels.get(COMPONENT_LABEL) == FIX_CHECKS_COMPONENT
            ),
            key=lambda job: (_created_at(job), job.name),
        )
        if roadmap.fix_checks.mode != "off"
        else []
    )
    running = sum(1 for job in live if not job.suspended)
    return ModelSlots(roadmap.model_jobs, running, tuple(waiting))


__all__ = [
    "CREATED_AT_ANNOTATION",
    "ModelSlots",
    "RunnerUnit",
    "launch",
    "model_slots",
    "runner_job",
]
