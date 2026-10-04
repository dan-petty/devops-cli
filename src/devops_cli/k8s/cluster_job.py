"""Jobs that run one devops command in the cluster, built from CronJob devops-cli's template.

The suspended CronJob `devops/devops-cli` keeps the pod spec in git: its security context, the
`devops-cli` Secret through `envFrom`, the config and the volumes. A Job made from it changes
only the container's args, its name and one label, so it passes the namespace's `restricted`
Pod Security and cannot drift from git.
"""

from __future__ import annotations

import copy
import secrets
from datetime import UTC, datetime
from typing import Any

from devops_cli.exceptions.k8s import ClusterJobError

JOB_NAMESPACE = "devops"
JOB_CRONJOB = "devops-cli"
JOB_CONTAINER = "devops-cli"
JOB_NAME_LABEL = "app.kubernetes.io/name"
JOB_NAME_LABEL_VALUE = "devops-cli-job"
# Set on every pod by the Job controller.
JOB_POD_SELECTOR_LABEL = "batch.kubernetes.io/job-name"


def job_name(now: datetime | None = None) -> str:
    """`devops-cli-<UTC yyyymmdd-hhmmss>-<4 hex>`."""
    stamp = (now or datetime.now(UTC)).strftime("%Y%m%d-%H%M%S")
    return f"{JOB_CRONJOB}-{stamp}-{secrets.token_hex(2)}"


def _labelled(metadata: dict[str, Any] | None) -> dict[str, Any]:
    """A copy of the metadata carrying the cluster-job label."""
    labelled = copy.deepcopy(metadata or {})
    labelled["labels"] = {**labelled.get("labels", {}), JOB_NAME_LABEL: JOB_NAME_LABEL_VALUE}
    return labelled


def build_job(cronjob: dict[str, Any], args: list[str], name: str) -> dict[str, Any]:
    """The Job the CronJob's template makes, with only args, name and label changed.

    The label goes on the Job and on its pods, so `-l app.kubernetes.io/name=devops-cli-job`
    finds both.
    """
    template = cronjob["spec"]["jobTemplate"]
    spec = copy.deepcopy(template["spec"])
    pod_template = spec["template"]
    pod_template["metadata"] = _labelled(pod_template.get("metadata"))
    container = next(
        (c for c in pod_template["spec"]["containers"] if c.get("name") == JOB_CONTAINER), None
    )
    if container is None:
        raise ClusterJobError(
            f"CronJob {JOB_NAMESPACE}/{JOB_CRONJOB} has no container {JOB_CONTAINER}"
        )
    container["args"] = list(args)
    metadata = _labelled(template.get("metadata"))
    metadata.update(name=name, namespace=JOB_NAMESPACE)
    return {"apiVersion": "batch/v1", "kind": "Job", "metadata": metadata, "spec": spec}
