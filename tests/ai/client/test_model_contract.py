"""Contract suite for the model and embedding edge fake and real implementations (#1001, ADR 0007).

Tests the promises of the model edge: completion, streaming, thinking extraction,
finish reasons, token usage, error propagation, sequential answering, pattern routing,
embeddings, and model listing. Verifies both the in-memory fake (`ModelFake`) and
real implementations (`TestModel`, `LLMClient` over recorded frames) offline without network.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

import httpx2
import pytest
from pydantic_ai.direct import model_request_stream_sync, model_request_sync
from pydantic_ai.messages import ModelRequest, TextPart, ThinkingPart, UserPromptPart
from pydantic_ai.models.test import TestModel

if TYPE_CHECKING:
    from devops_cli.ai.spend.ledger import SpendLedger

from devops_cli.ai.client import AIClientError, LLMClient
from devops_cli.config.settings import AIConfig
from devops_cli.models.ai import ChatMessage
from tests.llm_stream_fakes import (
    OPENAI_DONE,
    openai_chunk,
    reply,
    route_client,
)
from tests.support.fakes.model import (
    ModelAnswer,
    ModelCall,
    ModelFake,
    deterministic_embedding,
)


@pytest.fixture(autouse=True)
def _isolate_spend(spend_ledger: SpendLedger) -> None:
    """Isolate spend records for model contract tests (#2192)."""


def test_completion_contract_fake() -> None:
    """`ModelFake` fulfills the completion contract returning expected content and metadata."""
    fake = ModelFake("Hello world")
    response = fake.chat("You are an assistant.", "Greeting prompt")

    assert response.content == "Hello world"
    assert response.model == "fake-model"
    assert response.finish_reason is None
    assert response.prompt_tokens == 10
    assert response.completion_tokens == 20
    assert response.total_tokens == 30
    assert fake.call_count == 1
    assert fake.requested == ["Greeting prompt"]


def test_completion_contract_real_pydantic_ai() -> None:
    """Real `TestModel` fulfills the direct model request completion contract."""
    real_model = TestModel(custom_output_text="Real test model response")
    request = [ModelRequest(parts=[UserPromptPart(content="Test prompt")])]
    response = model_request_sync(real_model, request)

    text_parts = [part.content for part in response.parts if isinstance(part, TextPart)]
    assert "".join(text_parts) == "Real test model response"


def test_completion_contract_real_llm_client(monkeypatch: pytest.MonkeyPatch) -> None:
    """Real `LLMClient` over recorded JSON response fulfills the chat completion contract."""
    config = AIConfig(
        provider="openai",
        model="gpt-4o",
        api_base_url="http://example.com/v1",
        allow_private_network=True,
    )
    client = LLMClient(config=config, api_key="sk-test")

    payload = {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": "Hello from recorded completion",
                },
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 15, "completion_tokens": 25, "total_tokens": 40},
    }
    route_client(
        client,
        monkeypatch,
        lambda req: httpx2.Response(
            200, json=payload, headers={"content-type": "application/json"}
        ),
    )

    response = client.chat("System", "User")
    assert response.content == "Hello from recorded completion"
    assert response.finish_reason == "stop"


def test_streaming_contract_fake() -> None:
    """`ModelFake.chat_stream` yields tokens whose concatenation reconstructs full response."""
    fake = ModelFake("Streaming token test")
    tokens = list(fake.chat_stream("System", "Stream prompt"))

    assert "".join(tokens) == "Streaming token test"
    assert fake.call_count == 1
    assert fake.sent[0].stream is True


def test_streaming_contract_real_pydantic_ai() -> None:
    """Real `TestModel` streaming yields deltas whose concatenation matches full text."""
    real_model = TestModel(custom_output_text="Pydantic stream")
    request = [ModelRequest(parts=[UserPromptPart(content="Stream request")])]

    deltas: list[str] = []
    with model_request_stream_sync(real_model, request) as stream:
        for event in stream:
            delta = getattr(event, "delta", None)
            delta_content = getattr(delta, "content_delta", None)
            if delta_content:
                deltas.append(delta_content)

    assert "".join(deltas) == "Pydantic stream"


def test_streaming_contract_real_llm_client(monkeypatch: pytest.MonkeyPatch) -> None:
    """Real `LLMClient.chat_stream` yields tokens matching recorded chunks."""
    config = AIConfig(
        provider="openai",
        model="gpt-4o",
        api_base_url="http://example.com/v1",
        allow_private_network=True,
    )
    client = LLMClient(config=config, api_key="sk-test")

    frames = [
        openai_chunk("Stream "),
        openai_chunk("chunk "),
        openai_chunk("three", finish_reason="stop"),
        OPENAI_DONE,
    ]
    route_client(client, monkeypatch, lambda req: reply(frames))

    chunks = list(client.chat_stream("System", "Stream request"))
    assert "".join(chunks) == "Stream chunk three"


def test_thinking_extraction_contract() -> None:
    """`ModelFake` preserves thinking blocks in both `LLMResponse` and `ModelResponse`."""
    fake = ModelFake()
    fake.answer(
        ModelAnswer(
            content="Final answer",
            thinking="Detailed step-by-step reasoning",
            finish_reason="stop",
        )
    )

    llm_resp = fake.chat("System", "Solve riddle")
    assert llm_resp.content == "Final answer"
    assert llm_resp.thinking == "Detailed step-by-step reasoning"
    assert llm_resp.finish_reason == "stop"

    request = [ModelRequest(parts=[UserPromptPart(content="Solve riddle")])]
    direct_resp = model_request_sync(fake, request)
    assert direct_resp.finish_reason == "stop"
    thinking_parts = [part.content for part in direct_resp.parts if isinstance(part, ThinkingPart)]
    assert thinking_parts == ["Detailed step-by-step reasoning"]


