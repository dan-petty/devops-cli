"""`devops k8s volume move`: a local-path claim copied to a volume on another node and bound to it.

The cluster is a scripted answer of the shared process fake (#2186): each kubectl request reads
or changes the objects of `Cluster`, and `Cluster.changes` records, in order, every request that
changes the cluster. No test starts kubectl or bash, and no test reaches a cluster.
"""

from __future__ import annotations

import json
import shlex
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest

from devops_cli.exceptions.k8s import (
    VolumeMoveError,
    VolumeMoveRefusedError,
    VolumeMoveStrandedError,
)
from devops_cli.k8s.volume_move import (
    CopyDigest,
    VolumeMovePlan,
    Workload,
    describe_volume_move,
    dry_run_volume_move,
    plan_volume_move,
    run_volume_move,
)
from devops_cli.lang import MESSAGES
from devops_cli.output import format_bytes
from tests.support.fakes.process import ProcessAnswer, ProcessCall, ProcessFake

CONTEXT = "test-ctx"
NAMESPACE = "monitoring"
PARENTS = ("bootstrap", "cluster")
CLAIM = "grafana"
OLD_VOLUME = "pvc-old"
NEW_VOLUME = "pvc-new"
CONTROL_PLANE = "control-1"
WORKER_A = "worker-a"
WORKER_B = "worker-b"
POD = "grafana-5d4f-abcde"
ENDED_POD = "grafana-old-fghij"
REPLICA_SET = "grafana-5d4f"
FREE_BYTES = {
    CONTROL_PLANE: 40_000_000_000,
    WORKER_A: 1_000_000_000_000,
    WORKER_B: 1_700_000_000_000,
}
DIGEST = f"entries 12\nfiles 7\nbytes 4096\nmetadata {'a' * 64}\ncontent {'b' * 64}\n"
OTHER_DIGEST = DIGEST.replace("b" * 64, "c" * 64)
LAST_APPLIED = json.dumps(
    {"apiVersion": "v1", "kind": "PersistentVolumeClaim", "metadata": {"name": CLAIM}}
)
TRACKING = "argocd.argoproj.io/tracking-id"
PAUSE = ("bootstrap", "cluster", "grafana")
VOLUME_MOVE_IMAGE = (
    "debian:trixie-slim@sha256:a72b4433de1cf7d6bae0c4cee74d0547f58601a643b3375f070c51600d63b6b2"
)
LONGHORN = "longhorn"
LONGHORN_DRIVER = "driver.longhorn.io"


def _claim_object() -> dict[str, Any]:
    """Claim monitoring/grafana as the API server returns it, bound to the old volume."""
    return {
        "apiVersion": "v1",
        "kind": "PersistentVolumeClaim",
        "metadata": {
            "name": CLAIM,
            "namespace": NAMESPACE,
            "uid": "c54a286c-0000-4000-8000-000000000000",
            "resourceVersion": "1862816",
            "creationTimestamp": "2026-09-30T12:59:10Z",
            "finalizers": ["kubernetes.io/pvc-protection"],
            "labels": {
                "app.kubernetes.io/instance": "grafana",
                "app.kubernetes.io/name": "grafana",
            },
            "annotations": {
                "argocd.argoproj.io/sync-options": "Prune=false,Delete=false",
                TRACKING: "grafana:/PersistentVolumeClaim:monitoring/grafana",
                "kubectl.kubernetes.io/last-applied-configuration": LAST_APPLIED,
                "pv.kubernetes.io/bind-completed": "yes",
                "pv.kubernetes.io/bound-by-controller": "yes",
                "volume.beta.kubernetes.io/storage-provisioner": "rancher.io/local-path",
                "volume.kubernetes.io/selected-node": CONTROL_PLANE,
                "volume.kubernetes.io/storage-provisioner": "rancher.io/local-path",
            },
        },
        "spec": {
            "accessModes": ["ReadWriteOnce"],
            "resources": {"requests": {"storage": "5Gi"}},
            "storageClassName": "local-path",
            "volumeMode": "Filesystem",
            "volumeName": OLD_VOLUME,
        },
        "status": {"phase": "Bound"},
    }


def _node(name: str, *, control_plane: bool = False) -> dict[str, Any]:
    labels = {"kubernetes.io/hostname": name}
    if control_plane:
        labels["node-role.kubernetes.io/control-plane"] = "true"
    return {
        "metadata": {"name": name, "labels": labels},
        "spec": {},
        "status": {"conditions": [{"type": "Ready", "status": "True"}]},
    }


def _owned(kind: str, name: str) -> list[dict[str, Any]]:
    return [{"kind": kind, "name": name, "controller": True}]


