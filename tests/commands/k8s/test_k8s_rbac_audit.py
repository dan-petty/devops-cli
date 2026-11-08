"""Tests for the Kubernetes RBAC audit (`devops k8s rbac-audit`)."""

from __future__ import annotations

import json
import subprocess
from typing import Any

from typer.testing import CliRunner

from devops_cli.commands.k8s import app
from tests.support.fakes.process import ProcessAnswer, ProcessCall, ProcessFake

runner = CliRunner()


def _binding(
    kind: str, name: str, role_kind: str, role: str, subjects: list[dict[str, str]], ns: str = ""
) -> dict[str, Any]:
    """Build a ClusterRoleBinding or RoleBinding as `kubectl get -o json` lists it."""
    metadata = {"name": name, "namespace": ns} if ns else {"name": name}
    return {
        "kind": kind,
        "metadata": metadata,
        "roleRef": {"apiGroup": "rbac.authorization.k8s.io", "kind": role_kind, "name": role},
        "subjects": subjects,
    }


def _role(kind: str, name: str, rules: list[dict[str, list[str]]], ns: str = "") -> dict[str, Any]:
    """Build a ClusterRole or Role as `kubectl get -o json` lists it."""
    metadata = {"name": name, "namespace": ns} if ns else {"name": name}
    return {"kind": kind, "metadata": metadata, "rules": rules}


_STOCK_ROLES = [
    _role(
        "ClusterRole", "cluster-admin", [{"apiGroups": ["*"], "resources": ["*"], "verbs": ["*"]}]
    ),
    _role("ClusterRole", "view", [{"apiGroups": [""], "resources": ["pods"], "verbs": ["get"]}]),
]
_STOCK_BINDINGS = [
    _binding(
        "ClusterRoleBinding",
        "cluster-admin",
        "ClusterRole",
        "cluster-admin",
        [{"kind": "Group", "name": "system:masters"}],
    ),
]


def _kubectl(
    process_fake: ProcessFake, bindings: list[dict[str, Any]], roles: list[dict[str, Any]]
) -> None:
    """Make kubectl answer the binding and role reads with `List` documents."""

    def answer(call: ProcessCall) -> subprocess.CompletedProcess[str]:
        items = bindings if "clusterrolebindings,rolebindings" in call.argv else roles
        document = json.dumps({"kind": "List", "items": items})
        return subprocess.CompletedProcess(list(call.argv), 0, document, "")

    process_fake.answer(lambda _call: True, ProcessAnswer(side_effect=answer))


def _calls(process_fake: ProcessFake) -> list[list[str]]:
    """The argv of each program that the audit started."""
    return [list(call.argv) for call in process_fake.calls]


def test_k8s_rbac_audit_dry_run() -> None:
    result = runner.invoke(app, ["rbac-audit"], env={"DEVOPS_CLI_DRY_RUN": "true"})
    assert result.exit_code == 0
    assert "kubectl get" in result.output


def test_rbac_audit_fails_a_service_account_bound_to_cluster_admin(
    process_fake: ProcessFake,
) -> None:
    """A ServiceAccount outside kube-system holding cluster-admin is a failing finding."""
    ci_bot = _binding(
        "ClusterRoleBinding",
        "ci-bot-admin",
        "ClusterRole",
        "cluster-admin",
        [{"kind": "ServiceAccount", "name": "ci-bot", "namespace": "default"}],
    )
    _kubectl(process_fake, [*_STOCK_BINDINGS, ci_bot], _STOCK_ROLES)
    result = runner.invoke(app, ["rbac-audit"])

    assert (result.exit_code, "ci-bot" in result.output, "FAIL" in result.output) == (1, True, True)
    assert ("PASS" in result.output, "system:masters" in result.output) == (False, False)
    assert _calls(process_fake) == [
        ["kubectl", "get", "clusterrolebindings,rolebindings", "-o", "json", "--all-namespaces"],
        ["kubectl", "get", "clusterroles,roles", "-o", "json", "--all-namespaces"],
    ]


