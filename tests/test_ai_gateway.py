"""Unit and integration tests for AI LLM Gateway and distributed model routing."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import httpx2
import pytest
from typer.testing import CliRunner

from devops_cli.ai.gateway import (
    GatewayRouter,
)
from devops_cli.commands.ai_gateway import app as gateway_cli_app
from devops_cli.config.constants import (
    CONST_AI_GATEWAY_PROVIDER,
    CONST_AI_GATEWAY_VIRTUAL_MODELS,
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
            3,
            1,
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
            "llama-3.3-70b-instruct",
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
            "qwen2.5-coder:14b",
            False,
            "qwen2.5-coder:14b",
            "failover:ollama",
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
            default_scale["replicas"],
            default_scale["tensor_parallel_size"],
            default_scale["total_vram_gb"],
            custom_scale["replicas"],
            custom_scale["tensor_parallel_size"],
            custom_scale["total_vram_gb"],
            custom_scale["vram_per_replica_gb"],
        ) == (
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
