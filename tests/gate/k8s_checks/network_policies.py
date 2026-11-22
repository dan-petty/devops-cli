"""Every network policy has a path that deploy-stack applies (#2164), the pods that reach SearXNG
(#3924), and no policy with both types lets its egress rules skip its ingress rules (#6708)."""

from __future__ import annotations

import functools
import ipaddress
from collections.abc import Iterable
from pathlib import Path
from typing import Any

import yaml

from devops_cli.commands.k8s import stack_lifecycle
from devops_cli.commands.k8s.networking import _resolve_stacks
from devops_cli.commands.k8s.stack_lifecycle import KUSTOMIZATIONS_BY_STACK
from devops_cli.github.repo_ref import RepoRef
from devops_cli.k8s.cluster_job import (
    RUNNER_TEMPLATE,
    STAGE_TEMPLATE,
    JobTemplate,
    build_job,
    stage_job_labels,
)
from tests.gate.k8s_render import applied_objects, kustomize, kustomized_objects, manifest_objects
from tests.support.k8s_tree import deploy_stack_manifests
from tests.support.paths import REPO_ROOT

K8S_DIR = REPO_ROOT / "k8s"


# The NetworkPolicies `devops k8s deploy-stack` does not apply: (namespace, name) to the file that
# declares the policy and the issue that owns its deploy path, or the path that applies it instead.
# An Argo CD Application is such a path, never a deploy-stack one: a cluster without Argo CD gets
# only what deploy-stack applies (#913). Delete an entry once its policy gains a deploy-stack path
# or leaves its file; the guard below fails until then.
UNDEPLOYED_NETWORK_POLICIES: dict[tuple[str, str], tuple[str, str]] = {}


def _deploy_stack_network_policies() -> set[tuple[str, str]]:
    """(namespace, name) of every NetworkPolicy `deploy-stack --stack all` applies without Argo CD.

    It applies the root kustomization, then each stack's kustomizations, then its manifest paths,
    then its post-Helm paths. A manifest path is a file or a kustomization directory.
    """
    stacks = _resolve_stacks("all")
    post_helm_by_stack: dict[str, tuple[Path, ...]] = getattr(
        stack_lifecycle, "POST_HELM_BY_STACK", {}
    )
    post_helm = [
        *(K8S_DIR / entry for stack in stacks for entry in post_helm_by_stack.get(stack, ())),
        *(
            K8S_DIR / "devops" / entry
            for stack in stacks
            for entry in stack_lifecycle.PRODUCT_POST_HELM_BY_STACK.get(stack, ())
        ),
    ]
    kustomizations = [
        K8S_DIR,
        *(K8S_DIR / entry for stack in stacks for entry in KUSTOMIZATIONS_BY_STACK.get(stack, ())),
        *(path for path in post_helm if path.is_dir()),
    ]
    manifests = [
        *deploy_stack_manifests(stacks),
        *(path for path in post_helm if path.is_file()),
    ]
    return {
        policy
        for kustomization in kustomizations
        for policy in kustomized_objects(kustomization, "NetworkPolicy")
    } | {policy for manifest in manifests for policy in applied_objects(manifest, "NetworkPolicy")}


def _policies_from_source(src: dict[str, Any]) -> set[tuple[str, str]]:
    rel_path = src.get("path")
    if not rel_path:
        return set()
    target = REPO_ROOT / rel_path
    if (target / "kustomization.yaml").is_file() or (target / "kustomization.yml").is_file():
        return set(kustomized_objects(target, "NetworkPolicy"))
    if target.is_file():
        return set(manifest_objects(target, "NetworkPolicy"))
    return set()


def _argocd_network_policies() -> set[tuple[str, str]]:
    """(namespace, name) of every NetworkPolicy rendered by Argo CD Applications (#1673)."""
    apps_dir = K8S_DIR / "argocd" / "apps"
    policies: set[tuple[str, str]] = set()
    for app_file in sorted(apps_dir.glob("*.yaml")):
        if app_file.name == "projects.yaml":
            continue
        for doc in yaml.safe_load_all(app_file.read_text(encoding="utf-8")):
            if not isinstance(doc, dict) or doc.get("kind") != "Application":
                continue
            spec = doc.get("spec", {})
            sources = list(spec.get("sources", []))
            if "source" in spec and isinstance(spec["source"], dict):
                sources.append(spec["source"])
            for src in sources:
                policies.update(_policies_from_source(src))
    return policies


