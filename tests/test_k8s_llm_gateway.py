"""Manifest syntax, security perimeter, and zero-leakage validation for LLM Gateway and vLLM."""

from __future__ import annotations

import copy
import re
from collections.abc import Callable
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import pytest
import yaml

from devops_cli.commands.k8s.stack_lifecycle import _HELM_RELEASES_BY_STACK, _MANIFESTS_BY_STACK
from devops_cli.config.defaults import (
    DEFAULT_AI_GATEWAY_CLUSTER_URL,
    DEFAULT_REVIEW_TIMEOUT_SECONDS,
)

GATEWAY_DIR = Path("k8s/llm/gateway")
PROFILES_DIR = Path("k8s/llm/profiles")
OLLAMA_PROFILES_MANIFEST = PROFILES_DIR / "ollama-profiles.yaml"
SERVICES_MANIFEST = PROFILES_DIR / "services.yaml"
NETWORKPOLICY_MANIFEST = PROFILES_DIR / "networkpolicy.yaml"
LLM_KUSTOMIZATION = Path("k8s/llm/kustomization.yaml")
OPEN_WEBUI_VALUES = Path("k8s/llm/values-open-webui.yaml")

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


def _gateway_config() -> dict[str, Any]:
    """Return the LiteLLM configuration the gateway ConfigMap carries."""
    cm = _load_kind(GATEWAY_DIR / "configmap.yaml", "ConfigMap")
    return dict(yaml.safe_load(cm["data"]["config.yaml"]))