@dataclass
class Cluster:
    """The objects of one move, read and changed through kubectl argv."""

    claim_phase: str = "Bound"
    volume_node: str = CONTROL_PLANE
    old_reclaim_policy: str = "Delete"
    workload_kind: str = "Deployment"
    when_scaled: str = "Retain"
    leftovers: tuple[str, ...] = ()
    copy_failures: int = 0
    interrupt_copy: bool = False
    destination_digest: str = DIGEST
    failing: frozenset[str] = frozenset()
    replicas: int = 1
    claim_volume: str | None = OLD_VOLUME
    move_claim_volume: str | None = None
    target_hostname: str | None = None
    restarted_on: str | None = None
    restarted_phase: str = "Running"
    ended_pod: bool = False
    # The phase of the sync operation of each Application, and whether its end never comes.
    operation_phase: str = "Succeeded"
    operation_never_ends: bool = False
    operation_ends_alone: bool = False
    claim_exists: bool = True
    owner_kind: str | None = None
    tracked: bool = True
    cronjob_exists: bool = True
    known_applications: tuple[str, ...] = ("bootstrap", "cluster", "grafana", "loki")
    timeout_on: str | None = None
    # The provisioner of each StorageClass, the CSIDrivers, and the drivers of each CSINode: only
    # worker-a has the Longhorn driver, as only the storage nodes of the homelab do.
    storage_classes: dict[str, str] = field(
        default_factory=lambda: {
            "local-path": "rancher.io/local-path",
            LONGHORN: LONGHORN_DRIVER,
            "nfs": "example.com/nfs",
        }
    )
    csi_drivers: tuple[str, ...] = (LONGHORN_DRIVER,)
    csi_nodes: dict[str, tuple[str, ...]] = field(
        default_factory=lambda: {CONTROL_PLANE: (), WORKER_A: (LONGHORN_DRIVER,), WORKER_B: ()}
    )
    changes: list[str] = field(default_factory=list)
    created: list[dict[str, Any]] = field(default_factory=list)

    def __call__(self, call: ProcessCall) -> subprocess.CompletedProcess[str]:
        argv = list(call.argv)
        if argv[0] == "bash":
            return self._copy(argv)
        assert argv[:3] == ["kubectl", "--context", CONTEXT], argv
        args = argv[3:]
        if args[0] == "get":
            return _ok(self._get(args))
        if args[0] == "wait":
            if args[1].startswith("application/"):
                self.changes.append(f"wait {args[1]}")
                if self.operation_never_ends or self.operation_ends_alone:
                    if self.operation_ends_alone:
                        self.operation_phase = "Succeeded"
                    return _failed("error: timed out waiting for the condition")
            return _ok("")
        if args[0] == "exec":
            return self._exec(args)
        return self._change(args, call.stdin if isinstance(call.stdin, str) else None)

    # ── reads ──────────────────────────────────────────────────────────────

    def _get(self, args: list[str]) -> str:
        what = args[1]
        if what == self.timeout_on:
            raise subprocess.TimeoutExpired(cmd=args, timeout=1)
        if what.startswith("pod/"):
            return "".join(f"{name}\n" for name in self.leftovers)
        if what == "--raw":
            node = args[2].split("/")[4]
            return json.dumps({"node": {"fs": {"availableBytes": FREE_BYTES[node]}}})
        readers = {
            "pvc": self._get_claim,
            "pv": self._get_volume,
            "nodes": lambda _args: json.dumps({"items": self._nodes()}),
            "pods": lambda _args: json.dumps({"items": self._pods()}),
            "replicaset": lambda _args: json.dumps(
                {"metadata": {"ownerReferences": _owned("Deployment", CLAIM)}}
            ),
            "deployment": lambda _args: json.dumps(self._workload()),
            "statefulset": lambda _args: json.dumps(self._workload()),
            "applications": lambda _args: json.dumps({"items": self._applications()}),
            "application": lambda _args: self.operation_phase,
            "cronjob": self._get_cronjob,
            "storageclass": self._get_storage_class,
            "csidriver": lambda args: (
                json.dumps({"metadata": {"name": args[2]}}) if args[2] in self.csi_drivers else ""
            ),
            "csinodes": lambda _args: json.dumps({"items": self._csi_nodes()}),
        }
        return readers[what](args)

    def _get_storage_class(self, args: list[str]) -> str:
        provisioner = self.storage_classes.get(args[2])
        if provisioner is None:
            return ""
        return json.dumps({"metadata": {"name": args[2]}, "provisioner": provisioner})

    def _csi_nodes(self) -> list[dict[str, Any]]:
        return [
            {
                "metadata": {"name": node},
                "spec": {"drivers": [{"name": driver, "nodeID": node} for driver in drivers]},
            }
            for node, drivers in self.csi_nodes.items()
        ]

    def _get_cronjob(self, args: list[str]) -> str:
        if not self.cronjob_exists:
            return ""
        return json.dumps(
            {
                "apiVersion": "batch/v1",
                "kind": "CronJob",
                "metadata": {"name": "volume-move", "namespace": "devops"},
                "spec": {
                    "suspend": True,
                    "jobTemplate": {
                        "spec": {
                            "template": {
                                "spec": {
                                    "containers": [
                                        {
                                            "name": "copy",
                                            "image": VOLUME_MOVE_IMAGE,
                                            "securityContext": {
                                                "allowPrivilegeEscalation": False,
                                                "readOnlyRootFilesystem": True,
                                                "runAsNonRoot": True,
                                                "runAsUser": 65534,
                                                "capabilities": {"drop": ["ALL"]},
                                            },
                                        }
                                    ]
                                }
                            }
                        }
                    },
                },
            }
        )

    def _get_claim(self, args: list[str]) -> str:
        if args[2] == f"{CLAIM}-move":
            return self.move_claim_volume or ""
        if not self.claim_exists:
            return ""
        claim = _claim_object()
        claim["status"]["phase"] = self.claim_phase
        if not self.tracked:
            del claim["metadata"]["annotations"][TRACKING]
        return json.dumps(claim)

    def _get_volume(self, args: list[str]) -> str:
        if args[2] == NEW_VOLUME:
            return "Delete"
        return json.dumps(
            {
                "metadata": {"name": OLD_VOLUME},
                "spec": {
                    "persistentVolumeReclaimPolicy": self.old_reclaim_policy,
                    "nodeAffinity": {
                        "required": {
                            "nodeSelectorTerms": [
                                {
                                    "matchExpressions": [
                                        {
                                            "key": "kubernetes.io/hostname",
                                            "operator": "In",
                                            "values": [self.volume_node],
                                        }
                                    ]
                                }
                            ]
                        }
                    },
                },
            }
        )

    def _nodes(self) -> list[dict[str, Any]]:
        return [_node(CONTROL_PLANE, control_plane=True), _node(WORKER_A), _node(WORKER_B)]

    def _pod_node(self) -> str:
        if self.claim_volume != NEW_VOLUME:
            return self.volume_node
        return self.restarted_on or self.target_hostname or ""

    def _pods(self) -> list[dict[str, Any]]:
        owner = (
            _owned("ReplicaSet", REPLICA_SET)
            if self.workload_kind == "Deployment"
            else _owned("StatefulSet", CLAIM)
        )
        if self.owner_kind:
            owner = _owned(self.owner_kind, "backup")
        pods = []
        if self.replicas and self.claim_volume:
            pods.append(
                {
                    "metadata": {"name": POD, "ownerReferences": owner},
                    "spec": {
                        "nodeName": self._pod_node(),
                        "tolerations": [{"key": "example.com/dedicated", "operator": "Exists"}],
                        "volumes": [
                            {"name": "storage", "persistentVolumeClaim": {"claimName": CLAIM}}
                        ],
                    },
                    "status": {
                        "phase": "Running"
                        if self.claim_volume != NEW_VOLUME
                        else self.restarted_phase
                    },
                }
            )
        if self.ended_pod:
            # A pod of an old ReplicaSet that a node shutdown ended: it still names the claim.
            pods.append(
                {
                    "metadata": {
                        "name": ENDED_POD,
                        "ownerReferences": _owned("ReplicaSet", "grafana-old"),
                    },
                    "spec": {
                        "nodeName": self.volume_node,
                        "volumes": [
                            {"name": "storage", "persistentVolumeClaim": {"claimName": CLAIM}}
                        ],
                    },
                    "status": {"phase": "Succeeded"},
                }
            )
        pods.append(
            {
                "metadata": {"name": "unrelated-0", "ownerReferences": _owned("StatefulSet", "x")},
                "spec": {"volumes": [{"name": "tmp", "emptyDir": {}}]},
                "status": {"phase": "Running"},
            }
        )
        return pods

    def _workload(self) -> dict[str, Any]:
        spec: dict[str, Any] = {"replicas": 1}
        if self.workload_kind == "StatefulSet":
            spec["persistentVolumeClaimRetentionPolicy"] = {
                "whenDeleted": "Retain",
                "whenScaled": self.when_scaled,
            }
        annotations = (
            {TRACKING: f"grafana:apps/{self.workload_kind}:monitoring/grafana"}
            if self.tracked
            else {}
        )
        return {"metadata": {"name": CLAIM, "annotations": annotations}, "spec": spec}

    def _applications(self) -> list[dict[str, Any]]:
        return [
            {
                "metadata": {"name": name},
                "spec": {"syncPolicy": {"automated": {"enabled": True, "selfHeal": True}}},
            }
            for name in self.known_applications
        ]

    # ── exec and copy ──────────────────────────────────────────────────────

    def _exec(self, args: list[str]) -> subprocess.CompletedProcess[str]:
        command = args[args.index("--") + 1 :]
        if command[0] == "find":
            self.changes.append(f"empty {command[1]}")
            return _ok("")
        assert command[:2] == ["bash", "-c"], command
        directory = command[-1]
        return _ok(DIGEST if directory == "/src" else self.destination_digest)

    def _copy(self, argv: list[str]) -> subprocess.CompletedProcess[str]:
        assert argv[:4] == ["bash", "-o", "pipefail", "-c"], argv
        self.changes.append("copy")
        if self.interrupt_copy:
            raise KeyboardInterrupt
        if self.copy_failures:
            self.copy_failures -= 1
            return _failed("error: read tcp: connection reset by peer")
        return _ok("")

    # ── changes ────────────────────────────────────────────────────────────

    def _change(self, args: list[str], stdin: str | None) -> subprocess.CompletedProcess[str]:
        summary = self._summary(args, stdin)
        self.changes.append(summary)
        if summary in self.failing:
            return _failed("admission webhook denied the request")
        self._apply(summary)
        return _ok("")

    def _summary(self, args: list[str], stdin: str | None) -> str:
        verb = args[0]
        if verb == "create":
            created = json.loads(stdin or "{}")
            self.created.append(created)
            if created["kind"] == "Pod" and "nodeSelector" in created["spec"]:
                self.target_hostname = created["spec"]["nodeSelector"]["kubernetes.io/hostname"]
            return f"create {created['kind']} {created['metadata']['name']}"
        if verb == "patch":
            return f"patch {args[1]} {args[2]} {_patch_summary(json.loads(args[args.index('-p') + 1]))}"
        if verb == "scale":
            replicas = next(arg for arg in args if arg.startswith("--replicas="))
            return f"scale {args[1]} {replicas}"
        if verb == "delete":
            names = [arg for arg in args[2:] if not arg.startswith("-")]
            names = names[: names.index(NAMESPACE)] if NAMESPACE in names else names
            return " ".join(["delete", args[1], *names])
        assert verb == "annotate", args
        return f"annotate {args[1]} {args[2]}"

    def _apply(self, summary: str) -> None:
        match summary:
            case "create Pod grafana-dst":
                self.move_claim_volume = NEW_VOLUME
            case "delete pvc grafana":
                self.claim_volume = None
            case "create PersistentVolumeClaim grafana":
                self.claim_volume = self.created[-1]["spec"]["volumeName"]
            case _ if summary.startswith("scale "):
                self.replicas = int(summary.rsplit("=", 1)[1])