def check_every_network_policy_has_a_deploy_stack_path_or_an_owned_exemption() -> None:
    """deploy-stack and Argo CD apply every NetworkPolicy under k8s/, or an exemption names its owner (#913, #1673).

    Each namespace's kustomization lists its policy, and a policy counts as deployed only when
    rendered by both native deploy-stack and an Argo CD Application (or it carries an owned exemption).
    """
    declared = {
        policy
        for path in K8S_DIR.rglob("*.y*ml")
        for policy in manifest_objects(path, "NetworkPolicy")
    }
    applied = _deploy_stack_network_policies() & _argocd_network_policies()
    exempted = set(UNDEPLOYED_NETWORK_POLICIES)
    assert (
        sorted(declared - applied - exempted),
        sorted(exempted & applied),
        sorted(
            policy
            for policy, (path, _owner) in UNDEPLOYED_NETWORK_POLICIES.items()
            if policy not in manifest_objects(REPO_ROOT / path, "NetworkPolicy")
        ),
    ) == ([], [], [])


# ── Who reaches SearXNG (#3924, #5483) ────────────────────────────────────────

SEARXNG_PORT = 8080


@functools.cache
def _devops_documents() -> tuple[dict[str, Any], ...]:
    rendered = yaml.load_all(kustomize(K8S_DIR / "devops").stdout, Loader=yaml.CSafeLoader)
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


