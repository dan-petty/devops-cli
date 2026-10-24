"""Tests for Kubernetes PersistentVolume safe orphan reclamation (devops k8s volume reclaim)."""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

from typer.testing import CliRunner

from devops_cli.commands.k8s import app
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
from tests.k8s_fakes import FakeCoreV1, client, pod

CONST_K8S_PV_PHASE_BOUND: str = "Bound"


class _FakeApiException(Exception):
    def __init__(self, status: int = 404, reason: str = "Not Found") -> None:
        super().__init__(f"({status}) Reason: {reason}")
        self.status = status
        self.reason = reason


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


class ExtendedFakeCoreV1(FakeCoreV1):
    """Extended FakeCoreV1 supporting PersistentVolume and PersistentVolumeClaim APIs."""

    def __init__(
        self,
        pvs: dict[str, Any] | None = None,
        pvcs: dict[tuple[str, str], Any] | None = None,
        pods: list[Any] | None = None,
    ) -> None:
        super().__init__(pods=pods)
        self.pvs = pvs or {}
        self.pvcs = pvcs or {}
        self.mutating_calls: list[tuple[str, dict[str, Any]]] = []

    def read_persistent_volume(self, name: str, **kwargs: Any) -> Any:
        self.calls.append(("read_persistent_volume", {"name": name, **kwargs}))
        if name not in self.pvs:
            raise _FakeApiException(status=404, reason=f"PersistentVolume '{name}' not found")
        return self.pvs[name]

    def read_namespaced_persistent_volume_claim(
        self, name: str, namespace: str, **kwargs: Any
    ) -> Any:
        self.calls.append(
            (
                "read_namespaced_persistent_volume_claim",
                {"name": name, "namespace": namespace, **kwargs},
            )
        )
        key = (namespace, name)
        if key not in self.pvcs:
            raise _FakeApiException(
                status=404, reason=f"PersistentVolumeClaim '{namespace}/{name}' not found"
            )
        return self.pvcs[key]

    def delete_persistent_volume(self, name: str, **kwargs: Any) -> Any:
        call_info = ("delete_persistent_volume", {"name": name, **kwargs})
        self.calls.append(call_info)
        self.mutating_calls.append(call_info)
        return self.pvs.pop(name, None)

    def patch_persistent_volume(self, name: str, body: Any, **kwargs: Any) -> Any:
        call_info = ("patch_persistent_volume", {"name": name, "body": body, **kwargs})
        self.calls.append(call_info)
        self.mutating_calls.append(call_info)
        return self.pvs.get(name)


def test_volume_reclaim_help() -> None:
    """Criterion 1: devops k8s volume reclaim --help prints command name, argument, and options."""
    runner = CliRunner()
    result = runner.invoke(app, ["volume", "reclaim", "--help"])
    assert (
        result.exit_code,
        "reclaim" in result.stdout,
        "NAME" in result.stdout or "name" in result.stdout,
        "--dry-run" in result.stdout,
        "--yes" in result.stdout,
    ) == (0, True, True, True, True)


def test_volume_reclaim_dry_run_delete() -> None:
    """Criterion 4: --dry-run prints DELETE request and makes zero API calls."""
    runner = CliRunner()
    fake_client = ExtendedFakeCoreV1()
    with patch("devops_cli.commands.k8s.volume.get_k8s_client", return_value=fake_client):
        result = runner.invoke(app, ["volume", "reclaim", "pv-reclaim-test", "--dry-run"])

    assert (
        result.exit_code,
        len(fake_client.calls),
        "pv-reclaim-test" in result.stdout,
        "DELETE" in result.stdout,
        "/api/v1/persistentvolumes/pv-reclaim-test" in result.stdout,
    ) == (0, 0, True, True, True)


def test_volume_reclaim_dry_run_patch() -> None:
    """Criterion 4: --dry-run with --patch prints PATCH request and makes zero API calls."""
    runner = CliRunner()
    fake_client = ExtendedFakeCoreV1()
    with patch("devops_cli.commands.k8s.volume.get_k8s_client", return_value=fake_client):
        result = runner.invoke(
            app, ["volume", "reclaim", "pv-reclaim-test", "--dry-run", "--patch"]
        )

    assert (
        result.exit_code,
        len(fake_client.calls),
        "pv-reclaim-test" in result.stdout,
        "PATCH" in result.stdout,
        "/api/v1/persistentvolumes/pv-reclaim-test" in result.stdout,
    ) == (0, 0, True, True, True)


