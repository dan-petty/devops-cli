"""Move a local-path claim to a volume on another node, and bind the claim to that volume (#2186).

The new volume can have another StorageClass (#7382). Then the target node is one that can attach
a volume of that class: when a CSIDriver has the name of the provisioner of the class, only a node
whose CSINode lists that driver.

`plan_volume_move` only reads: the claim, its volume, the nodes, the pods that mount the claim and
their workloads, the leftovers of an earlier move and the Argo CD Applications. It refuses a move
that cannot run safely, and returns the plan with the real names. `run_volume_move` runs the steps
that `describe_volume_move` names, the procedure of `k8s/README.md` (Local-Path Volume Placement):
it pauses Argo CD from the top down, copies the data with GNU tar from pod to pod, compares
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
    CONST_ARGOCD_OPERATION_PHASES_RUNNING,
    CONST_ARGOCD_TRACKING_ID_ANNOTATION,
    CONST_K8S_ACCESS_MODES,
    CONST_K8S_CLAIM_CONTROLLER_ANNOTATIONS,
    CONST_K8S_CLAIM_PHASE_BOUND,
    CONST_K8S_CONTROL_PLANE_LABEL,
    CONST_K8S_HOSTNAME_LABEL,
    CONST_K8S_LABEL_RE,
    CONST_K8S_LAST_APPLIED_ANNOTATION,
    CONST_K8S_POD_PHASE_RUNNING,
    CONST_K8S_POD_PHASES_ENDED,
    CONST_K8S_RECLAIM_DELETE,
    CONST_K8S_RECLAIM_RETAIN,
    CONST_K8S_RECREATED_CLAIM_METADATA_KEYS,
    CONST_K8S_RETENTION_DELETE,
    CONST_K8S_SCALABLE_WORKLOAD_KINDS,
    CONST_K8S_SUBDOMAIN_RE,
    CONST_K8S_UNSCHEDULABLE_TAINT,
    CONST_K8S_VOLUME_MOVE_CLAIM_SUFFIX,
    CONST_K8S_VOLUME_MOVE_COPY_PORT,
    CONST_K8S_VOLUME_MOVE_DESTINATION_DIR,
    CONST_K8S_VOLUME_MOVE_DESTINATION_SUFFIX,
    CONST_K8S_VOLUME_MOVE_DIGEST_SCRIPT,
    CONST_K8S_VOLUME_MOVE_LABELS,
    CONST_K8S_VOLUME_MOVE_LISTEN_SCRIPT,
    CONST_K8S_VOLUME_MOVE_LISTENER,
    CONST_K8S_VOLUME_MOVE_POLICY_SUFFIX,
    CONST_K8S_VOLUME_MOVE_RESULT_SCRIPT,
    CONST_K8S_VOLUME_MOVE_SEND_SCRIPT,
    CONST_K8S_VOLUME_MOVE_SOURCE_DIR,
    CONST_K8S_VOLUME_MOVE_SOURCE_SUFFIX,
)
from devops_cli.config.defaults import (
    DEFAULT_ARGOCD_NAMESPACE,
    DEFAULT_K8S_VOLUME_MOVE_COPY_TIMEOUT_SECONDS,
    DEFAULT_K8S_VOLUME_MOVE_DETAIL_CHARS,
    DEFAULT_K8S_VOLUME_MOVE_EXTRACT_WAIT_SECONDS,
    DEFAULT_K8S_VOLUME_MOVE_REQUEST_TIMEOUT_SECONDS,
    DEFAULT_K8S_VOLUME_MOVE_ROLLOUT_SECONDS,
    DEFAULT_K8S_VOLUME_MOVE_SYNC_WAIT_SECONDS,
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
    image: str = ""
    # The class of the new volume when the move changes the class; empty when it keeps the class.
    target_storage_class: str = ""
    # The access modes of the new claims when the move changes them; empty when it keeps them.
    target_access_modes: tuple[str, ...] = ()
    # The size of the new claims when the move changes it; empty when it keeps the size (#7484).
    target_size: str = ""

    @property
    def changes_class(self) -> bool:
        """True when the new volume has another class than the old claim."""
        return bool(self.target_storage_class)

    @property
    def new_size(self) -> str:
        """The size of the temporary claim and of the claim made again (#7484)."""
        return self.target_size or self.size

    @property
    def new_access_modes(self) -> tuple[str, ...]:
        """The access modes of the temporary claim and of the claim made again (#7459)."""
        return self.target_access_modes or self.access_modes

    @property
    def new_storage_class(self) -> str:
        """The class of the temporary claim and of the claim made again."""
        return self.target_storage_class or self.storage_class

    @property
    def move_claim(self) -> str:
        """The temporary claim that gets the new volume on the target node."""
        return f"{self.claim}{CONST_K8S_VOLUME_MOVE_CLAIM_SUFFIX}"

    @property
    def source_pod(self) -> str:
        """The copy pod that mounts the old claim read-only."""
        return f"{self.claim}{CONST_K8S_VOLUME_MOVE_SOURCE_SUFFIX}"

    @property
    def copy_policy(self) -> str:
        """The temporary NetworkPolicy that lets the source copy pod reach the destination."""
        return f"{self.claim}{CONST_K8S_VOLUME_MOVE_POLICY_SUFFIX}"

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


def read_volume_move_image(context: str | None = None) -> str:
    """Read the copy container image from suspended CronJob devops/volume-move in the cluster."""
    data = _read_json(
        ["get", "cronjob", "volume-move", "-n", "devops", "--ignore-not-found", "-o", "json"],
        context,
    )
    if not data:
        raise VolumeMoveError(MESSAGES.k8s.job_cronjob_missing.format(cronjob="volume-move"))
    pod_spec = (
        data.get("spec", {})
        .get("jobTemplate", {})
        .get("spec", {})
        .get("template", {})
        .get("spec", {})
    )
    containers = pod_spec.get("containers") or []
    container = next((c for c in containers if c.get("name") == "copy"), None)
    if not container or not container.get("image"):
        raise VolumeMoveError("CronJob devops/volume-move has no copy container with an image")
    return str(container["image"])


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


def digest_args(pod: str, namespace: str, directory: str) -> list[str]:
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


def empty_args(pod: str, namespace: str) -> list[str]:
    return [
        "exec",
        pod,
        "-n",
        namespace,
        "--",
        "find",
        CONST_K8S_VOLUME_MOVE_DESTINATION_DIR,
        "-mindepth",
        "1",
        "-delete",
    ]


def copy_argv(
    namespace: str, source_pod: str, destination_pod: str, context: str | None
) -> list[str]:
    """The copy as one bash script: GNU tar from pod to pod over the pod network (#7408).

    The stdout of an exec stream through the API server lost data at full speed, so no data goes
    through an exec stream. The script reads the IP address of the destination pod, starts a
    listener in that pod that gives one connection to `tar -x`, lets the source pod send `tar -c`
    to it, and waits for the exit code of the extract. Each exec stream carries only a script and
    its result. `run_subprocess` starts one program, so bash runs the four requests; `set -eu`
    stops at the first one that fails, and `shlex.join` quotes every word of each request.
    """
    port = str(CONST_K8S_VOLUME_MOVE_COPY_PORT)

    def kubectl(*args: str) -> str:
        return shlex.join(build_kubectl_cmd(list(args), context))

    def exec_in(pod: str, script: str, name: str, *args: str) -> str:
        return kubectl("exec", pod, "-n", namespace, "--", "bash", "-c", script, name, *args)

    pod_ip = kubectl(
        "get", "pod", destination_pod, "-n", namespace, "-o", "jsonpath={.status.podIP}"
    )
    script = [
        "set -eu",
        f"ip=$({pod_ip})",
        exec_in(
            destination_pod,
            CONST_K8S_VOLUME_MOVE_LISTEN_SCRIPT,
            "volume-move-listen",
            CONST_K8S_VOLUME_MOVE_LISTENER,
            port,
            CONST_K8S_VOLUME_MOVE_DESTINATION_DIR,
        ),
        exec_in(source_pod, CONST_K8S_VOLUME_MOVE_SEND_SCRIPT, "volume-move-send")
        + f' "$ip" {port} {CONST_K8S_VOLUME_MOVE_SOURCE_DIR}',
        exec_in(
            destination_pod,
            CONST_K8S_VOLUME_MOVE_RESULT_SCRIPT,
            "volume-move-result",
            str(DEFAULT_K8S_VOLUME_MOVE_EXTRACT_WAIT_SECONDS),
        ),
    ]
    return [BIN_BASH, "-o", "pipefail", "-c", "\n".join(script)]


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
            "accessModes": list(plan.new_access_modes),
            "storageClassName": plan.new_storage_class,
            "volumeMode": plan.volume_mode,
            "resources": {"requests": {"storage": plan.new_size}},
        },
    }