def _admits(rules: list[dict[str, Any]], side: str, labels: dict[str, str]) -> bool:
    """Whether a rule of `rules` admits TCP 8080 for a peer pod with `labels` of namespace devops."""
    return any(
        any(_selects(peer.get("podSelector", {}), labels) for peer in rule.get(side, []))
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


# ── A policy with both types lets its egress skip its ingress (#6708) ─────────────
#
# kube-router keeps one chain for each policy, with its ingress and its egress rules. The chain of
# a pod jumps to the chain of each policy that selects it, and for a policy with both types the
# jump has no source or destination match. So when such a policy selects the source and the
# destination pod, its egress rule marks the traffic, and the destination accepts it before its
# ingress rules run. Two single-type policies are enforced correctly (#6708, retest 2026-11-22).

NAMESPACE_NAME_LABEL = "kubernetes.io/metadata.name"

# The ranges a pod address takes: the private ranges of RFC 1918 and the shared range of
# RFC 6598. kube-router matches an ipBlock against pod addresses (k8s/llm/gateway/networkpolicy.yaml).
POD_ADDRESS_RANGES = tuple(
    ipaddress.IPv4Network(cidr)
    for cidr in ("10.0.0.0/8", "100.64.0.0/10", "172.16.0.0/12", "192.168.0.0/16")
)


def _apart(first: dict[str, Any], second: dict[str, Any]) -> bool:
    """Whether no pod can match both label selectors: one key has two values, or an expression
    of one selector refuses the value that the other selector requires."""
    first_labels = first.get("matchLabels") or {}
    second_labels = second.get("matchLabels") or {}
    if any(
        first_labels[key] != second_labels[key]
        for key in first_labels.keys() & second_labels.keys()
    ):
        return True
    return any(
        not _selects({"matchExpressions": [expression]}, labels)
        for labels, expressions in (
            (first_labels, second.get("matchExpressions") or []),
            (second_labels, first.get("matchExpressions") or []),
        )
        for expression in expressions
        if expression["key"] in labels
    )


def _names_other_namespace(peer: dict[str, Any], namespace: str | None) -> bool:
    """Whether the namespace selector of `peer` names a namespace other than `namespace`."""
    named = ((peer.get("namespaceSelector") or {}).get("matchLabels") or {}).get(
        NAMESPACE_NAME_LABEL
    )
    return named is not None and namespace is not None and named != namespace


def _without(
    network: ipaddress.IPv4Network, cut: ipaddress.IPv4Network
) -> list[ipaddress.IPv4Network]:
    """The parts of `network` outside `cut`."""
    if not network.overlaps(cut):
        return [network]
    return [] if network.subnet_of(cut) else list(network.address_exclude(cut))


def _holds_pod_addresses(ip_block: dict[str, Any]) -> bool:
    """Whether an ipBlock holds an address of `POD_ADDRESS_RANGES` after its `except` list."""
    block = ipaddress.ip_network(ip_block["cidr"])
    excepted = [
        cut
        for cut in map(ipaddress.ip_network, ip_block.get("except") or [])
        if isinstance(cut, ipaddress.IPv4Network)
    ]
    if not isinstance(block, ipaddress.IPv4Network):
        return False
    for pod_range in POD_ADDRESS_RANGES:
        if not block.overlaps(pod_range):
            continue
        rest = [block if block.subnet_of(pod_range) else pod_range]
        for cut in excepted:
            rest = [part for network in rest for part in _without(network, cut)]
        if rest:
            return True
    return False


def _reaches_own_pods(peer: dict[str, Any], policy: dict[str, Any]) -> bool:
    """Whether the egress peer `peer` of `policy` can be a pod that `policy` selects."""
    if "ipBlock" in peer:
        return _holds_pod_addresses(peer["ipBlock"])
    if _names_other_namespace(peer, policy["metadata"].get("namespace")):
        return False
    return not _apart(peer.get("podSelector") or {}, policy["spec"].get("podSelector") or {})


def _admits_own_pods(peer: dict[str, Any], policy: dict[str, Any]) -> bool:
    """Whether the ingress peer `peer` of `policy` holds each pod that `policy` selects."""
    if "ipBlock" in peer:
        return False
    selector = policy["spec"].get("podSelector") or {}
    namespaces = peer.get("namespaceSelector")
    if namespaces and (
        namespaces.get("matchExpressions")
        or (namespaces.get("matchLabels") or {})
        != {NAMESPACE_NAME_LABEL: policy["metadata"].get("namespace")}
    ):
        return False
    pods = peer.get("podSelector") or {}
    return (
        not pods
        or pods == selector
        or (
            not pods.get("matchExpressions")
            and pods.get("matchLabels", {}).items() <= (selector.get("matchLabels") or {}).items()
        )
    )


def _port_range(entry: dict[str, Any]) -> tuple[str, tuple[Any, Any] | None]:
    """The protocol and the first and last port of a port entry; None for each port."""
    port = entry.get("port")
    if port is None:
        return entry.get("protocol", "TCP"), None
    return entry.get("protocol", "TCP"), (port, entry.get("endPort", port))


def _covers_port(admitted: dict[str, Any], wanted: dict[str, Any]) -> bool:
    """Whether the ingress port entry `admitted` holds each port of the entry `wanted`."""
    (admitted_protocol, admitted_ports), (wanted_protocol, wanted_ports) = (
        _port_range(admitted),
        _port_range(wanted),
    )
    if admitted_protocol != wanted_protocol or (
        admitted_ports is not None and wanted_ports is None
    ):
        return False
    if admitted_ports is None or wanted_ports is None:
        return True
    if isinstance(admitted_ports[0], str) or isinstance(wanted_ports[0], str):
        return admitted_ports == wanted_ports
    return bool(admitted_ports[0] <= wanted_ports[0] and wanted_ports[1] <= admitted_ports[1])


def _ingress_admits(policy: dict[str, Any], wanted: dict[str, Any] | None) -> bool:
    """Whether an ingress rule of `policy` admits each pod of the policy on the port entry
    `wanted`; None stands for each port."""
    return any(
        (not rule.get("from") or any(_admits_own_pods(peer, policy) for peer in rule["from"]))
        and (
            not rule.get("ports")
            or (wanted is not None and any(_covers_port(entry, wanted) for entry in rule["ports"]))
        )
        for rule in policy["spec"].get("ingress") or []
    )


def _port_text(entry: dict[str, Any] | None) -> str:
    if entry is None:
        return "each port"
    protocol, ports = _port_range(entry)
    if ports is None:
        return f"each {protocol} port"
    first, last = ports
    return f"{protocol} {first}" if first == last else f"{protocol} {first}-{last}"


def dual_type_problems(policies: Iterable[dict[str, Any]]) -> list[str]:
    """Each egress rule of a policy with both types that lets the pods of the policy reach each
    other on a port that no ingress rule of the policy admits from them. kube-router applies no
    ingress rule to that traffic (#6708). A rule with no `to`, a pod peer of the own namespace and
    an ipBlock with a pod address reach the pods of the policy."""
    problems = []
    for policy in policies:
        if not {"Ingress", "Egress"} <= set(policy["spec"].get("policyTypes") or []):
            continue
        name = f"{policy['metadata'].get('namespace')}/{policy['metadata']['name']}"
        for number, rule in enumerate(policy["spec"].get("egress") or [], start=1):
            if rule.get("to") and not any(_reaches_own_pods(peer, policy) for peer in rule["to"]):
                continue
            problems += [
                f"NetworkPolicy {name}: has the types Ingress and Egress, and egress rule {number} "
                f"lets its pods reach each other on {_port_text(wanted)}, which no ingress rule of "
                "it admits from them; kube-router applies no ingress rule to that traffic (#6708), "
                "so split it into an Ingress policy and an Egress policy"
                for wanted in rule.get("ports") or [None]
                if not _ingress_admits(policy, wanted)
            ]
    return problems


@functools.cache
def _tree_network_policies() -> tuple[dict[str, Any], ...]:
    """Each NetworkPolicy document of each YAML file of the environment tree `k8s/`."""
    return tuple(
        document
        for path in sorted(K8S_DIR.rglob("*.y*ml"))
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


def check_no_network_policy_of_the_tree_has_both_types() -> None:
    """Each NetworkPolicy of the environment tree has one type, `Ingress` or `Egress`: kube-router
    lets the rules of one type of a policy with both types skip the rules of the other type for
    traffic between two pods that the policy selects (#6708)."""
    problems = dual_type_problems(_tree_network_policies())
    assert not problems, "\n".join(problems)
