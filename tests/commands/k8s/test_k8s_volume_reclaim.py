"""Tests for Kubernetes PersistentVolume safe orphan reclamation (devops k8s volume reclaim)."""

from __future__ import annotations

from typing import Any

from devops_cli.config.constants import (
    CONST_K8S_PV_PHASE_FAILED,
    CONST_K8S_PV_PHASE_RELEASED,
)
from devops_cli.k8s.volume import (
    check_volume_claim_absent,
    check_volume_not_mounted,
    check_volume_orphan_phase,
    plan_volume_reclaim_requests,
    reclaim_volume,
    verify_volume_orphaned,
)
from devops_cli.lang import ERRORS
from tests.support.fakes.kubernetes import FakeCluster, FakeCoreV1, client, pod

CONST_K8S_PV_PHASE_BOUND: str = "Bound"


def _fake_pv(
    name: str = "pv-test",
    phase: str = CONST_K8S_PV_PHASE_RELEASED,
    claim_name: str | None = None,
    claim_namespace: str | None = None,
    deletion_timestamp: Any = None,
    finalizers: list[str] | None = None,
) -> Any:
    """Create a mock V1PersistentVolume object for testing."""
    claim_ref = None
    if claim_name:
        claim_ref = client.V1ObjectReference(
            name=claim_name, namespace=claim_namespace or "default"
        )
    return client.V1PersistentVolume(
        metadata=client.V1ObjectMeta(
            name=name,
            deletion_timestamp=deletion_timestamp,
            finalizers=finalizers or [],
        ),
        spec=client.V1PersistentVolumeSpec(
            access_modes=["ReadWriteOnce"],
            capacity={"storage": "10Gi"},
            claim_ref=claim_ref,
        ),
        status=client.V1PersistentVolumeStatus(phase=phase),
    )


def _mutations(core: FakeCoreV1) -> list[str]:
    """The names of the calls that changed a PersistentVolume, in call order."""
    return [
        method
        for method, _ in core.calls
        if method in {"delete_persistent_volume", "patch_persistent_volume"}
    ]


def test_volume_reclaim_help(cli: Any) -> None:
    """Criterion 1: devops k8s volume reclaim --help prints command name, argument, and options."""
    result = cli(["k8s", "volume", "reclaim", "--help"])
    assert (
        result.exit_code,
        "reclaim" in result.stdout,
        "NAME" in result.stdout or "name" in result.stdout,
        "--dry-run" in result.stdout,
        "--yes" in result.stdout,
    ) == (0, True, True, True, True)


def test_volume_reclaim_dry_run_delete(cli: Any, cluster: FakeCluster) -> None:
    """Criterion 4: --dry-run prints DELETE request and makes zero API calls."""
    result = cli(["k8s", "volume", "reclaim", "pv-reclaim-test", "--dry-run"])

    assert (
        result.exit_code,
        len(cluster.core.calls),
        "pv-reclaim-test" in result.stdout,
        "DELETE" in result.stdout,
        "/api/v1/persistentvolumes/pv-reclaim-test" in result.stdout,
    ) == (0, 0, True, True, True)


def test_volume_reclaim_dry_run_patch(cli: Any, cluster: FakeCluster) -> None:
    """Criterion 4: --dry-run with --patch prints PATCH request and makes zero API calls."""
    result = cli(["k8s", "volume", "reclaim", "pv-reclaim-test", "--dry-run", "--patch"])

    assert (
        result.exit_code,
        len(cluster.core.calls),
        "pv-reclaim-test" in result.stdout,
        "PATCH" in result.stdout,
        "/api/v1/persistentvolumes/pv-reclaim-test" in result.stdout,
    ) == (0, 0, True, True, True)


