"""The stage CronJob `roadmap-stage`, the template of the Job that plans one item (#5483)."""

from __future__ import annotations

import functools
from typing import Any

import yaml

from devops_cli.config.constants import (
    CONST_ROADMAP_STAGE_JOB_DEADLINE_SECONDS,
    CONST_ROADMAP_STAGE_JOB_SECRET_KEYS,
)
from devops_cli.k8s.cluster_job import STAGE_TEMPLATE
from tests.gate.k8s_render import kustomize
from tests.support.paths import REPO_ROOT

DEVOPS_DIR = REPO_ROOT / "k8s" / "devops"


SERVICE_IMAGE = "ghcr.io/dan-petty/devops-cli/service"


@functools.cache
def _rendered() -> tuple[dict[str, Any], ...]:
    documents = yaml.load_all(kustomize(DEVOPS_DIR).stdout, Loader=yaml.CSafeLoader)
    return tuple(document for document in documents if isinstance(document, dict))


def _cronjob(name: str) -> dict[str, Any]:
    (found,) = (
        document
        for document in _rendered()
        if document["kind"] == "CronJob" and document["metadata"]["name"] == name
    )
    return found


def _pod(name: str) -> dict[str, Any]:
    pod: dict[str, Any] = _cronjob(name)["spec"]["jobTemplate"]["spec"]["template"]["spec"]
    return pod


def _stage_container() -> dict[str, Any]:
    (container,) = _pod(STAGE_TEMPLATE.cronjob)["containers"]
    return container


def check_the_stage_cronjob_is_a_suspended_template_of_the_service_image() -> None:
    cronjob = _cronjob(STAGE_TEMPLATE.cronjob)
    pod = _pod(STAGE_TEMPLATE.cronjob)
    container = _stage_container()

    assert (
        cronjob["metadata"]["namespace"],
        cronjob["spec"]["suspend"],
        pod["restartPolicy"],
        pod["serviceAccountName"],
        pod["automountServiceAccountToken"],
        container["name"],
        container["image"],
        container["imagePullPolicy"],
        "envFrom" in container,
        container["resources"],
    ) == (
        "devops",
        True,
        "Never",
        "devops-cli",
        False,
        STAGE_TEMPLATE.container,
        SERVICE_IMAGE,
        "IfNotPresent",
        False,
        {"requests": {"cpu": "250m", "memory": "1Gi"}, "limits": {"cpu": "1", "memory": "2Gi"}},
    )


def check_the_stage_job_runs_again_only_after_an_eviction_and_ends_by_its_deadline() -> None:
    """Exit 75 is the `evicted` exit of `attempt_kill.py`: the pod runs again, at most twice. A pod
    that a disruption ends runs again and does not count. Any other exit fails the Job, so the
    Service decides each later attempt (#5483)."""
    job = _cronjob(STAGE_TEMPLATE.cronjob)["spec"]["jobTemplate"]["spec"]

    assert (job["activeDeadlineSeconds"], job["backoffLimit"], job["podFailurePolicy"]) == (
        CONST_ROADMAP_STAGE_JOB_DEADLINE_SECONDS,
        2,
        {
            "rules": [
                {"action": "Ignore", "onPodConditions": [{"type": "DisruptionTarget"}]},
                {
                    "action": "FailJob",
                    "onExitCodes": {
                        "containerName": STAGE_TEMPLATE.container,
                        "operator": "NotIn",
                        "values": [75],
                    },
                },
            ]
        },
    )


def check_the_stage_pod_has_time_to_check_in_after_a_sigterm() -> None:
    """After the time budget, a SIGTERM makes the Job check in, with up to 4 GitHub writes in the
    request budget of the pod. The default grace of 30 s can cut them with a SIGKILL."""
    assert _pod(STAGE_TEMPLATE.cronjob)["terminationGracePeriodSeconds"] == 120


def check_the_stage_container_takes_two_keys_of_the_secret_and_no_other_value() -> None:
    """The private key of the App and the key of the gateway. The MCP client of the stage job is
    off (`roadmap.stage.mcp`), so the pod has no MCP token: the server accepts one token for every
    role."""
    env = _stage_container()["env"]
    sourced = [entry for entry in env if "valueFrom" in entry]

    assert [(entry["name"], entry["valueFrom"]) for entry in sourced] == [
        (key, {"secretKeyRef": {"name": "devops-cli", "key": key}})
        for key in CONST_ROADMAP_STAGE_JOB_SECRET_KEYS
    ]
    assert CONST_ROADMAP_STAGE_JOB_SECRET_KEYS == (
        "DEVOPS_CLI_SERVICE_GITHUB_APP_PRIVATE_KEY",
        "DEVOPS_CLI_AI_API_KEY",
    )


def check_the_stage_pod_reports_its_telemetry_as_roadmap_stage() -> None:
    env = {entry["name"]: entry.get("value") for entry in _stage_container()["env"]}
    labels = _cronjob(STAGE_TEMPLATE.cronjob)["spec"]["jobTemplate"]["spec"]["template"][
        "metadata"
    ]["labels"]

    assert (
        env["OTEL_SERVICE_NAME"],
        env["OTEL_RESOURCE_ATTRIBUTES"],
        env["DEVOPS_CLI_CONFIG"],
        env["DEVOPS_CLI_DATA_DIR"],
        labels["app.kubernetes.io/name"],
        labels["app.kubernetes.io/component"],
    ) == (
        "roadmap-stage",
        "service.instance.id=roadmap-stage",
        "/config/devops-cli.yaml",
        "/home/devops/.data",
        "devops-cli-job",
        "roadmap-stage",
    )


def check_the_stage_pod_is_restricted_as_the_other_job_pods() -> None:
    pod = _pod(STAGE_TEMPLATE.cronjob)
    reference = _pod("devops-cli-runner")

    assert (
        pod["securityContext"],
        _stage_container()["securityContext"],
        sorted((volume["name"], sorted(volume)) for volume in pod["volumes"]),
    ) == (
        reference["securityContext"],
        reference["containers"][0]["securityContext"],
        [
            ("config", ["configMap", "name"]),
            ("home", ["emptyDir", "name"]),
            ("tmp", ["emptyDir", "name"]),
        ],
    )
