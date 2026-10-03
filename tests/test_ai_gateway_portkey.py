"""Unit and integration tests for Portkey AI Gateway routing integration."""

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
    CONST_AI_GATEWAY_PROVIDER_PORTKEY,
    CONST_AI_GATEWAY_VIRTUAL_MODELS,
)
from devops_cli.config.defaults import DEFAULT_VLLM_CLUSTER_URL, DEFAULT_VLLM_SERVED_MODEL_NAME
from devops_cli.config.settings import AIConfig

runner = CliRunner()
PORTKEY_DIR = Path("k8s/llm/portkey")


class TestPortkeyGatewayRouter:
    """Test suite for GatewayRouter configured with Portkey provider."""

    def test_portkey_default_routes_initialization(self) -> None:
        """Verify GatewayRouter initializes Portkey routes with vLLM coder target."""
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
            "vllm",
            True,
        )

    def test_portkey_reasoning_targets_vllm_served_model(self) -> None:
        """Verify Portkey default routes and ConfigMap address vLLM by its served model name."""
        router = GatewayRouter(AIConfig(gateway_provider=CONST_AI_GATEWAY_PROVIDER_PORTKEY))
        reasoning = next(r for r in router.list_routes() if r.virtual_model == "devops-reasoning")
        docs = yaml.safe_load_all((PORTKEY_DIR / "configmap.yaml").read_text(encoding="utf-8"))
        cm = next(d for d in docs if d and d.get("kind") == "ConfigMap")
        targets = {t["virtual_key"]: t for t in json.loads(cm["data"]["config.json"])["targets"]}

        assert (
            reasoning.target_model,
            reasoning.backend_url,
            targets["vllm-backend"]["override_params"]["model"],
        ) == (
            DEFAULT_VLLM_SERVED_MODEL_NAME,
            DEFAULT_VLLM_CLUSTER_URL,
            DEFAULT_VLLM_SERVED_MODEL_NAME,
        )

    @pytest.mark.usefixtures("public_dns")
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
            status.backend_counts.get("vllm"),
            status.backend_counts.get("ollama"),
        ) == (
            True,
            "http://example.com:8787",
            False,
            2,
            2,
        )

    @pytest.mark.usefixtures("public_dns")
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

    @pytest.mark.usefixtures("public_dns")
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


class TestPortkeyCLI:
    """Test suite for CLI ai gateway commands with the Portkey provider."""

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
            "vllm",
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


class TestK8sPortkeyManifests:
    """Validate Kubernetes manifests and security controls for Portkey."""

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
            label
            for rule in egress
            if "to" in rule and "podSelector" in rule["to"][0]
            for label in rule["to"][0]["podSelector"]["matchLabels"].items()
        ]

        assert (
            netpol["metadata"]["name"],
            sorted(egress_backends),
        ) == (
            "portkey-perimeter",
            [
                ("app.kubernetes.io/name", "valkey"),
                ("app.kubernetes.io/name", "vllm"),
                ("llm.devops.io/provider", "ollama"),
            ],
        )

    def test_portkey_ollama_egress_selects_every_ollama_tier(self) -> None:
        """Verify Portkey's Ollama egress rule selects the pods of every Ollama tier (#953).

        It selected `app.kubernetes.io/name: ollama`, the label of the single `ollama` workload
        the tiers in `k8s/llm/profiles/ollama-profiles.yaml` replaced, so it admitted no pod
        deploy-stack creates.
        """
        netpol = next(
            d
            for d in yaml.safe_load_all(
                (PORTKEY_DIR / "networkpolicy.yaml").read_text(encoding="utf-8")
            )
            if d and d.get("kind") == "NetworkPolicy"
        )
        selectors = [
            peer["podSelector"]["matchLabels"]
            for rule in netpol["spec"]["egress"]
            if {"protocol": "TCP", "port": 11434} in rule.get("ports", [])
            for peer in rule.get("to", [])
        ]
        tiers = [
            d["spec"]["template"]["metadata"]["labels"]
            for d in yaml.safe_load_all(
                Path("k8s/llm/profiles/ollama-profiles.yaml").read_text(encoding="utf-8")
            )
            if d and d.get("kind") == "DaemonSet"
        ]

        assert (
            len(selectors),
            bool(tiers),
            [all(selector.items() <= labels.items() for selector in selectors) for labels in tiers],
        ) == (1, True, [True] * len(tiers))

    def test_zero_homelab_ip_or_hostname_leakage_in_portkey_manifests(self) -> None:
        """Verify zero RFC 1918 IPs or *.lan hostnames exist in Portkey manifests."""
        all_yamls = list(PORTKEY_DIR.glob("*.yaml"))
        private_ip_pattern = re.compile(
            r"\b(192\.168\.\d{1,3}\.\d{1,3}|10\.\d{1,3}\.\d{1,3}\.\d{1,3}|172\.(1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3})\b(?!/)"
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
