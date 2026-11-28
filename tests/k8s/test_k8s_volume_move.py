"""`devops k8s volume move`: a local-path claim copied to a volume on another node and bound to it.

The cluster is a scripted answer of the shared process fake (#2186): each kubectl request reads
or changes the objects of `Cluster`, and `Cluster.changes` records, in order, every request that
changes the cluster. pv-migrate is an answer of the same fake (#7498). No test starts kubectl or
pv-migrate, and no test reaches a cluster.
"""

from __future__ import annotations

import json
import re
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
LAST_APPLIED = json.dumps(
    {"apiVersion": "v1", "kind": "PersistentVolumeClaim", "metadata": {"name": CLAIM}}
)
TRACKING = "argocd.argoproj.io/tracking-id"
PAUSE = ("bootstrap", "cluster", "grafana")
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
    copy_fails: bool = False
    interrupt_copy: bool = False
    copy_times_out: bool = False
    # The Pod Security level that the namespace enforces, the fsGroup of the pod template of the
    # workload, and whether pv-migrate is on PATH.
    pod_security: str = "privileged"
    fs_group: int | None = 472
    pv_migrate_installed: bool = True
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
    known_applications: tuple[str, ...] = ("bootstrap", "cluster", "grafana", "loki")
    application_owners: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    application_sets: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
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
    # The fsGroupPolicy of each CSIDriver.
    csi_drivers: dict[str, str] = field(
        default_factory=lambda: {LONGHORN_DRIVER: "ReadWriteOnceWithFSType"}
    )
    csi_nodes: dict[str, tuple[str, ...]] = field(
        default_factory=lambda: {CONTROL_PLANE: (), WORKER_A: (LONGHORN_DRIVER,), WORKER_B: ()}
    )
    changes: list[str] = field(default_factory=list)
    created: list[dict[str, Any]] = field(default_factory=list)
    # The argv and the Helm values of each pv-migrate copy.
    copies: list[tuple[list[str], dict[str, Any]]] = field(default_factory=list)

    def __call__(self, call: ProcessCall) -> subprocess.CompletedProcess[str]:
        argv = list(call.argv)
        if argv[0] == "pv-migrate":
            return self._pv_migrate(argv, call.stdin if isinstance(call.stdin, str) else None)
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
        return self._change(args, call.stdin if isinstance(call.stdin, str) else None)

    # ── reads ──────────────────────────────────────────────────────────────

    def _get(self, args: list[str]) -> str:
        what = args[1]
        if what == self.timeout_on:
            raise subprocess.TimeoutExpired(cmd=args, timeout=1)
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
            "applicationset": self._get_application_set,
            "namespace": self._get_namespace,
            "storageclass": self._get_storage_class,
            "csidriver": self._get_csi_driver,
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

    def _get_namespace(self, args: list[str]) -> str:
        labels = {"pod-security.kubernetes.io/enforce": self.pod_security}
        return json.dumps({"metadata": {"name": args[2], "labels": labels}})

    def _get_csi_driver(self, args: list[str]) -> str:
        policy = self.csi_drivers.get(args[2])
        if policy is None:
            return ""
        return json.dumps({"metadata": {"name": args[2]}, "spec": {"fsGroupPolicy": policy}})

    def _get_claim(self, args: list[str]) -> str:
        if args[-1] == "name":
            return "".join(f"{name}\n" for name in self.leftovers)
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
        security = {} if self.fs_group is None else {"fsGroup": self.fs_group}
        spec: dict[str, Any] = {
            "replicas": 1,
            "template": {"spec": {"securityContext": {"runAsUser": 472, **security}}},
        }
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

    def _get_application_set(self, args: list[str]) -> str:
        name = args[2]
        return json.dumps(
            {
                "metadata": {"name": name},
                "spec": {"ignoreApplicationDifferences": self.application_sets.get(name, [])},
            }
        )

    def _applications(self) -> list[dict[str, Any]]:
        items = []
        for name in self.known_applications:
            metadata: dict[str, Any] = {"name": name}
            if name in self.application_owners:
                metadata["ownerReferences"] = self.application_owners[name]
            items.append(
                {
                    "metadata": metadata,
                    "spec": {"syncPolicy": {"automated": {"enabled": True, "selfHeal": True}}},
                }
            )
        return items

    # ── pv-migrate ─────────────────────────────────────────────────────────

    def _pv_migrate(self, argv: list[str], stdin: str | None) -> subprocess.CompletedProcess[str]:
        if argv[1] == "cleanup":
            self.changes.append(f"pv-migrate cleanup {argv[2]}")
            return _ok("")
        values = json.loads(stdin or "{}")
        self.copies.append((argv, values))
        self.changes.append("pv-migrate")
        # The rsync pod of pv-migrate mounts the new claim on the node that the values select,
        # so local-path binds the new volume there.
        self.move_claim_volume = NEW_VOLUME
        self.target_hostname = values["rsync"]["nodeSelector"]["kubernetes.io/hostname"]
        if self.interrupt_copy:
            raise KeyboardInterrupt
        if self.copy_times_out:
            raise subprocess.TimeoutExpired(cmd=argv, timeout=1)
        if self.copy_fails:
            log = "".join(f"rsync progress line {n}\n" for n in range(40))
            return _failed(log + "rsync job failed with exit code 23")
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
def cluster(process_fake: ProcessFake, monkeypatch: pytest.MonkeyPatch) -> Cluster:
    scripted = Cluster()
    process_fake.answer(lambda _call: True, ProcessAnswer(side_effect=scripted))
    monkeypatch.setattr(
        "devops_cli.k8s.volume_move.shutil.which",
        lambda name: f"/usr/local/bin/{name}" if scripted.pv_migrate_installed else None,
    )
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
)
BEFORE_COPY = [
    *_pause(False, PAUSE),
    "create PersistentVolumeClaim grafana-move",
    "scale deployment/grafana --replicas=0",
]
UNDO_AFTER_COPY = [
    "scale deployment/grafana --replicas=1",
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
            claim="grafana-move", size="5Gi", storage_class="local-path"
        ),
        m.volume_move_step_stop.format(workloads="deployment/grafana", pods=POD),
        m.volume_move_step_copy.format(
            claim=CLAIM, move_claim="grafana-move", source=CONTROL_PLANE, target=WORKER_B
        ),
        m.volume_move_step_retain.format(claim="grafana-move", volume=OLD_VOLUME),
        m.volume_move_step_settle,
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
        claim="grafana-move", size="5Gi", storage_class=LONGHORN
    )
    assert steps[3] == m.volume_move_step_copy.format(
        claim=CLAIM, move_claim="grafana-move", source=CONTROL_PLANE, target=WORKER_A
    )
    assert steps[9] == m.volume_move_step_start_any_node.format(workloads="deployment/grafana to 1")


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
    assert deleted > cluster.changes.index("patch pv pvc-old reclaim=Retain")


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
    assert second > cluster.changes.index("pv-migrate")
    assert second < cluster.changes.index("delete pvc grafana")


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
    cluster.leftovers = ("persistentvolumeclaim/grafana-move",)
    return {}, MESSAGES.k8s.volume_move_leftovers.format(names="persistentvolumeclaim/grafana-move")


