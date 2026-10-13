"""Kubernetes PersistentVolume orphan detection and safe volume reclamation engine."""

from __future__ import annotations

from typing import Any

from devops_cli.config.constants import (
    CONST_K8S_ORPHAN_VOLUME_PHASES,
    CONST_K8S_PV_API_PATH_TEMPLATE,
)
from devops_cli.dry_run.requests import PlannedRequest
from devops_cli.exceptions.k8s import VolumeReclaimError


def _get_obj_attr(obj: Any, key: str, default: Any = None) -> Any:
    """Retrieve attribute from Kubernetes object or dictionary key."""
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def plan_volume_reclaim_requests(name: str, patch: bool = False) -> list[PlannedRequest]:
    """Build the planned external Kubernetes API request for dry-run simulation."""
    verb = "PATCH" if patch else "DELETE"
    target = CONST_K8S_PV_API_PATH_TEMPLATE.format(name=name)
    return [PlannedRequest(method=verb, target=target)]


def check_volume_orphan_phase(pv: Any) -> tuple[bool, str | None]:
    """Verify that the volume phase is in Released or Failed."""
    status = _get_obj_attr(pv, "status")
    phase = _get_obj_attr(status, "phase") if status else None
    if not phase:
        return (False, "volume has no status or phase")
    if phase not in CONST_K8S_ORPHAN_VOLUME_PHASES:
        return (False, f"volume phase is '{phase}' (must be Released or Failed)")
    return (True, None)


def check_volume_claim_absent(core: Any, pv: Any) -> tuple[bool, str | None]:
    """Verify that any referenced PersistentVolumeClaim is absent or deleted."""
    spec = _get_obj_attr(pv, "spec")
    claim_ref = _get_obj_attr(spec, "claim_ref") or _get_obj_attr(spec, "claimRef")
    if not claim_ref:
        return (True, None)
    claim_name = _get_obj_attr(claim_ref, "name")
    if not claim_name:
        return (True, None)
    claim_ns = _get_obj_attr(claim_ref, "namespace") or "default"
    try:
        core.read_namespaced_persistent_volume_claim(name=claim_name, namespace=claim_ns)
        return (False, f"PersistentVolumeClaim '{claim_ns}/{claim_name}' still exists")
    except Exception as exc:
        status_code = getattr(exc, "status", None)
        if status_code == 404 or "not found" in str(exc).lower():
            return (True, None)
        raise VolumeReclaimError(
            f"Failed to verify PersistentVolumeClaim '{claim_ns}/{claim_name}': {exc}",
            reason=str(exc),
        ) from exc


def _pod_mounts_volume_or_claim(
    pod: Any, pv_name: str, claim_name: str | None
) -> tuple[bool, str | None]:
    """Determine if a single pod mounts the given PersistentVolume or referenced PVC."""
    pod_spec = _get_obj_attr(pod, "spec")
    volumes = _get_obj_attr(pod_spec, "volumes") or []
    pod_meta = _get_obj_attr(pod, "metadata")
    pod_name = _get_obj_attr(pod_meta, "name") or "unknown"
    pod_ns = _get_obj_attr(pod_meta, "namespace") or "default"

    for vol in volumes:
        pvc = _get_obj_attr(vol, "persistent_volume_claim") or _get_obj_attr(
            vol, "persistentVolumeClaim"
        )
        if pvc:
            pvc_name = _get_obj_attr(pvc, "claim_name") or _get_obj_attr(pvc, "claimName")
            if claim_name and pvc_name == claim_name:
                return (True, f"Pod '{pod_ns}/{pod_name}' mounts volume via PVC '{claim_name}'")
        vol_name = _get_obj_attr(vol, "name")
        if vol_name == pv_name:
            return (True, f"Pod '{pod_ns}/{pod_name}' mounts volume '{pv_name}'")
    return (False, None)


def check_volume_not_mounted(
    core: Any, pv_name: str, claim_name: str | None = None
) -> tuple[bool, str | None]:
    """Verify that no pod in any namespace mounts the volume or its claim."""
    pod_list = core.list_pod_for_all_namespaces()
    pods = getattr(pod_list, "items", pod_list) if not isinstance(pod_list, list) else pod_list
    for p in pods:
        mounted, reason = _pod_mounts_volume_or_claim(p, pv_name, claim_name)
        if mounted:
            return (False, reason)
    return (True, None)


def verify_volume_orphaned(core: Any, pv: Any) -> tuple[bool, str | None]:
    """Verify that the PersistentVolume satisfies all conditions to be considered orphaned."""
    pv_meta = _get_obj_attr(pv, "metadata")
    pv_name = _get_obj_attr(pv_meta, "name") or "unknown"

    phase_ok, phase_err = check_volume_orphan_phase(pv)
    if not phase_ok:
        return (False, phase_err)

    claim_ok, claim_err = check_volume_claim_absent(core, pv)
    if not claim_ok:
        return (False, claim_err)

    spec = _get_obj_attr(pv, "spec")
    claim_ref = _get_obj_attr(spec, "claim_ref") or _get_obj_attr(spec, "claimRef")
    claim_name = _get_obj_attr(claim_ref, "name") if claim_ref else None

    mount_ok, mount_err = check_volume_not_mounted(core, pv_name, claim_name)
    if not mount_ok:
        return (False, mount_err)

    return (True, None)


def reclaim_volume(core: Any, name: str, patch: bool = False) -> str:
    """Execute the volume reclamation mutation (DELETE or PATCH finalizers)."""
    if patch:
        core.patch_persistent_volume(name=name, body={"metadata": {"finalizers": []}})
        return "patched"
    core.delete_persistent_volume(name=name)
    return "deleted"


def get_k8s_client(context: str | None = None) -> Any:
    """Retrieve an initialized Kubernetes CoreV1Api client."""
    from devops_cli.k8s.doctor import get_k8s_client as _get_client

    return _get_client(context)


__all__ = [
    "check_volume_claim_absent",
    "check_volume_not_mounted",
    "check_volume_orphan_phase",
    "get_k8s_client",
    "plan_volume_reclaim_requests",
    "reclaim_volume",
    "verify_volume_orphaned",
]
