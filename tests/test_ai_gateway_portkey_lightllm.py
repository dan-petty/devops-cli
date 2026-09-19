"""Unit and integration tests for Portkey AI Gateway and LightLLM routing integration."""

from __future__ import annotations

import json
import re
from pathlib import Path
from unittest.mock import MagicMock, patch

import httpx2
import pytest
import yaml
from typer.testing import CliRunner

from devops_cli.ai.gateway import GatewayRouter
from devops_cli.commands.ai_gateway import app as gateway_cli_app
from devops_cli.config.constants import (
    CONST_AI_BACKEND_LIGHTLLM,
    CONST_AI_GATEWAY_PROVIDER_PORTKEY,
    CONST_AI_GATEWAY_VIRTUAL_MODELS,
)
from devops_cli.config.settings import AIConfig

runner = CliRunner()
PORTKEY_DIR = Path("k8s/llm/portkey")
LIGHTLLM_DIR = Path("k8s/llm/lightllm")


class TestPortkeyGatewayRouter:
    """Test suite for GatewayRouter configured with Portkey provider."""

    def test_portkey_default_routes_initialization(self) -> None:
        """Verify GatewayRouter initializes Portkey routes with LightLLM coder target."""
        config = AIConfig(gateway_provider=CONST_AI_GATEWAY_PROVIDER_PORTKEY)
        router = GatewayRouter(config)
        routes = router.list_routes()
        models = tuple(r.virtual_model for r in routes)
        coder_route = next(r for r in routes if r.virtual_model == "devops-coder")

        assert (
            len(routes),
            models,
            coder_route.backend_type,
            all(r.healthy for r in routes),
        ) == (
            4,
            CONST_AI_GATEWAY_VIRTUAL_MODELS,
            CONST_AI_BACKEND_LIGHTLLM,
            True,
        )

    def test_portkey_probe_gateway_success(self) -> None:
        """Verify probe_gateway handles Portkey endpoints and records backend counts."""
        config = AIConfig(
            gateway_provider=CONST_AI_GATEWAY_PROVIDER_PORTKEY,
            portkey_url="http://example.com:8787",
        )
        router = GatewayRouter(config)
        mock_resp = MagicMock()
        mock_resp.status_code = 200

        with patch.object(httpx2.Client, "get", return_value=mock_resp):
            status = router.probe_gateway()

        assert (
            status.healthy,
            status.gateway_url,
            status.circuit_breaker_tripped,
            status.backend_counts.get("lightllm"),
            status.backend_counts.get("ollama"),
        ) == (
            True,
            "http://example.com:8787",
            False,
            1,
            2,
        )

    def test_portkey_probe_gateway_degraded(self) -> None:
        """Verify Portkey probe_gateway marks status degraded on 503."""
        config = AIConfig(
            gateway_provider=CONST_AI_GATEWAY_PROVIDER_PORTKEY,
            portkey_url="http://example.com:8787",
        )
        router = GatewayRouter(config)
        mock_resp = MagicMock()
        mock_resp.status_code = 503

        with patch.object(httpx2.Client, "get", return_value=mock_resp):
            status = router.probe_gateway()

        assert (status.healthy, status.details.get("status_code")) == (False, 503)

    def test_portkey_probe_gateway_connection_failure(self) -> None:
        """Verify Portkey probe handles connection errors with bounded details."""
        config = AIConfig(
            gateway_provider=CONST_AI_GATEWAY_PROVIDER_PORTKEY,
            portkey_url="http://example.com:8787",
        )
        router = GatewayRouter(config)
        long_err = "Portkey connection refused " + "y" * 400

        with patch.object(httpx2.Client, "get", side_effect=httpx2.ConnectError(long_err)):
            status = router.probe_gateway()

        err_detail = status.details.get("error", "")
        assert (
            status.healthy,
            len(err_detail) <= 256,
            "Portkey connection refused" in err_detail,
        ) == (
            False,
            True,
            True,
        )