def _patch_summary(body: dict[str, Any]) -> str:
    if "status" in body:
        assert body == {"status": {"operationState": {"phase": "Terminating"}}}
        return "terminate"
    spec = body["spec"]
    if "syncPolicy" in spec:
        return f"enabled={str(spec['syncPolicy']['automated']['enabled']).lower()}"
    if "claimRef" in spec:
        ref = spec["claimRef"]
        assert (ref["uid"], ref["resourceVersion"]) == (None, None)
        return f"claimRef={ref['namespace']}/{ref['name']}"
    return f"reclaim={spec['persistentVolumeReclaimPolicy']}"


def _ok(stdout: str) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess([], 0, stdout, "")


def _failed(stderr: str) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess([], 1, "", stderr)


@pytest.fixture
def cluster(process_fake: ProcessFake) -> Cluster:
    scripted = Cluster()
    process_fake.answer(lambda _call: True, ProcessAnswer(side_effect=scripted))
    return scripted


def _plan(**options: Any) -> VolumeMovePlan:
    return plan_volume_move(NAMESPACE, CLAIM, parents=PARENTS, context=CONTEXT, **options)


def _move(tmp_path: Path, progress: list[str] | None = None, **options: Any) -> Any:
    lines = progress if progress is not None else []
    return run_volume_move(
        _plan(**options), context=CONTEXT, save_dir=tmp_path, progress=lines.append
    )


def _pause(enabled: bool, names: tuple[str, ...]) -> list[str]:
    return [f"patch application {name} enabled={str(enabled).lower()}" for name in names]


PLAN = VolumeMovePlan(
    namespace=NAMESPACE,
    claim=CLAIM,
    old_volume=OLD_VOLUME,
    old_reclaim_policy="Delete",
    source_node=CONTROL_PLANE,
    target_node=WORKER_B,
    target_hostname=WORKER_B,
    target_free_bytes=FREE_BYTES[WORKER_B],
    storage_class="local-path",
    size="5Gi",
    access_modes=("ReadWriteOnce",),
    volume_mode="Filesystem",
    workloads=(Workload(kind="deployment", name=CLAIM, replicas=1),),
    pods=(POD,),
    source_tolerations=({"key": "example.com/dedicated", "operator": "Exists"},),
    applications=("grafana",),
    paused=PAUSE,
    image=VOLUME_MOVE_IMAGE,
)
BEFORE_COPY = [
    *_pause(False, PAUSE),
    "create PersistentVolumeClaim grafana-move",
    "create NetworkPolicy grafana-copy",
    "create Pod grafana-dst",
    "scale deployment/grafana --replicas=0",
    "create Pod grafana-src",
]
UNDO_AFTER_COPY = [
    "delete pod grafana-src",
    "scale deployment/grafana --replicas=1",
    "delete pod grafana-dst",
    "delete networkpolicy grafana-copy",
    "patch pv pvc-new reclaim=Delete",
    "delete pvc grafana-move",
    *_pause(True, ("grafana", "cluster", "bootstrap")),
]


# ── The plan ───────────────────────────────────────────────────────────────


def test_the_plan_picks_the_worker_with_the_most_free_disk_and_changes_nothing(
    cluster: Cluster,
) -> None:
    assert _plan() == PLAN
    assert cluster.changes == []


def test_the_plan_takes_the_worker_that_to_node_names(cluster: Cluster) -> None:
    plan = _plan(to_node=WORKER_A)

    assert (plan.target_node, plan.target_free_bytes) == (WORKER_A, FREE_BYTES[WORKER_A])


def test_the_plan_moves_a_volume_between_workers_when_to_node_names_the_target(
    cluster: Cluster,
) -> None:
    cluster.volume_node = WORKER_A

    assert _plan(to_node=WORKER_B).source_node == WORKER_A


def test_the_plan_names_each_step_with_the_real_names(cluster: Cluster) -> None:
    m = MESSAGES.k8s

    assert describe_volume_move(_plan()) == (
        m.volume_move_step_pause.format(applications="bootstrap, cluster, grafana"),
        m.volume_move_step_destination.format(
            claim="grafana-move",
            size="5Gi",
            storage_class="local-path",
            pod="grafana-dst",
            node=WORKER_B,
            policy="grafana-copy",
            port=7373,
        ),
        m.volume_move_step_stop.format(workloads="deployment/grafana", pods=POD),
        m.volume_move_step_source.format(pod="grafana-src", claim=CLAIM, node=CONTROL_PLANE),
        m.volume_move_step_copy.format(source="grafana-src", destination="grafana-dst", port=7373),
        m.volume_move_step_compare,
        m.volume_move_step_retain.format(claim="grafana-move", volume=OLD_VOLUME),
        m.volume_move_step_delete_pods.format(
            source="grafana-src", destination="grafana-dst", policy="grafana-copy"
        ),
        m.volume_move_step_delete_claim.format(namespace=NAMESPACE, claim=CLAIM),
        m.volume_move_step_rebind.format(
            move_claim="grafana-move", namespace=NAMESPACE, claim=CLAIM
        ),
        m.volume_move_step_recreate.format(namespace=NAMESPACE, claim=CLAIM),
        m.volume_move_step_start.format(workloads="deployment/grafana to 1", node=WORKER_B),
        m.volume_move_step_resume.format(applications="grafana, cluster, bootstrap"),
    )


def test_a_claim_that_no_application_tracks_moves_with_no_pause(
    cluster: Cluster, tmp_path: Path
) -> None:
    cluster.tracked = False

    plan = _plan()
    _move(tmp_path)

    assert (plan.applications, plan.paused) == ((), ())
    steps = describe_volume_move(plan)
    assert (steps[0], steps[-1]) == (
        MESSAGES.k8s.volume_move_step_no_pause,
        MESSAGES.k8s.volume_move_step_no_resume,
    )
    assert not any(change.startswith("patch application") for change in cluster.changes)


# ── A class change ─────────────────────────────────────────────────────────


def test_a_class_change_picks_the_worker_whose_csinode_lists_the_driver(
    cluster: Cluster,
) -> None:
    """worker-b has more free disk, but only worker-a can attach a Longhorn volume (#7382)."""
    plan = _plan(storage_class=LONGHORN)

    assert (plan.storage_class, plan.target_storage_class, plan.new_storage_class) == (
        "local-path",
        LONGHORN,
        LONGHORN,
    )
    assert (plan.target_node, plan.target_free_bytes) == (WORKER_A, FREE_BYTES[WORKER_A])
    assert cluster.changes == []


def test_a_class_without_a_csi_driver_does_not_limit_the_nodes(cluster: Cluster) -> None:
    assert _plan(storage_class="nfs").target_node == WORKER_B


def test_a_class_change_moves_a_volume_off_a_worker_without_to_node(cluster: Cluster) -> None:
    """The new volume is not the old one, so the node of the old volume can be the target."""
    cluster.volume_node = WORKER_A

    plan = _plan(storage_class=LONGHORN)

    assert (plan.source_node, plan.target_node) == (WORKER_A, WORKER_A)


def test_the_class_of_the_old_claim_is_a_move_that_keeps_the_class(cluster: Cluster) -> None:
    assert _plan(storage_class="local-path") == PLAN


def test_the_steps_of_a_class_change_name_the_new_class(cluster: Cluster) -> None:
    m = MESSAGES.k8s

    steps = describe_volume_move(_plan(storage_class=LONGHORN))

    assert steps[1] == m.volume_move_step_destination.format(
        claim="grafana-move",
        size="5Gi",
        storage_class=LONGHORN,
        pod="grafana-dst",
        node=WORKER_A,
        policy="grafana-copy",
        port=7373,
    )
    assert steps[11] == m.volume_move_step_start_any_node.format(
        workloads="deployment/grafana to 1"
    )


