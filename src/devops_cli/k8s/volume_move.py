"""Move a local-path claim to a volume on another node, and bind the claim to that volume (#2186).

`plan_volume_move` only reads: the claim, its volume, the nodes, the pods that mount the claim and
their workloads, the leftovers of an earlier move and the Argo CD Applications. It refuses a move
that cannot run safely, and returns the plan with the real names. `run_volume_move` runs the steps
that `describe_volume_move` names, the procedure of `k8s/README.md` (Local-Path Volume Placement):
it pauses Argo CD from the top down, copies the data with GNU tar through the API server, compares
the two sides, and binds the claim to the new volume.

Until the run sends the delete of the old claim, a failure undoes each change the run made, in
reverse order. From that request on, a failure leaves Argo CD paused and raises
`VolumeMoveStrandedError` with the saved claim: a self-heal would make an empty claim in place of
the moved one.

`dry_run_volume_move` makes no request: it lists the requests a move would make, in order, with a
placeholder for each value that a read gives.
"""

from __future__ import annotations

import itertools
import json
import shlex
import subprocess
from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from functools import partial
from pathlib import Path
from typing import Any

from devops_cli.config.commands import BIN_BASH, build_kubectl_cmd
from devops_cli.config.constants import (
    CONST_ARGOCD_TRACKING_ID_ANNOTATION,
    CONST_K8S_ARGOCD_PAUSE_PARENTS,
    CONST_K8S_CLAIM_CONTROLLER_ANNOTATIONS,
    CONST_K8S_CLAIM_PHASE_BOUND,
    CONST_K8S_CONTROL_PLANE_LABEL,
    CONST_K8S_HOSTNAME_LABEL,
    CONST_K8S_LABEL_RE,
    CONST_K8S_LAST_APPLIED_ANNOTATION,
    CONST_K8S_POD_PHASE_RUNNING,
    CONST_K8S_RECLAIM_RETAIN,
    CONST_K8S_RECREATED_CLAIM_METADATA_KEYS,
    CONST_K8S_RETENTION_DELETE,
    CONST_K8S_SCALABLE_WORKLOAD_KINDS,
    CONST_K8S_SUBDOMAIN_RE,
    CONST_K8S_VOLUME_MOVE_CLAIM_SUFFIX,
    CONST_K8S_VOLUME_MOVE_DESTINATION_DIR,
    CONST_K8S_VOLUME_MOVE_DESTINATION_SUFFIX,
    CONST_K8S_VOLUME_MOVE_DIGEST_SCRIPT,
    CONST_K8S_VOLUME_MOVE_LABELS,
    CONST_K8S_VOLUME_MOVE_SOURCE_DIR,
    CONST_K8S_VOLUME_MOVE_SOURCE_SUFFIX,
)
from devops_cli.config.defaults import (
    DEFAULT_ARGOCD_NAMESPACE,
    DEFAULT_K8S_VOLUME_MOVE_COPY_TIMEOUT_SECONDS,
    DEFAULT_K8S_VOLUME_MOVE_DETAIL_CHARS,
    DEFAULT_K8S_VOLUME_MOVE_IMAGE,
    DEFAULT_K8S_VOLUME_MOVE_REQUEST_TIMEOUT_SECONDS,
    DEFAULT_K8S_VOLUME_MOVE_ROLLOUT_SECONDS,
    DEFAULT_K8S_VOLUME_MOVE_WAIT_SECONDS,
)
from devops_cli.core.process import run_subprocess
from devops_cli.dry_run.requests import PlannedRequest
from devops_cli.exceptions.k8s import (
    VolumeMoveError,
    VolumeMoveRefusedError,
    VolumeMoveStrandedError,
)
from devops_cli.lang import MESSAGES

Progress = Callable[[str], None]

# The index, in `describe_volume_move`, of the step that deletes the old claim.
POINT_OF_NO_RETURN_INDEX = 8
_DIGEST_FIELDS = ("entries", "files", "bytes", "metadata", "content")


@dataclass(frozen=True)
class Workload:
    """A Deployment or StatefulSet whose pods mount the claim, with its replicas before the move."""

    kind: str
    name: str
    replicas: int

    @property
    def ref(self) -> str:
        """The workload as kubectl names it: `<kind>/<name>`."""
        return f"{self.kind}/{self.name}"


@dataclass(frozen=True)
class VolumeMovePlan:
    """What a move reads before it changes anything, with the real names."""

    namespace: str
    claim: str
    old_volume: str
    old_reclaim_policy: str
    source_node: str
    target_node: str
    target_hostname: str
    target_free_bytes: int
    storage_class: str
    size: str
    access_modes: tuple[str, ...]
    volume_mode: str
    workloads: tuple[Workload, ...]
    pods: tuple[str, ...]
    source_tolerations: tuple[dict[str, Any], ...] = ()
    applications: tuple[str, ...] = ()
    paused: tuple[str, ...] = ()

    @property
    def move_claim(self) -> str:
        """The temporary claim that gets the new volume on the target node."""
        return f"{self.claim}{CONST_K8S_VOLUME_MOVE_CLAIM_SUFFIX}"

    @property
    def source_pod(self) -> str:
        """The copy pod that mounts the old claim read-only."""
        return f"{self.claim}{CONST_K8S_VOLUME_MOVE_SOURCE_SUFFIX}"

    @property
    def destination_pod(self) -> str:
        """The copy pod that mounts the temporary claim on the target node."""
        return f"{self.claim}{CONST_K8S_VOLUME_MOVE_DESTINATION_SUFFIX}"


@dataclass(frozen=True)
class CopyDigest:
    """One side of the copy: its counts and digests, as the digest script prints them."""

    entries: int
    files: int
    bytes: int
    metadata: str
    content: str


@dataclass(frozen=True)
class VolumeMoveResult:
    """A finished move: the new volume the claim is bound to, and the saved old claim."""

    plan: VolumeMovePlan
    new_volume: str
    saved_claim: Path
    digest: CopyDigest


@dataclass(frozen=True)
class _Node:
    name: str
    hostname: str
    control_plane: bool
    available: bool


@dataclass(frozen=True)
class _WorkloadState:
    workload: Workload
    when_scaled: str
    application: str | None


# ── kubectl ──────────────────────────────────────────────────────────────────