class TestLightLLMScaleAndProbe:
    """Test suite for LightLLM scaling and backend probing."""

    def test_scale_lightllm_calculation(self) -> None:
        """Verify scale_lightllm computes correct VRAM aggregates and parameters."""
        router = GatewayRouter()
        default_scale = router.scale_lightllm()
        custom_scale = router.scale_lightllm(
            replicas=2, tensor_parallel_size=2, max_model_len=16384
        )

        assert (
            default_scale["backend"],
            default_scale["replicas"],
            default_scale["tensor_parallel_size"],
            default_scale["total_vram_gb"],
            custom_scale["replicas"],
            custom_scale["tensor_parallel_size"],
            custom_scale["max_model_len"],
            custom_scale["total_vram_gb"],
            custom_scale["vram_per_replica_gb"],
        ) == (
            "lightllm",
            1,
            1,
            24,
            2,
            2,
            16384,
            96,
            48,
        )

    def test_scale_lightllm_kubectl_execution(self) -> None:
        """Verify scale_lightllm executes kubectl scale against lightllm deployment."""
        router = GatewayRouter()
        mock_proc_ok = MagicMock(returncode=0, stdout="deployment.apps/lightllm scaled", stderr="")
        mock_proc_err = MagicMock(returncode=1, stdout="", stderr="deployment not found")

        with patch("subprocess.run", return_value=mock_proc_ok) as mock_sub:
            res_ok = router.scale_lightllm(replicas=3, apply=True)
            called_cmd = mock_sub.call_args[0][0]

        with patch("subprocess.run", return_value=mock_proc_err):
            res_err = router.scale_lightllm(replicas=3, apply=True)

        assert (
            res_ok["status"],
            "lightllm" in called_cmd,
            "--replicas=3" in called_cmd,
            res_err["status"],
            "deployment not found" in res_err["details"]["error"],
        ) == (
            "scaled",
            True,
            True,
            "error",
            True,
        )

    def test_probe_backend_lightllm_success(self) -> None:
        """Verify probe_backend queries LightLLM health and model registry."""
        router = GatewayRouter(AIConfig(lightllm_url="http://example.com:8000"))
        mock_health = MagicMock(status_code=200)
        mock_models = MagicMock(
            status_code=200,
            json=lambda: {"data": [{"id": "meta-llama/Llama-3.2-3B-Instruct"}]},
        )

        def mock_get(url: str, **kwargs: object) -> MagicMock:
            return mock_health if "health" in url else mock_models

        with patch.object(httpx2.Client, "get", side_effect=mock_get):
            res = router.probe_backend("lightllm")

        assert (
            res["backend"],
            res["healthy"],
            res["model_count"],
            res["models"],
        ) == (
            "lightllm",
            True,
            1,
            ["meta-llama/Llama-3.2-3B-Instruct"],
        )

    def test_probe_backend_vllm_and_ollama(self) -> None:
        """Verify probe_backend supports vLLM and Ollama inference endpoints."""
        config = AIConfig(
            vllm_url="http://example.com:8000/v1",
            ollama_urls=["http://example.com:11434"],
        )
        router = GatewayRouter(config)
        mock_vllm = MagicMock(
            status_code=200,
            json=lambda: {"data": [{"id": "llama-3.3-70b-instruct"}]},
        )
        mock_ollama = MagicMock(
            status_code=200,
            json=lambda: {"models": [{"name": "qwen2.5-coder:14b"}]},
        )

        with patch.object(httpx2.Client, "get", return_value=mock_vllm):
            res_vllm = router.probe_backend("vllm")

        with patch.object(httpx2.Client, "get", return_value=mock_ollama):
            res_ollama = router.probe_backend("ollama")

        assert (
            res_vllm["backend"],
            res_vllm["healthy"],
            res_vllm["model_count"],
            res_ollama["backend"],
            res_ollama["healthy"],
            res_ollama["model_count"],
        ) == (
            "vllm",
            True,
            1,
            "ollama",
            True,
            1,
        )

    def test_probe_backend_unsupported_raises(self) -> None:
        """Verify probe_backend raises ValueError when backend is unsupported."""
        router = GatewayRouter()
        with pytest.raises(ValueError, match="Unknown backend type"):
            router.probe_backend("unsupported-backend")


