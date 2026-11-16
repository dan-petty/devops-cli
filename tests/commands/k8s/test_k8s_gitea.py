"""Gitea, the homelab's internal forge and container registry (#1081).

Each test reads committed files only. It starts no program and reaches no cluster or network.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from devops_cli.commands.k8s.networking import _resolve_stacks
from devops_cli.config.constants import (
    CONST_K8S_ARGOCD_HOMELAB_APPLICATIONS_BY_STACK,
)
from devops_cli.k8s.cluster_secrets import DETACHED_STACKS
from tests.support.paths import REPO_ROOT

K8S_DIR = REPO_ROOT / "k8s"
GITEA_DIR = K8S_DIR / "gitea"
KEEP = "Prune=false,Delete=false"
NOT_ON_THE_CONTROL_PLANE = {
    "nodeAffinity": {
        "requiredDuringSchedulingIgnoredDuringExecution": {
            "nodeSelectorTerms": [
                {
                    "matchExpressions": [
                        {"key": "node-role.kubernetes.io/control-plane", "operator": "DoesNotExist"}
                    ]
                }
            ]
        }
    }
}


def _yaml(path: Path) -> dict[str, Any]:
    loaded: dict[str, Any] = yaml.safe_load(path.read_text(encoding="utf-8"))
    return loaded


def _documents(path: Path) -> list[dict[str, Any]]:
    return [doc for doc in yaml.safe_load_all(path.read_text(encoding="utf-8")) if doc]


def _values() -> dict[str, Any]:
    return _yaml(GITEA_DIR / "values.yaml")


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


def test_the_gitea_namespace_enforces_restricted_pod_security_and_keeps_its_data() -> None:
    (namespace,) = [
        doc for doc in _documents(K8S_DIR / "namespaces.yaml") if doc["metadata"]["name"] == "gitea"
    ]
    labels = namespace["metadata"]["labels"]

    assert (
        {
            mode: labels[f"pod-security.kubernetes.io/{mode}"]
            for mode in ("enforce", "warn", "audit")
        },
        namespace["metadata"]["annotations"]["argocd.argoproj.io/sync-options"],
    ) == ({"enforce": "restricted", "warn": "restricted", "audit": "restricted"}, KEEP)


# ── Chart values ─────────────────────────────────────────────────────────────


def test_gitea_keeps_its_data_on_a_claim_that_argo_cd_never_deletes() -> None:
    """A pod that mounts a local-path claim never runs on the control-plane node (#1634)."""
    values = _values()

    assert (values["persistence"], values["affinity"]) == (
        {
            "enabled": True,
            "create": True,
            "claimName": "gitea-shared-storage",
            "size": "10Gi",
            "storageClass": "local-path",
            "accessModes": ["ReadWriteOnce"],
            "annotations": {
                "helm.sh/resource-policy": "keep",
                "argocd.argoproj.io/sync-options": KEEP,
            },
        },
        NOT_ON_THE_CONTROL_PLANE,
    )


def test_gitea_is_a_locked_forge_with_its_container_registry_on() -> None:
    """Nobody registers or reads without signing in, a repository is private and only the API
    creates one, nothing reaches outside the cluster, and SSH is off: the rootless image would
    otherwise start its own SSH server on 2222. Packages are on: they hold the container
    registry."""
    config = _values()["gitea"]["config"]

    assert (
        config["service"],
        config["repository"],
        config["mirror"],
        config["actions"],
        config["packages"],
        {key: config["server"][key] for key in ("DISABLE_SSH", "START_SSH_SERVER", "OFFLINE_MODE")},
    ) == (
        {"DISABLE_REGISTRATION": True, "REQUIRE_SIGNIN_VIEW": True},
        {
            "DEFAULT_PRIVATE": "private",
            "ENABLE_PUSH_CREATE_USER": False,
            "ENABLE_PUSH_CREATE_ORG": False,
            "DISABLE_MIGRATIONS": True,
        },
        {"ENABLED": False},
        {"ENABLED": False},
        {"ENABLED": True},
        {"DISABLE_SSH": True, "START_SSH_SERVER": False, "OFFLINE_MODE": True},
    )


def test_gitea_runs_rootless_and_non_root_with_a_read_only_root_and_bounded_resources() -> None:
    """The security contexts follow the gateway's (k8s/llm/gateway/deployment.yaml). The chart's
    connection test pod stays out of the render: it runs `busybox:latest` with no security
    context."""
    values = _values()

    assert (
        {"rootless": values["image"]["rootless"]},
        values["podSecurityContext"],
        values["containerSecurityContext"],
        values["resources"],
        values["test"],
    ) == (
        {"rootless": True},
        {
            "runAsNonRoot": True,
            "runAsUser": 1000,
            "runAsGroup": 1000,
            "fsGroup": 1000,
            "seccompProfile": {"type": "RuntimeDefault"},
        },
        {
            "allowPrivilegeEscalation": False,
            "readOnlyRootFilesystem": True,
            "capabilities": {"drop": ["ALL"]},
        },
        {"requests": {"cpu": "100m", "memory": "256Mi"}, "limits": {"cpu": "1", "memory": "1Gi"}},
        {"enabled": False},
    )


def test_the_admin_comes_from_the_pushed_secret_with_no_password_in_git() -> None:
    """Each start sets the admin's password to the Secret's, so a pushed rotation takes effect
    when push-secrets restarts Gitea."""
    admin = _values()["gitea"]["admin"]

    assert admin == {"existingSecret": "gitea-admin", "passwordMode": "keepUpdated"}
