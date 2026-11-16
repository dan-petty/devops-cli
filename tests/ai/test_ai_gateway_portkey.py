"""Unit and integration tests for Portkey AI Gateway routing integration."""

from __future__ import annotations

import json
from pathlib import Path

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
from devops_cli.config.settings import AIConfig
from tests.support.fakes.http import WebFake

pytestmark = pytest.mark.usefixtures("keyring_store", "web")

runner = CliRunner()


def _refuse(request: httpx2.Request) -> httpx2.Response:
    """Refuse the connection, as a gateway that is down does."""
    raise httpx2.ConnectError("Connection refused", request=request)


PORTKEY_DIR = Path("k8s/llm/portkey")


class TestPortkeyGatewayRouter:
    """Test suite for GatewayRouter configured with Portkey provider."""

    def test_portkey_default_routes_initialization(self) -> None:
        """Verify GatewayRouter initializes Portkey routes with coder target."""
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
            "ollama",
            True,
        )

    def test_portkey_probe_gateway_success(self, web: WebFake) -> None:
        """Verify probe_gateway handles Portkey endpoints and records backend counts."""
        config = AIConfig(
            gateway_provider=CONST_AI_GATEWAY_PROVIDER_PORTKEY,
            portkey_url="http://example.com:8787",
        )
        router = GatewayRouter(config)
        mock_resp = httpx2.Response(200)

        web.serve(lambda request: mock_resp)
        status = router.probe_gateway()

        assert (
            status.healthy,
            status.gateway_url,
            status.circuit_breaker_tripped,
            status.backend_counts.get("ollama"),
        ) == (
            True,
            "http://example.com:8787",
            False,
            4,
        )

    def test_portkey_probe_gateway_degraded(self, web: WebFake) -> None:
        """Verify Portkey probe_gateway marks status degraded on 503."""
        config = AIConfig(
            gateway_provider=CONST_AI_GATEWAY_PROVIDER_PORTKEY,
            portkey_url="http://example.com:8787",
        )
        router = GatewayRouter(config)
        mock_resp = httpx2.Response(503)

        web.serve(lambda request: mock_resp)
        status = router.probe_gateway()

        assert (status.healthy, status.details.get("status_code")) == (False, 503)

    def test_portkey_probe_gateway_connection_failure(self, web: WebFake) -> None:
        """Verify Portkey probe handles connection errors with bounded details."""
        config = AIConfig(
            gateway_provider=CONST_AI_GATEWAY_PROVIDER_PORTKEY,
            portkey_url="http://example.com:8787",
        )
        router = GatewayRouter(config)
        long_err = "Portkey connection refused " + "y" * 400

        web.fail("http://example.com:8787/health", httpx2.ConnectError(long_err))
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

    def test_routes_with_portkey_provider(self, web: WebFake) -> None:
        """Verify 'devops ai gateway routes --provider portkey' prints Portkey routes.

        The gateway is down, so the routes are the defaults.
        """
        web.serve(_refuse)
        portkey = ["--provider", "portkey", "--gateway-url", "http://127.0.0.1:8787"]
        res_table = runner.invoke(gateway_cli_app, ["routes", *portkey])
        res_json = runner.invoke(gateway_cli_app, ["routes", *portkey, "--format", "json"])

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
            "ollama",
        )

    def test_status_with_portkey_provider(self, web: WebFake) -> None:
        """Verify 'devops ai gateway status --provider portkey' checks Portkey gateway."""
        mock_resp = httpx2.Response(200)

        web.serve(lambda request: mock_resp)
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

    def test_portkey_network_policy_rules(self) -> None:
        """Verify Portkey NetworkPolicy isolates egress to the model backends.

        Portkey 1.15.0 reads its cache only from REDIS_CONNECTION_STRING, which the Deployment
        does not set, so it calls no Valkey and its policy admits none (#1654).
        """
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
            [("llm.devops.io/provider", "ollama")],
        )
