"""Test-first specifications for unified thinking/reasoning handling across all LLM providers."""

from __future__ import annotations

from typing import Any

import httpx2
import pytest

from devops_cli.ai.client.models import is_reasoning_model
from devops_cli.ai.client.unified import LLMClient
from devops_cli.config.settings import AIConfig


@pytest.fixture(autouse=True)
def _bypass_dns_validation(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "devops_cli.core.validation.validate_service_url", lambda *args, **kwargs: None
    )


def _make_resp(status_code: int = 200, json_data: dict[str, Any] | None = None) -> httpx2.Response:
    req = httpx2.Request("POST", "http://localhost")
    return httpx2.Response(status_code, request=req, json=json_data)


class TestReasoningModelDetection:
    """Validate reasoning model classification heuristics."""

    def test_detects_openai_reasoning_models(self) -> None:
        assert is_reasoning_model("o1") is True
        assert is_reasoning_model("o1-mini") is True
        assert is_reasoning_model("o1-preview") is True
        assert is_reasoning_model("o3-mini") is True
        assert is_reasoning_model("o3") is True
        assert is_reasoning_model("o4-preview") is True
        assert is_reasoning_model("gpt-4o") is False
        assert is_reasoning_model("gpt-4o-mini") is False

    def test_detects_claude_reasoning_models(self) -> None:
        assert is_reasoning_model("claude-3-7-sonnet-20250219:thinking") is True
        assert is_reasoning_model("claude-3-7-sonnet:thinking") is True
        assert is_reasoning_model("claude-3-5-sonnet") is False

    def test_detects_open_weights_reasoning_models(self) -> None:
        assert is_reasoning_model("deepseek-r1") is True
        assert is_reasoning_model("deepseek-r1:32b") is True
        assert is_reasoning_model("deepseek-reasoner") is True
        assert is_reasoning_model("qwq-32b") is True
        assert is_reasoning_model("qwen2.5-coder:7b") is False


