"""The agents of the cluster (#1154): the deploy order of their manifests, and the RBAC audit
of a ServiceAccount bound to the view role.

The form of the manifests under `k8s/agents/` is the work of the `k8s` row of `devops ci` and of
kube-linter, and `devops k8s rbac-audit` audits the live bindings (#6060).
"""

from __future__ import annotations

from pathlib import Path

from devops_cli.commands.k8s.stack_lifecycle import MANIFESTS_BY_STACK
from devops_cli.k8s.rbac import RbacBinding, RbacRole, audit_rbac


def test_audit_rbac_reports_zero_violations_for_a_service_account_bound_to_view() -> None:
    """A ServiceAccount that a ClusterRoleBinding binds to the read-only role `view` passes."""
    binding = RbacBinding.model_validate(
        {
            "kind": "ClusterRoleBinding",
            "metadata": {"name": "example-agent-view"},
            "roleRef": {
                "apiGroup": "rbac.authorization.k8s.io",
                "kind": "ClusterRole",
                "name": "view",
            },
            "subjects": [
                {"kind": "ServiceAccount", "name": "example-agent", "namespace": "agents"}
            ],
        }
    )

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
    """Verify MANIFESTS_BY_STACK['devops'] contains both agents manifests in proper order."""
    devops_manifests = MANIFESTS_BY_STACK.get("devops", [])
    expected_sa = Path("agents", "serviceaccount.yaml")
    expected_crb = Path("agents", "clusterrolebinding.yaml")

    assert (
        expected_sa in devops_manifests,
        expected_crb in devops_manifests,
    ) == (True, True)

    sa_idx = devops_manifests.index(expected_sa)
    crb_idx = devops_manifests.index(expected_crb)
    assert sa_idx < crb_idx, "ServiceAccount must precede ClusterRoleBinding for safe teardown"
