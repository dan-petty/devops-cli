"""Jobs that run one devops command in the cluster, built from a suspended CronJob's template.

A suspended CronJob in namespace `devops` keeps the pod spec in git: its security context, the
keys of the `devops-cli` Secret, the config and the volumes. A Job made from it changes only the
container's args, its name, its labels and some environment values, so it passes the namespace's
`restricted` Pod Security and cannot drift from git. Three CronJobs are templates: `devops-cli`
for any command, `devops-cli-runner` for the implement job (#2667), and `roadmap-stage` for the
stage job of one item (#5483). The stage Job carries the labels of ADR 0022: the component
`roadmap-stage`, the owner, the repository and the item.
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

from devops_cli.config.constants import (
    CONST_GITHUB_APP_TOKEN_REPOSITORY_SETTING,
    CONST_ROADMAP_STAGE_JOB_DEADLINE_SETTING,
    CONST_ROADMAP_STAGE_JOB_SETTING,
)
from devops_cli.exceptions.k8s import ClusterJobError
from devops_cli.github.repo_ref import RepoRef, ServiceRow

JOB_NAMESPACE = "devops"
JOB_NAME_LABEL = "app.kubernetes.io/name"
JOB_NAME_LABEL_VALUE = "devops-cli-job"
# Set on every pod by the Job controller.
JOB_POD_SELECTOR_LABEL = "batch.kubernetes.io/job-name"
# The labels of ADR 0022, section 3, on the Job of a row of the Service and on its pod.
COMPONENT_LABEL = "app.kubernetes.io/component"
OWNER_LABEL = "roadmap.devops-cli/owner"
REPO_LABEL = "roadmap.devops-cli/repo"
ITEM_LABEL = "roadmap.devops-cli/item"


@dataclass(frozen=True)
class JobTemplate:
    """A CronJob that Jobs come from: its name, which also starts the name of each Job, and the
    name of the container whose args a Job changes."""

    cronjob: str
    container: str


DEFAULT_TEMPLATE = JobTemplate(cronjob="devops-cli", container="devops-cli")
RUNNER_TEMPLATE = JobTemplate(cronjob="devops-cli-runner", container="runner")
STAGE_TEMPLATE = JobTemplate(cronjob="roadmap-stage", container="stage")
# The component of the stage Job and of its pod: `roadmap-<row>` (ADR 0022).
STAGE_COMPONENT = f"roadmap-{ServiceRow.STAGE}"


class TemplateName(StrEnum):
    """The `--template` values of `devops k8s run-job`."""

    DEFAULT = "default"
    RUNNER = "runner"
    STAGE = "stage"

    @property
    def template(self) -> JobTemplate:
        return {
            TemplateName.DEFAULT: DEFAULT_TEMPLATE,
            TemplateName.RUNNER: RUNNER_TEMPLATE,
            TemplateName.STAGE: STAGE_TEMPLATE,
        }[self]


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


def stage_job_name(repo: RepoRef, item: int, plan_key: str) -> str:
    """The name of the stage Job of `item` for the plan input `plan_key`, such as the hash of the
    text of the item: `devops-cli-stage-<slug>-<item>-<10 hex>`, 63 characters at most. The same
    inputs give the same name, so a second create of the Job gets 409 (ADR 0022)."""
    return repo.unit_name(ServiceRow.STAGE, plan_key, item)


def stage_job_labels(repo: RepoRef, item: int) -> dict[str, str]:
    """The labels of the stage Job of `item` and of its pod: the component, the owner, the
    repository and the item. The owner and the repository labels together select `repo` and no
    other repository."""
    return {
        COMPONENT_LABEL: STAGE_COMPONENT,
        OWNER_LABEL: repo.owner_label,
        REPO_LABEL: repo.repo_label,
        ITEM_LABEL: str(item),
    }


def stage_jobs_selector(repo: RepoRef) -> dict[str, str]:
    """The labels that select each stage Job of `repo` and no other Job: the labels of
    `stage_job_labels` but the item. The stage row of the Service lists its Jobs by them (#4559)."""
    return {
        COMPONENT_LABEL: STAGE_COMPONENT,
        OWNER_LABEL: repo.owner_label,
        REPO_LABEL: repo.repo_label,
    }


def stage_job_env(repo: RepoRef, name: str, deadline: datetime) -> dict[str, str]:
    """The plain environment values of the stage Job `name`: the repository of its GitHub token,
    the name of the Job, and the time at which the deadline of the Job ends. The admission policy
    refuses `valueFrom` but for the keys of the Secret, so these values are plain."""
    from devops_cli.config.env import setting_variables

    variables = setting_variables()
    return {
        variables[CONST_GITHUB_APP_TOKEN_REPOSITORY_SETTING]: repo.display,
        variables[CONST_ROADMAP_STAGE_JOB_SETTING]: name,
        variables[CONST_ROADMAP_STAGE_JOB_DEADLINE_SETTING]: deadline.astimezone(UTC).isoformat(),
    }


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


def _with_resources(
    container: dict[str, Any], resources: Mapping[str, Mapping[str, str]] | None
) -> None:
    """Replace the request and limit values that `resources` names; the other values stay."""
    if not resources:
        return
    held = container.setdefault("resources", {})
    for kind, values in resources.items():
        held[kind] = {**held.get(kind, {}), **values}


def template_container(pod_spec: dict[str, Any], template: JobTemplate) -> dict[str, Any]:
    """The container of `pod_spec` that the template names. Raises ClusterJobError when the pod
    spec has none."""
    for container in pod_spec["containers"]:
        if container.get("name") == template.container:
            found: dict[str, Any] = container
            return found
    raise ClusterJobError(
        f"CronJob {JOB_NAMESPACE}/{template.cronjob} has no container {template.container}"
    )


def image_digest(cronjob: dict[str, Any], template: JobTemplate) -> str | None:
    """The digest in the image of the template's container in `cronjob`: the text after the `@`,
    as `sha256:<hex>`, or None when the image names no digest. Image Updater writes the digest
    there, and a Job made from `cronjob` runs it. Raises ClusterJobError when the CronJob has no
    such container."""
    pod_spec = cronjob["spec"]["jobTemplate"]["spec"]["template"]["spec"]
    image = str(template_container(pod_spec, template).get("image", ""))
    return image.partition("@")[2] or None


def build_job(
    cronjob: dict[str, Any],
    args: list[str],
    name: str,
    *,
    template: JobTemplate = DEFAULT_TEMPLATE,
    env: Mapping[str, str] | None = None,
    labels: Mapping[str, str] | None = None,
    deadline: int | None = None,
    annotations: Mapping[str, str] | None = None,
    resources: Mapping[str, Mapping[str, str]] | None = None,
) -> dict[str, Any]:
    """The Job the CronJob's template makes, with only args, name, labels, `env`, the deadline,
    the annotations and the `resources` changed.

    The labels go on the Job and on its pods, so `-l app.kubernetes.io/name=devops-cli-job`
    finds both. The annotations go on the Job only. `deadline` replaces the
    `activeDeadlineSeconds` of the template. `resources` maps `requests` and `limits` to the values
    that replace those of the container, such as `{"requests": {"memory": "2Gi"}}`.
    """
    job_template = cronjob["spec"]["jobTemplate"]
    spec = copy.deepcopy(job_template["spec"])
    pod_template = spec["template"]
    pod_template["metadata"] = _labelled(pod_template.get("metadata"), labels)
    container = template_container(pod_template["spec"], template)
    container["args"] = list(args)
    _with_env(container, env)
    _with_resources(container, resources)
    metadata = _labelled(job_template.get("metadata"), labels)
    metadata.update(name=name, namespace=JOB_NAMESPACE)
    if annotations:
        metadata["annotations"] = {**metadata.get("annotations", {}), **annotations}
    if deadline is not None:
        spec["activeDeadlineSeconds"] = deadline
    return {"apiVersion": "batch/v1", "kind": "Job", "metadata": metadata, "spec": spec}