def test_finish_reason_and_usage_contract() -> None:
    """`ModelFake` reflects custom finish reasons and token usage counts."""
    fake = ModelFake()
    fake.answer(
        ModelAnswer(
            content="Truncated output",
            finish_reason="length",
            input_tokens=150,
            output_tokens=400,
        )
    )

    response = fake.chat("System", "Generate report")
    assert response.finish_reason == "length"
    assert response.prompt_tokens == 150
    assert response.completion_tokens == 400
    assert response.total_tokens == 550


def test_error_propagation_contract() -> None:
    """`ModelFake` raises configured exceptions on matching prompts or queued answers."""
    fake = ModelFake()
    fake.route_error("fatal-crash", AIClientError("Simulated provider outage"))
    fake.answer(RuntimeError("Queued error"))

    with pytest.raises(AIClientError, match="Simulated provider outage"):
        fake.chat("System", "Run fatal-crash now")

    with pytest.raises(RuntimeError, match="Queued error"):
        fake.chat("System", "Normal prompt triggers queued error")


def test_sequential_answering_contract() -> None:
    """`fake.answer(...)` answers queued responses in order and repeats the final entry."""
    fake = ModelFake()
    fake.answer("First step", "Second step")

    assert fake.chat("System", "Query 1").content == "First step"
    assert fake.chat("System", "Query 2").content == "Second step"
    assert fake.chat("System", "Query 3").content == "Second step"
    assert fake.requested == ["Query 1", "Query 2", "Query 3"]


def test_pattern_routing_contract() -> None:
    """`fake.route(...)` dispatches by substring, regex, and callable predicate."""
    fake = ModelFake("Default answer")
    fake.route("substring-key", "Substring answer")
    fake.route(re.compile(r"^regex-\d+$"), "Regex answer")
    fake.route(lambda text: "custom" in text, "Predicate answer")

    assert fake.chat("System", "contains substring-key here").content == "Substring answer"
    assert fake.chat("System", "regex-123").content == "Regex answer"
    assert fake.chat("System", "has custom word").content == "Predicate answer"
    assert fake.chat("System", "unmatched text").content == "Default answer"


def test_call_recording_and_reset_contract() -> None:
    """`ModelFake` records complete call details and clears them on `reset()`."""
    fake = ModelFake()
    fake.chat("System directive", "First prompt")
    fake.chat_messages(
        "Chat system",
        [
            ChatMessage(role="user", content="User message"),
            ChatMessage(role="assistant", content="Assistant reply"),
        ],
    )

    assert fake.call_count == 2
    assert fake.requested == ["First prompt", "User message"]
    assert fake.sent[0] == ModelCall(
        prompt="First prompt",
        system_prompt="System directive",
        messages=(),
        model_name="fake-model",
        stream=False,
    )

    fake.reset()
    assert fake.call_count == 0
    assert fake.sent == []
    assert fake.requested == []


def test_deterministic_embedding_contract() -> None:
    """`fake.embed(...)` produces unit-normalized float vectors of requested dimension."""
    fake = ModelFake()
    vector_a = fake.embed("hello world", dimension=64)[0]
    vector_b = fake.embed("hello world", dimension=64)[0]
    vector_c = fake.embed("different text", dimension=64)[0]

    assert len(vector_a) == 64
    assert vector_a == vector_b
    assert vector_a != vector_c

    norm = sum(x * x for x in vector_a)
    assert pytest.approx(norm, rel=1e-3) == 1.0

    direct_embed = deterministic_embedding("direct invocation", dimension=32)
    assert len(direct_embed) == 32


def test_the_fake_embeds_through_the_embedder_protocol_of_intake() -> None:
    """`fake.embed_texts(...)` gives the vectors `fake.embed(...)` gives, query or not (#2420)."""
    fake = ModelFake()

    assert (
        fake.embed_texts(["a", "b"]),
        fake.embed_texts(["a"], is_query=True),
    ) == (fake.embed(["a", "b"]), fake.embed(["a"]))


def test_list_models_and_llm_client_duck_typing() -> None:
    """`ModelFake` presents compatible properties and helpers for `LLMClient` consumers."""
    fake = ModelFake(available_models=["fake-1", "fake-2"])

    assert fake.list_models() == ["fake-1", "fake-2"]
    assert fake.backend_type == "fake"
    assert fake.backend_host == "localhost"
    assert fake.get_context_window() == 128000
    assert fake.model == "fake-model"


def test_pydantic_ai_model_request_sync_over_the_fake() -> None:
    """`ModelFake` answers a native `model_request_sync` with a `ModelResponse` of its content."""
    fake = ModelFake("Pydantic AI direct sync response")
    request = [ModelRequest(parts=[UserPromptPart(content="Explain unit testing")])]
    response = model_request_sync(fake, request)

    text_parts = [part.content for part in response.parts if isinstance(part, TextPart)]
    assert "".join(text_parts) == "Pydantic AI direct sync response"
    assert fake.requested == ["Explain unit testing"]


def test_pydantic_ai_model_request_stream_sync_over_the_fake() -> None:
    """`ModelFake` streams a native `model_request_stream_sync` whose deltas rebuild its content."""
    fake = ModelFake("Pydantic AI stream response")
    request = [ModelRequest(parts=[UserPromptPart(content="Explain streaming")])]

    deltas: list[str] = []
    with model_request_stream_sync(fake, request) as stream:
        for event in stream:
            delta_content = getattr(getattr(event, "delta", None), "content_delta", None)
            if delta_content:
                deltas.append(delta_content)

    assert "".join(deltas) == "Pydantic AI stream response"
    assert fake.call_count == 1
