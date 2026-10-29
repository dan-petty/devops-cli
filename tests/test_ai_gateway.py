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
from tests.support.config_writes import written_keys
from tests.web_fakes import PUBLIC_ADDRESS, http_response, record_connects, scripted_resolver

pytestmark = pytest.mark.usefixtures("keyring_store", "public_dns")

runner = CliRunner()


def _write_routes_with_a_small_coder(state_file: Path) -> None:
    """Write devops-coder in failover to gpt-oss:20b, below the 30B floor of devops-reasoning,
    which fails over to devops-coder. No default route is below the floor of a virtual model that
    fails over to it."""
    routes = [
        route.model_copy(update={"target_model": "gpt-oss:20b", "backend_type": "failover:ollama"})
        if route.virtual_model == "devops-coder"
        else route
        for route in GatewayRouter(state_file=state_file).list_routes()
    ]
    state_file.parent.mkdir(parents=True, exist_ok=True)
    state_file.write_text(
        json.dumps(
            {
                "circuit_breaker_active": True,
                "routes": [
                    route.model_dump()
                    for route in routes
                    if route.backend_type.startswith("failover:")
                ],
            }
        ),
        encoding="utf-8",
    )


def _default_route_file() -> dict[str, Any]:
    """The route file that holds no failover routes and no tripped breaker."""
    return {
        "circuit_breaker_active": False,
        "routes": [],
    }


