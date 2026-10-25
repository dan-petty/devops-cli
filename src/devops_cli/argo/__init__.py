"""ArgoCD multi-cluster fleet coordination and progressive rollouts module."""

from __future__ import annotations

from devops_cli.argo.credentials import (
    resolve_argocd_server_address,
    resolve_argocd_server_and_token,
)
from devops_cli.argo.fleet import sync_fleet, sync_single_target
from devops_cli.argo.gitops import (
    GitOpsWatcher,
    compute_manifest_state,
    scan_manifest_drift,
    trigger_argocd_sync,
)
from devops_cli.argo.rollouts import (
    abort_rollout,
    evaluate_rollout_gate,
    promote_rollout,
    restart_rollout,
)
from devops_cli.argo.sync import build_sync_request_body

__all__ = [
    "GitOpsWatcher",
    "abort_rollout",
    "build_sync_request_body",
    "compute_manifest_state",
    "evaluate_rollout_gate",
    "promote_rollout",
    "resolve_argocd_server_address",
    "resolve_argocd_server_and_token",
    "restart_rollout",
    "scan_manifest_drift",
    "sync_fleet",
    "sync_single_target",
    "trigger_argocd_sync",
]
