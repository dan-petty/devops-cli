"""Test-first specifications for unified thinking/reasoning handling across all LLM providers."""

from __future__ import annotations

import json
from typing import Any

import httpx2
import pytest

from devops_cli.ai.client.models import is_reasoning_model
from devops_cli.ai.client.unified import LLMClient
from devops_cli.config.settings import AIConfig
from tests.llm_stream_fakes import route_llm_clients


@pytest.fixture(autouse=True)
def _bypass_dns_validation(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "devops_cli.core.validation.validate_service_url", lambda *args, **kwargs: None
    )


def _make_resp(status_code: int = 200, json_data: dict[str, Any] | None = None) -> httpx2.Response:
    req = httpx2.Request("POST", "http://localhost")
    return httpx2.Response(status_code, request=req, json=json_data)


class TestReasoningCapabilityResolution:
    """Validate reasoning model capability resolution from config and gateway declarations."""

    def test_undeclared_models_default_to_not_reasoning(self) -> None:
        """Models without declared reasoning capability return False."""
        models = [
            "o1",
            "o1-mini",
            "o3",
            "o3-mini",
            "o4-preview",
            "gpt-4o",
            "claude-3-7-sonnet:thinking",
            "deepseek-r1",
            "devops-reasoning",
            "devops-review",
            "qwen2.5-coder:7b",
        ]
        assert all(not is_reasoning_model(m) for m in models)

    def test_declared_model_via_config_returns_true(self) -> None:
        """Explicit supports_reasoning in AIConfig marks model as reasoning."""
        cfg_declared = AIConfig(model="o3", supports_reasoning=True)
        cfg_undeclared = AIConfig(model="o3", supports_reasoning=False)
        assert (
            is_reasoning_model("o3", config=cfg_declared),
            is_reasoning_model("o3", config=cfg_undeclared),
        ) == (True, False)

    def test_gateway_model_info_parsing(self) -> None:
        """Fake /model/info payload checks that only unanimously declared models reason."""
        from devops_cli.ai.gateway import parse_gateway_reasoning_models

        fake_info = [
            {
                "model_name": "gpt-oss:20b",
                "litellm_params": {"model": "ollama_chat/gpt-oss:20b"},
                "model_info": {"supports_reasoning": True},
            },
            {
                "model_name": "devops-review",
                "litellm_params": {"model": "ollama_chat/qwen3-coder:30b"},
                "model_info": {},
            },
            {
                "model_name": "devops-review",
                "litellm_params": {"model": "ollama_chat/gpt-oss:20b"},
                "model_info": {"supports_reasoning": True},
            },
            {
                "model_name": "qwen3-coder:30b",
                "litellm_params": {"model": "ollama_chat/qwen3-coder:30b"},
                "model_info": {},
            },
        ]
        capabilities = parse_gateway_reasoning_models(fake_info)
        assert (
            capabilities.get("gpt-oss:20b"),
            capabilities.get("devops-review"),
            capabilities.get("qwen3-coder:30b"),
            capabilities.get("o3"),
        ) == (True, False, False, None)


