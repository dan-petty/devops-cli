"""Manifest syntax, security perimeter, and zero-leakage validation for LLM Gateway."""

from __future__ import annotations

import copy
import json
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import pytest
import yaml
from docker.utils import parse_repository_tag
from packaging.version import Version

from devops_cli.ai.benchmark.runner import BenchmarkRunner
from devops_cli.ai.gateway import DEFAULT_GATEWAY_ROUTES, GatewayRoute, GatewayRouter
from devops_cli.ai.harness.slots import ModelSlot, SubAgentSlot
from devops_cli.commands.k8s.stack_lifecycle import HELM_RELEASES_BY_STACK, MANIFESTS_BY_STACK
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
    DEFAULT_OLLAMA_EMBEDDING_CLUSTER_URL,
    DEFAULT_RAG_EMBEDDING_MODEL,
    DEFAULT_REVIEW_TIMEOUT_SECONDS,
)
from devops_cli.config.settings import AIConfig, Settings
from devops_cli.k8s.cluster_secrets import load_cluster_secrets_table
from devops_cli.k8s.gpu_matrix import (
    get_gateway_routing_entries,
    get_service_aliases,
    list_gpu_profiles,
)
from tests.support.k8s_tree import TREE, release_values
from tests.support.markdown_examples import (
    tables,
)

DEFAULT_AI_GATEWAY_CLUSTER_URL: str = "http://llm-gateway.llm.svc.cluster.local:4000/v1"
GATEWAY_DIR = Path("k8s/llm/gateway")
# The LiteLLM config; the gateway kustomization generates ConfigMap llm-gateway-config from it.
GATEWAY_CONFIG = GATEWAY_DIR / "config.yaml"
PROFILES_DIR = Path("k8s/llm/profiles")
OLLAMA_PROFILES_MANIFEST = PROFILES_DIR / "ollama-profiles.yaml"
SERVICES_MANIFEST = PROFILES_DIR / "services.yaml"
NETWORKPOLICY_MANIFEST = PROFILES_DIR / "networkpolicy.yaml"
OPEN_WEBUI_VALUES = Path("k8s/llm/values-open-webui.yaml")
K8S_README = Path("k8s/README.md")
INGRESS_ROUTES = Path("k8s/ingress/ingress-routes.yaml")
DEVCONTAINER = Path(".devcontainer/devcontainer.json")
# The column of the README's GPU placement table that says whether a node satisfies the tier.
SERVES_COLUMN = "Serves"

# The first release of each line that holds the fixes of GHSA-7hp6-4w63-5g45 (1.103.1) and
# GHSA-w4c7-34wj-hqm8 (1.103.10), both critical advisories of LiteLLM (#4370).
GATEWAY_ADVISORY_FIXED_IN = {
    (1, 103): "1.103.10",
    (1, 104): "1.104.8",
    (1, 105): "1.105.6",
    (1, 106): "1.106.5",
}
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
HOSTED_GROUPS = (
    "gemini-3.8-flash",
    "claude-sonnet-5-5",
    "claude-haiku-5-5",
    "deepseek-v4.1-flash-1017",
    "deepseek-v4.1-flash",
)
HOSTED_SECRET = "llm-gateway-secrets"
# The LiteLLM injection points of a Claude group (#3658): the system messages, and the last message.
CLAUDE_SYSTEM_CACHE_POINT = {"location": "message", "role": "system"}
CLAUDE_HISTORY_CACHE_POINT = {"location": "message", "index": -1}
# Anthropic refuses a request with more than 4 `cache_control` breakpoints.
ANTHROPIC_MAX_CACHE_BREAKPOINTS = 4


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


def _gateway_embedding_aliases() -> set[str]:
    """Return aliases targeting embedding groups."""
    direct = _gateway_embedding_groups()
    aliases = _full_gateway_config().get("router_settings", {}).get("model_group_alias", {})
    return {alias for alias, target in aliases.items() if target in direct}


