"""The agents of the cluster (#1154): the RBAC audit of a ServiceAccount bound to the view role.

The manifests of that ServiceAccount belong to the environment tree, which devops-cli does not
ship. `devops k8s rbac-audit` audits the live bindings (#6060). deploy-stack applies the build of
the Application `agents` (#6681).
"""

from __future__ import annotations

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