class TestPortkeyAndLightLLMCLI:
    """Test suite for CLI ai gateway commands with Portkey and LightLLM."""

    def test_routes_with_portkey_provider(self) -> None:
        """Verify 'devops ai gateway routes --provider portkey' prints Portkey routes."""
        res_table = runner.invoke(gateway_cli_app, ["routes", "--provider", "portkey"])
        res_json = runner.invoke(
            gateway_cli_app, ["routes", "--provider", "portkey", "--format", "json"]
        )

        parsed = json.loads(res_json.output)
        coder_item = next(p for p in parsed if p["virtual_model"] == "devops-coder")

        assert (
            res_table.exit_code,
            res_json.exit_code,
            "LLM Gateway Virtual Model Routes" in res_table.output,
            len(parsed),
            coder_item["backend_type"],
        ) == (
            0,
            0,
            True,
            4,
            CONST_AI_BACKEND_LIGHTLLM,
        )

    def test_status_with_portkey_provider(self) -> None:
        """Verify 'devops ai gateway status --provider portkey' checks Portkey gateway."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200

        with patch.object(httpx2.Client, "get", return_value=mock_resp):
            res_table = runner.invoke(
                gateway_cli_app,
                ["status", "--provider", "portkey", "--gateway-url", "http://example.com:8787"],
            )
            res_json = runner.invoke(
                gateway_cli_app,
                [
                    "status",
                    "--provider",
                    "portkey",
                    "--gateway-url",
                    "http://example.com:8787",
                    "--format",
                    "json",
                ],
            )

        parsed = json.loads(res_json.output)
        assert (
            res_table.exit_code,
            res_json.exit_code,
            "LLM Gateway Status" in res_table.output,
            parsed["healthy"],
        ) == (
            0,
            0,
            True,
            True,
        )

    def test_scale_lightllm_command(self) -> None:
        """Verify 'devops ai gateway scale --backend lightllm' prints LightLLM scale params."""
        res_table = runner.invoke(
            gateway_cli_app, ["scale", "--backend", "lightllm", "--replicas", "2"]
        )
        res_json = runner.invoke(
            gateway_cli_app,
            ["scale", "--backend", "lightllm", "--replicas", "2", "--format", "json"],
        )

        parsed = json.loads(res_json.output)
        assert (
            res_table.exit_code,
            res_json.exit_code,
            "LightLLM Scale Parameters" in res_table.output,
            parsed["replicas"],
            parsed["backend"],
        ) == (
            0,
            0,
            True,
            2,
            "lightllm",
        )

    def test_probe_backend_command(self) -> None:
        """Verify 'devops ai gateway probe-backend' prints backend health status."""
        mock_health = MagicMock(status_code=200)
        mock_models = MagicMock(
            status_code=200,
            json=lambda: {"data": [{"id": "meta-llama/Llama-3.2-3B-Instruct"}]},
        )

        def mock_get(url: str, **kwargs: object) -> MagicMock:
            return mock_health if "health" in url else mock_models

        with patch.object(httpx2.Client, "get", side_effect=mock_get):
            res_table = runner.invoke(
                gateway_cli_app,
                ["probe-backend", "lightllm", "--backend-url", "http://example.com:8000"],
            )
            res_json = runner.invoke(
                gateway_cli_app,
                [
                    "probe-backend",
                    "lightllm",
                    "--backend-url",
                    "http://example.com:8000",
                    "--format",
                    "json",
                ],
            )

        parsed = json.loads(res_json.output)
        assert (
            res_table.exit_code,
            res_json.exit_code,
            "Inference Backend Health" in res_table.output,
            parsed["healthy"],
            parsed["backend"],
        ) == (
            0,
            0,
            True,
            True,
            "lightllm",
        )


class TestK8sPortkeyAndLightLLMManifests:
    """Validate Kubernetes manifests and security controls for Portkey and LightLLM."""

    def test_portkey_deployment_and_service(self) -> None:
        """Verify Portkey deployment security context, ports, and service definitions."""
        dep_docs = list(
            yaml.safe_load_all((PORTKEY_DIR / "deployment.yaml").read_text(encoding="utf-8"))
        )
        dep = next(d for d in dep_docs if d and d.get("kind") == "Deployment")
        spec = dep["spec"]["template"]["spec"]
        container = spec["containers"][0]

        svc_docs = list(
            yaml.safe_load_all((PORTKEY_DIR / "service.yaml").read_text(encoding="utf-8"))
        )
        svc = next(d for d in svc_docs if d and d.get("kind") == "Service")

        assert (
            dep["metadata"]["namespace"],
            spec["securityContext"]["runAsNonRoot"],
            spec["securityContext"]["runAsUser"],
            container["ports"][0]["containerPort"],
            svc["spec"]["ports"][0]["port"],
        ) == (
            "llm",
            True,
            1000,
            8787,
            8787,
        )

    def test_portkey_network_policy_rules(self) -> None:
        """Verify Portkey NetworkPolicy isolates egress to model backends and cache."""
        netpol_docs = list(
            yaml.safe_load_all((PORTKEY_DIR / "networkpolicy.yaml").read_text(encoding="utf-8"))
        )
        netpol = next(d for d in netpol_docs if d and d.get("kind") == "NetworkPolicy")
        egress = netpol["spec"]["egress"]

        egress_backends = [
            rule["to"][0]["podSelector"]["matchLabels"]["app.kubernetes.io/name"]
            for rule in egress
            if "to" in rule and "podSelector" in rule["to"][0]
        ]

        assert (
            netpol["metadata"]["name"],
            sorted(egress_backends),
        ) == (
            "portkey-perimeter",
            ["lightllm", "ollama", "valkey", "vllm"],
        )

    def test_lightllm_deployment_and_network_policy(self) -> None:
        """Verify LightLLM deployment ports, resources, and ingress isolation."""
        dep_docs = list(
            yaml.safe_load_all((LIGHTLLM_DIR / "deployment.yaml").read_text(encoding="utf-8"))
        )
        dep = next(d for d in dep_docs if d and d.get("kind") == "Deployment")
        spec = dep["spec"]["template"]["spec"]
        container = spec["containers"][0]
        cmd = container["command"]

        netpol_docs = list(
            yaml.safe_load_all((LIGHTLLM_DIR / "networkpolicy.yaml").read_text(encoding="utf-8"))
        )
        netpol = next(d for d in netpol_docs if d and d.get("kind") == "NetworkPolicy")
        ingress_from = [
            rule["podSelector"]["matchLabels"]["app.kubernetes.io/name"]
            for rule in netpol["spec"]["ingress"][0]["from"]
            if "podSelector" in rule
        ]

        assert (
            spec["runtimeClassName"],
            spec["nodeSelector"]["nvidia.com/gpu.present"],
            "--tp" in cmd,
            container["ports"][0]["containerPort"],
            sorted(ingress_from),
        ) == (
            "nvidia",
            "true",
            True,
            8000,
            ["llm-gateway", "portkey"],
        )

    def test_zero_homelab_ip_or_hostname_leakage_in_portkey_lightllm(self) -> None:
        """Verify zero RFC 1918 IPs or *.lan hostnames exist in Portkey and LightLLM manifests."""
        all_yamls = list(PORTKEY_DIR.glob("*.yaml")) + list(LIGHTLLM_DIR.glob("*.yaml"))
        private_ip_pattern = re.compile(
            r"\b(192\.168\.\d{1,3}\.\d{1,3}|10\.\d{1,3}\.\d{1,3}\.\d{1,3}|172\.(1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3})\b"
        )
        lan_hostname_pattern = re.compile(r"\b[a-zA-Z0-9_\-]+\.lan\b")

        for file_path in all_yamls:
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
