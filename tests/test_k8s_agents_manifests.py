"""Tests for agent Kubernetes manifests and RBAC security invariants (#1154)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from devops_cli.commands.k8s.stack_lifecycle import _MANIFESTS_BY_STACK, DEFAULT_K8S_DIR
from devops_cli.k8s.rbac import RbacBinding, RbacRole, audit_rbac

_REPO_ROOT = Path(__file__).resolve().parent.parent
_K8S_DIR = _REPO_ROOT / "k8s"


def _load_yaml_docs(path: Path) -> list[dict[str, Any]]:
    with open(path, encoding="utf-8") as f:
        return [doc for doc in yaml.safe_load_all(f) if isinstance(doc, dict)]


def test_agents_namespace_enforces_restricted_pod_security() -> None:
    """Verify namespace agents in k8s/namespaces.yaml enforces restricted Pod Security."""
    namespaces = _load_yaml_docs(_K8S_DIR / "namespaces.yaml")
    agents_ns = next(
        (ns for ns in namespaces if ns.get("metadata", {}).get("name") == "agents"), None
    )
    assert agents_ns is not None, "Namespace 'agents' not found in k8s/namespaces.yaml"

    metadata = agents_ns.get("metadata", {})
    labels = metadata.get("labels", {})
    annotations = metadata.get("annotations", {})

    assert (
        labels.get("pod-security.kubernetes.io/enforce"),
        labels.get("pod-security.kubernetes.io/warn"),
        labels.get("pod-security.kubernetes.io/audit"),
        annotations.get("argocd.argoproj.io/sync-options"),
    ) == (
        "restricted",
        "restricted",
        "restricted",
        "Prune=false,Delete=false",
    )


def test_devops_agent_serviceaccount_automount_disabled() -> None:
    """Verify ServiceAccount agents/devops-agent has automountServiceAccountToken: false."""
    sa_path = _K8S_DIR / "agents" / "serviceaccount.yaml"
    assert sa_path.is_file(), f"Missing {sa_path}"

    docs = _load_yaml_docs(sa_path)
    assert len(docs) == 1
    sa = docs[0]

    assert (
        sa.get("kind"),
        sa.get("metadata", {}).get("name"),
        sa.get("metadata", {}).get("namespace"),
        sa.get("automountServiceAccountToken"),
    ) == (
        "ServiceAccount",
        "devops-agent",
        "agents",
        False,
    )


def test_devops_agent_clusterrolebinding_view_only() -> None:
    """Verify ClusterRoleBinding devops-agent-view binds devops-agent to built-in view."""
    crb_path = _K8S_DIR / "agents" / "clusterrolebinding.yaml"
    assert crb_path.is_file(), f"Missing {crb_path}"

    docs = _load_yaml_docs(crb_path)
    assert len(docs) == 1
    crb = docs[0]

    role_ref = crb.get("roleRef", {})
    subjects = crb.get("subjects", [])

    assert (
        crb.get("kind"),
        crb.get("metadata", {}).get("name"),
        role_ref.get("apiGroup"),
        role_ref.get("kind"),
        role_ref.get("name"),
        len(subjects),
    ) == (
        "ClusterRoleBinding",
        "devops-agent-view",
        "rbac.authorization.k8s.io",
        "ClusterRole",
        "view",
        1,
    )

    subj = subjects[0]
    assert (
        subj.get("kind"),
        subj.get("name"),
        subj.get("namespace"),
    ) == (
        "ServiceAccount",
        "devops-agent",
        "agents",
    )


def test_no_other_rbac_manifest_grants_roles_to_devops_agent() -> None:
    """Verify no other Role, ClusterRole, RoleBinding or ClusterRoleBinding under k8s/ names devops-agent."""
    rbac_kinds = {"Role", "ClusterRole", "RoleBinding", "ClusterRoleBinding"}
    named_files: list[tuple[str, str, str]] = []

    for yaml_file in _K8S_DIR.rglob("*.yaml"):
        if yaml_file.name.endswith(".example.yaml"):
            continue
        try:
            docs = _load_yaml_docs(yaml_file)
        except Exception:
            continue
        for doc in docs:
            kind = doc.get("kind", "")
            if kind in rbac_kinds:
                text = yaml.dump(doc)
                if "devops-agent" in text:
                    named_files.append(
                        (yaml_file.name, kind, doc.get("metadata", {}).get("name", ""))
                    )

    assert named_files == [
        ("clusterrolebinding.yaml", "ClusterRoleBinding", "devops-agent-view"),
    ]


def test_audit_rbac_reports_zero_violations_for_agents_binding() -> None:
    """Verify audit_rbac reports no violations for the agents ClusterRoleBinding."""
    crb_path = _K8S_DIR / "agents" / "clusterrolebinding.yaml"
    crb_doc = _load_yaml_docs(crb_path)[0]
    binding = RbacBinding.model_validate(crb_doc)

    view_role = RbacRole.model_validate(
        {
            "kind": "ClusterRole",
            "metadata": {"name": "view"},
            "rules": [
                {
                    "apiGroups": [""],
                    "resources": ["pods", "configmaps", "services"],
                    "verbs": ["get", "list", "watch"],
                }
            ],
        }
    )

    violations = audit_rbac([binding], [view_role])
    assert violations == []


def test_manifests_by_stack_includes_agents_manifests() -> None:
    """Verify _MANIFESTS_BY_STACK['devops'] contains both agents manifests in proper order."""
    devops_manifests = _MANIFESTS_BY_STACK.get("devops", [])
    expected_sa = DEFAULT_K8S_DIR / "agents" / "serviceaccount.yaml"
    expected_crb = DEFAULT_K8S_DIR / "agents" / "clusterrolebinding.yaml"

    assert (
        expected_sa in devops_manifests,
        expected_crb in devops_manifests,
    ) == (True, True)

    sa_idx = devops_manifests.index(expected_sa)
    crb_idx = devops_manifests.index(expected_crb)
    assert sa_idx < crb_idx, "ServiceAccount must precede ClusterRoleBinding for safe teardown"