def test_rbac_audit_fails_a_wildcard_role_and_escapes_names(process_fake: ProcessFake) -> None:
    """A Role granting `*` to a user is a finding; cluster names are shown literally, not as markup."""
    roles = [
        *_STOCK_ROLES,
        _role("Role", "ops", [{"apiGroups": [""], "resources": ["*"], "verbs": ["get"]}], "team-a"),
    ]
    bindings = [
        *_STOCK_BINDINGS,
        _binding(
            "RoleBinding", "ops", "Role", "ops", [{"kind": "User", "name": "[red]eve"}], "team-a"
        ),
        _binding(
            "RoleBinding",
            "viewers",
            "ClusterRole",
            "view",
            [{"kind": "User", "name": "bob"}],
            "team-a",
        ),
    ]
    _kubectl(process_fake, bindings, roles)
    result = runner.invoke(app, ["rbac-audit", "--namespace", "team-a"])

    assert (result.exit_code, "User/[red]eve" in result.output, "bob" in result.output) == (
        1,
        True,
        False,
    )
    assert [call[-2:] for call in _calls(process_fake)] == [["-n", "team-a"], ["-n", "team-a"]]


def test_rbac_audit_passes_a_cluster_with_only_system_and_scoped_grants(
    process_fake: ProcessFake,
) -> None:
    """System subjects and narrow roles pass, and the exit code says so."""
    bindings = [
        *_STOCK_BINDINGS,
        _binding(
            "ClusterRoleBinding",
            "readers",
            "ClusterRole",
            "view",
            [{"kind": "Group", "name": "devs"}],
        ),
        _binding(
            "RoleBinding",
            "dns-admin",
            "ClusterRole",
            "admin",
            [{"kind": "ServiceAccount", "name": "coredns", "namespace": "kube-system"}],
            "kube-system",
        ),
    ]
    _kubectl(process_fake, bindings, _STOCK_ROLES)
    result = runner.invoke(app, ["rbac-audit"])

    assert (result.exit_code, "FAIL" in result.output, "3 binding" in result.output) == (
        0,
        False,
        True,
    )


def test_rbac_audit_does_not_excuse_the_groups_that_stand_for_everyone(
    process_fake: ProcessFake,
) -> None:
    """`system:authenticated` is every client: its `system:` prefix excuses nothing."""
    open_door = _binding(
        "ClusterRoleBinding",
        "open-door",
        "ClusterRole",
        "edit",
        [
            {"kind": "Group", "name": "system:authenticated"},
            {"kind": "User", "name": "system:kube-scheduler"},
        ],
    )
    # An aggregated ClusterRole with nothing aggregated yet is listed with `"rules": null`.
    edit = {"kind": "ClusterRole", "metadata": {"name": "edit"}, "rules": None}
    _kubectl(process_fake, [open_door], [*_STOCK_ROLES, edit])
    result = runner.invoke(app, ["rbac-audit"])

    assert (
        result.exit_code,
        "Group/system:authenticated" in result.output,
        "kube-scheduler" in result.output,
    ) == (1, True, False)


def test_rbac_audit_reads_service_account_users_and_groups_as_service_accounts(
    process_fake: ProcessFake,
) -> None:
    """`User system:serviceaccount:<ns>:<name>` and `Group system:serviceaccounts:<ns>` are
    ServiceAccounts, so outside kube-system their `system:` prefix excuses nothing."""
    subjects = [
        {"kind": "User", "name": "system:serviceaccount:default:ci-bot"},
        {"kind": "Group", "name": "system:serviceaccounts:default"},
        {"kind": "User", "name": "system:serviceaccount:kube-system:job-runner"},
        {"kind": "Group", "name": "system:serviceaccounts:kube-system"},
    ]
    as_service_accounts = _binding(
        "ClusterRoleBinding", "sa-admins", "ClusterRole", "cluster-admin", subjects
    )
    _kubectl(process_fake, [as_service_accounts], _STOCK_ROLES)
    result = runner.invoke(app, ["rbac-audit"])

    assert (
        result.exit_code,
        result.output.count("FAIL"),
        "User/system:serviceaccount:default:ci-bot" in result.output,
        "Group/system:serviceaccounts:default" in result.output,
        "kube-system" in result.output,
    ) == (1, 2, True, True, False)