class TestOpenAIReasoningPayloadAndParsing:
    """Validate OpenAI-compatible payload adaptation for declared reasoning models."""

    def test_openai_reasoning_payload_omits_temperature_and_uses_max_completion_tokens(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Declared reasoning models must omit temperature and use max_completion_tokens."""
        captured_payload: dict[str, Any] = {}

        def mock_post(request: httpx2.Request) -> httpx2.Response:
            nonlocal captured_payload
            if "chat/completions" in str(request.url):
                captured_payload = json.loads(request.content)
            return _make_resp(
                200,
                {
                    "choices": [{"message": {"content": "Reasoned response", "role": "assistant"}}],
                    "usage": {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30},
                },
            )

        route_llm_clients(monkeypatch, mock_post)

        cfg = AIConfig(
            provider="openai",
            model="o3-mini",
            supports_reasoning=True,
            temperature=0.7,
            max_tokens=4000,
            reasoning_effort="high",
            allow_private_network=True,
        )
        client = LLMClient(cfg, api_key="sk-test-token")
        res = client.chat("System instructions", "Solve this logic problem")

        assert (
            "temperature" in captured_payload,
            "max_tokens" in captured_payload,
            captured_payload.get("max_completion_tokens"),
            captured_payload.get("reasoning_effort"),
            res.text,
        ) == (False, False, 4000, "high", "Reasoned response")

    def test_openai_undeclared_o3_model_gets_standard_params(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A model named o3 with no declaration gets standard parameters."""
        captured_payload: dict[str, Any] = {}

        def mock_post(request: httpx2.Request) -> httpx2.Response:
            nonlocal captured_payload
            if "chat/completions" in str(request.url):
                captured_payload = json.loads(request.content)
            return _make_resp(
                200,
                {
                    "choices": [{"message": {"content": "Standard response", "role": "assistant"}}],
                    "usage": {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30},
                },
            )

        route_llm_clients(monkeypatch, mock_post)

        cfg = AIConfig(
            provider="openai",
            model="o3",
            temperature=0.7,
            max_tokens=4000,
            reasoning_effort="high",
            allow_private_network=True,
        )
        client = LLMClient(cfg, api_key="sk-test-token")
        res = client.chat("System instructions", "Solve this problem")

        assert (
            "reasoning_effort" in captured_payload,
            "max_completion_tokens" in captured_payload,
            captured_payload.get("max_tokens"),
            captured_payload.get("temperature"),
            res.text,
        ) == (False, False, 4000, 0.7, "Standard response")

    def test_openai_reasoning_disabled_thinking_omits_reasoning_effort(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When thinking is disabled on a reasoning model, no reasoning parameter is sent."""
        captured_payload: dict[str, Any] = {}

        def mock_post(request: httpx2.Request) -> httpx2.Response:
            nonlocal captured_payload
            if "chat/completions" in str(request.url):
                captured_payload = json.loads(request.content)
            return _make_resp(
                200,
                {
                    "choices": [{"message": {"content": "Direct response", "role": "assistant"}}],
                    "usage": {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30},
                },
            )

        route_llm_clients(monkeypatch, mock_post)

        cfg = AIConfig(
            provider="openai",
            model="gpt-oss:20b",
            supports_reasoning=True,
            temperature=0.7,
            max_tokens=4000,
            reasoning_effort="high",
            allow_private_network=True,
        )
        client = LLMClient(cfg, api_key="sk-test-token")
        res = client.chat("System instructions", "Answer directly", enable_thinking=False)

        assert (
            "reasoning_effort" in captured_payload,
            "temperature" in captured_payload,
            captured_payload.get("max_completion_tokens"),
            res.text,
        ) == (False, False, 4000, "Direct response")

    def test_openai_non_reasoning_payload_omits_reasoning_effort(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Non-reasoning models must omit reasoning_effort even if configured globally."""
        captured_payload: dict[str, Any] = {}

        def mock_post(request: httpx2.Request) -> httpx2.Response:
            nonlocal captured_payload
            if "chat/completions" in str(request.url):
                captured_payload = json.loads(request.content)
            return _make_resp(
                200,
                {
                    "choices": [{"message": {"content": "Standard response", "role": "assistant"}}],
                    "usage": {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30},
                },
            )

        route_llm_clients(monkeypatch, mock_post)

        cfg = AIConfig(
            provider="openai",
            model="devops-review",
            temperature=0.2,
            max_tokens=4000,
            reasoning_effort="low",
            allow_private_network=True,
        )
        client = LLMClient(cfg, api_key="sk-test-token")
        res = client.chat("System instructions", "Review code")

        assert (
            "reasoning_effort" in captured_payload,
            "max_completion_tokens" in captured_payload,
            captured_payload.get("max_tokens"),
            captured_payload.get("temperature"),
            res.text,
        ) == (False, False, 4000, 0.2, "Standard response")

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
        route_llm_clients(monkeypatch, lambda request: resp)

        cfg = AIConfig(provider="openai", model="deepseek-reasoner", allow_private_network=True)
        client = LLMClient(cfg, api_key="sk-test-token")

        res = client.chat("System instructions", "What is the answer?")

        assert res.text == "42"
        assert res.thinking == "Pondering the meaning of life, universe and everything..."
        assert str(res) == "42"


class TestClaudeThinkingPayloadAndParsing:
    """Validate Anthropic Claude adaptive thinking payload generation and multi-block response parsing."""

    def test_claude_extended_thinking_payload(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Claude with thinking enabled includes adaptive thinking block and omits temperature."""
        from tests.llm_stream_fakes import (
            make_anthropic_model_info_payload as _make_model_info_payload,
        )

        model_name = "claude-sonnet-4-5"
        captured_payload: dict[str, Any] = {}

        def mock_post(request: httpx2.Request) -> httpx2.Response:
            nonlocal captured_payload
            url_str = str(request.url)
            if f"/v1/models/{model_name}" in url_str:
                return httpx2.Response(
                    200,
                    json=_make_model_info_payload(
                        model_name, adaptive_thinking=True, sampling=False
                    ),
                )
            if "v1/messages" in url_str:
                captured_payload = json.loads(request.content)
                return _make_resp(
                    200,
                    {
                        "content": [
                            {
                                "type": "thinking",
                                "thinking": "Analyzing architecture invariants...",
                            },
                            {"type": "text", "text": "Plan approved."},
                        ],
                        "usage": {"input_tokens": 50, "output_tokens": 100},
                    },
                )
            return httpx2.Response(404)

        route_llm_clients(monkeypatch, mock_post)

        cfg = AIConfig(
            provider="claude",
            model=model_name,
            temperature=0.2,
            max_tokens=8192,
            allow_private_network=True,
        )
        client = LLMClient(cfg, api_key="sk-ant-test")

        res = client.chat("System", "Review architecture", enable_thinking=True)

        assert captured_payload.get("thinking") == {"type": "adaptive"}
        assert "budget_tokens" not in captured_payload.get("thinking", {})
        assert captured_payload.get("temperature") is None
        assert res.text == "Plan approved."
        assert res.thinking == "Analyzing architecture invariants..."
        assert str(res) == "Plan approved."

    def test_claude_disabled_thinking_payload(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Claude with enable_thinking=False does not include thinking block."""
        from tests.llm_stream_fakes import (
            make_anthropic_model_info_payload as _make_model_info_payload,
        )

        model_name = "claude-sonnet-4-5"
        captured_payload: dict[str, Any] = {}

        def mock_post(request: httpx2.Request) -> httpx2.Response:
            nonlocal captured_payload
            url_str = str(request.url)
            if f"/v1/models/{model_name}" in url_str:
                return httpx2.Response(
                    200,
                    json=_make_model_info_payload(
                        model_name, adaptive_thinking=True, sampling=False
                    ),
                )
            if "v1/messages" in url_str:
                captured_payload = json.loads(request.content)
                return _make_resp(
                    200,
                    {
                        "content": [{"type": "text", "text": "Direct answer"}],
                        "usage": {"input_tokens": 10, "output_tokens": 20},
                    },
                )
            return httpx2.Response(404)

        route_llm_clients(monkeypatch, mock_post)

        cfg = AIConfig(
            provider="claude",
            model=model_name,
            allow_private_network=True,
        )
        client = LLMClient(cfg, api_key="sk-ant-test")

        res = client.chat("System", "Quick question", enable_thinking=False)

        assert "thinking" not in captured_payload
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
        route_llm_clients(monkeypatch, lambda request: resp)

        cfg = AIConfig(
            provider="ollama",
            ollama_urls=["http://localhost:11434"],
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
    """Validate SSE stream frames for thinking deltas."""

    def test_extract_claude_thinking_delta(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from devops_cli.ai.client import LLMClient
        from devops_cli.config.settings import AIConfig
        from tests.llm_stream_fakes import (
            anthropic_event,
            reply,
            route_client,
        )
        from tests.llm_stream_fakes import (
            make_anthropic_model_info_payload as _make_model_info_payload,
        )

        model_name = "claude-sonnet-4-5"
        frames = [
            anthropic_event(
                "message_start",
                message={"id": "msg_1", "content": [], "usage": {"input_tokens": 10}},
            ),
            anthropic_event(
                "content_block_start",
                index=0,
                content_block={"type": "thinking", "thinking": ""},
            ),
            anthropic_event(
                "content_block_delta",
                index=0,
                delta={"type": "thinking_delta", "thinking": "step 1 reasoning"},
            ),
            anthropic_event("content_block_stop", index=0),
            anthropic_event(
                "message_delta",
                delta={"stop_reason": "end_turn"},
                usage={"output_tokens": 5},
            ),
            anthropic_event("message_stop"),
        ]

        def handler(request: httpx2.Request) -> httpx2.Response:
            url_path = request.url.path
            if url_path.endswith(f"/v1/models/{model_name}"):
                return httpx2.Response(
                    200,
                    json=_make_model_info_payload(
                        model_name, adaptive_thinking=True, sampling=False
                    ),
                )
            if url_path.endswith("/v1/messages"):
                return reply(frames)
            return httpx2.Response(404)

        cfg = AIConfig(provider="claude", model=model_name, allow_private_network=True)
        client = LLMClient(cfg, api_key="sk-ant-test")
        route_client(client, monkeypatch, handler)

        chunks = list(client.chat_stream("System", "Hello", enable_thinking=True))
        assert "<think>step 1 reasoning</think>" in "".join(chunks)

    def test_extract_openai_reasoning_content_delta(self) -> None:
        from devops_cli.ai.client.streaming import StreamFrame, _openai_stream_frame

        data = '{"choices": [{"delta": {"reasoning_content": "step 1 reasoning"}}]}'
        frame = _openai_stream_frame(httpx2.ServerSentEvent(data=data))
        assert frame == StreamFrame(chunk="<think>step 1 reasoning</think>")


class TestGatewayReasoningPayloadRouting:
    """Validate gateway parameter routing based on /model/info capability declarations."""

    def test_gateway_declared_reasoning_model_gets_reasoning_parameters(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When gateway /model/info declares supports_reasoning, reasoning params are applied."""
        from devops_cli.ai.gateway import clear_gateway_reasoning_cache

        clear_gateway_reasoning_cache()
        captured_payload: dict[str, Any] = {}

        monkeypatch.setattr(
            "devops_cli.ai.gateway.fetch_model_info",
            lambda *args, **kwargs: [
                {
                    "model_name": "gpt-oss:20b",
                    "model_info": {"supports_reasoning": True},
                }
            ],
        )

        def mock_handler(request: httpx2.Request) -> httpx2.Response:
            nonlocal captured_payload
            url_str = str(request.url)
            if "chat/completions" in url_str:
                captured_payload = json.loads(request.content)
                return _make_resp(
                    200,
                    {
                        "choices": [
                            {
                                "message": {
                                    "content": "Gateway reasoning response",
                                    "role": "assistant",
                                }
                            }
                        ],
                        "usage": {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30},
                    },
                )
            return _make_resp(404)

        route_llm_clients(monkeypatch, mock_handler)

        cfg = AIConfig(
            provider="gateway",
            model="gpt-oss:20b",
            gateway_url="http://localhost:4000/v1",
            temperature=0.7,
            max_tokens=4000,
            reasoning_effort="medium",
            allow_private_network=True,
        )
        client = LLMClient(cfg)
        res = client.chat("System", "Reason through this")

        assert (
            "temperature" in captured_payload,
            "max_tokens" in captured_payload,
            captured_payload.get("max_completion_tokens"),
            captured_payload.get("reasoning_effort"),
            res.text,
        ) == (False, False, 4000, "medium", "Gateway reasoning response")

    def test_gateway_mixed_deployment_group_gets_standard_parameters(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When a model group has mixed deployments, standard parameters are used."""
        from devops_cli.ai.gateway import clear_gateway_reasoning_cache

        clear_gateway_reasoning_cache()
        captured_payload: dict[str, Any] = {}

        monkeypatch.setattr(
            "devops_cli.ai.gateway.fetch_model_info",
            lambda *args, **kwargs: [
                {
                    "model_name": "devops-review",
                    "model_info": {"supports_reasoning": True},
                },
                {
                    "model_name": "devops-review",
                    "model_info": {},
                },
            ],
        )

        def mock_handler(request: httpx2.Request) -> httpx2.Response:
            nonlocal captured_payload
            url_str = str(request.url)
            if "chat/completions" in url_str:
                captured_payload = json.loads(request.content)
                return _make_resp(
                    200,
                    {
                        "choices": [
                            {
                                "message": {
                                    "content": "Standard review response",
                                    "role": "assistant",
                                }
                            }
                        ],
                        "usage": {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30},
                    },
                )
            return _make_resp(404)

        route_llm_clients(monkeypatch, mock_handler)

        cfg = AIConfig(
            provider="gateway",
            model="devops-review",
            gateway_url="http://localhost:4000/v1",
            temperature=0.2,
            max_tokens=4000,
            reasoning_effort="high",
            allow_private_network=True,
        )
        client = LLMClient(cfg)
        res = client.chat("System", "Review code")

        assert (
            "reasoning_effort" in captured_payload,
            "max_completion_tokens" in captured_payload,
            captured_payload.get("max_tokens"),
            captured_payload.get("temperature"),
            res.text,
        ) == (False, False, 4000, 0.2, "Standard review response")

    def test_gateway_disabled_thinking_omits_reasoning_effort(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When enable_thinking=False on gateway reasoning model, reasoning_effort is omitted."""
        from devops_cli.ai.gateway import clear_gateway_reasoning_cache

        clear_gateway_reasoning_cache()
        captured_payload: dict[str, Any] = {}

        monkeypatch.setattr(
            "devops_cli.ai.gateway.fetch_model_info",
            lambda *args, **kwargs: [
                {
                    "model_name": "gpt-oss:20b",
                    "model_info": {"supports_reasoning": True},
                }
            ],
        )

        def mock_handler(request: httpx2.Request) -> httpx2.Response:
            nonlocal captured_payload
            url_str = str(request.url)
            if "chat/completions" in url_str:
                captured_payload = json.loads(request.content)
                return _make_resp(
                    200,
                    {
                        "choices": [
                            {"message": {"content": "Direct response", "role": "assistant"}}
                        ],
                        "usage": {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30},
                    },
                )
            return _make_resp(404)

        route_llm_clients(monkeypatch, mock_handler)

        cfg = AIConfig(
            provider="gateway",
            model="gpt-oss:20b",
            gateway_url="http://localhost:4000/v1",
            temperature=0.7,
            max_tokens=4000,
            reasoning_effort="high",
            allow_private_network=True,
        )
        client = LLMClient(cfg)
        res = client.chat("System", "Direct answer", enable_thinking=False)

        assert (
            "reasoning_effort" in captured_payload,
            captured_payload.get("max_completion_tokens"),
            res.text,
        ) == (False, 4000, "Direct response")
