"""In-memory fake for the model and embedding edge (#1001, ADR 0007).

Doubles what devops-cli reaches beyond its process for AI model inference and embeddings:
completion, streaming, token usage, finish reasons, thinking blocks, and embeddings.
Answers sequential responses or routed patterns, records every call, and simulates
errors without opening sockets or making live network requests.
"""

from __future__ import annotations

import hashlib
import math
import re
import time
from collections.abc import AsyncGenerator, Callable, Iterator, Sequence
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Any

from pydantic_ai.messages import (
    FinishReason,
    ModelMessage,
    ModelRequest,
    ModelResponse,
    SystemPromptPart,
    TextPart,
    ThinkingPart,
    UserPromptPart,
)
from pydantic_ai.models import Model, ModelRequestParameters, StreamedResponse
from pydantic_ai.models.test import TestStreamedResponse
from pydantic_ai.settings import ModelSettings
from pydantic_ai.usage import RequestUsage

from devops_cli.ai.client.models import LLMResponse


def deterministic_embedding(text: str, dimension: int = 128) -> list[float]:
    """Generate a deterministic unit-normalized float vector for `text` (#1001)."""
    raw_hash = hashlib.sha256(text.encode("utf-8")).digest()
    components = [float((raw_hash[i % len(raw_hash)] + i) % 100) - 50.0 for i in range(dimension)]
    norm = math.sqrt(sum(component * component for component in components)) or 1.0
    return [round(component / norm, 6) for component in components]


def _extract_part_content(
    part: Any,
    prompts: list[str],
    systems: list[str],
) -> None:
    """Extract prompt or system content from a single message part."""
    if isinstance(part, UserPromptPart):
        content = part.content
        if isinstance(content, str):
            prompts.append(content)
        elif isinstance(content, Sequence):
            prompts.extend(
                str(subpart)
                for subpart in content
                if not getattr(subpart, "kind", None) == "cache_point"
            )
    elif isinstance(part, SystemPromptPart):
        systems.append(part.content)


def _extract_role_content(
    msg: Any,
    prompts: list[str],
    systems: list[str],
) -> None:
    """Extract prompt or system content from an arbitrary role-bearing message."""
    role = str(getattr(msg, "role", "")).lower()
    content = str(getattr(msg, "content", ""))
    if role == "system":
        systems.append(content)
    elif role in ("user", "human"):
        prompts.append(content)


def _extract_prompt_and_system(
    messages: Sequence[Any] | None,
    system_prompt: str = "",
    prompt: str = "",
) -> tuple[str, str]:
    """Extract combined user prompt and system prompt from message collections or strings."""
    if not messages:
        return prompt, system_prompt

    prompts: list[str] = [prompt] if prompt else []
    systems: list[str] = [system_prompt] if system_prompt else []

    for msg in messages:
        if isinstance(msg, ModelRequest):
            for part in msg.parts:
                _extract_part_content(part, prompts, systems)
        else:
            _extract_role_content(msg, prompts, systems)

    return "\n\n".join(filter(None, prompts)), "\n\n".join(filter(None, systems))


@dataclass(frozen=True)
class ModelCall:
    """A recorded invocation of the fake model."""

    prompt: str
    system_prompt: str = ""
    messages: tuple[Any, ...] = ()
    model_name: str = "fake-model"
    stream: bool = False
    timestamp: float = field(default_factory=time.monotonic, compare=False)


@dataclass
class ModelAnswer:
    """A prepared response for the fake model."""

    content: str
    thinking: str | None = None
    finish_reason: FinishReason | None = None
    input_tokens: int = 10
    output_tokens: int = 20


AnswerType = str | ModelAnswer | Exception | type[Exception]
RoutePattern = str | re.Pattern[str] | Callable[[str], bool]


