"""Unit and integration tests for AI LLM Gateway and distributed model routing."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import httpx2
import pytest
from typer.testing import CliRunner

from devops_cli.ai.client import AICredentialsError
from devops_cli.ai.gateway import (
    GatewayRouter,
)
from devops_cli.commands.ai_gateway import app as gateway_cli_app
from devops_cli.config.constants import (
    CONST_AI_GATEWAY_PROVIDER,
    CONST_AI_GATEWAY_VIRTUAL_MODELS,
)
from devops_cli.config.defaults import (
    DEFAULT_VLLM_CLUSTER_URL,
    DEFAULT_VLLM_MODEL,
    DEFAULT_VLLM_SERVED_MODEL_NAME,
    DEFAULT_VLLM_SINGLE_CLUSTER_URL,
    DEFAULT_VLLM_SINGLE_SERVED_MODEL_NAME,
)
from devops_cli.config.settings import AIConfig

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
            status.backend_counts["vllm"],
        ) == (
            True,
            "http://example.com/v1",
            False,
            2,
            2,
        )

    def test_probe_gateway_degraded_http_status(self) -> None:
        """Verify probe_gateway marks status degraded when gateway returns 503."""
        router = GatewayRouter(AIConfig(gateway_url="http://example.com/v1"))
        mock_resp = MagicMock()
        mock_resp.status_code = 503

        with patch.object(httpx2.Client, "get", return_value=mock_resp):
            status = router.probe_gateway()

        assert (status.healthy, status.details.get("status_code")) == (False, 503)

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

    def test_resolve_model_context_thresholds(self) -> None:
        """Verify token counts and tasks correctly steer between chat, coder, reasoning, and embedding."""
        router = GatewayRouter()

        small_chat = router.resolve_model("summarize", token_count=1000, complexity="low")
        coder_task = router.resolve_model("persona_review", token_count=2000, complexity="medium")
        large_context = router.resolve_model("deep_review", token_count=35000, complexity="low")
        frontier_task = router.resolve_model("synthesis", token_count=5000, complexity="frontier")
        embedding = router.resolve_model("embed_documents", token_count=500)

        assert (
            small_chat,
            coder_task,
            large_context,
            frontier_task,
            embedding,
        ) == (
            (CONST_AI_GATEWAY_PROVIDER, "devops-chat"),
            (CONST_AI_GATEWAY_PROVIDER, "devops-coder"),
            (CONST_AI_GATEWAY_PROVIDER, "devops-reasoning"),
            (CONST_AI_GATEWAY_PROVIDER, "devops-reasoning"),
            (CONST_AI_GATEWAY_PROVIDER, "devops-embedding"),
        )

    def test_trigger_failover_simulation_and_execution(self, tmp_path: Path) -> None:
        """Verify simulated failover leaves routes untouched while non-simulated alters table."""
        state_file = tmp_path / "gateway_state.json"
        router = GatewayRouter(state_file=state_file)

        simulated = router.trigger_failover("devops-reasoning", simulate=True)
        assert (
            simulated["fallback_target"],
            simulated["simulated"],
            router.list_routes()[2].target_model,
        ) == (
            "devops-coder",
            True,
            DEFAULT_VLLM_SERVED_MODEL_NAME,
        )

        executed = router.trigger_failover("devops-reasoning", simulate=False)
        assert (
            executed["fallback_target"],
            executed["target_model"],
            executed["simulated"],
            router.list_routes()[2].target_model,
            router.list_routes()[2].backend_type,
        ) == (
            "devops-coder",
            DEFAULT_VLLM_SINGLE_SERVED_MODEL_NAME,
            False,
            DEFAULT_VLLM_SINGLE_SERVED_MODEL_NAME,
            "failover:vllm",
        )

    def test_default_routes_target_vllm_profiles(self) -> None:
        """Verify reasoning and coder aliases route to the dual- and single-GPU vLLM profiles."""
        routes = {
            r.virtual_model: (r.target_model, r.backend_type, r.backend_url)
            for r in GatewayRouter().list_routes()
        }

        assert (routes["devops-reasoning"], routes["devops-coder"]) == (
            (DEFAULT_VLLM_SERVED_MODEL_NAME, "vllm", DEFAULT_VLLM_CLUSTER_URL),
            (DEFAULT_VLLM_SINGLE_SERVED_MODEL_NAME, "vllm", DEFAULT_VLLM_SINGLE_CLUSTER_URL),
        )

    def test_trigger_failover_invalid_model_raises_value_error(self) -> None:
        """Verify unknown virtual model alias raises ValidationError (subclass of ValueError)."""
        router = GatewayRouter()
        with pytest.raises(ValueError, match="Unknown virtual model 'unknown-model'"):
            router.trigger_failover("unknown-model")

    def test_scale_vllm_parameters(self) -> None:
        """Verify vLLM scale configurations calculate correct VRAM aggregates with replica multiplication."""
        router = GatewayRouter()
        default_scale = router.scale_vllm()
        custom_scale = router.scale_vllm(replicas=2, tensor_parallel_size=4)

        assert (
            default_scale["model"],
            default_scale["served_model_name"],
            default_scale["replicas"],
            default_scale["tensor_parallel_size"],
            default_scale["total_vram_gb"],
            custom_scale["replicas"],
            custom_scale["tensor_parallel_size"],
            custom_scale["total_vram_gb"],
            custom_scale["vram_per_replica_gb"],
        ) == (
            DEFAULT_VLLM_MODEL,
            DEFAULT_VLLM_SERVED_MODEL_NAME,
            1,
            2,
            48,
            2,
            4,
            192,
            96,
        )


class TestAIGatewayCLI:
    """Test suite for CLI devops ai gateway commands."""

    def test_routes_command_table_and_json(self) -> None:
        """Verify 'devops ai gateway routes' executes with table and JSON formatting."""
        res_table = runner.invoke(gateway_cli_app, ["routes"])
        res_json = runner.invoke(gateway_cli_app, ["routes", "--format", "json"])

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
        res_sim = runner.invoke(
            gateway_cli_app,
            ["failover", "devops-reasoning", "--simulate", "--format", "json"],
        )
        parsed_sim = json.loads(res_sim.output)

        res_exec = runner.invoke(
            gateway_cli_app,
            ["failover", "devops-reasoning", "--no-simulate"],
        )

        res_err = runner.invoke(
            gateway_cli_app,
            ["failover", "nonexistent-model"],
        )

        assert (
            res_sim.exit_code,
            parsed_sim["simulated"],
            res_exec.exit_code,
            "Failover status: failover_active" in res_exec.output,
            res_err.exit_code,
        ) == (
            0,
            True,
            0,
            True,
            1,
        )

    def test_scale_command_execution(self) -> None:
        """Verify 'devops ai gateway scale' outputs scale parameters in table and JSON."""
        res_table = runner.invoke(gateway_cli_app, ["scale", "--replicas", "2"])
        res_json = runner.invoke(
            gateway_cli_app,
            ["scale", "--replicas", "2", "--tensor-parallel-size", "4", "--format", "json"],
        )

        parsed = json.loads(res_json.output)
        assert (
            res_table.exit_code,
            res_json.exit_code,
            "vLLM Scale Parameters" in res_table.output,
            parsed["replicas"],
            parsed["tensor_parallel_size"],
        ) == (
            0,
            0,
            True,
            2,
            4,
        )


class TestFastMCPGatewayTools:
    """Test suite for FastMCP server gateway tool bindings."""

    def test_fastmcp_gateway_tools_registered(self) -> None:
        """Verify FastMCP server exports gateway tools and resources."""
        from devops_cli.ai.mcp.server import (
            ai_backend_probe,
            ai_gateway_failover,
            ai_gateway_routes,
            ai_gateway_status,
            ai_lightllm_scale,
            ai_vllm_scale,
            get_ai_gateway_resource,
        )

        with patch("devops_cli.ai.mcp.server._run_mcp_cmd", return_value="{}") as mock_run:
            ai_gateway_status()
            ai_gateway_routes()
            ai_gateway_failover("devops-coder", simulate=True)
            ai_vllm_scale(replicas=2, tensor_parallel_size=2)
            ai_lightllm_scale(replicas=2, tensor_parallel_size=1)
            ai_backend_probe("lightllm")
            get_ai_gateway_resource()

        assert mock_run.call_count == 7


class TestRouterAndClientGatewayIntegration:
    """Test suite for Router fallback chain and LLMClient gateway provider dispatch."""

    def test_router_fallback_chain_respects_gateway_enabled(self) -> None:
        """Verify gateway is only inserted into fallback chain when gateway_enabled is True."""
        from devops_cli.ai.router import DataSensitivity, LLMRouter, TaskComplexity

        router_disabled = LLMRouter(AIConfig(gateway_enabled=False))
        chain_disabled = router_disabled._build_fallback_chain(
            "ollama", "qwen2.5-coder:7b", TaskComplexity.LOW, DataSensitivity.INTERNAL
        )

        router_enabled = LLMRouter(AIConfig(gateway_enabled=True))
        chain_enabled = router_enabled._build_fallback_chain(
            "ollama", "qwen2.5-coder:7b", TaskComplexity.LOW, DataSensitivity.INTERNAL
        )

        assert (
            any(prov == "gateway" for prov, _ in chain_disabled),
            chain_enabled[0][0],
        ) == (
            False,
            "gateway",
        )

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

    def test_scale_vllm_kubectl_apply_success_and_failure(self) -> None:
        """Verify scale_vllm applies kubectl scale command when apply=True."""
        router = GatewayRouter()
        mock_proc_ok = MagicMock(returncode=0, stdout="deployment.apps/vllm scaled", stderr="")
        mock_proc_err = MagicMock(
            returncode=1, stdout="", stderr="Error from server: connection refused"
        )

        with patch("subprocess.run", return_value=mock_proc_ok) as mock_sub:
            res_ok = router.scale_vllm(replicas=3, apply=True)
            called_cmd = mock_sub.call_args[0][0]

        with patch("subprocess.run", return_value=mock_proc_err):
            res_err = router.scale_vllm(replicas=3, apply=True)

        assert (
            res_ok["status"],
            "--replicas=3" in called_cmd,
            res_err["status"],
            "connection refused" in res_err["details"]["error"],
        ) == (
            "scaled",
            True,
            "error",
            True,
        )

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
                "api_base": "http://vllm.example.com:8000/v1",
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
