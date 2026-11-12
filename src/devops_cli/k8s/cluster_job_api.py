"""The Kubernetes API calls of the Jobs that the roadmap Service creates (#2667).

The Service builds a Job from a suspended CronJob's template (`cluster_job.build_job`), creates
it, lists the Jobs of a repository, and reads the tail of the log of a Job's pod. It uses the
process's `KubernetesService`, so a pod connects with its projected service account token and a
test connects to the fake cluster. The generic `CustomObjectsApi` reaches `batch/v1` `jobs` and
`cronjobs`, as it reaches the custom resources, and returns the objects as dicts.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any

from devops_cli.exceptions.k8s import ClusterJobError
from devops_cli.k8s.api import api_error_type
from devops_cli.k8s.cluster_job import (
    DEFAULT_TEMPLATE,
    JOB_NAMESPACE,
    JOB_POD_SELECTOR_LABEL,
    JobTemplate,
    build_job,
    image_digest,
    job_name,
)
from devops_cli.k8s.service import KubernetesService, read_pod_log_text
from devops_cli.lang import MESSAGES

_BATCH = ("batch", "v1")
_APPS = ("apps", "v1")
_NOT_FOUND = 404
# The conditions of a Job that ended.
_END_CONDITIONS = frozenset({"Complete", "Failed"})


class JobState(StrEnum):
    """Where a Job is: it has not ended, or it has the condition Complete or Failed."""

    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


@dataclass(frozen=True)
class ClusterJob:
    """A Job of namespace `devops` as the API lists it: its state, the time its pod started (None
    until the Job controller sets it), the `activeDeadlineSeconds` in force (None when it sets
    none), its annotations, and the time it got the condition Complete or Failed (None until it
    ends, #4845)."""

    name: str
    state: JobState
    started: datetime | None = None
    deadline: int | None = None
    annotations: Mapping[str, str] = field(default_factory=dict[str, str])
    ended: datetime | None = None


def _started(job: Mapping[str, Any]) -> datetime | None:
    """The `status.startTime` of a Job as a time, or None when the controller has not set it."""
    text = (job.get("status") or {}).get("startTime")
    return datetime.fromisoformat(text) if text else None


def _ended(job: Mapping[str, Any]) -> datetime | None:
    """The `lastTransitionTime` of the condition Complete or Failed of a Job as a time, or None
    while the Job runs or when the controller set no time."""
    for condition in ((job.get("status") or {}).get("conditions")) or []:
        if condition.get("type") in _END_CONDITIONS and condition.get("status") == "True":
            text = condition.get("lastTransitionTime")
            return datetime.fromisoformat(text) if text else None
    return None


def _listed(job: Mapping[str, Any]) -> ClusterJob:
    return ClusterJob(
        job["metadata"]["name"],
        job_state(job),
        started=_started(job),
        deadline=(job.get("spec") or {}).get("activeDeadlineSeconds"),
        annotations=dict(job["metadata"].get("annotations") or {}),
        ended=_ended(job),
    )


def job_state(job: Mapping[str, Any]) -> JobState:
    """The state of a Job object: Complete or Failed once the Job controller says so."""
    conditions = ((job.get("status") or {}).get("conditions")) or []
    true = {c.get("type") for c in conditions if c.get("status") == "True"}
    if "Complete" in true:
        return JobState.SUCCEEDED
    return JobState.FAILED if "Failed" in true else JobState.RUNNING


class ClusterJobs:
    """Create, list and read the Jobs of namespace `devops` through the Kubernetes API."""

    def __init__(self, service: KubernetesService | None = None) -> None:
        self._service = service or KubernetesService.get_instance()

    def create(
        self,
        args: list[str],
        *,
        template: JobTemplate = DEFAULT_TEMPLATE,
        env: Mapping[str, str] | None = None,
        labels: Mapping[str, str] | None = None,
        name: str | None = None,
        cronjob: dict[str, Any] | None = None,
        deadline: int | None = None,
        annotations: Mapping[str, str] | None = None,
        resources: Mapping[str, Mapping[str, str]] | None = None,
    ) -> str:
        """Create a Job from the template's CronJob and return its name: `name`, else a new one.
        `deadline` replaces the `activeDeadlineSeconds` of the template, `annotations` go on
        the Job, and `resources` replaces the named request and limit values of its container.
        A caller that records the Job before it creates it chooses the name with `job_name`. A
        caller that records the digest of the image passes the `cronjob` that it read with
        `cronjob()`, so the record and the Job come from one read.

        Raises ClusterJobError when the CronJob is missing or the API refuses a call.
        """
        cronjob = cronjob or self.cronjob(template)
        name = name or job_name(template=template)
        job = build_job(
            cronjob,
            args,
            name,
            template=template,
            env=env,
            labels=labels,
            deadline=deadline,
            annotations=annotations,
            resources=resources,
        )
        try:
            self._service.custom_objects_api().create_namespaced_custom_object(
                *_BATCH, JOB_NAMESPACE, "jobs", job
            )
        except api_error_type() as error:
            raise self._refused("create Job", error) from error
        return name

    def template_digest(self, template: JobTemplate) -> str | None:
        """The digest of the image in the template's CronJob, as `image_digest` reads it.

        Raises ClusterJobError when the CronJob is missing, has no such container, or the API
        refuses the read.
        """
        return image_digest(self.cronjob(template), template)

    def deployment_digest(self, name: str, container: str) -> str | None:
        """The digest in the image of `container` of Deployment `name`: the text after the `@`,
        as `sha256:<hex>`, or None when the image names no digest. Image Updater writes it there.

        Raises ClusterJobError when the Deployment is missing, has no such container, or the API
        refuses the read.
        """
        try:
            deployment = self._service.custom_objects_api().get_namespaced_custom_object(
                *_APPS, JOB_NAMESPACE, "deployments", name
            )
        except api_error_type() as error:
            if getattr(error, "status", None) == _NOT_FOUND:
                raise ClusterJobError(
                    MESSAGES.k8s.job_deployment_missing.format(deployment=name)
                ) from error
            raise self._refused("read Deployment", error) from error
        for candidate in deployment["spec"]["template"]["spec"]["containers"]:
            if candidate.get("name") == container:
                return str(candidate.get("image", "")).partition("@")[2] or None
        raise ClusterJobError(
            MESSAGES.k8s.job_deployment_no_container.format(deployment=name, container=container)
        )

    def list_jobs(self, labels: Mapping[str, str]) -> tuple[ClusterJob, ...]:
        """The Jobs that carry every one of `labels`, selected by the API server."""
        custom = self._service.custom_objects_api()
        selector = ",".join(f"{key}={value}" for key, value in labels.items())
        try:
            listed = custom.list_namespaced_custom_object(
                *_BATCH, JOB_NAMESPACE, "jobs", label_selector=selector
            )
        except api_error_type() as error:
            raise self._refused("list Jobs", error) from error
        return tuple(_listed(job) for job in listed.get("items", []))

    def patch_job(
        self,
        name: str,
        *,
        deadline: int | None = None,
        annotations: Mapping[str, str] | None = None,
    ) -> None:
        """Set `activeDeadlineSeconds` of Job `name` to `deadline` when given, and merge
        `annotations` into its annotations. The API server accepts a new deadline on a running
        Job, and the Job controller applies it at once.

        Raises ClusterJobError when the API refuses the patch.
        """
        body: dict[str, Any] = {}
        if annotations:
            body["metadata"] = {"annotations": dict(annotations)}
        if deadline is not None:
            body["spec"] = {"activeDeadlineSeconds": deadline}
        try:
            self._service.custom_objects_api().patch_namespaced_custom_object(
                *_BATCH, JOB_NAMESPACE, "jobs", name, body
            )
        except api_error_type() as error:
            raise self._refused("patch Job", error) from error

    def log_tail(self, name: str, lines: int) -> str:
        """The last `lines` lines of the log of Job `name`'s pod as text, or "" when the Job has no
        pod. The text is what the pod wrote, decoded as UTF-8 (`read_pod_log_text`)."""
        core = self._service.core_api()
        try:
            pods = core.list_namespaced_pod(
                JOB_NAMESPACE, label_selector=f"{JOB_POD_SELECTOR_LABEL}={name}"
            )
            if not pods.items:
                return ""
            return read_pod_log_text(
                core, pods.items[0].metadata.name, JOB_NAMESPACE, tail_lines=lines
            )
        except api_error_type() as error:
            raise self._refused("read the log of a Job", error) from error

    def cronjob(self, template: JobTemplate) -> dict[str, Any]:
        """The CronJob of `template`, as the API returns it.

        Raises ClusterJobError when the CronJob is missing or the API refuses the read.
        """
        try:
            return dict(
                self._service.custom_objects_api().get_namespaced_custom_object(
                    *_BATCH, JOB_NAMESPACE, "cronjobs", template.cronjob
                )
            )
        except api_error_type() as error:
            if getattr(error, "status", None) == _NOT_FOUND:
                raise ClusterJobError(
                    MESSAGES.k8s.job_cronjob_missing.format(cronjob=template.cronjob)
                ) from error
            raise self._refused("read CronJob", error) from error

    @staticmethod
    def _refused(action: str, error: Exception) -> ClusterJobError:
        status = getattr(error, "status", "?")
        reason = getattr(error, "reason", "") or ""
        return ClusterJobError(
            MESSAGES.k8s.job_api_refused.format(action=action, status=status, reason=reason)
        )
