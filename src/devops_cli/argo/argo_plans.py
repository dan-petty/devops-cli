"""Planned request builders for Argo CD, Rollout, and Workflow operations.

A dry run makes zero external requests and returns the ordered PlannedRequest items.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from devops_cli.argo.fleet import resolve_cluster_app_name
from devops_cli.argo.sync import build_sync_request_body
from devops_cli.config.defaults import (
    DEFAULT_ARGOCD_NAMESPACE,
    DEFAULT_K8S_NAMESPACE,
)
from devops_cli.dry_run.requests import PlannedRequest


def resolve_argocd_base_url(settings: Any | None = None) -> str:
    """Extract clean Argo CD base URL from settings or return placeholder."""
    if settings is None:
        from devops_cli.config.settings import load_settings

        settings = load_settings()
    url = getattr(getattr(settings, "argocd", None), "url", None)
    if not url:
        return "https://<argocd-url>"
    try:
        from devops_cli.http.urls import service_base_url

        return str(service_base_url(url, "argocd.url"))
    except ValueError:
        return str(url).rstrip("/")


def resolve_prometheus_base_url(settings: Any | None = None) -> str:
    """Extract clean Prometheus base URL from settings or return placeholder."""
    if settings is None:
        from devops_cli.config.settings import load_settings

        settings = load_settings()
    url = getattr(getattr(settings, "prometheus", None), "url", None)
    if not url:
        return "https://<prometheus-url>"
    return str(url).rstrip("/")


def plan_argocd_token(base_url: str | None = None) -> PlannedRequest:
    """Plan token session request for Argo CD authentication."""
    base = base_url or resolve_argocd_base_url()
    return PlannedRequest(
        method="POST",
        target=f"{base}/api/v1/session",
        stdin='{"username": "admin", "password": "<password>"}',
        condition="token missing or expired",
    )


def plan_argocd_apps_list(base_url: str | None = None) -> list[PlannedRequest]:
    """Plan listing Argo CD applications."""
    base = base_url or resolve_argocd_base_url()
    return [
        plan_argocd_token(base),
        PlannedRequest(
            method="GET",
            target=f"{base}/api/v1/applications",
        ),
    ]


def plan_argocd_apps_status(name: str, base_url: str | None = None) -> list[PlannedRequest]:
    """Plan showing status and image pins for an Argo CD application."""
    base = base_url or resolve_argocd_base_url()
    return [
        plan_argocd_token(base),
        PlannedRequest(
            method="GET",
            target=f"{base}/api/v1/applications/{name}",
        ),
    ]


def plan_argocd_apps_sync(
    name: str,
    prune: bool = False,
    force: bool = False,
    base_url: str | None = None,
) -> list[PlannedRequest]:
    """Plan synchronizing an Argo CD application."""
    base = base_url or resolve_argocd_base_url()
    payload = build_sync_request_body(prune=prune, force=force)
    return [
        plan_argocd_token(base),
        PlannedRequest(
            method="POST",
            target=f"{base}/api/v1/applications/{name}/sync",
            stdin=json.dumps(payload),
        ),
    ]


def plan_argocd_bootstrap_gitops(
    manifest_path: Path | str,
    context: str | None = None,
) -> list[PlannedRequest]:
    """Plan bootstrapping GitOps root application on Kubernetes cluster."""
    path = Path(manifest_path)
    from devops_cli.config.commands import build_kubectl_cmd

    argv = tuple(build_kubectl_cmd(["apply", "-f", str(path)], context=context))
    return [
        PlannedRequest(
            method="CustomObjectsApi.create_namespaced_custom_object",
            target=f"argoproj.io/v1alpha1/namespaces/{DEFAULT_ARGOCD_NAMESPACE}/applications/<root-app>",
            argv=argv,
        )
    ]


def plan_argo_fleet_sync(
    app_name: str,
    clusters: Sequence[str],
    prune: bool = False,
    force: bool = False,
    base_url: str | None = None,
) -> list[PlannedRequest]:
    """Plan synchronizing an application across multi-cluster fleet."""
    base = base_url or resolve_argocd_base_url()
    requests = [plan_argocd_token(base)]
    payload = build_sync_request_body(prune=prune, force=force, app_namespace="argocd")
    for cluster in clusters:
        target_app = resolve_cluster_app_name(app_name, cluster)
        requests.append(
            PlannedRequest(
                method="POST",
                target=f"{base}/api/v1/applications/{target_app}/sync?appNamespace=argocd",
                stdin=json.dumps(payload),
            )
        )
    return requests


def plan_argo_gitops_sync(
    app_name: str,
    mode: str = "api",
    prune: bool = False,
    force: bool = False,
    base_url: str | None = None,
) -> list[PlannedRequest]:
    """Plan triggering GitOps synchronization."""
    base = base_url or resolve_argocd_base_url()
    if mode == "webhook":
        payload = {
            "ref": "refs/heads/main",
            "repository": {
                "name": app_name,
                "html_url": f"https://example.com/{app_name}",
                "default_branch": "main",
            },
        }
        return [
            PlannedRequest(
                method="POST",
                target=f"{base}/api/webhook",
                stdin=json.dumps(payload),
            )
        ]

    payload = build_sync_request_body(prune=prune, force=force)
    return [
        plan_argocd_token(base),
        PlannedRequest(
            method="POST",
            target=f"{base}/api/v1/applications/{app_name}/sync",
            stdin=json.dumps(payload),
        ),
    ]


def plan_argo_gitops_watch(
    app_name: str,
    mode: str = "api",
    prune: bool = False,
    force: bool = False,
    base_url: str | None = None,
) -> list[PlannedRequest]:
    """Plan continuous or single-cycle GitOps drift watch and reconciliation."""
    sync_plan = plan_argo_gitops_sync(
        app_name=app_name,
        mode=mode,
        prune=prune,
        force=force,
        base_url=base_url,
    )
    # Mark the sync requests as conditional on manifest drift
    return [
        PlannedRequest(
            method=req.method,
            target=req.target,
            stdin=req.stdin,
            condition="manifest drift detected",
        )
        for req in sync_plan
    ]


def plan_argo_rollouts_abort(
    name: str,
    namespace: str = DEFAULT_K8S_NAMESPACE,
) -> list[PlannedRequest]:
    """Plan aborting an Argo Rollout."""
    return [
        PlannedRequest(
            method="CustomObjectsApi.patch_namespaced_custom_object",
            target=f"argoproj.io/v1alpha1/namespaces/{namespace}/rollouts/{name}",
            stdin=json.dumps({"spec": {"abort": True}}),
        )
    ]


def plan_argo_rollouts_promote(
    name: str,
    namespace: str = DEFAULT_K8S_NAMESPACE,
    full: bool = False,
) -> list[PlannedRequest]:
    """Plan promoting an Argo Rollout."""
    patch_body = {"status": {"promoteFull": True}} if full else {"spec": {"paused": False}}
    return [
        PlannedRequest(
            method="CustomObjectsApi.patch_namespaced_custom_object",
            target=f"argoproj.io/v1alpha1/namespaces/{namespace}/rollouts/{name}",
            stdin=json.dumps(patch_body),
        )
    ]


def plan_argo_rollouts_restart(
    name: str,
    namespace: str = DEFAULT_K8S_NAMESPACE,
) -> list[PlannedRequest]:
    """Plan restarting an Argo Rollout."""
    return [
        PlannedRequest(
            method="CustomObjectsApi.patch_namespaced_custom_object",
            target=f"argoproj.io/v1alpha1/namespaces/{namespace}/rollouts/{name}",
            stdin=json.dumps({"spec": {"restartAt": "<restart-timestamp>"}}),
        )
    ]


def plan_argo_rollouts_analyze(
    name: str,
    namespace: str = DEFAULT_K8S_NAMESPACE,
    error_rate_threshold: float = 1.0,
    auto_abort: bool = True,
    prom_url: str | None = None,
) -> list[PlannedRequest]:
    """Plan evaluating metric rollback gates for an Argo Rollout."""
    base_prom = prom_url or resolve_prometheus_base_url()
    query = (
        f'sum(rate(http_requests_total{{status=~"5..",app="{name}"}}[2m])) / '
        f'sum(rate(http_requests_total{{app="{name}"}}[2m])) * 100'
    )
    requests = [
        PlannedRequest(
            method="GET",
            target=f"{base_prom}/api/v1/query?query={query}",
        )
    ]
    if auto_abort:
        requests.append(
            PlannedRequest(
                method="CustomObjectsApi.patch_namespaced_custom_object",
                target=f"argoproj.io/v1alpha1/namespaces/{namespace}/rollouts/{name}",
                stdin=json.dumps({"spec": {"abort": True}}),
                condition="metric analysis violates threshold",
            )
        )
    return requests


def plan_argo_rollouts_list(
    namespace: str = DEFAULT_K8S_NAMESPACE,
) -> list[PlannedRequest]:
    """Plan listing Argo Rollouts."""
    return [
        PlannedRequest(
            method="CustomObjectsApi.list_namespaced_custom_object",
            target=f"argoproj.io/v1alpha1/namespaces/{namespace}/rollouts",
        )
    ]


def plan_argo_rollouts_status(
    name: str,
    namespace: str = DEFAULT_K8S_NAMESPACE,
) -> list[PlannedRequest]:
    """Plan getting status of an Argo Rollout."""
    return [
        PlannedRequest(
            method="CustomObjectsApi.get_namespaced_custom_object",
            target=f"argoproj.io/v1alpha1/namespaces/{namespace}/rollouts/{name}",
        )
    ]


def plan_argo_workflows_list(
    namespace: str = DEFAULT_K8S_NAMESPACE,
) -> list[PlannedRequest]:
    """Plan listing Argo Workflows."""
    return [
        PlannedRequest(
            method="CustomObjectsApi.list_namespaced_custom_object",
            target=f"argoproj.io/v1alpha1/namespaces/{namespace}/workflows",
        )
    ]


def plan_argo_workflows_submit(
    manifest_path: Path | str,
    namespace: str = DEFAULT_K8S_NAMESPACE,
) -> list[PlannedRequest]:
    """Plan submitting an Argo Workflow."""
    path = Path(manifest_path)
    return [
        PlannedRequest(
            method="CustomObjectsApi.create_namespaced_custom_object",
            target=f"argoproj.io/v1alpha1/namespaces/{namespace}/workflows/<workflow>",
            stdin=f"<manifest from {path}>",
        )
    ]


def plan_argo_workflows_logs(
    name: str,
    namespace: str = DEFAULT_K8S_NAMESPACE,
    container: str = "main",
) -> list[PlannedRequest]:
    """Plan reading logs for an Argo Workflow."""
    return [
        PlannedRequest(
            method="CustomObjectsApi.get_namespaced_custom_object",
            target=f"argoproj.io/v1alpha1/namespaces/{namespace}/workflows/{name}",
        ),
        PlannedRequest(
            method="CoreV1Api.read_namespaced_pod_log",
            target=f"namespaces/{namespace}/pods/<workflow-pod>/log?container={container}",
            condition="pod discovered from workflow",
        ),
    ]
