"""Unit tests for native Pydantic AI direct requests and model invocation optimizations."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

import pytest
from pydantic_ai.messages import (
    ModelRequest,
    ModelResponse,
    SystemPromptPart,
    TextPart,
    ThinkingPart,
    UserPromptPart,
)
from pydantic_ai.models.test import TestModel

from devops_cli.ai.direct import (
    StreamedResponseSync,
    direct_model_request,
    direct_model_request_stream,
    direct_model_request_stream_sync,
    direct_model_request_sync,
    extract_response_text,
    extract_response_thinking,
    model_request,
    model_request_stream,
    model_request_stream_sync,
    model_request_sync,
    to_llm_response,
    to_model_messages,
)
from devops_cli.models.ai import ChatMessage


def test_native_direct_reexports() -> None:
    """Verify that native pydantic_ai.direct symbols are re-exported and callable."""
    import pydantic_ai.direct as native_direct

    assert model_request is native_direct.model_request
    assert model_request_sync is native_direct.model_request_sync
    assert model_request_stream is native_direct.model_request_stream
    assert model_request_stream_sync is native_direct.model_request_stream_sync
    assert StreamedResponseSync is native_direct.StreamedResponseSync


def test_to_model_messages_from_str() -> None:
    """Verify that a single string prompt converts to ModelRequest with UserPromptPart."""
    msgs = to_model_messages("What is CI/CD?")
    assert len(msgs) == 1
    req = msgs[0]
    assert isinstance(req, ModelRequest)
    assert len(req.parts) == 1
    assert isinstance(req.parts[0], UserPromptPart)
    assert req.parts[0].content == "What is CI/CD?"


def test_to_model_messages_with_system_prompt() -> None:
    """Verify that system prompt is prepended as SystemPromptPart."""
    msgs = to_model_messages("List Kubernetes pods", system_prompt="You are an SRE.")
    assert len(msgs) == 1
    req = msgs[0]
    assert isinstance(req, ModelRequest)
    assert len(req.parts) == 2
    assert isinstance(req.parts[0], SystemPromptPart)
    assert req.parts[0].content == "You are an SRE."
    assert isinstance(req.parts[1], UserPromptPart)
    assert req.parts[1].content == "List Kubernetes pods"


def test_to_model_messages_from_chat_messages() -> None:
    """Verify conversion of multi-turn ChatMessage sequence."""
    chat_history = [
        ChatMessage(role="system", content="System instruction"),
        ChatMessage(role="user", content="First question"),
        ChatMessage(role="assistant", content="First answer"),
        ChatMessage(role="user", content="Second question"),
    ]
    msgs = to_model_messages(chat_history)
    assert len(msgs) == 3
    # First turn: System + User in ModelRequest
    assert isinstance(msgs[0], ModelRequest)
    assert len(msgs[0].parts) == 2
    assert isinstance(msgs[0].parts[0], SystemPromptPart)
    assert msgs[0].parts[0].content == "System instruction"
    assert isinstance(msgs[0].parts[1], UserPromptPart)
    assert msgs[0].parts[1].content == "First question"

    # Second turn: Assistant response
    assert isinstance(msgs[1], ModelResponse)
    assert isinstance(msgs[1].parts[0], TextPart)
    assert msgs[1].parts[0].content == "First answer"

    # Third turn: User follow-up
    assert isinstance(msgs[2], ModelRequest)
    assert isinstance(msgs[2].parts[0], UserPromptPart)
    assert msgs[2].parts[0].content == "Second question"


def test_to_model_messages_passthrough() -> None:
    """Verify that already typed ModelMessage instances pass through directly."""
    orig = [ModelRequest.user_text_prompt("Existing prompt")]
    msgs = to_model_messages(orig)
    assert msgs == orig


def test_to_model_messages_other_roles_and_system_only() -> None:
    """Verify other role fallbacks and system-only messages."""
    from types import SimpleNamespace

    custom_role = [SimpleNamespace(role="custom", content="Custom payload")]
    msgs = to_model_messages(custom_role)
    assert len(msgs) == 1
    assert isinstance(msgs[0], ModelRequest)
    assert isinstance(msgs[0].parts[0], UserPromptPart)
    assert msgs[0].parts[0].content == "Custom payload"

    # System-only ChatMessage list
    sys_only = to_model_messages([ChatMessage(role="system", content="System instructions only")])
    assert len(sys_only) == 1
    assert isinstance(sys_only[0], ModelRequest)
    assert isinstance(sys_only[0].parts[0], SystemPromptPart)
    assert sys_only[0].parts[0].content == "System instructions only"


def test_direct_model_request_sync_with_test_model() -> None:
    """Verify synchronous direct model execution using TestModel."""
    res = direct_model_request_sync(
        model=TestModel(),
        prompt_or_messages="Run diagnostic check",
        system_prompt="You are a DevOps bot.",
    )
    assert isinstance(res, ModelResponse)
    assert extract_response_text(res) == "success (no tool calls)"


@pytest.mark.asyncio
async def test_direct_model_request_async_with_test_model() -> None:
    """Verify asynchronous direct model execution using TestModel."""
    res = await direct_model_request(
        model=TestModel(),
        prompt_or_messages="Check cluster health",
    )
    assert isinstance(res, ModelResponse)
    assert extract_response_text(res) == "success (no tool calls)"


def test_direct_model_request_stream_sync() -> None:
    """Verify synchronous streaming chunks from direct request."""
    chunks = list(
        direct_model_request_stream_sync(
            model=TestModel(),
            prompt_or_messages="Stream response",
        )
    )
    assert len(chunks) > 0
    full_text = "".join(chunks)
    assert "success (no tool calls)" in full_text


@pytest.mark.asyncio
async def test_direct_model_request_stream_async() -> None:
    """Verify asynchronous streaming chunks from direct request."""
    chunks: list[str] = []
    async for chunk in direct_model_request_stream(
        model=TestModel(),
        prompt_or_messages="Async stream response",
    ):
        chunks.append(chunk)

    assert len(chunks) > 0
    full_text = "".join(chunks)
    assert "success (no tool calls)" in full_text


def test_direct_model_request_with_concurrency_limit() -> None:
    """Verify that direct request respects model concurrency limit wrappers."""
    res = direct_model_request_sync(
        model=TestModel(),
        prompt_or_messages="Test concurrency wrapper",
        model_concurrency=2,
    )
    assert isinstance(res, ModelResponse)
    assert extract_response_text(res) == "success (no tool calls)"


def test_extract_response_text_and_thinking() -> None:
    """Verify extraction of thinking tokens and final text from ModelResponse."""
    resp = ModelResponse(
        parts=[
            ThinkingPart(content="Thinking about deployment rollback..."),
            TextPart(content="Rollback initiated successfully."),
        ],
        timestamp=datetime.now(UTC),
    )
    assert extract_response_thinking(resp) == "Thinking about deployment rollback..."
    assert extract_response_text(resp) == "Rollback initiated successfully."


def test_to_llm_response_adapter() -> None:
    """Verify conversion of ModelResponse to legacy LLMResponse."""
    resp = ModelResponse(
        parts=[
            ThinkingPart(content="Analyzing cluster logs..."),
            TextPart(content="Pods are healthy."),
        ],
        model_name="gemma4:26b",
        timestamp=datetime.now(UTC),
    )
    llm_resp = to_llm_response(resp)
    assert str(llm_resp) == "Pods are healthy."
    assert llm_resp.content == "Pods are healthy."
    assert llm_resp.thinking == "Analyzing cluster logs..."


def test_unified_client_direct_request_integration() -> None:
    """Verify that LLMClient provides direct_request and direct_request_sync methods."""
    from devops_cli.ai.client.unified import LLMClient
    from devops_cli.config.settings import AIConfig

    client = LLMClient(AIConfig(model="test"))
    # Synchronous direct request
    res_sync = client.direct_request_sync(
        prompt="Verify direct API on client",
        model=TestModel(),
    )
    assert isinstance(res_sync, ModelResponse)
    assert extract_response_text(res_sync) == "success (no tool calls)"

    # Asynchronous direct request
    res_async = asyncio.run(
        client.direct_request(
            prompt="Verify async direct API on client",
            model=TestModel(),
        )
    )
    assert isinstance(res_async, ModelResponse)
    assert extract_response_text(res_async) == "success (no tool calls)"