def test_a_class_change_makes_the_move_claim_and_the_claim_again_with_the_new_class(
    cluster: Cluster, tmp_path: Path
) -> None:
    _move(tmp_path, storage_class=LONGHORN)

    claims = [item for item in cluster.created if item["kind"] == "PersistentVolumeClaim"]
    assert [(claim["metadata"]["name"], claim["spec"]["storageClassName"]) for claim in claims] == [
        ("grafana-move", LONGHORN),
        (CLAIM, LONGHORN),
    ]
    assert claims[-1]["spec"]["volumeName"] == NEW_VOLUME
    assert cluster.changes[-3:] == _pause(True, ("grafana", "cluster", "bootstrap"))


def test_a_pod_of_a_class_change_can_run_on_another_node(cluster: Cluster, tmp_path: Path) -> None:
    """The scheduler places the pod of a replicated volume: the run only needs it Running."""
    cluster.restarted_on = WORKER_B

    result = _move(tmp_path, storage_class=LONGHORN)

    assert (result.plan.target_node, result.new_volume) == (WORKER_A, NEW_VOLUME)
    assert cluster.changes[-3:] == _pause(True, ("grafana", "cluster", "bootstrap"))


def test_a_pod_of_a_class_change_that_does_not_run_leaves_argo_cd_paused(
    cluster: Cluster, tmp_path: Path
) -> None:
    cluster.restarted_phase = "Pending"

    with pytest.raises(VolumeMoveStrandedError) as stranded:
        _move(tmp_path, storage_class=LONGHORN)

    assert len(stranded.value.remaining) == 2
    assert MESSAGES.k8s.volume_move_not_running.format(
        claim=CLAIM, pods=f"{WORKER_A} (Pending)"
    ) in str(stranded.value)
    assert not any(change.endswith("enabled=true") for change in cluster.changes)


def test_an_ended_pod_of_the_claim_is_deleted_before_the_old_claim(
    cluster: Cluster, tmp_path: Path
) -> None:
    """An ended pod still holds the claim, so the delete of the claim would wait for it (#7465)."""
    cluster.ended_pod = True

    _move(tmp_path)

    deleted = cluster.changes.index(f"delete pod {ENDED_POD}")
    assert deleted < cluster.changes.index("delete pvc grafana")
    assert deleted > cluster.changes.index("delete pod grafana-src grafana-dst")


def test_the_dry_run_deletes_the_ended_pods_before_the_old_claim(
    process_fake: ProcessFake,
) -> None:
    requests = dry_run_volume_move(NAMESPACE, CLAIM, parents=PARENTS, context=CONTEXT)

    deletes = [r.argv[4:6] for r in requests if r.argv[3] == "delete"]
    assert deletes.index(("pod", "<ended pod>")) < deletes.index(("pvc", CLAIM))


def test_an_ended_pod_of_the_claim_is_not_a_pod_of_the_move(
    cluster: Cluster, process_fake: ProcessFake, tmp_path: Path
) -> None:
    """A pod that has ended holds no volume, and a scale to zero does not delete it (#7431)."""
    cluster.ended_pod = True

    plan = _plan()
    _move(tmp_path)

    assert plan.pods == (POD,)
    waits = [call.argv for call in process_fake.calls if "wait" in call.argv]
    assert not any(f"pod/{ENDED_POD}" in argv for argv in waits)


# ── A size change ──────────────────────────────────────────────────────────


def test_a_size_change_makes_both_claims_with_the_new_size(
    cluster: Cluster, tmp_path: Path
) -> None:
    """local-path does not limit the data to the size of the claim, but Longhorn does (#7484)."""
    plan = _plan(storage_class=LONGHORN, size="10Gi")
    _move(tmp_path, storage_class=LONGHORN, size="10Gi")

    assert (plan.size, plan.target_size, plan.new_size) == ("5Gi", "10Gi", "10Gi")
    claims = [item for item in cluster.created if item["kind"] == "PersistentVolumeClaim"]
    assert [claim["spec"]["resources"]["requests"]["storage"] for claim in claims] == [
        "10Gi",
        "10Gi",
    ]


def test_the_size_of_the_old_claim_is_a_move_that_keeps_it(cluster: Cluster) -> None:
    assert _plan(size="5Gi") == PLAN


def test_the_dry_run_of_a_size_change_shows_the_new_size(process_fake: ProcessFake) -> None:
    requests = dry_run_volume_move(
        NAMESPACE, CLAIM, parents=PARENTS, storage_class=LONGHORN, size="10Gi", context=CONTEXT
    )

    claims = [
        json.loads(request.stdin)
        for request in requests
        if request.stdin and '"PersistentVolumeClaim"' in request.stdin
    ]
    assert [claim["spec"]["resources"]["requests"]["storage"] for claim in claims] == [
        "10Gi",
        "10Gi",
    ]
    assert process_fake.calls == []


# ── An access mode change ─────────────────────────────────────────────────


def test_an_access_mode_change_makes_both_claims_with_the_new_mode(
    cluster: Cluster, tmp_path: Path
) -> None:
    """A claim of several pods becomes ReadWriteMany on a replicated class (#7459)."""
    plan = _plan(storage_class=LONGHORN, access_mode="ReadWriteMany")
    _move(tmp_path, storage_class=LONGHORN, access_mode="ReadWriteMany")

    assert (plan.access_modes, plan.target_access_modes, plan.new_access_modes) == (
        ("ReadWriteOnce",),
        ("ReadWriteMany",),
        ("ReadWriteMany",),
    )
    claims = [item for item in cluster.created if item["kind"] == "PersistentVolumeClaim"]
    assert [claim["spec"]["accessModes"] for claim in claims] == [
        ["ReadWriteMany"],
        ["ReadWriteMany"],
    ]


def test_the_access_mode_of_the_old_claim_is_a_move_that_keeps_it(cluster: Cluster) -> None:
    assert _plan(access_mode="ReadWriteOnce") == PLAN


def test_the_dry_run_of_an_access_mode_change_shows_the_new_mode(
    process_fake: ProcessFake,
) -> None:
    requests = dry_run_volume_move(
        NAMESPACE,
        CLAIM,
        parents=PARENTS,
        storage_class=LONGHORN,
        access_mode="ReadWriteMany",
        context=CONTEXT,
    )

    claims = [
        json.loads(request.stdin)
        for request in requests
        if request.stdin and '"PersistentVolumeClaim"' in request.stdin
    ]
    assert [claim["spec"]["accessModes"] for claim in claims] == [
        ["ReadWriteMany"],
        ["ReadWriteMany"],
    ]
    assert process_fake.calls == []


def test_a_running_sync_of_a_paused_application_is_waited_for(
    cluster: Cluster, tmp_path: Path
) -> None:
    """A pause does not stop a sync that runs: it can make the claim again from git (#7464)."""
    cluster.operation_phase = "Running"

    _move(tmp_path)

    # A retrying operation has `finishedAt` between its attempts, so the run ends it (#7485).
    ends = [
        step
        for name in PAUSE
        for step in (f"patch application {name} terminate", f"wait application/{name}")
    ]
    first = cluster.changes.index(ends[0])
    assert cluster.changes[first : first + 6] == ends
    assert first > cluster.changes.index(_pause(False, PAUSE)[-1])
    second = cluster.changes.index(ends[0], first + 1)
    assert cluster.changes[second : second + 6] == ends
    assert second < cluster.changes.index("delete pod grafana-src grafana-dst")


def test_a_sync_that_ends_by_itself_during_the_wait_lets_the_move_go_on(
    cluster: Cluster, tmp_path: Path
) -> None:
    cluster.operation_phase = "Running"
    cluster.operation_ends_alone = True

    result = _move(tmp_path)

    assert result.new_volume == NEW_VOLUME
    assert cluster.changes[-3:] == _pause(True, ("grafana", "cluster", "bootstrap"))


def test_no_running_sync_means_no_wait(cluster: Cluster, tmp_path: Path) -> None:
    _move(tmp_path)

    assert not any(change.startswith("wait application/") for change in cluster.changes)


def test_a_sync_that_does_not_end_undoes_the_move(cluster: Cluster, tmp_path: Path) -> None:
    cluster.operation_phase = "Running"
    cluster.operation_never_ends = True

    with pytest.raises(VolumeMoveError) as failed:
        _move(tmp_path)

    assert not isinstance(failed.value, VolumeMoveStrandedError)
    assert cluster.changes[-3:] == _pause(True, ("grafana", "cluster", "bootstrap"))
    assert "delete pvc grafana" not in cluster.changes


