"""Every model reply carries the reason it ended, read from its provider and never guessed."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any, get_args

import httpx2
import pytest
from pydantic_ai.messages import FinishReason

if TYPE_CHECKING:
    from devops_cli.ai.spend.ledger import SpendLedger

from devops_cli.ai.client import LLMClient, LLMResponse, ReplyRejectedError, RequestPriority
from devops_cli.config.constants import (
    CONST_ANTHROPIC_STOP_REASONS,
    CONST_OLLAMA_DONE_REASONS,
    CONST_OPENAI_FINISH_REASONS,
    CONST_UNCACHED_FINISH_REASONS,
)
from devops_cli.config.settings import AIConfig
from devops_cli.models.ai import ChatMessage
from tests.llm_stream_fakes import route_client

_PROMPT = [ChatMessage(role="user", content="hi")]

# Each provider's stop values, as the issue lists them, and the reason each must become.
_STOP_VALUES: dict[str, list[tuple[str | None, FinishReason | None]]] = {
    "openai": [
        ("stop", "stop"),
        ("length", "length"),
        ("tool_calls", "tool_call"),
        ("function_call", "tool_call"),
        ("content_filter", "content_filter"),
        (None, None),
    ],
    "anthropic": [
        ("end_turn", "stop"),
        ("stop_sequence", "stop"),
        ("max_tokens", "length"),
        ("model_context_window_exceeded", "length"),
        ("tool_use", "tool_call"),
        ("refusal", "content_filter"),
        ("pause_turn", None),
        (None, None),
    ],
    "ollama": [
        ("stop", "stop"),
        ("length", "length"),
        ("load", None),
        ("unload", None),
        (None, None),
    ],
}


def _with(key: str, value: str | None) -> dict[str, str]:
    """The provider's stop field, or no field at all when the value is absent."""
    return {key: value} if value is not None else {}


# A non-streamed reply body from each provider, carrying one stop value.
_REPLY_BODIES: dict[str, Callable[[str | None], dict[str, Any]]] = {
    "openai": lambda value: {
        "choices": [{"message": {"content": "ok"}, **_with("finish_reason", value)}]
    },
    "anthropic": lambda value: {
        "content": [{"type": "text", "text": "ok"}],
        **_with("stop_reason", value),
    },
    "ollama": lambda value: {
        "message": {"content": "ok"},
        "done": True,
        **_with("done_reason", value),
    },
}

# Each provider's non-streamed request, which parses the reply.
_REQUESTS: dict[str, Callable[[LLMClient], LLMResponse]] = {
    "openai": lambda client: client._openai_compat_messages("sys", _PROMPT),
    "anthropic": lambda client: client._claude_messages("sys", _PROMPT),
    "ollama": lambda client: client._ollama_request(
        "http://example.com:11434", "sys", _PROMPT, think=False
    ),
}

_CONFIGS: dict[str, AIConfig] = {
    "openai": AIConfig(provider="openai", model="gpt-test", api_base_url="http://example.com/v1"),
    "anthropic": AIConfig(
        provider="claude", model="claude-test", api_base_url="http://example.com"
    ),
    "ollama": AIConfig(provider="ollama", model="llama3", ollama_urls=["http://example.com:11434"]),
}


@pytest.mark.parametrize("provider", ["openai", "anthropic", "ollama"])
def test_each_parser_reads_its_providers_stop_value(
    provider: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify each non-streamed parser maps every stop value its provider sends, absent included."""
    table = _STOP_VALUES[provider]
    bodies = iter([_REPLY_BODIES[provider](value) for value, _ in table])
    client = LLMClient(
        _CONFIGS[provider].model_copy(update={"allow_private_network": True}), api_key="sk-test"
    )

    def _handle_request(request: httpx2.Request) -> httpx2.Response:
        if "/models" in request.url.path:
            return httpx2.Response(404, json={"error": {"type": "not_found_error"}})
        return httpx2.Response(200, json=next(bodies))

    route_client(client, monkeypatch, _handle_request)

    assert [(value, _REQUESTS[provider](client).finish_reason) for value, _ in table] == table


def test_every_mapped_reason_is_a_pydantic_ai_finish_reason() -> None:
    """Verify each map yields only pydantic-ai's FinishReason values, or None for unknown."""
    known = {*get_args(FinishReason), None}
    tables = (CONST_OPENAI_FINISH_REASONS, CONST_ANTHROPIC_STOP_REASONS, CONST_OLLAMA_DONE_REASONS)

    assert (
        [[value for value in table.values() if value not in known] for table in tables],
        sorted(CONST_UNCACHED_FINISH_REASONS - known),
    ) == ([[], [], []], [])


def test_the_reason_survives_conversion_to_a_model_response() -> None:
    """Verify `to_model_response` passes the reason on."""
    assert (
        LLMResponse("ok", finish_reason="length").to_model_response().finish_reason,
        LLMResponse("ok").to_model_response().finish_reason,
    ) == ("length", None)


@pytest.mark.parametrize(
    ("reason", "cached"),
    [
        ("length", False),
        ("content_filter", False),
        ("error", False),
        ("tool_call", False),
        ("stop", True),
        (None, True),
    ],
)
def test_only_replies_that_ended_normally_are_cached(
    reason: FinishReason | None, cached: bool, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify a cut, filtered, failed or tool-calling reply is returned but not cached, so it
    is asked again."""
    provider_calls: list[str] = []

    def provider(
        _self: object,
        _system: str,
        _messages: list[ChatMessage],
        *,
        enable_thinking: bool = True,
        priority: RequestPriority | str | None = None,
    ) -> LLMResponse:
        provider_calls.append(_system)
        return LLMResponse("reply", prompt_tokens=3, completion_tokens=2, finish_reason=reason)

    monkeypatch.setattr(LLMClient, "_ollama_messages", provider)
    monkeypatch.setattr("devops_cli.ai.spend.track_request_spend", lambda **kwargs: None)
    client = LLMClient(AIConfig(provider="ollama", model="llama3"))
    stored: list[str] = []
    store = client.cache.set
    monkeypatch.setattr(
        client.cache, "set", lambda **entry: (stored.append(entry["key"]), store(**entry))[1]
    )

    first = client.chat("sys", "user")
    second = client.chat("sys", "user")

    assert (str(first), first.finish_reason, len(stored), len(provider_calls), second.cached) == (
        "reply",
        reason,
        1 if cached else 0,
        1 if cached else 2,
        cached,
    )


def test_a_reply_the_validator_refuses_keeps_its_finish_reason(
    monkeypatch: pytest.MonkeyPatch, public_dns: str, spend_ledger: SpendLedger
) -> None:
    """Verify the rejection carries the reply as the provider gave it, so a caller reads why it
    ended, and a refused reply is neither cached nor sent again (#1013)."""
    config = AIConfig(
        provider="gateway", model="demo-model", gateway_url="http://example.com:4000/v1"
    )
    client = LLMClient(config, api_key="sk")
    body = {"choices": [{"message": {"content": "not json"}, "finish_reason": "length"}]}
    sent = route_client(client, monkeypatch, lambda _request: httpx2.Response(200, json=body))

    with pytest.raises(ReplyRejectedError) as refused:
        client.chat("sys", "user", validator=lambda text: False, max_retries=0)

    assert (
        len(sent),
        str(refused.value.reply),
        getattr(refused.value.reply, "finish_reason", None),
    ) == (1, "not json", "length")
