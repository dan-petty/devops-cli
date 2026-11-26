"""Gitea, the homelab's internal forge and container registry (#1081): its stack.

The manifests and values of Gitea belong to the environment tree, which devops-cli does not
ship.
"""

from __future__ import annotations

from devops_cli.commands.k8s.networking import _resolve_stacks
from devops_cli.k8s.cluster_secrets import DETACHED_STACKS

# ── Argo CD and deploy-stack ─────────────────────────────────────────────────


def test_gitea_is_a_stack_of_its_own_that_stack_all_deploys() -> None:
    """Its rows are pushed only with stack `gitea` or `all`, so a deploy of another stack never
    needs the Gitea admin password."""
    assert (
        _resolve_stacks("gitea"),
        "gitea" in _resolve_stacks("all"),
        "gitea" in DETACHED_STACKS,
    ) == (["gitea"], True, False)