# ── Refusals: nothing changes ──────────────────────────────────────────────


def _not_bound(cluster: Cluster) -> tuple[dict[str, Any], str]:
    cluster.claim_phase = "Pending"
    return {}, MESSAGES.k8s.volume_move_claim_not_bound.format(
        namespace=NAMESPACE, claim=CLAIM, phase="Pending"
    )


def _on_a_worker(cluster: Cluster) -> tuple[dict[str, Any], str]:
    cluster.volume_node = WORKER_A
    return {}, MESSAGES.k8s.volume_move_not_on_control_plane.format(
        volume=OLD_VOLUME, node=WORKER_A
    )


def _target_on_the_control_plane(cluster: Cluster) -> tuple[dict[str, Any], str]:
    cluster.volume_node = WORKER_A
    return {"to_node": CONTROL_PLANE}, MESSAGES.k8s.volume_move_target_control_plane.format(
        node=CONTROL_PLANE
    )


def _target_is_the_source(cluster: Cluster) -> tuple[dict[str, Any], str]:
    cluster.volume_node = WORKER_A
    return {"to_node": WORKER_A}, MESSAGES.k8s.volume_move_target_is_source.format(
        volume=OLD_VOLUME, node=WORKER_A
    )


def _unknown_target(cluster: Cluster) -> tuple[dict[str, Any], str]:
    return {"to_node": "worker-z"}, MESSAGES.k8s.volume_move_unknown_node.format(node="worker-z")


def _deletes_claims_on_scale_down(cluster: Cluster) -> tuple[dict[str, Any], str]:
    cluster.workload_kind = "StatefulSet"
    cluster.when_scaled = "Delete"
    return {}, MESSAGES.k8s.volume_move_retention_delete.format(name=CLAIM, claim=CLAIM)


def _leftovers(cluster: Cluster) -> tuple[dict[str, Any], str]:
    cluster.leftovers = ("pod/grafana-src", "persistentvolumeclaim/grafana-move")
    return {}, MESSAGES.k8s.volume_move_leftovers.format(
        names="pod/grafana-src, persistentvolumeclaim/grafana-move"
    )


def _no_pod_mounts_the_claim(cluster: Cluster) -> tuple[dict[str, Any], str]:
    cluster.replicas = 0
    return {}, MESSAGES.k8s.volume_move_no_pods.format(namespace=NAMESPACE, claim=CLAIM)


def _claim_missing(cluster: Cluster) -> tuple[dict[str, Any], str]:
    cluster.claim_exists = False
    return {}, MESSAGES.k8s.volume_move_claim_missing.format(namespace=NAMESPACE, claim=CLAIM)


def _owned_by_a_job(cluster: Cluster) -> tuple[dict[str, Any], str]:
    cluster.owner_kind = "Job"
    return {}, MESSAGES.k8s.volume_move_unsupported_owner.format(pod=POD, owner="Job backup")


def _unknown_application(cluster: Cluster) -> tuple[dict[str, Any], str]:
    cluster.known_applications = ("bootstrap", "cluster")
    return {}, MESSAGES.k8s.volume_move_unknown_application.format(
        application="grafana", namespace="argocd"
    )


def _bad_size(cluster: Cluster) -> tuple[dict[str, Any], str]:
    return {"size": "lots"}, MESSAGES.k8s.volume_move_bad_size.format(size="lots")


def _smaller_size(cluster: Cluster) -> tuple[dict[str, Any], str]:
    return {"size": "1Gi"}, MESSAGES.k8s.volume_move_smaller_size.format(size="1Gi", old="5Gi")


def _unknown_access_mode(cluster: Cluster) -> tuple[dict[str, Any], str]:
    return {"access_mode": "ReadWriteSome"}, MESSAGES.k8s.volume_move_unknown_access_mode.format(
        access_mode="ReadWriteSome",
        modes="ReadWriteOnce, ReadOnlyMany, ReadWriteMany, ReadWriteOncePod",
    )


def _unknown_storage_class(cluster: Cluster) -> tuple[dict[str, Any], str]:
    return {"storage_class": "fast"}, MESSAGES.k8s.volume_move_unknown_storage_class.format(
        storage_class="fast"
    )


def _target_without_the_driver(cluster: Cluster) -> tuple[dict[str, Any], str]:
    return (
        {"storage_class": LONGHORN, "to_node": WORKER_B},
        MESSAGES.k8s.volume_move_target_no_driver.format(
            node=WORKER_B, storage_class=LONGHORN, driver=LONGHORN_DRIVER
        ),
    )


def _no_worker_has_the_driver(cluster: Cluster) -> tuple[dict[str, Any], str]:
    cluster.csi_nodes = {CONTROL_PLANE: (LONGHORN_DRIVER,), WORKER_A: (), WORKER_B: ()}
    return {"storage_class": LONGHORN}, MESSAGES.k8s.volume_move_no_target_for_class.format(
        storage_class=LONGHORN
    )


@pytest.mark.parametrize(
    "precondition",
    [
        _bad_size,
        _smaller_size,
        _unknown_access_mode,
        _unknown_storage_class,
        _target_without_the_driver,
        _no_worker_has_the_driver,
        _claim_missing,
        _owned_by_a_job,
        _unknown_application,
        _not_bound,
        _on_a_worker,
        _target_on_the_control_plane,
        _target_is_the_source,
        _unknown_target,
        _deletes_claims_on_scale_down,
        _leftovers,
        _no_pod_mounts_the_claim,
    ],
)
def test_a_move_that_cannot_run_safely_is_refused_and_changes_nothing(
    cluster: Cluster, precondition: Any
) -> None:
    options, problem = precondition(cluster)

    with pytest.raises(VolumeMoveRefusedError) as refused:
        _plan(**options)

    assert (refused.value.problems, refused.value.error_code, refused.value.exit_code) == (
        (problem,),
        "K8S_VOLUME_MOVE_REFUSED",
        1,
    )
    assert cluster.changes == []


# ── A full move ────────────────────────────────────────────────────────────


def test_a_move_copies_compares_rebinds_the_claim_and_resumes_argo_cd(
    cluster: Cluster, process_fake: ProcessFake, tmp_path: Path
) -> None:
    result = _move(tmp_path)

    assert cluster.changes == [
        *BEFORE_COPY,
        "copy",
        "patch pv pvc-new reclaim=Retain",
        "patch pv pvc-old reclaim=Retain",
        "delete pod grafana-src grafana-dst",
        "delete networkpolicy grafana-copy",
        "delete pvc grafana",
        "delete pvc grafana-move",
        "patch pv pvc-new claimRef=monitoring/grafana",
        "create PersistentVolumeClaim grafana",
        "annotate pvc grafana",
        "scale deployment/grafana --replicas=1",
        *_pause(True, ("grafana", "cluster", "bootstrap")),
    ]
    assert (result.new_volume, result.digest) == (
        NEW_VOLUME,
        CopyDigest(entries=12, files=7, bytes=4096, metadata="a" * 64, content="b" * 64),
    )
    assert json.loads(result.saved_claim.read_text(encoding="utf-8")) == _claim_object()


def test_the_claim_is_made_again_without_its_last_applied_configuration_then_gets_it_back(
    cluster: Cluster, process_fake: ProcessFake, tmp_path: Path
) -> None:
    _move(tmp_path)

    assert cluster.created[-1] == {
        "apiVersion": "v1",
        "kind": "PersistentVolumeClaim",
        "metadata": {
            "name": CLAIM,
            "namespace": NAMESPACE,
            "labels": {
                "app.kubernetes.io/instance": "grafana",
                "app.kubernetes.io/name": "grafana",
            },
            "annotations": {
                "argocd.argoproj.io/sync-options": "Prune=false,Delete=false",
                TRACKING: "grafana:/PersistentVolumeClaim:monitoring/grafana",
            },
        },
        "spec": {
            "accessModes": ["ReadWriteOnce"],
            "resources": {"requests": {"storage": "5Gi"}},
            "storageClassName": "local-path",
            "volumeMode": "Filesystem",
            "volumeName": NEW_VOLUME,
        },
    }
    annotate = next(call.argv for call in process_fake.calls if "annotate" in call.argv)
    assert annotate[-1] == f"kubectl.kubernetes.io/last-applied-configuration={LAST_APPLIED}"