def test_volume_reclaim_refuses_non_orphaned_phase() -> None:
    """Criterion 2: Refuses to reclaim volume in Bound phase and reports phase reason."""
    bound_pv = _fake_pv("pv-bound", phase=CONST_K8S_PV_PHASE_BOUND)
    fake_client = ExtendedFakeCoreV1(pvs={"pv-bound": bound_pv})
    runner = CliRunner()

    with patch("devops_cli.commands.k8s.volume.get_k8s_client", return_value=fake_client):
        result = runner.invoke(app, ["volume", "reclaim", "pv-bound", "--yes"])

    assert (
        result.exit_code != 0,
        "phase" in result.output.lower(),
        "bound" in result.output.lower(),
        len(fake_client.mutating_calls),
    ) == (True, True, True, 0)


def test_volume_reclaim_refuses_active_claim() -> None:
    """Criterion 2: Refuses to reclaim volume when referenced PVC still exists."""
    claimed_pv = _fake_pv(
        "pv-claimed",
        phase=CONST_K8S_PV_PHASE_RELEASED,
        claim_name="data-pvc",
        claim_namespace="default",
    )
    active_pvc = client.V1PersistentVolumeClaim(
        metadata=client.V1ObjectMeta(name="data-pvc", namespace="default")
    )
    fake_client = ExtendedFakeCoreV1(
        pvs={"pv-claimed": claimed_pv},
        pvcs={("default", "data-pvc"): active_pvc},
    )
    runner = CliRunner()

    with patch("devops_cli.commands.k8s.volume.get_k8s_client", return_value=fake_client):
        result = runner.invoke(app, ["volume", "reclaim", "pv-claimed", "--yes"])

    assert (
        result.exit_code != 0,
        "claim" in result.output.lower(),
        len(fake_client.mutating_calls),
    ) == (True, True, 0)


def test_volume_reclaim_refuses_mounted_volume() -> None:
    """Criterion 2: Refuses to reclaim volume when mounted by an active pod."""
    mounted_pv = _fake_pv(
        "pv-mounted",
        phase=CONST_K8S_PV_PHASE_RELEASED,
        claim_name="orphan-pvc",
        claim_namespace="prod",
    )
    pod_with_mount = pod(
        name="worker-pod",
        namespace="prod",
    )
    pod_with_mount.spec.volumes = [
        client.V1Volume(
            name="vol-data",
            persistent_volume_claim=client.V1PersistentVolumeClaimVolumeSource(
                claim_name="orphan-pvc"
            ),
        )
    ]
    fake_client = ExtendedFakeCoreV1(
        pvs={"pv-mounted": mounted_pv},
        pods=[pod_with_mount],
    )
    runner = CliRunner()

    with patch("devops_cli.commands.k8s.volume.get_k8s_client", return_value=fake_client):
        result = runner.invoke(app, ["volume", "reclaim", "pv-mounted", "--yes"])

    assert (
        result.exit_code != 0,
        "mount" in result.output.lower(),
        len(fake_client.mutating_calls),
    ) == (True, True, 0)


def test_volume_reclaim_refuses_non_interactive_without_yes() -> None:
    """Criterion 3: Refuses to proceed in non-interactive session without --yes."""
    orphan_pv = _fake_pv("pv-orphaned", phase=CONST_K8S_PV_PHASE_RELEASED)
    fake_client = ExtendedFakeCoreV1(pvs={"pv-orphaned": orphan_pv})
    runner = CliRunner()

    with (
        patch("devops_cli.commands.k8s.volume.get_k8s_client", return_value=fake_client),
        patch("devops_cli.commands.k8s.volume._is_interactive", return_value=False),
    ):
        result = runner.invoke(app, ["volume", "reclaim", "pv-orphaned"])

    assert (
        result.exit_code != 0,
        len(fake_client.mutating_calls),
    ) == (True, 0)