def _default_route_embedding_models() -> set[str]:
    """Return the target model of the `qwen3-embedding:0.6b` default gateway route."""
    return {
        route["target_model"]
        for route in DEFAULT_GATEWAY_ROUTES
        if route["virtual_model"] == "qwen3-embedding:0.6b"
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


def _gateway_providers() -> set[str]:
    """Return the LiteLLM providers the gateway ConfigMap's backends name (`ollama`, `ollama_chat`)."""
    return {m["litellm_params"]["model"].partition("/")[0] for m in _gateway_config()["model_list"]}


def _without_provider(model: str, providers: set[str]) -> str:
    """Return `model` without a leading provider (`ollama/qwen3-embedding:0.6b` is
    `qwen3-embedding:0.6b`)."""
    provider, _, rest = model.partition("/")
    return rest if provider in providers else model


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
            container["resources"]["limits"]["memory"],
        ) == (
            "llm",
            True,
            1000,
            4000,
            "200m",
            "1000m",
            "4Gi",
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

    @pytest.mark.parametrize(
        "embedding_models",
        [
            pytest.param(_default_route_embedding_models, id="the-default-gateway-routes"),
            pytest.param(_gpu_matrix_embedding_models, id="the-gpu-matrix-gateway-routes"),
        ],
    )
    def test_every_registry_that_names_an_embedding_model_names_a_group_the_gateway_serves(
        self, embedding_models: Callable[[], set[str]]
    ) -> None:
        """Verify the embedding model that each of two places in the code names is an embedding
        group of the gateway ConfigMap: the default gateway routes and the GPU matrix routes. A
        place that falls behind a renamed group sends its requests to a model the gateway refuses
        (#481, #1637)."""
        named = embedding_models()

        assert (
            bool(named),
            named - (_gateway_embedding_groups() | _gateway_embedding_aliases()),
        ) == (True, set())

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
            "llm-gateway-perimeter-ingress",
            "llm-gateway",
            [(None, [4000])],
        )

    def test_gateway_deployment_reads_master_key_from_secret(self) -> None:
        """Verify the gateway never embeds its master key."""
        dep = _load_kind(GATEWAY_DIR / "deployment.yaml", "Deployment")
        container = dep["spec"]["template"]["spec"]["containers"][0]
        env = {e["name"]: e for e in container["env"]}
        master_key = env["LITELLM_MASTER_KEY"]

        assert (
            "value" in master_key,
            master_key["valueFrom"]["secretKeyRef"]["name"],
            master_key["valueFrom"]["secretKeyRef"]["key"],
        ) == (
            False,
            GATEWAY_SECRET,
            GATEWAY_SECRET_KEY,
        )

    def test_gateway_image_is_not_below_the_release_that_fixes_the_critical_advisories(
        self,
    ) -> None:
        """Verify the pinned LiteLLM release holds the fixes of GHSA-7hp6-4w63-5g45 (an internal
        user becomes proxy admin) and GHSA-w4c7-34wj-hqm8 (a file read that leaks the master key).
        The gateway is reachable from outside the cluster (#4370). A line that is not in the table
        has no known fix, and a release of a newer line holds both."""
        dep = _load_kind(GATEWAY_DIR / "deployment.yaml", "Deployment")
        image = dep["spec"]["template"]["spec"]["containers"][0]["image"]
        repository, tag = parse_repository_tag(image)
        version = Version((tag or "").removeprefix("v"))
        fixed_in = GATEWAY_ADVISORY_FIXED_IN.get(version.release[:2])
        newest_line = max(GATEWAY_ADVISORY_FIXED_IN)

        assert repository == "ghcr.io/berriai/litellm"
        assert (
            version >= Version(fixed_in)
            if fixed_in is not None
            else version.release[:2] > newest_line
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

    def test_llm_namespace_default_perimeter_excludes_gateway_and_workloads(self) -> None:
        """Verify both llm-default-perimeter policies exclude gateway, portkey and the three
        Valkeys to avoid additive policy leakage.

        The egress policy allows every destination on every port, so a Valkey that it selects
        gets full egress.
        """
        np_path = Path("k8s/llm/networkpolicy.yaml")
        docs = list(yaml.safe_load_all(np_path.read_text(encoding="utf-8")))
        policies = {
            d["metadata"]["name"]: d for d in docs if d and d.get("kind") == "NetworkPolicy"
        }

        assert [
            (expr["operator"], sorted(expr["values"]))
            for side in ("ingress", "egress")
            for expr in policies[f"llm-default-perimeter-{side}"]["spec"]["podSelector"][
                "matchExpressions"
            ]
            if expr["key"] == "app.kubernetes.io/name"
        ] == [("NotIn", ["llm-gateway", "portkey", "valkey", "valkey-devops", "valkey-runs"])] * 2

    def test_llm_manifests_have_a_deploy_path(self, tmp_path: Path) -> None:
        """Verify every manifest under k8s/llm is applied by something (#953).

        A file counts when a k8s/llm kustomization lists it (a listed directory lists its
        files), when deploy-stack applies it (`MANIFESTS_BY_STACK["llm"]`), or when it is the
        values file of an `llm` Helm release. `ollama-host-service.yaml` and `values-ollama.yaml`
        had none: nothing applied them once the Ollama tiers replaced the single `ollama` workload.
        The thresholds and the tier templates are inputs of `devops ai gateway render`: what it
        writes from them is applied, and they are not.
        """
        llm_dir = Path("k8s/llm")
        manifests = {path for path in llm_dir.rglob("*.yaml") if path.name != "kustomization.yaml"}
        applied = (
            {
                path
                for kustomization in llm_dir.rglob("kustomization.yaml")
                for path in _kustomized_files(kustomization.parent)
            }
            | {Path("k8s") / path for path in MANIFESTS_BY_STACK["llm"]}
            | {
                value.relative_to(TREE.repo)
                for release in HELM_RELEASES_BY_STACK["llm"]
                for value in release_values(release, tmp_path)
            }
            | {
                Path("k8s/llm/profiles/gpu-thresholds.yaml"),
                *Path("k8s/llm/profiles/tier-templates").glob("*.yaml"),
            }
        )

        assert sorted(manifests - applied) == []


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
# The database of the virtual keys: the pods of CloudNativePG Cluster llm-gateway-db, on 5432 (#1635).
_DATABASE_PEER = {"podSelector": {"matchLabels": {"cnpg.io/cluster": "llm-gateway-db"}}}
_DATABASE_PORTS = frozenset({("TCP", 5432, None)})
# The spans of the `otel` callback: the OpenTelemetry Collector pods on OTLP/HTTP, never the
# namespace, so no span reaches Tempo past the Collector rule that deletes key data (#4518).
_COLLECTOR_PEER = {
    "namespaceSelector": {"matchLabels": {"kubernetes.io/metadata.name": "otel"}},
    "podSelector": {
        "matchLabels": {
            "app.kubernetes.io/name": "opentelemetry-collector",
            "app.kubernetes.io/instance": "otel-collector",
        }
    },
}
_COLLECTOR_PORTS = frozenset({("TCP", 4318, None)})

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
    if peer == _DATABASE_PEER:
        return (
            None
            if ports == _DATABASE_PORTS
            else f"the database peer admits {sorted(map(str, ports))}"
        )
    if peer == _COLLECTOR_PEER:
        return (
            None
            if ports == _COLLECTOR_PORTS
            else f"the collector peer admits {sorted(map(str, ports))}"
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
    models, with its private ranges excluded, or the Collector pods on TCP 4318. No other ipBlock
    passes.
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


def _database_rule(spec: dict[str, Any]) -> dict[str, Any]:
    """Return the egress rule that admits the gateway database."""
    return next(rule for rule in spec["egress"] if _DATABASE_PEER in rule["to"])


def _hosted_rule(spec: dict[str, Any]) -> dict[str, Any]:
    """Return the egress rule that admits the hosted providers."""
    return next(rule for rule in spec["egress"] if _HOSTED_PEER in rule["to"])


@pytest.fixture(scope="module")
def gateway_egress() -> tuple[dict[str, Any], list[BackendTarget], dict[str, str]]:
    """Return the gateway policy, its resolved backends and the gateway's pod labels."""
    deployment = _load_kind(GATEWAY_DIR / "deployment.yaml", "Deployment")
    backends = [target for target in _gateway_backends().values() if target is not None]
    (egress,) = [
        doc
        for doc in yaml.safe_load_all(
            (GATEWAY_DIR / "networkpolicy.yaml").read_text(encoding="utf-8")
        )
        if doc["metadata"]["name"] == "llm-gateway-perimeter-egress"
    ]
    return (
        egress,
        backends,
        deployment["spec"]["template"]["metadata"]["labels"],
    )


def test_gateway_egress_admits_nothing_else(
    gateway_egress: tuple[dict[str, Any], list[BackendTarget], dict[str, str]],
) -> None:
    """The gateway reaches its backends, DNS, its key database, the hosted providers and the span
    Collector, and nothing else.

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
        pytest.param(
            lambda spec: _database_rule(spec)["ports"].append({"protocol": "TCP", "port": 8000}),
            id="database-rule-on-the-operator-port",
        ),
        pytest.param(
            lambda spec: _database_rule(spec)["to"].append({"podSelector": {}}),
            id="any-pod-on-the-database-rule",
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
        f"{defaults}.DEFAULT_OLLAMA_EMBEDDING_CLUSTER_URL": _named_ollama_services(
            DEFAULT_OLLAMA_EMBEDDING_CLUSTER_URL
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
        "devops_cli.k8s.gpu_matrix.gateway_routes": _named_ollama_services(
            get_gateway_routing_entries()
        ),
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


def test_every_ollama_consumer_names_a_service_that_selects_a_serving_tier() -> None:
    """Each place that names an Ollama Service names one that selects the pods of a tier the
    README marks as serving: the CLI's default Service and failover routes, the review slots,
    the ollama ingress, the gateway, the routes of the GPU matrix and the devcontainer. Open WebUI names none since #1668, and
    is held to the same rule if it names one again. Before #1637 the ingress, the CLI default
    and Open WebUI named tiers whose host was offline, and answered 503 or nothing for weeks."""
    assert (bool(_ollama_consumers()), _consumers_off_serving_tiers(_serving_tiers())) == (
        True,
        set(),
    )


def test_a_tier_that_stops_serving_names_each_consumer_that_reaches_it_alone() -> None:
    """Negative control: with ollama-64gib marked as not serving, as when its host went
    offline, the check names exactly the consumers whose Service selects that tier alone."""
    assert _consumers_off_serving_tiers(_serving_tiers() - {"ollama-64gib"}) == {
        (str(GATEWAY_CONFIG), "ollama-64gib-standard"),
        ("devops_cli.config.defaults.DEFAULT_GATEWAY_REVIEW_SLOTS", "ollama-64gib-standard"),
        ("devops_cli.k8s.gpu_matrix.gateway_routes", "ollama-64gib-standard"),
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


SINGLE_MODEL_TIERS = ("ollama-48gib", "ollama-64gib")


def _single_model_tiers_of(url: str) -> set[str]:
    """Return the single-model tiers whose pods the Service of `url` selects (#3574, #3567)."""
    return _tiers_of(url) & set(SINGLE_MODEL_TIERS)


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


def _unknown_gateway_model_names(
    names: list[str] | tuple[str, ...] | set[str],
    served: set[str] | None = None,
) -> set[str]:
    """Return each virtual model name absent from `k8s/llm/gateway/config.yaml` model_name entries."""
    known = (
        {
            str(entry["model_name"])
            for entry in _gateway_config()["model_list"]
            if isinstance(entry, dict) and entry.get("model_name")
        }
        if served is None
        else served
    )
    return {name for name in names if name not in known}


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
    assert _unknown_gateway_model_names([route.virtual_model for route in routes]) == set()
    assert _unknown_gateway_model_names(CONST_AI_GATEWAY_VIRTUAL_MODELS) == set()
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
            ("qwen3-embedding:0.6b", "qwen3-embedding:0.6b", "ollama-24gib"),
            ("devops-chat", "qwen3.8:27b", "ollama-nowhere"),
            ("devops-review", "qwen3.8:27b", "ollama-64gib-standard"),
        ]
    ]

    assert _routes_off_the_gateway(routes) == {
        ("devops-coder", "qwen2.5-coder:14b"),
        ("devops-reasoning", "deepseek-r1:70b"),
        ("qwen3-embedding:0.6b", "qwen3-embedding:0.6b"),
        ("devops-chat", "qwen3.8:27b"),
    }
    assert _unknown_gateway_model_names(["devops-chat", "devops-unknown", "missing-group"]) == {
        "devops-unknown",
        "missing-group",
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


def _groups_off_the_gateway(models: set[str]) -> set[str]:
    """Return each of `models` that is no group of the gateway config, or whose deployments call
    no serving tier."""
    serving = _serving_tiers()
    served = {m["model_name"] for m, tiers in _deployment_tiers() if tiers & serving}
    aliases = _full_gateway_config().get("router_settings", {}).get("model_group_alias", {})
    alias_groups = {alias for alias, target in aliases.items() if target in served}
    return models - (served | alias_groups)


def test_the_group_check_names_each_model_that_is_no_served_gateway_group() -> None:
    """Negative control: the check names a model that no gateway deployment names, a virtual model
    that the gateway config does not have, and an Ollama model name that is no group. It passes
    the groups that the gateway serves."""
    assert _groups_off_the_gateway(
        {
            "devops-chat",
            "qwen3.8:27b",
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


def _default_tier_url(model: str) -> str:
    """Return the Service that serves a default model: the default Ollama Service for a chat
    model, and the embedding Service for the embedding model. The default Service names a tier that
    loads one chat model and no embedding model (#3567)."""
    if model == DEFAULT_RAG_EMBEDDING_MODEL:
        return DEFAULT_OLLAMA_EMBEDDING_CLUSTER_URL
    return DEFAULT_OLLAMA_CLUSTER_URL


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
        model for model, _ in _off_the_gateway({(m, _default_tier_url(m)) for m in models})
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


# ── The hosted model groups call a provider with a key from the gateway Secret (#3113) ──────────


def _hosted_violations(config: dict[str, Any], deployment: dict[str, Any]) -> list[str]:
    """Return every way the hosted groups of `config` break their rules.

    A hosted group names a gemini or anthropic backend with no `api_base`, and reads its key from
    an environment variable of the gateway Deployment. The variable is an optional key of the
    gateway Secret, which `CLUSTER_SECRETS` writes without requiring it, so the gateway starts
    without the key. A group sets its window and, where the cost map of the pinned image lacks the
    model, its prices. A Claude group drops the sampling parameters that its API refuses. No pool, fallback or routing group names a hosted group, so a prompt leaves
    the cluster only when its caller names the group. A hosted group with more than one
    deployment gives each deployment its own `order`, so the router tries them one after the
    other and does not spread the calls over them (#5990).

    A Claude group asks Anthropic to cache its prefix (#3658): one injection point on the system
    messages caches the tools and the system prompt, and one on the last message caches the
    history of an agent run. It sets at most the 4 breakpoints that Anthropic allows. No other
    group sets an injection point.
    """
    entries = [m for m in config["model_list"] if m["model_name"] in HOSTED_GROUPS]
    env = {
        v["name"]: v["valueFrom"]["secretKeyRef"]
        for v in deployment["spec"]["template"]["spec"]["containers"][0]["env"]
        if "secretKeyRef" in v.get("valueFrom", {})
    }
    secret = next(s for s in load_cluster_secrets_table() if s.ref == f"llm/{HOSTED_SECRET}")
    optional_keys = {entry.key for entry in secret.entries if not entry.required}
    router = config["router_settings"]
    chains = [*router.get("fallbacks", []), *router.get("context_window_fallbacks", [])]
    routed = {
        name
        for link in router.get("context_window_fallbacks", [])
        for key, targets in link.items()
        for name in (key, *targets)
    } | {name for group in router.get("routing_groups", []) for name in group["models"]}
    hosted = set(HOSTED_GROUPS)
    listed = [m["model_name"] for m in entries]
    orders = {
        name: {m["litellm_params"].get("order") for m in entries if m["model_name"] == name}
        for name in HOSTED_GROUPS
    }
    problems = [f"{name} is not listed" for name in HOSTED_GROUPS if name not in listed]
    problems += [
        f"{name} has deployments with no distinct order"
        for name in HOSTED_GROUPS
        if listed.count(name) > 1 and len(orders[name] - {None}) != listed.count(name)
    ]
    problems += [
        f"{name} is in a pool or a fallback" for name in sorted(routed & set(HOSTED_GROUPS))
    ]
    problems += [
        f"{source} falls back to the hosted group {target}"
        for link in chains
        for source, targets in link.items()
        for target in targets
        if target in hosted and source not in hosted
    ]
    for model in entries:
        params, info = model["litellm_params"], model.get("model_info") or {}
        name = model["model_name"]
        variable = str(params.get("api_key", "")).removeprefix("os.environ/")
        reference = env.get(variable)
        if params["model"].partition("/")[0] not in {"gemini", "anthropic", "openrouter"}:
            problems.append(f"{name} calls a provider that is not gemini, anthropic or openrouter")
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
        if params["model"].startswith("anthropic/") and not (
            info.get("supports_native_structured_output") and info.get("supports_response_schema")
        ):
            problems.append(f"{name} would get a forced tool call for a structured reply")
        if params["model"].startswith("anthropic/") and set(
            params.get("additional_drop_params") or ()
        ) != {"temperature", "top_p", "top_k"}:
            problems.append(f"{name} does not drop the sampling parameters that the API refuses")
    return problems + _cache_point_violations(config)


def _cache_point_violations(config: dict[str, Any]) -> list[str]:
    """Return every way the groups of `config` break the cache rules (#3658): a Claude group
    sets the system point and the last-message point and at most the 4 breakpoints of Anthropic,
    and no other group sets an injection point."""
    problems: list[str] = []
    for model in config["model_list"]:
        name, params = model["model_name"], model["litellm_params"]
        points = params.get("cache_control_injection_points") or []
        if not params["model"].startswith("anthropic/"):
            if "cache_control_injection_points" in params:
                problems.append(f"{name} sets cache points, which only a Claude group sets")
            continue
        if CLAUDE_SYSTEM_CACHE_POINT not in points:
            problems.append(f"{name} caches no system prompt")
        if CLAUDE_HISTORY_CACHE_POINT not in points:
            problems.append(f"{name} caches no history of an agent run")
        if len(points) > ANTHROPIC_MAX_CACHE_BREAKPOINTS:
            problems.append(f"{name} sets more cache points than Anthropic allows")
    return problems


# The OpenRouter filter of each deployment of the two DeepSeek groups: fp8 weights only, and
# only providers that do not store or train on prompts (SECURITY.md item 13).
DEEPSEEK_PROVIDER_FILTER = {"quantizations": ["fp8"], "data_collection": "deny"}
DEEPSEEK_WINDOW = 1048576


def _hosted_deployments(group: str) -> list[dict[str, Any]]:
    """Return the deployments of one hosted group, in configuration order."""
    return [m for m in _hosted_models() if m["model_name"] == group]


def test_the_dated_deepseek_group_tries_the_dated_model_first_and_the_undated_model_next() -> None:
    """The group `deepseek-v4.1-flash-1017` has two deployments (#5990). Order 1 calls the dated
    model. One failure cools it for 120 s (`allowed_fails: 0`), and a failed health check takes
    it out of the routing, so the next call goes to order 2 in the same group: the undated model
    with no `floor` route. Each deployment asks OpenRouter for fp8 weights and
    `data_collection: deny`, takes a structured reply (#5571) and has the same window, so a call
    that order 2 answers keeps its privacy filter, its response format and its prompt."""
    deployments = _hosted_deployments("deepseek-v4.1-flash-1017")

    assert [
        (
            d["litellm_params"].get("order"),
            d["litellm_params"]["model"],
            d["litellm_params"]["extra_body"]["provider"],
            {
                key: d["model_info"].get(key)
                for key in ("allowed_fails", "cooldown_time", "health_check_timeout")
            },
            d["model_info"]["max_input_tokens"],
            d["model_info"].get("supports_response_schema"),
        )
        for d in deployments
    ] == [
        (
            1,
            "openrouter/deepseek/deepseek-v4.1-flash-1017",
            DEEPSEEK_PROVIDER_FILTER,
            {"allowed_fails": 0, "cooldown_time": 120, "health_check_timeout": 30},
            DEEPSEEK_WINDOW,
            True,
        ),
        (
            2,
            "openrouter/deepseek/deepseek-v4.1-flash",
            DEEPSEEK_PROVIDER_FILTER,
            {"allowed_fails": None, "cooldown_time": None, "health_check_timeout": 30},
            DEEPSEEK_WINDOW,
            True,
        ),
    ]


def test_the_deepseek_group_falls_back_to_the_undated_group_with_the_same_provider_filter() -> None:
    """A call of `deepseek-v4.1-flash-1017` that both of its deployments cannot answer goes to
    the group `deepseek-v4.1-flash` (owner decision of 2026-11-13, #5564). That group has its own
    deployment and its own cooldown, so it answers when both deployments of the dated group are
    cooled (#5990). It calls the undated model with the same filter, so the privacy control of
    SECURITY.md item 13 does not change, and it takes a structured reply."""
    config = _full_gateway_config()
    (fallback,) = _hosted_deployments("deepseek-v4.1-flash")

    assert (
        {"deepseek-v4.1-flash-1017": ["deepseek-v4.1-flash"]}
        in config["router_settings"]["fallbacks"],
        fallback["litellm_params"]["model"],
        fallback["litellm_params"]["extra_body"]["provider"],
        fallback["model_info"]["max_input_tokens"],
        fallback["model_info"].get("supports_response_schema"),
    ) == (
        True,
        "openrouter/deepseek/deepseek-v4.1-flash",
        DEEPSEEK_PROVIDER_FILTER,
        DEEPSEEK_WINDOW,
        True,
    )


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
            "devops-review falls back to the hosted group claude-haiku-5-5",
            id="fallback-from-an-ollama-group-to-a-hosted-group",
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
            )["model_info"].pop("supports_native_structured_output"),
            "claude-sonnet-5-5 would get a forced tool call for a structured reply",
            id="structured-reply-by-forced-tool-call",
        ),
        pytest.param(
            lambda config, deployment: next(
                m for m in config["model_list"] if m["model_name"] == "claude-sonnet-5-5"
            )["litellm_params"].pop("additional_drop_params"),
            "claude-sonnet-5-5 does not drop the sampling parameters that the API refuses",
            id="sampling-parameters-reach-the-api",
        ),
        pytest.param(
            lambda config, deployment: next(
                m for m in config["model_list"] if m["model_name"] == "claude-sonnet-5-5"
            )["litellm_params"].pop("cache_control_injection_points"),
            "claude-sonnet-5-5 caches no system prompt",
            id="claude-group-without-cache-points",
        ),
        pytest.param(
            lambda config, deployment: next(
                m for m in config["model_list"] if m["model_name"] == "claude-haiku-5-5"
            )["litellm_params"]["cache_control_injection_points"].remove(
                CLAUDE_HISTORY_CACHE_POINT
            ),
            "claude-haiku-5-5 caches no history of an agent run",
            id="claude-group-without-the-last-message-point",
        ),
        pytest.param(
            lambda config, deployment: next(
                m for m in config["model_list"] if m["model_name"] == "claude-haiku-5-5"
            )["litellm_params"]["cache_control_injection_points"].extend(
                [{"location": "message", "index": i} for i in (0, 1, 2)]
            ),
            "claude-haiku-5-5 sets more cache points than Anthropic allows",
            id="claude-group-over-the-breakpoint-limit",
        ),
        pytest.param(
            lambda config, deployment: next(
                m for m in config["model_list"] if m["model_name"] == "deepseek-v4.1-flash-1017"
            )["litellm_params"].update(
                cache_control_injection_points=[dict(CLAUDE_SYSTEM_CACHE_POINT)]
            ),
            "deepseek-v4.1-flash-1017 sets cache points, which only a Claude group sets",
            id="cache-points-on-a-group-that-is-not-claude",
        ),
        pytest.param(
            lambda config, deployment: [
                m["litellm_params"].update(order=1)
                for m in config["model_list"]
                if m["model_name"] == "deepseek-v4.1-flash-1017"
            ],
            "deepseek-v4.1-flash-1017 has deployments with no distinct order",
            id="two-hosted-deployments-with-one-order",
        ),
        pytest.param(
            lambda config, deployment: config["model_list"].remove(
                next(m for m in config["model_list"] if m["model_name"] == "gemini-3.8-flash")
            ),
            "gemini-3.8-flash is not listed",
            id="hosted-group-missing",
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


def test_the_default_embedding_url_names_no_tier_that_loads_one_chat_model() -> None:
    """The default Ollama embedding URL names no tier that loads one chat model (#3574, #3567)."""
    assert (
        bool(_tiers_of(DEFAULT_OLLAMA_EMBEDDING_CLUSTER_URL)),
        _single_model_tiers_of(DEFAULT_OLLAMA_EMBEDDING_CLUSTER_URL),
    ) == (True, set())


def test_the_embedding_url_check_names_the_48gib_tier() -> None:
    """The single-model tier check detects a URL pointing to the 48 GiB tier (#3574, #3567)."""
    test_url = "http://ollama-48gib.llm.svc.cluster.local:11434"
    assert _single_model_tiers_of(test_url) == {"ollama-48gib"}