def test_volume_reclaim_refuses_non_orphaned_phase(cli: Any, cluster: FakeCluster) -> None:
    """Criterion 2: Refuses to reclaim volume in Bound phase and reports phase reason."""
    cluster.core.pvs["pv-bound"] = _fake_pv("pv-bound", phase=CONST_K8S_PV_PHASE_BOUND)

    result = cli(["k8s", "volume", "reclaim", "pv-bound", "--yes"])

    assert (
        result.exit_code != 0,
        "phase" in result.output.lower(),
        "bound" in result.output.lower(),
        _mutations(cluster.core),
    ) == (True, True, True, [])


def test_volume_reclaim_refuses_active_claim(cli: Any, cluster: FakeCluster) -> None:
    """Criterion 2: Refuses to reclaim volume when referenced PVC still exists."""
    cluster.core.pvs["pv-claimed"] = _fake_pv(
        "pv-claimed",
        phase=CONST_K8S_PV_PHASE_RELEASED,
        claim_name="data-pvc",
        claim_namespace="default",
    )
    cluster.core.pvcs[("default", "data-pvc")] = client.V1PersistentVolumeClaim(
        metadata=client.V1ObjectMeta(name="data-pvc", namespace="default")
    )

    result = cli(["k8s", "volume", "reclaim", "pv-claimed", "--yes"])

    assert (
        result.exit_code != 0,
        "claim" in result.output.lower(),
        _mutations(cluster.core),
    ) == (True, True, [])


def test_volume_reclaim_refuses_mounted_volume(cli: Any, cluster: FakeCluster) -> None:
    """Criterion 2: Refuses to reclaim volume when mounted by an active pod."""
    cluster.core.pvs["pv-mounted"] = _fake_pv(
        "pv-mounted",
        phase=CONST_K8S_PV_PHASE_RELEASED,
        claim_name="orphan-pvc",
        claim_namespace="prod",
    )
    pod_with_mount = pod(name="worker-pod", namespace="prod")
    pod_with_mount.spec.volumes = [
        client.V1Volume(
            name="vol-data",
            persistent_volume_claim=client.V1PersistentVolumeClaimVolumeSource(
                claim_name="orphan-pvc"
            ),
        )
    ]
    cluster.core.answers["list_pod_for_all_namespaces"] = [pod_with_mount]
    cluster.core.answers["list_namespaced_pod"] = [pod_with_mount]

    result = cli(["k8s", "volume", "reclaim", "pv-mounted", "--yes"])

    assert (
        result.exit_code != 0,
        "mount" in result.output.lower(),
        _mutations(cluster.core),
    ) == (True, True, [])


def test_volume_reclaim_refuses_non_interactive_without_yes(cli: Any, cluster: FakeCluster) -> None:
    """Criterion 3: Refuses to proceed in non-interactive session without --yes.

    The standard input of a test run is no terminal, so the command takes the non-interactive path.
    """
    cluster.core.pvs["pv-orphaned"] = _fake_pv("pv-orphaned", phase=CONST_K8S_PV_PHASE_RELEASED)

    result = cli(["k8s", "volume", "reclaim", "pv-orphaned"])

    assert (
        result.exit_code != 0,
        ERRORS.k8s.volume_reclaim_non_interactive in result.output,
        _mutations(cluster.core),
    ) == (True, True, [])


def test_volume_reclaim_success_delete(cli: Any, cluster: FakeCluster) -> None:
    """Criterion 5: Successfully deletes orphaned volume and reports volume name and 'deleted'."""
    cluster.core.pvs["pv-orphaned"] = _fake_pv("pv-orphaned", phase=CONST_K8S_PV_PHASE_RELEASED)

    result = cli(["k8s", "volume", "reclaim", "pv-orphaned", "--yes"])

    assert (
        result.exit_code,
        _mutations(cluster.core),
        "pv-orphaned" in result.output,
        "deleted" in result.output.lower(),
    ) == (0, ["delete_persistent_volume"], True, True)


