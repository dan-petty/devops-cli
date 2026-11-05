"""What the GPU architecture thresholds make of an Ollama tier: its manifests and gateway routes.

`k8s/llm/profiles/gpu-thresholds.yaml` names two architectures, and each template in
`k8s/llm/profiles/tier-templates/` is one tier. A tier at or below `embedding_only` serves embedding
models alone, and the gateway tries it first. A tier above it is a chat tier: it loads one model, and
the gateway sends it no embedding batch (#3567). A tier at or below `per_gpu` runs one Ollama
instance per GPU, each with its own Service and gateway deployment. A rendered tier is named for what it is:
`ollama-<VRAM of one instance>gib-<embed or speed tier>`, with `-gpu<n>` for each instance. The output
goes between two marker lines in each manifest, so the rest of the file stays as a person wrote it
(#3501).
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Final
from urllib.parse import urlsplit

import yaml
from pydantic import BaseModel, ConfigDict, ValidationError, field_validator

from devops_cli.config.constants import (
    CONST_K8S_GPU_ARCHITECTURE_LABEL,
    CONST_K8S_GPU_ARCHITECTURES,
    CONST_K8S_GPU_COUNT_LABEL,
    CONST_K8S_GPU_RESOURCE,
    CONST_RAG_MAX_CHUNK_TOKENS,
)
from devops_cli.config.defaults import DEFAULT_OLLAMA_PORT
from devops_cli.exceptions.k8s import KubernetesDeployError

_BEGIN_MARKER: Final[str] = "# BEGIN rendered by devops ai gateway render from gpu-thresholds.yaml"
_END_MARKER: Final[str] = "# END rendered by devops ai gateway render from gpu-thresholds.yaml"
_GPU_COUNT_ANNOTATION: Final[str] = "llm.devops.io/gpu-count"
_EMBEDDING_MODEL_ANNOTATION: Final[str] = "llm.devops.io/embedding-model"
_GPU_INSTANCE_LABEL: Final[str] = "llm.devops.io/gpu-instance"
_NAME_LABEL: Final[str] = "app.kubernetes.io/name"
_PROVIDER_LABEL: Final[str] = "llm.devops.io/provider"
_VRAM_LABEL: Final[str] = "llm.devops.io/vram-gib"
_TOTAL_VRAM_LABEL: Final[str] = "llm.devops.io/total-vram-gib"
_SPEED_LABEL: Final[str] = "llm.devops.io/speed-tier"
# The speed tier of an embedding-only tier. The selectors of the Services ollama-slow and
# ollama-24gib ask for `slow`, so a client of those Services never reaches an embedding-only tier.
_EMBEDDING_ONLY_SPEED: Final[str] = "embed"
# The most GPUs a node has for the gpu.count requirement of a later instance. The operator is In,
# the one operator that the GPU placement check reads.
_MOST_GPUS_ON_A_NODE: Final[int] = 8
# LiteLLM tries the lowest order first. The tiers that the config writes by hand are at order 2.
_EMBEDDING_ONLY_ORDER: Final[int] = 1
# An embedding-only tier needs no memory for a chat model. Peak memory of an instance was 890 MiB
# under load. With LLAMA_ARG_THREADS at 1, an instance uses 1.2 CPU cores under load.
_EMBEDDING_ONLY_RESOURCES: Final[dict[str, dict[str, str]]] = {
    "requests": {"cpu": "2000m", "memory": "2Gi"},
    "limits": {"memory": "4Gi"},
}


class GpuThresholds(BaseModel):
    """The newest GPU architecture of each rule, oldest architectures included."""

    model_config = ConfigDict(frozen=True, extra="forbid", hide_input_in_errors=True)

    embedding_only: str
    per_gpu: str

    @field_validator("embedding_only", "per_gpu")
    @classmethod
    def _known_architecture(cls, value: str) -> str:
        if value not in CONST_K8S_GPU_ARCHITECTURES:
            raise ValueError(
                f"{value} is not a GPU architecture: use one of {CONST_K8S_GPU_ARCHITECTURES}"
            )
        return value


@dataclass(frozen=True)
class TierManifests:
    """The text of each manifest that holds a rendered region."""

    profiles: str
    services: str
    gateway: str


def load_gpu_thresholds(path: Path) -> GpuThresholds:
    """The thresholds that `path` sets. A file that cannot be read or has a bad value is an error."""
    try:
        return GpuThresholds.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))
    except (OSError, yaml.YAMLError, ValidationError) as exc:
        raise KubernetesDeployError(
            f"Cannot read the GPU thresholds from {path}: {exc}", chart_or_manifest=str(path)
        ) from exc


def load_tier_templates(directory: Path) -> list[dict[str, Any]]:
    """The tier templates in `directory`, by file name. Each file holds one DaemonSet."""
    try:
        return [
            yaml.safe_load(path.read_text(encoding="utf-8"))
            for path in sorted(directory.glob("*.yaml"))
        ]
    except (OSError, yaml.YAMLError) as exc:
        raise KubernetesDeployError(
            f"Cannot read the tier templates from {directory}: {exc}",
            chart_or_manifest=str(directory),
        ) from exc


def _newest_architecture(template: dict[str, Any]) -> str:
    """The newest GPU architecture that the required node affinity of the template accepts."""
    affinity = template["spec"]["template"]["spec"]["affinity"]["nodeAffinity"]
    required = affinity["requiredDuringSchedulingIgnoredDuringExecution"]["nodeSelectorTerms"]
    return str(
        max(
            (
                value
                for term in required
                for expression in term["matchExpressions"]
                if expression["key"] == CONST_K8S_GPU_ARCHITECTURE_LABEL
                for value in expression["values"]
            ),
            key=CONST_K8S_GPU_ARCHITECTURES.index,
        )
    )


def _at_or_below(template: dict[str, Any], threshold: str) -> bool:
    return CONST_K8S_GPU_ARCHITECTURES.index(
        _newest_architecture(template)
    ) <= CONST_K8S_GPU_ARCHITECTURES.index(threshold)


def _gpu_count(template: dict[str, Any]) -> int:
    return int(template["metadata"]["annotations"][_GPU_COUNT_ANNOTATION])


def _set_env(env: list[dict[str, str]], name: str, value: str) -> None:
    """Set one variable of a container in its present place, or add it at the end."""
    for variable in env:
        if variable["name"] == name:
            variable["value"] = value
            return
    env.append({"name": name, "value": value})


def _named_tier(template: dict[str, Any], thresholds: GpuThresholds) -> dict[str, Any]:
    """A copy of the template with the name and labels of what the thresholds make of it."""
    tier: dict[str, Any] = yaml.safe_load(yaml.safe_dump(template))
    tier["metadata"].pop("annotations", None)
    embedding_only = _at_or_below(template, thresholds.embedding_only)
    per_gpu = _at_or_below(template, thresholds.per_gpu)
    if not embedding_only and not per_gpu:
        return tier

    template_labels = template["metadata"]["labels"]
    vram = int(template_labels[_TOTAL_VRAM_LABEL])
    vram = vram // _gpu_count(template) if per_gpu else vram
    speed = _EMBEDDING_ONLY_SPEED if embedding_only else template_labels[_SPEED_LABEL]
    name = f"{template_labels[_PROVIDER_LABEL]}-{vram}gib-{speed}"
    tier["metadata"]["name"] = name
    tier["spec"]["selector"]["matchLabels"][_NAME_LABEL] = name
    for labels in (tier["metadata"]["labels"], tier["spec"]["template"]["metadata"]["labels"]):
        labels[_NAME_LABEL] = name
        labels[_VRAM_LABEL] = f"{vram}gib"
        labels[_TOTAL_VRAM_LABEL] = str(vram)
        labels[_SPEED_LABEL] = speed
    return tier


def _gpu_instance(tier: dict[str, Any], instance: int) -> dict[str, Any]:
    """The DaemonSet of one GPU of `tier`: it claims that GPU, and a later instance needs a node
    with that many GPUs."""
    daemonset: dict[str, Any] = yaml.safe_load(yaml.safe_dump(tier))
    pod = daemonset["spec"]["template"]
    name = f"{tier['metadata']['name']}-gpu{instance}"
    daemonset["metadata"]["name"] = name
    for labels in (
        daemonset["metadata"]["labels"],
        daemonset["spec"]["selector"]["matchLabels"],
        pod["metadata"]["labels"],
    ):
        labels[_NAME_LABEL] = name
    pod["metadata"]["labels"][_GPU_INSTANCE_LABEL] = str(instance)
    [container] = pod["spec"]["containers"]
    container["env"] = [v for v in container["env"] if v["name"] != "OLLAMA_SCHED_SPREAD"]
    # The instances of a node share one model directory, and a pruning start removes each blob that
    # no manifest names yet, as during a pull on the other instance.
    _set_env(container["env"], "OLLAMA_NOPRUNE", "1")
    container["resources"].setdefault("limits", {})[CONST_K8S_GPU_RESOURCE] = 1
    if instance > 0:
        affinity = pod["spec"]["affinity"]["nodeAffinity"]
        for term in affinity["requiredDuringSchedulingIgnoredDuringExecution"]["nodeSelectorTerms"]:
            term["matchExpressions"].append(
                {
                    "key": CONST_K8S_GPU_COUNT_LABEL,
                    "operator": "In",
                    "values": [str(n) for n in range(instance + 1, _MOST_GPUS_ON_A_NODE + 1)],
                }
            )
    return daemonset


def _rendered_daemonsets(
    template: dict[str, Any], thresholds: GpuThresholds
) -> list[dict[str, Any]]:
    """The DaemonSets of one tier: one for each GPU at or below `per_gpu`, else one for all."""
    tier = _named_tier(template, thresholds)
    if _at_or_below(template, thresholds.embedding_only):
        [container] = tier["spec"]["template"]["spec"]["containers"]
        _set_env(container["env"], "OLLAMA_CONTEXT_LENGTH", str(CONST_RAG_MAX_CHUNK_TOKENS))
        _set_env(container["env"], "OLLAMA_MAX_LOADED_MODELS", "1")
        # The embedder runs on the GPU, and the default threads of llama-server only spin: 12 CPU
        # cores against 1.2 with one thread, at the same speed and with equal vectors (#3518).
        _set_env(container["env"], "LLAMA_ARG_THREADS", "1")
        container["resources"] = yaml.safe_load(yaml.safe_dump(_EMBEDDING_ONLY_RESOURCES))
    if not _at_or_below(template, thresholds.per_gpu):
        return [tier]
    return [_gpu_instance(tier, instance) for instance in range(_gpu_count(template))]


def _rendered_service(daemonset: dict[str, Any]) -> dict[str, Any]:
    """The Service of one DaemonSet, with the selector form of the other Services of a tier."""
    pod_labels = daemonset["spec"]["template"]["metadata"]["labels"]
    selector = {
        key: pod_labels[key]
        for key in (_PROVIDER_LABEL, _VRAM_LABEL, _SPEED_LABEL, _GPU_INSTANCE_LABEL)
        if key in pod_labels
    }
    return {
        "apiVersion": "v1",
        "kind": "Service",
        "metadata": {
            "name": daemonset["metadata"]["name"],
            "namespace": daemonset["metadata"]["namespace"],
            "labels": daemonset["metadata"]["labels"],
        },
        "spec": {
            "type": "ClusterIP",
            "ports": [
                {
                    "name": "http",
                    "port": DEFAULT_OLLAMA_PORT,
                    "targetPort": DEFAULT_OLLAMA_PORT,
                    "protocol": "TCP",
                }
            ],
            "selector": selector,
        },
    }


def _embedding_route(daemonset: dict[str, Any], model: str, *, order: int) -> dict[str, Any]:
    metadata = daemonset["metadata"]
    return {
        "model_name": model,
        "litellm_params": {
            "model": f"ollama/{model}",
            "api_base": (
                f"http://{metadata['name']}.{metadata['namespace']}"
                f".svc.cluster.local:{DEFAULT_OLLAMA_PORT}"
            ),
            "num_ctx": CONST_RAG_MAX_CHUNK_TOKENS,
            "order": order,
        },
        "model_info": {"mode": "embedding"},
    }


class _IndentedDumper(yaml.SafeDumper):
    """Writes a list inside its key, as the manifests of this repository do."""

    def increase_indent(self, flow: bool = False, indentless: bool = False) -> None:
        super().increase_indent(flow, False)


def _dump(document: Any) -> str:
    return yaml.dump(document, Dumper=_IndentedDumper, sort_keys=False, width=100)


def _replace_region(text: str, body: str, manifest: str) -> str:
    """`text` with the lines between the two markers replaced by `body`."""
    lines = text.splitlines(keepends=True)
    stripped = [line.strip() for line in lines]
    for marker in (_BEGIN_MARKER, _END_MARKER):
        if marker not in stripped:
            raise KubernetesDeployError(
                f"The {manifest} has no line '{marker}', so the render has no place to write.",
                chart_or_manifest=manifest,
            )
    begin, end = stripped.index(_BEGIN_MARKER), stripped.index(_END_MARKER)
    return "".join([*lines[: begin + 1], body, *lines[end:]])


def _refuse_chat_routes(gateway: str, services: set[str], tier: str) -> None:
    """Fail for a generation deployment on an embedding-only tier. Which tier serves a group
    instead is a routing decision, so the render moves none."""
    groups = sorted(
        {
            str(deployment["model_name"])
            for deployment in yaml.safe_load(gateway)["model_list"]
            if deployment.get("model_info", {}).get("mode") != "embedding"
            and (
                urlsplit(deployment["litellm_params"].get("api_base", "")).hostname or ""
            ).partition(".")[0]
            in services
        }
    )
    if groups:
        raise KubernetesDeployError(
            f"{tier} serves embedding models alone, but the gateway routes {', '.join(groups)} to "
            "it. Move each group to another tier in k8s/llm/gateway/config.yaml.",
            chart_or_manifest=tier,
        )


def render_tier_manifests(
    manifests: TierManifests, thresholds: GpuThresholds, templates: list[dict[str, Any]]
) -> TierManifests:
    """`manifests` with each rendered region written from `thresholds` and `templates`."""
    if not templates:
        raise KubernetesDeployError(
            "No tier template exists, so the render has nothing to write.",
            chart_or_manifest="k8s/llm/profiles/tier-templates",
        )
    newest = max(
        (_newest_architecture(t) for t in templates), key=CONST_K8S_GPU_ARCHITECTURES.index
    )
    for threshold in (thresholds.embedding_only, thresholds.per_gpu):
        if CONST_K8S_GPU_ARCHITECTURES.index(threshold) > CONST_K8S_GPU_ARCHITECTURES.index(newest):
            raise KubernetesDeployError(
                f"The threshold {threshold} is newer than {newest}, the newest architecture of the "
                "tier templates. A tier with no template cannot follow it: add a template first.",
                chart_or_manifest="k8s/llm/profiles/gpu-thresholds.yaml",
            )

    daemonsets: list[dict[str, Any]] = []
    routes: list[dict[str, Any]] = []
    refusals: list[tuple[set[str], str]] = []
    for template in templates:
        tier = _rendered_daemonsets(template, thresholds)
        embedding_only = _at_or_below(template, thresholds.embedding_only)
        daemonsets += tier
        if embedding_only:
            model = template["metadata"]["annotations"][_EMBEDDING_MODEL_ANNOTATION]
            routes += [
                _embedding_route(daemonset, model, order=_EMBEDDING_ONLY_ORDER)
                for daemonset in tier
            ]
            names = {str(d["metadata"]["name"]) for d in tier}
            refusals.append(({str(template["metadata"]["name"]), *names}, sorted(names)[0]))

    gateway = _replace_region(
        manifests.gateway,
        "".join(f"  {line}\n" for line in _dump(routes).splitlines()) if routes else "",
        "gateway config",
    )
    for services, tier_name in refusals:
        _refuse_chat_routes(gateway, services, tier_name)
    return replace(
        manifests,
        profiles=_replace_region(
            manifests.profiles, "---\n".join(_dump(d) for d in daemonsets), "Ollama profiles"
        ),
        services=_replace_region(
            manifests.services,
            "---\n".join(_dump(_rendered_service(d)) for d in daemonsets),
            "LLM services",
        ),
        gateway=gateway,
    )


__all__ = [
    "GpuThresholds",
    "TierManifests",
    "load_gpu_thresholds",
    "load_tier_templates",
    "render_tier_manifests",
]
