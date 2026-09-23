"""Manifest syntax, security perimeter, and zero-leakage validation for LLM Gateway and vLLM."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

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
VLLM_DIR = Path("k8s/llm/vllm")
VLLM_SINGLE_DIR = Path("k8s/llm/vllm-single")
OLLAMA_MANIFEST = Path("k8s/llm/ollama.yaml")
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


def _flag(args: list[str], flag: str) -> str | None:
    """Return the value following a CLI flag, or None when the flag is absent."""
    return args[args.index(flag) + 1] if flag in args else None


def _vllm_container(dep: dict[str, Any]) -> dict[str, Any]:
    """Return the vLLM serving container of a Deployment."""
    return next(c for c in dep["spec"]["template"]["spec"]["containers"] if c["name"] == "vllm")


def _ollama_pod_urls() -> list[str]:
    """Return the per-pod URL of every Ollama StatefulSet replica, via its headless Service."""
    sts = _load_kind(OLLAMA_MANIFEST, "StatefulSet")
    service = sts["spec"]["serviceName"]
    return [
        f"http://ollama-{n}.{service}.llm.svc.cluster.local:11434"
        for n in range(sts["spec"]["replicas"])
    ]


def _deployments(group: str) -> list[dict[str, Any]]:
    """Return the gateway deployments of one model group, in configuration order."""
    cm = _load_kind(GATEWAY_DIR / "configmap.yaml", "ConfigMap")
    cfg = yaml.safe_load(cm["data"]["config.yaml"])
    return [m for m in cfg["model_list"] if m["model_name"] == group]


def _node_selector_terms(pod_spec: dict[str, Any]) -> list[dict[str, Any]]:
    """Return required node affinity terms of a pod spec."""
    affinity = pod_spec["affinity"]["nodeAffinity"]
    return affinity["requiredDuringSchedulingIgnoredDuringExecution"]["nodeSelectorTerms"]


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
                "ollama/*",
            ],
            "least-busy",
            2,
        )

    def test_gateway_configmap_routes_vllm_profiles_by_served_model_name(self) -> None:
        """Verify reasoning and coder aliases reach the dual- and single-GPU vLLM profiles."""
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
                _vllm_container(_load_kind(VLLM_SINGLE_DIR / "deployment.yaml", "Deployment"))[
                    "args"
                ],
                "--max-model-len",
            ),
            "devops-reasoning": _flag(
                _vllm_container(_load_kind(VLLM_DIR / "deployment.yaml", "Deployment"))["args"],
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
        """Verify devops-review load-balances over vLLM and Ollama within each backend's limits."""
        cm = _load_kind(GATEWAY_DIR / "configmap.yaml", "ConfigMap")
        cfg = yaml.safe_load(cm["data"]["config.yaml"])
        pool = {
            m["litellm_params"]["api_base"]: m
            for m in cfg["model_list"]
            if m["model_name"] == "devops-review"
        }
        ollama_env = {
            e["name"]: e.get("value")
            for e in _load_kind(OLLAMA_MANIFEST, "StatefulSet")["spec"]["template"]["spec"][
                "containers"
            ][0]["env"]
        }
        ollama_window = int(ollama_env["OLLAMA_CONTEXT_LENGTH"] or 0)
        windows = {
            DEFAULT_VLLM_CLUSTER_URL: int(
                _flag(
                    _vllm_container(_load_kind(VLLM_DIR / "deployment.yaml", "Deployment"))["args"],
                    "--max-model-len",
                )
                or 0
            ),
            DEFAULT_VLLM_SINGLE_CLUSTER_URL: int(
                _flag(
                    _vllm_container(_load_kind(VLLM_SINGLE_DIR / "deployment.yaml", "Deployment"))[
                        "args"
                    ],
                    "--max-model-len",
                )
                or 0
            ),
            **dict.fromkeys(_ollama_pod_urls(), ollama_window),
        }

        assert (
            sorted(pool),
            all(m["litellm_params"]["max_parallel_requests"] >= 1 for m in pool.values()),
            all(m["model_info"]["max_input_tokens"] < windows[base] for base, m in pool.items()),
        ) == (
            sorted(windows),
            True,
            True,
        )

    def test_gateway_lists_one_deployment_per_ollama_pod(self) -> None:
        """Verify each Ollama-backed group has one deployment per StatefulSet pod.

        The `ollama` Service would pin all gateway traffic to one pod, because LiteLLM keeps its
        connections open; per-pod deployments let LiteLLM balance and cool down each node.
        """
        ollama_env = {
            e["name"]: e.get("value")
            for e in _load_kind(OLLAMA_MANIFEST, "StatefulSet")["spec"]["template"]["spec"][
                "containers"
            ][0]["env"]
        }
        review_ollama = [
            m for m in _deployments("devops-review") if "ollama" in m["litellm_params"]["model"]
        ]

        assert (
            [m["litellm_params"]["api_base"] for m in _deployments("devops-chat")],
            [m["litellm_params"]["api_base"] for m in _deployments("devops-embedding")],
            [m["litellm_params"]["api_base"] for m in review_ollama],
            [m["litellm_params"]["api_base"] for m in _deployments("ollama/*")],
            {m["litellm_params"]["max_parallel_requests"] for m in review_ollama},
        ) == (
            _ollama_pod_urls(),
            _ollama_pod_urls(),
            _ollama_pod_urls(),
            [f"{url}/v1" for url in _ollama_pod_urls()],
            {int(ollama_env["OLLAMA_NUM_PARALLEL"] or 0)},
        )

    def test_gateway_health_checks_probe_each_deployment_the_way_it_is_called(self) -> None:
        """Verify embedding deployments are probed as embeddings and the wildcard with a real model.

        LiteLLM probes with a chat completion by default, which embedding-only models reject, and
        probes a wildcard with a placeholder model name that no Ollama node has.
        """
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
        ) == (
            True,
            DEFAULT_AI_GATEWAY_CLUSTER_URL,
            GATEWAY_SECRET,
            GATEWAY_SECRET_KEY,
        )

    def test_vllm_deployment_serves_qwen_coder_with_tensor_parallelism(self) -> None:
        """Verify the dual-GPU profile serves Qwen2.5-Coder-32B AWQ at TP=2 with YaRN 64K context."""
        dep = _load_kind(VLLM_DIR / "deployment.yaml", "Deployment")
        container = _vllm_container(dep)
        args = container["args"]
        overrides = json.loads(_flag(args, "--hf-overrides") or "{}")
        rope = overrides["rope_parameters"]

        assert (
            container["image"],
            container["command"],
            args[0],
            _flag(args, "--served-model-name"),
            _flag(args, "--tensor-parallel-size"),
            _flag(args, "--max-model-len"),
            (
                rope["rope_type"],
                rope["factor"],
                rope["original_max_position_embeddings"],
                rope["rope_theta"],
            ),
            int(rope["factor"] * rope["original_max_position_embeddings"]),
            # vLLM expects YaRN models to carry the already-extended length here.
            overrides["max_position_embeddings"],
            _flag(args, "--gpu-memory-utilization"),
            _flag(args, "--max-num-seqs"),
            "--quantization" in args,
            container["resources"]["limits"]["nvidia.com/gpu"],
            container["resources"]["limits"]["memory"],
            dep["spec"]["strategy"]["type"],
        ) == (
            VLLM_IMAGE,
            ["vllm", "serve"],
            DEFAULT_VLLM_MODEL,
            DEFAULT_VLLM_SERVED_MODEL_NAME,
            "2",
            "65536",
            ("yarn", 2.0, 32768, 1000000),
            65536,
            65536,
            "0.95",
            "64",
            False,
            "2",
            "48Gi",
            "Recreate",
        )

    def test_vllm_single_deployment_fits_one_16gib_gpu(self) -> None:
        """Verify the single-GPU profile serves Qwen2.5-Coder-14B AWQ with an FP8 KV cache."""
        dep = _load_kind(VLLM_SINGLE_DIR / "deployment.yaml", "Deployment")
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
            container["resources"]["limits"]["nvidia.com/gpu"],
            container["resources"]["limits"]["memory"],
            dep["spec"]["strategy"]["type"],
        ) == (
            "vllm-single",
            VLLM_IMAGE,
            ["vllm", "serve"],
            DEFAULT_VLLM_SINGLE_MODEL,
            DEFAULT_VLLM_SINGLE_SERVED_MODEL_NAME,
            False,
            "16384",
            "fp8",
            "0.95",
            "16",
            "1",
            "12Gi",
            "Recreate",
        )

    @pytest.mark.parametrize(
        ("manifest", "gpu_count_requirement"),
        [
            (VLLM_DIR / "deployment.yaml", ("Gt", ["1"])),
            (VLLM_SINGLE_DIR / "deployment.yaml", ("In", ["1"])),
        ],
    )
    def test_vllm_profiles_select_gpu_count_and_architecture(
        self, manifest: Path, gpu_count_requirement: tuple[str, list[str]]
    ) -> None:
        """Verify each vLLM profile targets Ampere-or-newer GPUs under either GPU label scheme."""
        dep = _load_kind(manifest, "Deployment")
        terms = _node_selector_terms(dep["spec"]["template"]["spec"])
        summary = sorted(
            (
                arch["key"],
                arch["operator"],
                sorted(arch["values"]),
                (count["operator"], count["values"]),
            )
            for term in terms
            for arch in term["matchExpressions"]
            if arch["key"] in GPU_ARCHITECTURE_LABELS
            for count in term["matchExpressions"]
            if count["key"] == "nvidia.com/gpu.count"
        )

        assert summary == [
            (label, "In", VLLM_ARCHITECTURES, gpu_count_requirement)
            for label in GPU_ARCHITECTURE_LABELS
        ]

    def test_ollama_leaves_vllm_architectures_to_vllm(self) -> None:
        """Verify Ollama runs only on GPU nodes whose architecture is not reserved for vLLM."""
        sts = _load_kind(OLLAMA_MANIFEST, "StatefulSet")
        spec = sts["spec"]["template"]["spec"]
        terms = _node_selector_terms(spec)
        expressions = sorted(
            (e["key"], e["operator"], sorted(e["values"]))
            for term in terms
            for e in term["matchExpressions"]
        )

        assert (
            spec["nodeSelector"]["nvidia.com/gpu.present"],
            len(terms),
            expressions,
        ) == (
            "true",
            1,
            [(label, "NotIn", VLLM_ARCHITECTURES) for label in GPU_ARCHITECTURE_LABELS],
        )

    def test_ollama_pods_have_stable_names_one_per_gpu_node(self) -> None:
        """Verify Ollama pods get per-pod DNS, one pod per node, and keep the shared Service."""
        docs = [d for d in yaml.safe_load_all(OLLAMA_MANIFEST.read_text(encoding="utf-8")) if d]
        sts = next(d for d in docs if d["kind"] == "StatefulSet")
        services = {d["metadata"]["name"]: d["spec"] for d in docs if d["kind"] == "Service"}
        pod_labels = sts["spec"]["template"]["metadata"]["labels"]
        anti_affinity = sts["spec"]["template"]["spec"]["affinity"]["podAntiAffinity"][
            "requiredDuringSchedulingIgnoredDuringExecution"
        ]
        headless = services[sts["spec"]["serviceName"]]

        assert (
            sts["spec"]["podManagementPolicy"],
            [(t["topologyKey"], t["labelSelector"]["matchLabels"]) for t in anti_affinity],
            headless["clusterIP"],
            headless["selector"],
            services["ollama"]["selector"],
        ) == (
            "Parallel",
            [("kubernetes.io/hostname", sts["spec"]["selector"]["matchLabels"])],
            "None",
            sts["spec"]["selector"]["matchLabels"],
            sts["spec"]["selector"]["matchLabels"],
        )
        assert sts["spec"]["selector"]["matchLabels"].items() <= pod_labels.items()

    @pytest.mark.parametrize("profile_dir", [VLLM_DIR, VLLM_SINGLE_DIR])
    def test_vllm_profiles_trust_squid_ca_and_persist_model_cache(self, profile_dir: Path) -> None:
        """Verify vLLM downloads through the SSL-bumping proxy, keeps weights, and tolerates long loads."""
        dep = _load_kind(profile_dir / "deployment.yaml", "Deployment")
        pvc = _load_kind(profile_dir / "pvc.yaml", "PersistentVolumeClaim")
        spec = dep["spec"]["template"]["spec"]
        container = _vllm_container(dep)
        init = next(c for c in spec["initContainers"] if c["name"] == "ca-bundle")
        env = {e["name"]: e.get("value") for e in container["env"]}
        volumes = {v["name"]: v for v in spec["volumes"]}
        startup = container["startupProbe"]

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

    @pytest.mark.parametrize("profile_dir", [VLLM_DIR, VLLM_SINGLE_DIR])
    def test_vllm_services_stay_behind_the_gateway(self, profile_dir: Path) -> None:
        """Verify vLLM Services are cluster-internal; LAN clients use the authenticated gateway."""
        svc = _load_kind(profile_dir / "service.yaml", "Service")
        dep = _load_kind(profile_dir / "deployment.yaml", "Deployment")

        assert (
            svc["spec"]["type"],
            svc["spec"]["ports"][0]["port"],
            svc["spec"]["selector"]["app.kubernetes.io/name"],
        ) == (
            "ClusterIP",
            8000,
            dep["spec"]["template"]["metadata"]["labels"]["app.kubernetes.io/name"],
        )

    def test_vllm_single_network_policy_mirrors_vllm_perimeter(self) -> None:
        """Verify single-GPU vLLM admits only the gateway and the gateway may reach it."""
        netpol = _load_kind(VLLM_SINGLE_DIR / "networkpolicy.yaml", "NetworkPolicy")
        gateway_netpol = _load_kind(GATEWAY_DIR / "networkpolicy.yaml", "NetworkPolicy")
        ingress = netpol["spec"]["ingress"][0]
        egress_namespaces = sorted(
            peer["namespaceSelector"]["matchLabels"]["kubernetes.io/metadata.name"]
            for rule in netpol["spec"]["egress"]
            for peer in rule["to"]
        )
        gateway_targets = sorted(
            peer["podSelector"]["matchLabels"]["app.kubernetes.io/name"]
            for rule in gateway_netpol["spec"]["egress"]
            for peer in rule.get("to", [])
            if "podSelector" in peer
        )

        assert (
            netpol["spec"]["podSelector"]["matchLabels"]["app.kubernetes.io/name"],
            ingress["from"][0]["podSelector"]["matchLabels"]["app.kubernetes.io/name"],
            ingress["ports"][0]["port"],
            egress_namespaces,
            "vllm-single" in gateway_targets,
        ) == (
            "vllm-single",
            "llm-gateway",
            8000,
            ["kube-system", "squid"],
            True,
        )

    def test_llm_kustomization_includes_vllm_profiles(self) -> None:
        """Verify the llm kustomization deploys both vLLM profiles with their model caches."""
        resources = yaml.safe_load(LLM_KUSTOMIZATION.read_text(encoding="utf-8"))["resources"]
        expected = [
            f"{profile}/{name}.yaml"
            for profile in ("vllm", "vllm-single")
            for name in ("pvc", "deployment", "service", "networkpolicy")
        ]

        assert [r for r in resources if r.startswith("vllm")] == expected

    def test_llm_namespace_default_perimeter_excludes_gateway_and_vllm(self) -> None:
        """Verify llm-default-perimeter excludes gateway, vLLM, portkey, and lightllm to avoid additive policy leakage."""
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
            ["lightllm", "llm-gateway", "portkey", "vllm", "vllm-single"],
        )

    def test_zero_homelab_ip_or_hostname_leakage(self) -> None:
        """Verify no private RFC 1918 IPs or *.lan hostnames exist in Gateway/vLLM manifests."""
        all_yaml_files = [
            *GATEWAY_DIR.glob("*.yaml"),
            *VLLM_DIR.glob("*.yaml"),
            *VLLM_SINGLE_DIR.glob("*.yaml"),
            OLLAMA_MANIFEST,
        ]
        private_ip_pattern = re.compile(
            r"\b(192\.168\.\d{1,3}\.\d{1,3}|10\.\d{1,3}\.\d{1,3}\.\d{1,3}|172\.(1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3})\b"
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
