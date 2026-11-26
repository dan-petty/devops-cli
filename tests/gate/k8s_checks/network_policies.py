"""Every network policy of the product base `k8s/devops` has a path that deploy-stack applies
(#2164), the pods that reach SearXNG (#3924), and no policy has both types, `Ingress` and `Egress`
(#6708)."""

from __future__ import annotations

import functools
from collections.abc import Iterable
from typing import Any

import yaml

from devops_cli.commands.k8s.stack_lifecycle import (
    PRODUCT_MANIFESTS_BY_STACK,
    PRODUCT_POST_HELM_BY_STACK,
)
from devops_cli.github.repo_ref import RepoRef
from devops_cli.k8s.cluster_job import (
    RUNNER_TEMPLATE,
    STAGE_TEMPLATE,
    JobTemplate,
    build_job,
    stage_job_labels,
)
from tests.gate.k8s_render import applied_objects, kustomize, manifest_objects
from tests.support.paths import REPO_ROOT

DEVOPS_DIR = REPO_ROOT / "k8s" / "devops"


def check_every_network_policy_of_the_product_base_has_both_apply_paths() -> None:
    """Argo CD and deploy-stack each apply every NetworkPolicy of `k8s/devops` (#913). Application
    `devops` applies the build of the folder, and it prunes, so a policy that the root
    kustomization does not reach leaves the cluster. A cluster without Argo CD gets only what
    deploy-stack applies, so a policy that no product table names stays out."""
    declared = {
        policy
        for path in DEVOPS_DIR.rglob("*.y*ml")
        for policy in manifest_objects(path, "NetworkPolicy")
    }
    applied = {
        policy
        for table in (PRODUCT_MANIFESTS_BY_STACK, PRODUCT_POST_HELM_BY_STACK)
        for paths in table.values()
        for path in paths
        for policy in applied_objects(DEVOPS_DIR / path, "NetworkPolicy")
    }

    built = applied_objects(DEVOPS_DIR, "NetworkPolicy")

    assert (sorted(declared - applied), sorted(declared - built)) == ([], [])


# ── Who reaches SearXNG (#3924, #5483) ────────────────────────────────────────

SEARXNG_PORT = 8080


@functools.cache
def _devops_documents() -> tuple[dict[str, Any], ...]:
    rendered = yaml.load_all(kustomize(DEVOPS_DIR).stdout, Loader=yaml.CSafeLoader)
    return tuple(document for document in rendered if isinstance(document, dict))


def _selects(selector: dict[str, Any], labels: dict[str, str]) -> bool:
    """Whether a label selector of Kubernetes selects a pod with `labels`."""
    if not selector.get("matchLabels", {}).items() <= labels.items():
        return False
    for expression in selector.get("matchExpressions", []):
        key, operator, values = expression["key"], expression["operator"], expression.get("values")
        held = labels.get(key)
        if operator == "In" and held not in values:
            return False
        if operator == "NotIn" and held in values:
            return False
        if operator == "Exists" and key not in labels:
            return False
        if operator == "DoesNotExist" and key in labels:
            return False
    return True


_DEVOPS_NAMESPACE_LABELS = {"kubernetes.io/metadata.name": "devops"}


def _peer_admits_a_devops_pod(peer: dict[str, Any], labels: dict[str, str]) -> bool:
    """Whether a peer of a rule admits a pod of namespace devops with `labels`: its
    `namespaceSelector` selects the namespace devops, and its `podSelector` selects the pod. A
    peer with neither selector admits each pod, and a peer of another namespace admits no pod of
    devops (#4201)."""
    return _selects(peer.get("namespaceSelector", {}), _DEVOPS_NAMESPACE_LABELS) and _selects(
        peer.get("podSelector", {}), labels
    )


def _admits(rules: list[dict[str, Any]], side: str, labels: dict[str, str]) -> bool:
    """Whether a rule of `rules` admits TCP 8080 for a peer pod with `labels` of namespace devops."""
    return any(
        any(_peer_admits_a_devops_pod(peer, labels) for peer in rule.get(side, []))
        and any(port["port"] == SEARXNG_PORT for port in rule.get("ports", []))
        for rule in rules
    )


def _reaches_searxng(labels: dict[str, str]) -> bool:
    """Whether a pod of namespace devops with `labels` may send to SearXNG on TCP 8080 and
    SearXNG admits it: a policy that selects the pod lets it out, and the perimeter of SearXNG
    lets it in."""
    policies = [document for document in _devops_documents() if document["kind"] == "NetworkPolicy"]
    searxng = {"app.kubernetes.io/name": "searxng"}
    egress = any(
        _selects(policy["spec"]["podSelector"], labels)
        and _admits(policy["spec"].get("egress", []), "to", searxng)
        for policy in policies
    )
    ingress = any(
        _selects(policy["spec"]["podSelector"], searxng)
        and _admits(policy["spec"].get("ingress", []), "from", labels)
        for policy in policies
    )
    return egress and ingress


def _job_pod_labels(template: JobTemplate, labels: dict[str, str] | None = None) -> dict[str, str]:
    """The labels of the pod of a Job that `build_job` makes from `template`."""
    (cronjob,) = (
        document
        for document in _devops_documents()
        if document["kind"] == "CronJob" and document["metadata"]["name"] == template.cronjob
    )
    job = build_job(cronjob, ["--version"], "probe", template=template, labels=labels)
    pod_labels: dict[str, str] = job["spec"]["template"]["metadata"]["labels"]
    return pod_labels


