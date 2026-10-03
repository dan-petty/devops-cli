"""Kubernetes RBAC audit: the bindings that grant broad or wildcard roles to non-system subjects.

The audit reads RoleBindings, ClusterRoleBindings, Roles and ClusterRoles as `kubectl get
-o json` lists them. A binding is overprivileged when its role is one of the built-in
cluster-admin, admin or edit ClusterRoles, or has a rule granting `*` verbs, resources or API
groups. Each subject it grants that role to is a violation, unless the subject is a cluster
component: a ServiceAccount in kube-system, a `system:` user or group other than the built-in
groups that stand for every client or every service account, or a control-plane identity k3s
or kubeadm binds on every cluster. A user or group named for a ServiceAccount
(`system:serviceaccount:<ns>:<name>`, `system:serviceaccounts:<ns>`) is a ServiceAccount.
"""

from __future__ import annotations

from typing import Annotated, Any

from pydantic import BaseModel, BeforeValidator, Field

from devops_cli.config.constants import (
    CONST_K8S_RBAC_BROAD_SUBJECTS,
    CONST_K8S_RBAC_DISTRIBUTION_SUBJECTS,
    CONST_K8S_RBAC_PRIVILEGED_CLUSTER_ROLES,
    CONST_K8S_RBAC_WILDCARD,
    CONST_K8S_SERVICE_ACCOUNT_SUBJECT_PREFIXES,
    CONST_K8S_SYSTEM_NAMESPACE,
    CONST_K8S_SYSTEM_SUBJECT_PREFIX,
)


def _null_as_empty(value: Any) -> Any:
    """Read `null` as an empty list, which is how Kubernetes writes one without omitempty."""
    return [] if value is None else value


_NULL_AS_EMPTY = BeforeValidator(_null_as_empty)


class RbacObjectMeta(BaseModel):
    """The identifying metadata of an RBAC object; cluster-scoped objects have no namespace."""

    name: str = ""
    namespace: str = ""


class RbacSubject(BaseModel):
    """A user, group or ServiceAccount a binding grants its role to."""

    kind: str
    name: str
    namespace: str = ""

    def label(self) -> str:
        """`Kind/name`, with the namespace of a ServiceAccount: `ServiceAccount/default/ci-bot`."""
        if self.kind == "ServiceAccount" and self.namespace:
            return f"{self.kind}/{self.namespace}/{self.name}"
        return f"{self.kind}/{self.name}"

    def is_cluster_component(self, binding_namespace: str) -> bool:
        """Whether the subject is a kube-system ServiceAccount, a narrow `system:` identity or a
        distribution's control plane."""
        if self.name in CONST_K8S_RBAC_BROAD_SUBJECTS:
            return False
        if (self.kind, self.name) in CONST_K8S_RBAC_DISTRIBUTION_SUBJECTS:
            return True
        if self.kind == "ServiceAccount":
            return (self.namespace or binding_namespace) == CONST_K8S_SYSTEM_NAMESPACE
        for prefix in CONST_K8S_SERVICE_ACCOUNT_SUBJECT_PREFIXES:
            if self.name.startswith(prefix):
                service_account_namespace = self.name.removeprefix(prefix).split(":", 1)[0]
                return service_account_namespace == CONST_K8S_SYSTEM_NAMESPACE
        return self.name.startswith(CONST_K8S_SYSTEM_SUBJECT_PREFIX)


class RbacRoleRef(BaseModel):
    """The Role or ClusterRole a binding grants."""

    kind: str
    name: str


class RbacPolicyRule(BaseModel):
    """One rule of a Role or ClusterRole."""

    verbs: Annotated[list[str], _NULL_AS_EMPTY] = Field(default_factory=list)
    resources: Annotated[list[str], _NULL_AS_EMPTY] = Field(default_factory=list)
    api_groups: Annotated[list[str], _NULL_AS_EMPTY] = Field(
        default_factory=list, alias="apiGroups"
    )

    def wildcard_fields(self) -> list[str]:
        """The fields, by their Kubernetes names, where this rule grants `*`."""
        fields = {"verbs": self.verbs, "resources": self.resources, "apiGroups": self.api_groups}
        return [name for name, values in fields.items() if CONST_K8S_RBAC_WILDCARD in values]


class RbacRole(BaseModel):
    """A Role or ClusterRole."""

    kind: str
    metadata: RbacObjectMeta
    rules: Annotated[list[RbacPolicyRule], _NULL_AS_EMPTY] = Field(default_factory=list)


class RbacBinding(BaseModel):
    """A RoleBinding or ClusterRoleBinding."""

    kind: str
    metadata: RbacObjectMeta
    role_ref: RbacRoleRef = Field(alias="roleRef")
    subjects: Annotated[list[RbacSubject], _NULL_AS_EMPTY] = Field(default_factory=list)


class RbacBindingList(BaseModel):
    """`kubectl get clusterrolebindings,rolebindings -o json`."""

    items: list[RbacBinding] = Field(default_factory=list)


class RbacRoleList(BaseModel):
    """`kubectl get clusterroles,roles -o json`."""

    items: list[RbacRole] = Field(default_factory=list)


class RbacViolation(BaseModel):
    """One subject a binding grants an overprivileged role."""

    namespace: str
    binding: str
    role: str
    subject: str
    reason: str


def _role_key(kind: str, namespace: str, name: str) -> tuple[str, str, str]:
    """Key a role by kind, name and, for a namespaced Role only, namespace."""
    return (kind, namespace if kind == "Role" else "", name)


def _overprivilege(role_ref: RbacRoleRef, role: RbacRole | None) -> str:
    """Why the referenced role is overprivileged, or an empty string when it is not."""
    if role_ref.kind == "ClusterRole" and role_ref.name in CONST_K8S_RBAC_PRIVILEGED_CLUSTER_ROLES:
        return f"grants the built-in {role_ref.name} role"
    rules = role.rules if role else []
    wildcards = dict.fromkeys(field for rule in rules for field in rule.wildcard_fields())
    return f"grants '*' {', '.join(wildcards)}" if wildcards else ""


def _binding_violations(
    binding: RbacBinding, roles: dict[tuple[str, str, str], RbacRole]
) -> list[RbacViolation]:
    """The non-system subjects an overprivileged binding grants its role to."""
    namespace, ref = binding.metadata.namespace, binding.role_ref
    reason = _overprivilege(ref, roles.get(_role_key(ref.kind, namespace, ref.name)))
    if not reason:
        return []
    return [
        RbacViolation(
            namespace=namespace,
            binding=f"{binding.kind}/{binding.metadata.name}",
            role=f"{ref.kind}/{ref.name}",
            subject=subject.label(),
            reason=reason,
        )
        for subject in binding.subjects
        if not subject.is_cluster_component(namespace)
    ]


def audit_rbac(bindings: list[RbacBinding], roles: list[RbacRole]) -> list[RbacViolation]:
    """Each non-system subject a binding grants a broad built-in role or a wildcard rule."""
    by_key = {_role_key(r.kind, r.metadata.namespace, r.metadata.name): r for r in roles}
    return [violation for binding in bindings for violation in _binding_violations(binding, by_key)]
