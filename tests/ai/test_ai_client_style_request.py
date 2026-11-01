"""A model call asks for ASD-STE100 Simplified Technical English in its system prompt (#1866).

The client reaches its provider through httpx2's `MockTransport`, as the other client tests do, so
each test reads the system message of the request the provider is sent. `ModelFake` replaces the
whole client at the factory seam and never runs this code. Hosts are `example.com`.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

import httpx2
import pytest
from pydantic import BaseModel
from syrupy.assertion import SnapshotAssertion

from devops_cli.ai.client import LLMClient
from devops_cli.ai.context_budget import count_tokens
from devops_cli.ai.spend.ledger import SpendLedger, observe_llm_calls
from devops_cli.ai.task_loader import load_task_prompt
from devops_cli.config.settings import AIConfig
from devops_cli.models.ai import ChatMessage
from tests.llm_stream_fakes import OPENAI_DONE, openai_chunk, reply, route_client

_SYSTEM = "You review one change."
_PROMPT = "Explain the diff."
_MESSAGES = [ChatMessage(role="user", content=_PROMPT)]
_ANSWER = "Done."


@pytest.fixture(autouse=True)
def _isolate_spend(spend_ledger: SpendLedger) -> None:
    """Isolate spend records for style request tests (#2192)."""


class Verdict(BaseModel):
    """A structured reply with one free-text field."""

    summary: str


def _client() -> LLMClient:
    config = AIConfig(
        provider="openai", model="demo-model", api_base_url="http://example.com:8080/v1"
    )
    return LLMClient(config, api_key="sk")


def _provider(request: httpx2.Request) -> httpx2.Response:
    """A reply in the form the request asks for: a stream of events, or one message."""
    if json.loads(request.content).get("stream"):
        return reply([openai_chunk(_ANSWER), openai_chunk(finish_reason="stop"), OPENAI_DONE])
    choice = {"message": {"content": _ANSWER}, "finish_reason": "stop"}
    return httpx2.Response(200, json={"choices": [choice]})


def _sent_messages(request: httpx2.Request) -> list[dict[str, str]]:
    messages: list[dict[str, str]] = json.loads(request.content)["messages"]
    return messages


_ENTRY_POINTS: dict[str, Callable[[LLMClient], object]] = {
    "chat": lambda client: client.chat(_SYSTEM, _PROMPT, use_cache=False),
    "chat_messages": lambda client: client.chat_messages(_SYSTEM, _MESSAGES, use_cache=False),
    "chat_stream": lambda client: list(client.chat_stream(_SYSTEM, _PROMPT)),
    "chat_messages_stream": lambda client: list(client.chat_messages_stream(_SYSTEM, _MESSAGES)),
}


@pytest.mark.parametrize("entry_point", _ENTRY_POINTS)
def test_every_free_text_call_sends_the_callers_prompt_then_the_style_request(
    entry_point: str,
    monkeypatch: pytest.MonkeyPatch,
    public_dns: str,
    snapshot: SnapshotAssertion,
) -> None:
    """Verify each way to ask for free text appends the request to the system prompt, once,
    and leaves the user message as the caller wrote it."""
    client = _client()
    sent = route_client(client, monkeypatch, _provider)

    _ENTRY_POINTS[entry_point](client)

    assert _sent_messages(sent[0]) == snapshot


def test_a_call_without_a_system_prompt_sends_the_style_request_alone(
    monkeypatch: pytest.MonkeyPatch, public_dns: str
) -> None:
    """Verify the request becomes the system prompt when the caller gives none."""
    client = _client()
    sent = route_client(client, monkeypatch, _provider)

    client.chat_messages("", _MESSAGES, use_cache=False)

    assert _sent_messages(sent[0])[0] == {
        "role": "system",
        "content": load_task_prompt("style_ste100.md"),
    }


def test_a_call_that_sets_its_own_format_keeps_its_instruction_first_and_the_request_defers_to_it(
    monkeypatch: pytest.MonkeyPatch, public_dns: str
) -> None:
    """Verify a grader's own format instruction stays whole and first, and the request ends the
    system prompt with the rule that a format the task sets wins over the style."""
    grader = "Return only a JSON object with a score from 0 to 10."
    client = _client()
    sent = route_client(client, monkeypatch, _provider)

    client.chat(grader, _PROMPT, use_cache=False)

    system = _sent_messages(sent[0])[0]["content"]
    request = load_task_prompt("style_ste100.md")
    assert (
        system == f"{grader}\n\n{request}",
        "If the task sets an output format, such as JSON, code or a score, keep that format."
        in request,
    ) == (True, True)


def test_a_structured_call_gets_the_request_once_before_the_schema_instruction(
    monkeypatch: pytest.MonkeyPatch, public_dns: str
) -> None:
    """Verify the request sits between the caller's prompt and the schema instruction, appears
    once, and leaves the schema as the end of the system prompt."""
    client = _client()
    sent = route_client(
        client,
        monkeypatch,
        lambda request: httpx2.Response(
            200,
            json={
                "choices": [{"message": {"content": '{"summary": "ok"}'}, "finish_reason": "stop"}]
            },
        ),
    )

    verdict = client.chat_structured(_SYSTEM, _PROMPT, Verdict, use_cache=False)

    schema = json.dumps(Verdict.model_json_schema(), ensure_ascii=False)
    expected = "\n\n".join(
        (
            _SYSTEM,
            load_task_prompt("style_ste100.md"),
            load_task_prompt("structured_output_schema.md"),
            schema,
        )
    )
    assert (verdict, _sent_messages(sent[0])[0]["content"]) == (Verdict(summary="ok"), expected)


def test_a_reply_cached_before_the_style_request_is_not_served(
    monkeypatch: pytest.MonkeyPatch, public_dns: str
) -> None:
    """Verify the cache key holds the system prompt as sent, so a reply cached under the bare
    prompt is passed over and the call reaches the provider."""
    client = _client()
    bare_key = client.cache.generate_key(
        "openai", "demo-model", _SYSTEM, _MESSAGES, {"enable_thinking": True}
    )
    client.cache.set(
        key=bare_key,
        provider="openai",
        model="demo-model",
        system=_SYSTEM,
        prompt=_PROMPT,
        content="An earlier reply.",
    )
    sent = route_client(client, monkeypatch, _provider)

    answer = client.chat(_SYSTEM, _PROMPT)

    assert (str(answer), len(sent), answer.cached) == (_ANSWER, 1, False)


def test_a_repeated_call_is_served_from_the_cache_under_the_system_prompt_as_sent(
    monkeypatch: pytest.MonkeyPatch, public_dns: str
) -> None:
    """Verify the second identical call reaches no provider, so the style request does not
    defeat the cache."""
    client = _client()
    sent = route_client(client, monkeypatch, _provider)

    first = client.chat(_SYSTEM, _PROMPT)
    second = client.chat(_SYSTEM, _PROMPT)

    assert (str(first), str(second), len(sent), second.cached) == (_ANSWER, _ANSWER, 1, True)


def test_the_token_estimate_of_a_request_counts_the_style_request(
    monkeypatch: pytest.MonkeyPatch, public_dns: str
) -> None:
    """Verify the prompt tokens a reply without usage figures is billed for cover the system
    prompt as sent, the style request included."""
    client = _client()
    sent = route_client(client, monkeypatch, _provider)
    recorded: list[dict[str, Any]] = []

    with observe_llm_calls(recorded.append):
        client.chat(_SYSTEM, _PROMPT, use_cache=False)

    system = _sent_messages(sent[0])[0]["content"]
    assert (recorded[0]["prompt_tokens"], system.startswith(f"{_SYSTEM}\n\n")) == (
        count_tokens(system) + count_tokens(_PROMPT),
        True,
    )