def test_the_copy_pods_mount_each_claim_on_its_own_node(
    cluster: Cluster, process_fake: ProcessFake, tmp_path: Path
) -> None:
    _move(tmp_path)

    pods = {
        item["metadata"]["name"]: item["spec"] for item in cluster.created if item["kind"] == "Pod"
    }
    assert pods["grafana-dst"]["nodeSelector"] == {"kubernetes.io/hostname": WORKER_B}
    assert pods["grafana-src"]["tolerations"] == [
        {"key": "example.com/dedicated", "operator": "Exists"},
        {
            "key": "node.kubernetes.io/unschedulable",
            "operator": "Exists",
            "effect": "NoSchedule",
        },
    ]
    assert [
        (spec["volumes"][0]["persistentVolumeClaim"], spec["containers"][0]["volumeMounts"][0])
        for spec in (pods["grafana-src"], pods["grafana-dst"])
    ] == [
        (
            {"claimName": CLAIM, "readOnly": True},
            {"name": "data", "mountPath": "/src", "readOnly": True},
        ),
        (
            {"claimName": "grafana-move", "readOnly": False},
            {"name": "data", "mountPath": "/dst", "readOnly": False},
        ),
    ]


def test_the_copy_command_comes_from_copy_argv(
    cluster: Cluster, process_fake: ProcessFake, tmp_path: Path
) -> None:
    """The move streams the command that `copy_argv` builds, so a measure runs the same pipe."""
    # Imported here, so the file collects on the base commit and this test fails there.
    from devops_cli.k8s.volume_move import copy_argv

    plan = _plan()
    _move(tmp_path)

    streamed = next(call.argv for call in process_fake.calls if call.argv[0] == "bash")
    assert list(streamed) == copy_argv(
        plan.namespace, plan.source_pod, plan.destination_pod, CONTEXT
    )


def test_the_copy_sends_the_data_from_pod_to_pod_not_through_the_api_server(
    cluster: Cluster, process_fake: ProcessFake, tmp_path: Path
) -> None:
    """The stdout of an exec stream loses data at full speed (#7408), so each exec carries only a
    script and its result, and tar goes over the pod network to a listener in the destination."""
    # Imported here, so the file collects on the base commit and this test fails there.
    from devops_cli.config.constants import (
        CONST_K8S_VOLUME_MOVE_LISTEN_SCRIPT,
        CONST_K8S_VOLUME_MOVE_LISTENER,
        CONST_K8S_VOLUME_MOVE_RESULT_SCRIPT,
        CONST_K8S_VOLUME_MOVE_SEND_SCRIPT,
    )

    _move(tmp_path)

    kubectl = ["kubectl", "--context", CONTEXT]

    def exec_in(pod: str, script: str, name: str, *args: str) -> list[str]:
        return [*kubectl, "exec", pod, "-n", NAMESPACE, "--", "bash", "-c", script, name, *args]

    pod_ip = [*kubectl, "get", "pod", "grafana-dst", "-n", NAMESPACE, "-o"]
    listen = exec_in(
        "grafana-dst",
        CONST_K8S_VOLUME_MOVE_LISTEN_SCRIPT,
        "volume-move-listen",
        CONST_K8S_VOLUME_MOVE_LISTENER,
        "7373",
        "/dst",
    )
    send = exec_in("grafana-src", CONST_K8S_VOLUME_MOVE_SEND_SCRIPT, "volume-move-send")
    result = exec_in(
        "grafana-dst", CONST_K8S_VOLUME_MOVE_RESULT_SCRIPT, "volume-move-result", "300"
    )
    script = next(call.argv[-1] for call in process_fake.calls if call.argv[0] == "bash")
    assert script == "\n".join(
        [
            "set -eu",
            f"ip=$({shlex.join([*pod_ip, 'jsonpath={.status.podIP}'])})",
            shlex.join(listen),
            shlex.join(send) + ' "$ip" 7373 /src',
            shlex.join(result),
        ]
    )
    assert not {"-i", "--stdin"} & {*listen, *send, *result}


def test_the_source_sends_gnu_tar_to_the_listener_that_extracts_it() -> None:
    from devops_cli.config.constants import (
        CONST_K8S_VOLUME_MOVE_LISTENER,
        CONST_K8S_VOLUME_MOVE_SEND_SCRIPT,
    )

    assert CONST_K8S_VOLUME_MOVE_SEND_SCRIPT == (
        'exec 3>"/dev/tcp/$1/$2" && tar -C "$3" --numeric-owner --sparse -cpf - . >&3'
    )
    assert 'system("tar", "-C", $dir, "--numeric-owner", "-xpf", "-")' in (
        CONST_K8S_VOLUME_MOVE_LISTENER
    )


def test_the_copy_policy_lets_the_copy_pods_reach_each_other_on_the_copy_port_only(
    cluster: Cluster, tmp_path: Path
) -> None:
    """A namespace that refuses traffic by default still lets the source reach the listener."""
    _move(tmp_path)

    labels = {
        "app.kubernetes.io/managed-by": "devops-cli",
        "app.kubernetes.io/component": "volume-move",
    }
    peers = [{"podSelector": {"matchLabels": labels}}]
    ports = [{"protocol": "TCP", "port": 7373}]
    assert next(item for item in cluster.created if item["kind"] == "NetworkPolicy") == {
        "apiVersion": "networking.k8s.io/v1",
        "kind": "NetworkPolicy",
        "metadata": {"name": "grafana-copy", "namespace": NAMESPACE, "labels": labels},
        "spec": {
            "podSelector": {"matchLabels": labels},
            "policyTypes": ["Ingress", "Egress"],
            "ingress": [{"from": peers, "ports": ports}],
            "egress": [{"to": peers, "ports": ports}],
        },
    }


def test_the_plan_looks_for_the_copy_policy_of_an_earlier_move(
    cluster: Cluster, process_fake: ProcessFake
) -> None:
    _plan()

    leftovers = next(call.argv for call in process_fake.calls if "pod/grafana-src" in call.argv)
    assert "networkpolicy/grafana-copy" in leftovers


# ── Failures before the point of no return: the move undoes its steps ──────


def test_a_digest_difference_undoes_every_step(cluster: Cluster, tmp_path: Path) -> None:
    cluster.destination_digest = OTHER_DIGEST

    with pytest.raises(VolumeMoveError) as failed:
        _move(tmp_path)

    assert not isinstance(failed.value, VolumeMoveStrandedError)
    assert cluster.changes == [*BEFORE_COPY, "copy", *UNDO_AFTER_COPY]
    assert (failed.value.error_code, failed.value.undo_failures) == ("K8S_VOLUME_MOVE_FAILED", ())
    assert cluster.claim_volume == OLD_VOLUME


def test_an_incomplete_digest_undoes_every_step(cluster: Cluster, tmp_path: Path) -> None:
    cluster.destination_digest = "entries 12\n"

    with pytest.raises(VolumeMoveError) as failed:
        _move(tmp_path)

    assert cluster.changes == [*BEFORE_COPY, "copy", *UNDO_AFTER_COPY]
    assert MESSAGES.k8s.volume_move_digest_unreadable.format(
        pod="grafana-dst", output="entries 12\n"
    ) in str(failed.value)


def test_a_dropped_copy_is_retried_once_on_an_empty_destination(
    cluster: Cluster, tmp_path: Path
) -> None:
    cluster.copy_failures = 1
    progress: list[str] = []

    result = _move(tmp_path, progress)

    assert cluster.changes[len(BEFORE_COPY) : len(BEFORE_COPY) + 4] == [
        "copy",
        "empty /dst",
        "copy",
        "patch pv pvc-new reclaim=Retain",
    ]
    assert result.new_volume == NEW_VOLUME
    assert any("connection reset by peer" in line for line in progress)


def test_a_second_dropped_copy_undoes_every_step(cluster: Cluster, tmp_path: Path) -> None:
    cluster.copy_failures = 2

    with pytest.raises(VolumeMoveError) as raised:
        _move(tmp_path)
    assert raised.value.error_code == "K8S_VOLUME_MOVE_FAILED"

    assert cluster.changes == [*BEFORE_COPY, "copy", "empty /dst", "copy", *UNDO_AFTER_COPY]