def test_volume_reclaim_confirmation_aborted() -> None:
    """Criterion 3: Confirmation prompt declines action when user responds 'n'."""
    orphan_pv = _fake_pv("pv-orphaned", phase=CONST_K8S_PV_PHASE_RELEASED)
    fake_client = ExtendedFakeCoreV1(pvs={"pv-orphaned": orphan_pv})
    runner = CliRunner()

    with (
        patch("devops_cli.commands.k8s.volume.get_k8s_client", return_value=fake_client),
        patch("devops_cli.commands.k8s.volume._is_interactive", return_value=True),
    ):
        result = runner.invoke(app, ["volume", "reclaim", "pv-orphaned"], input="n\n")

    assert (
        result.exit_code,
        len(fake_client.mutating_calls),
        "aborted" in result.output.lower(),
    ) == (0, 0, True)


def test_volume_reclaim_success_delete() -> None:
    """Criterion 5: Successfully deletes orphaned volume and reports volume name and 'deleted'."""
    orphan_pv = _fake_pv("pv-orphaned", phase=CONST_K8S_PV_PHASE_RELEASED)
    fake_client = ExtendedFakeCoreV1(pvs={"pv-orphaned": orphan_pv})
    runner = CliRunner()

    with patch("devops_cli.commands.k8s.volume.get_k8s_client", return_value=fake_client):
        result = runner.invoke(app, ["volume", "reclaim", "pv-orphaned", "--yes"])

    assert (
        result.exit_code,
        len(fake_client.mutating_calls),
        fake_client.mutating_calls[0][0],
        "pv-orphaned" in result.output,
        "deleted" in result.output.lower(),
    ) == (0, 1, "delete_persistent_volume", True, True)


def test_volume_reclaim_success_patch() -> None:
    """Criterion 5: Successfully patches orphaned volume and reports volume name and 'patched'."""
    orphan_pv = _fake_pv(
        "pv-orphaned", phase=CONST_K8S_PV_PHASE_FAILED, finalizers=["kubernetes.io/pv-protection"]
    )
    fake_client = ExtendedFakeCoreV1(pvs={"pv-orphaned": orphan_pv})
    runner = CliRunner()

    with patch("devops_cli.commands.k8s.volume.get_k8s_client", return_value=fake_client):
        result = runner.invoke(app, ["volume", "reclaim", "pv-orphaned", "--yes", "--patch"])

    assert (
        result.exit_code,
        len(fake_client.mutating_calls),
        fake_client.mutating_calls[0][0],
        "pv-orphaned" in result.output,
        "patched" in result.output.lower(),
    ) == (0, 1, "patch_persistent_volume", True, True)


def test_volume_reclaim_not_found() -> None:
    """Refuses reclaim when PersistentVolume does not exist."""
    fake_client = ExtendedFakeCoreV1()
    runner = CliRunner()

    with patch("devops_cli.commands.k8s.volume.get_k8s_client", return_value=fake_client):
        result = runner.invoke(app, ["volume", "reclaim", "pv-missing", "--yes"])

    assert (
        result.exit_code != 0,
        "not found" in result.output.lower(),
        len(fake_client.mutating_calls),
    ) == (True, True, 0)


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
    fake_client = ExtendedFakeCoreV1(
        pvcs={("default", "extant-claim"): client.V1PersistentVolumeClaim()}
    )
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
    fake_client_mounted = ExtendedFakeCoreV1(pods=[p])
    fake_client_unmounted = ExtendedFakeCoreV1(pods=[pod("unrelated", "default")])

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
    fake_reclaim_client = ExtendedFakeCoreV1(pvs={"pv-unit": orphaned_pv})
    action_patch = reclaim_volume(fake_reclaim_client, "pv-unit", patch=True)
    action_delete = reclaim_volume(fake_reclaim_client, "pv-unit", patch=False)
    assert (
        plan_del[0].method,
        plan_patch[0].method,
        action_patch,
        action_delete,
    ) == ("DELETE", "PATCH", "patched", "deleted")