def _copy_policy_manifest(plan: VolumeMovePlan) -> dict[str, Any]:
    """A NetworkPolicy that lets the copy pods reach each other on the copy port, and no more.

    A namespace that refuses traffic by default still lets the source reach the listener. The
    policy allows both directions: a pod that a policy selects for egress needs an egress rule too.
    """
    peers = [{"podSelector": {"matchLabels": dict(CONST_K8S_VOLUME_MOVE_LABELS)}}]
    ports = [{"protocol": "TCP", "port": CONST_K8S_VOLUME_MOVE_COPY_PORT}]
    return {
        "apiVersion": "networking.k8s.io/v1",
        "kind": "NetworkPolicy",
        "metadata": {
            "name": plan.copy_policy,
            "namespace": plan.namespace,
            "labels": dict(CONST_K8S_VOLUME_MOVE_LABELS),
        },
        "spec": {
            "podSelector": {"matchLabels": dict(CONST_K8S_VOLUME_MOVE_LABELS)},
            "policyTypes": ["Ingress", "Egress"],
            "ingress": [{"from": peers, "ports": ports}],
            "egress": [{"to": peers, "ports": ports}],
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
    image = plan.image or read_volume_move_image()
    spec: dict[str, Any] = {
        "restartPolicy": "Never",
        "terminationGracePeriodSeconds": 0,
        "automountServiceAccountToken": False,
        "containers": [
            {
                "name": "copy",
                "image": image,
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
    else:
        # The source node is often cordoned, and the workload pod has no toleration for the taint
        # that a cordon adds, so the source copy pod must carry one itself (#5305).
        spec["tolerations"] = [
            *plan.source_tolerations,
            {
                "key": CONST_K8S_UNSCHEDULABLE_TAINT,
                "operator": "Exists",
                "effect": "NoSchedule",
            },
        ]
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


def rebound_claim(
    saved: dict[str, Any],
    volume: str,
    storage_class: str | None = None,
    access_modes: Sequence[str] = (),
    size: str | None = None,
) -> tuple[dict[str, Any], str | None]:
    """The saved claim made again on `volume`, and its last-applied configuration to put back.

    The create leaves the last-applied configuration out: `kubectl create` writes the whole new
    object into that annotation when the manifest has it, `volumeName` included, and Argo CD then
    tries to remove `volumeName`, which the API server refuses (`spec is immutable`). It leaves
    out the annotations of the volume controllers too, which name the old binding.

    `storage_class`, when given, replaces the class of the saved claim: a claim binds only to a
    volume of its own class. `access_modes`, when given, replace the access modes of the saved
    claim, which must fit the modes of the volume.
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
    spec = {**(saved.get("spec") or {}), "volumeName": volume}
    if storage_class:
        spec["storageClassName"] = storage_class
    if access_modes:
        spec["accessModes"] = list(access_modes)
    if size:
        spec["resources"] = {**(spec.get("resources") or {}), "requests": {"storage": size}}
    manifest = {
        "apiVersion": "v1",
        "kind": "PersistentVolumeClaim",
        "metadata": new_metadata,
        "spec": spec,
    }
    return manifest, last_applied


# ── The plan ─────────────────────────────────────────────────────────────────


def _size_problem(size: str, old_size: str) -> str | None:
    """The problem of a size for the new claim, or None: a quantity, not under the old size."""
    from kubernetes.utils import quantity

    parse_fn: Any = quantity.parse_quantity
    try:
        new = parse_fn(size)
    except ValueError:
        return MESSAGES.k8s.volume_move_bad_size.format(size=size)
    try:
        old = parse_fn(old_size)
    except ValueError:
        return None
    if new < old:
        return MESSAGES.k8s.volume_move_smaller_size.format(size=size, old=old_size)
    return None


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
    """The pods whose specs mount the claim; labels can lie, the volumes cannot. A pod that has
    ended holds no volume, and a scale to zero does not delete it, so it is not a pod of the move.
    """
    items = _read_json(["get", "pods", "-n", namespace, "-o", "json"], context).get("items") or []
    return [
        pod
        for pod in items
        if _mounts(pod, claim)
        and (pod.get("status") or {}).get("phase") not in CONST_K8S_POD_PHASES_ENDED
    ]


def _ended_claim_pods(namespace: str, claim: str, context: str | None) -> list[str]:
    """The names of the pods that name the claim and have ended. They hold no data, but the
    claim protection still counts them, so the delete of the claim waits for them (#7465)."""
    items = _read_json(["get", "pods", "-n", namespace, "-o", "json"], context).get("items") or []
    return [
        (pod.get("metadata") or {}).get("name", "")
        for pod in items
        if _mounts(pod, claim)
        and (pod.get("status") or {}).get("phase") in CONST_K8S_POD_PHASES_ENDED
    ]


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
        f"networkpolicy/{claim}{CONST_K8S_VOLUME_MOVE_POLICY_SUFFIX}",
    ]
    found = _kubectl(
        ["get", *names, "-n", namespace, "--ignore-not-found", "-o", "name"], context
    ).split()
    return [MESSAGES.k8s.volume_move_leftovers.format(names=", ".join(found))] if found else []


def _free_bytes(node: str, context: str | None) -> int:
    summary = _read_json(["get", "--raw", f"/api/v1/nodes/{node}/proxy/stats/summary"], context)
    return int(((summary.get("node") or {}).get("fs") or {}).get("availableBytes") or 0)


@dataclass(frozen=True)
class _TargetClass:
    """The class of a class change, its provisioner, and the nodes that can attach its volumes.

    `nodes` is None when the provisioner is not a CSI driver: it does not limit the nodes.
    """

    name: str
    driver: str
    nodes: frozenset[str] | None

    def attaches(self, node: _Node) -> bool:
        return self.nodes is None or node.name in self.nodes


def _target_class(storage_class: str, context: str | None) -> _TargetClass | str:
    """The class of a class change, or the problem that stops the move.

    A CSI driver attaches a volume only on a node whose CSINode lists it, so the nodes come from
    the CSINodes when a CSIDriver has the name of the provisioner of the class.
    """
    found = _read_json(
        ["get", "storageclass", storage_class, "--ignore-not-found", "-o", "json"], context
    )
    if not found:
        return MESSAGES.k8s.volume_move_unknown_storage_class.format(storage_class=storage_class)
    driver = str(found.get("provisioner") or "")
    if not _read_json(["get", "csidriver", driver, "--ignore-not-found", "-o", "json"], context):
        return _TargetClass(name=storage_class, driver=driver, nodes=None)
    items = _read_json(["get", "csinodes", "-o", "json"], context).get("items") or []
    nodes = frozenset(
        (item.get("metadata") or {}).get("name", "")
        for item in items
        if any(
            listed.get("name") == driver for listed in (item.get("spec") or {}).get("drivers") or []
        )
    )
    return _TargetClass(name=storage_class, driver=driver, nodes=nodes)


def _named_target_problem(
    node: _Node | None, name: str, source: _Node, volume: str, new_class: _TargetClass | None
) -> str | None:
    m = MESSAGES.k8s
    if node is None:
        return m.volume_move_unknown_node.format(node=name)
    if node.control_plane:
        return m.volume_move_target_control_plane.format(node=name)
    if new_class is None and node.name == source.name:
        return m.volume_move_target_is_source.format(volume=volume, node=name)
    if not node.available:
        return m.volume_move_target_unavailable.format(node=name)
    if new_class is not None and not new_class.attaches(node):
        return m.volume_move_target_no_driver.format(
            node=name, storage_class=new_class.name, driver=new_class.driver
        )
    return None


def _target(
    source: _Node,
    nodes: dict[str, _Node],
    to_node: str | None,
    volume: str,
    context: str | None,
    new_class: _TargetClass | None = None,
) -> tuple[_Node, int] | str:
    """The target node and its free bytes, or the problem that stops the move.

    A move that keeps the class needs another node. With a class change, the new volume is not
    the old one, so the node of the old volume can be the target too.
    """
    if to_node:
        node = nodes.get(to_node)
        problem = _named_target_problem(node, to_node, source, volume, new_class)
        if node is None or problem:
            return problem or MESSAGES.k8s.volume_move_unknown_node.format(node=to_node)
        return node, _free_bytes(node.name, context)
    if new_class is None and not source.control_plane:
        return MESSAGES.k8s.volume_move_not_on_control_plane.format(volume=volume, node=source.name)
    candidates = [
        node
        for node in nodes.values()
        if node.available
        and not node.control_plane
        and (node.name != source.name if new_class is None else new_class.attaches(node))
    ]
    if not candidates:
        return (
            MESSAGES.k8s.volume_move_no_target
            if new_class is None
            else MESSAGES.k8s.volume_move_no_target_for_class.format(storage_class=new_class.name)
        )
    free = {node.name: _free_bytes(node.name, context) for node in candidates}
    best = max(candidates, key=lambda node: (free[node.name], node.name))
    return best, free[best.name]


def _automated(application: dict[str, Any]) -> bool:
    automated = ((application.get("spec") or {}).get("syncPolicy") or {}).get("automated")
    return isinstance(automated, dict) and automated.get("enabled", True) is not False


def _pause_order(
    applications: Sequence[str], parents: Sequence[str], context: str | None
) -> tuple[tuple[str, ...], list[str]]:
    """The Applications to pause, top down (the root Applications `parents` first), and a problem
    for each tracked one that is missing."""
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
    order = dict.fromkeys((*parents, *applications))
    return tuple(name for name in order if automated.get(name)), problems


def plan_volume_move(
    namespace: str,
    claim: str,
    *,
    parents: Sequence[str],
    to_node: str | None = None,
    storage_class: str | None = None,
    access_mode: str | None = None,
    size: str | None = None,
    context: str | None = None,
) -> VolumeMovePlan:
    """Read what the move needs and return its plan; refuse a move that cannot run safely.
    `parents` are the root Applications (`argocd.root_applications`), paused first.
    `storage_class` is the class of the new volume; the class of the old claim keeps the class.
    `access_mode` is the access mode of the new claims; the modes of the old claim keep them.

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
    old_class = spec.get("storageClassName", "")
    old_modes = tuple(spec.get("accessModes") or ())
    if access_mode and access_mode not in CONST_K8S_ACCESS_MODES:
        problems.append(
            MESSAGES.k8s.volume_move_unknown_access_mode.format(
                access_mode=access_mode, modes=", ".join(CONST_K8S_ACCESS_MODES)
            )
        )
    new_modes = (access_mode,) if access_mode and (access_mode,) != old_modes else ()
    old_size = ((spec.get("resources") or {}).get("requests") or {}).get("storage", "")
    size_problem = _size_problem(size, old_size) if size else None
    if size_problem:
        problems.append(size_problem)
    new_size = size if size and not size_problem and size != old_size else ""
    change = storage_class if storage_class and storage_class != old_class else ""
    new_class = _target_class(change, context) if change else None
    target = (
        new_class
        if isinstance(new_class, str)
        else _target(source, nodes, to_node, spec["volumeName"], context, new_class)
    )
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
    paused, missing = _pause_order(applications, parents, context)
    problems += missing
    if isinstance(target, str) or problems:
        raise _refuse(namespace, claim, problems)
    node, free = target
    image = read_volume_move_image(context)
    return VolumeMovePlan(
        namespace=namespace,
        claim=claim,
        old_volume=spec["volumeName"],
        old_reclaim_policy=(volume.get("spec") or {}).get("persistentVolumeReclaimPolicy", ""),
        source_node=source.name,
        target_node=node.name,
        target_hostname=node.hostname,
        target_free_bytes=free,
        storage_class=old_class,
        size=old_size,
        access_modes=old_modes,
        volume_mode=spec.get("volumeMode", "Filesystem"),
        workloads=tuple(state.workload for state in states),
        pods=tuple((pod.get("metadata") or {}).get("name", "") for pod in pods),
        source_tolerations=tuple((pods[0].get("spec") or {}).get("tolerations") or ()),
        applications=applications,
        paused=paused,
        image=image,
        target_storage_class=change,
        target_access_modes=new_modes,
        target_size=new_size,
    )


def describe_volume_move(plan: VolumeMovePlan) -> tuple[str, ...]:
    """The steps of the move, in order, with the real names; the run prints the same text."""
    m = MESSAGES.k8s
    workloads = ", ".join(workload.ref for workload in plan.workloads)
    scaled = ", ".join(f"{w.ref} to {w.replicas}" for w in plan.workloads)
    return (
        m.volume_move_step_pause.format(applications=", ".join(plan.paused))
        if plan.paused
        else m.volume_move_step_no_pause,
        m.volume_move_step_destination.format(
            claim=plan.move_claim,
            size=plan.new_size,
            storage_class=plan.new_storage_class,
            policy=plan.copy_policy,
            port=CONST_K8S_VOLUME_MOVE_COPY_PORT,
            pod=plan.destination_pod,
            node=plan.target_node,
        ),
        m.volume_move_step_stop.format(workloads=workloads, pods=", ".join(plan.pods)),
        m.volume_move_step_source.format(
            pod=plan.source_pod, claim=plan.claim, node=plan.source_node
        ),
        m.volume_move_step_copy.format(
            source=plan.source_pod,
            destination=plan.destination_pod,
            port=CONST_K8S_VOLUME_MOVE_COPY_PORT,
        ),
        m.volume_move_step_compare,
        m.volume_move_step_retain.format(claim=plan.move_claim, volume=plan.old_volume),
        m.volume_move_step_delete_pods.format(
            source=plan.source_pod, destination=plan.destination_pod, policy=plan.copy_policy
        ),
        m.volume_move_step_delete_claim.format(namespace=plan.namespace, claim=plan.claim),
        m.volume_move_step_rebind.format(
            move_claim=plan.move_claim, namespace=plan.namespace, claim=plan.claim
        ),
        m.volume_move_step_recreate.format(namespace=plan.namespace, claim=plan.claim),
        m.volume_move_step_start_any_node.format(workloads=scaled)
        if plan.changes_class
        else m.volume_move_step_start.format(workloads=scaled, node=plan.target_node),
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

    def _discard_move_claim(self) -> None:
        """Delete the temporary claim and the volume that the move made for it (#7416).

        A class with the reclaim policy Retain, such as `longhorn`, keeps a volume after the delete
        of its claim, and a class with `Immediate` binding makes it before the pod starts. So the
        undo reads the volume when it runs, and sets it to Delete first.
        """
        plan = self.plan
        volume = self._kubectl(
            [
                "get",
                "pvc",
                plan.move_claim,
                "-n",
                plan.namespace,
                "--ignore-not-found",
                "-o",
                "jsonpath={.spec.volumeName}",
            ]
        ).strip()
        if volume:
            self._set_reclaim(volume, CONST_K8S_RECLAIM_DELETE)
        self._delete("pvc", plan.move_claim, missing_ok=True)

    def _undo_delete(self, kind: str, name: str, label: str) -> None:
        self._on_undo(
            MESSAGES.k8s.volume_move_undo_delete.format(kind=label, name=name),
            partial(self._delete, kind, name, missing_ok=True),
        )

    # ── steps ──
    # Each step adds the undo of a change before it asks for the change: a request can fail after
    # the API server made the change, and each undo is harmless when the change did not happen.

    def _settle(self) -> None:
        """Wait until no paused Application runs a sync operation (#7464).

        A pause turns off automated sync, but an operation that already runs, such as the retry
        of a sync that failed on the immutable class of the claim, goes on, and it can make the
        deleted claim again from git. `kubectl wait` waits until the operation has `finishedAt`.
        """
        seconds = DEFAULT_K8S_VOLUME_MOVE_SYNC_WAIT_SECONDS
        for application in self.plan.paused:
            phase = self._kubectl(
                [
                    "get",
                    "application",
                    application,
                    "-n",
                    DEFAULT_ARGOCD_NAMESPACE,
                    "-o",
                    "jsonpath={.status.operationState.phase}",
                ]
            ).strip()
            if phase not in CONST_ARGOCD_OPERATION_PHASES_RUNNING:
                continue
            self._kubectl(
                [
                    "wait",
                    f"application/{application}",
                    "-n",
                    DEFAULT_ARGOCD_NAMESPACE,
                    "--for=jsonpath={.status.operationState.finishedAt}",
                    f"--timeout={seconds}s",
                ],
                timeout=_wait_timeout(seconds),
            )

    def pause(self) -> None:
        for application in self.plan.paused:
            self._on_undo(
                MESSAGES.k8s.volume_move_undo_resume.format(application=application),
                partial(self._pause_application, application, enabled=True),
            )
            self._pause_application(application, enabled=False)
        self._settle()

    def make_destination(self) -> None:
        plan = self.plan
        self._on_undo(
            MESSAGES.k8s.volume_move_undo_discard.format(claim=plan.move_claim),
            self._discard_move_claim,
        )
        self._create(_move_claim_manifest(plan))
        self._undo_delete("networkpolicy", plan.copy_policy, "NetworkPolicy")
        self._create(_copy_policy_manifest(plan))
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
            copy_argv(
                self.plan.namespace,
                self.plan.source_pod,
                self.plan.destination_pod,
                self.context,
            ),
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
                empty_args(self.plan.destination_pod, self.plan.namespace),
                timeout=DEFAULT_K8S_VOLUME_MOVE_COPY_TIMEOUT_SECONDS,
            )
            self._stream()

    def _side(self, pod: str, directory: str) -> CopyDigest:
        output = self._kubectl(
            digest_args(pod, self.plan.namespace, directory),
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
        self._settle()
        self._delete("pod", self.plan.source_pod, self.plan.destination_pod)
        self._delete("networkpolicy", self.plan.copy_policy)

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
        ended = _ended_claim_pods(plan.namespace, plan.claim, self.context)
        if ended:
            self._delete("pod", *ended, missing_ok=True)
        self.past_point_of_no_return = True
        self._delete("pvc", plan.claim)

    def rebind(self) -> None:
        self._delete("pvc", self.plan.move_claim)
        self._kubectl(_claim_ref_args(self.new_volume, self.plan.namespace, self.plan.claim))

    def recreate_claim(self) -> None:
        plan = self.plan
        manifest, last_applied = rebound_claim(
            self.saved,
            self.new_volume,
            plan.new_storage_class,
            plan.new_access_modes,
            plan.target_size or None,
        )
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
        # A volume of another class does not hold its pod on the target node: the scheduler
        # selects the node, so the pods must only run.
        if placed and all(
            phase == CONST_K8S_POD_PHASE_RUNNING
            and (plan.changes_class or node == plan.target_node)
            for node, phase in placed
        ):
            return
        found = ", ".join(f"{node or 'no node'} ({phase})" for node, phase in placed) or "none"
        raise VolumeMoveError(
            MESSAGES.k8s.volume_move_not_running.format(claim=plan.claim, pods=found)
            if plan.changes_class
            else MESSAGES.k8s.volume_move_placement.format(
                claim=plan.claim, node=plan.target_node, pods=found
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


def _placeholder_plan(
    namespace: str,
    claim: str,
    to_node: str | None,
    parents: Sequence[str],
    storage_class: str | None = None,
    access_mode: str | None = None,
    size: str | None = None,
) -> VolumeMovePlan:
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
        paused=(*parents, "<application>"),
        image="<template image>",
        target_storage_class=storage_class or "",
        target_access_modes=(access_mode,) if access_mode else (),
        target_size=size or "",
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


def _dry_run_class_reads(storage_class: str, context: str | None) -> list[PlannedRequest]:
    if not storage_class:
        return []
    csi = "a CSIDriver has the name of the provisioner of the class"
    return [
        _planned(
            ["get", "storageclass", storage_class, "--ignore-not-found", "-o", "json"],
            context,
            f"StorageClass {storage_class}",
            condition="the class is not the class of the claim",
        ),
        _planned(
            ["get", "csidriver", "<provisioner>", "--ignore-not-found", "-o", "json"],
            context,
            "the CSIDriver of the provisioner of the class",
            condition="the class is not the class of the claim",
        ),
        _planned(
            ["get", "csinodes", "-o", "json"],
            context,
            "the CSI drivers of each node",
            condition=csi,
        ),
    ]


def _dry_run_reads(
    plan: VolumeMovePlan, to_node: str | None, context: str | None
) -> list[PlannedRequest]:
    ns, claim = plan.namespace, plan.claim
    node = to_node or "<worker-node>"
    leftovers = [
        f"pod/{plan.source_pod}",
        f"pod/{plan.destination_pod}",
        f"pvc/{plan.move_claim}",
        f"networkpolicy/{plan.copy_policy}",
    ]
    nodes = "for each worker node that is Ready and schedulable" + (
        " and can attach a volume of the class" if plan.changes_class else ""
    )
    return [
        _planned(
            ["get", "cronjob", "volume-move", "-n", "devops", "--ignore-not-found", "-o", "json"],
            context,
            "the copy container image of suspended CronJob devops/volume-move",
        ),
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
        *_dry_run_class_reads(plan.target_storage_class, context),
        _planned(
            ["get", "--raw", f"/api/v1/nodes/{node}/proxy/stats/summary"],
            context,
            "the free disk of a node",
            repeat="" if to_node else nodes,
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
    stream = tuple(copy_argv(ns, plan.source_pod, plan.destination_pod, context))
    retry = "the copy fails one time"
    return [
        PlannedRequest(method=BIN_BASH, target="the copy", argv=stream),
        _planned(
            empty_args(plan.destination_pod, ns),
            context,
            f"pod {plan.destination_pod}",
            condition=retry,
        ),
        PlannedRequest(method=BIN_BASH, target="the copy", argv=stream, condition=retry),
        _planned(
            digest_args(plan.source_pod, ns, CONST_K8S_VOLUME_MOVE_SOURCE_DIR),
            context,
            f"pod {plan.source_pod}",
        ),
        _planned(
            digest_args(plan.destination_pod, ns, CONST_K8S_VOLUME_MOVE_DESTINATION_DIR),
            context,
            f"pod {plan.destination_pod}",
        ),
    ]


def _dry_run_settle(context: str | None) -> list[PlannedRequest]:
    """The wait for the sync operation of each paused Application that still runs (#7464)."""
    seconds = DEFAULT_K8S_VOLUME_MOVE_SYNC_WAIT_SECONDS
    paused = "for each paused Application"
    return [
        _planned(
            [
                "get",
                "application",
                "<application>",
                "-n",
                DEFAULT_ARGOCD_NAMESPACE,
                "-o",
                "jsonpath={.status.operationState.phase}",
            ],
            context,
            "the sync operation of an Argo CD Application",
            repeat=paused,
        ),
        _planned(
            [
                "wait",
                "application/<application>",
                "-n",
                DEFAULT_ARGOCD_NAMESPACE,
                "--for=jsonpath={.status.operationState.finishedAt}",
                f"--timeout={seconds}s",
            ],
            context,
            "the end of that sync operation",
            condition="the operation runs",
            repeat=paused,
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
        plan.new_storage_class,
        plan.new_access_modes,
        plan.target_size or None,
    )
    return [
        _planned(
            _pause_args("<application>", enabled=False),
            context,
            "an Argo CD Application",
            repeat=top_down,
        ),
        *_dry_run_settle(context),
        _planned(
            ["create", "-f", "-", "-o", "name"],
            context,
            f"claim {plan.move_claim}",
            stdin=_move_claim_manifest(plan),
        ),
        _planned(
            ["create", "-f", "-", "-o", "name"],
            context,
            f"NetworkPolicy {plan.copy_policy}",
            stdin=_copy_policy_manifest(plan),
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
        *_dry_run_settle(context),
        _planned(
            _delete_args("pod", (plan.source_pod, plan.destination_pod), ns, missing_ok=False),
            context,
            "the copy pods",
        ),
        _planned(
            _delete_args("networkpolicy", (plan.copy_policy,), ns, missing_ok=False),
            context,
            f"NetworkPolicy {plan.copy_policy}",
        ),
        _planned(
            ["get", "pvc", claim, "-n", ns, "-o", "json"],
            context,
            f"claim {ns}/{claim}, saved to a file",
        ),
        _planned(["get", "pods", "-n", ns, "-o", "json"], context, "the pods that have ended"),
        _planned(
            _delete_args("pod", ("<ended pod>",), ns, missing_ok=True),
            context,
            "the pods that name the claim and have ended",
            condition="a pod of the claim has ended",
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
    namespace: str,
    claim: str,
    *,
    parents: Sequence[str],
    to_node: str | None = None,
    storage_class: str | None = None,
    access_mode: str | None = None,
    size: str | None = None,
    context: str | None = None,
) -> tuple[PlannedRequest, ...]:
    """The requests a move would make, in order, making none: not even the claim is read."""
    plan = _placeholder_plan(namespace, claim, to_node, parents, storage_class, access_mode, size)
    return (*_dry_run_reads(plan, to_node, context), *_dry_run_writes(plan, context))


__all__ = [
    "POINT_OF_NO_RETURN_INDEX",
    "CopyDigest",
    "VolumeMovePlan",
    "VolumeMoveResult",
    "Workload",
    "copy_argv",
    "delete_old_volume_command",
    "describe_volume_move",
    "digest_args",
    "dry_run_volume_move",
    "empty_args",
    "parse_claim_ref",
    "plan_volume_move",
    "read_volume_move_image",
    "rebound_claim",
    "run_volume_move",
]