class TestOpenAIReasoningPayloadAndParsing:
    """Validate OpenAI-compatible payload adaptation for reasoning models (o1, o3-mini, DeepSeek)."""

    def test_openai_reasoning_payload_omits_temperature_and_uses_max_completion_tokens(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """o1/o3 reasoning models must omit temperature and use max_completion_tokens."""
        captured_payload: dict[str, Any] = {}

        def mock_post(self: Any, url: str, **kwargs: Any) -> httpx2.Response:
            nonlocal captured_payload
            if "chat/completions" in str(url):
                captured_payload = dict(kwargs.get("json", {}))
            return _make_resp(
                200,
                {
                    "choices": [{"message": {"content": "Reasoned response", "role": "assistant"}}],
                    "usage": {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30},
                },
            )

        monkeypatch.setattr(httpx2.Client, "post", mock_post)

        cfg = AIConfig(
            provider="openai",
            model="o3-mini",
            temperature=0.7,
            max_tokens=4000,
            reasoning_effort="high",
            allow_private_network=True,
        )
        client = LLMClient(cfg, api_key="sk-test-token")
        res = client.chat("System instructions", "Solve this logic problem")

        assert "temperature" not in captured_payload
        assert "max_tokens" not in captured_payload
        assert captured_payload.get("max_completion_tokens") == 4000
        assert captured_payload.get("reasoning_effort") == "high"
        assert res.text == "Reasoned response"

    def test_openai_extracts_reasoning_content_into_thinking(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """DeepSeek / OpenRouter format with reasoning_content is extracted into res.thinking."""
        resp = _make_resp(
            200,
            {
                "choices": [
                    {
                        "message": {
                            "content": "42",
                            "reasoning_content": "Pondering the meaning of life, universe and everything...",
                        }
                    }
                ],
                "usage": {"prompt_tokens": 5, "completion_tokens": 15, "total_tokens": 20},
            },
        )
        monkeypatch.setattr(httpx2.Client, "post", lambda self, url, **kwargs: resp)

        cfg = AIConfig(provider="openai", model="deepseek-reasoner", allow_private_network=True)
        client = LLMClient(cfg, api_key="sk-test-token")

        res = client.chat("System instructions", "What is the answer?")

        assert res.text == "42"
        assert res.thinking == "Pondering the meaning of life, universe and everything..."
        assert str(res) == "42"


class TestClaudeThinkingPayloadAndParsing:
    """Validate Anthropic Claude extended thinking payload generation and multi-block response parsing."""

    def test_claude_extended_thinking_payload(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Claude 3.7 with thinking enabled includes thinking budget and omits non-1.0 temperature."""
        captured_payload: dict[str, Any] = {}

        def mock_post(self: Any, url: str, **kwargs: Any) -> httpx2.Response:
            nonlocal captured_payload
            if "v1/messages" in str(url):
                captured_payload = dict(kwargs.get("json", {}))
            return _make_resp(
                200,
                {
                    "content": [
                        {"type": "thinking", "thinking": "Analyzing architecture invariants..."},
                        {"type": "text", "text": "Plan approved."},
                    ],
                    "usage": {"input_tokens": 50, "output_tokens": 100},
                },
            )

        monkeypatch.setattr(httpx2.Client, "post", mock_post)

        cfg = AIConfig(
            provider="claude",
            model="claude-3-7-sonnet-20250219",
            temperature=0.2,
            max_tokens=8192,
            allow_private_network=True,
        )
        client = LLMClient(cfg, api_key="sk-ant-test")

        res = client.chat("System", "Review architecture", enable_thinking=True)

        assert captured_payload.get("thinking", {}).get("type") == "enabled"
        assert captured_payload.get("thinking", {}).get("budget_tokens", 0) >= 1024
        assert captured_payload.get("temperature") in (None, 1.0)
        assert res.text == "Plan approved."
        assert res.thinking == "Analyzing architecture invariants..."
        assert str(res) == "Plan approved."

    def test_claude_disabled_thinking_payload(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Claude with enable_thinking=False does not include enabled thinking block."""
        captured_payload: dict[str, Any] = {}

        def mock_post(self: Any, url: str, **kwargs: Any) -> httpx2.Response:
            nonlocal captured_payload
            captured_payload = dict(kwargs.get("json", {}))
            return _make_resp(
                200,
                {
                    "content": [{"type": "text", "text": "Direct answer"}],
                    "usage": {"input_tokens": 10, "output_tokens": 20},
                },
            )

        monkeypatch.setattr(httpx2.Client, "post", mock_post)

        cfg = AIConfig(
            provider="claude",
            model="claude-3-7-sonnet-20250219",
            allow_private_network=True,
        )
        client = LLMClient(cfg, api_key="sk-ant-test")

        res = client.chat("System", "Quick question", enable_thinking=False)

        assert captured_payload.get("thinking", {}).get("type") != "enabled"
        assert res.text == "Direct answer"
        assert res.thinking is None


class TestOllamaThinkingSeparation:
    """Validate Ollama thinking extraction and clean output separation."""

    def test_ollama_separates_inline_think_blocks_into_thinking_field(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When Ollama model outputs inline <think> tags, res.text is stripped and res.thinking is populated."""
        resp = _make_resp(
            200,
            {
                "message": {
                    "role": "assistant",
                    "content": '<think>\nCarefully examining diff...\nFound no memory leak.\n</think>\n```json\n{"status": "APPROVED"}\n```',
                },
                "prompt_eval_count": 100,
                "eval_count": 50,
            },
        )
        monkeypatch.setattr(httpx2.Client, "post", lambda self, url, **kwargs: resp)

        cfg = AIConfig(
            provider="ollama",
            model="deepseek-r1:14b",
            allow_private_network=True,
        )
        client = LLMClient(cfg)

        res = client.chat("System", "Review diff", enable_thinking=True)

        assert "<think>" not in res.text
        assert "</think>" not in res.text
        assert res.text == '```json\n{"status": "APPROVED"}\n```'
        assert str(res) == res.text
        assert res.thinking is not None
        assert "Carefully examining diff" in res.thinking


class TestStreamingThinkingExtractors:
    """Validate SSE streaming chunk extraction for thinking deltas."""

    def test_extract_claude_thinking_delta(self) -> None:
        from devops_cli.ai.client.streaming import _extract_claude_stream_chunk

        line = 'data: {"type": "content_block_delta", "delta": {"type": "thinking_delta", "thinking": "step 1 reasoning"}}'
        chunk, is_done = _extract_claude_stream_chunk(line)
        assert chunk == "<think>step 1 reasoning</think>"
        assert is_done is False

    def test_extract_openai_reasoning_content_delta(self) -> None:
        from devops_cli.ai.client.streaming import _extract_openai_stream_chunk

        line = 'data: {"choices": [{"delta": {"reasoning_content": "step 1 reasoning"}}]}'
        chunk, is_done = _extract_openai_stream_chunk(line)
        assert chunk == "<think>step 1 reasoning</think>"
        assert is_done is False
