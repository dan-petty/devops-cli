"""Manifest syntax, security perimeter, and zero-leakage validation for LLM Gateway."""

from __future__ import annotations

import copy
import json
import re
import shutil
import sys
from collections.abc import Callable, Iterator
from functools import reduce
from itertools import chain
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import pytest
import yaml
from docker.utils import parse_repository_tag

from devops_cli.ai.benchmark.runner import BenchmarkRunner
from devops_cli.ai.gateway import DEFAULT_GATEWAY_ROUTES, GatewayRoute, GatewayRouter
from devops_cli.ai.gateway_render import load_service_context_lengths, load_tier_context_lengths
from devops_cli.ai.harness.slots import ModelSlot, SubAgentSlot
from devops_cli.commands.k8s.stack_lifecycle import _HELM_RELEASES_BY_STACK, _MANIFESTS_BY_STACK
from devops_cli.config.constants import (
    CONST_AI_GATEWAY_VIRTUAL_MODELS,
    CONST_K8S_OLLAMA_PROVIDER_LABEL,
    CONST_RAG_MAX_CHUNK_TOKENS,
)
from devops_cli.config.defaults import (
    DEFAULT_AI_FALLBACK_MODEL,
    DEFAULT_AI_MODEL,
    DEFAULT_BUNDLE_MODELS,
    DEFAULT_GATEWAY_REVIEW_SLOTS,
    DEFAULT_OLLAMA_CLUSTER_SERVICE,
    DEFAULT_OLLAMA_CLUSTER_URL,
    DEFAULT_REVIEW_TIMEOUT_SECONDS,
)
from devops_cli.config.settings import AIConfig, Settings
from devops_cli.k8s.cluster_secrets import CLUSTER_SECRETS
from devops_cli.k8s.gpu_matrix import (
    get_gateway_routing_entries,
    get_service_aliases,
    list_gpu_profiles,
)
from tests.k8s_manifests import kustomize
from tests.support.markdown_examples import (
    YAML_FENCE_LANGUAGES,
    code_snippets,
    fences,
    headings,
    tables,
)

DEFAULT_AI_GATEWAY_CLUSTER_URL: str = "http://llm-gateway.llm.svc.cluster.local:4000/v1"
GATEWAY_DIR = Path("k8s/llm/gateway")
# The LiteLLM config; the gateway kustomization generates ConfigMap llm-gateway-config from it.
GATEWAY_CONFIG = GATEWAY_DIR / "config.yaml"
LLM_DIR = Path("k8s/llm")
PROFILES_DIR = Path("k8s/llm/profiles")
OLLAMA_PROFILES_MANIFEST = PROFILES_DIR / "ollama-profiles.yaml"
SERVICES_MANIFEST = PROFILES_DIR / "services.yaml"
NETWORKPOLICY_MANIFEST = PROFILES_DIR / "networkpolicy.yaml"
LLM_KUSTOMIZATION = Path("k8s/llm/kustomization.yaml")
OPEN_WEBUI_VALUES = Path("k8s/llm/values-open-webui.yaml")
DEVOPS_CONFIGMAP_EXAMPLE = Path("k8s/devops/configmap.example.yaml")
K8S_README = Path("k8s/README.md")
GATEWAY_READMES = [K8S_README, PROFILES_DIR / "README.md"]
INGRESS_ROUTES = Path("k8s/ingress/ingress-routes.yaml")
DEVCONTAINER = Path(".devcontainer/devcontainer.json")
# The column of the README's GPU placement table that says whether a node satisfies the tier.
SERVES_COLUMN = "Serves"

GATEWAY_IMAGE = "ghcr.io/berriai/litellm:v1.103.0"
GATEWAY_SECRET = "llm-gateway-secrets"
GATEWAY_SECRET_KEY = "master-key"
# The UID and GID every ollama tier runs as; no host login account uses it (#1060).
OLLAMA_UID = 10001


def _load_kind(path: Path, kind: str) -> dict[str, Any]:
    """Return the first document of the given kind from a multi-document manifest."""
    docs = yaml.safe_load_all(path.read_text(encoding="utf-8"))
    return next(d for d in docs if d and d.get("kind") == kind)


def _load_deployment(path: Path, name: str) -> dict[str, Any]:
    """Return the Deployment or DaemonSet with the given metadata.name from a multi-document manifest."""
    docs = yaml.safe_load_all(path.read_text(encoding="utf-8"))
    return next(
        d
        for d in docs
        if d and d.get("kind") in ("Deployment", "DaemonSet") and d["metadata"]["name"] == name
    )


def _load_service(path: Path, name: str) -> dict[str, Any]:
    """Return the Service with the given metadata.name from a multi-document manifest."""
    docs = yaml.safe_load_all(path.read_text(encoding="utf-8"))
    return next(
        d for d in docs if d and d.get("kind") == "Service" and d["metadata"]["name"] == name
    )


# The groups that call a provider outside the cluster (#3113). Every other group is an Ollama tier.
HOSTED_GROUPS = ("gemini-3.8-flash", "claude-sonnet-5-5", "claude-haiku-5-5")
HOSTED_SECRET = "llm-gateway-secrets"


def _full_gateway_config() -> dict[str, Any]:
    """Return the LiteLLM configuration the gateway ConfigMap carries, hosted groups included."""
    return dict(yaml.safe_load(GATEWAY_CONFIG.read_text(encoding="utf-8")))


def _gateway_config() -> dict[str, Any]:
    """Return the LiteLLM configuration of the in-cluster backends: the hosted groups, which
    have no `api_base`, are left out of its `model_list` (`_hosted_models` returns them)."""
    config = _full_gateway_config()
    config["model_list"] = [m for m in config["model_list"] if m["model_name"] not in HOSTED_GROUPS]
    return config


def _hosted_models() -> list[dict[str, Any]]:
    """Return the `model_list` entries of the hosted groups, in configuration order."""
    return [m for m in _full_gateway_config()["model_list"] if m["model_name"] in HOSTED_GROUPS]


