"""ArgoCD multi-cluster fleet coordination and progressive rollouts module."""

from __future__ import annotations

from devops_cli.argo.fleet import sync_fleet, sync_single_target
from devops_cli.argo.rollouts import (
    abort_rollout,
    evaluate_rollout_gate,
    promote_rollout,
    restart_rollout,
)

__all__ = [
    "abort_rollout",
    "evaluate_rollout_gate",
    "promote_rollout",
    "restart_rollout",
    "sync_fleet",
    "sync_single_target",
]
