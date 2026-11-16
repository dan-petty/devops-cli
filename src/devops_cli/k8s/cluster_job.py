"""Jobs that run one devops command in the cluster, built from a suspended CronJob's template.

A suspended CronJob in namespace `devops` keeps the pod spec in git: its security context, the
keys of the `devops-cli` Secret, the config and the volumes. A Job made from it changes only the
container's args, its name, its labels and some environment values, so it passes the namespace's
`restricted` Pod Security and cannot drift from git. Three CronJobs are templates: `devops-cli`
for any command, `devops-cli-runner` for the implement job (#2667) and the fix-checks unit
(#5027), and `roadmap-stage` for the stage job of one item (#5483). The stage Job carries the
labels of ADR 0022: the component `roadmap-stage`, the owner, the repository and the item. Only
the implement Job of the runner template carries the label `implement-repo`, which the implement
lock lists.
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
    CONST_ROADMAP_IMPLEMENT_JOB_LABEL,
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
PART_OF_LABEL = "app.kubernetes.io/part-of"
PART_OF_LABEL_VALUE = "devops-cli-stack"
MANAGED_BY_LABEL = "app.kubernetes.io/managed-by"
MANAGED_BY_LABEL_VALUE = "devops-cli"
OWNER_LABEL = "roadmap.devops-cli/owner"
REPO_LABEL = "roadmap.devops-cli/repo"
ITEM_LABEL = "roadmap.devops-cli/item"
REPOSITORY_ANNOTATION = "roadmap.devops-cli/repository"
# The input key of a fix unit (`<pr>:<head>:<check>`), its attempt, and the outcome that the
# Service read from the result line of an ended unit (#5027).
UNIT_KEY_ANNOTATION = "roadmap.devops-cli/unit-key"
ATTEMPT_ANNOTATION = "roadmap.devops-cli/attempt"
OUTCOME_ANNOTATION = "roadmap.devops-cli/outcome"


@dataclass(frozen=True)
class JobTemplate:
    """A CronJob that Jobs come from: its name, which also starts the name of each Job, and the
    name of the container whose args a Job changes."""

    cronjob: str
    container: str


DEFAULT_TEMPLATE = JobTemplate(cronjob="devops-cli", container="devops-cli")
RUNNER_TEMPLATE = JobTemplate(cronjob="devops-cli-runner", container="runner")
STAGE_TEMPLATE = JobTemplate(cronjob="roadmap-stage", container="stage")
PLANNER_TEMPLATE = JobTemplate(cronjob="devops-cli-planner-run", container="runner")
# The pod label of a planner run Job: the deny-all NetworkPolicy and the admission policy select
# it, and no egress allow policy does (ADR 0018, #4003).
PLANNER_NAME_LABEL_VALUE = "devops-cli-planner-run"
# The component of the runner and stage Jobs and of their pods: `roadmap-<row>` (ADR 0022).
RUNNER_COMPONENT = f"roadmap-{ServiceRow.IMPLEMENT}"
STAGE_COMPONENT = f"roadmap-{ServiceRow.STAGE}"
FIX_CHECKS_COMPONENT = f"roadmap-{ServiceRow.FIX_CHECKS}"
# The components of the Jobs that run a model: they share the limit `roadmap.model_jobs` (#5027).
MODEL_COMPONENTS = frozenset({RUNNER_COMPONENT, STAGE_COMPONENT, FIX_CHECKS_COMPONENT})


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


def runner_job_name(repo: RepoRef, item: int | None = None) -> str:
    """The ad hoc name of the runner Job: `devops-cli-implement-<slug>-<item>-<6 hex>` (or with no
    item, `devops-cli-implement-<slug>-<6 hex>`), 63 characters at most (ADR 0022)."""
    return repo.adhoc_name(ServiceRow.IMPLEMENT.value, item)


def runner_job_labels(repo: RepoRef, item: int | None = None) -> dict[str, str]:
    """The labels of the runner Job of `repo` and of its pod: the component, part-of, managed-by,
    owner, repository, item (when given), and the legacy implement-repo label."""
    labels = {
        COMPONENT_LABEL: RUNNER_COMPONENT,
        PART_OF_LABEL: PART_OF_LABEL_VALUE,
        MANAGED_BY_LABEL: MANAGED_BY_LABEL_VALUE,
        OWNER_LABEL: repo.owner_label,
        REPO_LABEL: repo.repo_label,
        CONST_ROADMAP_IMPLEMENT_JOB_LABEL: repo.id,
    }
    if item is not None:
        labels[ITEM_LABEL] = str(item)
    return labels


def stage_job_name(repo: RepoRef, item: int, plan_key: str) -> str:
    """The name of the stage Job of `item` for the plan input `plan_key`, such as the hash of the
    text of the item: `devops-cli-stage-<slug>-<item>-<10 hex>`, 63 characters at most. The same
    inputs give the same name, so a second create of the Job gets 409 (ADR 0022)."""
    return repo.unit_name(ServiceRow.STAGE, plan_key, item)


def stage_job_labels(repo: RepoRef, item: int) -> dict[str, str]:
    """The labels of the stage Job of `item` and of its pod: the component, part-of, managed-by,
    owner, repository and item."""
    return {
        COMPONENT_LABEL: STAGE_COMPONENT,
        PART_OF_LABEL: PART_OF_LABEL_VALUE,
        MANAGED_BY_LABEL: MANAGED_BY_LABEL_VALUE,
        OWNER_LABEL: repo.owner_label,
        REPO_LABEL: repo.repo_label,
        ITEM_LABEL: str(item),
    }


def stage_jobs_selector() -> dict[str, str]:
    """The label that selects each stage Job of every repository and no other Job: the component
    of `stage_job_labels`. The stage row of the Service lists its Jobs by it, counts them against
    `roadmap.stage.jobs`, and takes the Jobs of its repository by their owner and repository labels
    (#4559)."""
    return {COMPONENT_LABEL: STAGE_COMPONENT}


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
    repo: RepoRef | str | None = None,
    item: int | None = None,
    row: ServiceRow | str | None = None,
    suspend: bool = False,
) -> dict[str, Any]:
    """The Job the CronJob's template makes, with only args, name, labels, `env`, the deadline,
    the annotations, the `resources` and the suspension changed.

    The labels go on the Job and on its pods, so `-l app.kubernetes.io/name=devops-cli-job`
    finds both. With `repo`, the owner, repo and repository annotations are set on the Job and its
    pod, as are the component and stack labels. The implement Job of the runner template also
    gets the label `implement-repo`, and a Job of another row does not. `deadline` replaces the
    `activeDeadlineSeconds` of the template. `resources` maps `requests` and `limits` to the
    values that replace those of the container, such as `{"requests": {"memory": "2Gi"}}`.
    `suspend` creates the Job suspended: the Job controller starts no pod until a patch resumes it.
    """
    job_template = cronjob["spec"]["jobTemplate"]
    spec = copy.deepcopy(job_template["spec"])
    pod_template = spec["template"]

    extra_labels: dict[str, str] = {}
    extra_annotations: dict[str, str] = {}

    determined_row = row or (
        ServiceRow.IMPLEMENT.value
        if template == RUNNER_TEMPLATE
        else (ServiceRow.STAGE.value if template == STAGE_TEMPLATE else None)
    )
    if repo is not None:
        repo_ref = repo if isinstance(repo, RepoRef) else RepoRef(repo)
        extra_labels[OWNER_LABEL] = repo_ref.owner_label
        extra_labels[REPO_LABEL] = repo_ref.repo_label
        if item is not None:
            extra_labels[ITEM_LABEL] = str(item)
        if template == RUNNER_TEMPLATE and determined_row == ServiceRow.IMPLEMENT.value:
            extra_labels[CONST_ROADMAP_IMPLEMENT_JOB_LABEL] = repo_ref.id
        extra_annotations[REPOSITORY_ANNOTATION] = repo_ref.key

    if determined_row:
        extra_labels[COMPONENT_LABEL] = f"roadmap-{determined_row}"
        extra_labels[PART_OF_LABEL] = PART_OF_LABEL_VALUE
        extra_labels[MANAGED_BY_LABEL] = MANAGED_BY_LABEL_VALUE

    merged_labels = {**extra_labels, **(labels or {})}
    if template == PLANNER_TEMPLATE:
        merged_labels.setdefault(JOB_NAME_LABEL, PLANNER_NAME_LABEL_VALUE)
    merged_annotations = {**extra_annotations, **(annotations or {})}

    pod_template["metadata"] = _labelled(pod_template.get("metadata"), merged_labels)
    if merged_annotations:
        pod_template["metadata"]["annotations"] = {
            **pod_template["metadata"].get("annotations", {}),
            **merged_annotations,
        }

    container = template_container(pod_template["spec"], template)
    container["args"] = list(args)
    _with_env(container, env)
    _with_resources(container, resources)

    metadata = _labelled(job_template.get("metadata"), merged_labels)
    metadata.update(name=name, namespace=JOB_NAMESPACE)
    if merged_annotations:
        metadata["annotations"] = {**metadata.get("annotations", {}), **merged_annotations}

    if deadline is not None:
        spec["activeDeadlineSeconds"] = deadline
    if suspend:
        spec["suspend"] = True
    return {"apiVersion": "batch/v1", "kind": "Job", "metadata": metadata, "spec": spec}