def _run(argv: Sequence[str], request: str, *, stdin: str | None = None, timeout: float) -> str:
    """Run one request through `run_subprocess` and return its stdout, raising when it fails."""
    try:
        result = run_subprocess(list(argv), input=stdin, quiet=True, timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        raise VolumeMoveError(
            MESSAGES.k8s.volume_move_request_timeout.format(request=request, seconds=timeout)
        ) from exc
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()
        raise VolumeMoveError(
            MESSAGES.k8s.volume_move_request_failed.format(
                request=request,
                code=result.returncode,
                detail=detail[:DEFAULT_K8S_VOLUME_MOVE_DETAIL_CHARS],
            )
        )
    return result.stdout or ""


def _request(args: Sequence[str]) -> str:
    """A kubectl request as a failure names it: the words before its first flag."""
    return " ".join(["kubectl", *itertools.takewhile(lambda arg: not arg.startswith("-"), args)])


def _kubectl(
    args: Sequence[str],
    context: str | None,
    *,
    stdin: str | None = None,
    timeout: float = DEFAULT_K8S_VOLUME_MOVE_REQUEST_TIMEOUT_SECONDS,
) -> str:
    return _run(build_kubectl_cmd(args, context), _request(args), stdin=stdin, timeout=timeout)


def _read_json(args: Sequence[str], context: str | None) -> dict[str, Any]:
    """A kubectl read as JSON; an empty answer, such as `--ignore-not-found`, is `{}`."""
    raw = _kubectl(args, context)
    if not raw.strip():
        return {}
    try:
        decoded = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise VolumeMoveError(
            MESSAGES.k8s.volume_move_bad_output.format(
                request=_request(args),
                detail=raw[:DEFAULT_K8S_VOLUME_MOVE_DETAIL_CHARS],
            )
        ) from exc
    return decoded if isinstance(decoded, dict) else {}


def _wait_args(target: str, namespace: str, condition: str, seconds: int) -> list[str]:
    return ["wait", target, "-n", namespace, f"--for={condition}", f"--timeout={seconds}s"]


def _wait_timeout(seconds: int) -> float:
    """The bound of a `kubectl wait`: its own timeout, then the time of a plain request."""
    return seconds + DEFAULT_K8S_VOLUME_MOVE_REQUEST_TIMEOUT_SECONDS


def _pause_args(application: str, *, enabled: bool) -> list[str]:
    patch = {"spec": {"syncPolicy": {"automated": {"enabled": enabled}}}}
    return [
        "patch",
        "application",
        application,
        "-n",
        DEFAULT_ARGOCD_NAMESPACE,
        "--type",
        "merge",
        "-p",
        json.dumps(patch),
    ]


def _reclaim_args(volume: str, policy: str) -> list[str]:
    patch = {"spec": {"persistentVolumeReclaimPolicy": policy}}
    return ["patch", "pv", volume, "--type", "merge", "-p", json.dumps(patch)]


def _claim_ref_args(volume: str, namespace: str, claim: str) -> list[str]:
    patch = {
        "spec": {
            "claimRef": {
                "name": claim,
                "namespace": namespace,
                "uid": None,
                "resourceVersion": None,
            }
        }
    }
    return ["patch", "pv", volume, "--type", "merge", "-p", json.dumps(patch)]


def _scale_args(workload: str, namespace: str, replicas: int | str) -> list[str]:
    return ["scale", workload, "-n", namespace, f"--replicas={replicas}"]


def _delete_args(kind: str, names: Sequence[str], namespace: str, *, missing_ok: bool) -> list[str]:
    args = ["delete", kind, *names, "-n", namespace, "--wait=true"]
    args.append(f"--timeout={DEFAULT_K8S_VOLUME_MOVE_WAIT_SECONDS}s")
    return [*args, "--ignore-not-found"] if missing_ok else args


def _digest_args(pod: str, namespace: str, directory: str) -> list[str]:
    return [
        "exec",
        pod,
        "-n",
        namespace,
        "--",
        "bash",
        "-c",
        CONST_K8S_VOLUME_MOVE_DIGEST_SCRIPT,
        "digest",
        directory,
    ]


def _empty_destination_args(plan: VolumeMovePlan) -> list[str]:
    return [
        "exec",
        plan.destination_pod,
        "-n",
        plan.namespace,
        "--",
        "find",
        CONST_K8S_VOLUME_MOVE_DESTINATION_DIR,
        "-mindepth",
        "1",
        "-delete",
    ]


def _copy_argv(plan: VolumeMovePlan, context: str | None) -> list[str]:
    """One pipe between two exec streams through the API server, which reach each pod's node.

    `run_subprocess` starts one program, so bash holds the pipe; `pipefail` fails the copy when
    either side fails, and `shlex.join` quotes every word of the two kubectl commands.
    """
    source = build_kubectl_cmd(
        [
            "exec",
            plan.source_pod,
            "-n",
            plan.namespace,
            "--",
            "tar",
            "-C",
            CONST_K8S_VOLUME_MOVE_SOURCE_DIR,
            "--numeric-owner",
            "--sparse",
            "-cpf",
            "-",
            ".",
        ],
        context,
    )
    destination = build_kubectl_cmd(
        [
            "exec",
            "-i",
            plan.destination_pod,
            "-n",
            plan.namespace,
            "--",
            "tar",
            "-C",
            CONST_K8S_VOLUME_MOVE_DESTINATION_DIR,
            "--numeric-owner",
            "-xpf",
            "-",
        ],
        context,
    )
    return [BIN_BASH, "-o", "pipefail", "-c", f"{shlex.join(source)} | {shlex.join(destination)}"]


def delete_old_volume_command(plan: VolumeMovePlan, context: str | None) -> str:
    """The command a person runs to delete the old volume, and its data, after the move."""
    patch = json.dumps({"spec": {"persistentVolumeReclaimPolicy": "Delete"}})
    return shlex.join(build_kubectl_cmd(["patch", "pv", plan.old_volume, "-p", patch], context))


# ── Manifests ────────────────────────────────────────────────────────────────


def _move_claim_manifest(plan: VolumeMovePlan) -> dict[str, Any]:
    return {
        "apiVersion": "v1",
        "kind": "PersistentVolumeClaim",
        "metadata": {
            "name": plan.move_claim,
            "namespace": plan.namespace,
            "labels": dict(CONST_K8S_VOLUME_MOVE_LABELS),
        },
        "spec": {
            "accessModes": list(plan.access_modes),
            "storageClassName": plan.storage_class,
            "volumeMode": plan.volume_mode,
            "resources": {"requests": {"storage": plan.size}},
        },
    }


def _copy_pod_manifest(plan: VolumeMovePlan, *, destination: bool) -> dict[str, Any]:
    """A pod that sleeps with one claim mounted, for the exec streams of the copy.

    The source pod mounts the old claim read-only, and its volume holds it on the old node. The
    destination pod selects the target node, where local-path makes the new volume.
    """
    name, claim, path = (
        (plan.destination_pod, plan.move_claim, CONST_K8S_VOLUME_MOVE_DESTINATION_DIR)
        if destination
        else (plan.source_pod, plan.claim, CONST_K8S_VOLUME_MOVE_SOURCE_DIR)
    )
    spec: dict[str, Any] = {
        "restartPolicy": "Never",
        "terminationGracePeriodSeconds": 0,
        "automountServiceAccountToken": False,
        "containers": [
            {
                "name": "copy",
                "image": DEFAULT_K8S_VOLUME_MOVE_IMAGE,
                "command": ["sleep", "infinity"],
                "volumeMounts": [{"name": "data", "mountPath": path, "readOnly": not destination}],
            }
        ],
        "volumes": [
            {
                "name": "data",
                "persistentVolumeClaim": {"claimName": claim, "readOnly": not destination},
            }
        ],
    }
    if destination:
        spec["nodeSelector"] = {CONST_K8S_HOSTNAME_LABEL: plan.target_hostname}
    elif plan.source_tolerations:
        spec["tolerations"] = list(plan.source_tolerations)
    return {
        "apiVersion": "v1",
        "kind": "Pod",
        "metadata": {
            "name": name,
            "namespace": plan.namespace,
            "labels": dict(CONST_K8S_VOLUME_MOVE_LABELS),
        },
        "spec": spec,
    }


def rebound_claim(saved: dict[str, Any], volume: str) -> tuple[dict[str, Any], str | None]:
    """The saved claim made again on `volume`, and its last-applied configuration to put back.

    The create leaves the last-applied configuration out: `kubectl create` writes the whole new
    object into that annotation when the manifest has it, `volumeName` included, and Argo CD then
    tries to remove `volumeName`, which the API server refuses (`spec is immutable`). It leaves
    out the annotations of the volume controllers too, which name the old binding.
    """
    metadata = saved.get("metadata") or {}
    annotations = dict(metadata.get("annotations") or {})
    last_applied = annotations.pop(CONST_K8S_LAST_APPLIED_ANNOTATION, None)
    kept = {
        key: value
        for key, value in annotations.items()
        if key not in CONST_K8S_CLAIM_CONTROLLER_ANNOTATIONS
    }
    new_metadata = {
        key: metadata[key] for key in CONST_K8S_RECREATED_CLAIM_METADATA_KEYS if metadata.get(key)
    }
    if kept:
        new_metadata["annotations"] = kept
    manifest = {
        "apiVersion": "v1",
        "kind": "PersistentVolumeClaim",
        "metadata": new_metadata,
        "spec": {**(saved.get("spec") or {}), "volumeName": volume},
    }
    return manifest, last_applied


# ── The plan ─────────────────────────────────────────────────────────────────


def parse_claim_ref(ref: str) -> tuple[str, str]:
    """`<namespace>/<claim>` as its two names, each a valid Kubernetes name."""
    namespace, _, claim = ref.partition("/")
    if not (CONST_K8S_LABEL_RE.fullmatch(namespace) and CONST_K8S_SUBDOMAIN_RE.fullmatch(claim)):
        raise VolumeMoveRefusedError(MESSAGES.k8s.volume_move_bad_ref.format(ref=ref))
    return namespace, claim


def _refuse(namespace: str, claim: str, problems: Sequence[str]) -> VolumeMoveRefusedError:
    return VolumeMoveRefusedError(
        MESSAGES.k8s.volume_move_refused.format(namespace=namespace, claim=claim),
        problems=tuple(problems),
    )


def _read_claim(namespace: str, claim: str, context: str | None) -> dict[str, Any]:
    found = _read_json(
        ["get", "pvc", claim, "-n", namespace, "--ignore-not-found", "-o", "json"], context
    )
    if not found:
        problem = MESSAGES.k8s.volume_move_claim_missing.format(namespace=namespace, claim=claim)
        raise _refuse(namespace, claim, [problem])
    phase = (found.get("status") or {}).get("phase", "")
    if phase != CONST_K8S_CLAIM_PHASE_BOUND or not (found.get("spec") or {}).get("volumeName"):
        problem = MESSAGES.k8s.volume_move_claim_not_bound.format(
            namespace=namespace, claim=claim, phase=phase or "unknown"
        )
        raise _refuse(namespace, claim, [problem])
    return found


def _node_of(item: dict[str, Any]) -> _Node:
    metadata = item.get("metadata") or {}
    labels = metadata.get("labels") or {}
    conditions = (item.get("status") or {}).get("conditions") or []
    ready = any(c.get("type") == "Ready" and c.get("status") == "True" for c in conditions)
    name = metadata.get("name", "")
    return _Node(
        name=name,
        hostname=labels.get(CONST_K8S_HOSTNAME_LABEL, name),
        control_plane=CONST_K8S_CONTROL_PLANE_LABEL in labels,
        available=ready and not (item.get("spec") or {}).get("unschedulable", False),
    )


def _volume_hostnames(volume: dict[str, Any]) -> list[str]:
    required = (((volume.get("spec") or {}).get("nodeAffinity") or {}).get("required")) or {}
    return [
        value
        for term in required.get("nodeSelectorTerms") or []
        for expression in term.get("matchExpressions") or []
        if expression.get("key") == CONST_K8S_HOSTNAME_LABEL and expression.get("operator") == "In"
        for value in expression.get("values") or []
    ]


def _source_node(volume: dict[str, Any], nodes: dict[str, _Node]) -> _Node | None:
    """The one node a local volume is on, or None for a volume that is not local."""
    hostnames = _volume_hostnames(volume)
    matches = [node for node in nodes.values() if node.hostname in hostnames]
    return matches[0] if len(hostnames) == 1 and len(matches) == 1 else None


def _mounts(pod: dict[str, Any], claim: str) -> bool:
    return any(
        (volume.get("persistentVolumeClaim") or {}).get("claimName") == claim
        for volume in (pod.get("spec") or {}).get("volumes") or []
    )


def _claim_pods(namespace: str, claim: str, context: str | None) -> list[dict[str, Any]]:
    """The pods whose specs mount the claim; labels can lie, the volumes cannot."""
    items = _read_json(["get", "pods", "-n", namespace, "-o", "json"], context).get("items") or []
    return [pod for pod in items if _mounts(pod, claim)]


def _controller(item: dict[str, Any]) -> tuple[str, str] | None:
    for owner in (item.get("metadata") or {}).get("ownerReferences") or []:
        if owner.get("controller"):
            return owner.get("kind", ""), owner.get("name", "")
    return None


def _workload_ref(
    pod: dict[str, Any], namespace: str, claim: str, context: str | None
) -> tuple[str, str]:
    """The kubectl kind and name of the Deployment or StatefulSet that runs the pod."""
    owner = _controller(pod)
    if owner and owner[0] == "ReplicaSet":
        replica_set = _read_json(
            ["get", "replicaset", owner[1], "-n", namespace, "-o", "json"], context
        )
        owner = _controller(replica_set)
    kind = CONST_K8S_SCALABLE_WORKLOAD_KINDS.get(owner[0]) if owner else None
    if owner is None or kind is None:
        name = (pod.get("metadata") or {}).get("name", "")
        raise _refuse(
            namespace,
            claim,
            [
                MESSAGES.k8s.volume_move_unsupported_owner.format(
                    pod=name, owner=f"{owner[0]} {owner[1]}" if owner else "no controller"
                )
            ],
        )
    return kind, owner[1]


def _tracked_application(item: dict[str, Any]) -> str | None:
    tracking = ((item.get("metadata") or {}).get("annotations") or {}).get(
        CONST_ARGOCD_TRACKING_ID_ANNOTATION, ""
    )
    return tracking.partition(":")[0] or None


def _read_workload(kind: str, name: str, namespace: str, context: str | None) -> _WorkloadState:
    found = _read_json(["get", kind, name, "-n", namespace, "-o", "json"], context)
    spec = found.get("spec") or {}
    retention = spec.get("persistentVolumeClaimRetentionPolicy") or {}
    return _WorkloadState(
        workload=Workload(kind=kind, name=name, replicas=int(spec.get("replicas", 1))),
        when_scaled=retention.get("whenScaled", ""),
        application=_tracked_application(found),
    )


def _workloads(
    pods: Sequence[dict[str, Any]], namespace: str, claim: str, context: str | None
) -> list[_WorkloadState]:
    refs = dict.fromkeys(_workload_ref(pod, namespace, claim, context) for pod in pods)
    return [_read_workload(kind, name, namespace, context) for kind, name in refs]


def _retention_problems(states: Sequence[_WorkloadState], claim: str) -> list[str]:
    return [
        MESSAGES.k8s.volume_move_retention_delete.format(name=state.workload.name, claim=claim)
        for state in states
        if state.when_scaled == CONST_K8S_RETENTION_DELETE
    ]


def _leftover_problems(namespace: str, claim: str, context: str | None) -> list[str]:
    names = [
        f"pod/{claim}{CONST_K8S_VOLUME_MOVE_SOURCE_SUFFIX}",
        f"pod/{claim}{CONST_K8S_VOLUME_MOVE_DESTINATION_SUFFIX}",
        f"pvc/{claim}{CONST_K8S_VOLUME_MOVE_CLAIM_SUFFIX}",
    ]
    found = _kubectl(
        ["get", *names, "-n", namespace, "--ignore-not-found", "-o", "name"], context
    ).split()
    return [MESSAGES.k8s.volume_move_leftovers.format(names=", ".join(found))] if found else []


def _free_bytes(node: str, context: str | None) -> int:
    summary = _read_json(["get", "--raw", f"/api/v1/nodes/{node}/proxy/stats/summary"], context)
    return int(((summary.get("node") or {}).get("fs") or {}).get("availableBytes") or 0)


def _named_target_problem(node: _Node | None, name: str, source: _Node, volume: str) -> str | None:
    if node is None:
        return MESSAGES.k8s.volume_move_unknown_node.format(node=name)
    if node.control_plane:
        return MESSAGES.k8s.volume_move_target_control_plane.format(node=name)
    if node.name == source.name:
        return MESSAGES.k8s.volume_move_target_is_source.format(volume=volume, node=name)
    if not node.available:
        return MESSAGES.k8s.volume_move_target_unavailable.format(node=name)
    return None


def _target(
    source: _Node,
    nodes: dict[str, _Node],
    to_node: str | None,
    volume: str,
    context: str | None,
) -> tuple[_Node, int] | str:
    """The target node and its free bytes, or the problem that stops the move."""
    if to_node:
        node = nodes.get(to_node)
        problem = _named_target_problem(node, to_node, source, volume)
        if node is None or problem:
            return problem or MESSAGES.k8s.volume_move_unknown_node.format(node=to_node)
        return node, _free_bytes(node.name, context)
    if not source.control_plane:
        return MESSAGES.k8s.volume_move_not_on_control_plane.format(volume=volume, node=source.name)
    candidates = [
        node
        for node in nodes.values()
        if node.available and not node.control_plane and node.name != source.name
    ]
    if not candidates:
        return MESSAGES.k8s.volume_move_no_target
    free = {node.name: _free_bytes(node.name, context) for node in candidates}
    best = max(candidates, key=lambda node: (free[node.name], node.name))
    return best, free[best.name]


def _automated(application: dict[str, Any]) -> bool:
    automated = ((application.get("spec") or {}).get("syncPolicy") or {}).get("automated")
    return isinstance(automated, dict) and automated.get("enabled", True) is not False


def _pause_order(
    applications: Sequence[str], context: str | None
) -> tuple[tuple[str, ...], list[str]]:
    """The Applications to pause, top down, and a problem for each tracked one that is missing."""
    if not applications:
        return (), []
    items = (
        _read_json(
            ["get", "applications", "-n", DEFAULT_ARGOCD_NAMESPACE, "-o", "json"], context
        ).get("items")
        or []
    )
    automated = {(item.get("metadata") or {}).get("name", ""): _automated(item) for item in items}
    problems = [
        MESSAGES.k8s.volume_move_unknown_application.format(
            application=name, namespace=DEFAULT_ARGOCD_NAMESPACE
        )
        for name in applications
        if name not in automated
    ]
    order = dict.fromkeys((*CONST_K8S_ARGOCD_PAUSE_PARENTS, *applications))
    return tuple(name for name in order if automated.get(name)), problems


def plan_volume_move(
    namespace: str, claim: str, *, to_node: str | None = None, context: str | None = None
) -> VolumeMovePlan:
    """Read what the move needs and return its plan; refuse a move that cannot run safely.

    Raises `VolumeMoveRefusedError` with every problem it finds, and `VolumeMoveError` when a
    read fails. It changes nothing either way.
    """
    found = _read_claim(namespace, claim, context)
    spec = found.get("spec") or {}
    volume = _read_json(["get", "pv", spec["volumeName"], "-o", "json"], context)
    nodes = {
        node.name: node
        for node in map(
            _node_of, _read_json(["get", "nodes", "-o", "json"], context).get("items") or []
        )
    }
    source = _source_node(volume, nodes)
    if source is None:
        raise _refuse(
            namespace, claim, [MESSAGES.k8s.volume_move_not_local.format(volume=spec["volumeName"])]
        )
    pods = _claim_pods(namespace, claim, context)
    if not pods:
        raise _refuse(
            namespace,
            claim,
            [MESSAGES.k8s.volume_move_no_pods.format(namespace=namespace, claim=claim)],
        )
    states = _workloads(pods, namespace, claim, context)
    problems = _retention_problems(states, claim) + _leftover_problems(namespace, claim, context)
    target = _target(source, nodes, to_node, spec["volumeName"], context)
    if isinstance(target, str):
        problems.append(target)
    applications = tuple(
        sorted(
            {
                name
                for name in (_tracked_application(found), *(s.application for s in states))
                if name
            }
        )
    )
    paused, missing = _pause_order(applications, context)
    problems += missing
    if isinstance(target, str) or problems:
        raise _refuse(namespace, claim, problems)
    node, free = target
    return VolumeMovePlan(
        namespace=namespace,
        claim=claim,
        old_volume=spec["volumeName"],
        old_reclaim_policy=(volume.get("spec") or {}).get("persistentVolumeReclaimPolicy", ""),
        source_node=source.name,
        target_node=node.name,
        target_hostname=node.hostname,
        target_free_bytes=free,
        storage_class=spec.get("storageClassName", ""),
        size=((spec.get("resources") or {}).get("requests") or {}).get("storage", ""),
        access_modes=tuple(spec.get("accessModes") or ()),
        volume_mode=spec.get("volumeMode", "Filesystem"),
        workloads=tuple(state.workload for state in states),
        pods=tuple((pod.get("metadata") or {}).get("name", "") for pod in pods),
        source_tolerations=tuple((pods[0].get("spec") or {}).get("tolerations") or ()),
        applications=applications,
        paused=paused,
    )


def describe_volume_move(plan: VolumeMovePlan) -> tuple[str, ...]:
    """The steps of the move, in order, with the real names; the run prints the same text."""
    m = MESSAGES.k8s
    workloads = ", ".join(workload.ref for workload in plan.workloads)
    return (
        m.volume_move_step_pause.format(applications=", ".join(plan.paused))
        if plan.paused
        else m.volume_move_step_no_pause,
        m.volume_move_step_destination.format(
            claim=plan.move_claim,
            size=plan.size,
            storage_class=plan.storage_class,
            pod=plan.destination_pod,
            node=plan.target_node,
        ),
        m.volume_move_step_stop.format(workloads=workloads, pods=", ".join(plan.pods)),
        m.volume_move_step_source.format(
            pod=plan.source_pod, claim=plan.claim, node=plan.source_node
        ),
        m.volume_move_step_copy.format(source=plan.source_pod, destination=plan.destination_pod),
        m.volume_move_step_compare,
        m.volume_move_step_retain.format(claim=plan.move_claim, volume=plan.old_volume),
        m.volume_move_step_delete_pods.format(
            source=plan.source_pod, destination=plan.destination_pod
        ),
        m.volume_move_step_delete_claim.format(namespace=plan.namespace, claim=plan.claim),
        m.volume_move_step_rebind.format(
            move_claim=plan.move_claim, namespace=plan.namespace, claim=plan.claim
        ),
        m.volume_move_step_recreate.format(namespace=plan.namespace, claim=plan.claim),
        m.volume_move_step_start.format(
            workloads=", ".join(f"{w.ref} to {w.replicas}" for w in plan.workloads),
            node=plan.target_node,
        ),
        m.volume_move_step_resume.format(applications=", ".join(reversed(plan.paused)))
        if plan.paused
        else m.volume_move_step_no_resume,
    )


# ── The run ──────────────────────────────────────────────────────────────────


def _parse_digest(output: str, pod: str) -> CopyDigest:
    values = {key: value for key, _, value in (line.partition(" ") for line in output.splitlines())}
    try:
        return CopyDigest(
            entries=int(values["entries"]),
            files=int(values["files"]),
            bytes=int(values["bytes"]),
            metadata=values["metadata"],
            content=values["content"],
        )
    except (KeyError, ValueError) as exc:
        raise VolumeMoveError(
            MESSAGES.k8s.volume_move_digest_unreadable.format(
                pod=pod, output=output[:DEFAULT_K8S_VOLUME_MOVE_DETAIL_CHARS]
            )
        ) from exc


def _differences(source: CopyDigest, destination: CopyDigest) -> str:
    left, right = asdict(source), asdict(destination)
    return "; ".join(
        f"{name} {left[name]} and {right[name]}"
        for name in _DIGEST_FIELDS
        if left[name] != right[name]
    )


def _save_claim(saved: dict[str, Any], save_dir: Path, plan: VolumeMovePlan) -> Path:
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    path = save_dir / f"{plan.namespace}-{plan.claim}-{stamp}.json"
    try:
        save_dir.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(saved, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    except OSError as exc:
        raise VolumeMoveError(
            MESSAGES.k8s.volume_move_save_failed.format(claim=plan.claim, path=path, reason=exc)
        ) from exc
    return path


@dataclass
class _MoveRun:
    """One run of a plan: its undo steps, and what it learnt on the way."""

    plan: VolumeMovePlan
    context: str | None
    save_dir: Path
    progress: Progress
    undo: list[tuple[str, Callable[[], None]]] = field(default_factory=list)
    new_volume: str = ""
    saved: dict[str, Any] = field(default_factory=dict)
    saved_claim: Path = Path()
    digest: CopyDigest = field(default_factory=lambda: CopyDigest(0, 0, 0, "", ""))
    past_point_of_no_return: bool = False

    # ── helpers ──

    def _kubectl(
        self,
        args: Sequence[str],
        *,
        stdin: str | None = None,
        timeout: float = DEFAULT_K8S_VOLUME_MOVE_REQUEST_TIMEOUT_SECONDS,
    ) -> str:
        return _kubectl(args, self.context, stdin=stdin, timeout=timeout)

    def _on_undo(self, text: str, action: Callable[[], None]) -> None:
        self.undo.append((text, action))

    def _create(self, manifest: dict[str, Any]) -> None:
        self._kubectl(["create", "-f", "-", "-o", "name"], stdin=json.dumps(manifest))

    def _delete(self, kind: str, *names: str, missing_ok: bool = False) -> None:
        self._kubectl(
            _delete_args(kind, names, self.plan.namespace, missing_ok=missing_ok),
            timeout=_wait_timeout(DEFAULT_K8S_VOLUME_MOVE_WAIT_SECONDS),
        )

    def _wait(self, target: str, condition: str, seconds: int) -> None:
        self._kubectl(
            _wait_args(target, self.plan.namespace, condition, seconds),
            timeout=_wait_timeout(seconds),
        )

    def _pause_application(self, application: str, *, enabled: bool) -> None:
        self._kubectl(_pause_args(application, enabled=enabled))

    def _scale(self, workload: Workload, replicas: int) -> None:
        self._kubectl(_scale_args(workload.ref, self.plan.namespace, replicas))

    def _set_reclaim(self, volume: str, policy: str) -> None:
        self._kubectl(_reclaim_args(volume, policy))

    def _undo_delete(self, kind: str, name: str, label: str) -> None:
        self._on_undo(
            MESSAGES.k8s.volume_move_undo_delete.format(kind=label, name=name),
            partial(self._delete, kind, name, missing_ok=True),
        )

    # ── steps ──
    # Each step adds the undo of a change before it asks for the change: a request can fail after
    # the API server made the change, and each undo is harmless when the change did not happen.

    def pause(self) -> None:
        for application in self.plan.paused:
            self._on_undo(
                MESSAGES.k8s.volume_move_undo_resume.format(application=application),
                partial(self._pause_application, application, enabled=True),
            )
            self._pause_application(application, enabled=False)

    def make_destination(self) -> None:
        plan = self.plan
        self._undo_delete("pvc", plan.move_claim, "claim")
        self._create(_move_claim_manifest(plan))
        self._undo_delete("pod", plan.destination_pod, "pod")
        self._create(_copy_pod_manifest(plan, destination=True))
        self._wait(
            f"pod/{plan.destination_pod}", "condition=Ready", DEFAULT_K8S_VOLUME_MOVE_WAIT_SECONDS
        )
        self.new_volume = self._kubectl(
            [
                "get",
                "pvc",
                plan.move_claim,
                "-n",
                plan.namespace,
                "-o",
                "jsonpath={.spec.volumeName}",
            ]
        ).strip()
        if not self.new_volume:
            raise VolumeMoveError(
                MESSAGES.k8s.volume_move_unbound_copy.format(claim=plan.move_claim)
            )

    def stop_workloads(self) -> None:
        for workload in self.plan.workloads:
            self._on_undo(
                MESSAGES.k8s.volume_move_undo_scale.format(
                    workload=workload.ref, replicas=workload.replicas
                ),
                partial(self._scale, workload, workload.replicas),
            )
            self._scale(workload, 0)
        for pod in self.plan.pods:
            self._wait(f"pod/{pod}", "delete", DEFAULT_K8S_VOLUME_MOVE_WAIT_SECONDS)

    def start_source(self) -> None:
        self._undo_delete("pod", self.plan.source_pod, "pod")
        self._create(_copy_pod_manifest(self.plan, destination=False))
        self._wait(
            f"pod/{self.plan.source_pod}", "condition=Ready", DEFAULT_K8S_VOLUME_MOVE_WAIT_SECONDS
        )

    def _stream(self) -> None:
        _run(
            _copy_argv(self.plan, self.context),
            "the copy",
            timeout=DEFAULT_K8S_VOLUME_MOVE_COPY_TIMEOUT_SECONDS,
        )

    def copy(self) -> None:
        """Copy once, and once more on an empty destination when the stream stops (#1634)."""
        try:
            self._stream()
        except VolumeMoveError as exc:
            self.progress(MESSAGES.k8s.volume_move_copy_retry.format(reason=exc))
            self._kubectl(
                _empty_destination_args(self.plan),
                timeout=DEFAULT_K8S_VOLUME_MOVE_COPY_TIMEOUT_SECONDS,
            )
            self._stream()

    def _side(self, pod: str, directory: str) -> CopyDigest:
        output = self._kubectl(
            _digest_args(pod, self.plan.namespace, directory),
            timeout=DEFAULT_K8S_VOLUME_MOVE_COPY_TIMEOUT_SECONDS,
        )
        return _parse_digest(output, pod)

    def compare(self) -> None:
        source = self._side(self.plan.source_pod, CONST_K8S_VOLUME_MOVE_SOURCE_DIR)
        destination = self._side(self.plan.destination_pod, CONST_K8S_VOLUME_MOVE_DESTINATION_DIR)
        if source != destination:
            raise VolumeMoveError(
                MESSAGES.k8s.volume_move_digest_differs.format(
                    fields=_differences(source, destination)
                )
            )
        self.digest = source
        self.progress(
            MESSAGES.k8s.volume_move_digest_equal.format(
                entries=source.entries, files=source.files, bytes=source.bytes
            )
        )

    def _retain(self, volume: str, prior: str) -> None:
        if prior == CONST_K8S_RECLAIM_RETAIN:
            return
        self._on_undo(
            MESSAGES.k8s.volume_move_undo_reclaim.format(volume=volume, policy=prior),
            partial(self._set_reclaim, volume, prior),
        )
        self._set_reclaim(volume, CONST_K8S_RECLAIM_RETAIN)

    def retain_volumes(self) -> None:
        new_policy = self._kubectl(
            ["get", "pv", self.new_volume, "-o", "jsonpath={.spec.persistentVolumeReclaimPolicy}"]
        ).strip()
        self._retain(self.new_volume, new_policy)
        self._retain(self.plan.old_volume, self.plan.old_reclaim_policy)

    def delete_copy_pods(self) -> None:
        self._delete("pod", self.plan.source_pod, self.plan.destination_pod)

    def delete_old_claim(self) -> None:
        """Save the claim as it is now, then delete it: the point of no return."""
        plan = self.plan
        self.saved = _read_json(
            ["get", "pvc", plan.claim, "-n", plan.namespace, "-o", "json"], self.context
        )
        self.saved_claim = _save_claim(self.saved, self.save_dir, plan)
        self.progress(
            MESSAGES.k8s.volume_move_saved.format(
                namespace=plan.namespace, claim=plan.claim, path=self.saved_claim
            )
        )
        self.past_point_of_no_return = True
        self._delete("pvc", plan.claim)

    def rebind(self) -> None:
        self._delete("pvc", self.plan.move_claim)
        self._kubectl(_claim_ref_args(self.new_volume, self.plan.namespace, self.plan.claim))

    def recreate_claim(self) -> None:
        plan = self.plan
        manifest, last_applied = rebound_claim(self.saved, self.new_volume)
        self._create(manifest)
        if last_applied is not None:
            self._kubectl(
                [
                    "annotate",
                    "pvc",
                    plan.claim,
                    "-n",
                    plan.namespace,
                    "--overwrite",
                    f"{CONST_K8S_LAST_APPLIED_ANNOTATION}={last_applied}",
                ]
            )
        self._wait(
            f"pvc/{plan.claim}",
            f"jsonpath={{.status.phase}}={CONST_K8S_CLAIM_PHASE_BOUND}",
            DEFAULT_K8S_VOLUME_MOVE_WAIT_SECONDS,
        )

    def start_workloads(self) -> None:
        plan = self.plan
        for workload in plan.workloads:
            self._scale(workload, workload.replicas)
        for workload in plan.workloads:
            self._wait(
                workload.ref,
                f"jsonpath={{.status.readyReplicas}}={workload.replicas}",
                DEFAULT_K8S_VOLUME_MOVE_ROLLOUT_SECONDS,
            )
        pods = _claim_pods(plan.namespace, plan.claim, self.context)
        placed = [
            ((pod.get("spec") or {}).get("nodeName"), (pod.get("status") or {}).get("phase"))
            for pod in pods
        ]
        if not placed or any(
            place != (plan.target_node, CONST_K8S_POD_PHASE_RUNNING) for place in placed
        ):
            raise VolumeMoveError(
                MESSAGES.k8s.volume_move_placement.format(
                    claim=plan.claim,
                    node=plan.target_node,
                    pods=", ".join(f"{node or 'no node'} ({phase})" for node, phase in placed)
                    or "none",
                )
            )

    def resume(self) -> None:
        for application in reversed(self.plan.paused):
            self._pause_application(application, enabled=True)

    # ── the loop ──

    def actions(self) -> tuple[Callable[[], None], ...]:
        return (
            self.pause,
            self.make_destination,
            self.stop_workloads,
            self.start_source,
            self.copy,
            self.compare,
            self.retain_volumes,
            self.delete_copy_pods,
            self.delete_old_claim,
            self.rebind,
            self.recreate_claim,
            self.start_workloads,
            self.resume,
        )

    def roll_back(self) -> tuple[tuple[str, ...], tuple[str, ...]]:
        """Run every undo step, the last change first; report each one that fails and go on."""
        undone: list[str] = []
        failures: list[str] = []
        for text, action in reversed(self.undo):
            self.progress(MESSAGES.k8s.volume_move_undo_line.format(text=text))
            try:
                action()
            except VolumeMoveError as exc:
                failures.append(f"{text}: {exc}")
                continue
            undone.append(text)
        self.undo.clear()
        return tuple(undone), tuple(failures)

    def failure(self, exc: BaseException, number: int, steps: tuple[str, ...]) -> VolumeMoveError:
        reason = str(exc) or MESSAGES.k8s.volume_move_interrupted
        if self.past_point_of_no_return:
            return VolumeMoveStrandedError(
                MESSAGES.k8s.volume_move_stranded.format(step=number, reason=reason),
                saved_claim=self.saved_claim,
                paused=self.plan.paused,
                remaining=steps[number - 1 :],
                old_volume=self.plan.old_volume,
                new_volume=self.new_volume,
            )
        undone, failures = self.roll_back()
        return VolumeMoveError(
            MESSAGES.k8s.volume_move_undone.format(step=number, reason=reason),
            undone=undone,
            undo_failures=failures,
        )

    def run(self) -> VolumeMoveResult:
        steps = describe_volume_move(self.plan)
        for number, (text, action) in enumerate(zip(steps, self.actions(), strict=True), start=1):
            self.progress(
                MESSAGES.k8s.volume_move_step_line.format(
                    number=number, total=len(steps), text=text
                )
            )
            try:
                action()
            except (VolumeMoveError, KeyboardInterrupt) as exc:
                raise self.failure(exc, number, steps) from exc
        return VolumeMoveResult(
            plan=self.plan,
            new_volume=self.new_volume,
            saved_claim=self.saved_claim,
            digest=self.digest,
        )


def run_volume_move(
    plan: VolumeMovePlan, *, context: str | None, save_dir: Path, progress: Progress
) -> VolumeMoveResult:
    """Run the steps of the plan, printing each one through `progress`.

    Raises `VolumeMoveError` after it undid its steps, for a failure before it deleted the old
    claim, and `VolumeMoveStrandedError`, with Argo CD still paused, for a failure after.
    """
    return _MoveRun(plan=plan, context=context, save_dir=save_dir, progress=progress).run()


# ── The dry run ──────────────────────────────────────────────────────────────


def _placeholder_plan(namespace: str, claim: str, to_node: str | None) -> VolumeMovePlan:
    return VolumeMovePlan(
        namespace=namespace,
        claim=claim,
        old_volume="<old-volume>",
        old_reclaim_policy="<old-reclaim-policy>",
        source_node="<source-node>",
        target_node=to_node or "<target-node>",
        target_hostname="<target-hostname>",
        target_free_bytes=0,
        storage_class="<storage-class>",
        size="<size>",
        access_modes=("<access-mode>",),
        volume_mode="<volume-mode>",
        workloads=(Workload(kind="<kind>", name="<workload>", replicas=0),),
        pods=("<pod>",),
        applications=("<application>",),
        paused=(*CONST_K8S_ARGOCD_PAUSE_PARENTS, "<application>"),
    )


def _planned(
    args: Sequence[str],
    context: str | None,
    target: str,
    *,
    stdin: dict[str, Any] | None = None,
    condition: str = "",
    repeat: str = "",
) -> PlannedRequest:
    return PlannedRequest(
        method=f"kubectl {args[0]}",
        target=target,
        argv=tuple(build_kubectl_cmd(args, context)),
        stdin=json.dumps(stdin, indent=2) if stdin is not None else None,
        condition=condition,
        repeat=repeat,
    )


def _dry_run_reads(
    plan: VolumeMovePlan, to_node: str | None, context: str | None
) -> list[PlannedRequest]:
    ns, claim = plan.namespace, plan.claim
    node = to_node or "<worker-node>"
    leftovers = [f"pod/{plan.source_pod}", f"pod/{plan.destination_pod}", f"pvc/{plan.move_claim}"]
    return [
        _planned(
            ["get", "pvc", claim, "-n", ns, "--ignore-not-found", "-o", "json"],
            context,
            f"claim {ns}/{claim}",
        ),
        _planned(["get", "pv", plan.old_volume, "-o", "json"], context, "the volume of the claim"),
        _planned(["get", "nodes", "-o", "json"], context, "the nodes"),
        _planned(["get", "pods", "-n", ns, "-o", "json"], context, f"the pods of namespace {ns}"),
        _planned(
            ["get", "replicaset", "<replicaset>", "-n", ns, "-o", "json"],
            context,
            "the ReplicaSet of a pod that mounts the claim",
            condition="a pod that mounts the claim belongs to a ReplicaSet",
            repeat="for each such ReplicaSet",
        ),
        _planned(
            ["get", "<kind>", "<workload>", "-n", ns, "-o", "json"],
            context,
            "a workload that mounts the claim",
            repeat="for each Deployment or StatefulSet",
        ),
        _planned(
            ["get", *leftovers, "-n", ns, "--ignore-not-found", "-o", "name"],
            context,
            "leftovers of an earlier move",
        ),
        _planned(
            ["get", "--raw", f"/api/v1/nodes/{node}/proxy/stats/summary"],
            context,
            "the free disk of a node",
            repeat="" if to_node else "for each worker node that is Ready and schedulable",
        ),
        _planned(
            ["get", "applications", "-n", DEFAULT_ARGOCD_NAMESPACE, "-o", "json"],
            context,
            "the Argo CD Applications",
            condition="an Argo CD Application tracks the claim or a workload",
        ),
    ]


def _dry_run_copy(plan: VolumeMovePlan, context: str | None) -> list[PlannedRequest]:
    ns = plan.namespace
    copy_argv = tuple(_copy_argv(plan, context))
    retry = "the copy fails one time"
    return [
        PlannedRequest(method=BIN_BASH, target="the copy", argv=copy_argv),
        _planned(
            _empty_destination_args(plan), context, f"pod {plan.destination_pod}", condition=retry
        ),
        PlannedRequest(method=BIN_BASH, target="the copy", argv=copy_argv, condition=retry),
        _planned(
            _digest_args(plan.source_pod, ns, CONST_K8S_VOLUME_MOVE_SOURCE_DIR),
            context,
            f"pod {plan.source_pod}",
        ),
        _planned(
            _digest_args(plan.destination_pod, ns, CONST_K8S_VOLUME_MOVE_DESTINATION_DIR),
            context,
            f"pod {plan.destination_pod}",
        ),
    ]


def _dry_run_writes(plan: VolumeMovePlan, context: str | None) -> list[PlannedRequest]:
    ns, claim = plan.namespace, plan.claim
    workload = plan.workloads[0].ref
    wait = DEFAULT_K8S_VOLUME_MOVE_WAIT_SECONDS
    top_down = "for bootstrap, cluster and each Application, top down, whose automated sync is on"
    manifest, _ = rebound_claim(
        {
            "metadata": {
                "name": claim,
                "namespace": ns,
                "labels": {"<saved label>": "<value>"},
                "annotations": {"<saved annotation>": "<value>"},
            },
            "spec": _move_claim_manifest(plan)["spec"] | {"storageClassName": plan.storage_class},
        },
        "<new-volume>",
    )
    return [
        _planned(
            _pause_args("<application>", enabled=False),
            context,
            "an Argo CD Application",
            repeat=top_down,
        ),
        _planned(
            ["create", "-f", "-", "-o", "name"],
            context,
            f"claim {plan.move_claim}",
            stdin=_move_claim_manifest(plan),
        ),
        _planned(
            ["create", "-f", "-", "-o", "name"],
            context,
            f"pod {plan.destination_pod}",
            stdin=_copy_pod_manifest(plan, destination=True),
        ),
        _planned(
            _wait_args(f"pod/{plan.destination_pod}", ns, "condition=Ready", wait),
            context,
            "the destination pod",
        ),
        _planned(
            ["get", "pvc", plan.move_claim, "-n", ns, "-o", "jsonpath={.spec.volumeName}"],
            context,
            "the new volume",
        ),
        _planned(_scale_args(workload, ns, 0), context, "a workload", repeat="for each workload"),
        _planned(
            _wait_args("pod/<pod>", ns, "delete", wait),
            context,
            "a pod",
            repeat="for each pod that mounts the claim",
        ),
        _planned(
            ["create", "-f", "-", "-o", "name"],
            context,
            f"pod {plan.source_pod}",
            stdin=_copy_pod_manifest(plan, destination=False),
        ),
        _planned(
            _wait_args(f"pod/{plan.source_pod}", ns, "condition=Ready", wait),
            context,
            "the source pod",
        ),
        *_dry_run_copy(plan, context),
        _planned(
            ["get", "pv", "<new-volume>", "-o", "jsonpath={.spec.persistentVolumeReclaimPolicy}"],
            context,
            "the new volume",
        ),
        _planned(
            _reclaim_args("<new-volume>", CONST_K8S_RECLAIM_RETAIN),
            context,
            "the new volume",
            condition="its policy is not Retain",
        ),
        _planned(
            _reclaim_args(plan.old_volume, CONST_K8S_RECLAIM_RETAIN),
            context,
            "the old volume",
            condition="its policy is not Retain",
        ),
        _planned(
            _delete_args("pod", (plan.source_pod, plan.destination_pod), ns, missing_ok=False),
            context,
            "the copy pods",
        ),
        _planned(
            ["get", "pvc", claim, "-n", ns, "-o", "json"],
            context,
            f"claim {ns}/{claim}, saved to a file",
        ),
        _planned(
            _delete_args("pvc", (claim,), ns, missing_ok=False),
            context,
            f"claim {ns}/{claim}: the point of no return",
        ),
        _planned(
            _delete_args("pvc", (plan.move_claim,), ns, missing_ok=False),
            context,
            f"claim {plan.move_claim}",
        ),
        _planned(_claim_ref_args("<new-volume>", ns, claim), context, "the new volume"),
        _planned(
            ["create", "-f", "-", "-o", "name"], context, f"claim {ns}/{claim}", stdin=manifest
        ),
        _planned(
            [
                "annotate",
                "pvc",
                claim,
                "-n",
                ns,
                "--overwrite",
                f"{CONST_K8S_LAST_APPLIED_ANNOTATION}=<saved last-applied configuration>",
            ],
            context,
            f"claim {ns}/{claim}",
            condition="the saved claim has a last-applied configuration",
        ),
        _planned(
            _wait_args(
                f"pvc/{claim}",
                ns,
                f"jsonpath={{.status.phase}}={CONST_K8S_CLAIM_PHASE_BOUND}",
                wait,
            ),
            context,
            f"claim {ns}/{claim}",
        ),
        _planned(
            _scale_args(workload, ns, "<replicas>"),
            context,
            "a workload",
            repeat="for each workload",
        ),
        _planned(
            _wait_args(
                workload,
                ns,
                "jsonpath={.status.readyReplicas}=<replicas>",
                DEFAULT_K8S_VOLUME_MOVE_ROLLOUT_SECONDS,
            ),
            context,
            "a workload",
            repeat="for each workload",
        ),
        _planned(["get", "pods", "-n", ns, "-o", "json"], context, "the pods that mount the claim"),
        _planned(
            _pause_args("<application>", enabled=True),
            context,
            "an Argo CD Application",
            repeat="for each paused Application, in reverse order",
        ),
    ]


def dry_run_volume_move(
    namespace: str, claim: str, *, to_node: str | None = None, context: str | None = None
) -> tuple[PlannedRequest, ...]:
    """The requests a move would make, in order, making none: not even the claim is read."""
    plan = _placeholder_plan(namespace, claim, to_node)
    return (*_dry_run_reads(plan, to_node, context), *_dry_run_writes(plan, context))


__all__ = [
    "POINT_OF_NO_RETURN_INDEX",
    "CopyDigest",
    "VolumeMovePlan",
    "VolumeMoveResult",
    "Workload",
    "delete_old_volume_command",
    "describe_volume_move",
    "dry_run_volume_move",
    "parse_claim_ref",
    "plan_volume_move",
    "rebound_claim",
    "run_volume_move",
]
