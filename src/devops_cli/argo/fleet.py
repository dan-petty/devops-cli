"""Multi-cluster ArgoCD fleet synchronization engine."""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import TYPE_CHECKING

from devops_cli.config import load_settings
from devops_cli.config.defaults import DEFAULT_HTTP_TIMEOUT_SECONDS
from devops_cli.http.validation import validate_service_url
from devops_cli.models.argo import ArgoFleetAppTarget, ArgoFleetSyncResult

if TYPE_CHECKING:
    from devops_cli.output.models import TablePayload


def _execute_cluster_sync(
    app_name: str,
    cluster: str,
    prune: bool = False,
    force: bool = False,
) -> None:
    """Execute live ArgoCD REST API sync against target cluster."""
    import httpx2

    settings = load_settings()
    from devops_cli.config.settings import get_argocd_token

    if not settings.argocd.url:
        raise RuntimeError("ArgoCD URL is not configured in settings")

    validate_service_url(settings.argocd.url, "ArgoCD", allow=settings.ai.allow_private_network)
    headers: dict[str, str] = {"Content-Type": "application/json"}
    token = get_argocd_token(settings)
    if token:
        headers["Authorization"] = f"Bearer {token}"

    base = settings.argocd.url.rstrip("/")
    url = f"{base}/api/v1/applications/{app_name}/sync"
    payload = {"sync": {"prune": prune, "force": force}}

    with httpx2.Client() as client:
        resp = client.post(
            url,
            headers=headers,
            json=payload,
            params={"appNamespace": "argocd", "project": cluster},
            timeout=DEFAULT_HTTP_TIMEOUT_SECONDS,
        )
        resp.raise_for_status()


def sync_single_target(
    app_name: str,
    cluster: str,
    prune: bool = False,
    force: bool = False,
    dry_run: bool = False,
) -> ArgoFleetAppTarget:
    """Synchronize an application on a single cluster target with timing and error isolation."""
    start_time = time.monotonic()
    if dry_run:
        return ArgoFleetAppTarget(
            app_name=app_name,
            cluster=cluster,
            status="Synced",
            message="Dry run simulation succeeded",
            duration_seconds=round(time.monotonic() - start_time, 2),
        )

    try:
        _execute_cluster_sync(app_name, cluster, prune=prune, force=force)
        return ArgoFleetAppTarget(
            app_name=app_name,
            cluster=cluster,
            status="Synced",
            message="Application synced successfully",
            duration_seconds=round(time.monotonic() - start_time, 2),
        )
    except Exception as exc:
        return ArgoFleetAppTarget(
            app_name=app_name,
            cluster=cluster,
            status="Failed",
            message=str(exc),
            duration_seconds=round(time.monotonic() - start_time, 2),
        )


def sync_fleet(
    app_name: str,
    clusters: list[str] | None = None,
    fleet_name: str = "default-fleet",
    prune: bool = False,
    force: bool = False,
    max_concurrency: int = 3,
    dry_run: bool = False,
) -> ArgoFleetSyncResult:
    """Coordinate bounded concurrent multi-cluster application synchronization."""
    target_clusters = clusters or ["dev", "staging", "prod"]
    targets: list[ArgoFleetAppTarget] = []

    bounded_concurrency = max(1, min(max_concurrency, 10))

    with ThreadPoolExecutor(max_workers=bounded_concurrency) as executor:
        futures = {
            executor.submit(
                sync_single_target,
                app_name,
                cluster,
                prune,
                force,
                dry_run,
            ): cluster
            for cluster in target_clusters
        }
        for future in as_completed(futures):
            targets.append(future.result())

    targets.sort(key=lambda t: t.cluster)
    total_synced = sum(1 for t in targets if t.status == "Synced")
    total_failed = sum(1 for t in targets if t.status != "Synced")

    return ArgoFleetSyncResult(
        fleet_name=fleet_name,
        targets=targets,
        total_synced=total_synced,
        total_failed=total_failed,
        success=(total_failed == 0),
    )


def render_fleet_sync_table(result: ArgoFleetSyncResult) -> TablePayload:
    """Render structured TablePayload displaying fleet synchronization outcome."""
    from devops_cli.output import format_argo_fleet_sync_table

    return format_argo_fleet_sync_table(result)
