"""Which Ollama models each node of the llm stack keeps, and which the prune removes (#3654).

Ollama keeps every model that a person pulled, so the store of the control-plane node holds more
than its tiers serve and the root disk passes 85% used, where the kubelet starts to delete images.
The keep set of a node is the set of models that the gateway config sends to a tier Service whose
selector the Ollama pods of that node hold. A model that a node keeps once stays, even when two of
its tiers load it.

`gateway_targets`, `service_selectors` and `parse_ollama_list` read text, and `plan_ollama_prune`
takes the text of the two manifests, the pods and the `ollama list` of each node, so the plan runs
with no cluster. A node whose list was not read keeps every model: the plan removes nothing from
it, and its entry names the node.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit

import yaml

from devops_cli.config.defaults import DEFAULT_LLM_NAMESPACE
from devops_cli.dry_run.requests import PlannedRequest


@dataclass(frozen=True)
class OllamaPod:
    """One Ollama pod of the llm stack: the node it runs on and the labels a Service selects."""

    name: str
    node: str
    labels: Mapping[str, str]


@dataclass(frozen=True)
class NodePrune:
    """What one node keeps, what the prune removes from it, and whether its list was read."""

    node: str
    keep: tuple[str, ...]
    remove: tuple[str, ...]
    list_failed: bool


def _service_name(api_base: str) -> str:
    """The Service of an `api_base`: the first label of its host, which names it in namespace llm."""
    return (urlsplit(api_base).hostname or "").partition(".")[0]


def _backend_model(model: str) -> str:
    """The model that Ollama stores, without the provider prefix of LiteLLM."""
    return model.partition("/")[2]


def gateway_targets(text: str) -> dict[str, frozenset[str]]:
    """The models that the gateway sends to each target, by the Service name of the `api_base`.

    A deployment of a hosted provider has no `api_base`, so it names no target of the cluster.
    """
    targets: dict[str, set[str]] = {}
    for deployment in yaml.safe_load(text)["model_list"]:
        params = deployment["litellm_params"]
        if not (api_base := params.get("api_base")):
            continue
        targets.setdefault(_service_name(api_base), set()).add(_backend_model(params["model"]))
    return {target: frozenset(models) for target, models in targets.items()}


def service_selectors(text: str) -> dict[str, dict[str, str]]:
    """The selector of each Service of `text`, by Service name.

    A Service with no selector selects no pod, so it is left out.
    """
    return {
        str(document["metadata"]["name"]): {
            str(key): str(value) for key, value in document["spec"]["selector"].items()
        }
        for document in yaml.safe_load_all(text)
        if document
        and document.get("kind") == "Service"
        and document.get("spec", {}).get("selector")
    }


def parse_ollama_list(text: str) -> frozenset[str]:
    """The model names of an `ollama list`, whose header names the columns."""
    rows = [line for line in text.splitlines() if line.strip()]
    return frozenset(row.split()[0] for row in rows[1:])


def _selected(labels: Mapping[str, str], selector: Mapping[str, str]) -> bool:
    """Whether a pod with `labels` is an endpoint of a Service with `selector`."""
    return all(labels.get(key) == value for key, value in selector.items())


def _keep_set(
    pods: Iterable[OllamaPod],
    models: Mapping[str, frozenset[str]],
    selectors: Mapping[str, Mapping[str, str]],
) -> frozenset[str]:
    """The models that the gateway sends to each Service that one of `pods` holds."""
    return frozenset(
        model
        for name, selector in selectors.items()
        if any(_selected(pod.labels, selector) for pod in pods)
        for model in models.get(name, frozenset())
    )


def _node_prune(
    node: str,
    pods: list[OllamaPod],
    models: Mapping[str, frozenset[str]],
    selectors: Mapping[str, Mapping[str, str]],
    listing: str | None,
) -> NodePrune:
    """The entry of one node, which removes nothing when its list was not read."""
    keep = _keep_set(pods, models, selectors)
    remove = frozenset() if listing is None else parse_ollama_list(listing) - keep
    return NodePrune(
        node=node,
        keep=tuple(sorted(keep)),
        remove=tuple(sorted(remove)),
        list_failed=listing is None,
    )


def plan_ollama_prune(
    gateway: str,
    services: str,
    pods: Iterable[OllamaPod],
    listed: Mapping[str, str | None],
) -> tuple[NodePrune, ...]:
    """One entry for each node that runs an Ollama pod, sorted by node name.

    `gateway` and `services` are the texts of the two manifests, `pods` are the Ollama pods of the
    stack, and `listed` holds the `ollama list` of each node, or `None` when that call failed.
    """
    models = gateway_targets(gateway)
    selectors = service_selectors(services)
    pods_by_node: dict[str, list[OllamaPod]] = {}
    for pod in pods:
        pods_by_node.setdefault(pod.node, []).append(pod)
    return tuple(
        _node_prune(node, node_pods, models, selectors, listed.get(node))
        for node, node_pods in sorted(pods_by_node.items())
    )


def read_ollama_pods(core: Any, namespace: str = DEFAULT_LLM_NAMESPACE) -> list[OllamaPod]:
    """Read the Ollama pods in `namespace` with label `llm.devops.io/provider=ollama`."""
    pods = core.list_namespaced_pod(
        namespace=namespace, label_selector="llm.devops.io/provider=ollama"
    )
    items = pods.items if hasattr(pods, "items") else pods
    result: list[OllamaPod] = []
    for item in items:
        metadata = getattr(item, "metadata", None)
        spec = getattr(item, "spec", None)
        name = getattr(metadata, "name", "") if metadata else ""
        labels = getattr(metadata, "labels", {}) or {} if metadata else {}
        node = getattr(spec, "node_name", "") if spec else ""
        if isinstance(item, dict):
            name = item.get("metadata", {}).get("name", "")
            labels = item.get("metadata", {}).get("labels", {})
            node = item.get("spec", {}).get("node_name", "")
        result.append(OllamaPod(name=name, node=node, labels=labels))
    return result


def plan_ollama_prune_requests(
    gateway_text: str, context: str | None = None
) -> list[PlannedRequest]:
    """Build the planned external kubectl exec requests for dry-run simulation."""
    targets = gateway_targets(gateway_text)
    requests: list[PlannedRequest] = []
    for target in sorted(targets):
        cmd = [
            "kubectl",
            "exec",
            *(["--context", context] if context else []),
            "-n",
            DEFAULT_LLM_NAMESPACE,
            f"<{target}-pod>",
            "--",
            "ollama",
            "rm",
            "<model>",
        ]
        requests.append(
            PlannedRequest(
                method="kubectl",
                target=f"exec {target}",
                argv=tuple(cmd),
            )
        )
    return requests


__all__ = [
    "NodePrune",
    "OllamaPod",
    "gateway_targets",
    "parse_ollama_list",
    "plan_ollama_prune",
    "plan_ollama_prune_requests",
    "read_ollama_pods",
    "service_selectors",
]
