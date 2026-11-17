"""Gitea, the homelab's internal forge and container registry (#1081): its stack.

The form of the manifests and values under `k8s/gitea/` is the work of the `k8s` row of
`devops ci` and of kube-linter, and no test asserts a value of them (#6060).
"""

from __future__ import annotations

from devops_cli.commands.k8s.networking import _resolve_stacks
from devops_cli.config.constants import (
    CONST_K8S_ARGOCD_HOMELAB_APPLICATIONS_BY_STACK,
)
from devops_cli.k8s.cluster_secrets import DETACHED_STACKS

# ── Argo CD and deploy-stack ─────────────────────────────────────────────────


def test_gitea_is_a_stack_of_its_own_that_stack_all_deploys() -> None:
    """Its rows are pushed only with stack `gitea` or `all`, so a deploy of another stack never
    needs the Gitea admin password. Its deploy also sets the git host on Application `ingress`."""
    assert (
        _resolve_stacks("gitea"),
        "gitea" in _resolve_stacks("all"),
        "gitea" in DETACHED_STACKS,
        CONST_K8S_ARGOCD_HOMELAB_APPLICATIONS_BY_STACK["gitea"],
    ) == (["gitea"], True, False, ("ingress",))