def test_an_interrupted_copy_undoes_every_step(cluster: Cluster, tmp_path: Path) -> None:
    cluster.interrupt_copy = True

    with pytest.raises(VolumeMoveError) as raised:
        _move(tmp_path)
    assert raised.value.error_code == "K8S_VOLUME_MOVE_FAILED"

    assert cluster.changes == [*BEFORE_COPY, "copy", *UNDO_AFTER_COPY]


def test_a_failed_request_is_undone_as_if_it_made_its_change(
    cluster: Cluster, tmp_path: Path
) -> None:
    cluster.failing = frozenset({"create PersistentVolumeClaim grafana-move"})

    with pytest.raises(VolumeMoveError) as raised:
        _move(tmp_path)
    assert raised.value.error_code == "K8S_VOLUME_MOVE_FAILED"

    assert cluster.changes == [
        *_pause(False, PAUSE),
        "create PersistentVolumeClaim grafana-move",
        "delete pvc grafana-move",
        *_pause(True, ("grafana", "cluster", "bootstrap")),
    ]


def test_an_undo_deletes_the_volume_that_a_class_binds_before_the_pod(
    cluster: Cluster, tmp_path: Path
) -> None:
    """A class such as `longhorn` binds the temporary claim at once and keeps its volume after a
    delete (reclaim policy Retain), so the undo sets that volume to Delete first (#7416)."""
    cluster.move_claim_volume = NEW_VOLUME
    cluster.failing = frozenset({"create Pod grafana-dst"})

    with pytest.raises(VolumeMoveError) as failed:
        _move(tmp_path)

    assert failed.value.error_code == "K8S_VOLUME_MOVE_FAILED"
    created = cluster.changes.index("create Pod grafana-dst")
    assert cluster.changes[created + 1 :] == [
        "delete pod grafana-dst",
        "delete networkpolicy grafana-copy",
        "patch pv pvc-new reclaim=Delete",
        "delete pvc grafana-move",
        *_pause(True, ("grafana", "cluster", "bootstrap")),
    ]


def test_an_undo_step_that_fails_is_reported_and_the_others_still_run(
    cluster: Cluster, tmp_path: Path
) -> None:
    cluster.destination_digest = OTHER_DIGEST
    cluster.failing = frozenset({"scale deployment/grafana --replicas=1"})

    with pytest.raises(VolumeMoveError) as failed:
        _move(tmp_path)

    assert cluster.changes == [*BEFORE_COPY, "copy", *UNDO_AFTER_COPY]
    assert [failure.split(":")[0] for failure in failed.value.undo_failures] == [
        MESSAGES.k8s.volume_move_undo_scale.format(workload="deployment/grafana", replicas=1)
    ]


# ── Failures after the point of no return: Argo CD stays paused ────────────


def test_a_failure_after_the_old_claim_is_deleted_leaves_argo_cd_paused(
    cluster: Cluster, tmp_path: Path
) -> None:
    cluster.failing = frozenset({"create PersistentVolumeClaim grafana"})

    with pytest.raises(VolumeMoveStrandedError) as stranded:
        _move(tmp_path)

    assert cluster.changes[-4:] == [
        "delete pvc grafana",
        "delete pvc grafana-move",
        "patch pv pvc-new claimRef=monitoring/grafana",
        "create PersistentVolumeClaim grafana",
    ]
    assert not any(change.endswith("enabled=true") for change in cluster.changes)
    error = stranded.value
    assert (error.error_code, error.paused, error.old_volume, error.new_volume) == (
        "K8S_VOLUME_MOVE_STRANDED",
        PAUSE,
        OLD_VOLUME,
        NEW_VOLUME,
    )
    assert error.remaining == describe_volume_move(PLAN)[10:]
    assert json.loads(error.saved_claim.read_text(encoding="utf-8")) == _claim_object()


def test_a_pod_off_the_target_node_after_the_move_leaves_argo_cd_paused(
    cluster: Cluster, tmp_path: Path
) -> None:
    cluster.restarted_on = WORKER_A

    with pytest.raises(VolumeMoveStrandedError) as stranded:
        _move(tmp_path)

    assert stranded.value.remaining == describe_volume_move(PLAN)[11:]
    assert cluster.changes[-1] == "scale deployment/grafana --replicas=1"


# ── The dry run ────────────────────────────────────────────────────────────


def test_the_dry_run_makes_no_request_and_lists_the_writes_in_order(
    process_fake: ProcessFake,
) -> None:
    requests = dry_run_volume_move(NAMESPACE, CLAIM, parents=PARENTS, context=CONTEXT)

    assert process_fake.calls == []
    argvs = [request.argv for request in requests]

    def first(*words: str) -> int:
        return next(
            index
            for index, argv in enumerate(argvs)
            if all(any(word in token for token in argv) for word in words)
        )

    order = [
        first("get", "cronjob", "volume-move"),
        first("get", "pvc", "--ignore-not-found", "-o", "json"),
        first("patch", "application", '"enabled": false'),
        first("scale", "--replicas=0"),
        first("bash", "pipefail"),
        first("exec", "digest", "/dst"),
        first("patch", "pv", "<new-volume>", "Retain"),
        first("delete", "pvc", f"{CLAIM}-move") - 1,
        first("patch", "pv", "claimRef"),
        first("annotate", "pvc", "last-applied-configuration"),
        first("patch", "application", '"enabled": true'),
    ]
    assert order == sorted(order)
    assert argvs[order[7]][3:6] == ("delete", "pvc", CLAIM)
    assert {argv[:3] for argv in argvs} == {
        ("kubectl", "--context", CONTEXT),
        ("bash", "-o", "pipefail"),
    }


def test_the_dry_run_makes_the_copy_policy_before_the_pods_and_deletes_it_with_them(
    process_fake: ProcessFake,
) -> None:
    requests = dry_run_volume_move(NAMESPACE, CLAIM, parents=PARENTS, context=CONTEXT)

    created = [json.loads(r.stdin)["kind"] for r in requests if r.argv[3] == "create" and r.stdin]
    deletes = [r.argv[4:6] for r in requests if r.argv[3] == "delete"]
    assert created[:3] == ["PersistentVolumeClaim", "NetworkPolicy", "Pod"]
    assert deletes[:4] == [
        ("pod", "grafana-src"),
        ("networkpolicy", "grafana-copy"),
        ("pod", "<ended pod>"),
        ("pvc", CLAIM),
    ]
    assert process_fake.calls == []


def test_the_dry_run_of_a_class_change_reads_the_class_and_its_nodes_first(
    process_fake: ProcessFake,
) -> None:
    requests = dry_run_volume_move(
        NAMESPACE, CLAIM, parents=PARENTS, storage_class=LONGHORN, context=CONTEXT
    )

    assert process_fake.calls == []
    reads = [request.argv[3:5] for request in requests if request.argv[3] == "get"]
    order = [
        reads.index(("get", "storageclass")),
        reads.index(("get", "csidriver")),
        reads.index(("get", "csinodes")),
        reads.index(("get", "--raw")),
    ]
    assert order == sorted(order)
    claims = [
        json.loads(request.stdin)
        for request in requests
        if request.stdin and '"PersistentVolumeClaim"' in request.stdin
    ]
    assert [claim["spec"]["storageClassName"] for claim in claims] == [LONGHORN, LONGHORN]


def test_plan_volume_move_raises_when_cronjob_missing(cluster: Cluster) -> None:
    cluster.cronjob_exists = False
    with pytest.raises(VolumeMoveError) as exc_info:
        plan_volume_move(NAMESPACE, CLAIM, parents=PARENTS, context=CONTEXT)
    assert exc_info.value.error_code == "K8S_VOLUME_MOVE_FAILED"
    assert "volume-move" in str(exc_info.value)


def test_the_digest_leaves_out_the_lost_and_found_of_a_new_filesystem() -> None:
    """A new ext4 volume, such as one of `longhorn`, has `./lost+found`, and a local-path
    directory has none, so each count and digest leaves it out on both sides (#7414)."""
    # Imported here, so the file collects on the base commit and this test fails there.
    from devops_cli.config.constants import CONST_K8S_VOLUME_MOVE_DIGEST_SCRIPT

    finds = [line for line in CONST_K8S_VOLUME_MOVE_DIGEST_SCRIPT.splitlines() if "find " in line]

    assert [line.split("=", 1)[0] for line in finds] == [
        "entries",
        "files",
        "bytes",
        "metadata",
        "content",
    ]
    assert all("$(find . -path ./lost+found -prune -o " in line for line in finds)


