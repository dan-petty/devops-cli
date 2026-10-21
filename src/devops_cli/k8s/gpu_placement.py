"""Which GPU nodes the llm stack's Ollama tiers accept, and what to tell a person about the rest.

Each Ollama DaemonSet in `ollama-profiles.yaml` schedules only on nodes whose labels satisfy its
required `matchExpressions`. A GPU node none of them accept runs no Ollama pod, and the gateway's
routes to that tier fail. The accepted values are read from the profiles, never repeated here,
so a tier added or changed there is checked without an edit in this module (#1367).
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from devops_cli.config.constants import (
    CONST_K8S_GPU_ARCHITECTURE_LABEL,
    CONST_K8S_GPU_PRESENT_LABEL,
    CONST_K8S_GPU_RESOURCE,
    CONST_K8S_GPU_TOTAL_VRAM_LABEL,
    CONST_K8S_OLLAMA_PROVIDER_LABEL,
)
from devops_cli.exceptions.k8s import KubernetesDeployError
from devops_cli.lang import MESSAGES

Term = dict[str, frozenset[str]]


@dataclass(frozen=True)
class Tier:
    """One Ollama DaemonSet: its name and the label values each alternative term requires."""

    name: str
    terms: tuple[Term, ...]


def _term(expressions: Iterable[Mapping[str, Any]], tier: str) -> Term:
    """The label values one `matchExpressions` list requires. Only `In` is read as a list of
    accepted values, so any other operator is refused rather than read wrongly."""
    term: Term = {}
    for expression in expressions:
        if expression["operator"] != "In":
            raise KubernetesDeployError(
                f"{tier}: the node affinity operator {expression['operator']} on "
                f"{expression['key']} is not In, the one operator the GPU placement check reads.",
                chart_or_manifest=tier,
            )
        term[str(expression["key"])] = frozenset(str(v) for v in expression["values"])
    return term


def ollama_tiers(profiles: Path) -> list[Tier]:
    """The Ollama tiers `profiles` defines, each with the label values it requires."""
    provider_key, provider = CONST_K8S_OLLAMA_PROVIDER_LABEL
    try:
        documents = list(yaml.safe_load_all(profiles.read_text(encoding="utf-8")))
    except OSError as exc:
        raise KubernetesDeployError(
            f"Cannot read the Ollama tiers from {profiles}: {exc}", chart_or_manifest=str(profiles)
        ) from exc
    tiers: list[Tier] = []
    for document in documents:
        if not isinstance(document, dict) or document.get("kind") != "DaemonSet":
            continue
        if document["metadata"].get("labels", {}).get(provider_key) != provider:
            continue
        name = str(document["metadata"]["name"])
        affinity = document["spec"]["template"]["spec"]["affinity"]["nodeAffinity"]
        required = affinity["requiredDuringSchedulingIgnoredDuringExecution"]["nodeSelectorTerms"]
        tiers.append(Tier(name, tuple(_term(term["matchExpressions"], name) for term in required)))
    return tiers


def _labels(node: Mapping[str, Any]) -> Mapping[str, str]:
    return node.get("metadata", {}).get("labels") or {}


def _name(node: Mapping[str, Any]) -> str:
    return str(node.get("metadata", {}).get("name", "unknown"))


def is_gpu_node(node: Mapping[str, Any]) -> bool:
    """A node with GPU capacity above zero, or labelled `nvidia.com/gpu.present=true`."""
    capacity = node.get("status", {}).get("capacity") or {}
    try:
        has_gpus = int(capacity.get(CONST_K8S_GPU_RESOURCE, 0)) > 0
    except ValueError:
        has_gpus = False
    return has_gpus or _labels(node).get(CONST_K8S_GPU_PRESENT_LABEL) == "true"


def accepts(tier: Tier, labels: Mapping[str, str]) -> bool:
    """Whether a node with `labels` satisfies one of the tier's alternative terms."""
    return any(
        all(labels.get(key) in values for key, values in term.items()) for term in tier.terms
    )


def _accepted_values(tiers: Iterable[Tier], key: str, given: Mapping[str, str]) -> set[str]:
    """The values of label `key` that tiers accept for a node otherwise labelled `given`."""
    return {
        value
        for tier in tiers
        for term in tier.terms
        if key in term and all(given.get(k) in v for k, v in term.items() if k != key)
        for value in term[key]
    }


def _refusal(node: Mapping[str, Any], tiers: list[Tier]) -> str:
    """Why no tier accepts this GPU node, and what to do about it."""
    name, labels = _name(node), _labels(node)
    total = labels.get(CONST_K8S_GPU_TOTAL_VRAM_LABEL)
    known_totals = {
        v for t in tiers for term in t.terms for v in term.get(CONST_K8S_GPU_TOTAL_VRAM_LABEL, ())
    }
    if total is None:
        return MESSAGES.k8s.gpu_node_without_total.format(
            node=name, vram_label=CONST_K8S_GPU_TOTAL_VRAM_LABEL
        )
    if total not in known_totals:
        return MESSAGES.k8s.gpu_node_total_not_accepted.format(
            node=name, vram_label=CONST_K8S_GPU_TOTAL_VRAM_LABEL, value=total
        )
    accepted = _accepted_values(
        tiers, CONST_K8S_GPU_ARCHITECTURE_LABEL, {CONST_K8S_GPU_TOTAL_VRAM_LABEL: total}
    )
    return MESSAGES.k8s.gpu_node_architecture_not_accepted.format(
        node=name,
        arch_label=CONST_K8S_GPU_ARCHITECTURE_LABEL,
        arch=labels.get(CONST_K8S_GPU_ARCHITECTURE_LABEL, "unset"),
        vram_label=CONST_K8S_GPU_TOTAL_VRAM_LABEL,
        value=total,
        accepted=", ".join(sorted(accepted)),
    )


def placement_warnings(nodes: Iterable[Mapping[str, Any]], tiers: list[Tier]) -> list[str]:
    """One warning for each GPU node no tier accepts, and one more when no node satisfies any
    tier, so no Ollama pod will schedule."""
    nodes = list(nodes)
    placed = any(accepts(tier, _labels(node)) for node in nodes for tier in tiers)
    warnings = [
        _refusal(node, tiers)
        for node in nodes
        if is_gpu_node(node) and not any(accepts(tier, _labels(node)) for tier in tiers)
    ]
    return [*warnings, *([] if placed else [MESSAGES.k8s.no_ollama_tier_schedules])]
