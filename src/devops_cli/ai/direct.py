"""Native Pydantic AI Direct Model Requests and Invocations.

Provides imperative model execution with minimal abstraction per the Pydantic AI
Direct API specification (pydantic_ai.direct), offering zero-overhead synchronous
and asynchronous model requests, streaming execution, and telemetry integration.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator, Generator, Sequence
from typing import TYPE_CHECKING, Any

from pydantic_ai.direct import (
    StreamedResponseSync,
    model_request,
    model_request_stream,
    model_request_stream_sync,
    model_request_sync,
)
from pydantic_ai.messages import (
    ModelMessage,
    ModelRequest,
    ModelRequestPart,
    ModelResponse,
    PartDeltaEvent,
    SystemPromptPart,
    TextPart,
    TextPartDelta,
    ThinkingPart,
    UserPromptPart,
)
from pydantic_ai.models import KnownModelName, Model, ModelRequestParameters
from pydantic_ai.models.instrumented import InstrumentationSettings

from devops_cli.ai.concurrency import AnyConcurrencyLimit
from devops_cli.ai.settings import ModelSettings
from devops_cli.telemetry import trace_span

if TYPE_CHECKING:
    from devops_cli.ai.client.models import LLMResponse
    from devops_cli.models.ai import ChatMessage


def to_model_messages(
    prompt_or_messages: str | Sequence[ModelMessage | ChatMessage | Any],
    system_prompt: str = "",
) -> list[ModelMessage]:
    """Convert string prompt, ChatMessage sequence, or ModelMessage sequence to list[ModelMessage]."""
    if isinstance(prompt_or_messages, str):
        parts: list[ModelRequestPart] = []
        if system_prompt:
            parts.append(SystemPromptPart(content=system_prompt))
        parts.append(UserPromptPart(content=prompt_or_messages))
        return [ModelRequest(parts=parts)]

    if prompt_or_messages and isinstance(prompt_or_messages[0], (ModelRequest, ModelResponse)):
        return [m for m in prompt_or_messages if isinstance(m, (ModelRequest, ModelResponse))]

    model_msgs: list[ModelMessage] = []
    pending_system: str | None = system_prompt if system_prompt else None

    for m in prompt_or_messages:
        role = getattr(m, "role", "user").lower()
        content = getattr(m, "content", "")
        if role == "system":
            pending_system = f"{pending_system}\n\n{content}".strip() if pending_system else content
        elif role == "user":
            req_parts: list[ModelRequestPart] = []
            if pending_system:
                req_parts.append(SystemPromptPart(content=pending_system))
                pending_system = None
            req_parts.append(UserPromptPart(content=content))
            model_msgs.append(ModelRequest(parts=req_parts))
        elif role == "assistant":
            model_msgs.append(ModelResponse(parts=[TextPart(content=content)]))
        else:
            model_msgs.append(ModelRequest(parts=[UserPromptPart(content=content)]))

    if pending_system and not model_msgs:
        model_msgs.append(ModelRequest(parts=[SystemPromptPart(content=pending_system)]))

    return model_msgs


def direct_model_request_sync(
    prompt_or_messages: str | Sequence[ModelMessage | ChatMessage | Any],
    model: Model | KnownModelName | str | None = None,
    *,
    system_prompt: str = "",
    model_settings: ModelSettings | None = None,
    model_request_parameters: ModelRequestParameters | None = None,
    model_concurrency: AnyConcurrencyLimit = None,
    instrument: InstrumentationSettings | bool | None = None,
) -> ModelResponse:
    """Execute a synchronous direct model request with telemetry and automatic model resolution."""
    from devops_cli.ai.pydantic_ai_bridge import resolve_pydantic_ai_model

    resolved_model = resolve_pydantic_ai_model(model, model_concurrency=model_concurrency)
    msgs = to_model_messages(prompt_or_messages, system_prompt=system_prompt)
    model_repr = getattr(resolved_model, "model_name", str(resolved_model))

    with trace_span(
        "pydantic_ai.direct.model_request_sync",
        attributes={"gen_ai.request.model": model_repr, "gen_ai.messages_count": len(msgs)},
    ):
        return model_request_sync(
            resolved_model,
            msgs,
            model_settings=model_settings,
            model_request_parameters=model_request_parameters,
            instrument=instrument,
        )


async def direct_model_request(
    prompt_or_messages: str | Sequence[ModelMessage | ChatMessage | Any],
    model: Model | KnownModelName | str | None = None,
    *,
    system_prompt: str = "",
    model_settings: ModelSettings | None = None,
    model_request_parameters: ModelRequestParameters | None = None,
    model_concurrency: AnyConcurrencyLimit = None,
    instrument: InstrumentationSettings | bool | None = None,
) -> ModelResponse:
    """Execute an asynchronous direct model request with telemetry and automatic model resolution."""
    from devops_cli.ai.pydantic_ai_bridge import resolve_pydantic_ai_model

    resolved_model = resolve_pydantic_ai_model(model, model_concurrency=model_concurrency)
    msgs = to_model_messages(prompt_or_messages, system_prompt=system_prompt)
    model_repr = getattr(resolved_model, "model_name", str(resolved_model))

    with trace_span(
        "pydantic_ai.direct.model_request",
        attributes={"gen_ai.request.model": model_repr, "gen_ai.messages_count": len(msgs)},
    ):
        return await model_request(
            resolved_model,
            msgs,
            model_settings=model_settings,
            model_request_parameters=model_request_parameters,
            instrument=instrument,
        )


def direct_model_request_stream_sync(
    prompt_or_messages: str | Sequence[ModelMessage | ChatMessage | Any],
    model: Model | KnownModelName | str | None = None,
    *,
    system_prompt: str = "",
    model_settings: ModelSettings | None = None,
    model_request_parameters: ModelRequestParameters | None = None,
    model_concurrency: AnyConcurrencyLimit = None,
    instrument: InstrumentationSettings | bool | None = None,
) -> Generator[str]:
    """Execute a synchronous streamed direct model request and yield streaming text deltas."""
    from devops_cli.ai.pydantic_ai_bridge import resolve_pydantic_ai_model

    resolved_model = resolve_pydantic_ai_model(model, model_concurrency=model_concurrency)
    msgs = to_model_messages(prompt_or_messages, system_prompt=system_prompt)
    model_repr = getattr(resolved_model, "model_name", str(resolved_model))

    with trace_span(
        "pydantic_ai.direct.model_request_stream_sync",
        attributes={"gen_ai.request.model": model_repr, "gen_ai.messages_count": len(msgs)},
    ):
        with model_request_stream_sync(
            resolved_model,
            msgs,
            model_settings=model_settings,
            model_request_parameters=model_request_parameters,
            instrument=instrument,
        ) as stream:
            for event in stream:
                if isinstance(event, PartDeltaEvent) and isinstance(event.delta, TextPartDelta):
                    yield event.delta.content_delta


async def direct_model_request_stream(
    prompt_or_messages: str | Sequence[ModelMessage | ChatMessage | Any],
    model: Model | KnownModelName | str | None = None,
    *,
    system_prompt: str = "",
    model_settings: ModelSettings | None = None,
    model_request_parameters: ModelRequestParameters | None = None,
    model_concurrency: AnyConcurrencyLimit = None,
    instrument: InstrumentationSettings | bool | None = None,
) -> AsyncGenerator[str]:
    """Execute an asynchronous streamed direct model request and yield streaming text deltas."""
    from devops_cli.ai.pydantic_ai_bridge import resolve_pydantic_ai_model

    resolved_model = resolve_pydantic_ai_model(model, model_concurrency=model_concurrency)
    msgs = to_model_messages(prompt_or_messages, system_prompt=system_prompt)
    model_repr = getattr(resolved_model, "model_name", str(resolved_model))

    with trace_span(
        "pydantic_ai.direct.model_request_stream",
        attributes={"gen_ai.request.model": model_repr, "gen_ai.messages_count": len(msgs)},
    ):
        async with model_request_stream(
            resolved_model,
            msgs,
            model_settings=model_settings,
            model_request_parameters=model_request_parameters,
            instrument=instrument,
        ) as stream:
            async for event in stream:
                if isinstance(event, PartDeltaEvent) and isinstance(event.delta, TextPartDelta):
                    yield event.delta.content_delta


def extract_response_text(response: ModelResponse) -> str:
    """Extract concatenated text parts from a ModelResponse."""
    parts = [p.content for p in response.parts if isinstance(p, TextPart) and p.has_content()]
    return "\n".join(parts)


def extract_response_thinking(response: ModelResponse) -> str | None:
    """Extract concatenated thinking parts from a ModelResponse."""
    thinks = [p.content for p in response.parts if isinstance(p, ThinkingPart) and p.has_content()]
    return "\n\n".join(thinks) if thinks else None


def to_llm_response(response: ModelResponse) -> LLMResponse:
    """Convert a native ModelResponse to an LLMResponse instance."""
    from devops_cli.ai.client.models import LLMResponse

    return LLMResponse.from_model_response(response)


__all__ = [
    "StreamedResponseSync",
    "direct_model_request",
    "direct_model_request_stream",
    "direct_model_request_stream_sync",
    "direct_model_request_sync",
    "extract_response_text",
    "extract_response_thinking",
    "model_request",
    "model_request_stream",
    "model_request_stream_sync",
    "model_request_sync",
    "to_llm_response",
    "to_model_messages",
]
