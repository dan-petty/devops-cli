"""Manifest syntax, security perimeter, and zero-leakage validation for LLM Gateway and vLLM."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, cast

import pytest
import yaml

from devops_cli.config.defaults import (
    DEFAULT_AI_GATEWAY_CLUSTER_URL,
    DEFAULT_VLLM_CLUSTER_URL,
    DEFAULT_VLLM_MODEL,
    DEFAULT_VLLM_SERVED_MODEL_NAME,
    DEFAULT_VLLM_SINGLE_CLUSTER_URL,
    DEFAULT_VLLM_SINGLE_MODEL,
    DEFAULT_VLLM_SINGLE_SERVED_MODEL_NAME,
)

GATEWAY_DIR = Path("k8s/llm/gateway")
PROFILES_DIR = Path("k8s/llm/profiles")
VLLM_PROFILES_MANIFEST = PROFILES_DIR / "vllm-profiles.yaml"
OLLAMA_PROFILES_MANIFEST = PROFILES_DIR / "ollama-profiles.yaml"
SERVICES_MANIFEST = PROFILES_DIR / "services.yaml"
PVC_MANIFEST = PROFILES_DIR / "pvc.yaml"
NETWORKPOLICY_MANIFEST = PROFILES_DIR / "networkpolicy.yaml"
LLM_KUSTOMIZATION = Path("k8s/llm/kustomization.yaml")
OPEN_WEBUI_VALUES = Path("k8s/llm/values-open-webui.yaml")

GATEWAY_IMAGE = "ghcr.io/berriai/litellm:v1.102.1"
GATEWAY_SECRET = "llm-gateway-secrets"
GATEWAY_SECRET_KEY = "master-key"

VLLM_IMAGE = "vllm/vllm-openai:v0.30.0"
VLLM_ARCHITECTURES = ["ada-lovelace", "ampere", "blackwell", "hopper"]
GPU_ARCHITECTURE_LABELS = ["nvidia.com/gpu.architecture", "nvidia.com/gpu.family"]
CA_BUNDLE = "/etc/ssl/bundle/ca-certificates.crt"
SQUID_PROXY = "http://squid.squid.svc.cluster.local:3128"


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


def _load_pvc(path: Path, name: str) -> dict[str, Any]:
    """Return the PersistentVolumeClaim with the given metadata.name from a multi-document manifest."""
    docs = yaml.safe_load_all(path.read_text(encoding="utf-8"))
    return next(
        d
        for d in docs
        if d and d.get("kind") == "PersistentVolumeClaim" and d["metadata"]["name"] == name
    )


def _flag(args: list[str], flag: str) -> str | None:
    """Return the value following a CLI flag, or None when the flag is absent."""
    return args[args.index(flag) + 1] if flag in args else None


def _vllm_container(dep: dict[str, Any]) -> dict[str, Any]:
    """Return the vLLM serving container of a Deployment."""
    return next(c for c in dep["spec"]["template"]["spec"]["containers"] if c["name"] == "vllm")


def _deployments(group: str) -> list[dict[str, Any]]:
    """Return the gateway deployments of one model group, in configuration order."""
    cm = _load_kind(GATEWAY_DIR / "configmap.yaml", "ConfigMap")
    cfg = yaml.safe_load(cm["data"]["config.yaml"])
    return [m for m in cfg["model_list"] if m["model_name"] == group]


def _node_selector_terms(pod_spec: dict[str, Any]) -> list[dict[str, Any]]:
    """Return required node affinity terms of a pod spec."""
    affinity = pod_spec["affinity"]["nodeAffinity"]
    return cast(
        list[dict[str, Any]],
        affinity["requiredDuringSchedulingIgnoredDuringExecution"]["nodeSelectorTerms"],
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
            len(cfg["router_settings"]["fallbacks"]),
        ) == (
            "llm-gateway-config",
            [
                "devops-chat",
                "devops-coder",
                "devops-reasoning",
                "devops-embedding",
                "devops-review",
                "devops-flagship",
                "gemma4:31b",
                "ollama/*",
            ],
            "simple-shuffle",
            2,
        )

    def test_gateway_configmap_routes_vllm_profiles_by_served_model_name(self) -> None:
        """Verify reasoning and coder aliases reach the dual-GPU vLLM profile."""
        cm = _load_kind(GATEWAY_DIR / "configmap.yaml", "ConfigMap")
        cfg = yaml.safe_load(cm["data"]["config.yaml"])
        params = {m["model_name"]: m["litellm_params"] for m in cfg["model_list"]}

        assert (
            params["devops-reasoning"]["model"],
            params["devops-reasoning"]["api_base"],
            params["devops-coder"]["model"],
            params["devops-coder"]["api_base"],
        ) == (
            f"openai/{DEFAULT_VLLM_SERVED_MODEL_NAME}",
            DEFAULT_VLLM_CLUSTER_URL,
            f"openai/{DEFAULT_VLLM_SINGLE_SERVED_MODEL_NAME}",
            DEFAULT_VLLM_SINGLE_CLUSTER_URL,
        )

    def test_gateway_escalates_to_larger_models_and_prefers_vllm_on_outage(self) -> None:
        """Verify long prompts escalate by context window and an unavailable coder falls back to reasoning first."""
        cm = _load_kind(GATEWAY_DIR / "configmap.yaml", "ConfigMap")
        cfg = yaml.safe_load(cm["data"]["config.yaml"])
        router = cfg["router_settings"]
        input_limits = {
            m["model_name"]: m["model_info"]["max_input_tokens"]
            for m in cfg["model_list"]
            if m["model_name"] in ("devops-coder", "devops-reasoning")
        }
        vllm_windows = {
            "devops-coder": _flag(
                _vllm_container(_load_deployment(VLLM_PROFILES_MANIFEST, "vllm-16gib"))["args"],
                "--max-model-len",
            ),
            "devops-reasoning": _flag(
                _vllm_container(_load_deployment(VLLM_PROFILES_MANIFEST, "vllm-48gib"))["args"],
                "--max-model-len",
            ),
        }

        assert (
            router["enable_pre_call_checks"],
            router["context_window_fallbacks"],
            next(f for f in router["fallbacks"] if "devops-coder" in f),
            input_limits["devops-coder"] < input_limits["devops-reasoning"],
            all(limit < int(vllm_windows[name] or 0) for name, limit in input_limits.items()),
        ) == (
            True,
            [
                {"devops-chat": ["devops-coder", "devops-reasoning"]},
                {"devops-coder": ["devops-reasoning"]},
            ],
            {"devops-coder": ["devops-reasoning", "devops-chat"]},
            True,
            True,
        )

    def test_gateway_review_pool_spans_every_inference_backend(self) -> None:
        """Verify devops-review spans vLLM and Ollama within each backend's context window."""
        cm = _load_kind(GATEWAY_DIR / "configmap.yaml", "ConfigMap")
        cfg = yaml.safe_load(cm["data"]["config.yaml"])
        pool = {
            m["litellm_params"]["api_base"]: m
            for m in cfg["model_list"]
            if m["model_name"] == "devops-review"
        }
        ollama_dep = _load_deployment(OLLAMA_PROFILES_MANIFEST, "ollama-64gib")
        ollama_env = {
            e["name"]: e.get("value")
            for e in ollama_dep["spec"]["template"]["spec"]["containers"][0]["env"]
        }
        ollama_window = int(ollama_env["OLLAMA_CONTEXT_LENGTH"] or 0)
        vllm_dep = _load_deployment(VLLM_PROFILES_MANIFEST, "vllm-48gib")
        vllm_window = int(
            _flag(
                _vllm_container(vllm_dep)["args"],
                "--max-model-len",
            )
            or 0
        )
        ollama_64gib_url = "http://ollama-64gib.llm.svc.cluster.local:11434/v1"
        windows = {
            DEFAULT_VLLM_CLUSTER_URL: vllm_window,
            ollama_64gib_url: ollama_window,
        }

        assert (
            sorted(pool),
            all(m["model_info"]["max_input_tokens"] < windows[base] for base, m in pool.items()),
            pool[DEFAULT_VLLM_CLUSTER_URL]["model_info"]["max_input_tokens"],
            pool[ollama_64gib_url]["model_info"]["max_input_tokens"],
        ) == (
            sorted(windows),
            True,
            61440,
            43904,
        )

    def test_gateway_review_pool_weights_and_concurrency_caps(self) -> None:
        """Verify devops-review shares requests across inference backends with appropriate weights and caps."""
        deployments = _deployments("devops-review")
        weights = {
            m["litellm_params"]["api_base"]: m["litellm_params"].get("weight") for m in deployments
        }
        caps = {
            m["litellm_params"]["api_base"]: m["litellm_params"].get("max_parallel_requests")
            for m in deployments
        }
        ollama_64gib_url = "http://ollama-64gib.llm.svc.cluster.local:11434/v1"
        assert (
            weights[DEFAULT_VLLM_CLUSTER_URL],
            weights[ollama_64gib_url],
            caps[DEFAULT_VLLM_CLUSTER_URL],
            caps[ollama_64gib_url],
        ) == (
            6,
            1,
            None,
            None,
        )

    def test_gateway_routes_to_provider_vram_services(self) -> None:
        """Verify Gateway routes target standardized <llm_provider>-<vram_gib> services."""
        chat_deployments = _deployments("devops-chat")
        embedding_deployments = _deployments("devops-embedding")
        passthrough_deployments = _deployments("ollama/*")

        assert (
            [m["litellm_params"]["api_base"] for m in chat_deployments],
            [m["litellm_params"]["api_base"] for m in embedding_deployments],
            [m["litellm_params"]["api_base"] for m in passthrough_deployments],
        ) == (
            ["http://ollama-24gib.llm.svc.cluster.local:11434"],
            ["http://ollama-24gib.llm.svc.cluster.local:11434"],
            ["http://ollama-24gib.llm.svc.cluster.local:11434/v1"],
        )

    def test_gateway_health_checks_probe_each_deployment_the_way_it_is_called(self) -> None:
        """Verify embedding deployments are probed as embeddings and the wildcard with a real model."""
        passthrough = _deployments("ollama/*")[0]
        health_model = passthrough["model_info"]["health_check_model"]
        chat_model = _deployments("devops-chat")[0]["litellm_params"]["model"].split("/", 1)[1]

        assert (
            {m.get("model_info", {}).get("mode") for m in _deployments("devops-embedding")},
            health_model,
        ) == (
            {"embedding"},
            f"openai/{chat_model}",
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

    def test_vllm_deployment_serves_qwen_coder_with_tensor_parallelism(self) -> None:
        """Verify the dual-GPU profile serves Qwen3-Coder-30B AWQ at TP=2 with 64K context."""
        dep = _load_deployment(VLLM_PROFILES_MANIFEST, "vllm-48gib")
        container = _vllm_container(dep)
        args = container["args"]

        assert (
            container["image"],
            container["command"],
            args[0],
            _flag(args, "--served-model-name"),
            _flag(args, "--tensor-parallel-size"),
            _flag(args, "--max-model-len"),
            _flag(args, "--gpu-memory-utilization"),
            _flag(args, "--max-num-seqs"),
            "--enable-auto-tool-choice" in args,
            _flag(args, "--tool-call-parser"),
            "--quantization" in args,
            container["resources"]["limits"]["nvidia.com/gpu"],
            container["resources"]["limits"]["memory"],
            dep["kind"],
            dep["spec"]["updateStrategy"]["type"],
        ) == (
            VLLM_IMAGE,
            ["vllm", "serve"],
            DEFAULT_VLLM_MODEL,
            DEFAULT_VLLM_SERVED_MODEL_NAME,
            "2",
            "65536",
            "0.95",
            "64",
            True,
            "hermes",
            False,
            "2",
            "48Gi",
            "DaemonSet",
            "RollingUpdate",
        )

    def test_vllm_single_deployment_fits_one_16gib_gpu(self) -> None:
        """Verify the single-GPU profile serves Qwen2.5-Coder-14B AWQ with an FP8 KV cache."""
        dep = _load_deployment(VLLM_PROFILES_MANIFEST, "vllm-16gib")
        container = _vllm_container(dep)
        args = container["args"]

        assert (
            dep["metadata"]["name"],
            container["image"],
            container["command"],
            args[0],
            _flag(args, "--served-model-name"),
            "--tensor-parallel-size" in args,
            _flag(args, "--max-model-len"),
            _flag(args, "--kv-cache-dtype"),
            _flag(args, "--gpu-memory-utilization"),
            _flag(args, "--max-num-seqs"),
            "--enable-auto-tool-choice" in args,
            _flag(args, "--tool-call-parser"),
            container["resources"]["limits"]["nvidia.com/gpu"],
            container["resources"]["limits"]["memory"],
            dep["kind"],
            dep["spec"]["updateStrategy"]["type"],
        ) == (
            "vllm-16gib",
            VLLM_IMAGE,
            ["vllm", "serve"],
            DEFAULT_VLLM_SINGLE_MODEL,
            DEFAULT_VLLM_SINGLE_SERVED_MODEL_NAME,
            False,
            "16384",
            "fp8",
            "0.95",
            "16",
            True,
            "hermes",
            "1",
            "12Gi",
            "DaemonSet",
            "RollingUpdate",
        )

    @pytest.mark.parametrize(
        ("deployment_name", "expected_vram"),
        [
            ("vllm-16gib", "16Gi"),
            ("vllm-24gib", "24Gi"),
            ("vllm-32gib", "32Gi"),
            ("vllm-48gib", "48Gi"),
            ("vllm-64gib", "64Gi"),
            ("vllm-72gib", "72Gi"),
            ("vllm-96gib", "96Gi"),
            ("vllm-128gib", "128Gi"),
        ],
    )
    def test_vllm_profiles_select_total_vram_and_architecture(
        self, deployment_name: str, expected_vram: str
    ) -> None:
        """Verify each vLLM profile targets Ampere-or-newer GPUs and matching total VRAM under either GPU label scheme."""
        dep = _load_deployment(VLLM_PROFILES_MANIFEST, deployment_name)
        terms = _node_selector_terms(dep["spec"]["template"]["spec"])
        summary = sorted(
            (
                arch["key"],
                arch["operator"],
                sorted(arch["values"]),
                vram["key"],
                vram["operator"],
                vram["values"],
            )
            for term in terms
            for arch in term["matchExpressions"]
            if arch["key"] in GPU_ARCHITECTURE_LABELS
            for vram in term["matchExpressions"]
            if vram["key"] == "nvidia.com/gpu.total-vram-gib"
        )

        assert summary == [
            (
                label,
                "In",
                VLLM_ARCHITECTURES,
                "nvidia.com/gpu.total-vram-gib",
                "In",
                [expected_vram],
            )
            for label in GPU_ARCHITECTURE_LABELS
        ]

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

    @pytest.mark.parametrize("deployment_name", ["vllm-16gib", "vllm-48gib"])
    def test_vllm_profiles_trust_squid_ca_and_persist_model_cache(
        self, deployment_name: str
    ) -> None:
        """Verify vLLM downloads through the SSL-bumping proxy, keeps weights, and tolerates long loads."""
        dep = _load_deployment(VLLM_PROFILES_MANIFEST, deployment_name)
        spec = dep["spec"]["template"]["spec"]
        container = _vllm_container(dep)
        init = next(c for c in spec["initContainers"] if c["name"] == "ca-bundle")
        env = {e["name"]: e.get("value") for e in container["env"]}
        volumes = {v["name"]: v for v in spec["volumes"]}
        startup = container["startupProbe"]
        pvc = _load_pvc(PVC_MANIFEST, volumes["model-cache"]["persistentVolumeClaim"]["claimName"])

        assert (
            spec["enableServiceLinks"],
            init["image"] == container["image"],
            "/etc/ssl/squid-ca/squid-ca.pem" in " ".join(init["command"]),
            env["SSL_CERT_FILE"],
            env["REQUESTS_CA_BUNDLE"],
            env["HTTPS_PROXY"],
            env["HF_HUB_DISABLE_XET"],
            volumes["squid-ca-cert"]["configMap"]["name"],
            volumes["model-cache"]["persistentVolumeClaim"]["claimName"],
            pvc["spec"]["accessModes"],
            "storageClassName" in pvc["spec"],
            startup["httpGet"]["path"],
            startup["periodSeconds"] * startup["failureThreshold"] >= 1800,
        ) == (
            False,
            True,
            True,
            CA_BUNDLE,
            CA_BUNDLE,
            SQUID_PROXY,
            "1",
            "squid-ca-cert",
            pvc["metadata"]["name"],
            ["ReadWriteOnce"],
            False,
            "/health",
            True,
        )

    @pytest.mark.parametrize("service_name", ["vllm-16gib", "vllm-48gib"])
    def test_vllm_services_stay_behind_the_gateway(self, service_name: str) -> None:
        """Verify vLLM Services are cluster-internal; LAN clients use the authenticated gateway."""
        svc = _load_service(SERVICES_MANIFEST, service_name)
        dep = _load_deployment(VLLM_PROFILES_MANIFEST, service_name)

        assert (
            svc["spec"]["type"],
            svc["spec"]["ports"][0]["port"],
            svc["spec"]["selector"]["llm.devops.io/provider"],
        ) == (
            "ClusterIP",
            8000,
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
            ["kube-system", "squid"],
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
                "vllm-profiles.yaml",
                "pvc.yaml",
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

    def test_no_proxy_exempts_rfc1918_and_local_domains(self) -> None:
        """Verify NO_PROXY in gateway deployment exempts RFC 1918 CIDRs, .lan, and .local domains."""
        dep = _load_kind(GATEWAY_DIR / "deployment.yaml", "Deployment")
        container = dep["spec"]["template"]["spec"]["containers"][0]
        env = {e["name"]: e["value"] for e in container.get("env", []) if "value" in e}
        no_proxy = env.get("NO_PROXY", "")

        assert (
            "10.0.0.0/8" in no_proxy,
            "172.16.0.0/12" in no_proxy,
            "192.168.0.0/16" in no_proxy,
            ".lan" in no_proxy,
            ".local" in no_proxy,
            "*.ollama-nodes.llm.svc.cluster.local" in no_proxy,
            "ollama-volta-1.llm.svc.cluster.local" in no_proxy,
        ) == (
            True,
            True,
            True,
            True,
            True,
            True,
            True,
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
