"""Unit tests for the `model_fake` pytest fixture and client factory seam (#1001, ADR 0007)."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

import pytest
from pydantic import BaseModel
from pydantic_ai.direct import model_request_sync
from pydantic_ai.messages import ModelRequest, UserPromptPart

from devops_cli.ai.client import (
    AIClientError,
    build_llm_client,
    get_llm_client,
)
from tests.support.fakes.model import ModelFake, deterministic_embedding

if TYPE_CHECKING:
    pass


class SampleSchema(BaseModel):
    name: str
    score: int


def test_model_fake_fixture_injects_into_factory(model_fake: ModelFake) -> None:
    """The model_fake fixture installs into the factory seam so get_llm_client returns it."""
    client = get_llm_client()
    assert client is model_fake

    alias_client = build_llm_client()
    assert alias_client is model_fake


def test_model_fake_fixture_answers_and_records(model_fake: ModelFake) -> None:
    """The model_fake fixture returns queued answers and records invocations."""
    model_fake.answer("First canned answer", "Second canned answer")

    client = get_llm_client()
    res1 = client.chat("System guidance", "What is the status?")
    assert res1.content == "First canned answer"
    assert res1.model == "fake-model"

    res2 = client.chat("System guidance", "What is next?")
    assert res2.content == "Second canned answer"

    assert model_fake.call_count == 2
    assert model_fake.requested == ["What is the status?", "What is next?"]
    assert len(model_fake.sent) == 2
    assert model_fake.sent[0].system_prompt == "System guidance"
    assert model_fake.sent[0].prompt == "What is the status?"


def test_model_fake_fixture_route_matching(model_fake: ModelFake) -> None:
    """The model_fake fixture routes matching prompts to canned answers or errors."""
    model_fake.route("weather", "Sunny, 72F")
    model_fake.route(re.compile(r"stock:\s*(\w+)", re.IGNORECASE), "AAPL: $230")
    model_fake.route_error("crash", AIClientError("Simulated failure"))

    client = get_llm_client()
    assert client.chat("", "Tell me the weather").content == "Sunny, 72F"
    assert client.chat("", "Lookup stock: AAPL").content == "AAPL: $230"

    with pytest.raises(AIClientError, match="Simulated failure"):
        client.chat("", "Please crash now")


def test_model_fake_fixture_streaming(model_fake: ModelFake) -> None:
    """The model_fake fixture streams tokens through chat_stream and chat_messages_stream."""
    model_fake.answer("Streamed token output")

    client = get_llm_client()
    stream_chunks = list(client.chat_stream("System", "Stream this"))
    assert "".join(stream_chunks) == "Streamed token output"

    from devops_cli.models.ai import ChatMessage

    messages = [ChatMessage(role="user", content="Stream messages")]
    msg_chunks = list(client.chat_messages_stream("System", messages))
    assert "".join(msg_chunks) == "Streamed token output"


def test_model_fake_fixture_embeddings(model_fake: ModelFake) -> None:
    """The model_fake fixture returns deterministic unit-normalized embeddings."""
    client = get_llm_client()
    vecs = client.embed("test query text")
    expected = deterministic_embedding("test query text")
    assert vecs == [expected]


def test_model_fake_fixture_list_and_preload_models(model_fake: ModelFake) -> None:
    """The model_fake fixture reports model listing and ducked preload."""
    client = get_llm_client()
    assert "fake-model" in client.list_models()
    assert client.preload_models(["fake-model"]) == {"fake-model": True}
    assert client.model == "fake-model"
    assert client.backend_type == "fake"
    assert client.backend_host == "localhost"


def test_model_fake_fixture_chat_structured(model_fake: ModelFake) -> None:
    """The model_fake fixture returns structured output objects or validated models."""
    model_fake.answer('{"name": "alpha", "score": 99}')

    client = get_llm_client()
    structured = client.chat_structured("System", "Generate schema", schema=SampleSchema)
    assert isinstance(structured, SampleSchema)
    assert structured.name == "alpha"
    assert structured.score == 99


def test_model_fake_fixture_direct_model_request(model_fake: ModelFake) -> None:
    """The model_fake fixture acts as a direct pydantic_ai Model."""
    model_fake.answer("Direct model response")

    request = [ModelRequest(parts=[UserPromptPart(content="Direct prompt")])]
    response = model_request_sync(model_fake, request)
    assert response.parts[0].content == "Direct model response"
