"""Manifest syntax, security perimeter, and zero-leakage validation for LLM Gateway and vLLM."""

from __future__ import annotations

import re
from pathlib import Path

import yaml

GATEWAY_DIR = Path("k8s/llm/gateway")
VLLM_DIR = Path("k8s/llm/vllm")


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
        models = [m["model_name"] for m in cfg["model_list"]]

        assert (
            cm["metadata"]["name"],
            models,
            cfg["router_settings"]["routing_strategy"],
            len(cfg["router_settings"]["fallbacks"]),
        ) == (
            "llm-gateway-config",
            ["devops-chat", "devops-coder", "devops-reasoning", "devops-embedding"],
            "least-busy",
            2,
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

        assert (
            svc["spec"]["type"],
            svc["spec"]["ports"][0]["port"],
            netpol["metadata"]["name"],
            netpol["spec"]["podSelector"]["matchLabels"]["app.kubernetes.io/name"],
        ) == (
            "ClusterIP",
            4000,
            "llm-gateway-perimeter",
            "llm-gateway",
        )

    def test_vllm_deployment_tensor_parallelism(self) -> None:
        """Verify vLLM deployment configures Tensor Parallelism (TP=2) and 48GB VRAM limit."""
        vllm_path = VLLM_DIR / "deployment.yaml"
        docs = list(yaml.safe_load_all(vllm_path.read_text(encoding="utf-8")))
        dep = next(d for d in docs if d and d.get("kind") == "Deployment")

        spec = dep["spec"]["template"]["spec"]
        container = spec["containers"][0]
        cmd = container["command"]

        assert (
            spec["nodeSelector"]["nvidia.com/gpu.present"],
            "--tensor-parallel-size" in cmd and cmd[cmd.index("--tensor-parallel-size") + 1] == "2",
            "--max-model-len" in cmd and cmd[cmd.index("--max-model-len") + 1] == "32768",
            container["resources"]["limits"]["nvidia.com/gpu"],
            container["resources"]["limits"]["memory"],
        ) == (
            "true",
            True,
            True,
            "2",
            "48Gi",
        )

    def test_zero_homelab_ip_or_hostname_leakage(self) -> None:
        """Verify no private RFC 1918 IPs or *.lan hostnames exist in Gateway/vLLM manifests."""
        all_yaml_files = list(GATEWAY_DIR.glob("*.yaml")) + list(VLLM_DIR.glob("*.yaml"))
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