def _answer_every_get(monkeypatch: pytest.MonkeyPatch, status: int) -> None:
    """Make every GET of the gateway health probe receive `status`."""

    def fake_get(self: Any, url: str, **kwargs: Any) -> httpx2.Response:
        return httpx2.Response(status, request=httpx2.Request("GET", url))

    monkeypatch.setattr(httpx2.Client, "get", fake_get)


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

    def test_saved_file_with_old_default_route_uses_current_defaults(self, tmp_path: Path) -> None:
        """Verify a saved route file that holds an old default route is ignored and the router
        uses the current default route (#2045)."""
        state_file = tmp_path / "gateway_state.json"
        state_file.write_text(
            json.dumps(
                {
                    "circuit_breaker_active": False,
                    "routes": [
                        {
                            "virtual_model": "devops-chat",
                            "target_model": "qwen2.5-coder:7b",
                            "backend_type": "ollama",
                            "backend_url": "http://ollama-fast.llm.svc.cluster.local:11434",
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        router = GatewayRouter(state_file=state_file)
        chat_route = next(r for r in router.list_routes() if r.virtual_model == "devops-chat")
        assert (chat_route.target_model, chat_route.backend_type) == ("qwen3.8:27b", "ollama")

    def test_saved_failover_route_persists_after_restart(self, tmp_path: Path) -> None:
        """Verify a saved failover:* route still applies after a router restart (#2045)."""
        state_file = tmp_path / "gateway_state.json"
        state_file.write_text(
            json.dumps(
                {
                    "circuit_breaker_active": True,
                    "routes": [
                        {
                            "virtual_model": "devops-chat",
                            "target_model": "qwen3.8:27b",
                            "backend_type": "failover:ollama",
                            "backend_url": "http://ollama-fast.llm.svc.cluster.local:11434",
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        router = GatewayRouter(state_file=state_file)
        chat_route = next(r for r in router.list_routes() if r.virtual_model == "devops-chat")
        coder_route = next(r for r in router.list_routes() if r.virtual_model == "devops-coder")
        assert (
            chat_route.target_model,
            chat_route.backend_type,
            coder_route.target_model,
            coder_route.backend_type,
        ) == (
            "qwen3.8:27b",
            "failover:ollama",
            "qwen3-coder:30b",
            "ollama",
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

        # devops-coder fails over to devops-chat (27b >= 7b), satisfying capability tier
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
            "qwen3.8:27b",
            False,
        )

    def test_direct_ollama_failover_targets_the_default_ollama_tier(self, tmp_path: Path) -> None:
        """Verify devops-chat fails over to the Service of the default Ollama tier (#953), with the
        model of its default route (#1969).

        The direct-Ollama fallback sent requests to `ollama.llm.svc.cluster.local`, a Service
        nothing deploys since the Ollama tiers replaced the single `ollama` workload, and it named
        `qwen2.5-coder:7b`, which that tier does not hold.
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

        assert (
            chat.target_model,
            chat.backend_type,
            chat.backend_url,
            namespace,
            service in tier_services,
        ) == ("qwen3.8:27b", "failover:ollama", DEFAULT_OLLAMA_CLUSTER_URL, "llm", True)

    def test_trigger_failover_capability_gating(self, tmp_path: Path) -> None:
        """Verify reasoning failover to underpowered tier is blocked without --force."""
        state_file = tmp_path / "gateway_state.json"
        _write_routes_with_a_small_coder(state_file)
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

    def test_a_healthy_probe_keeps_a_failover_route_and_the_status_reports_it(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify a healthy probe keeps the failover route and the tripped breaker, and the status
        names the virtual model in failover (#1986).

        A healthy probe cleared the breaker and kept the route, so the status showed a healthy
        gateway while devops-chat still pointed at its failover backend.
        """
        state_file = tmp_path / "gateway_state.json"
        GatewayRouter(state_file=state_file).trigger_failover("devops-chat", simulate=False)
        _answer_every_get(monkeypatch, 200)

        status = GatewayRouter(
            AIConfig(gateway_url="http://example.com/v1"), state_file=state_file
        ).probe_gateway()
        saved = GatewayRouter(state_file=state_file).list_routes()

        assert (
            status.healthy,
            status.circuit_breaker_tripped,
            status.failover_routes,
            [(r.virtual_model, r.target_model, r.backend_type) for r in saved],
        ) == (
            True,
            True,
            ["devops-chat"],
            [
                ("devops-chat", "qwen3.8:27b", "failover:ollama"),
                ("devops-coder", "qwen3-coder:30b", "ollama"),
                ("devops-reasoning", "qwen3-coder:30b", "ollama"),
                ("devops-embedding", "qwen3-embedding:0.6b", "ollama"),
            ],
        )

    def test_failover_reset_restores_the_default_routes(self, tmp_path: Path) -> None:
        """Verify a reset writes no failover routes to the route file and clears the breaker
        (#1986, #2045). The file starts with a route in failover."""
        state_file = tmp_path / "gateway_state.json"
        _write_routes_with_a_small_coder(state_file)
        GatewayRouter(state_file=state_file).trigger_failover(
            "devops-reasoning", simulate=False, force=True
        )

        outcome = GatewayRouter(state_file=state_file).reset_failover()

        assert (outcome, json.loads(state_file.read_text(encoding="utf-8"))) == (
            {
                "status": "reset",
                "restored_routes": ["devops-coder", "devops-reasoning"],
                "circuit_breaker_tripped": False,
            },
            _default_route_file(),
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

    def test_failover_command_execution(self, isolate_data_dir: Path) -> None:
        """Verify 'devops ai gateway failover' triggers simulated and active transitions."""
        _write_routes_with_a_small_coder(isolate_data_dir / "agent" / "gateway_state.json")
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

    def test_status_reports_the_routes_in_failover(
        self, isolate_data_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify `status` names the routes in failover after a healthy probe, and names the reset
        (#1986)."""
        res_failover = runner.invoke(gateway_cli_app, ["failover", "devops-chat", "--no-simulate"])
        _answer_every_get(monkeypatch, 200)

        res_table = runner.invoke(gateway_cli_app, ["status"])
        res_json = runner.invoke(gateway_cli_app, ["status", "--format", "json"])

        parsed = json.loads(res_json.output)
        assert (
            res_failover.exit_code,
            res_table.exit_code,
            "Failover routes: devops-chat" in res_table.output,
            "--reset" in res_table.output,
            res_json.exit_code,
            parsed["healthy"],
            parsed["circuit_breaker_tripped"],
            parsed["failover_routes"],
        ) == (0, 0, True, True, 0, True, True, ["devops-chat"])

    def test_failover_reset_command(self, isolate_data_dir: Path) -> None:
        """Verify `failover --reset` restores the default routes and takes no virtual model
        (#1986)."""
        state_file = isolate_data_dir / "agent" / "gateway_state.json"
        runner.invoke(gateway_cli_app, ["failover", "devops-chat", "--no-simulate"])
        res_table = runner.invoke(gateway_cli_app, ["failover", "--reset"])
        runner.invoke(gateway_cli_app, ["failover", "devops-coder", "--no-simulate"])
        res_json = runner.invoke(gateway_cli_app, ["failover", "--reset", "--format", "json"])
        route_file = json.loads(state_file.read_text(encoding="utf-8"))
        res_both = runner.invoke(gateway_cli_app, ["failover", "devops-chat", "--reset"])
        res_none = runner.invoke(gateway_cli_app, ["failover"])

        assert (
            res_table.exit_code,
            "devops-chat" in res_table.output,
            res_json.exit_code,
            json.loads(res_json.output),
            route_file,
            res_both.exit_code,
            res_none.exit_code,
        ) == (
            0,
            True,
            0,
            {
                "status": "reset",
                "restored_routes": ["devops-coder"],
                "circuit_breaker_tripped": False,
            },
            _default_route_file(),
            2,
            2,
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

    def test_fastmcp_gateway_failover_resets_the_routes(self, isolate_data_dir: Path) -> None:
        """Verify the tool `ai_gateway_failover` with `reset` restores the default routes, although
        the tool sends its `simulate` default as `--simulate` (#1986)."""
        from devops_cli.ai.mcp.server import ai_gateway_failover

        GatewayRouter().trigger_failover("devops-chat", simulate=False)

        outcome = json.loads(ai_gateway_failover(reset=True))

        assert (
            outcome,
            json.loads(
                (isolate_data_dir / "agent" / "gateway_state.json").read_text(encoding="utf-8")
            ),
        ) == (
            {
                "status": "reset",
                "restored_routes": ["devops-chat"],
                "circuit_breaker_tripped": False,
            },
            _default_route_file(),
        )


GATEWAY_TOOL_PARAMETERS = {
    "ai_gateway_status": ["provider"],
    "ai_gateway_routes": ["provider"],
    "ai_gateway_probe_backend": ["backend"],
}
"""The parameters that the MCP tools of the gateway read-only commands publish: no URL."""


async def _call_gateway_tool(tool: str, arguments: dict[str, object]) -> bool:
    """Call a tool the way an MCP client does, and say whether the call failed."""
    from fastmcp import Client

    from devops_cli.ai.mcp.server import mcp

    async with Client(mcp) as client:
        result = await client.call_tool(tool, arguments, raise_on_error=False)
    return bool(result.is_error)


class TestGatewayToolsTakeNoUrlFromTheModel:
    """The read-only MCP gateway tools query the configured gateway and backend, never a URL that
    the calling model gives (#2480)."""

    async def test_the_tools_publish_no_url_parameter(self) -> None:
        """The schema of each tool holds the provider or the backend and no gateway or backend URL."""
        from fastmcp import Client

        from devops_cli.ai.mcp.server import mcp

        async with Client(mcp) as client:
            tools = await client.list_tools()

        assert {
            tool.name: list(tool.input_schema["properties"])
            for tool in tools
            if tool.name in GATEWAY_TOOL_PARAMETERS
        } == GATEWAY_TOOL_PARAMETERS

    @pytest.mark.parametrize(
        ("tool", "arguments"),
        [
            (
                "ai_gateway_probe_backend",
                {"backend": "ollama", "backend_url": "http://127.0.0.1:8200/v1/sys/seal-status?x="},
            ),
            ("ai_gateway_routes", {"gateway_url": "https://attacker.example.org/v1"}),
            ("ai_gateway_status", {"gateway_url": "https://attacker.example.org/v1"}),
        ],
        ids=["backend on loopback", "routes on a public host", "status on a public host"],
    )
    async def test_a_url_argument_is_refused_and_reaches_no_socket(
        self, monkeypatch: pytest.MonkeyPatch, tool: str, arguments: dict[str, object]
    ) -> None:
        """A call that gives a URL fails, no request is sent, and the AI API key is not on the wire.

        On `origin/main` the loopback call dialled `127.0.0.1:8200` with no flag, and the routes
        call sent `Authorization: Bearer <key>` to the public host.
        """
        monkeypatch.setenv("DEVOPS_CLI_AI_API_KEY", "sk-secret")
        scripted_resolver(monkeypatch, {"attacker.example.org": [[PUBLIC_ADDRESS]]})
        recorder = record_connects(monkeypatch, [http_response(200, "{}")] * 4)

        failed = await _call_gateway_tool(tool, arguments)

        reached = {(PUBLIC_ADDRESS, 443), ("127.0.0.1", 8200)}
        assert (
            failed,
            [dial for dial in recorder.dialled if dial in reached],
            b"sk-secret" in b"".join(recorder.written),
        ) == (True, [], False)

    @pytest.mark.parametrize(
        ("answer", "flag", "dialled"),
        [
            ("127.0.0.1", "false", [("127.0.0.1", 80)]),
            ("192.0.2.10", "false", []),
            ("192.0.2.10", "true", [("192.0.2.10", 80)]),
        ],
        ids=["loopback without the flag", "private without the flag", "private with the flag"],
    )
    async def test_the_status_tool_dials_the_configured_gateway_at_the_configured_level(
        self,
        monkeypatch: pytest.MonkeyPatch,
        answer: str,
        flag: str,
        dialled: list[tuple[str, int]],
    ) -> None:
        """Loopback, and private addresses with `ai.allow_private_network`, as for the CLI."""
        monkeypatch.setenv("DEVOPS_CLI_AI_GATEWAY_URL", "http://gateway.example.com/v1")
        monkeypatch.setenv("DEVOPS_CLI_AI_ALLOW_PRIVATE_NETWORK", flag)
        scripted_resolver(monkeypatch, {"gateway.example.com": [[answer]]})
        recorder = record_connects(monkeypatch, [http_response(200, "{}")])

        failed = await _call_gateway_tool("ai_gateway_status", {})

        assert (failed, [dial for dial in recorder.dialled if dial[0] == answer]) == (
            not dialled,
            dialled,
        )


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
        router = GatewayRouter(
            AIConfig(gateway_url=GATEWAY_URL, allow_private_network=True), api_key="sk-gateway"
        )

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
        router = GatewayRouter(
            AIConfig(gateway_url=GATEWAY_URL, allow_private_network=True), api_key=api_key
        )

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
        router = GatewayRouter(
            AIConfig(gateway_url=GATEWAY_URL, allow_private_network=True), api_key="stale-key"
        )

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

    def test_use_lan_brackets_ipv6_host(
        self, monkeypatch: pytest.MonkeyPatch, config: Any, isolate_data_dir: Path
    ) -> None:
        """Verify devops ai gateway use-lan properly brackets IPv6 addresses when building base_url,
        and writes only `ai.gateway_url` and `ai.allow_private_network` into the config file."""
        config(ai={"allow_private_network": False})
        monkeypatch.delenv("DEVOPS_CLI_AI_ALLOW_PRIVATE_NETWORK", raising=False)
        monkeypatch.setattr(
            "devops_cli.commands.ai_gateway.node_port_address",
            lambda *args, **kwargs: ("2001:db8::1", 30400),
        )
        probed_urls: list[str] = []
        monkeypatch.setattr(
            "devops_cli.commands.ai_gateway._probe_gateway_liveliness_and_models",
            lambda url, *args, **kwargs: probed_urls.append(url),
        )

        res = runner.invoke(gateway_cli_app, ["connect"])
        assert res.exit_code == 0
        assert probed_urls == ["http://[2001:db8::1]:30400"]
        assert written_keys(isolate_data_dir) == [["ai.allow_private_network", "ai.gateway_url"]]


class TestTheKeyGoesOnlyToTheConfiguredGateway:
    """A URL override is input from a caller. `routes` sends the AI API key only to the origin of
    the configured gateway (#2480)."""

    @staticmethod
    def _requests_of_discovery(
        monkeypatch: pytest.MonkeyPatch, ai_config: AIConfig, url: str
    ) -> list[bytes]:
        """List the routes at `url`; return the request bytes that each connection received."""
        scripted_resolver(
            monkeypatch,
            {
                "gateway.example.com": [[PUBLIC_ADDRESS]],
                "attacker.example.com": [[PUBLIC_ADDRESS]],
            },
        )
        recorder = record_connects(monkeypatch, [http_response(200, '{"data": []}')] * 2)
        GatewayRouter(ai_config, api_key="sk-gateway").list_routes(url)
        return [bytes(written) for written in recorder.written]

    @pytest.mark.parametrize(
        ("url", "gets_key"),
        [
            ("http://gateway.example.com:4000/v1", True),
            ("http://gateway.example.com:4000/another/path", True),
            ("HTTP://Gateway.Example.com:4000/v1", True),
            ("http://attacker.example.com:4000/v1", False),
            ("http://gateway.example.com:4001/v1", False),
            ("https://gateway.example.com:4000/v1", False),
            ("http://gateway.example.com:4000@attacker.example.com:4000/v1", False),
        ],
        ids=[
            "the configured URL",
            "another path",
            "another spelling of the origin",
            "another host",
            "another port",
            "another scheme",
            "the configured origin as user information",
        ],
    )
    def test_a_request_carries_the_key_only_for_the_configured_origin(
        self, monkeypatch: pytest.MonkeyPatch, url: str, gets_key: bool
    ) -> None:
        written = self._requests_of_discovery(monkeypatch, AIConfig(gateway_url=GATEWAY_URL), url)

        assert [b"Bearer sk-gateway" in request for request in written] == [gets_key]

    def test_no_override_gets_the_key_when_no_gateway_is_configured(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        written = self._requests_of_discovery(monkeypatch, AIConfig(), GATEWAY_URL)

        assert [b"Bearer sk-gateway" in request for request in written] == [False]

    def test_the_routes_command_sends_no_key_to_another_gateway(
        self, monkeypatch: pytest.MonkeyPatch, cli: Any
    ) -> None:
        monkeypatch.setenv("DEVOPS_CLI_AI_GATEWAY_URL", GATEWAY_URL)
        monkeypatch.setenv("DEVOPS_CLI_AI_API_KEY", "sk-gateway")
        scripted_resolver(monkeypatch, {"attacker.example.com": [[PUBLIC_ADDRESS]]})
        recorder = record_connects(monkeypatch, [http_response(200, '{"data": []}')] * 2)

        result = cli("ai", "gateway", "routes", "--gateway-url", "http://attacker.example.com/v1")

        assert (
            result.exit_code,
            recorder.requested_hosts,
            b"sk-gateway" in b"".join(recorder.written),
        ) == (0, ["attacker.example.com"], False)

    def test_a_refusal_by_another_gateway_says_that_it_got_no_key(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The AI API key is set, so a message that asks for a key would mislead."""
        scripted_resolver(monkeypatch, {"attacker.example.com": [[PUBLIC_ADDRESS]]})
        record_connects(monkeypatch, [http_response(401, "{}")])
        router = GatewayRouter(AIConfig(gateway_url=GATEWAY_URL), api_key="sk-gateway")

        with pytest.raises(AICredentialsError) as refused:
            router.list_routes("http://attacker.example.com:4000/v1")

        assert str(refused.value) == (
            "The LLM gateway at attacker.example.com:4000 requires an API key. "
            "The AI API key goes only to the configured gateway, so this gateway got none. "
            "To use the key with this gateway, make it the configured gateway."
        )
