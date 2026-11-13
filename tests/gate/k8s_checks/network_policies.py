"""Every network policy has a path that deploy-stack applies (#2164)."""

from __future__ import annotations

import functools
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