def test_rbac_audit_passes_the_stock_k3s_and_kubeadm_bindings(process_fake: ProcessFake) -> None:
    """The control-plane grants k3s and kubeadm create on every cluster pass, so a fresh cluster
    passes the audit; the same wildcard role granted to anyone else still fails."""
    roles = [
        *_STOCK_ROLES,
        _role(
            "ClusterRole",
            "system:kubelet-api-admin",
            [
                {"apiGroups": [""], "resources": ["nodes"], "verbs": ["get", "list", "watch"]},
                {"apiGroups": [""], "resources": ["nodes/log", "nodes/proxy"], "verbs": ["*"]},
            ],
        ),
        _role(
            "ClusterRole",
            "k3s-cloud-controller-manager",
            [
                {"apiGroups": [""], "resources": ["nodes"], "verbs": ["*"]},
                {"apiGroups": ["apps"], "resources": ["daemonsets"], "verbs": ["*"]},
            ],
        ),
    ]
    stock = [
        *_STOCK_BINDINGS,
        # k3s manifests/rolebindings.yaml and manifests/ccm.yaml.
        _binding(
            "ClusterRoleBinding",
            "kube-apiserver-kubelet-admin",
            "ClusterRole",
            "system:kubelet-api-admin",
            [{"kind": "User", "name": "kube-apiserver"}],
        ),
        _binding(
            "ClusterRoleBinding",
            "k3s-cloud-controller-manager",
            "ClusterRole",
            "k3s-cloud-controller-manager",
            [{"kind": "User", "name": "k3s-cloud-controller-manager", "namespace": "kube-system"}],
        ),
        # The k3s helm-controller's install job for the bundled Traefik chart.
        _binding(
            "ClusterRoleBinding",
            "helm-kube-system-traefik",
            "ClusterRole",
            "cluster-admin",
            [{"kind": "ServiceAccount", "name": "helm-traefik", "namespace": "kube-system"}],
        ),
        # kubeadm 1.29+, the group of admin.conf.
        _binding(
            "ClusterRoleBinding",
            "kubeadm:cluster-admins",
            "ClusterRole",
            "cluster-admin",
            [{"kind": "Group", "name": "kubeadm:cluster-admins"}],
        ),
    ]
    _kubectl(process_fake, stock, roles)
    stock_result = runner.invoke(app, ["rbac-audit"])
    look_alike = _binding(
        "ClusterRoleBinding",
        "look-alike",
        "ClusterRole",
        "system:kubelet-api-admin",
        [{"kind": "Group", "name": "kube-apiserver"}],
    )
    _kubectl(process_fake, [*stock, look_alike], roles)
    look_alike_result = runner.invoke(app, ["rbac-audit"])

    assert (stock_result.exit_code, "FAIL" in stock_result.output) == (0, False)
    assert (look_alike_result.exit_code, look_alike_result.output.count("FAIL")) == (1, 1)
    assert "Group/kube-apiserver" in look_alike_result.output


def test_rbac_audit_that_cannot_read_the_cluster_fails_without_a_verdict(
    process_fake: ProcessFake,
) -> None:
    """A kubectl that cannot read RBAC objects is an error and a non-zero exit, never a PASS."""
    denied = "Error from server (Forbidden): nope"
    process_fake.answer(lambda _call: True, ProcessAnswer(returncode=1, stderr=denied))
    result = runner.invoke(app, ["rbac-audit"])

    assert (result.exit_code, "Forbidden" in result.output, "PASS" in result.output) == (
        1,
        True,
        False,
    )