def _rendered_gateway(directory: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    """Return the gateway Deployment and the ConfigMap its config volume names, as
    `kubectl apply -k <directory>` applies them; the ConfigMap is empty when none has that name."""
    documents = [doc for doc in yaml.safe_load_all(kustomize(directory).stdout) if doc]
    deployment = next(
        doc
        for doc in documents
        if doc["kind"] == "Deployment" and doc["metadata"]["name"] == "llm-gateway"
    )
    volumes = {v["name"]: v for v in deployment["spec"]["template"]["spec"]["volumes"]}
    configmaps = {doc["metadata"]["name"]: doc for doc in documents if doc["kind"] == "ConfigMap"}
    return deployment, configmaps.get(volumes["config-volume"]["configMap"]["name"], {})


def _deployments(group: str) -> list[dict[str, Any]]:
    """Return the gateway deployments of one model group, in configuration order."""
    return [m for m in _gateway_config()["model_list"] if m["model_name"] == group]


def _gateway_embedding_groups() -> set[str]:
    """Return the model groups the gateway ConfigMap serves as embeddings."""
    return {
        m["model_name"]
        for m in _gateway_config()["model_list"]
        if m.get("model_info", {}).get("mode") == "embedding"
    }


def _job_configmap_embedding_models() -> set[str]:
    """Return the embedding model the example ConfigMap of the in-cluster jobs sets."""
    configmap = _load_kind(DEVOPS_CONFIGMAP_EXAMPLE, "ConfigMap")
    settings = yaml.safe_load(configmap["data"]["devops-cli.yaml"])
    return {_at(settings, "ai", "tasks", "embedding", "model")}


def _default_route_embedding_models() -> set[str]:
    """Return the target model of the `devops-embedding` default gateway route."""
    return {
        route["target_model"]
        for route in DEFAULT_GATEWAY_ROUTES
        if route["virtual_model"] == "devops-embedding"
    }


def _gpu_matrix_embedding_models() -> set[str]:
    """Return the embedding groups that the GPU matrix lists as gateway routes."""
    return {
        entry["model_name"]
        for entry in get_gateway_routing_entries()
        if entry.get("model_info", {}).get("mode") == "embedding"
    }


def _open_webui_env() -> dict[str, Any]:
    """Return each extra environment variable of Open WebUI: its value, or its `valueFrom`."""
    values = yaml.safe_load(OPEN_WEBUI_VALUES.read_text(encoding="utf-8"))
    return {
        variable["name"]: variable.get("value", variable.get("valueFrom"))
        for variable in values["extraEnvVars"]
    }


def _open_webui_embedding_models() -> set[str]:
    """Return the embedding model that Open WebUI's RAG asks the gateway for."""
    return {_open_webui_env()["RAG_EMBEDDING_MODEL"]}


def _gateway_providers() -> set[str]:
    """Return the LiteLLM providers the gateway ConfigMap's backends name (`ollama`, `ollama_chat`)."""
    return {m["litellm_params"]["model"].partition("/")[0] for m in _gateway_config()["model_list"]}


def _without_provider(model: str, providers: set[str]) -> str:
    """Return `model` without a leading provider (`ollama/qwen3-embedding:0.6b` is
    `qwen3-embedding:0.6b`)."""
    provider, _, rest = model.partition("/")
    return rest if provider in providers else model


def _gateway_served_models() -> set[str]:
    """Return the models the gateway ConfigMap names: each group and each backend's model."""
    entries, providers = _gateway_config()["model_list"], _gateway_providers()
    return {m["model_name"] for m in entries} | {
        _without_provider(m["litellm_params"]["model"], providers) for m in entries
    }


def _at(node: Any, *keys: str) -> Any:
    """Return the value under `keys` in nested mappings, or None where a level is absent, empty
    or not a mapping."""
    return reduce(
        lambda level, key: level.get(key) if isinstance(level, dict) else None, keys, node
    )


def _yaml_documents(readme: Path) -> list[dict[str, Any]]:
    """Return every mapping document in the README's YAML fences; an empty fence or a document
    that is no mapping adds none."""
    return [
        document
        for fence in fences(readme, YAML_FENCE_LANGUAGES)
        for document in yaml.safe_load_all(fence.text)
        if isinstance(document, dict)
    ]


def _configured_models(document: dict[str, Any], providers: set[str]) -> list[str]:
    """Return the models a YAML document sets: each `model_list` entry's group and backend model,
    and the model of `ai.tasks.embedding`."""
    entries = _at(document, "model_list")
    named = [
        _at(entry, *path)
        for entry in (entries if isinstance(entries, list) else [])
        for path in (("model_name",), ("litellm_params", "model"))
    ] + [_at(document, "ai", "tasks", "embedding", "model")]
    return [_without_provider(model, providers) for model in named if isinstance(model, str)]


def _is_model_reference(span: str) -> bool:
    """Whether a code span is one word that Docker's reference convention, which Ollama's model
    references follow, splits into a name and a tag (`qwen3-embedding:0.6b`)."""
    return len(span.split()) == 1 and bool(parse_repository_tag(span)[1])


def _gateway_sections(readme: Path) -> list[range]:
    """Return the lines of each section whose heading names the gateway, through to the next
    heading at its level or above."""
    found = headings(readme)
    return [
        range(
            heading.line,
            next((h.line for h in found[i + 1 :] if h.level <= heading.level), sys.maxsize),
        )
        for i, heading in enumerate(found)
        if "gateway" in heading.text.lower()
    ]


def _gateway_section_models(readme: Path, providers: set[str]) -> list[str]:
    """Return the model references in the inline code spans of the README's gateway sections."""
    sections = _gateway_sections(readme)
    return [
        _without_provider(span.text, providers)
        for span in code_snippets(readme)
        if not span.fenced
        and any(span.line in section for section in sections)
        and _is_model_reference(span.text)
    ]


def _gateway_readme_findings(readme: Path) -> tuple[list[str], list[str]]:
    """Return the models the README names for the gateway that the ConfigMap does not name, and
    the ConfigMap's embedding groups the README does not name.

    A README names a model in a YAML fence, as a `model_list` entry or the embedding task's
    model, or in an inline code span of a section whose heading names the gateway.
    """
    providers = _gateway_providers()
    named = set(
        chain(
            _gateway_section_models(readme, providers),
            *(_configured_models(d, providers) for d in _yaml_documents(readme)),
        )
    )
    return sorted(named - _gateway_served_models()), sorted(_gateway_embedding_groups() - named)


def _gateway_readme(body: str, *, names_embedding_model: bool = True) -> str:
    """Return a README whose gateway section holds `body`, after a sentence naming the embedding
    model unless `names_embedding_model` is False, and whose next section names an image."""
    served = "The embedding model is `qwen3-embedding:0.6b`.\n\n" if names_embedding_model else ""
    return (
        f"# Cluster\n\n## LLM Gateway\n\n{served}{body}\n\n"
        "## GitOps\n\nThe image is `service:latest`.\n"
    )


def _routes(deployments: list[dict[str, Any]]) -> list[tuple[str, str, int | None]]:
    """Return each deployment's model, backend and weight, in configuration order."""
    return [
        (
            m["litellm_params"]["model"],
            m["litellm_params"]["api_base"],
            m["litellm_params"].get("weight"),
        )
        for m in deployments
    ]


def _kustomized_files(directory: Path) -> set[Path]:
    """Return the files `kubectl apply -k` applies from a kustomization, following directories.

    A file a ConfigMap generator reads counts: the ConfigMap holds it.
    """
    kustomization = yaml.safe_load((directory / "kustomization.yaml").read_text(encoding="utf-8"))
    entries = [directory / entry for entry in kustomization.get("resources", [])]
    generated = {
        directory / file
        for generator in kustomization.get("configMapGenerator", [])
        for file in generator.get("files", [])
    }
    return (
        {entry for entry in entries if not entry.is_dir()}
        | generated
        | {path for entry in entries if entry.is_dir() for path in _kustomized_files(entry)}
    )


def _mounts(container: dict[str, Any]) -> dict[str, str]:
    """Return a container's volume mounts as {mountPath: volume name}."""
    return {mount["mountPath"]: mount["name"] for mount in container.get("volumeMounts", [])}


def _ollama_privileges(pod: dict[str, Any]) -> tuple[Any, ...]:
    """Return who an ollama tier's pod runs as and where it may write.

    In order: the pod and `ollama` container security contexts, HOME and OLLAMA_MODELS, the
    container's mounts, the pod's volumes, and each initContainer as (name, runs the `ollama`
    image, command, security context, mounts).
    """
    ollama = next(c for c in pod.get("containers", []) if c.get("name") == "ollama")
    env = {var["name"]: var.get("value") for var in ollama.get("env", [])}
    return (
        pod.get("securityContext"),
        ollama.get("securityContext"),
        (env.get("HOME"), env.get("OLLAMA_MODELS")),
        _mounts(ollama),
        {
            volume["name"]: {key: value for key, value in volume.items() if key != "name"}
            for volume in pod.get("volumes", [])
        },
        [
            (
                init.get("name"),
                init.get("image") == ollama.get("image"),
                init.get("command"),
                init.get("securityContext"),
                _mounts(init),
            )
            for init in pod.get("initContainers", [])
        ],
    )


class TestK8sLLMGatewayManifests:
    """Validate Kubernetes manifests and zero-trust policies for LiteLLM Gateway."""

    def test_gateway_deployment_security_and_resources(self) -> None:
        """Verify Gateway deployment enforces non-root execution and burstable QoS."""
        dep_path = GATEWAY_DIR / "deployment.yaml"
        docs = list(yaml.safe_load_all(dep_path.read_text(encoding="utf-8")))
        dep = next(d for d in docs if d and d.get("kind") == "Deployment")

        spec = dep["spec"]["template"]["spec"]
        container = spec["containers"][0]

        assert (
            dep["metadata"]["namespace"],
            spec["securityContext"]["runAsNonRoot"],
            spec["securityContext"]["runAsUser"],
            container["ports"][0]["containerPort"],
            container["resources"]["requests"]["cpu"],
            container["resources"]["limits"]["cpu"],
        ) == (
            "llm",
            True,
            1000,
            4000,
            "200m",
            "1000m",
        )

    def test_gateway_configmap_virtual_models(self) -> None:
        """Verify Gateway ConfigMap defines all virtual model aliases and routing rules."""
        cfg = _gateway_config()
        models = list(dict.fromkeys(m["model_name"] for m in cfg["model_list"]))

        assert (
            models,
            cfg["router_settings"]["routing_strategy"],
            cfg["router_settings"]["fallbacks"],
        ) == (
            [
                "devops-chat",
                "devops-coder",
                "devops-reasoning",
                "qwen3-embedding:0.6b",
                "devops-background",
                "devops-triage",
                "devops-review",
                "qwen3-coder:30b",
                "gpt-oss:20b",
                "gemma4:31b",
                "qwen3.8:27b",
                "deepseek-r1:70b",
            ],
            "least-busy",
            [
                {"devops-reasoning": ["devops-coder"]},
                {"devops-coder": ["devops-reasoning", "devops-chat"]},
                {"devops-review": ["devops-background"]},
                {"devops-triage": ["qwen3.8:27b"]},
                {"devops-background": ["qwen3.8:27b"]},
            ],
        )

    def test_gateway_configmap_routes_coder_and_reasoning(self) -> None:
        """Verify reasoning and coder aliases reach target Ollama profiles."""
        cfg = _gateway_config()
        params = {m["model_name"]: m["litellm_params"] for m in cfg["model_list"]}

        assert (
            params["devops-reasoning"]["model"],
            params["devops-reasoning"]["api_base"],
            params["devops-coder"]["model"],
            params["devops-coder"]["api_base"],
        ) == (
            "ollama_chat/qwen3-coder:30b",
            "http://ollama-48gib-fast.llm.svc.cluster.local:11434",
            "ollama_chat/qwen3-coder:30b",
            "http://ollama-48gib-fast.llm.svc.cluster.local:11434",
        )

    def test_gateway_checks_windows_and_has_no_useless_window_fallback(self) -> None:
        """Verify the router checks each prompt against the window of each deployment, and that no
        rule escalates a long prompt to a group that has no larger window (#2825).

        `ollama-48gib-fast` holds the largest window, 262144. `devops-coder` and
        `devops-reasoning` run on it, so a prompt that no `devops-chat` deployment holds does not
        fit them either."""
        router = _gateway_config()["router_settings"]

        assert (
            router["enable_pre_call_checks"],
            "context_window_fallbacks" in router,
            next(f for f in router["fallbacks"] if "devops-coder" in f),
        ) == (
            True,
            False,
            {"devops-coder": ["devops-reasoning", "devops-chat"]},
        )

    def test_each_chat_deployment_declares_the_window_of_its_tier(self) -> None:
        """Verify each `ollama_chat` deployment sets `max_input_tokens` in its top-level
        `model_info`, equal to the context length of its tier, and none hides a `model_info`
        inside `litellm_params` (#2825).

        LiteLLM v1.103.0 resolves the window of a deployment from its top-level `model_info`
        and ignores a key under `litellm_params`, so the pre-call check never ran. A deployment
        that sets no window reads the cost-map entry of its backend model, which the last
        deployment registered wrote: `devops-background` read 160000 for a 128000 tier."""
        tiers = load_tier_context_lengths(OLLAMA_PROFILES_MANIFEST)
        services = load_service_context_lengths(SERVICES_MANIFEST, tiers)
        chat = [
            m
            for m in _gateway_config()["model_list"]
            if m["litellm_params"]["model"].startswith("ollama_chat/")
        ]
        windows = {
            (m["model_name"], m["litellm_params"]["api_base"]): (m.get("model_info") or {}).get(
                "max_input_tokens"
            )
            for m in chat
        }
        tier_windows = {
            (m["model_name"], m["litellm_params"]["api_base"]): services[
                urlsplit(m["litellm_params"]["api_base"]).hostname.split(".")[0]
            ]
            for m in chat
        }
        misplaced = [
            (m["model_name"], m["litellm_params"]["api_base"])
            for m in _gateway_config()["model_list"]
            if "model_info" in m["litellm_params"]
        ]

        assert (windows, misplaced) == (tier_windows, [])

    def test_gateway_review_pool_spans_ollama_backends(self) -> None:
        """Verify devops-review shares requests across Ollama backends with zero retries and no weights."""
        deployments = _deployments("devops-review")
        weights = {
            m["litellm_params"]["api_base"]: m["litellm_params"].get("weight") for m in deployments
        }
        retries = [m["litellm_params"].get("num_retries") for m in deployments]
        assert (
            weights,
            retries,
        ) == (
            {
                "http://ollama-48gib-fast.llm.svc.cluster.local:11434": None,
                "http://ollama-64gib-standard.llm.svc.cluster.local:11434": None,
                "http://ollama-16gib-fast.llm.svc.cluster.local:11434": None,
            },
            [0, 0, 0],
        )

    @pytest.mark.parametrize("group", ["qwen3-coder:30b", "gpt-oss:20b"])
    def test_a_review_model_has_a_group_of_its_review_deployments_alone(self, group: str) -> None:
        """Verify each model devops-review serves can be pinned: its own group copies that model's
        devops-review deployments (model, backend and window, in order), so the pre-call check
        routes a pinned review as the pool routes it, and no fallback reaches or leaves it (#475)."""
        backend = f"ollama_chat/{group}"
        review = [
            m for m in _deployments("devops-review") if m["litellm_params"]["model"] == backend
        ]
        pinned = _deployments(group)
        router = _gateway_config()["router_settings"]
        fallback_groups = {
            name
            for rule in router["fallbacks"]
            for source, targets in rule.items()
            for name in (source, *targets)
        }

        assert (
            bool(review),
            _routes(pinned),
            [(sorted(m), sorted(m["litellm_params"])) for m in pinned],
            [(m.get("model_info") or {}).get("max_input_tokens") for m in pinned],
            group in fallback_groups,
        ) == (
            True,
            _routes(review),
            [(["litellm_params", "model_info", "model_name"], ["api_base", "model", "num_retries"])]
            * len(review),
            [(m.get("model_info") or {}).get("max_input_tokens") for m in review],
            False,
        )

    def test_gateway_routes_to_provider_vram_services(self) -> None:
        """Verify Gateway routes target standardized <llm_provider>-<vram_gib> services."""
        chat_deployments = _deployments("devops-chat")
        embedding_deployments = _deployments("qwen3-embedding:0.6b")

        assert (
            sorted(m["litellm_params"]["api_base"] for m in chat_deployments),
            sorted(
                (m["litellm_params"]["order"], m["litellm_params"]["api_base"])
                for m in embedding_deployments
            ),
            {m.get("model_info", {}).get("mode") for m in embedding_deployments},
        ) == (
            [
                "http://ollama-48gib-fast.llm.svc.cluster.local:11434",
                "http://ollama-64gib-standard.llm.svc.cluster.local:11434",
            ],
            [
                (1, "http://ollama-48gib-fast.llm.svc.cluster.local:11434"),
                (1, "http://ollama-64gib-standard.llm.svc.cluster.local:11434"),
                (2, "http://ollama-16gib-fast.llm.svc.cluster.local:11434"),
                (2, "http://ollama-48gib-slow.llm.svc.cluster.local:11434"),
            ],
            {"embedding"},
        )

    def test_qwen_and_chat_groups_exclude_16gib_tier(self) -> None:
        """Verify qwen3.8:27b and devops-chat exclude the 16gib tier and IQ3_S model (#2368).

        The 16gib tier lacks sufficient VRAM for 27B parameters with 48k context, causing heavy
        CPU offloading and high latency. Furthermore, the GGUF IQ3_S chat template fails on
        requests without a user query, returning HTTP 500 on multi-turn tool interaction requests.
        Both groups route only to tiers with at least 48 GiB of VRAM."""
        chat_deployments = _deployments("devops-chat")
        qwen_deployments = _deployments("qwen3.8:27b")

        assert (
            [m["litellm_params"]["model"] for m in chat_deployments],
            [m["litellm_params"]["api_base"] for m in chat_deployments],
            [m["litellm_params"]["model"] for m in qwen_deployments],
            [m["litellm_params"]["api_base"] for m in qwen_deployments],
        ) == (
            [
                "ollama_chat/qwen3.8:27b",
                "ollama_chat/qwen3.8:27b",
            ],
            [
                "http://ollama-48gib-fast.llm.svc.cluster.local:11434",
                "http://ollama-64gib-standard.llm.svc.cluster.local:11434",
            ],
            [
                "ollama_chat/qwen3.8:27b",
                "ollama_chat/qwen3.8:27b",
            ],
            [
                "http://ollama-48gib-fast.llm.svc.cluster.local:11434",
                "http://ollama-64gib-standard.llm.svc.cluster.local:11434",
            ],
        )

    def test_every_embedding_deployment_holds_the_largest_rag_chunk(self) -> None:
        """Verify Ollama loads the embedder with a context that holds a whole RAG chunk (#1987).

        Without `num_ctx`, Ollama loads it with the model's 32,768 tokens and up to 1.8 times the
        VRAM, so it fits beside fewer chat models. A smaller context would cut the largest chunks.
        """
        contexts = [
            m["litellm_params"].get("num_ctx")
            for group in sorted(_gateway_embedding_groups())
            for m in _deployments(group)
        ]

        assert contexts == [CONST_RAG_MAX_CHUNK_TOKENS] * len(contexts)

    def test_embedding_group_spreads_batches_over_order_1_tiers(self) -> None:
        """Verify Gateway ConfigMap configures simple-shuffle routing for the embedding group (#2027).

        Under least-busy, zero-in-flight ties select the first deployment every time.
        A routing group with simple-shuffle spreads sequential and parallel embedding batches
        over both order 1 deployments.
        """
        cfg = _gateway_config()
        routing_groups = cfg["router_settings"].get("routing_groups", [])
        embedding_group = next(
            (g for g in routing_groups if g.get("group_name") == "embedding"), None
        )
        assert embedding_group is not None
        assert embedding_group["models"] == ["qwen3-embedding:0.6b"]
        assert embedding_group["routing_strategy"] == "simple-shuffle"

    @pytest.mark.parametrize(
        "embedding_models",
        [
            pytest.param(_job_configmap_embedding_models, id="the-example-configmap-of-the-jobs"),
            pytest.param(_default_route_embedding_models, id="the-default-gateway-routes"),
            pytest.param(_gpu_matrix_embedding_models, id="the-gpu-matrix-gateway-routes"),
            pytest.param(_open_webui_embedding_models, id="the-open-webui-rag-embedding"),
        ],
    )
    def test_every_registry_that_names_an_embedding_model_names_a_group_the_gateway_serves(
        self, embedding_models: Callable[[], set[str]]
    ) -> None:
        """Verify the embedding model that each of four places names is an embedding group of
        the gateway ConfigMap: the example ConfigMap of the in-cluster jobs, the default
        gateway routes, the GPU matrix routes and Open WebUI's RAG. A place that falls behind a
        renamed group sends its requests to a model the gateway refuses (#481, #1637)."""
        named = embedding_models()

        assert (bool(named), named - _gateway_embedding_groups()) == (True, set())

    def test_the_slow_tier_serves_embeddings_and_devops_background_alone(self) -> None:
        """Verify ollama-48gib-slow is in no interactive or review pool: every generation
        deployment on it belongs to devops-background, which has that one deployment alone, so
        the tier never loads a third model beside its embedder and qwen3.8:27b (#1064, #1221)."""
        slow = "http://ollama-48gib-slow.llm.svc.cluster.local:11434"
        slow_generation_groups = [
            m["model_name"]
            for m in _gateway_config()["model_list"]
            if m["litellm_params"]["api_base"] == slow
            and m.get("model_info", {}).get("mode") != "embedding"
        ]

        assert (
            slow_generation_groups,
            _routes(_deployments("devops-background")),
        ) == (
            ["devops-background"],
            [("ollama_chat/qwen3.8:27b", slow, None)],
        )

    def test_devops_triage_serves_qwen_on_standard_tier(self) -> None:
        """Verify devops-triage has exactly one deployment: ollama_chat/qwen3.8:27b on
        ollama-64gib-standard."""
        standard = "http://ollama-64gib-standard.llm.svc.cluster.local:11434"
        assert _routes(_deployments("devops-triage")) == [
            ("ollama_chat/qwen3.8:27b", standard, None)
        ]

    @pytest.mark.parametrize("readme", GATEWAY_READMES, ids=str)
    def test_a_gateway_readme_names_exactly_the_embedding_groups_the_gateway_serves(
        self, readme: Path
    ) -> None:
        """Verify every model a README names for the gateway, in a YAML fence or in a gateway
        section's code spans, is one the ConfigMap names, and every embedding group the ConfigMap
        serves is named: one a README names but the gateway dropped fails the embedding task with
        HTTP 400, which turns RAG off for the run (#481, #1064). The README must have a gateway
        section, or the code spans would go unread."""
        assert (_gateway_readme_findings(readme), bool(_gateway_sections(readme))) == (
            ([], []),
            True,
        )

    @pytest.mark.parametrize(
        ("readme_text", "unserved", "missing"),
        [
            pytest.param(
                _gateway_readme(
                    "Also `ollama/qwen3-embedding:0.6b`, `ollama_chat/qwen3-coder:30b`, `qwen3.8:27b`,"
                    " `deepseek-r1:70b`, `model_info.mode: embedding`"
                    " and `devops-review`."
                ),
                [],
                [],
                id="every-spelling-the-gateway-serves",
            ),
            pytest.param(
                _gateway_readme("A stale option is `mxbai-embed-large:latest`."),
                ["mxbai-embed-large:latest"],
                [],
                id="an-embedding-model-no-table-sizes",
            ),
            pytest.param(
                _gateway_readme("Or `ollama/embeddinggemma:300m`."),
                ["embeddinggemma:300m"],
                [],
                id="a-provider-prefixed-span",
            ),
            pytest.param(
                _gateway_readme(
                    "- Models: `qwen3.8:27b`\n- Embeddings: `qwen3-embedding:0.6b`, `embeddinggemma:300m`"
                ),
                ["embeddinggemma:300m"],
                [],
                id="a-list-item",
            ),
            pytest.param(
                _gateway_readme("### Detail\n\nTry `mxbai-embed-large:latest`."),
                ["mxbai-embed-large:latest"],
                [],
                id="a-subsection-of-the-gateway-section",
            ),
            pytest.param(
                _gateway_readme(
                    "```yml title=config\nai:\n  tasks:\n    embedding:\n"
                    "      model: embeddinggemma:300m\n```"
                ),
                ["embeddinggemma:300m"],
                [],
                id="a-yml-fence-with-an-info-string",
            ),
            pytest.param(
                _gateway_readme(
                    "```yaml\nkind: ConfigMap\n---\nai:\n  tasks:\n    embedding:\n"
                    "      model: embeddinggemma:300m\n```"
                ),
                ["embeddinggemma:300m"],
                [],
                id="the-second-document-of-a-fence",
            ),
            pytest.param(
                _gateway_readme(
                    "```yaml\nmodel_list:\n  - model_name: embeddinggemma:300m\n"
                    "    litellm_params:\n      model: ollama/embeddinggemma:300m\n```"
                ),
                ["embeddinggemma:300m"],
                [],
                id="a-model-list-entry",
            ),
            pytest.param(
                _gateway_readme(
                    "```yaml\n```\n\n```yaml\nai:\n  tasks:\n    embedding:\n```"
                    "\n\n```yaml\n- a\n- b\n```\n\n```yaml\nai: text\nmodel_list: text\n```"
                ),
                [],
                [],
                id="an-empty-fence-a-valueless-key-and-documents-that-are-no-mapping",
            ),
            pytest.param(
                _gateway_readme("Chat models only: `qwen3.8:27b`.", names_embedding_model=False),
                [],
                ["qwen3-embedding:0.6b"],
                id="a-readme-that-drops-the-embedding-group",
            ),
        ],
    )
    def test_the_readme_guard_finds_a_stale_model_wherever_a_gateway_section_names_it(
        self, tmp_path: Path, readme_text: str, unserved: list[str], missing: list[str]
    ) -> None:
        """Verify the guard reads a model the ConfigMap lacks from a code span, a list item, a
        subsection and every `yaml` or `yml` fence document, whether or not the RAG embedder has a
        dimension for it, and reads nothing from a section whose heading does not name the gateway
        (each README names `service:latest` there, an image rather than a model)."""
        readme = tmp_path / "README.md"
        readme.write_text(readme_text, encoding="utf-8")
        assert _gateway_readme_findings(readme) == (unserved, missing)

    def test_devops_background_frees_its_slot_before_the_review_client_gives_up(self) -> None:
        """Verify the gateway abandons a devops-background call before the review client's read
        timeout and never retries it: the slow tier serves one request at a time, so a call the
        client has given up on, or a gateway retry, would hold the slot in front of new work
        (#1064)."""
        (background,) = _deployments("devops-background")
        params = background["litellm_params"]

        assert (params["timeout"] < DEFAULT_REVIEW_TIMEOUT_SECONDS, params["num_retries"]) == (
            True,
            0,
        )

    def test_gateway_service_and_network_policy(self) -> None:
        """Verify Gateway Service and zero-trust NetworkPolicy perimeters."""
        svc_docs = list(
            yaml.safe_load_all((GATEWAY_DIR / "service.yaml").read_text(encoding="utf-8"))
        )
        svc = next(d for d in svc_docs if d and d.get("kind") == "Service")

        netpol_docs = list(
            yaml.safe_load_all((GATEWAY_DIR / "networkpolicy.yaml").read_text(encoding="utf-8"))
        )
        netpol = next(d for d in netpol_docs if d and d.get("kind") == "NetworkPolicy")

        ingress = netpol["spec"]["ingress"]
        assert (
            svc["spec"]["type"],
            svc["spec"]["ports"][0]["port"],
            "nodePort" in svc["spec"]["ports"][0],
            netpol["metadata"]["name"],
            netpol["spec"]["podSelector"]["matchLabels"]["app.kubernetes.io/name"],
            [(rule.get("from"), [p["port"] for p in rule["ports"]]) for rule in ingress],
        ) == (
            "NodePort",
            4000,
            False,
            "llm-gateway-perimeter",
            "llm-gateway",
            [(None, [4000])],
        )

    def test_gateway_deployment_pins_litellm_and_reads_master_key_from_secret(self) -> None:
        """Verify the gateway runs a pinned LiteLLM release and never embeds its master key."""
        dep = _load_kind(GATEWAY_DIR / "deployment.yaml", "Deployment")
        container = dep["spec"]["template"]["spec"]["containers"][0]
        env = {e["name"]: e for e in container["env"]}
        master_key = env["LITELLM_MASTER_KEY"]

        assert (
            container["image"],
            "value" in master_key,
            master_key["valueFrom"]["secretKeyRef"]["name"],
            master_key["valueFrom"]["secretKeyRef"]["key"],
        ) == (
            GATEWAY_IMAGE,
            False,
            GATEWAY_SECRET,
            GATEWAY_SECRET_KEY,
        )

    def test_gateway_configmap_enforces_master_key_and_long_generations(self) -> None:
        """Verify the gateway requires its master key and allows long code-review generations."""
        cfg = _gateway_config()

        assert (
            cfg["general_settings"]["master_key"],
            cfg["general_settings"]["cancel_on_disconnect"],
            cfg["router_settings"]["timeout"] >= 600,
        ) == (
            "os.environ/LITELLM_MASTER_KEY",
            True,
            True,
        )

    def test_the_gateway_names_each_callers_end_user_id_on_its_metrics(self) -> None:
        """LiteLLM puts the end-user id that a request names, as the `x-litellm-end-user-id`
        header that devops-cli sends, on its request and token series only when this setting is
        true, so the AI spend dashboard can split the gateway's traffic by caller (#1668)."""
        assert (
            _gateway_config()["litellm_settings"].get(
                "enable_end_user_cost_tracking_prometheus_only"
            )
            is True
        )

    def test_open_webui_values_connect_to_gateway(self) -> None:
        """Verify Open WebUI uses the gateway as its OpenAI connection and for its RAG
        embeddings, both with the shared master key, and has no connection to Ollama's native
        API, so each of its model calls is on the gateway's series (#1668).

        Open WebUI sets no RAG Ollama URL, so its default is `localhost`, where its pod runs no
        Ollama, and its RAG API key defaults to none (#1637)."""
        values = yaml.safe_load(OPEN_WEBUI_VALUES.read_text(encoding="utf-8"))
        env = _open_webui_env()

        assert (
            values["enableOpenaiApi"],
            values["openaiBaseApiUrl"],
            values["openaiApiKeyExistingSecret"],
            values["openaiApiKeyExistingSecretKey"],
            values.get("ollamaUrls"),
            env["RAG_EMBEDDING_ENGINE"],
            env["RAG_OPENAI_API_BASE_URL"],
            env["RAG_OPENAI_API_KEY"],
        ) == (
            True,
            DEFAULT_AI_GATEWAY_CLUSTER_URL,
            GATEWAY_SECRET,
            GATEWAY_SECRET_KEY,
            None,
            "openai",
            DEFAULT_AI_GATEWAY_CLUSTER_URL,
            {"secretKeyRef": {"name": GATEWAY_SECRET, "key": GATEWAY_SECRET_KEY}},
        )

    def test_ollama_profiles_define_standard_vram_tiers(self) -> None:
        """Verify ollama-profiles defines the 8 standard VRAM tiers with nvidia runtime and persistent data."""
        docs = list(yaml.safe_load_all(OLLAMA_PROFILES_MANIFEST.read_text(encoding="utf-8")))
        daemonsets = [d for d in docs if d and d.get("kind") == "DaemonSet"]
        dep_names = [d["metadata"]["name"] for d in daemonsets]
        expected_names = [
            "ollama-16gib",
            "ollama-24gib",
            "ollama-32gib",
            "ollama-48gib",
            "ollama-48gib-slow",
            "ollama-64gib",
            "ollama-72gib",
            "ollama-96gib",
            "ollama-128gib",
        ]
        assert (
            dep_names,
            all(d["spec"]["template"]["spec"]["runtimeClassName"] == "nvidia" for d in daemonsets),
            all(
                any(v["name"] == "ollama-data" for v in d["spec"]["template"]["spec"]["volumes"])
                for d in daemonsets
            ),
        ) == (
            expected_names,
            True,
            True,
        )

    def test_every_ollama_tier_serves_one_request_and_keeps_the_embedder_beside_its_model(
        self,
    ) -> None:
        """Verify each tier reserves KV cache for one context: Ollama sizes it by NUM_PARALLEL (#1061).

        A tier the gateway sends embeddings to keeps two models loaded, so the embedder does not
        evict the chat model where both fit (#1987). Every other tier keeps one. The slow tier
        also keeps its two models loaded for good, so neither evicts the other (#1064).
        """
        docs = list(yaml.safe_load_all(OLLAMA_PROFILES_MANIFEST.read_text(encoding="utf-8")))
        settings = {
            d["metadata"]["name"]: {
                var["name"]: var.get("value")
                for container in d["spec"]["template"]["spec"]["containers"]
                for var in container.get("env", [])
                if var["name"]
                in ("OLLAMA_MAX_LOADED_MODELS", "OLLAMA_NUM_PARALLEL", "OLLAMA_KEEP_ALIVE")
            }
            for d in docs
            if d and d.get("kind") == "DaemonSet"
        }
        embedding_tiers = _embedding_tiers()
        expected = {
            name: {
                "OLLAMA_MAX_LOADED_MODELS": "2" if name in embedding_tiers else "1",
                "OLLAMA_NUM_PARALLEL": "1",
            }
            for name in settings
        }
        expected["ollama-48gib-slow"]["OLLAMA_KEEP_ALIVE"] = "-1"

        assert settings == expected

    def test_every_ollama_tier_runs_unprivileged(self) -> None:
        """Verify every tier runs ollama as one non-root UID with no privilege to gain (#1060).

        The one root step is the `own-model-directory` initContainer: fsGroup does not reach a
        hostPath volume, so it hands the model directory to that UID holding CAP_CHOWN alone.
        HOME keeps the key and models on the same hostPath, so nothing is downloaded again. The
        initContainer runs the ollama image, so a tag bump cannot leave two images on a node.
        """
        docs = yaml.safe_load_all(OLLAMA_PROFILES_MANIFEST.read_text(encoding="utf-8"))
        observed = {
            d["metadata"]["name"]: _ollama_privileges(d["spec"]["template"]["spec"])
            for d in docs
            if d and d.get("kind") == "DaemonSet"
        }
        expected = (
            {
                "runAsNonRoot": True,
                "runAsUser": OLLAMA_UID,
                "runAsGroup": OLLAMA_UID,
                "seccompProfile": {"type": "RuntimeDefault"},
            },
            {
                "allowPrivilegeEscalation": False,
                "readOnlyRootFilesystem": True,
                "capabilities": {"drop": ["ALL"]},
            },
            ("/home/ollama", "/home/ollama/.ollama/models"),
            {
                "/home/ollama/.ollama": "ollama-data",
                "/tmp": "tmp",  # nosec B108  # the pod's emptyDir mount path, under test
            },
            {
                "ollama-data": {
                    "hostPath": {"path": "/var/lib/ollama", "type": "DirectoryOrCreate"}
                },
                "tmp": {"emptyDir": {}},
            },
            [
                (
                    "own-model-directory",
                    True,
                    ["chown", "-R", f"{OLLAMA_UID}:{OLLAMA_UID}", "/home/ollama/.ollama"],
                    {
                        "runAsUser": 0,
                        "runAsNonRoot": False,
                        "allowPrivilegeEscalation": False,
                        "readOnlyRootFilesystem": True,
                        "capabilities": {"drop": ["ALL"], "add": ["CHOWN"]},
                    },
                    {"/home/ollama/.ollama": "ollama-data"},
                )
            ],
        )

        assert observed == {name: expected for name in observed}

    def test_ollama_64gib_tier_constrains_prompt_cache_and_memory_limit(self) -> None:
        """Verify the ollama-64gib tier sets a container memory limit and bounds prompt cache RAM (#2382).

        Node gemini has 15.3 GiB of memory. Under a 160000 context length, the default prompt cache
        can exhaust host memory and cause OOM kills. Setting LLAMA_ARG_CACHE_RAM to 4096 MiB bounds
        prompt cache size. Setting limits.memory to 12Gi protects the node from memory exhaustion.
        """
        dep = _load_deployment(OLLAMA_PROFILES_MANIFEST, "ollama-64gib")
        container = dep["spec"]["template"]["spec"]["containers"][0]
        env_vars = {v["name"]: v.get("value") for v in container.get("env", [])}
        resources = container.get("resources", {})

        assert (
            env_vars.get("LLAMA_ARG_CACHE_RAM"),
            resources.get("requests", {}).get("memory"),
            resources.get("limits", {}).get("memory"),
        ) == ("4096", "8Gi", "12Gi")

    @pytest.mark.parametrize("service_name", ["ollama-16gib", "ollama-48gib"])
    def test_ollama_services_stay_behind_the_gateway(self, service_name: str) -> None:
        """Verify Ollama Services are cluster-internal; LAN clients use the authenticated gateway."""
        svc = _load_service(SERVICES_MANIFEST, service_name)
        dep = _load_deployment(OLLAMA_PROFILES_MANIFEST, service_name)

        assert (
            svc["spec"]["type"],
            svc["spec"]["ports"][0]["port"],
            svc["spec"]["selector"]["llm.devops.io/provider"],
        ) == (
            "ClusterIP",
            11434,
            dep["spec"]["template"]["metadata"]["labels"]["llm.devops.io/provider"],
        )

    def test_llm_kustomization_includes_profiles(self) -> None:
        """Verify the llm kustomization includes the profiles package and all its resources."""
        resources = yaml.safe_load(LLM_KUSTOMIZATION.read_text(encoding="utf-8"))["resources"]
        profiles_kust = yaml.safe_load(
            (PROFILES_DIR / "kustomization.yaml").read_text(encoding="utf-8")
        )

        assert (
            "profiles" in resources,
            profiles_kust["resources"],
        ) == (
            True,
            [
                "services.yaml",
                "ollama-profiles.yaml",
            ],
        )

    def test_llm_namespace_default_perimeter_excludes_gateway_and_workloads(self) -> None:
        """Verify llm-default-perimeter excludes gateway, portkey and the three Valkeys
        to avoid additive policy leakage."""
        np_path = Path("k8s/llm/networkpolicy.yaml")
        docs = list(yaml.safe_load_all(np_path.read_text(encoding="utf-8")))
        np = next(d for d in docs if d and d.get("kind") == "NetworkPolicy")
        exprs = np["spec"]["podSelector"]["matchExpressions"]
        name_expr = next(e for e in exprs if e.get("key") == "app.kubernetes.io/name")

        assert (
            name_expr["operator"],
            sorted(name_expr["values"]),
        ) == (
            "NotIn",
            ["llm-gateway", "portkey", "valkey", "valkey-devops", "valkey-runs"],
        )

    def test_llm_manifests_have_a_deploy_path(self) -> None:
        """Verify every manifest under k8s/llm is applied by something (#953).

        A file counts when a k8s/llm kustomization lists it (a listed directory lists its
        files), when deploy-stack applies it (`_MANIFESTS_BY_STACK["llm"]`), or when it is the
        values file of an `llm` Helm release. `ollama-host-service.yaml` and `values-ollama.yaml`
        had none: nothing applied them once the Ollama tiers replaced the single `ollama` workload.
        """
        llm_dir = Path("k8s/llm")
        manifests = {path for path in llm_dir.rglob("*.yaml") if path.name != "kustomization.yaml"}
        applied = (
            {
                path
                for kustomization in llm_dir.rglob("kustomization.yaml")
                for path in _kustomized_files(kustomization.parent)
            }
            | set(_MANIFESTS_BY_STACK["llm"])
            | {Path(release["values"]) for release in _HELM_RELEASES_BY_STACK["llm"]}
        )

        assert sorted(manifests - applied) == []

    def test_zero_homelab_ip_or_hostname_leakage(self) -> None:
        """Verify no private RFC 1918 IPs or *.lan hostnames exist in any k8s/llm manifest."""
        all_yaml_files = sorted(Path("k8s/llm").rglob("*.yaml"))
        private_ip_pattern = re.compile(
            r"\b(192\.168\.\d{1,3}\.\d{1,3}|10\.\d{1,3}\.\d{1,3}\.\d{1,3}|172\.(1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3})\b(?!/)"
        )
        lan_hostname_pattern = re.compile(r"\b[a-zA-Z0-9_\-]+\.lan\b")

        for file_path in all_yaml_files:
            content = file_path.read_text(encoding="utf-8")
            ip_matches = private_ip_pattern.findall(content)
            lan_matches = lan_hostname_pattern.findall(content)
            assert (
                ip_matches,
                lan_matches,
            ) == (
                [],
                [],
            )

    def test_gateway_deployment_runs_without_proxy(self) -> None:
        """Verify gateway deployment does not configure HTTP_PROXY or NO_PROXY."""
        dep = _load_kind(GATEWAY_DIR / "deployment.yaml", "Deployment")
        container = dep["spec"]["template"]["spec"]["containers"][0]
        env = {e["name"]: e["value"] for e in container.get("env", []) if "value" in e}

        assert (
            "HTTP_PROXY" in env,
            "HTTPS_PROXY" in env,
            "NO_PROXY" in env,
        ) == (
            False,
            False,
            False,
        )

    def test_gateway_egress_admits_all_backends_in_configmap(self) -> None:
        """Verify the gateway policy admits every backend the gateway calls (#795).

        The backends are read from the ConfigMap: each `api_base`. Each must be a Service under
        k8s/llm with a selector, and some egress rule must select a subset of that selector on
        the Service's numeric targetPort. The test used to pin four selector names, two of which
        match no pod, and never read the ConfigMap.
        """
        policy = _load_kind(GATEWAY_DIR / "networkpolicy.yaml", "NetworkPolicy")
        backends = _gateway_backends()

        assert (
            sorted(address for address, target in backends.items() if target is None),
            sorted(
                address
                for address, target in backends.items()
                if target is not None and not _admits(policy, *target)
            ),
        ) == ([], [])


_DNS_PEER = {"namespaceSelector": {"matchLabels": {"kubernetes.io/metadata.name": "kube-system"}}}
_DNS_PORTS = frozenset({("UDP", 53, None), ("TCP", 53, None)})
_OLLAMA_PEER = {"podSelector": {"matchLabels": {"llm.devops.io/provider": "ollama"}}}
# The hosted groups call their providers over HTTPS. A NetworkPolicy cannot name a host, so the
# rule admits public addresses on 443: every private range and the metadata range stay out (#3113).
_HOSTED_PEER = {
    "ipBlock": {
        "cidr": "0.0.0.0/0",
        "except": [
            "10.0.0.0/8",
            "100.64.0.0/10",
            "169.254.0.0/16",
            "172.16.0.0/12",
            "192.168.0.0/16",
        ],
    }
}
_HOSTED_PORTS = frozenset({("TCP", 443, None)})

EgressPort = tuple[str, object, object]
BackendTarget = tuple[dict[str, str], int]


def _llm_services() -> dict[str, dict[str, Any]]:
    """Return every Service under k8s/llm by its cluster DNS name."""
    return {
        f"{doc['metadata']['name']}.{doc['metadata']['namespace']}.svc.cluster.local": doc
        for path in sorted(Path("k8s/llm").rglob("*.yaml"))
        for doc in yaml.load_all(path.read_text(encoding="utf-8"), Loader=yaml.CSafeLoader)
        if isinstance(doc, dict) and doc.get("kind") == "Service"
    }


def _service_target(service: dict[str, Any] | None, port: int | None) -> BackendTarget | None:
    """Return a Service's selector and the numeric targetPort behind `port`, if it has both."""
    if service is None:
        return None
    selector = service["spec"].get("selector")
    targets = [
        p.get("targetPort", p["port"]) for p in service["spec"]["ports"] if p["port"] == port
    ]
    return (selector, targets[0]) if selector and targets and isinstance(targets[0], int) else None


def _gateway_backends() -> dict[str, BackendTarget | None]:
    """Map each backend the gateway calls to its Service's selector and targetPort, or None.

    The backends are every `api_base` in the gateway ConfigMap. The config turns on no cache,
    so the gateway calls no Valkey (#1654). A backend maps to None unless its host names a
    Service under k8s/llm that has a selector and a numeric targetPort on the port it calls.
    """
    api_bases = {
        urlsplit(model["litellm_params"].get("api_base", ""))
        for model in _gateway_config()["model_list"]
    }
    addresses = {(url.hostname, url.port) for url in api_bases}
    services = _llm_services()
    return {
        f"{host}:{port}": _service_target(services.get(host or ""), port)
        for host, port in addresses
    }


def _ports(rule: dict[str, Any]) -> set[EgressPort]:
    """Return each (protocol, port, endPort) an egress rule admits."""
    return {
        (port.get("protocol", "TCP"), port.get("port"), port.get("endPort"))
        for port in rule.get("ports") or []
    }


def _pod_labels(peer: dict[str, Any]) -> dict[str, str]:
    """Return a same-namespace podSelector peer's matchLabels, or {} for any other peer."""
    selector = peer.get("podSelector")
    if set(peer) != {"podSelector"} or not isinstance(selector, dict):
        return {}
    return {} if "matchExpressions" in selector else dict(selector.get("matchLabels") or {})


def _admits(policy: dict[str, Any], selector: dict[str, str], target_port: int) -> bool:
    """Whether an egress rule selects a subset of `selector` on TCP `target_port`."""
    return any(
        ("TCP", target_port, None) in _ports(rule)
        and any(
            labels and labels.items() <= selector.items()
            for labels in map(_pod_labels, rule.get("to") or [])
        )
        for rule in policy["spec"].get("egress") or []
    )


def _peer_violation(
    peer: dict[str, Any], ports: set[EgressPort], backends: list[BackendTarget]
) -> str | None:
    """Return how a peer admits more than a backend or DNS on these ports, or None."""
    if peer == _DNS_PEER:
        return None if ports == _DNS_PORTS else f"the DNS peer admits {sorted(map(str, ports))}"
    if peer == _HOSTED_PEER:
        return (
            None if ports == _HOSTED_PORTS else f"the hosted peer admits {sorted(map(str, ports))}"
        )
    labels = _pod_labels(peer)
    if not labels:
        return f"{peer} is not a same-namespace podSelector with matchLabels alone"
    allowed = {
        ("TCP", target, None) for selector, target in backends if labels.items() <= selector.items()
    }
    if allowed and ports <= allowed:
        return None
    return f"{labels} on {sorted(map(str, ports))} is not a backend's selector and targetPort"


def _rule_violations(rule: dict[str, Any], backends: list[BackendTarget]) -> list[str]:
    """Return how one egress rule admits more than the gateway's backends and DNS."""
    peers, ports = rule.get("to") or [], _ports(rule)
    if not peers or not ports:
        return [f"{rule} admits every destination or every port"]
    return [
        problem for peer in peers if (problem := _peer_violation(peer, ports, backends)) is not None
    ]


def _egress_violations(
    policy: dict[str, Any], backends: list[BackendTarget], gateway_labels: dict[str, str]
) -> list[str]:
    """Return every way the gateway policy lets the gateway reach more than it needs (#795).

    The policy must select the gateway's pods and enforce Egress. Each rule needs a non-empty
    `to` and `ports`. A peer is the kube-system DNS peer on UDP and TCP 53, or a same-namespace
    podSelector whose labels are a subset of some backend Service's selector, on those
    backends' targetPorts alone, or the one public-address ipBlock on TCP 443 for the hosted
    models, with its private ranges excluded. No other ipBlock passes.
    """
    spec = policy["spec"]
    selected = (spec.get("podSelector") or {}).get("matchLabels") or {}
    return [
        *([] if selected and selected.items() <= gateway_labels.items() else ["not the gateway"]),
        *([] if "Egress" in spec.get("policyTypes", []) else ["Egress is not enforced"]),
        *(
            problem
            for rule in spec.get("egress") or []
            for problem in _rule_violations(rule, backends)
        ),
    ]


def _ollama_rule(spec: dict[str, Any]) -> dict[str, Any]:
    """Return the egress rule that admits the Ollama tiers."""
    return next(rule for rule in spec["egress"] if _OLLAMA_PEER in rule["to"])


def _hosted_rule(spec: dict[str, Any]) -> dict[str, Any]:
    """Return the egress rule that admits the hosted providers."""
    return next(rule for rule in spec["egress"] if _HOSTED_PEER in rule["to"])


@pytest.fixture(scope="module")
def gateway_egress() -> tuple[dict[str, Any], list[BackendTarget], dict[str, str]]:
    """Return the gateway policy, its resolved backends and the gateway's pod labels."""
    deployment = _load_kind(GATEWAY_DIR / "deployment.yaml", "Deployment")
    backends = [target for target in _gateway_backends().values() if target is not None]
    return (
        _load_kind(GATEWAY_DIR / "networkpolicy.yaml", "NetworkPolicy"),
        backends,
        deployment["spec"]["template"]["metadata"]["labels"],
    )


def test_gateway_egress_admits_nothing_else(
    gateway_egress: tuple[dict[str, Any], list[BackendTarget], dict[str, str]],
) -> None:
    """The gateway reaches its backends and DNS, and nothing else.

    The policy carried an ipBlock rule for every private address on 11434 and 8000, which
    kube-router matches against pod addresses, so every pod on those ports was reachable (#795).
    """
    assert _egress_violations(*gateway_egress) == []


@pytest.mark.parametrize(
    "widen",
    [
        pytest.param(
            lambda spec: spec["egress"].append(
                {
                    "to": [{"ipBlock": {"cidr": "192.0.2.0/24"}}],
                    "ports": [{"protocol": "TCP", "port": 11434}],
                }
            ),
            id="ip-block",
        ),
        pytest.param(
            lambda spec: _ollama_rule(spec)["to"].append({"podSelector": {}}), id="any-pod"
        ),
        pytest.param(
            lambda spec: _ollama_rule(spec)["to"].append(
                {"podSelector": {"matchLabels": {"app.kubernetes.io/name": "ollama"}}}
            ),
            id="selector-matching-no-backend",
        ),
        pytest.param(
            lambda spec: _ollama_rule(spec)["to"].append({"namespaceSelector": {}}),
            id="any-namespace",
        ),
        pytest.param(
            lambda spec: spec["egress"].append(
                {"to": [{"podSelector": {"matchLabels": {"app.kubernetes.io/name": "valkey"}}}]}
            ),
            id="rule-without-ports",
        ),
        pytest.param(
            lambda spec: _ollama_rule(spec)["ports"].append({"protocol": "TCP", "port": 6379}),
            id="valkey-port-on-the-ollama-rule",
        ),
        pytest.param(lambda spec: spec["policyTypes"].remove("Egress"), id="egress-not-enforced"),
        pytest.param(
            lambda spec: _hosted_rule(spec)["ports"].append({"protocol": "TCP", "port": 80}),
            id="hosted-rule-on-port-80",
        ),
        pytest.param(
            lambda spec: _hosted_rule(spec)["to"][0]["ipBlock"]["except"].pop(),
            id="hosted-rule-admits-a-private-range",
        ),
        pytest.param(
            lambda spec: _hosted_rule(spec)["to"][0]["ipBlock"].pop("except"),
            id="hosted-rule-without-exclusions",
        ),
        pytest.param(
            lambda spec: _hosted_rule(spec)["to"].append({"podSelector": {}}),
            id="any-pod-on-the-hosted-rule",
        ),
    ],
)
def test_each_widening_edit_is_a_violation(
    widen: Callable[[dict[str, Any]], None],
    gateway_egress: tuple[dict[str, Any], list[BackendTarget], dict[str, str]],
) -> None:
    """Each way back to a wider egress fails the check, the removed ipBlock rule first (#795).

    Any ipBlock is a violation, so a documentation range stands in for the private ones.
    """
    policy, backends, gateway_labels = gateway_egress
    widened = copy.deepcopy(policy)
    widen(widened["spec"])

    assert _egress_violations(widened, backends, gateway_labels) != []


# ── Every consumer of Ollama reaches a tier that has a pod (#1637) ─────────────────────────────


def _placement_tables() -> list[list[list[str]]]:
    """Return each table of the k8s README whose first column is Tier, which is the GPU placement
    table: its rows, the header first."""
    return [rows for rows in tables(K8S_README) if rows[0][:1] == ["Tier"]]


def _serving_tiers() -> set[str]:
    """Return the tiers that the README's GPU placement table marks as serving."""
    return {
        row[0].strip("`")
        for header, *rows in _placement_tables()
        if SERVES_COLUMN in header
        for row in rows
        if row[header.index(SERVES_COLUMN)] == "yes"
    }


def _tier_pod_labels() -> dict[str, dict[str, str]]:
    """Return the pod labels of each Ollama tier DaemonSet, by tier name, in profile order."""
    documents = yaml.safe_load_all(OLLAMA_PROFILES_MANIFEST.read_text(encoding="utf-8"))
    return {
        document["metadata"]["name"]: document["spec"]["template"]["metadata"]["labels"]
        for document in documents
        if document and document.get("kind") == "DaemonSet"
    }


def _ollama_services() -> dict[str, dict[str, str]]:
    """Return the selector of each Service in the profiles that selects Ollama pods."""
    key, provider = CONST_K8S_OLLAMA_PROVIDER_LABEL
    return {
        document["metadata"]["name"]: document["spec"]["selector"]
        for document in yaml.safe_load_all(SERVICES_MANIFEST.read_text(encoding="utf-8"))
        if document
        and document.get("kind") == "Service"
        and document["spec"].get("selector", {}).get(key) == provider
    }


def _embedding_tiers() -> set[str]:
    """Return the Ollama tiers whose pods the Service of a gateway embedding deployment selects."""
    services = _ollama_services()
    selectors = [
        services[(urlsplit(m["litellm_params"]["api_base"]).hostname or "").split(".")[0]]
        for group in _gateway_embedding_groups()
        for m in _deployments(group)
    ]
    return {
        tier
        for tier, labels in _tier_pod_labels().items()
        if any(selector.items() <= labels.items() for selector in selectors)
    }


def _ollama_ports() -> set[int]:
    """Return the ports the Ollama Services listen on."""
    documents = yaml.safe_load_all(SERVICES_MANIFEST.read_text(encoding="utf-8"))
    names = _ollama_services()
    return {
        port["port"]
        for document in documents
        if document and document["metadata"]["name"] in names
        for port in document["spec"]["ports"]
    }


def _strings(node: Any) -> Iterator[str]:
    """Yield every string in nested mappings and sequences, mapping keys included."""
    match node:
        case str():
            yield node
        case dict():
            for key, value in node.items():
                yield from _strings(key)
                yield from _strings(value)
        case list() | tuple():
            for item in node:
                yield from _strings(item)


def _named_ollama_services(node: Any) -> set[str]:
    """Return the Service of each URL in `node` that calls an Ollama port in the llm namespace.

    A URL to a Service that does not exist counts too, so a misspelt name is found."""
    ports = _ollama_ports()
    return {
        (url.hostname or "").partition(".")[0]
        for url in map(urlsplit, _strings(node))
        if (url.hostname or "").endswith(".llm.svc.cluster.local") and url.port in ports
    }


def _ingress_ollama_backends() -> set[str]:
    """Return the backend Service of each ingress path that calls an Ollama port."""
    ports = _ollama_ports()
    return {
        path["backend"]["service"]["name"]
        for document in yaml.safe_load_all(INGRESS_ROUTES.read_text(encoding="utf-8"))
        if document and document.get("kind") == "Ingress"
        for rule in document["spec"]["rules"]
        for path in rule["http"]["paths"]
        if path["backend"]["service"]["port"].get("number") in ports
    }


def _ollama_consumers() -> set[tuple[str, str]]:
    """Return each place that names an Ollama Service, paired with the Service it names."""
    defaults = "devops_cli.config.defaults"
    named = {
        f"{defaults}.DEFAULT_OLLAMA_CLUSTER_SERVICE": {DEFAULT_OLLAMA_CLUSTER_SERVICE},
        f"{defaults}.DEFAULT_OLLAMA_CLUSTER_URL": _named_ollama_services(
            DEFAULT_OLLAMA_CLUSTER_URL
        ),
        f"{defaults}.DEFAULT_GATEWAY_REVIEW_SLOTS": _named_ollama_services(
            DEFAULT_GATEWAY_REVIEW_SLOTS
        ),
        "devops_cli.ai.gateway.DEFAULT_GATEWAY_ROUTES": _named_ollama_services(
            DEFAULT_GATEWAY_ROUTES
        ),
        str(INGRESS_ROUTES): _ingress_ollama_backends(),
        str(OPEN_WEBUI_VALUES): _named_ollama_services(
            yaml.safe_load(OPEN_WEBUI_VALUES.read_text(encoding="utf-8"))
        ),
        str(GATEWAY_CONFIG): _named_ollama_services(_gateway_config()),
        str(DEVCONTAINER): _named_ollama_services(
            json.loads(DEVCONTAINER.read_text(encoding="utf-8"))
        ),
    }
    return {(place, service) for place, services in named.items() for service in services}


def _consumers_off_serving_tiers(serving: set[str]) -> set[tuple[str, str]]:
    """Return each consumer whose Service is no Ollama Service or selects no pod of a tier in
    `serving`."""
    selectors, tiers = _ollama_services(), _tier_pod_labels()
    serving_labels = [labels for tier, labels in tiers.items() if tier in serving]

    def selects_a_serving_tier(service: str) -> bool:
        selector = selectors.get(service)
        return selector is not None and any(
            selector.items() <= labels.items() for labels in serving_labels
        )

    return {
        (place, service)
        for place, service in _ollama_consumers()
        if not selects_a_serving_tier(service)
    }


def test_the_gpu_placement_table_says_for_each_tier_whether_it_serves() -> None:
    """The README's GPU placement table lists each Ollama tier of the profiles once, in profile
    order, and its Serves column says yes or no for each, so the serving tiers have one record."""
    [(header, *rows)] = _placement_tables()

    assert (
        [row[0].strip("`") for row in rows],
        SERVES_COLUMN in header and {row[header.index(SERVES_COLUMN)] for row in rows},
    ) == (list(_tier_pod_labels()), {"yes", "no"})


def test_every_ollama_consumer_names_a_service_that_selects_a_serving_tier() -> None:
    """Each place that names an Ollama Service names one that selects the pods of a tier the
    README marks as serving: the CLI's default Service and failover routes, the review slots,
    the ollama ingress, the gateway and the devcontainer. Open WebUI names none since #1668, and
    is held to the same rule if it names one again. Before #1637 the ingress, the CLI default
    and Open WebUI named tiers whose host was offline, and answered 503 or nothing for weeks."""
    assert (bool(_ollama_consumers()), _consumers_off_serving_tiers(_serving_tiers())) == (
        True,
        set(),
    )


def test_a_tier_that_stops_serving_names_each_consumer_that_reaches_it_alone() -> None:
    """Negative control: with ollama-16gib marked as not serving, as when its host went
    offline, the check names exactly the consumers whose Service selects that tier alone."""
    assert _consumers_off_serving_tiers(_serving_tiers() - {"ollama-16gib"}) == {
        (str(GATEWAY_CONFIG), "ollama-16gib-fast"),
        ("devops_cli.config.defaults.DEFAULT_GATEWAY_REVIEW_SLOTS", "ollama-16gib-fast"),
        (str(DEVCONTAINER), "ollama-16gib"),
    }


def _tiers_of(url: str) -> set[str]:
    """Return the Ollama tiers whose pods the Service of `url` selects; none when `url` names no
    Ollama Service."""
    selector = _ollama_services().get((urlsplit(url).hostname or "").partition(".")[0])
    return {
        tier
        for tier, labels in _tier_pod_labels().items()
        if selector is not None and selector.items() <= labels.items()
    }


def _deployment_tiers() -> list[tuple[dict[str, Any], set[str]]]:
    """Return each gateway deployment with the Ollama tiers that its Service selects. The tiers of
    each URL are found once, because each find reads the profiles again."""
    deployments = _gateway_config()["model_list"]
    tiers = {url: _tiers_of(url) for url in {m["litellm_params"]["api_base"] for m in deployments}}
    return [(m, tiers[m["litellm_params"]["api_base"]]) for m in deployments]


def _gateway_tier_models() -> set[tuple[str, str]]:
    """Return each tier and model to which a gateway deployment sends requests: the model of the
    deployment without its provider, on each tier that its Service selects."""
    providers = _gateway_providers()
    return {
        (tier, _without_provider(m["litellm_params"]["model"], providers))
        for m, tiers in _deployment_tiers()
        for tier in tiers
    }


def _off_the_gateway(targets: set[tuple[str, str]]) -> set[tuple[str, str]]:
    """Return each target, as a model and a URL, whose Service selects no serving tier, or whose
    model no gateway deployment sends to a serving tier that the Service selects."""
    served, serving = _gateway_tier_models(), _serving_tiers()
    return {
        (model, url)
        for model, url in targets
        if not (tiers := _tiers_of(url) & serving)
        or any((tier, model) not in served for tier in tiers)
    }


def _routes_off_the_gateway(routes: list[GatewayRoute]) -> set[tuple[str, str]]:
    """Return each route, as its virtual and target model, whose model and Service are off the
    gateway."""
    off = _off_the_gateway({(route.target_model, route.backend_url) for route in routes})
    return {
        (route.virtual_model, route.target_model)
        for route in routes
        if (route.target_model, route.backend_url) in off
    }


def _failover_routes(state_dir: Path) -> list[GatewayRoute]:
    """Return the route that a failover of each virtual model records, each on a new route
    table."""
    routes: list[GatewayRoute] = []
    for model in CONST_AI_GATEWAY_VIRTUAL_MODELS:
        router = GatewayRouter(state_file=state_dir / f"{model}.json")
        router.trigger_failover(model, simulate=False, force=True)
        routes += [route for route in router.list_routes() if route.virtual_model == model]
    return routes


def test_every_gateway_route_and_failover_route_names_a_model_that_its_tier_serves(
    tmp_path: Path,
) -> None:
    """Each default route of `devops ai gateway`, and the route that a failover of each virtual
    model records, names a model that a gateway deployment sends to the serving tier of the
    route's Service. Before #1969 the routes named qwen2.5-coder:7b and qwen2.5-coder:14b: no
    tier held the 14b model, and the tier of the default Ollama Service held neither, so a
    failover to them failed."""
    routes = [
        *GatewayRouter(state_file=tmp_path / "default.json").list_routes(),
        *_failover_routes(tmp_path),
    ]

    assert [route.virtual_model for route in routes] == [*CONST_AI_GATEWAY_VIRTUAL_MODELS] * 2
    assert _routes_off_the_gateway(routes) == set()


def test_the_route_check_names_each_route_whose_tier_the_gateway_sends_no_such_model() -> None:
    """Negative control: the check names a route to a model that no gateway deployment names, a
    route to a model that the gateway sends to another tier only, a route to a tier that does not
    serve and a route to no Ollama Service. It passes a route that the gateway serves."""
    routes = [
        GatewayRoute(
            virtual_model=virtual_model,
            target_model=model,
            backend_type="ollama",
            backend_url=f"http://{service}.llm.svc.cluster.local:11434",
        )
        for virtual_model, model, service in [
            ("devops-coder", "qwen2.5-coder:14b", DEFAULT_OLLAMA_CLUSTER_SERVICE),
            ("devops-reasoning", "deepseek-r1:70b", DEFAULT_OLLAMA_CLUSTER_SERVICE),
            ("devops-embedding", "qwen3-embedding:0.6b", "ollama-24gib"),
            ("devops-chat", "qwen3.8:27b", "ollama-nowhere"),
            ("devops-review", "qwen3-coder:30b", "ollama-64gib-standard"),
        ]
    ]

    assert _routes_off_the_gateway(routes) == {
        ("devops-coder", "qwen2.5-coder:14b"),
        ("devops-reasoning", "deepseek-r1:70b"),
        ("devops-embedding", "qwen3-embedding:0.6b"),
        ("devops-chat", "qwen3.8:27b"),
    }


def _default_fallback_models() -> dict[str, str]:
    """Return each place that names the default fallback model, with the model that it names: the
    default of `devops ai failover` and `devops ai chaos-model`, and the defaults of the harness
    model slot and of the sub-agent's model slot."""
    return {
        "devops_cli.config.defaults.DEFAULT_AI_FALLBACK_MODEL": DEFAULT_AI_FALLBACK_MODEL,
        "devops_cli.ai.harness.slots.ModelSlot": ModelSlot(name="model").model_name,
        "devops_cli.ai.harness.slots.SubAgentSlot": SubAgentSlot(
            name="subagent"
        ).model_slot.model_name,
    }


def test_the_default_fallback_model_is_a_model_that_the_default_ollama_tier_serves() -> None:
    """Each place that names the default fallback model names a model that a gateway deployment
    sends to the serving tier of the default Ollama Service, as a failover to direct Ollama does
    (#1969). Before #2047 each named qwen2.5-coder:7b, which no gateway deployment names, so a
    fallback to it found no model on the tier."""
    fallback_models = _default_fallback_models()
    off = _off_the_gateway(
        {(model, DEFAULT_OLLAMA_CLUSTER_URL) for model in fallback_models.values()}
    )

    assert (
        bool(fallback_models),
        {
            place: model
            for place, model in fallback_models.items()
            if (model, DEFAULT_OLLAMA_CLUSTER_URL) in off
        },
    ) == (True, {})


def _open_webui_default_models() -> set[str]:
    """Return each model that Open WebUI's `DEFAULT_MODELS` names. Open WebUI splits the value at
    each comma."""
    return {
        model.strip() for model in _open_webui_env()["DEFAULT_MODELS"].split(",") if model.strip()
    }


def _groups_off_the_gateway(models: set[str]) -> set[str]:
    """Return each of `models` that is no group of the gateway config, or whose deployments call
    no serving tier."""
    serving = _serving_tiers()
    return models - {m["model_name"] for m, tiers in _deployment_tiers() if tiers & serving}


def test_every_open_webui_default_model_is_a_group_that_the_gateway_serves() -> None:
    """Each model that Open WebUI's `DEFAULT_MODELS` names is a group of the gateway config with a
    deployment on a serving tier. Open WebUI asks its OpenAI connection, the gateway, for the
    model by its group name. The values set no `MODEL_FILTER_LIST`: Open WebUI removed that
    allow list in v0.4.0, and the list named two models that the gateway does not serve (#2047)."""
    default_models = _open_webui_default_models()

    assert (
        bool(default_models),
        _groups_off_the_gateway(default_models),
        "MODEL_FILTER_LIST" in _open_webui_env(),
    ) == (True, set(), False)


def test_the_group_check_names_each_model_that_is_no_served_gateway_group() -> None:
    """Negative control: the check names a model that no gateway deployment names, a virtual model
    that the gateway config does not have, and an Ollama model name that is no group. It passes
    the groups that the gateway serves."""
    assert _groups_off_the_gateway(
        {
            "devops-chat",
            "qwen3-coder:30b",
            "qwen2.5-coder:7b",
            "devops-flagship",
            "hf.co/ISTA-DASLab/Qwen3.8-27B-GSQ-RCO-GGUF:IQ3_S",
        }
    ) == {"qwen2.5-coder:7b", "devops-flagship", "hf.co/ISTA-DASLab/Qwen3.8-27B-GSQ-RCO-GGUF:IQ3_S"}


def _default_models() -> dict[str, set[str]]:
    """Return each place that names a default model of the CLI, with the models that it names: the
    default of `ai.model`, the models that `devops ai bundle-models` lists, and the candidate that a
    task benchmark runs when it gets none."""
    return {
        "devops_cli.config.defaults.DEFAULT_AI_MODEL": {DEFAULT_AI_MODEL},
        "devops_cli.config.defaults.DEFAULT_BUNDLE_MODELS": set(DEFAULT_BUNDLE_MODELS),
        "devops_cli.ai.benchmark.runner.BenchmarkRunner": set(
            BenchmarkRunner(models=[], tasks=[], settings=Settings(ai=AIConfig())).models
        ),
    }


def test_every_default_model_is_a_model_that_the_default_ollama_tier_and_the_gateway_serve() -> (
    None
):
    """Each default model of the CLI is a model that a gateway deployment sends to the serving tier
    of the default Ollama Service, and a group of the gateway config with a deployment on a serving
    tier. The default provider calls Ollama, which `devops k8s configure-urls` points at the default
    Ollama Service, and `provider: gateway` asks the gateway for the model by its name. Before #2125
    the defaults named gemma4:26b, qwen2.5-coder:7b and llama3.1:8b, which no gateway deployment
    names."""
    default_models = _default_models()
    models = set().union(*default_models.values())
    unserved = {
        model for model, _ in _off_the_gateway({(m, DEFAULT_OLLAMA_CLUSTER_URL) for m in models})
    } | _groups_off_the_gateway(models)

    assert (
        all(default_models.values()),
        {
            place: sorted(named & unserved)
            for place, named in default_models.items()
            if named & unserved
        },
    ) == (True, {})


def _gpu_matrix_virtual_models() -> dict[str, str]:
    """Return each place of the GPU matrix that names a gateway group, with the group that it
    names: the virtual model of each hardware profile, and of each Service alias that has one."""
    return {
        **{
            f"profile {p.gpu_count}x{p.vram_per_gpu_gib}GiB": p.virtual_gateway_model
            for p in list_gpu_profiles()
        },
        **{
            f"service alias {alias}": info["virtual_model"]
            for alias, info in get_service_aliases().items()
            if "virtual_model" in info
        },
    }


def test_every_gpu_matrix_virtual_model_is_a_group_that_the_gateway_serves() -> None:
    """The Virtual Model column of `devops k8s gpu-matrix` names the gateway group of each hardware
    profile and of each Service alias. Each is a group of the gateway config with a deployment on a
    serving tier. Before #2125 the 70B profiles and the aliases of 48 GiB and more named
    devops-flagship, a group that the gateway config removed with its vLLM backend."""
    virtual_models = _gpu_matrix_virtual_models()
    unserved = _groups_off_the_gateway(set(virtual_models.values()))

    assert (
        bool(virtual_models),
        {place: group for place, group in virtual_models.items() if group in unserved},
    ) == (True, {})


@pytest.mark.parametrize("directory", [LLM_DIR, GATEWAY_DIR], ids=["argo-cd", "deploy-stack"])
def test_the_gateway_mounts_a_config_map_named_by_a_hash_of_its_config(directory: Path) -> None:
    """Argo CD's `llm` Application renders `k8s/llm` with Kustomize, and deploy-stack applies
    `k8s/llm/gateway` with `kubectl apply -k`. Both give the gateway ConfigMap
    `llm-gateway-config-<hash>`, which holds `config.yaml` as git has it, and write that name into
    the Deployment's config volume. Before #1929 the name had no hash, so a changed config left
    the pod template as it was, and the gateway served the old config until a person restarted it.
    """
    _, configmap = _rendered_gateway(directory)
    name = configmap.get("metadata", {}).get("name", "")

    assert (
        re.fullmatch(r"llm-gateway-config-[a-z0-9]{10}", name) is not None,
        configmap.get("data"),
    ) == (True, {"config.yaml": GATEWAY_CONFIG.read_text(encoding="utf-8")})


def test_a_changed_gateway_config_changes_only_the_config_map_name_in_the_pod_template(
    tmp_path: Path,
) -> None:
    """A change to `config.yaml` alone changes the gateway's pod template, so Kubernetes rolls the
    Deployment onto the new config and no `kubectl rollout restart` is necessary (#1929). The
    template changes in the name of its config volume's ConfigMap and in nothing else."""
    before, after = tmp_path / "before", tmp_path / "after"
    shutil.copytree(GATEWAY_DIR, before)
    shutil.copytree(GATEWAY_DIR, after)
    config = after / "config.yaml"
    config.write_text(
        config.read_text(encoding="utf-8").replace("cooldown_time: 30", "cooldown_time: 60"),
        encoding="utf-8",
    )
    (old, old_configmap), (new, new_configmap) = _rendered_gateway(before), _rendered_gateway(after)

    def unnamed(deployment: dict[str, Any]) -> dict[str, Any]:
        template = copy.deepcopy(deployment["spec"]["template"])
        for volume in template["spec"]["volumes"]:
            volume.get("configMap", {}).pop("name", None)
        return template

    assert (
        old["spec"]["template"] == new["spec"]["template"],
        unnamed(old) == unnamed(new),
        old_configmap["metadata"]["name"] == new_configmap["metadata"]["name"],
        yaml.safe_load(new_configmap["data"]["config.yaml"])["router_settings"]["cooldown_time"],
    ) == (False, True, False, 60)


# ── The hosted model groups call a provider with a key from the gateway Secret (#3113) ──────────


def _hosted_violations(config: dict[str, Any], deployment: dict[str, Any]) -> list[str]:
    """Return every way the hosted groups of `config` break their rules.

    A hosted group names a gemini or anthropic backend with no `api_base`, and reads its key from
    an environment variable of the gateway Deployment. The variable is an optional key of the
    gateway Secret, which `CLUSTER_SECRETS` writes without requiring it, so the gateway starts
    without the key. A group sets its window and, where the cost map of the pinned image lacks the
    model, its prices. A Claude group drops the sampling parameters that its API refuses. No pool, fallback or routing group names a hosted group, so a prompt leaves
    the cluster only when its caller names the group.
    """
    entries = [m for m in config["model_list"] if m["model_name"] in HOSTED_GROUPS]
    env = {
        v["name"]: v["valueFrom"]["secretKeyRef"]
        for v in deployment["spec"]["template"]["spec"]["containers"][0]["env"]
        if "secretKeyRef" in v.get("valueFrom", {})
    }
    secret = next(s for s in CLUSTER_SECRETS if s.ref == f"llm/{HOSTED_SECRET}")
    optional_keys = {entry.key for entry in secret.entries if not entry.required}
    router = config["router_settings"]
    chains = [*router.get("fallbacks", []), *router.get("context_window_fallbacks", [])]
    routed = {
        name for link in chains for key, targets in link.items() for name in (key, *targets)
    } | {name for group in router.get("routing_groups", []) for name in group["models"]}
    listed = [m["model_name"] for m in entries]
    problems = [
        f"{name} is listed {listed.count(name)} times"
        for name in HOSTED_GROUPS
        if listed.count(name) != 1
    ]
    problems += [
        f"{name} is in a pool or a fallback" for name in sorted(routed & set(HOSTED_GROUPS))
    ]
    for model in entries:
        params, info = model["litellm_params"], model.get("model_info") or {}
        name = model["model_name"]
        variable = str(params.get("api_key", "")).removeprefix("os.environ/")
        reference = env.get(variable)
        if params["model"].partition("/")[0] not in {"gemini", "anthropic"}:
            problems.append(f"{name} calls a provider that is not gemini or anthropic")
        if "api_base" in params:
            problems.append(f"{name} sets an api_base")
        if not str(params.get("api_key", "")).startswith("os.environ/") or reference is None:
            problems.append(f"{name} reads its key from no Deployment variable of the Secret")
        elif (
            reference["name"] != HOSTED_SECRET
            or reference["key"] not in optional_keys
            or reference.get("optional") is not True
        ):
            problems.append(f"{name} does not read an optional key of {HOSTED_SECRET}")
        if not info.get("max_input_tokens"):
            problems.append(f"{name} sets no window")
        if params["model"].startswith("anthropic/") and not (
            info.get("input_cost_per_token") and info.get("output_cost_per_token")
        ):
            problems.append(f"{name} sets no prices, and the cost map of the image lacks it")
        if params["model"].startswith("anthropic/") and set(
            params.get("additional_drop_params") or ()
        ) != {"temperature", "top_p", "top_k"}:
            problems.append(f"{name} does not drop the sampling parameters that the API refuses")
    return problems


def test_the_hosted_groups_call_providers_with_optional_keys_and_join_no_pool() -> None:
    """The hosted groups follow their rules (#3113)."""
    deployment = _load_kind(GATEWAY_DIR / "deployment.yaml", "Deployment")
    assert _hosted_violations(_full_gateway_config(), deployment) == []


@pytest.mark.parametrize(
    ("edit", "expected"),
    [
        pytest.param(
            lambda config, deployment: config["router_settings"]["fallbacks"].append(
                {"devops-review": ["claude-haiku-5-5"]}
            ),
            "claude-haiku-5-5 is in a pool or a fallback",
            id="fallback-to-a-hosted-group",
        ),
        pytest.param(
            lambda config, deployment: config["router_settings"]["routing_groups"][0][
                "models"
            ].append("gemini-3.8-flash"),
            "gemini-3.8-flash is in a pool or a fallback",
            id="routing-group-with-a-hosted-group",
        ),
        pytest.param(
            lambda config, deployment: deployment["spec"]["template"]["spec"]["containers"][0][
                "env"
            ].remove(
                next(
                    v
                    for v in deployment["spec"]["template"]["spec"]["containers"][0]["env"]
                    if v["name"] == "GEMINI_API_KEY"
                )
            ),
            "gemini-3.8-flash reads its key from no Deployment variable of the Secret",
            id="key-variable-missing",
        ),
        pytest.param(
            lambda config, deployment: next(
                v
                for v in deployment["spec"]["template"]["spec"]["containers"][0]["env"]
                if v["name"] == "ANTHROPIC_API_KEY"
            )["valueFrom"]["secretKeyRef"].pop("optional"),
            "claude-sonnet-5-5 does not read an optional key of llm-gateway-secrets",
            id="required-key-stops-the-gateway-without-it",
        ),
        pytest.param(
            lambda config, deployment: next(
                m for m in config["model_list"] if m["model_name"] == "claude-sonnet-5-5"
            )["litellm_params"].update(api_base="http://example.com"),
            "claude-sonnet-5-5 sets an api_base",
            id="api-base-on-a-hosted-group",
        ),
        pytest.param(
            lambda config, deployment: next(
                m for m in config["model_list"] if m["model_name"] == "claude-haiku-5-5"
            )["model_info"].pop("output_cost_per_token"),
            "claude-haiku-5-5 sets no prices, and the cost map of the image lacks it",
            id="claude-prices-missing",
        ),
        pytest.param(
            lambda config, deployment: next(
                m for m in config["model_list"] if m["model_name"] == "claude-sonnet-5-5"
            )["litellm_params"].pop("additional_drop_params"),
            "claude-sonnet-5-5 does not drop the sampling parameters that the API refuses",
            id="sampling-parameters-reach-the-api",
        ),
    ],
)
def test_each_edit_that_breaks_a_hosted_rule_is_a_violation(
    edit: Callable[[dict[str, Any], dict[str, Any]], None], expected: str
) -> None:
    config = copy.deepcopy(_full_gateway_config())
    deployment = copy.deepcopy(_load_kind(GATEWAY_DIR / "deployment.yaml", "Deployment"))
    edit(config, deployment)
    assert expected in _hosted_violations(config, deployment)