def test_volume_reclaim_success_patch(cli: Any, cluster: FakeCluster) -> None:
    """Criterion 5: Successfully patches orphaned volume and reports volume name and 'patched'."""
    cluster.core.pvs["pv-orphaned"] = _fake_pv(
        "pv-orphaned", phase=CONST_K8S_PV_PHASE_FAILED, finalizers=["kubernetes.io/pv-protection"]
    )

    result = cli(["k8s", "volume", "reclaim", "pv-orphaned", "--yes", "--patch"])

    assert (
        result.exit_code,
        _mutations(cluster.core),
        "pv-orphaned" in result.output,
        "patched" in result.output.lower(),
    ) == (0, ["patch_persistent_volume"], True, True)


def test_volume_reclaim_not_found(cli: Any, cluster: FakeCluster) -> None:
    """Refuses reclaim when PersistentVolume does not exist."""
    result = cli(["k8s", "volume", "reclaim", "pv-missing", "--yes"])

    assert (
        result.exit_code != 0,
        "not found" in result.output.lower(),
        _mutations(cluster.core),
    ) == (True, True, [])


def test_orphan_detection_unit_logic() -> None:
    """Criterion 6: Unit validation of phase, claim, and mount detection predicates."""
    released_pv = _fake_pv("pv-1", phase=CONST_K8S_PV_PHASE_RELEASED)
    failed_pv = _fake_pv("pv-2", phase=CONST_K8S_PV_PHASE_FAILED)
    bound_pv = _fake_pv("pv-3", phase=CONST_K8S_PV_PHASE_BOUND)

    assert (
        check_volume_orphan_phase(released_pv)[0],
        check_volume_orphan_phase(failed_pv)[0],
        check_volume_orphan_phase(bound_pv)[0],
    ) == (True, True, False)

    # Claim absence check
    fake_client = FakeCoreV1(pvcs={("default", "extant-claim"): client.V1PersistentVolumeClaim()})
    pv_with_extant_claim = _fake_pv("pv-4", claim_name="extant-claim", claim_namespace="default")
    pv_with_absent_claim = _fake_pv("pv-5", claim_name="missing-claim", claim_namespace="default")
    pv_without_claim_ref = _fake_pv("pv-6")

    assert (
        check_volume_claim_absent(fake_client, pv_with_extant_claim)[0],
        check_volume_claim_absent(fake_client, pv_with_absent_claim)[0],
        check_volume_claim_absent(fake_client, pv_without_claim_ref)[0],
    ) == (False, True, True)

    # Mount absence check
    p = pod("mounter", "default")
    p.spec.volumes = [
        client.V1Volume(
            name="v1",
            persistent_volume_claim=client.V1PersistentVolumeClaimVolumeSource(
                claim_name="mounted-claim"
            ),
        )
    ]
    fake_client_mounted = FakeCoreV1(pods=[p])
    fake_client_unmounted = FakeCoreV1(pods=[pod("unrelated", "default")])

    assert (
        check_volume_not_mounted(fake_client_mounted, "pv-7", claim_name="mounted-claim")[0],
        check_volume_not_mounted(fake_client_unmounted, "pv-7", claim_name="mounted-claim")[0],
    ) == (False, True)

    # Combined verify_volume_orphaned
    orphaned_pv = _fake_pv("pv-clean", phase=CONST_K8S_PV_PHASE_RELEASED)
    assert verify_volume_orphaned(fake_client_unmounted, orphaned_pv) == (True, None)

    # Planned requests and reclaim execution unit checks
    plan_del = plan_volume_reclaim_requests("pv-unit", patch=False)
    plan_patch = plan_volume_reclaim_requests("pv-unit", patch=True)
    fake_reclaim_client = FakeCoreV1(pvs={"pv-unit": orphaned_pv})
    action_patch = reclaim_volume(fake_reclaim_client, "pv-unit", patch=True)
    action_delete = reclaim_volume(fake_reclaim_client, "pv-unit", patch=False)
    assert (
        plan_del[0].method,
        plan_patch[0].method,
        action_patch,
        action_delete,
    ) == ("DELETE", "PATCH", "patched", "deleted")
