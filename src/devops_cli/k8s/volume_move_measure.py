"""Measure the copy path of a volume move: twenty copies of 100 MiB between two nodes (#3701).

The move copies a claim with one pipe between two `kubectl exec` streams (#3695), so this measure
plans the same `copy_argv` and reads each side with `digest_args`. A person runs it against a
cluster, because the runner holds no kubectl, and records its report in #3953.

The measure makes one temporary namespace with two claims and two pods, one pod on each named
node. Each copy writes fresh random data to the source claim, empties the destination claim, runs
the pipe of the move and compares the two digests. The run deletes the namespace when it ends,
whether the copies passed or failed.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Final

from devops_cli.config.commands import BIN_BASH, build_kubectl_cmd
from devops_cli.config.constants import (
    CONST_K8S_HOSTNAME_LABEL,
    CONST_K8S_VOLUME_MOVE_DESTINATION_DIR,
    CONST_K8S_VOLUME_MOVE_DESTINATION_SUFFIX,
    CONST_K8S_VOLUME_MOVE_LABELS,
    CONST_K8S_VOLUME_MOVE_SOURCE_DIR,
    CONST_K8S_VOLUME_MOVE_SOURCE_SUFFIX,
)
from devops_cli.config.defaults import (
    DEFAULT_K8S_VOLUME_MOVE_IMAGE,
    DEFAULT_K8S_VOLUME_MOVE_WAIT_SECONDS,
)
from devops_cli.dry_run.requests import PlannedRequest
from devops_cli.exceptions.k8s import VolumeMoveRefusedError
from devops_cli.k8s.volume_move import copy_argv, digest_args, empty_args

MEASURE_COPIES: Final[int] = 20
MEASURE_BYTES: Final[int] = 104_857_600
_MEASURE_NAMESPACE: Final[str] = "volume-move-measure"
_MEASURE_CLAIM_SIZE: Final[str] = "1Gi"
_MEASURE_SOURCE_FILE: Final[str] = "data.bin"
_SAME_NODE: Final[str] = (
    "The measure needs two different nodes, and it got {node} for both the source and the target."
)


@dataclass(frozen=True)
class MeasurePlan:
    """The temporary namespace, the two nodes and the counts of one measure run."""

    namespace: str
    source_node: str
    target_node: str
    storage_class: str
    copies: int = MEASURE_COPIES
    bytes_per_copy: int = MEASURE_BYTES

    @property
    def source_claim(self) -> str:
        """The claim on the source node, which holds the random data of each copy."""
        return f"measure{CONST_K8S_VOLUME_MOVE_SOURCE_SUFFIX}"

    @property
    def destination_claim(self) -> str:
        """The claim on the target node, which receives each copy."""
        return f"measure{CONST_K8S_VOLUME_MOVE_DESTINATION_SUFFIX}"

    @property
    def source_pod(self) -> str:
        """The pod that runs the source side of the pipe."""
        return f"measure{CONST_K8S_VOLUME_MOVE_SOURCE_SUFFIX}"

    @property
    def destination_pod(self) -> str:
        """The pod that runs the destination side of the pipe."""
        return f"measure{CONST_K8S_VOLUME_MOVE_DESTINATION_SUFFIX}"


def plan_measure(source_node: str, target_node: str, storage_class: str) -> MeasurePlan:
    """The plan of one measure run, which refuses the same node for both sides."""
    if source_node == target_node:
        raise VolumeMoveRefusedError(_SAME_NODE.format(node=source_node))
    return MeasurePlan(
        namespace=_MEASURE_NAMESPACE,
        source_node=source_node,
        target_node=target_node,
        storage_class=storage_class,
    )


def claim_manifests(plan: MeasurePlan) -> list[dict[str, Any]]:
    """The two claims, made fresh so local-path binds each one on the node of its pod."""
    return [
        _claim_manifest(plan, plan.source_claim),
        _claim_manifest(plan, plan.destination_claim),
    ]


def _claim_manifest(plan: MeasurePlan, name: str) -> dict[str, Any]:
    return {
        "apiVersion": "v1",
        "kind": "PersistentVolumeClaim",
        "metadata": {
            "name": name,
            "namespace": plan.namespace,
            "labels": dict(CONST_K8S_VOLUME_MOVE_LABELS),
        },
        "spec": {
            "accessModes": ["ReadWriteOnce"],
            "storageClassName": plan.storage_class,
            "resources": {"requests": {"storage": _MEASURE_CLAIM_SIZE}},
        },
    }


def pod_manifests(plan: MeasurePlan) -> list[dict[str, Any]]:
    """The two pods, each pinned to its node, read-write on its claim and holding no token."""
    return [
        _pod_manifest(
            plan,
            pod=plan.source_pod,
            claim=plan.source_claim,
            node=plan.source_node,
            directory=CONST_K8S_VOLUME_MOVE_SOURCE_DIR,
        ),
        _pod_manifest(
            plan,
            pod=plan.destination_pod,
            claim=plan.destination_claim,
            node=plan.target_node,
            directory=CONST_K8S_VOLUME_MOVE_DESTINATION_DIR,
        ),
    ]


def _pod_manifest(
    plan: MeasurePlan, *, pod: str, claim: str, node: str, directory: str
) -> dict[str, Any]:
    return {
        "apiVersion": "v1",
        "kind": "Pod",
        "metadata": {
            "name": pod,
            "namespace": plan.namespace,
            "labels": dict(CONST_K8S_VOLUME_MOVE_LABELS),
        },
        "spec": {
            "restartPolicy": "Never",
            "terminationGracePeriodSeconds": 0,
            "automountServiceAccountToken": False,
            "nodeSelector": {CONST_K8S_HOSTNAME_LABEL: node},
            "containers": [
                {
                    "name": "copy",
                    "image": DEFAULT_K8S_VOLUME_MOVE_IMAGE,
                    "command": ["sleep", "infinity"],
                    "volumeMounts": [{"name": "data", "mountPath": directory, "readOnly": False}],
                }
            ],
            "volumes": [
                {
                    "name": "data",
                    "persistentVolumeClaim": {"claimName": claim, "readOnly": False},
                }
            ],
        },
    }


def random_data_args(plan: MeasurePlan) -> list[str]:
    """The request that replaces the source file with fresh random data of one copy."""
    path = f"{CONST_K8S_VOLUME_MOVE_SOURCE_DIR}/{_MEASURE_SOURCE_FILE}"
    script = f"head -c {plan.bytes_per_copy} /dev/urandom > {path}"
    return ["exec", plan.source_pod, "-n", plan.namespace, "--", "bash", "-c", script]


def measure_requests(plan: MeasurePlan, context: str | None) -> list[PlannedRequest]:
    """Every request of a run, in order, as the dry run of the measure lists them."""
    manifests: list[tuple[dict[str, Any], str]] = [
        (_namespace_manifest(plan), f"namespace {plan.namespace}")
    ]
    manifests.extend(
        (manifest, f"claim {manifest['metadata']['name']}") for manifest in claim_manifests(plan)
    )
    manifests.extend(
        (manifest, f"pod {manifest['metadata']['name']}") for manifest in pod_manifests(plan)
    )
    requests = [_planned_create(context, target, manifest) for manifest, target in manifests]
    requests.extend(
        _wait_request(context, plan, pod) for pod in (plan.source_pod, plan.destination_pod)
    )
    for number in range(1, plan.copies + 1):
        requests.extend(_copy_requests(plan, context, number))
    requests.append(_delete_namespace_request(plan, context))
    return requests


def _namespace_manifest(plan: MeasurePlan) -> dict[str, Any]:
    return {
        "apiVersion": "v1",
        "kind": "Namespace",
        "metadata": {
            "name": plan.namespace,
            "labels": dict(CONST_K8S_VOLUME_MOVE_LABELS),
        },
    }


def _planned_create(context: str | None, target: str, manifest: dict[str, Any]) -> PlannedRequest:
    return _planned(["create", "-f", "-", "-o", "name"], context, target, stdin=manifest)


def _wait_request(context: str | None, plan: MeasurePlan, pod: str) -> PlannedRequest:
    args = [
        "wait",
        f"pod/{pod}",
        "-n",
        plan.namespace,
        "--for=condition=Ready",
        f"--timeout={DEFAULT_K8S_VOLUME_MOVE_WAIT_SECONDS}s",
    ]
    return _planned(args, context, f"pod {pod}")


def _copy_requests(plan: MeasurePlan, context: str | None, number: int) -> list[PlannedRequest]:
    copy = f"copy {number}/{plan.copies}"
    stream = tuple(copy_argv(plan.namespace, plan.source_pod, plan.destination_pod, context))
    return [
        _planned(random_data_args(plan), context, f"the source of {copy}"),
        _planned(
            empty_args(plan.destination_pod, plan.namespace), context, f"the destination of {copy}"
        ),
        PlannedRequest(method=BIN_BASH, target=copy, argv=stream),
        _planned(
            digest_args(plan.source_pod, plan.namespace, CONST_K8S_VOLUME_MOVE_SOURCE_DIR),
            context,
            f"the source of {copy}",
        ),
        _planned(
            digest_args(
                plan.destination_pod, plan.namespace, CONST_K8S_VOLUME_MOVE_DESTINATION_DIR
            ),
            context,
            f"the destination of {copy}",
        ),
    ]


def _delete_namespace_request(plan: MeasurePlan, context: str | None) -> PlannedRequest:
    args = [
        "delete",
        "namespace",
        plan.namespace,
        "--wait=true",
        f"--timeout={DEFAULT_K8S_VOLUME_MOVE_WAIT_SECONDS}s",
    ]
    return _planned(args, context, f"namespace {plan.namespace}")


def _planned(
    args: Sequence[str],
    context: str | None,
    target: str,
    *,
    stdin: dict[str, Any] | None = None,
) -> PlannedRequest:
    return PlannedRequest(
        method=f"kubectl {args[0]}",
        target=target,
        argv=tuple(build_kubectl_cmd(args, context)),
        stdin=json.dumps(stdin, indent=2) if stdin is not None else None,
    )


__all__ = [
    "MEASURE_BYTES",
    "MEASURE_COPIES",
    "MeasurePlan",
    "claim_manifests",
    "measure_requests",
    "plan_measure",
    "pod_manifests",
    "random_data_args",
]
