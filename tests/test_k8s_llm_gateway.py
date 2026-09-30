"""Manifest syntax, security perimeter, and zero-leakage validation for LLM Gateway and vLLM."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest
import yaml

from devops_cli.config.defaults import DEFAULT_AI_GATEWAY_CLUSTER_URL

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


def _deployments(group: str) -> list[dict[str, Any]]:
    """Return the gateway deployments of one model group, in configuration order."""
    cm = _load_kind(GATEWAY_DIR / "configmap.yaml", "ConfigMap")
    cfg = yaml.safe_load(cm["data"]["config.yaml"])
    return [m for m in cfg["model_list"] if m["model_name"] == group]


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
            len(cfg["router_settings"]["fallbacks"]),
        ) == (
            "llm-gateway-config",
            [
                "devops-chat",
                "devops-coder",
                "devops-reasoning",
                "bge-m3:latest",
                "embeddinggemma:300m",
                "devops-review",
                "gemma4:31b",
                "qwen3.8:27b",
                "deepseek-r1:70b",
            ],
            "simple-shuffle",
            2,
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
            "http://ollama-48gib.llm.svc.cluster.local:11434",
            "ollama_chat/qwen3-coder:30b",
            "http://ollama-48gib.llm.svc.cluster.local:11434",
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
        """Verify devops-review shares requests across Ollama backends with appropriate weights."""
        deployments = _deployments("devops-review")
        weights = {
            m["litellm_params"]["api_base"]: m["litellm_params"].get("weight") for m in deployments
        }
        assert weights == {
            "http://ollama-48gib.llm.svc.cluster.local:11434": 9,
            "http://ollama-64gib.llm.svc.cluster.local:11434": 6,
            "http://ollama-16gib.llm.svc.cluster.local:11434": 8,
            "http://ollama-24gib.llm.svc.cluster.local:11434": 1,
        }

    def test_gateway_routes_to_provider_vram_services(self) -> None:
        """Verify Gateway routes target standardized <llm_provider>-<vram_gib> services."""
        chat_deployments = _deployments("devops-chat")
        bge_deployments = _deployments("bge-m3:latest")
        gemma_deployments = _deployments("embeddinggemma:300m")

        assert (
            sorted(m["litellm_params"]["api_base"] for m in chat_deployments),
            sorted(m["litellm_params"]["api_base"] for m in bge_deployments),
            sorted(m["litellm_params"]["api_base"] for m in gemma_deployments),
            all(m.get("model_info", {}).get("mode") == "embedding" for m in bge_deployments),
            all(m.get("model_info", {}).get("mode") == "embedding" for m in gemma_deployments),
        ) == (
            [
                "http://ollama-16gib.llm.svc.cluster.local:11434",
                "http://ollama-24gib.llm.svc.cluster.local:11434",
                "http://ollama-48gib.llm.svc.cluster.local:11434",
                "http://ollama-64gib.llm.svc.cluster.local:11434",
            ],
            [
                "http://ollama-16gib.llm.svc.cluster.local:11434",
                "http://ollama-24gib.llm.svc.cluster.local:11434",
            ],
            [
                "http://ollama-16gib.llm.svc.cluster.local:11434",
                "http://ollama-24gib.llm.svc.cluster.local:11434",
            ],
            True,
            True,
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
            cfg["router_settings"]["timeout"] >= 600,
        ) == (
            "os.environ/LITELLM_MASTER_KEY",
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

    def test_zero_homelab_ip_or_hostname_leakage(self) -> None:
        """Verify no private RFC 1918 IPs or *.lan hostnames exist in Gateway/profiles manifests."""
        all_yaml_files = [
            *GATEWAY_DIR.glob("*.yaml"),
            *PROFILES_DIR.glob("*.yaml"),
        ]
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
        """Verify the gateway's network policy admits egress to all backends configured in configmap."""
        netpol = _load_kind(GATEWAY_DIR / "networkpolicy.yaml", "NetworkPolicy")

        egress_selectors = [
            peer["podSelector"]["matchLabels"]
            for rule in netpol["spec"]["egress"]
            if "to" in rule
            for peer in rule["to"]
            if "podSelector" in peer
        ]
        allowed_names = {
            sel["app.kubernetes.io/name"]
            for sel in egress_selectors
            if "app.kubernetes.io/name" in sel
        }
        allowed_providers = {
            sel["llm.devops.io/provider"]
            for sel in egress_selectors
            if "llm.devops.io/provider" in sel
        }

        assert (
            "ollama-volta-1" in allowed_names,
            "ollama" in allowed_names,
            "vllm" in allowed_names,
            "vllm-single" in allowed_names,
            "valkey" in allowed_names,
            "ollama" in allowed_providers,
            "vllm" in allowed_providers,
        ) == (True, True, True, True, True, True, True)