def _no_pv_migrate(cluster: Cluster) -> tuple[dict[str, Any], str]:
    cluster.pv_migrate_installed = False
    return {}, MESSAGES.k8s.volume_move_no_pv_migrate


def _restricted_without_fs_group(cluster: Cluster) -> tuple[dict[str, Any], str]:
    """pv-migrate --non-root keeps no owner, so the workload reads the copy only through its
    fsGroup (#7449, #7451)."""
    cluster.pod_security = "restricted"
    cluster.fs_group = None
    return {"storage_class": LONGHORN}, MESSAGES.k8s.volume_move_restricted_no_fs_group.format(
        namespace=NAMESPACE, workload="deployment/grafana"
    )


def _restricted_on_local_path(cluster: Cluster) -> tuple[dict[str, Any], str]:
    """The kubelet gives no fsGroup to the files of a local-path volume."""
    cluster.pod_security = "restricted"
    return {}, MESSAGES.k8s.volume_move_restricted_class.format(
        namespace=NAMESPACE, storage_class="local-path"
    )


def _restricted_on_a_driver_without_fs_group(cluster: Cluster) -> tuple[dict[str, Any], str]:
    cluster.pod_security = "restricted"
    cluster.csi_drivers = {LONGHORN_DRIVER: "None"}
    return {"storage_class": LONGHORN}, MESSAGES.k8s.volume_move_restricted_class.format(
        namespace=NAMESPACE, storage_class=LONGHORN
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
        _no_pv_migrate,
        _restricted_without_fs_group,
        _restricted_on_local_path,
        _restricted_on_a_driver_without_fs_group,
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


def test_a_move_copies_with_pv_migrate_rebinds_the_claim_and_resumes_argo_cd(
    cluster: Cluster, process_fake: ProcessFake, tmp_path: Path
) -> None:
    result = _move(tmp_path)

    assert cluster.changes == [
        *BEFORE_COPY,
        "pv-migrate",
        "patch pv pvc-new reclaim=Retain",
        "patch pv pvc-old reclaim=Retain",
        "delete pvc grafana",
        "delete pvc grafana-move",
        "patch pv pvc-new claimRef=monitoring/grafana",
        "create PersistentVolumeClaim grafana",
        "annotate pvc grafana",
        "scale deployment/grafana --replicas=1",
        *_pause(True, ("grafana", "cluster", "bootstrap")),
    ]
    assert result.new_volume == NEW_VOLUME
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


def test_the_copy_runs_pv_migrate_from_the_old_claim_to_the_move_claim(
    cluster: Cluster, tmp_path: Path
) -> None:
    """pv-migrate copies with rsync over SSH from a pod with the old claim to a pod with the new
    claim, through a ClusterIP Service, and removes its pods itself (#7498)."""
    _move(tmp_path)

    [(argv, values)] = cluster.copies
    operation = argv[argv.index("--id") + 1]
    assert re.fullmatch(r"volume-move-[0-9a-f]{8}", operation)
    assert argv == [
        "pv-migrate",
        "--source-namespace",
        NAMESPACE,
        "--source",
        CLAIM,
        "--dest-namespace",
        NAMESPACE,
        "--dest",
        "grafana-move",
        "--strategies",
        "clusterip",
        "--id",
        operation,
        "--helm-timeout",
        "300s",
        "--helm-values",
        "-",
        "--show-progress-bar=false",
        "--source-context",
        CONTEXT,
        "--dest-context",
        CONTEXT,
    ]
    # The rsync pod mounts the new claim on the target node, so local-path binds the new volume
    # there. The sshd pod mounts the old claim on its node, which a cordon often marks (#5305).
    assert values == {
        "rsync": {"nodeSelector": {"kubernetes.io/hostname": WORKER_B}},
        "sshd": {
            "tolerations": [
                {"key": "example.com/dedicated", "operator": "Exists"},
                {
                    "key": "node.kubernetes.io/unschedulable",
                    "operator": "Exists",
                    "effect": "NoSchedule",
                },
            ]
        },
    }


def test_a_namespace_that_enforces_restricted_copies_with_non_root(
    cluster: Cluster, tmp_path: Path
) -> None:
    """pv-migrate --non-root sets the securityContext that Pod Security restricted asks for on
    its pods (#7449). As user 10000, rsync cannot chmod the root folder of the new volume, which
    root owns, so `-p` of `-a` failed with exit 23 on `.` in the live test of #7518: --no-perms
    makes rsync keep the mode of that folder and give each new file its source mode under the
    umask of the rsync pod."""
    cluster.pod_security = "restricted"

    plan = _plan(storage_class=LONGHORN)
    _move(tmp_path, storage_class=LONGHORN)

    assert plan.non_root
    [(argv, values)] = cluster.copies
    assert argv[-2:] == ["--non-root", "--rsync-extra-args=--no-perms"]
    assert values["rsync"] == {"nodeSelector": {"kubernetes.io/hostname": WORKER_A}}


def test_a_copy_as_root_keeps_the_modes_of_rsync_a(cluster: Cluster, tmp_path: Path) -> None:
    """As root, rsync -a sets the mode of each file and of the root folder of the new volume."""
    _move(tmp_path)

    [(argv, _values)] = cluster.copies
    assert not [arg for arg in argv if arg.startswith(("--non-root", "--rsync-extra-args"))]


def test_a_namespace_that_does_not_enforce_restricted_copies_as_root(cluster: Cluster) -> None:
    """A copy as root keeps the owner and the group of each file."""
    for level in ("privileged", "baseline", ""):
        cluster.pod_security = level
        assert not _plan().non_root


def test_the_plan_reads_no_class_of_a_move_that_copies_as_root(
    cluster: Cluster, process_fake: ProcessFake
) -> None:
    _plan()

    assert not any("storageclass" in call.argv for call in process_fake.calls)


# ── Failures before the point of no return: the move undoes its steps ──────


def test_a_failed_copy_undoes_every_step(cluster: Cluster, tmp_path: Path) -> None:
    """pv-migrate removes its own pods when it fails, so the undo starts with the workload."""
    cluster.copy_fails = True

    with pytest.raises(VolumeMoveError) as failed:
        _move(tmp_path)

    assert not isinstance(failed.value, VolumeMoveStrandedError)
    assert cluster.changes == [*BEFORE_COPY, "pv-migrate", *UNDO_AFTER_COPY]
    assert (failed.value.error_code, failed.value.undo_failures) == ("K8S_VOLUME_MOVE_FAILED", ())
    assert cluster.claim_volume == OLD_VOLUME


def test_a_failed_copy_names_the_end_of_the_output_of_pv_migrate(
    cluster: Cluster, tmp_path: Path
) -> None:
    cluster.copy_fails = True

    with pytest.raises(VolumeMoveError) as failed:
        _move(tmp_path)

    assert "rsync job failed with exit code 23" in str(failed.value)
    assert "rsync progress line 0\n" not in str(failed.value)


@pytest.mark.parametrize("stop", ["interrupt_copy", "copy_times_out"])
def test_a_copy_that_the_run_stops_removes_the_objects_of_pv_migrate_first(
    cluster: Cluster, tmp_path: Path, stop: str
) -> None:
    """pv-migrate has no time to remove its pods when the run stops it, and its rsync pod would
    hold the move claim."""
    setattr(cluster, stop, True)

    with pytest.raises(VolumeMoveError) as raised:
        _move(tmp_path)

    [(argv, _values)] = cluster.copies
    operation = argv[argv.index("--id") + 1]
    assert raised.value.error_code == "K8S_VOLUME_MOVE_FAILED"
    assert cluster.changes == [
        *BEFORE_COPY,
        "pv-migrate",
        f"pv-migrate cleanup {operation}",
        *UNDO_AFTER_COPY,
    ]
    assert raised.value.undone[0] == MESSAGES.k8s.volume_move_undo_cleanup.format(
        operation=operation
    )


def test_the_cleanup_of_pv_migrate_names_the_operation_and_the_namespace(
    cluster: Cluster, process_fake: ProcessFake, tmp_path: Path
) -> None:
    cluster.interrupt_copy = True

    with pytest.raises(VolumeMoveError) as raised:
        _move(tmp_path)

    assert raised.value.error_code == "K8S_VOLUME_MOVE_FAILED"
    [(copy, _values)] = cluster.copies
    operation = copy[copy.index("--id") + 1]
    cleanup = next(
        call.argv for call in process_fake.calls if call.argv[:2] == ("pv-migrate", "cleanup")
    )
    assert list(cleanup) == [
        "pv-migrate",
        "cleanup",
        operation,
        "--namespace",
        NAMESPACE,
        "--force",
        "--context",
        CONTEXT,
    ]


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


def test_an_undo_deletes_the_volume_that_a_class_binds_before_the_copy(
    cluster: Cluster, tmp_path: Path
) -> None:
    """A class such as `longhorn` binds the temporary claim at once and keeps its volume after a
    delete (reclaim policy Retain), so the undo sets that volume to Delete first (#7416)."""
    cluster.move_claim_volume = NEW_VOLUME
    cluster.failing = frozenset({"scale deployment/grafana --replicas=0"})

    with pytest.raises(VolumeMoveError) as failed:
        _move(tmp_path)

    assert failed.value.error_code == "K8S_VOLUME_MOVE_FAILED"
    scaled = cluster.changes.index("scale deployment/grafana --replicas=0")
    assert cluster.changes[scaled + 1 :] == UNDO_AFTER_COPY


def test_an_undo_step_that_fails_is_reported_and_the_others_still_run(
    cluster: Cluster, tmp_path: Path
) -> None:
    cluster.copy_fails = True
    cluster.failing = frozenset({"scale deployment/grafana --replicas=1"})

    with pytest.raises(VolumeMoveError) as failed:
        _move(tmp_path)

    assert cluster.changes == [*BEFORE_COPY, "pv-migrate", *UNDO_AFTER_COPY]
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
    assert error.remaining == describe_volume_move(PLAN)[8:]
    assert json.loads(error.saved_claim.read_text(encoding="utf-8")) == _claim_object()


def test_a_pod_off_the_target_node_after_the_move_leaves_argo_cd_paused(
    cluster: Cluster, tmp_path: Path
) -> None:
    cluster.restarted_on = WORKER_A

    with pytest.raises(VolumeMoveStrandedError) as stranded:
        _move(tmp_path)

    assert stranded.value.remaining == describe_volume_move(PLAN)[9:]
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
        first("get", "pvc", "--ignore-not-found", "-o", "json"),
        first("get", "namespace", NAMESPACE),
        first("patch", "application", '"enabled": false'),
        first("scale", "--replicas=0"),
        first("pv-migrate", "clusterip"),
        first("get", "pvc", f"{CLAIM}-move", "jsonpath"),
        first("patch", "pv", "<new-volume>", "Retain"),
        first("delete", "pvc", f"{CLAIM}-move") - 1,
        first("patch", "pv", "claimRef"),
        first("annotate", "pvc", "last-applied-configuration"),
        first("patch", "application", '"enabled": true'),
    ]
    assert order == sorted(order)
    assert argvs[order[7]][3:6] == ("delete", "pvc", CLAIM)
    assert {argv[:3] for argv in argvs if argv[0] != "pv-migrate"} == {
        ("kubectl", "--context", CONTEXT)
    }


