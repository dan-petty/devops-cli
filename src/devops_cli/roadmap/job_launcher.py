"""The one seam that makes the Job of a Service row from the suspended CronJob
`devops-cli-runner` (#5027, ADR 0021 section 8).

A row gives a `RunnerUnit`: the row, the repository and the item, the args of the command, the
size of the pod, the name, the deadline, and its own labels and annotations. The seam builds the
Job with `build_job`: the runner image of the template, the args only, a row of `RUNNER_SIZES`
with a memory limit equal to its memory request (#7422), a GitHub token for the one repository, and
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
Job. A waiting fix Job holds a place only while `roadmap.fix_checks.mode` is not `off`, its
repository is in `service.repos`, and it has waited at most `roadmap.fix_checks.max_wait_minutes`
(#6018): only the watch row of its own repository resumes it, and the watch row deletes it after
that limit (`stale`).
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
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
    OWNER_LABEL,
    REPO_LABEL,
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


def _options(unit: RunnerUnit) -> dict[str, Any]:
    """The arguments of `build_job` for `unit`, but the CronJob, the args and the name."""
    return {
        "template": RUNNER_TEMPLATE,
        "env": unit.env,
        "labels": unit.labels,
        "deadline": unit.deadline,
        "annotations": unit.annotations,
        "resources": unit.size.resources(),
        "repo": unit.repo,
        "item": unit.item,
        "row": unit.row,
        "suspend": unit.suspend,
    }


def runner_job(cronjob: dict[str, Any], unit: RunnerUnit) -> dict[str, Any]:
    """The Job that `launch` creates for `unit` from `cronjob`. Pure: the gate check of the
    admission policy reads it."""
    return build_job(cronjob, list(unit.args), unit.name, **_options(unit))


def launch(jobs: ClusterJobs, unit: RunnerUnit, *, cronjob: dict[str, Any] | None = None) -> str:
    """Create the Job of `unit` from CronJob `devops-cli-runner`, or from `cronjob` when the
    caller read it, and give its name.

    Raises ClusterJobExistsError when a Job of the name exists (409), and ClusterJobError when the
    CronJob is missing or the API refuses the create.
    """
    return jobs.create(list(unit.args), name=unit.name, cronjob=cronjob, **_options(unit))


@dataclass(frozen=True)
class ModelSlots:
    """The model Jobs of the cluster against `roadmap.model_jobs`: the limit, the Jobs that run,
    and the fix-checks Jobs that wait suspended and hold a place, oldest first."""

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


def created_at(job: ClusterJob) -> int:
    """The time (epoch seconds) at which the Service created `job`, from its annotation, or 0
    when it has none."""
    text = job.annotations.get(CREATED_AT_ANNOTATION, "")
    return int(text) if text.isdecimal() else 0


def waits(job: ClusterJob) -> bool:
    """Whether `job` is a fix-checks Job that waits suspended for a model place."""
    return (
        job.suspended
        and job.state is JobState.RUNNING
        and job.labels.get(COMPONENT_LABEL) == FIX_CHECKS_COMPONENT
    )


def stale(job: ClusterJob, now: datetime) -> bool:
    """Whether the waiting fix Job `job` has waited longer than
    `roadmap.fix_checks.max_wait_minutes` at `now`. A Job with no time of creation is stale."""
    limit = timedelta(minutes=load_settings().roadmap.fix_checks.max_wait_minutes)
    return waits(job) and now - datetime.fromtimestamp(created_at(job), UTC) > limit


def oldest_first(jobs: Iterable[ClusterJob]) -> tuple[ClusterJob, ...]:
    """`jobs` in the order of their creation, oldest first."""
    return tuple(sorted(jobs, key=lambda job: (created_at(job), job.name)))


def _service_repos() -> frozenset[tuple[str, str]]:
    """The values of the labels owner and repo of each repository of `service.repos`."""
    refs = (RepoRef(repo) for repo in load_settings().service.repos)
    return frozenset((ref.owner_label, ref.repo_label) for ref in refs)


def model_slots(jobs: ClusterJobs, *, now: datetime | None = None) -> ModelSlots:
    """The model Jobs that run and wait in the cluster at `now`, as the module says: the Jobs of
    the Service (`app.kubernetes.io/managed-by: devops-cli`) whose component is a model component
    and that have not ended. A suspended fix Job waits while `roadmap.fix_checks.mode` is not
    `off`, its repository is in `service.repos`, and it is not `stale`.

    Raises ClusterJobError when the API refuses the list.
    """
    roadmap = load_settings().roadmap
    moment = now or datetime.now(UTC)
    listed = jobs.list_jobs({MANAGED_BY_LABEL: MANAGED_BY_LABEL_VALUE})
    live = [
        job
        for job in listed
        if job.labels.get(COMPONENT_LABEL) in MODEL_COMPONENTS and job.state is JobState.RUNNING
    ]
    served = _service_repos()
    waiting = (
        oldest_first(
            job
            for job in live
            if waits(job)
            and (job.labels.get(OWNER_LABEL), job.labels.get(REPO_LABEL)) in served
            and not stale(job, moment)
        )
        if roadmap.fix_checks.mode != "off"
        else ()
    )
    running = sum(1 for job in live if not job.suspended)
    return ModelSlots(roadmap.model_jobs, running, waiting)


__all__ = [
    "CREATED_AT_ANNOTATION",
    "ModelSlots",
    "RunnerUnit",
    "created_at",
    "launch",
    "model_slots",
    "oldest_first",
    "runner_job",
    "stale",
    "waits",
]