def check_the_service_and_the_stage_job_reach_searxng_and_the_runner_job_does_not() -> None:
    """The stage planner has the tool `search_web`, so the pod of a stage Job reaches SearXNG, as
    the Service pod does. The pod of a runner Job does not."""
    stage = _job_pod_labels(STAGE_TEMPLATE, stage_job_labels(RepoRef("example/project"), 7))
    runner = _job_pod_labels(RUNNER_TEMPLATE)
    service = {"app.kubernetes.io/name": "roadmap-service"}

    assert (
        _reaches_searxng(service),
        _reaches_searxng(stage),
        _reaches_searxng(runner),
    ) == (True, True, False)


# ── A policy with both types (#6708) ───────────────────────────────────────────────
#
# kube-router keeps one chain for each policy, with its ingress and its egress rules. The chain of
# a pod jumps to the chain of each policy that selects it, and for a policy with both types the
# jump has no source or destination match. So when such a policy selects the source and the
# destination pod, its egress rule marks the traffic, and the destination accepts it before its
# ingress rules run. By the same chain, its ingress rule can let the source skip its egress
# rules. Two single-type policies are enforced correctly (#6708, retest 2026-11-22).


def _policy_types(policy: dict[str, Any]) -> set[str]:
    """The types of a NetworkPolicy as the API server sets them (`SetDefaults_NetworkPolicy`):
    `policyTypes` as written; with no types, `Ingress`, and `Egress` when it has an egress rule."""
    spec = policy["spec"]
    if spec.get("policyTypes"):
        return set(spec["policyTypes"])
    return {"Ingress", "Egress"} if spec.get("egress") else {"Ingress"}


def dual_type_problems(policies: Iterable[dict[str, Any]]) -> list[str]:
    """Each NetworkPolicy whose types hold `Ingress` and `Egress` (#6708)."""
    return [
        f"NetworkPolicy {policy['metadata'].get('namespace')}/{policy['metadata']['name']}: has "
        "the types Ingress and Egress, and kube-router lets the rules of one type skip the rules "
        "of the other type for traffic between the pods that it selects (#6708), so split it "
        "into <name>-ingress with the type Ingress and <name>-egress with the type Egress"
        for policy in policies
        if {"Ingress", "Egress"} <= _policy_types(policy)
    ]


@functools.cache
def _product_network_policies() -> tuple[dict[str, Any], ...]:
    """Each NetworkPolicy document of each YAML file of the product base `k8s/devops`."""
    return tuple(
        document
        for path in sorted(DEVOPS_DIR.rglob("*.y*ml"))
        for document in yaml.load_all(path.read_text(encoding="utf-8"), Loader=yaml.CSafeLoader)
        if isinstance(document, dict) and document.get("kind") == "NetworkPolicy"
    )


def _fixture(name: str, types: list[str] | None, **spec: Any) -> dict[str, Any]:
    """A NetworkPolicy named `name` in namespace `fixture` that selects each pod. `types` None
    leaves `policyTypes` out, so the API server sets the types."""
    written = {} if types is None else {"policyTypes": types}
    return {
        "kind": "NetworkPolicy",
        "metadata": {"name": name, "namespace": "fixture"},
        "spec": {"podSelector": {}, **written, **spec},
    }


_INGRESS = [{"from": [{"podSelector": {}}], "ports": [{"protocol": "TCP", "port": 3000}]}]
_EGRESS = [{"to": [{"podSelector": {}}]}]


def check_the_dual_type_rule_names_a_policy_that_writes_both_types() -> None:
    # The probe of #6708: the egress rule lets each pod reach each other pod on every port, and
    # kube-router applies no ingress rule of the policy to that traffic.
    fixture = _fixture("fixture-written", ["Ingress", "Egress"], ingress=_INGRESS, egress=_EGRESS)

    (problem,) = dual_type_problems([fixture])
    assert ("fixture/fixture-written" in problem, "kube-router" in problem) == (True, True)


def check_the_dual_type_rule_names_a_policy_with_no_types_and_an_egress_rule() -> None:
    # The API server gives a policy with no `policyTypes` the type Ingress, and Egress when the
    # policy has an egress rule.
    public = [{"to": [{"ipBlock": {"cidr": "0.0.0.0/0"}}]}]
    fixture = _fixture("fixture-defaulted", None, egress=public)

    (problem,) = dual_type_problems([fixture])
    assert "fixture/fixture-defaulted" in problem


def check_the_dual_type_rule_accepts_single_type_policies() -> None:
    policies = [
        _fixture("ingress-only", ["Ingress"], ingress=_INGRESS),
        _fixture("egress-only", ["Egress"], egress=_EGRESS),
        _fixture("defaulted-ingress", None, ingress=_INGRESS),
        _fixture("defaulted-no-egress-rule", None, ingress=_INGRESS, egress=[]),
    ]

    assert dual_type_problems(policies) == []


def check_no_network_policy_of_the_product_base_has_both_types() -> None:
    """Each NetworkPolicy of `k8s/devops` has one type, `Ingress` or `Egress`: kube-router
    lets the rules of one type of a policy with both types skip the rules of the other type for
    traffic between two pods that the policy selects (#6708)."""
    problems = dual_type_problems(_product_network_policies())
    assert not problems, "\n".join(problems)
