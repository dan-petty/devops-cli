"""Jobs that run one devops command in the cluster, built from a suspended CronJob's template.

A suspended CronJob in namespace `devops` keeps the pod spec in git: its security context, the
`devops-cli` Secret through `envFrom`, the config and the volumes. A Job made from it changes
only the container's args, its name, its labels and, for the runner, some environment values, so
it passes the namespace's `restricted` Pod Security and cannot drift from git. Two CronJobs are
templates: `devops-cli` for any command, and `devops-cli-runner` for the implement job (#2667).
"""

from __future__ import annotations

import copy
import hashlib
import secrets
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from devops_cli.exceptions.k8s import ClusterJobError

JOB_NAMESPACE = "devops"
JOB_NAME_LABEL = "app.kubernetes.io/name"
JOB_NAME_LABEL_VALUE = "devops-cli-job"
# Set on every pod by the Job controller.
JOB_POD_SELECTOR_LABEL = "batch.kubernetes.io/job-name"


@dataclass(frozen=True)
class JobTemplate:
    """A CronJob that Jobs come from: its name, which also starts the name of each Job, and the
    name of the container whose args a Job changes."""

    cronjob: str
    container: str


DEFAULT_TEMPLATE = JobTemplate(cronjob="devops-cli", container="devops-cli")
RUNNER_TEMPLATE = JobTemplate(cronjob="devops-cli-runner", container="runner")


class TemplateName(StrEnum):
    """The `--template` values of `devops k8s run-job`."""

    DEFAULT = "default"
    RUNNER = "runner"

    @property
    def template(self) -> JobTemplate:
        return RUNNER_TEMPLATE if self is TemplateName.RUNNER else DEFAULT_TEMPLATE


def job_name(now: datetime | None = None, template: JobTemplate = DEFAULT_TEMPLATE) -> str:
    """`<cronjob>-<UTC yyyymmdd-hhmmss>-<4 hex>`."""
    stamp = (now or datetime.now(UTC)).strftime("%Y%m%d-%H%M%S")
    return f"{template.cronjob}-{stamp}-{secrets.token_hex(2)}"


def repository_label(repo: str) -> str:
    """The value of the Job label `implement-repo` for `repo`: a digest, since `owner/name` is no
    label value. The Service and `devops k8s run-job` label the runner Jobs of a repository with
    it, and both list the Jobs by it. GitHub names are not case sensitive, so every spelling of a
    name has one label."""
    return hashlib.sha256(repo.casefold().encode("utf-8")).hexdigest()[:16]


def _labelled(
    metadata: dict[str, Any] | None, extra: Mapping[str, str] | None = None
) -> dict[str, Any]:
    """A copy of the metadata carrying the cluster-job label and the extra labels."""
    labelled = copy.deepcopy(metadata or {})
    labelled["labels"] = {
        **labelled.get("labels", {}),
        JOB_NAME_LABEL: JOB_NAME_LABEL_VALUE,
        **(extra or {}),
    }
    return labelled


def _with_env(container: dict[str, Any], env: Mapping[str, str] | None) -> None:
    """Set the environment values on the container; a name the template sets is replaced."""
    if not env:
        return
    kept = [entry for entry in container.get("env", []) if entry.get("name") not in env]
    container["env"] = [*kept, *({"name": name, "value": value} for name, value in env.items())]


def build_job(
    cronjob: dict[str, Any],
    args: list[str],
    name: str,
    *,
    template: JobTemplate = DEFAULT_TEMPLATE,
    env: Mapping[str, str] | None = None,
    labels: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """The Job the CronJob's template makes, with only args, name, labels and `env` changed.

    The labels go on the Job and on its pods, so `-l app.kubernetes.io/name=devops-cli-job`
    finds both.
    """
    job_template = cronjob["spec"]["jobTemplate"]
    spec = copy.deepcopy(job_template["spec"])
    pod_template = spec["template"]
    pod_template["metadata"] = _labelled(pod_template.get("metadata"), labels)
    container = next(
        (c for c in pod_template["spec"]["containers"] if c.get("name") == template.container),
        None,
    )
    if container is None:
        raise ClusterJobError(
            f"CronJob {JOB_NAMESPACE}/{template.cronjob} has no container {template.container}"
        )
    container["args"] = list(args)
    _with_env(container, env)
    metadata = _labelled(job_template.get("metadata"), labels)
    metadata.update(name=name, namespace=JOB_NAMESPACE)
    return {"apiVersion": "batch/v1", "kind": "Job", "metadata": metadata, "spec": spec}
