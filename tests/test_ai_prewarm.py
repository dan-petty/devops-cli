"""Unit and integration test suite for local model prewarming and VRAM eviction."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock, patch

if TYPE_CHECKING:
    from tests.support.fakes.model import ModelFake
    from tests.support.fakes.otlp import FakeCollector

import httpx2
import pytest
from typer.testing import CliRunner

from devops_cli.ai.client.ollama import OllamaProviderMixin
from devops_cli.commands.ai import _render_prewarm_results, _resolve_prewarm_urls
from devops_cli.config.settings import AIConfig
from devops_cli.exceptions import ValidationError
from devops_cli.telemetry.instruments import AI_PREWARMS_TOTAL
from tests.web_fakes import PUBLIC_ADDRESS, http_response, record_connects, scripted_resolver

runner = CliRunner()


class DummyOllamaProvider(OllamaProviderMixin):
    """Dummy provider implementation for isolating OllamaProviderMixin methods."""

    def __init__(self, config: AIConfig) -> None:
        self._config = config

    def _validate_base_url(self, base_url: str, purpose: str = "API") -> str:
        return base_url.rstrip("/")

    def _request_timeout(self) -> httpx2.Timeout:
        return httpx2.Timeout(5.0)


class TestOllamaProviderPrewarm:
    """Test suite for OllamaProviderMixin prewarm and VRAM eviction methods."""

    def test_preload_single_ollama_url_success(self) -> None:
        """Verify successful single-node prewarm dispatches to /api/generate with 200."""
        config = AIConfig(provider="ollama", model="gemma4:26b")
        provider = DummyOllamaProvider(config)

        mock_http = MagicMock()
        mock_http.post.return_value = MagicMock(status_code=200)
        with patch.object(type(provider), "_shared_client", return_value=mock_http):
            url, ok = provider._preload_single_ollama_url(
                "http://example.com:11434",
                model="gemma4:26b",
                keep_alive="1h",
            )
            assert (url, ok) == ("http://example.com:11434", True)

            # The timeout is now a per-request argument: the client is shared, so it
            # cannot carry one caller's timeout.
            assert mock_http.post.call_args.args == ("http://example.com:11434/api/generate",)
            assert mock_http.post.call_args.kwargs["json"] == {
                "model": "gemma4:26b",
                "prompt": "",
                "keep_alive": "1h",
            }

    def test_preload_single_ollama_url_failure(self) -> None:
        """Verify failing status code or connection exception returns ok=False."""
        config = AIConfig(provider="ollama", model="gemma4:26b")
        provider = DummyOllamaProvider(config)

        mock_http = MagicMock()
        mock_http.post.side_effect = ConnectionError("Connection refused")
        with patch.object(type(provider), "_shared_client", return_value=mock_http):
            url, ok = provider._preload_single_ollama_url(
                "http://example.com:11434",
                model="gemma4:26b",
                keep_alive="1h",
            )
            assert (url, ok) == ("http://example.com:11434", False)

    def test_preload_single_ollama_url_eviction_payload(self) -> None:
        """Verify VRAM eviction payload sends keep_alive=0 to /api/generate."""
        config = AIConfig(provider="ollama", model="gemma4:26b")
        provider = DummyOllamaProvider(config)

        mock_http = MagicMock()
        mock_http.post.return_value = MagicMock(status_code=200)
        with patch.object(type(provider), "_shared_client", return_value=mock_http):
            url, ok = provider._preload_single_ollama_url(
                "http://example.com:11434",
                model="qwen2.5-coder:7b",
                keep_alive=0,
            )
            assert (url, ok) == ("http://example.com:11434", True)
            # The timeout is now a per-request argument: the client is shared, so it
            # cannot carry one caller's timeout.
            assert mock_http.post.call_args.args == ("http://example.com:11434/api/generate",)
            assert mock_http.post.call_args.kwargs["json"] == {
                "model": "qwen2.5-coder:7b",
                "prompt": "",
                "keep_alive": 0,
            }

    def test_execute_preload_all_and_callback(self) -> None:
        """Verify concurrent multi-node prewarm execution and on_complete callback dispatch."""
        config = AIConfig(
            provider="ollama",
            model="gemma4:26b",
            ollama_urls=["http://localhost:11434", "http://example.com:11434"],
        )
        provider = DummyOllamaProvider(config)
        callback_results: dict[str, bool] = {}

        def record_callback(res: dict[str, bool]) -> None:
            callback_results.update(res)

        with patch.object(
            provider,
            "_preload_single_ollama_url",
            side_effect=[("http://localhost:11434", True), ("http://example.com:11434", True)],
        ):
            results = provider._execute_preload_all(
                ["http://localhost:11434", "http://example.com:11434"],
                on_complete=record_callback,
                model="gemma4:26b",
                keep_alive="1h",
            )
            expected = {"http://localhost:11434": True, "http://example.com:11434": True}
            assert (results, callback_results) == (expected, expected)

    def test_execute_preload_all_callback_failure_handled(self) -> None:
        """Verify exception raised in on_complete callback is caught and logged."""
        config = AIConfig(provider="ollama", model="gemma4:26b")
        provider = DummyOllamaProvider(config)

        def bad_callback(_: dict[str, bool]) -> None:
            raise RuntimeError("Callback crashed")

        with patch.object(
            provider,
            "_preload_single_ollama_url",
            return_value=("http://localhost:11434", True),
        ):
            results = provider._execute_preload_all(
                ["http://localhost:11434"],
                on_complete=bad_callback,
                model="gemma4:26b",
                keep_alive="1h",
            )
            assert results == {"http://localhost:11434": True}

    def test_preload_models_provider_guard(self) -> None:
        """Verify preload_models exits early when provider is not ollama or urls are empty."""
        non_ollama = DummyOllamaProvider(AIConfig(provider="openai", model="gpt-4o"))
        provider = DummyOllamaProvider(AIConfig(provider="ollama", model="gemma4:26b"))

        res_provider = non_ollama.preload_models()
        res_urls = provider.preload_models(urls=[])
        assert (res_provider, res_urls) == ({}, {})

    def test_preload_models_non_blocking_starts_thread(self) -> None:
        """Verify non-blocking preload launches daemon background thread and returns immediately."""
        config = AIConfig(
            provider="ollama",
            model="gemma4:26b",
            ollama_urls=["http://localhost:11434"],
        )
        provider = DummyOllamaProvider(config)

        with patch("threading.Thread") as mock_thread_cls:
            mock_thread = MagicMock()
            mock_thread_cls.return_value = mock_thread

            res = provider.preload_models(blocking=False)
            assert res == {}
            assert (mock_thread_cls.called, mock_thread.start.called) == (True, True)

    def test_evict_models_and_prewarm_async_convenience_methods(self) -> None:
        """Verify evict_models delegates with keep_alive=0 and prewarm_async delegates non-blocking."""
        config = AIConfig(
            provider="ollama",
            model="gemma4:26b",
            ollama_urls=["http://localhost:11434"],
        )
        provider = DummyOllamaProvider(config)

        with patch.object(
            provider, "preload_models", return_value={"http://localhost:11434": True}
        ) as mock_preload:
            res_evict = provider.evict_models(model="gemma4:26b")
            provider.prewarm_async()

            assert res_evict == {"http://localhost:11434": True}
            mock_preload.assert_any_call(
                model="gemma4:26b",
                keep_alive=0,
                urls=None,
                blocking=True,
                on_complete=None,
            )
            has_async = any(c.kwargs.get("blocking") is False for c in mock_preload.call_args_list)
            assert has_async is True


class TestUnifiedLLMClientPrewarm:
    """Test suite verifying LLMClient inherits and executes prewarm capabilities."""

    def test_unified_client_prewarm_and_evict_delegation(self) -> None:
        """Verify LLMClient instance exposes prewarm_models and evict_models."""
        from devops_cli.ai.client.unified import LLMClient

        config = AIConfig(
            provider="ollama",
            model="gemma4:26b",
            ollama_urls=["http://localhost:11434"],
        )
        client = LLMClient(config=config, cache_enabled=False)

        with patch.object(
            client, "preload_models", return_value={"http://localhost:11434": True}
        ) as mock_preload:
            prewarm_res = client.prewarm_models(keep_alive="24h")
            evict_res = client.evict_models()

            assert (prewarm_res, evict_res) == (
                {"http://localhost:11434": True},
                {"http://localhost:11434": True},
            )
            has_prewarm = any(
                c.kwargs.get("keep_alive") == "24h" for c in mock_preload.call_args_list
            )
            has_evict = any(c.kwargs.get("keep_alive") == 0 for c in mock_preload.call_args_list)
            assert (has_prewarm, has_evict) == (True, True)


class TestCLIPrewarmHelpers:
    """Test suite for URL resolution and output rendering helpers."""

    def test_resolve_prewarm_urls(self) -> None:
        """Verify URL resolution logic across explicit overrides and all-nodes flags."""
        configured = ["http://localhost:11434", "http://example.com:11434"]

        res_override = _resolve_prewarm_urls("http://example.com:11434", True, configured)
        res_all = _resolve_prewarm_urls(None, True, configured)
        res_single = _resolve_prewarm_urls(None, False, configured)
        res_empty = _resolve_prewarm_urls(None, False, [])

        assert (res_override, res_all, res_single, res_empty) == (
            ["http://example.com:11434"],
            configured,
            ["http://localhost:11434"],
            [],
        )

    def test_render_prewarm_results_console_and_json(self) -> None:
        """Verify console and JSON formatting for prewarm and eviction results."""
        results = {"http://localhost:11434": True, "http://example.com:11434": False}

        with patch("devops_cli.output.write_stdout") as mock_stdout:
            json_success = _render_prewarm_results(
                results=results,
                model="gemma4:26b",
                keep_alive="1h",
                is_evict=False,
                json_output=True,
            )
            assert json_success is False
            written = json.loads(mock_stdout.call_args[0][0])
            assert (written["action"], written["model"], written["success"]) == (
                "prewarming",
                "gemma4:26b",
                False,
            )

        with (
            patch("devops_cli.commands.ai.print_info") as mock_info,
            patch("devops_cli.commands.ai.print_success") as mock_success,
            patch("devops_cli.commands.ai.print_error") as mock_error,
        ):
            console_success = _render_prewarm_results(
                results={"http://localhost:11434": True},
                model="gemma4:26b",
                keep_alive="1h",
                is_evict=False,
                json_output=False,
            )
            assert console_success is True
            assert (mock_info.called, mock_success.called, mock_error.called) == (True, True, False)


class TestCLIPrewarmCommand:
    """Test suite for 'devops ai prewarm' CLI command."""

    @pytest.fixture
    def app(self):
        from devops_cli.main import app

        return app

    def test_cli_prewarm_success_default_args(self, app: Any, model_fake: ModelFake) -> None:
        """Verify devops ai prewarm succeeds with default configured model and urls."""
        result = runner.invoke(app, ["ai", "prewarm"])

        assert result.exit_code == 0
        assert "prewarmed into VRAM" in result.output
        assert "confirmed HTTP 200" in result.output

    def test_cli_prewarm_evict_and_json_flag(self, app: Any, model_fake: ModelFake) -> None:
        """Verify devops ai prewarm --evict --json passes keep_alive=0 and emits structured json."""
        result = runner.invoke(app, ["ai", "prewarm", "--evict", "--json"])

        assert result.exit_code == 0
        payload = json.loads(result.output)
        assert (payload["action"], payload["keep_alive"], payload["success"]) == (
            "eviction",
            0,
            True,
        )

    def test_cli_prewarm_failure_exits_code_1(self, app: Any, model_fake: ModelFake) -> None:
        """Verify devops ai prewarm exits with code 1 when node prewarming fails."""
        model_fake.set_preload_results({"http://localhost:11434": False})
        result = runner.invoke(app, ["ai", "prewarm"])

        assert result.exit_code == 1
        assert "request failed or timed out" in result.output

    def test_cli_prewarm_single_node_flag(self, app: Any, model_fake: ModelFake) -> None:
        """Verify devops ai prewarm --single-node targets only primary node."""
        result = runner.invoke(app, ["ai", "prewarm", "--single-node"])

        assert result.exit_code == 0
        assert model_fake.preload_calls[-1]["urls"] == ["http://localhost:11434"]

    @pytest.mark.parametrize(
        ("node_ok", "exit_code", "outcome"), [(True, 0, "ok"), (False, 1, "failed")]
    )
    def test_a_prewarm_run_counts_once_by_model_evict_and_outcome(
        self,
        app: Any,
        model_fake: ModelFake,
        otlp: FakeCollector,
        node_ok: bool,
        exit_code: int,
        outcome: str,
    ) -> None:
        """Verify devops ai prewarm counts its run one time, by model, evict and outcome."""
        model_fake.set_preload_results({"http://localhost:11434": node_ok})

        result = runner.invoke(app, ["ai", "prewarm", "--model", "gemma4:26b", "--single-node"])

        assert (result.exit_code, otlp.points(AI_PREWARMS_TOTAL.name)) == (
            exit_code,
            [({"model": "gemma4:26b", "evict": "false", "outcome": outcome}, 1.0)],
        )


class TestFastMCPPrewarmTool:
    """Test suite for FastMCP ai_prewarm tool."""

    def test_ai_prewarm_tool_dispatch(self) -> None:
        """Verify ai_prewarm tool invokes devops ai prewarm with safe arguments."""
        from devops_cli.ai.mcp.server import ai_prewarm

        with patch("devops_cli.ai.mcp.server._run_mcp_cmd", return_value="Success") as mock_cmd:
            res = ai_prewarm(
                model="qwen2.5-coder:7b",
                keep_alive="24h",
                evict=True,
                all_nodes=True,
            )
            assert res == "Success"
            called_cmd = mock_cmd.call_args[0][0]
            expected_flags = [
                "uv",
                "run",
                "devops",
                "ai",
                "prewarm",
                "--model",
                "qwen2.5-coder:7b",
                "--keep-alive",
                "24h",
                "--all-nodes",
                "--evict",
                "--format",
                "table",
            ]
            assert called_cmd == expected_flags

    def test_ai_prewarm_tool_flag_injection_rejected(self) -> None:
        """Verify ai_prewarm rejects hyphen-prefixed model or keep-alive argument."""
        from devops_cli.ai.mcp.server import ai_prewarm

        with pytest.raises(ValidationError):
            ai_prewarm(model="--injected-flag")

        with pytest.raises(ValidationError):
            ai_prewarm(keep_alive="--bad-duration")


PREWARM_TOOL_PARAMETERS = [
    "model",
    "keep_alive",
    "all_nodes",
    "evict",
    "output_format",
    "json_output",
]
"""The parameters that the MCP tool of `devops ai prewarm` publishes: no URL."""

_PREWARM_REQUEST_LINE = b"POST /api/generate HTTP/1.1"


async def _call_prewarm_tool(arguments: dict[str, object]) -> tuple[bool, str]:
    """Call the tool the way an MCP client does: whether the call failed, and its reply."""
    from fastmcp import Client

    from devops_cli.ai.mcp.server import mcp

    async with Client(mcp) as client:
        result = await client.call_tool("ai_prewarm", arguments, raise_on_error=False)
    return bool(result.is_error), "\n".join(getattr(block, "text", "") for block in result.content)


@pytest.mark.usefixtures("keyring_store")
class TestPrewarmToolTakesNoUrlFromTheModel:
    """The MCP tool `ai_prewarm` posts to the servers of `ai.ollama_urls`, never to a URL that the
    calling model gives (#2637)."""

    async def test_the_tool_publishes_no_url_parameter(self) -> None:
        """The schema of the tool holds its own options and no URL."""
        from fastmcp import Client

        from devops_cli.ai.mcp.server import mcp

        async with Client(mcp) as client:
            tools = await client.list_tools()

        assert {
            tool.name: list(tool.input_schema["properties"])
            for tool in tools
            if tool.name == "ai_prewarm"
        } == {"ai_prewarm": PREWARM_TOOL_PARAMETERS}

    async def test_a_url_argument_is_refused_and_reaches_no_socket(
        self, monkeypatch: pytest.MonkeyPatch, config: Callable[..., Any]
    ) -> None:
        """A call that gives a URL fails and sends no request.

        On `origin/main` the client dialled `127.0.0.1:8200` with no flag and wrote
        `POST /v1/sys/seal-status?x=/api/generate`, and the tool replied "confirmed HTTP 200".
        """
        monkeypatch.setenv("DEVOPS_CLI_AI_ALLOW_PRIVATE_NETWORK", "false")
        config(ai={"provider": "ollama", "ollama_urls": ["http://example.com:11434"]})
        scripted_resolver(monkeypatch, {"example.com": [[PUBLIC_ADDRESS]]})
        recorder = record_connects(monkeypatch, [http_response(200, "{}")] * 2)

        failed, reply = await _call_prewarm_tool(
            {"url": "http://127.0.0.1:8200/v1/sys/seal-status?x="}
        )

        assert (
            failed,
            "1. Parameter: `url`\n   Kind: HALLUCINATED_PARAM\n" in reply,
            recorder.dialled,
            recorder.written,
        ) == (True, True, [], [])

    async def test_the_tool_prewarms_each_configured_server(
        self, monkeypatch: pytest.MonkeyPatch, config: Callable[..., Any]
    ) -> None:
        """With no URL, the tool posts the model and the keep-alive value to every configured server."""
        config(
            ai={
                "provider": "ollama",
                "model": "gemma4:26b",
                "ollama_urls": ["http://example.com:11434", "http://example.org:11434"],
            }
        )
        scripted_resolver(
            monkeypatch,
            {"example.com": [[PUBLIC_ADDRESS]], "example.org": [[PUBLIC_ADDRESS]]},
        )
        recorder = record_connects(monkeypatch, [http_response(200, "{}")] * 2)

        failed, reply = await _call_prewarm_tool({"keep_alive": "24h"})

        assert (
            failed,
            sorted(recorder.requested_hosts),
            [bytes(written).split(b"\r\n")[0] for written in recorder.written],
            [json.loads(bytes(written).partition(b"\r\n\r\n")[2]) for written in recorder.written],
            reply.count("confirmed HTTP 200 (keep_alive=24h)"),
        ) == (
            False,
            ["example.com:11434", "example.org:11434"],
            [_PREWARM_REQUEST_LINE] * 2,
            [{"model": "gemma4:26b", "prompt": "", "keep_alive": "24h"}] * 2,
            2,
        )

    @pytest.mark.parametrize(
        ("address", "flag", "dialled"),
        [
            ("127.0.0.1", False, True),
            ("192.0.2.10", False, False),
            ("192.0.2.10", True, True),
        ],
        ids=["loopback without the flag", "private without the flag", "private with the flag"],
    )
    async def test_the_tool_dials_the_configured_server_at_the_configured_level(
        self,
        monkeypatch: pytest.MonkeyPatch,
        config: Callable[..., Any],
        address: str,
        flag: bool,
        dialled: bool,
    ) -> None:
        """Loopback, and private addresses with `ai.allow_private_network`, as for the CLI.

        The floor sets the flag with its environment variable, which outranks the config file, so
        the test sets the variable.
        """
        monkeypatch.setenv("DEVOPS_CLI_AI_ALLOW_PRIVATE_NETWORK", str(flag).lower())
        config(ai={"provider": "ollama", "ollama_urls": [f"http://{address}:11434"]})
        recorder = record_connects(monkeypatch, [http_response(200, "{}")] * 2)

        await _call_prewarm_tool({})

        assert [dial for dial in recorder.dialled if dial[0] == address] == (
            [(address, 11434)] if dialled else []
        )

    def test_the_url_option_of_the_command_prewarms_the_host_that_a_person_types(
        self,
        monkeypatch: pytest.MonkeyPatch,
        config: Callable[..., Any],
        cli: Callable[..., Any],
    ) -> None:
        """A person types `--url`, and no model gives it, so the command posts to that host."""
        config(ai={"provider": "ollama", "ollama_urls": ["http://example.org:11434"]})
        scripted_resolver(
            monkeypatch,
            {"example.com": [[PUBLIC_ADDRESS]], "example.org": [[PUBLIC_ADDRESS]]},
        )
        recorder = record_connects(monkeypatch, [http_response(200, "{}")] * 2)

        result = cli("ai", "prewarm", "--url", "http://example.com:11434")

        assert (result.exit_code, recorder.requested_hosts) == (0, ["example.com:11434"])


_SERVER_URL_WITH_SECRETS = "http://FAKE-2676-user@example.com:11434/?x=FAKE-2676-query"
_SECRET_TEXT = ("FAKE-2676-user", "FAKE-2676-query", "http://")


@pytest.mark.usefixtures("keyring_store")
class TestPrewarmNamesEachServerByHostAndPort:
    """A reply names a server as `host[:port]`, never as the URL in `ai.ollama_urls` (#2676)."""

    @pytest.fixture
    def served(self, monkeypatch: pytest.MonkeyPatch, config: Callable[..., Any]) -> None:
        """One configured server whose URL holds a user name and a query value, and a 200 reply."""
        config(ai={"provider": "ollama", "ollama_urls": [_SERVER_URL_WITH_SECRETS]})
        scripted_resolver(monkeypatch, {"example.com": [[PUBLIC_ADDRESS]]})
        record_connects(monkeypatch, [http_response(200, "{}")] * 2)

    @pytest.mark.usefixtures("served")
    @pytest.mark.parametrize("json_output", [False, True], ids=["table", "json"])
    async def test_the_tool_reply_shows_no_url_text(self, json_output: bool) -> None:
        """The reply of `ai_prewarm` holds `example.com:11434` and none of the URL text."""
        failed, reply = await _call_prewarm_tool({"json_output": json_output})

        assert (
            failed,
            "example.com:11434" in reply,
            [text for text in _SECRET_TEXT if text in reply],
        ) == (False, True, [])

    @pytest.mark.usefixtures("served")
    def test_the_json_nodes_are_keyed_by_host_and_port(self, cli: Callable[..., Any]) -> None:
        """`devops ai prewarm --json` keys `nodes` by `host:port`."""
        result = cli("ai", "prewarm", "--json")

        assert (result.exit_code, json.loads(result.output)["nodes"]) == (
            0,
            {"example.com:11434": True},
        )

    @pytest.mark.usefixtures("served")
    def test_the_preload_command_shows_no_url_text(self, cli: Callable[..., Any]) -> None:
        """`devops ai preload` prints `example.com:11434` and none of the URL text."""
        result = cli("ai", "preload")

        assert (
            result.exit_code,
            "example.com:11434" in result.output,
            [text for text in _SECRET_TEXT if text in result.output],
        ) == (0, True, [])

    @pytest.mark.parametrize(
        ("nodes", "outcome"),
        [
            ({"http://u@example.com:1/?a=b": True, "http://example.com:1/c": False}, "failed"),
            ({"http://u@example.com:1/?a=b": True, "http://example.com:1/c": True}, "ok"),
        ],
        ids=["one failed", "both ok"],
    )
    def test_two_urls_of_one_server_make_one_node_that_holds_a_failure(
        self,
        cli: Callable[..., Any],
        model_fake: ModelFake,
        nodes: dict[str, bool],
        outcome: str,
    ) -> None:
        """Two URLs with one host and port show as one node, which is ok only if both are ok."""
        model_fake.set_preload_results(nodes)

        result = cli("ai", "prewarm", "--json")

        assert (result.exit_code, json.loads(result.output)["nodes"]) == (
            0 if outcome == "ok" else 1,
            {"example.com:1": outcome == "ok"},
        )


class TestPrewarmCounterModelLabel:
    """The label `model` of `devops_cli_ai_prewarms_total` is short and holds only safe characters,
    because the calling model sets it (#2676)."""

    @pytest.mark.parametrize(
        ("model", "label"),
        [
            ("gemma4:26b", "gemma4:26b"),
            ("hf.co/org/repo:Q4_K_M", "hf.co/org/repo:Q4_K_M"),
            ("my/model`@v2`.0!beta", "my/model__v2_.0_beta"),
            ("name\nwith line\tbreaks", "name_with_line_breaks"),
            ("m" * 300, "m" * 128),
        ],
        ids=["tag", "registry path", "symbols", "control characters", "long"],
    )
    def test_the_label_is_bounded(
        self,
        app: Any,
        model_fake: ModelFake,
        otlp: FakeCollector,
        model: str,
        label: str,
    ) -> None:
        """The counter holds the model as a label of safe characters and at most 128 of them."""
        result = runner.invoke(app, ["ai", "prewarm", "--model", model, "--single-node"])

        assert (result.exit_code, [a["model"] for a, _ in otlp.points(AI_PREWARMS_TOTAL.name)]) == (
            0,
            [label],
        )

    @pytest.fixture
    def app(self) -> Any:
        from devops_cli.main import app

        return app