def test_the_dry_run_shows_the_copy_as_root_and_with_non_root(process_fake: ProcessFake) -> None:
    requests = dry_run_volume_move(NAMESPACE, CLAIM, parents=PARENTS, context=CONTEXT)

    copies = [request for request in requests if request.argv[0] == "pv-migrate"]
    assert [("--non-root" in request.argv, bool(request.condition)) for request in copies] == [
        (False, True),
        (True, True),
    ]
    assert json.loads(copies[0].stdin or "{}")["rsync"] == {
        "nodeSelector": {"kubernetes.io/hostname": "<target-hostname>"}
    }
    # A move that keeps the class reads that class only for a copy with --non-root.
    assert [r.condition for r in requests if r.argv[3:5] == ("get", "storageclass")] == [
        "the namespace enforces Pod Security restricted"
    ]
    assert not any(
        json.loads(request.stdin)["kind"] in ("Pod", "NetworkPolicy")
        for request in requests
        if request.argv[0] == "kubectl" and request.stdin
    )
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
        if request.argv[0] == "kubectl"
        and request.stdin
        and '"PersistentVolumeClaim"' in request.stdin
    ]
    assert [claim["spec"]["storageClassName"] for claim in claims] == [LONGHORN, LONGHORN]


# ── The command ────────────────────────────────────────────────────────────