def test_copy_pods_use_template_image_and_allow_root(cluster: Cluster, tmp_path: Path) -> None:
    _move(tmp_path)
    copy_pods = [
        obj
        for obj in cluster.created
        if obj.get("kind") == "Pod"
        and obj.get("metadata", {}).get("name") in ("grafana-src", "grafana-dst")
    ]
    assert len(copy_pods) == 2
    for pod in copy_pods:
        container = pod["spec"]["containers"][0]
        assert container["image"] == VOLUME_MOVE_IMAGE
        assert "securityContext" not in container


# ── The command ────────────────────────────────────────────────────────────


def test_move_plan_prints_the_steps_and_changes_nothing(cli: Any, cluster: Cluster) -> None:
    result = cli("k8s", "volume", "move", "monitoring/grafana", "--plan", "--context", CONTEXT)

    assert result.exit_code == 0, result.output
    assert MESSAGES.k8s.volume_move_plan_heading.format(namespace=NAMESPACE, claim=CLAIM) in (
        result.output
    )
    assert (
        "9. " + MESSAGES.k8s.volume_move_step_delete_claim.format(namespace=NAMESPACE, claim=CLAIM)
        in result.output
    )
    assert cluster.changes == []


def test_move_plan_of_a_class_change_prints_the_two_classes(cli: Any, cluster: Cluster) -> None:
    result = cli(
        "k8s",
        "volume",
        "move",
        "monitoring/grafana",
        "--storage-class",
        LONGHORN,
        "--plan",
        "--context",
        CONTEXT,
    )

    assert result.exit_code == 0, result.output
    m = MESSAGES.k8s
    output = " ".join(result.output.split())
    for line in (
        m.volume_move_plan_claim.format(
            volume=OLD_VOLUME,
            size="5Gi",
            storage_class="local-path",
            node=CONTROL_PLANE,
            policy="Delete",
        ),
        m.volume_move_plan_target.format(
            node=WORKER_A, free=format_bytes(FREE_BYTES[WORKER_A]), storage_class=LONGHORN
        ),
    ):
        assert " ".join(line.split()) in output
    assert cluster.changes == []


def test_move_plan_of_a_size_change_prints_the_two_sizes(cli: Any, cluster: Cluster) -> None:
    result = cli(
        "k8s",
        "volume",
        "move",
        "monitoring/grafana",
        "--storage-class",
        LONGHORN,
        "--size",
        "10Gi",
        "--plan",
        "--context",
        CONTEXT,
    )

    assert result.exit_code == 0, result.output
    line = MESSAGES.k8s.volume_move_plan_size.format(old="5Gi", new="10Gi")
    assert " ".join(line.split()) in " ".join(result.output.split())
    assert cluster.changes == []


def test_move_plan_of_an_access_mode_change_prints_the_two_modes(
    cli: Any, cluster: Cluster
) -> None:
    result = cli(
        "k8s",
        "volume",
        "move",
        "monitoring/grafana",
        "--storage-class",
        LONGHORN,
        "--access-mode",
        "ReadWriteMany",
        "--plan",
        "--context",
        CONTEXT,
    )

    assert result.exit_code == 0, result.output
    line = MESSAGES.k8s.volume_move_plan_access_modes.format(
        old="ReadWriteOnce", new="ReadWriteMany"
    )
    assert " ".join(line.split()) in " ".join(result.output.split())
    assert cluster.changes == []


def test_move_of_a_class_change_names_the_class_when_done(cli: Any, cluster: Cluster) -> None:
    result = cli(
        "k8s", "volume", "move", "monitoring/grafana", "--storage-class", LONGHORN, "-c", CONTEXT
    )

    assert result.exit_code == 0, result.output
    done = MESSAGES.k8s.volume_move_done_class.format(
        namespace=NAMESPACE, claim=CLAIM, storage_class=LONGHORN
    )
    assert " ".join(done.split()) in " ".join(result.output.split())


def test_move_dry_run_prints_the_requests_and_makes_none(
    cli: Any, process_fake: ProcessFake
) -> None:
    result = cli("k8s", "volume", "move", "monitoring/grafana", "--dry-run", "--context", CONTEXT)

    assert result.exit_code == 0, result.output
    assert MESSAGES.k8s.volume_move_dry_run_heading in result.output
    assert "kubectl --context test-ctx delete pvc grafana -n monitoring" in result.output
    assert process_fake.calls == []


def test_move_prints_the_old_volume_to_delete_later(cli: Any, cluster: Cluster) -> None:
    result = cli("k8s", "volume", "move", "monitoring/grafana", "--context", CONTEXT)

    assert result.exit_code == 0, result.output
    assert (
        MESSAGES.k8s.volume_move_done.format(namespace=NAMESPACE, claim=CLAIM, node=WORKER_B)
        in result.output
    )
    assert (
        "kubectl --context test-ctx patch pv pvc-old -p "
        '\'{"spec": {"persistentVolumeReclaimPolicy": "Delete"}}\''
    ) in result.output


def test_move_refusal_names_each_problem_and_exits_1(cli: Any, cluster: Cluster) -> None:
    cluster.volume_node = WORKER_A

    result = cli("k8s", "volume", "move", "monitoring/grafana", "--context", CONTEXT)

    assert result.exit_code == 1
    assert (
        MESSAGES.k8s.volume_move_not_on_control_plane.format(volume=OLD_VOLUME, node=WORKER_A)
        in result.output
    )
    assert cluster.changes == []


def test_move_stranded_prints_the_saved_claim_and_the_paused_applications(
    cli: Any, cluster: Cluster
) -> None:
    cluster.failing = frozenset({"create PersistentVolumeClaim grafana"})

    result = cli("k8s", "volume", "move", "monitoring/grafana", "--context", CONTEXT)

    assert result.exit_code == 1
    assert (
        MESSAGES.k8s.volume_move_stranded_paused.format(
            applications="bootstrap, cluster, grafana", namespace=NAMESPACE, claim=CLAIM
        )
        in result.output
    )
    assert "Saved claim: " in result.output


def test_move_undone_prints_the_steps_it_undid(cli: Any, cluster: Cluster) -> None:
    cluster.destination_digest = OTHER_DIGEST

    result = cli("k8s", "volume", "move", "monitoring/grafana", "--context", CONTEXT)

    assert result.exit_code == 1
    assert (
        MESSAGES.k8s.volume_move_undone_steps.format(
            steps="; ".join(
                [
                    MESSAGES.k8s.volume_move_undo_delete.format(kind="pod", name="grafana-src"),
                    MESSAGES.k8s.volume_move_undo_scale.format(
                        workload="deployment/grafana", replicas=1
                    ),
                    MESSAGES.k8s.volume_move_undo_delete.format(kind="pod", name="grafana-dst"),
                    MESSAGES.k8s.volume_move_undo_delete.format(
                        kind="NetworkPolicy", name="grafana-copy"
                    ),
                    MESSAGES.k8s.volume_move_undo_discard.format(claim="grafana-move"),
                    *(
                        MESSAGES.k8s.volume_move_undo_resume.format(application=name)
                        for name in ("grafana", "cluster", "bootstrap")
                    ),
                ]
            )
        )
        in result.output
    )


def test_move_read_failure_exits_1_and_changes_nothing(cli: Any, cluster: Cluster) -> None:
    cluster.timeout_on = "nodes"

    result = cli("k8s", "volume", "move", "monitoring/grafana", "--plan", "--context", CONTEXT)

    assert result.exit_code == 1
    assert "did not end within" in result.output
    assert cluster.changes == []


@pytest.mark.parametrize("ref", ["grafana", "monitoring/grafana/extra", "Monitoring/grafana"])
def test_move_refuses_a_claim_that_is_not_namespace_slash_claim(
    cli: Any, process_fake: ProcessFake, ref: str
) -> None:
    result = cli("k8s", "volume", "move", ref, "--context", CONTEXT)

    assert result.exit_code == 2
    assert process_fake.calls == []
