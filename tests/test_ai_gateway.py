"""Unit and integration tests for AI LLM Gateway and distributed model routing."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch
from urllib.parse import urlsplit

import httpx2
import pytest
import yaml
from typer.testing import CliRunner

from devops_cli.ai.client import AICredentialsError
from devops_cli.ai.gateway import (
    GatewayRouter,
)
from devops_cli.commands.ai_gateway import app as gateway_cli_app
from devops_cli.config.constants import (
    CONST_AI_GATEWAY_VIRTUAL_MODELS,
)
from devops_cli.config.defaults import (
    DEFAULT_OLLAMA_CLUSTER_URL,
)
from devops_cli.config.settings import AIConfig
from devops_cli.exceptions.ai import CapabilityDegradationError

pytestmark = pytest.mark.usefixtures("mock_keyring", "public_dns")

runner = CliRunner()


class TestGatewayRouter:
    """Test suite for GatewayRouter model resolution, health probing, and failover."""

    def test_default_routes_initialization(self) -> None:
        """Verify GatewayRouter initializes all 4 default virtual model routes."""
        router = GatewayRouter()
        routes = router.list_routes()
        models = tuple(r.virtual_model for r in routes)

        assert (
            len(routes),
            models,
            all(r.healthy for r in routes),
        ) == (
            4,
            CONST_AI_GATEWAY_VIRTUAL_MODELS,
            True,
        )

    @pytest.mark.usefixtures("public_dns")
    def test_probe_gateway_success(self) -> None:
        """Verify probe_gateway returns healthy status when gateway responds with 200."""
        router = GatewayRouter(AIConfig(gateway_url="http://example.com/v1"))
        mock_resp = MagicMock()
        mock_resp.status_code = 200

        with patch.object(httpx2.Client, "get", return_value=mock_resp):
            status = router.probe_gateway()

        assert (
            status.healthy,
            status.gateway_url,
            status.circuit_breaker_tripped,
            status.backend_counts["ollama"],
        ) == (
            True,
            "http://example.com/v1",
            False,
            4,
        )

    @pytest.mark.usefixtures("public_dns")
    def test_probe_gateway_degraded_http_status(self) -> None:
        """Verify probe_gateway marks status degraded when gateway returns 503."""
        router = GatewayRouter(AIConfig(gateway_url="http://example.com/v1"))
        mock_resp = MagicMock()
        mock_resp.status_code = 503

        with patch.object(httpx2.Client, "get", return_value=mock_resp):
            status = router.probe_gateway()

        assert (status.healthy, status.details.get("status_code")) == (False, 503)

    @pytest.mark.usefixtures("public_dns")
    def test_probe_gateway_connection_failure(self) -> None:
        """Verify probe_gateway gracefully handles network connection errors with bounded details."""
        router = GatewayRouter(AIConfig(gateway_url="http://example.com/v1"))
        long_err = "Connection refused by peer " + "x" * 500

        with patch.object(
            httpx2.Client,
            "get",
            side_effect=httpx2.ConnectError(long_err),
        ):
            status = router.probe_gateway()

        err_detail = status.details.get("error", "")
        assert (
            status.healthy,
            len(err_detail) <= 256,
            "Connection refused" in err_detail,
        ) == (
            False,
            True,
            True,
        )

    def test_trigger_failover_simulation_and_execution(self, tmp_path: Path) -> None:
        """Verify simulated failover leaves routes untouched while non-simulated alters table."""
        state_file = tmp_path / "gateway_state.json"
        router = GatewayRouter(state_file=state_file)

        # devops-coder fails over to devops-chat (7b >= 7b), satisfying capability tier
        simulated = router.trigger_failover("devops-coder", simulate=True)
        executed = router.trigger_failover("devops-coder", simulate=False)
        assert (
            simulated["fallback_target"],
            simulated["simulated"],
            router.list_routes()[1].backend_type,
            executed["fallback_target"],
            executed["target_model"],
            executed["simulated"],
        ) == (
            "devops-chat",
            True,
            "failover:ollama",
            "devops-chat",
            "qwen2.5-coder:7b",
            False,
        )

    def test_direct_ollama_failover_targets_the_default_ollama_tier(self, tmp_path: Path) -> None:
        """Verify devops-chat fails over to the Service of the default Ollama tier (#953).

        The direct-Ollama fallback sent requests to `ollama.llm.svc.cluster.local`, a Service
        nothing deploys since the Ollama tiers replaced the single `ollama` workload.
        """
        router = GatewayRouter(state_file=tmp_path / "gateway_state.json")
        router.trigger_failover("devops-chat", simulate=False)
        chat = next(r for r in router.list_routes() if r.virtual_model == "devops-chat")
        tier_services = {
            doc["metadata"]["name"]
            for doc in yaml.safe_load_all(
                Path("k8s/llm/profiles/services.yaml").read_text(encoding="utf-8")
            )
            if doc and doc.get("kind") == "Service"
        }

        service, namespace = str(urlsplit(chat.backend_url).hostname).split(".")[:2]

        assert (chat.backend_type, chat.backend_url, namespace, service in tier_services) == (
            "failover:ollama",
            DEFAULT_OLLAMA_CLUSTER_URL,
            "llm",
            True,
        )

    def test_trigger_failover_capability_gating(self, tmp_path: Path) -> None:
        """Verify reasoning failover to underpowered tier is blocked without --force."""
        state_file = tmp_path / "gateway_state.json"
        router = GatewayRouter(state_file=state_file)

        with pytest.raises(CapabilityDegradationError) as exc_info:
            router.trigger_failover("devops-reasoning", simulate=True)

        forced = router.trigger_failover("devops-reasoning", simulate=True, force=True)
        assert (
            exc_info.value.details["required_tier_b"],
            forced["simulated"],
            forced["status"],
        ) == (
            30,
            True,
            "simulated",
        )

    def test_default_routes_target_profiles(self) -> None:
        """Verify reasoning and coder aliases route to the designated Ollama profiles."""
        routes = {
            r.virtual_model: (r.target_model, r.backend_type, r.backend_url)
            for r in GatewayRouter().list_routes()
        }

        assert (routes["devops-reasoning"], routes["devops-coder"]) == (
            ("qwen3-coder:30b", "ollama", DEFAULT_OLLAMA_CLUSTER_URL),
            ("qwen2.5-coder:14b", "ollama", DEFAULT_OLLAMA_CLUSTER_URL),
        )

    def test_trigger_failover_invalid_model_raises_value_error(self) -> None:
        """Verify unknown virtual model alias raises ValidationError (subclass of ValueError)."""
        router = GatewayRouter()
        with pytest.raises(ValueError, match="Unknown virtual model 'unknown-model'"):
            router.trigger_failover("unknown-model")

    @pytest.mark.usefixtures("public_dns")
    def test_probe_backend_ollama(self) -> None:
        """Verify probe_backend supports Ollama inference endpoints."""
        config = AIConfig(
            ollama_urls=["http://example.com:11434"],
        )
        router = GatewayRouter(config)
        mock_ollama = MagicMock(
            status_code=200,
            json=lambda: {"models": [{"name": "qwen2.5-coder:14b"}]},
        )

        with patch.object(httpx2.Client, "get", return_value=mock_ollama):
            res_ollama = router.probe_backend("ollama")

        assert (
            res_ollama["backend"],
            res_ollama["healthy"],
            res_ollama["model_count"],
        ) == (
            "ollama",
            True,
            1,
        )

    def test_probe_backend_unsupported_raises(self) -> None:
        """Verify probe_backend raises ValueError when backend is unsupported."""
        router = GatewayRouter()
        with pytest.raises(ValueError, match="Unknown backend type"):
            router.probe_backend("unsupported-backend")


class TestAIGatewayCLI:
    """Test suite for CLI devops ai gateway commands."""

    def test_routes_command_table_and_json(self, refusing_port: int) -> None:
        """Verify 'devops ai gateway routes' executes with table and JSON formatting.

        The gateway is down, refused through `refusing_port`, so the routes are the defaults.
        """
        gateway = ["--gateway-url", f"http://127.0.0.1:{refusing_port}"]
        res_table = runner.invoke(gateway_cli_app, ["routes", *gateway])
        res_json = runner.invoke(gateway_cli_app, ["routes", *gateway, "--format", "json"])

        parsed = json.loads(res_json.output)
        assert (
            res_table.exit_code,
            res_json.exit_code,
            "LLM Gateway Virtual Model Routes" in res_table.output,
            len(parsed),
            parsed[0]["virtual_model"],
        ) == (
            0,
            0,
            True,
            4,
            "devops-chat",
        )

    def test_status_command_table_and_json(self) -> None:
        """Verify 'devops ai gateway status' outputs health and metrics."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200

        with patch.object(httpx2.Client, "get", return_value=mock_resp):
            res_table = runner.invoke(gateway_cli_app, ["status"])
            res_json = runner.invoke(gateway_cli_app, ["status", "--format", "json"])

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

    def test_failover_command_execution(self) -> None:
        """Verify 'devops ai gateway failover' triggers simulated and active transitions."""
        res_blocked = runner.invoke(
            gateway_cli_app,
            ["failover", "devops-reasoning", "--simulate", "--format", "json"],
        )
        res_sim = runner.invoke(
            gateway_cli_app,
            ["failover", "devops-reasoning", "--force", "--simulate", "--format", "json"],
        )
        parsed_sim = json.loads(res_sim.output)

        res_exec = runner.invoke(
            gateway_cli_app,
            ["failover", "devops-reasoning", "--force", "--no-simulate"],
        )

        res_err = runner.invoke(
            gateway_cli_app,
            ["failover", "nonexistent-model"],
        )

        assert (
            res_blocked.exit_code,
            res_sim.exit_code,
            parsed_sim["simulated"],
            res_exec.exit_code,
            "Failover status: failover_active" in res_exec.output,
            res_err.exit_code,
        ) == (
            1,
            0,
            True,
            0,
            True,
            1,
        )

    def test_probe_backend_command(self) -> None:
        """Verify 'devops ai gateway probe-backend' prints backend health status."""
        mock_ollama = MagicMock(
            status_code=200,
            json=lambda: {"models": [{"name": "qwen2.5-coder:14b"}]},
        )

        with patch.object(httpx2.Client, "get", return_value=mock_ollama):
            res_table = runner.invoke(
                gateway_cli_app,
                ["probe-backend", "ollama", "--backend-url", "http://example.com:11434"],
            )
            res_json = runner.invoke(
                gateway_cli_app,
                [
                    "probe-backend",
                    "ollama",
                    "--backend-url",
                    "http://example.com:11434",
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
            "ollama",
        )


class TestFastMCPGatewayTools:
    """Test suite for FastMCP server gateway tool bindings."""

    def test_fastmcp_gateway_tools_registered(self) -> None:
        """Verify FastMCP server exports gateway tools and resources."""
        from devops_cli.ai.mcp.server import (
            ai_gateway_failover,
            ai_gateway_probe_backend,
            ai_gateway_routes,
            ai_gateway_status,
            get_ai_gateway_resource,
        )

        with patch("devops_cli.ai.mcp.server._run_mcp_cmd", return_value="{}") as mock_run:
            ai_gateway_status()
            ai_gateway_routes()
            ai_gateway_failover("devops-coder", simulate=True)
            ai_gateway_probe_backend("ollama")
            get_ai_gateway_resource()

        assert mock_run.call_count == 5


class TestRouterAndClientGatewayIntegration:
    """Test suite for LLMClient gateway provider dispatch."""

    def test_unified_client_gateway_dispatch(self) -> None:
        """Verify LLMClient dispatches to OpenAI compatible handler when provider is gateway."""
        from devops_cli.ai.client.models import LLMResponse
        from devops_cli.ai.client.unified import LLMClient

        client = LLMClient(AIConfig(provider="gateway", gateway_url="http://example.com/v1"))
        dummy_res = LLMResponse(content="gateway response", backend_info="gateway (example.com)")

        with patch.object(client, "_openai_compat_messages", return_value=dummy_res) as mock_compat:
            resp = client.chat("system prompt", "user query")

        assert (
            mock_compat.call_count,
            resp.content,
            client.backend_type,
            client.backend_host,
        ) == (
            1,
            "gateway response",
            "gateway",
            "example.com",
        )

    @pytest.mark.usefixtures("public_dns")
    def test_probe_gateway_strips_v1_and_updates_circuit_breaker(self, tmp_path: Path) -> None:
        """Verify health probe strips /v1 and updates circuit breaker on failure."""
        state_file = tmp_path / "gw_state.json"
        router = GatewayRouter(AIConfig(gateway_url="http://example.com/v1"), state_file=state_file)

        mock_resp_fail = MagicMock(status_code=502)
        with patch.object(httpx2.Client, "get", return_value=mock_resp_fail) as mock_get:
            status = router.probe_gateway()
            initial_probe_url = mock_get.call_args_list[0][0][0]

        assert (
            initial_probe_url,
            status.healthy,
            status.circuit_breaker_tripped,
            router._circuit_breaker_active,
            all(not r.healthy for r in router.list_routes()),
        ) == (
            "http://example.com/health/readiness",
            False,
            True,
            True,
            True,
        )


GATEWAY_URL = "http://gateway.example.com:4000/v1"


def _model_info(status: int = 200) -> tuple[list[dict[str, str]], Any]:
    """Serve a LiteLLM /model/info with two deployments and one expanded wildcard."""
    requests: list[dict[str, str]] = []
    wildcard = [
        {
            "model_name": name,
            "litellm_params": {"model": name, "api_base": "http://ollama.example.com:11434/v1"},
            "model_info": {"id": "wild"},
        }
        for name in ("ollama/gpt-4", "ollama/gpt-4o", "ollama/o3")
    ]
    data = [
        {
            "model_name": "devops-review",
            "litellm_params": {
                "model": "openai/qwen2.5-coder-32b-instruct",
                "api_base": "http://remote.example.com:8000/v1",
            },
            "model_info": {"id": "a"},
        },
        {
            "model_name": "devops-review",
            "litellm_params": {
                "model": "ollama_chat/gpt-oss:20b",
                "api_base": "http://ollama.example.com:11434",
            },
            "model_info": {"id": "b"},
        },
        *wildcard,
    ]

    def fake_get(self: Any, url: str, **kwargs: Any) -> httpx2.Response:
        requests.append({"url": url, **(kwargs.get("headers") or {})})
        body = {"data": data} if status == 200 else {"error": {"message": "No api key"}}
        return httpx2.Response(status, json=body, request=httpx2.Request("GET", url))

    return requests, fake_get


class TestGatewayRouteDiscovery:
    """Live route discovery authenticates and reports the gateway's real deployments."""

    def test_discovery_authenticates_and_collapses_wildcard_expansions(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify /model/info is read with the key and a wildcard's expansions become one route."""
        requests, fake_get = _model_info()
        monkeypatch.setattr(httpx2.Client, "get", fake_get)
        router = GatewayRouter(AIConfig(allow_private_network=True), api_key="sk-gateway")

        routes = router.list_routes(GATEWAY_URL)

        assert (
            [(r.virtual_model, r.target_model) for r in routes],
            [(r["url"], r.get("Authorization")) for r in requests],
        ) == (
            [
                ("devops-review", "openai/qwen2.5-coder-32b-instruct"),
                ("devops-review", "ollama_chat/gpt-oss:20b"),
                ("ollama/*", "ollama/*"),
            ],
            [(f"{GATEWAY_URL}/model/info", "Bearer sk-gateway")],
        )

    @pytest.mark.parametrize(
        ("api_key", "expected"),
        [(None, "no API key is configured"), ("sk-wrong", "rejected the configured API key")],
    )
    def test_rejected_discovery_names_the_key_instead_of_showing_defaults(
        self, monkeypatch: pytest.MonkeyPatch, api_key: str | None, expected: str
    ) -> None:
        """Verify a 401 raises a credentials error rather than falling back to default routes."""
        requests, fake_get = _model_info(status=401)
        monkeypatch.setattr(httpx2.Client, "get", fake_get)
        router = GatewayRouter(AIConfig(allow_private_network=True), api_key=api_key)

        with pytest.raises(AICredentialsError) as exc_info:
            router.list_routes(GATEWAY_URL)

        assert (
            expected in str(exc_info.value),
            "DEVOPS_CLI_AI_API_KEY" in str(exc_info.value),
            [r.get("Authorization") for r in requests],
        ) == (True, True, [f"Bearer {api_key}" if api_key else None])

    def test_routes_command_queries_the_configured_gateway(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify `routes` reads the configured gateway, with its key, without --gateway-url."""
        requests, fake_get = _model_info()
        monkeypatch.setattr(httpx2.Client, "get", fake_get)
        settings = MagicMock()
        settings.ai = AIConfig(gateway_url=GATEWAY_URL, allow_private_network=True)
        monkeypatch.setattr("devops_cli.commands.ai_gateway.load_settings", lambda: settings)
        monkeypatch.setattr("devops_cli.commands.ai_gateway.get_ai_api_key", lambda _s: "sk-gw")

        result = runner.invoke(gateway_cli_app, ["routes", "--format", "json"])

        assert (
            result.exit_code,
            [r["target_model"] for r in json.loads(result.output)],
            [r.get("Authorization") for r in requests],
        ) == (
            0,
            ["openai/qwen2.5-coder-32b-instruct", "ollama_chat/gpt-oss:20b", "ollama/*"],
            ["Bearer sk-gw"],
        )

    def test_routes_command_reports_missing_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verify `routes` exits non-zero and names the key when the gateway rejects it."""
        _requests, fake_get = _model_info(status=401)
        monkeypatch.setattr(httpx2.Client, "get", fake_get)
        settings = MagicMock()
        settings.ai = AIConfig(gateway_url=GATEWAY_URL, allow_private_network=True)
        monkeypatch.setattr("devops_cli.commands.ai_gateway.load_settings", lambda: settings)
        monkeypatch.setattr("devops_cli.commands.ai_gateway.get_ai_api_key", lambda _s: None)

        result = runner.invoke(gateway_cli_app, ["routes"])

        assert (result.exit_code, "DEVOPS_CLI_AI_API_KEY" in result.output) == (1, True)

    def test_list_routes_401_with_agent_grant_names_grant_and_omits_api_key_hint(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify a 401 with DEVOPS_CLI_AGENT_GRANT set names the grant ID, cuts long IDs, and omits the generic key hint."""
        _requests, fake_get = _model_info(status=401)
        monkeypatch.setattr(httpx2.Client, "get", fake_get)
        router = GatewayRouter(AIConfig(allow_private_network=True), api_key="stale-key")

        # Standard grant ID
        monkeypatch.setenv("DEVOPS_CLI_AGENT_GRANT", "g-123")
        with pytest.raises(AICredentialsError) as exc_info:
            router.list_routes(GATEWAY_URL)

        msg = str(exc_info.value)
        assert ("g-123" in msg, "DEVOPS_CLI_AI_API_KEY" not in msg, "person" in msg) == (
            True,
            True,
            True,
        )

        # Long grant ID cut to 256
        long_id = "x" * 300
        monkeypatch.setenv("DEVOPS_CLI_AGENT_GRANT", long_id)
        with pytest.raises(AICredentialsError) as exc_info_long:
            router.list_routes(GATEWAY_URL)

        msg_long = str(exc_info_long.value)
        assert (long_id[:256] in msg_long, long_id not in msg_long) == (True, True)

        # Without DEVOPS_CLI_AGENT_GRANT, message is unchanged
        monkeypatch.delenv("DEVOPS_CLI_AGENT_GRANT")
        with pytest.raises(AICredentialsError) as exc_info_orig:
            router.list_routes(GATEWAY_URL)

        msg_orig = str(exc_info_orig.value)
        assert ("DEVOPS_CLI_AI_API_KEY" in msg_orig, "g-123" not in msg_orig) == (True, True)

    def test_use_lan_brackets_ipv6_host(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verify devops ai gateway use-lan properly brackets IPv6 addresses when building base_url."""
        monkeypatch.setattr(
            "devops_cli.commands.ai_gateway.node_port_address",
            lambda *args, **kwargs: ("2001:db8::1", 30400),
        )
        probed_urls: list[str] = []
        monkeypatch.setattr(
            "devops_cli.commands.ai_gateway.validate_url_egress",
            lambda url, **kwargs: None,
        )
        monkeypatch.setattr(
            "devops_cli.commands.ai_gateway._probe_gateway_liveliness_and_models",
            lambda url, *args, **kwargs: probed_urls.append(url),
        )
        monkeypatch.setattr(
            "devops_cli.commands.ai_gateway.save_settings",
            lambda *args, **kwargs: None,
        )

        res = runner.invoke(gateway_cli_app, ["connect"])
        assert res.exit_code == 0
        assert probed_urls == ["http://[2001:db8::1]:30400"]