def test_move_plan_prints_the_steps_and_changes_nothing(cli: Any, cluster: Cluster) -> None:
    result = cli("k8s", "volume", "move", "monitoring/grafana", "--plan", "--context", CONTEXT)

    assert result.exit_code == 0, result.output
    assert MESSAGES.k8s.volume_move_plan_heading.format(namespace=NAMESPACE, claim=CLAIM) in (
        result.output
    )
    assert (
        "7. " + MESSAGES.k8s.volume_move_step_delete_claim.format(namespace=NAMESPACE, claim=CLAIM)
        in result.output
    )
    assert " ".join(MESSAGES.k8s.volume_move_plan_copy_root.split()) in " ".join(
        result.output.split()
    )
    assert cluster.changes == []


def test_move_plan_in_a_restricted_namespace_says_that_the_copy_keeps_no_owner(
    cli: Any, cluster: Cluster
) -> None:
    cluster.pod_security = "restricted"

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
    line = MESSAGES.k8s.volume_move_plan_copy_non_root.format(namespace=NAMESPACE)
    assert " ".join(line.split()) in " ".join(result.output.split())
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
    cluster.copy_fails = True

    result = cli("k8s", "volume", "move", "monitoring/grafana", "--context", CONTEXT)

    assert result.exit_code == 1
    assert (
        MESSAGES.k8s.volume_move_undone_steps.format(
            steps="; ".join(
                [
                    MESSAGES.k8s.volume_move_undo_scale.format(
                        workload="deployment/grafana", replicas=1
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


def _applicationset_owner(name: str = "service-workloads") -> list[dict[str, Any]]:
    return [
        {
            "apiVersion": "argoproj.io/v1alpha1",
            "kind": "ApplicationSet",
            "name": name,
            "controller": True,
        }
    ]


def test_applicationset_owned_application_without_pause_ignore_is_refused(
    cluster: Cluster,
) -> None:
    cluster.application_owners["grafana"] = _applicationset_owner()
    cluster.application_sets["service-workloads"] = [
        {"jsonPointers": ["/spec/source/kustomize/images"]}
    ]

    with pytest.raises(VolumeMoveRefusedError) as refused:
        _plan()

    assert (refused.value.error_code, refused.value.exit_code) == ("K8S_VOLUME_MOVE_REFUSED", 1)
    assert len(refused.value.problems) == 1
    problem = refused.value.problems[0]
    assert "service-workloads" in problem
    assert "grafana" in problem
    assert "/spec/syncPolicy" in problem
    assert "ignoreApplicationDifferences" in problem
    assert cluster.changes == []


@pytest.mark.parametrize(
    "entry",
    [
        {"jsonPointers": ["/spec"]},
        {"jsonPointers": ["/spec/syncPolicy"]},
        {"jsonPointers": ["/spec/syncPolicy/automated"]},
        {"jsonPointers": ["/spec/syncPolicy/automated/enabled"]},
        {"name": "grafana", "jsonPointers": ["/spec/syncPolicy"]},
    ],
)
def test_applicationset_owned_application_with_covering_ignore_is_allowed(
    cluster: Cluster, entry: dict[str, Any]
) -> None:
    cluster.application_owners["grafana"] = _applicationset_owner()
    cluster.application_sets["service-workloads"] = [entry]

    plan = _plan()

    assert plan == PLAN


@pytest.mark.parametrize(
    "entries",
    [
        [{"jsonPointers": ["/spec/syncPolicy2"]}],
        [{"jsonPointers": ["/spec/syncPolicy/automated/selfHeal"]}],
        [{"name": "loki", "jsonPointers": ["/spec/syncPolicy"]}],
        [],
    ],
)
def test_applicationset_owned_application_with_non_covering_ignore_is_refused(
    cluster: Cluster, entries: list[dict[str, Any]]
) -> None:
    cluster.application_owners["grafana"] = _applicationset_owner()
    cluster.application_sets["service-workloads"] = entries

    with pytest.raises(VolumeMoveRefusedError) as refused:
        _plan()

    assert "service-workloads" in refused.value.problems[0]
    assert "/spec/syncPolicy" in refused.value.problems[0]
    assert cluster.changes == []


def test_applicationset_is_not_read_when_no_application_has_an_applicationset_owner(
    cluster: Cluster, process_fake: ProcessFake
) -> None:
    plan = _plan()

    assert plan == PLAN
    assert not any("applicationset" in call.argv for call in process_fake.calls)


def test_dry_run_lists_the_conditional_applicationset_read(process_fake: ProcessFake) -> None:
    requests = dry_run_volume_move(NAMESPACE, CLAIM, parents=PARENTS, context=CONTEXT)

    assert process_fake.calls == []
    reads = [r for r in requests if r.argv[3:5] == ("get", "applicationset")]
    assert len(reads) == 1
    assert reads[0].condition
    argvs = [r.argv for r in requests]
    apps_index = next(i for i, a in enumerate(argvs) if a[3:5] == ("get", "applications"))
    appset_index = next(i for i, a in enumerate(argvs) if a[3:5] == ("get", "applicationset"))
    assert apps_index < appset_index
