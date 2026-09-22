"""Unit and integration test suite for local model prewarming and VRAM eviction."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import httpx2
import pytest
from typer.testing import CliRunner

from devops_cli.ai.client.ollama import OllamaProviderMixin
from devops_cli.ai.client.unified import LLMClient
from devops_cli.ai.mcp.server import ai_prewarm_models
from devops_cli.commands.ai import _render_prewarm_results, _resolve_prewarm_urls
from devops_cli.config.settings import AIConfig
from devops_cli.exceptions import ValidationError
from devops_cli.main import app

runner = CliRunner()


class DummyOllamaProvider(OllamaProviderMixin):
    """Dummy provider implementation for isolating OllamaProviderMixin methods."""

    def __init__(self, config: AIConfig) -> None:
        self._config = config

    def _validate_base_url(
        self,
        base_url: str,
        purpose: str = "API",
        *,
        allow_loopback_for_local_tooling: bool = False,
    ) -> str:
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

    def test_cli_prewarm_success_default_args(self) -> None:
        """Verify devops ai prewarm succeeds with default configured model and urls."""
        with patch("devops_cli.ai.client.LLMClient.preload_models") as mock_preload:
            mock_preload.return_value = {"http://localhost:11434": True}
            result = runner.invoke(app, ["ai", "prewarm"])

            assert result.exit_code == 0
            assert "prewarmed into VRAM" in result.output
            assert "confirmed HTTP 200" in result.output

    def test_cli_prewarm_evict_and_json_flag(self) -> None:
        """Verify devops ai prewarm --evict --json passes keep_alive=0 and emits structured json."""
        with patch("devops_cli.ai.client.LLMClient.preload_models") as mock_preload:
            mock_preload.return_value = {"http://localhost:11434": True}
            result = runner.invoke(app, ["ai", "prewarm", "--evict", "--json"])

            assert result.exit_code == 0
            payload = json.loads(result.output)
            assert (payload["action"], payload["keep_alive"], payload["success"]) == (
                "eviction",
                0,
                True,
            )

    def test_cli_prewarm_failure_exits_code_1(self) -> None:
        """Verify devops ai prewarm exits with code 1 when node prewarming fails."""
        with patch("devops_cli.ai.client.LLMClient.preload_models") as mock_preload:
            mock_preload.return_value = {"http://localhost:11434": False}
            result = runner.invoke(app, ["ai", "prewarm"])

            assert result.exit_code == 1
            assert "request failed or timed out" in result.output

    def test_cli_prewarm_single_node_flag(self) -> None:
        """Verify devops ai prewarm --single-node targets only primary node."""
        with patch("devops_cli.ai.client.LLMClient.preload_models") as mock_preload:
            mock_preload.return_value = {"http://localhost:11434": True}
            result = runner.invoke(app, ["ai", "prewarm", "--single-node"])

            assert result.exit_code == 0
            assert mock_preload.call_args[1]["urls"] == ["http://localhost:11434"]

    def test_cli_prewarm_telemetry_recording(self) -> None:
        """Verify devops ai prewarm records OpenTelemetry span and execution metric."""
        with (
            patch(
                "devops_cli.ai.client.LLMClient.preload_models",
                return_value={"http://localhost:11434": True},
            ),
            patch("devops_cli.commands.ai.record_metric") as mock_metric,
            patch("devops_cli.commands.ai.trace_span") as mock_span,
        ):
            result = runner.invoke(app, ["ai", "prewarm"])

            assert result.exit_code == 0
            assert (mock_span.called, mock_metric.called) == (True, True)

    def test_cli_prewarm_telemetry_recording_failure(self) -> None:
        """Verify devops ai prewarm records failure metric when node prewarm fails."""
        with (
            patch(
                "devops_cli.ai.client.LLMClient.preload_models",
                return_value={"http://localhost:11434": False},
            ),
            patch("devops_cli.commands.ai.record_metric") as mock_metric,
            patch("devops_cli.commands.ai.trace_span") as mock_span,
        ):
            result = runner.invoke(app, ["ai", "prewarm"])

            assert result.exit_code == 1
            assert (mock_span.called, mock_metric.called) == (True, True)


class TestFastMCPPrewarmTool:
    """Test suite for FastMCP ai_prewarm_models tool."""

    def test_ai_prewarm_models_tool_dispatch(self) -> None:
        """Verify ai_prewarm_models tool invokes devops ai prewarm with safe arguments."""
        with patch("devops_cli.ai.mcp.server._run_mcp_cmd", return_value="Success") as mock_cmd:
            res = ai_prewarm_models(
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
                "--keep-alive",
                "24h",
                "--model",
                "qwen2.5-coder:7b",
                "--evict",
                "--all-nodes",
            ]
            assert called_cmd == expected_flags

    def test_ai_prewarm_models_tool_flag_injection_rejected(self) -> None:
        """Verify ai_prewarm_models rejects hyphen-prefixed model or keep-alive argument."""
        with pytest.raises(ValidationError):
            ai_prewarm_models(model="--injected-flag")

        with pytest.raises(ValidationError):
            ai_prewarm_models(keep_alive="--bad-duration")
