"""Tests for AI model sampling, parameter validation, and session provenance (#1070)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx2
import pytest
from pydantic import ValidationError

from devops_cli.ai.client import LLMClient
from devops_cli.config.settings import AIConfig, AITaskOverride
from devops_cli.exceptions import ConfigurationError

# =============================================================================
# 1. num_ctx refusal and unknown keys validation
# =============================================================================


def test_num_ctx_refused_on_gateway_provider() -> None:
    """A client for the gateway provider raises ConfigurationError naming the task when num_ctx is set."""
    cfg = AIConfig(provider="gateway", num_ctx=4096, task_name="analysis")
    with pytest.raises(ConfigurationError) as exc_info:
        LLMClient(config=cfg)

    msg = str(exc_info.value)
    assert "analysis" in msg
    assert "num_ctx" in msg
    assert "OLLAMA_CONTEXT_LENGTH" in msg
    assert "context_window" in msg


def test_num_ctx_refused_on_openai_provider() -> None:
    """A client for an OpenAI-compatible provider raises ConfigurationError when num_ctx is set."""
    cfg = AIConfig(provider="openai", num_ctx=4096, task_name="chat")
    with pytest.raises(ConfigurationError) as exc_info:
        LLMClient(config=cfg)

    msg = str(exc_info.value)
    assert "chat" in msg
    assert "num_ctx" in msg
    assert "OLLAMA_CONTEXT_LENGTH" in msg
    assert "context_window" in msg


def test_num_ctx_accepted_on_native_ollama_provider() -> None:
    """A client for the native Ollama provider accepts num_ctx without raising ConfigurationError."""
    cfg = AIConfig(provider="ollama", num_ctx=4096, task_name="analysis")
    client = LLMClient(config=cfg)
    assert client.get_context_window("analysis") == 4096


@pytest.mark.parametrize(
    "key",
    ["top_k", "min_p", "presence_penalty", "repeat_penalty", "think", "keep_alive"],
)
def test_per_model_sampling_keys_fail_validation_with_guidance(key: str) -> None:
    """Unknown keys under ai.tasks.<task> fail validation, naming the key and where it belongs."""
    with pytest.raises((ValidationError, ValueError)) as exc_info:
        AITaskOverride.model_validate({key: 20})

    err_str = str(exc_info.value)
    assert key in err_str
    assert "litellm_params" in err_str
    assert "Ollama tag" in err_str


def test_generic_unknown_keys_under_ai_fail_validation() -> None:
    """Generic undeclared keys under ai and ai.tasks.<task> fail validation naming the key."""
    with pytest.raises((ValidationError, ValueError)) as exc_info:
        AIConfig.model_validate({"unsupported_custom_key": "val"})

    assert "unsupported_custom_key" in str(exc_info.value)

    with pytest.raises((ValidationError, ValueError)) as exc_info2:
        AITaskOverride.model_validate({"another_bad_key": 123})

    assert "another_bad_key" in str(exc_info2.value)


# =============================================================================
# 2. Streamed sampling parity and use_model_sampling
# =============================================================================


def test_streamed_openai_compat_payload_includes_sampling() -> None:
    """Streamed OpenAI-compatible payloads include temperature and top_p matching unstreamed calls."""
    cfg = AIConfig(provider="gateway", temperature=0.7, top_p=0.85)
    client = LLMClient(config=cfg)

    payload_unstreamed = client._build_compat_payload("sys", [], stream=False)
    payload_streamed = client._build_compat_payload("sys", [], stream=True)

    assert payload_unstreamed.get("temperature") == 0.7
    assert payload_unstreamed.get("top_p") == 0.85
    assert payload_streamed.get("temperature") == 0.7
    assert payload_streamed.get("top_p") == 0.85


def test_streamed_openai_compat_payload_omits_sampling_when_use_model_sampling() -> None:
    """When use_model_sampling is true, OpenAI payloads carry neither temperature nor top_p."""
    cfg = AIConfig(provider="gateway", temperature=0.7, top_p=0.85, use_model_sampling=True)
    client = LLMClient(config=cfg)

    payload = client._build_compat_payload("sys", [], stream=True)
    assert "temperature" not in payload
    assert "top_p" not in payload


def test_streamed_native_ollama_request_includes_options_and_trace_headers(
    monkeypatch: pytest.MonkeyPatch,
    tracer: Any,
) -> None:
    """Streamed native Ollama requests carry the same options and trace headers as unstreamed requests."""
    from devops_cli.models.ai import ChatMessage
    from tests.llm_stream_fakes import ollama_line, route_client

    cfg = AIConfig(
        provider="ollama",
        temperature=0.7,
        top_p=0.85,
        num_ctx=8192,
        max_tokens=500,
        task_name="analysis",
    )
    client = LLMClient(config=cfg)

    def fake_handler(req: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(
            200,
            headers={"content-type": "application/x-ndjson"},
            content=iter([ollama_line("Hello", done=True)]),
        )

    sent = route_client(client, monkeypatch, fake_handler)

    with tracer.span("test_stream"):
        list(client.chat_messages_stream("sys", [ChatMessage(role="user", content="hi")]))

    assert len(sent) == 1
    req = sent[0]
    data = json.loads(req.content.decode("utf-8"))
    options = data.get("options", {})

    assert options.get("temperature") == 0.7
    assert options.get("top_p") == 0.85
    assert options.get("num_ctx") == 8192
    assert options.get("num_predict") == 500
    assert "traceparent" in req.headers


def test_streamed_native_ollama_omits_sampling_when_use_model_sampling(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When use_model_sampling is true, Ollama requests omit temperature and top_p."""
    from devops_cli.models.ai import ChatMessage
    from tests.llm_stream_fakes import ollama_line, route_client

    cfg = AIConfig(
        provider="ollama",
        temperature=0.7,
        top_p=0.85,
        num_ctx=8192,
        use_model_sampling=True,
    )
    client = LLMClient(config=cfg)

    def fake_handler(req: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(
            200,
            headers={"content-type": "application/x-ndjson"},
            content=iter([ollama_line("Hello", done=True)]),
        )

    sent = route_client(client, monkeypatch, fake_handler)
    list(client.chat_messages_stream("sys", [ChatMessage(role="user", content="hi")]))

    assert len(sent) == 1
    data = json.loads(sent[0].content.decode("utf-8"))
    options = data.get("options", {})
    assert "temperature" not in options
    assert "top_p" not in options
    assert options.get("num_ctx") == 8192


def test_use_model_sampling_task_override_inheritance() -> None:
    """A task can set use_model_sampling or inherit it from root ai configuration."""
    cfg = AIConfig(use_model_sampling=True)
    cfg.tasks.analysis = AITaskOverride(use_model_sampling=False)
    cfg.tasks.chat = AITaskOverride()

    assert cfg.for_task("analysis").use_model_sampling is False
    assert cfg.for_task("chat").use_model_sampling is True


def test_review_setup_records_sampling_and_models_for_all_review_tasks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """review_setup records models and sampling for analysis, verification, and compose."""
    from devops_cli.ai import run_store
    from devops_cli.config.settings import load_settings

    settings = load_settings().model_copy(deep=True)
    settings.ai.provider = "gateway"
    settings.ai.model = "devops-chat"
    settings.ai.temperature = 0.5
    settings.ai.top_p = 0.9
    settings.ai.max_tokens = 4096
    settings.ai.tasks.analysis = AITaskOverride(
        provider="gateway",
        model="devops-coder",
        temperature=0.2,
        top_p=0.8,
        max_tokens=2048,
    )
    settings.ai.tasks.verification = AITaskOverride(
        provider="gateway",
        model="devops-reasoner",
        supports_reasoning=True,
        reasoning_effort="high",
        max_tokens=8192,
    )
    settings.ai.tasks.compose = AITaskOverride(
        provider="ollama",
        model="qwen3:8b",
        use_model_sampling=True,
        max_tokens=1024,
    )
    monkeypatch.setattr("devops_cli.config.settings.load_settings", lambda: settings)
    monkeypatch.setattr(run_store, "gateway_pool", lambda task: [])

    setup = run_store.review_setup()

    assert setup["models"] == {
        "analysis": "gateway/devops-coder",
        "verification": "gateway/devops-reasoner",
        "compose": "ollama/qwen3:8b",
    }
    assert setup["sampling"] == {
        "analysis": {
            "temperature": 0.2,
            "top_p": 0.8,
            "max_tokens": 2048,
            "reasoning_effort": None,
            "use_model_sampling": False,
        },
        "verification": {
            "temperature": None,
            "top_p": None,
            "max_tokens": 8192,
            "reasoning_effort": "high",
            "use_model_sampling": False,
        },
        "compose": {
            "temperature": None,
            "top_p": None,
            "max_tokens": 1024,
            "reasoning_effort": None,
            "use_model_sampling": True,
        },
    }


def test_review_profile_records_and_serializes_models_and_sampling(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """ReviewProfile contains models and sampling mappings and serializes them to JSON."""
    from devops_cli.ai import run_store
    from devops_cli.ai.review.profile import ReviewProfile, ReviewProfiler
    from devops_cli.config.settings import load_settings

    settings = load_settings().model_copy(deep=True)
    settings.ai.tasks.analysis = AITaskOverride(
        provider="gateway",
        model="devops-coder",
        temperature=0.3,
        top_p=0.85,
        max_tokens=2048,
    )
    monkeypatch.setattr("devops_cli.config.settings.load_settings", lambda: settings)
    monkeypatch.setattr(run_store, "gateway_pool", lambda task: [])

    profiler = ReviewProfiler()
    profile = profiler.build(session_id="test-session", target="src")

    assert "analysis" in profile.models
    assert "verification" in profile.models
    assert "compose" in profile.models
    assert "analysis" in profile.sampling

    json_str = profile.model_dump_json()
    roundtrip = ReviewProfile.model_validate_json(json_str)
    assert roundtrip.models == profile.models
    assert roundtrip.sampling == profile.sampling


def test_response_cache_key_varies_with_sampling_parameters(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """LLM client cache keys differ when temperature or max_tokens differ."""
    from devops_cli.ai.response_cache import LLMResponseCache
    from devops_cli.models.ai import ChatMessage
    from tests.llm_stream_fakes import route_llm_clients

    cache = LLMResponseCache(cache_dir=tmp_path / "cache", enabled=True)

    calls = 0

    def fake_handler(req: httpx2.Request) -> httpx2.Response:
        nonlocal calls
        calls += 1
        return httpx2.Response(
            200,
            json={"message": {"role": "assistant", "content": f"response {calls}"}},
        )

    route_llm_clients(monkeypatch, fake_handler)

    cfg1 = AIConfig(
        provider="ollama",
        temperature=0.7,
        top_p=0.9,
        max_tokens=100,
    )
    client1 = LLMClient(config=cfg1)
    client1._cache = cache

    cfg2 = AIConfig(
        provider="ollama",
        temperature=0.9,
        top_p=0.9,
        max_tokens=100,
    )
    client2 = LLMClient(config=cfg2)
    client2._cache = cache

    msgs = [ChatMessage(role="user", content="hello")]
    res1 = client1.chat_messages("system", msgs)
    res2 = client2.chat_messages("system", msgs)

    # Different temperatures must produce different cache keys and therefore make separate calls
    assert calls == 2
    assert res1.content == "response 1"
    assert res2.content == "response 2"

    # Repeating the first call hits the cache
    res1_cached = client1.chat_messages("system", msgs)
    assert calls == 2
    assert res1_cached.content == "response 1"