class ModelFake(Model):
    """In-memory fake for model and embedding providers (#1001, ADR 0007).

    Implements pydantic-ai's `Model` interface as well as `LLMClient` verbs
    (`chat`, `chat_messages`, `chat_stream`, `list_models`, `embed`), recording
    every call made and answering from queued responses, routed regex/predicate rules,
    or a default text response.
    """

    __test__ = False  # Avoid pytest collection

    supported_tool_deferral_modes = frozenset({"standalone", "with_tool_search"})
    supported_tool_addition_modes = frozenset({"by_reference", "with_definitions"})

    def __init__(
        self,
        default_response: str = "Fake model response",
        *,
        model_name: str = "fake-model",
        system: str = "fake",
        available_models: Sequence[str] | None = None,
    ) -> None:
        self.default_response = default_response
        self._model_name = model_name
        self._system = system
        self._available_models = list(available_models or [model_name, "test-model"])
        self._queue: list[AnswerType] = []
        self._routes: list[tuple[Callable[[str], bool], AnswerType]] = []
        self.sent: list[ModelCall] = []
        self.delay: float = 0.0

    @property
    def model_name(self) -> str:
        """The model name reported by this fake."""
        return self._model_name

    @property
    def system(self) -> str:
        """The system or provider identifier for this fake."""
        return self._system

    @property
    def model(self) -> str:
        """Alias for `model_name` matching `LLMClient.model`."""
        return self._model_name

    @property
    def backend_type(self) -> str:
        """Backend type string for `LLMClient` compatibility."""
        return "fake"

    @property
    def backend_host(self) -> str:
        """Backend host string for `LLMClient` compatibility."""
        return "localhost"

    @property
    def requested(self) -> list[str]:
        """The prompt text of each recorded call, in invocation order."""
        return [call.prompt for call in self.sent]

    @property
    def call_count(self) -> int:
        """Total number of recorded calls."""
        return len(self.sent)

    def answer(self, *responses: AnswerType) -> None:
        """Enqueue sequential responses; the last one repeats when the queue is exhausted."""
        self._queue.extend(responses)

    def route(self, pattern: RoutePattern, answer: AnswerType) -> None:
        """Route prompts matching `pattern` to `answer`."""
        predicate = self._make_predicate(pattern)
        self._routes.append((predicate, answer))

    def route_error(self, pattern: RoutePattern, exc: Exception | type[Exception]) -> None:
        """Convenience method to route matching prompts to an exception."""
        self.route(pattern, exc)

    def reset(self) -> None:
        """Clear recorded calls, response queue, and custom routes."""
        self.sent.clear()
        self._queue.clear()
        self._routes.clear()

    def get_context_window(self, model: str | None = None) -> int:
        """Return fake context window token limit for `LLMClient` compatibility."""
        return 128000

    def list_models(self) -> list[str]:
        """Return the sequence of available models."""
        return list(self._available_models)

    def preload_models(self, models: list[str] | None = None) -> dict[str, bool]:
        """Duck OllamaClient.preload_models returning success for requested models."""
        target_models = models or [self._model_name]
        return {model: True for model in target_models}

    def chat_structured(
        self,
        system: str = "",
        prompt: str = "",
        schema: type[Any] | None = None,
        **kwargs: Any,
    ) -> Any:
        """Duck structured client completion returning parsed model or schema instance."""
        self._record_call(prompt=prompt, system_prompt=system, messages=(), stream=False)
        answer = self._resolve_answer(prompt)
        if schema is not None:
            if isinstance(answer, schema):
                return answer
            if isinstance(answer.content, schema):
                return answer.content
            if isinstance(answer.content, str):
                import json

                try:
                    if hasattr(schema, "model_validate_json"):
                        return schema.model_validate_json(answer.content)
                    if hasattr(schema, "model_validate"):
                        return schema.model_validate(json.loads(answer.content))
                except Exception:
                    pass
        return answer.content

    def embed(self, texts: str | Sequence[str], dimension: int = 128) -> list[list[float]]:
        """Return deterministic unit embeddings for the given text or sequence of texts."""
        text_list = [texts] if isinstance(texts, str) else list(texts)
        return [deterministic_embedding(item, dimension=dimension) for item in text_list]

    def chat(self, system_prompt: str = "", prompt: str = "", **kwargs: Any) -> LLMResponse:
        """Execute a synchronous chat completion returning an `LLMResponse`."""
        return self._dispatch_sync(prompt=prompt, system_prompt=system_prompt, messages=())

    def chat_messages(
        self, system_prompt: str = "", messages: Sequence[Any] = (), **kwargs: Any
    ) -> LLMResponse:
        """Execute a chat completion over a sequence of messages."""
        prompt, extracted_sys = _extract_prompt_and_system(messages, system_prompt=system_prompt)
        return self._dispatch_sync(prompt=prompt, system_prompt=extracted_sys, messages=messages)

    def chat_stream(
        self, system_prompt: str = "", prompt: str = "", **kwargs: Any
    ) -> Iterator[str]:
        """Stream response tokens synchronously."""
        self._record_call(prompt=prompt, system_prompt=system_prompt, messages=(), stream=True)
        answer = self._resolve_answer(prompt)
        words = answer.content.split(" ")
        for i, word in enumerate(words):
            yield word if i == len(words) - 1 else f"{word} "

    def chat_messages_stream(
        self, system_prompt: str = "", messages: Sequence[Any] = (), **kwargs: Any
    ) -> Iterator[str]:
        """Stream response tokens synchronously over a sequence of messages."""
        prompt, extracted_sys = _extract_prompt_and_system(messages, system_prompt=system_prompt)
        self._record_call(
            prompt=prompt, system_prompt=extracted_sys, messages=messages, stream=True
        )
        answer = self._resolve_answer(prompt)
        words = answer.content.split(" ")
        for i, word in enumerate(words):
            yield word if i == len(words) - 1 else f"{word} "

    async def request(
        self,
        messages: list[ModelMessage],
        model_settings: ModelSettings | None = None,
        model_request_parameters: ModelRequestParameters | None = None,
    ) -> ModelResponse:
        """Execute a direct model request per the Pydantic AI `Model` interface."""
        prompt, system_prompt = _extract_prompt_and_system(messages)
        self._record_call(
            prompt=prompt, system_prompt=system_prompt, messages=messages, stream=False
        )
        answer = self._resolve_answer(prompt)
        parts: list[Any] = []
        if answer.thinking:
            parts.append(ThinkingPart(content=answer.thinking))
        parts.append(TextPart(content=answer.content))
        usage = RequestUsage(
            input_tokens=answer.input_tokens,
            output_tokens=answer.output_tokens,
        )
        return ModelResponse(
            parts=parts,
            model_name=self._model_name,
            usage=usage,
            finish_reason=answer.finish_reason,
        )

    @asynccontextmanager
    async def request_stream(
        self,
        messages: list[ModelMessage],
        model_settings: ModelSettings | None = None,
        model_request_parameters: ModelRequestParameters | None = None,
        run_context: Any = None,
    ) -> AsyncGenerator[StreamedResponse]:
        """Stream a direct model request per the Pydantic AI `Model` interface."""
        prompt, system_prompt = _extract_prompt_and_system(messages)
        self._record_call(
            prompt=prompt, system_prompt=system_prompt, messages=messages, stream=True
        )
        answer = self._resolve_answer(prompt)
        params = model_request_parameters or ModelRequestParameters()
        parts: list[Any] = []
        if answer.thinking:
            parts.append(ThinkingPart(content=answer.thinking))
        parts.append(TextPart(content=answer.content))
        usage = RequestUsage(
            input_tokens=answer.input_tokens,
            output_tokens=answer.output_tokens,
        )
        structured_response = ModelResponse(
            parts=parts,
            model_name=self._model_name,
            usage=usage,
            finish_reason=answer.finish_reason,
        )
        yield TestStreamedResponse(
            model_request_parameters=params,
            _model_name=self._model_name,
            _structured_response=structured_response,
            _messages=messages,
            _provider_name=self._system,
        )

    def _dispatch_sync(
        self,
        *,
        prompt: str,
        system_prompt: str,
        messages: Sequence[Any],
    ) -> LLMResponse:
        self._record_call(
            prompt=prompt, system_prompt=system_prompt, messages=messages, stream=False
        )
        answer = self._resolve_answer(prompt)
        return LLMResponse(
            content=answer.content,
            thinking=answer.thinking,
            prompt_tokens=answer.input_tokens,
            completion_tokens=answer.output_tokens,
            total_tokens=answer.input_tokens + answer.output_tokens,
            finish_reason=answer.finish_reason,
            model=self._model_name,
        )

    def _record_call(
        self,
        *,
        prompt: str,
        system_prompt: str,
        messages: Sequence[Any],
        stream: bool,
    ) -> None:
        self.sent.append(
            ModelCall(
                prompt=prompt,
                system_prompt=system_prompt,
                messages=tuple(messages),
                model_name=self._model_name,
                stream=stream,
            )
        )

    def _resolve_answer(self, prompt: str) -> ModelAnswer:
        for predicate, candidate in self._routes:
            if predicate(prompt):
                return self._materialize_answer(candidate)

        if self._queue:
            candidate = self._queue.pop(0) if len(self._queue) > 1 else self._queue[0]
            return self._materialize_answer(candidate)

        return ModelAnswer(content=self.default_response)

    def _materialize_answer(self, candidate: AnswerType) -> ModelAnswer:
        if isinstance(candidate, type) and issubclass(candidate, Exception):
            raise candidate("Model error")
        if isinstance(candidate, Exception):
            raise candidate
        if isinstance(candidate, str):
            return ModelAnswer(content=candidate)
        return candidate

    @staticmethod
    def _make_predicate(pattern: RoutePattern) -> Callable[[str], bool]:
        if callable(pattern):
            return pattern
        if isinstance(pattern, re.Pattern):
            return lambda text: bool(pattern.search(text))
        return lambda text: pattern in text