def _deployments(group: str) -> list[dict[str, Any]]:
    """Return the gateway deployments of one model group, in configuration order."""
    return [m for m in _gateway_config()["model_list"] if m["model_name"] == group]


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
    """Return the files `kubectl apply -k` applies from a kustomization, following directories."""
    kustomization = yaml.safe_load((directory / "kustomization.yaml").read_text(encoding="utf-8"))
    entries = [directory / entry for entry in kustomization.get("resources", [])]
    return {entry for entry in entries if not entry.is_dir()} | {
        path for entry in entries if entry.is_dir() for path in _kustomized_files(entry)
    }


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
        cm_path = GATEWAY_DIR / "configmap.yaml"
        docs = list(yaml.safe_load_all(cm_path.read_text(encoding="utf-8")))
        cm = next(d for d in docs if d and d.get("kind") == "ConfigMap")

        raw_cfg = cm["data"]["config.yaml"]
        cfg = yaml.safe_load(raw_cfg)
        models = list(dict.fromkeys(m["model_name"] for m in cfg["model_list"]))

        assert (
            cm["metadata"]["name"],
            models,
            cfg["router_settings"]["routing_strategy"],
            cfg["router_settings"]["fallbacks"],
        ) == (
            "llm-gateway-config",
            [
                "devops-chat",
                "devops-coder",
                "devops-reasoning",
                "bge-m3:latest",
                "devops-background",
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
            ],
        )

    def test_gateway_configmap_routes_coder_and_reasoning(self) -> None:
        """Verify reasoning and coder aliases reach target Ollama profiles."""
        cm = _load_kind(GATEWAY_DIR / "configmap.yaml", "ConfigMap")
        cfg = yaml.safe_load(cm["data"]["config.yaml"])
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

    def test_gateway_escalates_to_larger_models(self) -> None:
        """Verify long prompts escalate by context window and fallback chain is configured."""
        cm = _load_kind(GATEWAY_DIR / "configmap.yaml", "ConfigMap")
        cfg = yaml.safe_load(cm["data"]["config.yaml"])
        router = cfg["router_settings"]

        assert (
            router["enable_pre_call_checks"],
            router["context_window_fallbacks"],
            next(f for f in router["fallbacks"] if "devops-coder" in f),
        ) == (
            True,
            [
                {"devops-chat": ["devops-coder", "devops-reasoning"]},
                {"devops-coder": ["devops-reasoning"]},
            ],
            {"devops-coder": ["devops-reasoning", "devops-chat"]},
        )

    def test_gateway_review_pool_spans_ollama_backends(self) -> None:
        """Verify devops-review shares requests across Ollama backends with appropriate weights and zero retries."""
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
                "http://ollama-48gib-fast.llm.svc.cluster.local:11434": 9,
                "http://ollama-64gib-standard.llm.svc.cluster.local:11434": 6,
                "http://ollama-16gib-fast.llm.svc.cluster.local:11434": 6,
            },
            [0, 0, 0],
        )

    @pytest.mark.parametrize("group", ["qwen3-coder:30b", "gpt-oss:20b"])
    def test_a_review_model_has_a_group_of_its_review_deployments_alone(self, group: str) -> None:
        """Verify each model devops-review serves can be pinned: its own group copies that model's
        devops-review deployments (model, backend and weight, in order) with no window that would
        route it differently from the pool, and no fallback reaches or leaves it (#475).

        No other group gives that backend model a window either. LiteLLM v1.103.0 writes a
        deployment's top-level model_info into the cost-map entry that every deployment of the
        same backend model reads, so the window would become the pinned group's too (#1064)."""
        backend = f"ollama_chat/{group}"
        model_list = _gateway_config()["model_list"]
        review = [
            m for m in _deployments("devops-review") if m["litellm_params"]["model"] == backend
        ]
        pinned = _deployments(group)
        router = _gateway_config()["router_settings"]
        fallback_groups = {
            name
            for rule in [*router["fallbacks"], *router["context_window_fallbacks"]]
            for source, targets in rule.items()
            for name in (source, *targets)
        }
        groups_windowing_the_backend = [
            m["model_name"]
            for m in model_list
            if m["litellm_params"]["model"] == backend
            and "max_input_tokens" in (m.get("model_info") or {})
        ]

        assert (
            bool(review),
            _routes(pinned),
            [(sorted(m), sorted(m["litellm_params"])) for m in pinned],
            group in fallback_groups,
            groups_windowing_the_backend,
        ) == (
            True,
            _routes(review),
            [(["litellm_params", "model_name"], ["api_base", "model", "num_retries", "weight"])]
            * len(review),
            False,
            [],
        )

    def test_gateway_routes_to_provider_vram_services(self) -> None:
        """Verify Gateway routes target standardized <llm_provider>-<vram_gib> services."""
        chat_deployments = _deployments("devops-chat")
        bge_deployments = _deployments("bge-m3:latest")

        assert (
            sorted(m["litellm_params"]["api_base"] for m in chat_deployments),
            [m["litellm_params"]["api_base"] for m in bge_deployments],
            [m.get("model_info", {}).get("mode") for m in bge_deployments],
        ) == (
            [
                "http://ollama-16gib-fast.llm.svc.cluster.local:11434",
                "http://ollama-48gib-fast.llm.svc.cluster.local:11434",
                "http://ollama-64gib-standard.llm.svc.cluster.local:11434",
            ],
            ["http://ollama-48gib-slow.llm.svc.cluster.local:11434"],
            ["embedding"],
        )

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
        cm = _load_kind(GATEWAY_DIR / "configmap.yaml", "ConfigMap")
        cfg = yaml.safe_load(cm["data"]["config.yaml"])

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
        """Verify Open WebUI uses the gateway as its OpenAI connection with the shared master key."""
        values = yaml.safe_load(OPEN_WEBUI_VALUES.read_text(encoding="utf-8"))

        assert (
            values["enableOpenaiApi"],
            values["openaiBaseApiUrl"],
            values["openaiApiKeyExistingSecret"],
            values["openaiApiKeyExistingSecretKey"],
            values["ollamaUrls"],
        ) == (
            True,
            DEFAULT_AI_GATEWAY_CLUSTER_URL,
            GATEWAY_SECRET,
            GATEWAY_SECRET_KEY,
            [
                "http://ollama-24gib.llm.svc.cluster.local:11434",
                "http://ollama-64gib.llm.svc.cluster.local:11434",
            ],
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

    def test_every_ollama_tier_keeps_one_model_and_serves_one_request(self) -> None:
        """Verify each tier reserves KV cache for one context: Ollama sizes it by NUM_PARALLEL (#1061).

        The slow tier is the exception on residency alone: it keeps its embedding model and its
        one background model loaded together, for good, so neither evicts the other (#1064).
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
        expected = {
            name: {"OLLAMA_MAX_LOADED_MODELS": "1", "OLLAMA_NUM_PARALLEL": "1"} for name in settings
        }
        expected["ollama-48gib-slow"] = {
            "OLLAMA_MAX_LOADED_MODELS": "2",
            "OLLAMA_NUM_PARALLEL": "1",
            "OLLAMA_KEEP_ALIVE": "-1",
        }

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
            {"/home/ollama/.ollama": "ollama-data", "/tmp": "tmp"},
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

    def test_vllm_profiles_network_policy_secures_perimeter(self) -> None:
        """Verify vLLM profiles admit only the gateway and monitoring, and egress is isolated."""
        netpol = _load_kind(NETWORKPOLICY_MANIFEST, "NetworkPolicy")
        ingress = netpol["spec"]["ingress"]
        egress_namespaces = sorted(
            peer["namespaceSelector"]["matchLabels"]["kubernetes.io/metadata.name"]
            for rule in netpol["spec"]["egress"]
            for peer in rule["to"]
            if "namespaceSelector" in peer
        )

        assert (
            netpol["spec"]["podSelector"]["matchLabels"]["llm.devops.io/provider"],
            ingress[0]["from"][0]["podSelector"]["matchLabels"]["app.kubernetes.io/name"],
            ingress[0]["ports"][0]["port"],
            ingress[1]["from"][0]["namespaceSelector"]["matchLabels"][
                "kubernetes.io/metadata.name"
            ],
            egress_namespaces,
        ) == (
            "vllm",
            "llm-gateway",
            8000,
            "monitoring",
            ["kube-system"],
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
                "networkpolicy.yaml",
            ],
        )

    def test_llm_namespace_default_perimeter_excludes_gateway_and_vllm(self) -> None:
        """Verify llm-default-perimeter excludes gateway, vLLM, portkey, and the run index
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
            ["llm-gateway", "portkey", "valkey-runs", "vllm", "vllm-single"],
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

        The backends are read from the manifests: each ConfigMap `api_base` and the Deployment's
        Valkey host. Each must be a Service under k8s/llm with a selector, and some egress rule
        must select a subset of that selector on the Service's numeric targetPort. The test used
        to pin four selector names, two of which match no pod, and never read the ConfigMap.
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


# The gateway policy's vLLM rule matches no deployed pod; #820 deletes the rule and this constant.
_VLLM_SELECTORS: tuple[dict[str, str], ...] = (
    {"app.kubernetes.io/name": "vllm"},
    {"app.kubernetes.io/name": "vllm-single"},
    {"llm.devops.io/provider": "vllm"},
)
_VLLM_PORTS = frozenset({("TCP", 8000, None)})
_DNS_PEER = {"namespaceSelector": {"matchLabels": {"kubernetes.io/metadata.name": "kube-system"}}}
_DNS_PORTS = frozenset({("UDP", 53, None), ("TCP", 53, None)})
_OLLAMA_PEER = {"podSelector": {"matchLabels": {"llm.devops.io/provider": "ollama"}}}

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

    The backends are every `api_base` in the gateway ConfigMap and the Deployment's
    LITELLM_REDIS_HOST and LITELLM_REDIS_PORT. A backend maps to None unless its host names a
    Service under k8s/llm that has a selector and a numeric targetPort on the port it calls.
    """
    deployment = _load_kind(GATEWAY_DIR / "deployment.yaml", "Deployment")
    env = {
        variable["name"]: variable.get("value")
        for variable in deployment["spec"]["template"]["spec"]["containers"][0]["env"]
    }
    api_bases = {
        urlsplit(model["litellm_params"].get("api_base", ""))
        for model in _gateway_config()["model_list"]
    }
    addresses = {(url.hostname, url.port) for url in api_bases} | {
        (env["LITELLM_REDIS_HOST"], int(env["LITELLM_REDIS_PORT"]))
    }
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
    labels = _pod_labels(peer)
    if not labels:
        return f"{peer} is not a same-namespace podSelector with matchLabels alone"
    if labels in _VLLM_SELECTORS:
        return None if ports == _VLLM_PORTS else f"vLLM selector {labels} admits other ports"
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
    `to` and `ports`. A peer is the kube-system DNS peer on UDP and TCP 53, one of the vLLM
    selectors on TCP 8000, or a same-namespace podSelector whose labels are a subset of some
    backend Service's selector, on those backends' targetPorts alone. No ipBlock passes.
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
    """The gateway reaches its backends, DNS and the vLLM rule #820 removes, and nothing else.

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
