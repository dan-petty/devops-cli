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
    max_retries: int | None = None
    timestamp: float = field(default_factory=time.monotonic, compare=False)

    @property
    def user(self) -> str:
        """Alias for `prompt` matching chat parameter naming."""
        return self.prompt

    @property
    def system(self) -> str:
        """Alias for `system_prompt` matching chat parameter naming."""
        return self.system_prompt


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


@dataclass
class _FakeConfig:
    """Minimal config double for LLMClient._config compatibility (#1001)."""

    provider: str = "fake"
    model: str = "fake-model"
    get_ollama_urls: list[str] = field(default_factory=lambda: ["http://localhost:11434"])


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
        self._last_answer: AnswerType | None = None
        self._routes: list[tuple[Callable[[str], bool], AnswerType]] = []
        self.sent: list[ModelCall] = []
        self.delay: float = 0.0
        self._preload_results: dict[str, bool] | None = None
        self._preload_calls: list[dict[str, Any]] = []
        self._factory_calls: list[dict[str, Any]] = []
        self._list_models_error: Exception | None = None
        self._config = _FakeConfig(provider=system, model=model_name)

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
    def backend_info(self) -> str:
        """Backend info string for `LLMClient` compatibility."""
        return f"{self.backend_type} ({self.backend_host})"

    @property
    def requested(self) -> list[str]:
        """The prompt text of each recorded call, in invocation order."""
        return [call.prompt for call in self.sent]

    @property
    def call_count(self) -> int:
        """Total number of recorded calls."""
        return len(self.sent)

    @property
    def calls(self) -> list[ModelCall]:
        """Alias for `sent` calls list."""
        return self.sent

    @property
    def factory_calls(self) -> list[dict[str, Any]]:
        """List of calls made to the client factory while this fake was active."""
        return self._factory_calls

    def record_factory_call(self, **kwargs: Any) -> None:
        """Record an invocation of get_llm_client."""
        self._factory_calls.append(kwargs)

    @property
    def preload_calls(self) -> list[dict[str, Any]]:
        """List of calls made to preload_models."""
        return self._preload_calls

    def set_preload_results(self, results: dict[str, bool]) -> None:
        """Configure the mapping returned by preload_models."""
        self._preload_results = dict(results)

    def set_available_models(self, models: Sequence[str]) -> None:
        """Set available model identifiers returned by list_models."""
        self._available_models = list(models)

    def set_list_models_error(self, err: Exception | None) -> None:
        """Configure list_models to raise an error when called."""
        self._list_models_error = err

    def answer(self, *responses: AnswerType) -> None:
        """Enqueue sequential responses; the last one repeats when the queue is exhausted."""
        self._last_answer = None
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
        self._last_answer = None
        self._routes.clear()
        self._preload_calls.clear()
        self._factory_calls.clear()
        self._preload_results = None
        self._list_models_error = None

    def get_context_window(self, model: str | None = None) -> int:
        """Return fake context window token limit for `LLMClient` compatibility."""
        return 128000

    def list_models(self) -> list[str]:
        """Return the sequence of available models."""
        if getattr(self, "_list_models_error", None) is not None:
            raise self._list_models_error
        return list(self._available_models)

    def preload_models(
        self,
        model: str | Sequence[str] | None = None,
        urls: Sequence[str] | None = None,
        keep_alive: str | int | None = None,
        **kwargs: Any,
    ) -> dict[str, bool]:
        """Duck OllamaClient.preload_models returning success or configured results."""
        if getattr(self, "_preload_results", None) is not None:
            self._preload_calls.append(
                {
                    "model": model,
                    "urls": list(urls) if urls else None,
                    "keep_alive": keep_alive,
                    **kwargs,
                }
            )
            return dict(self._preload_results)

        if urls is not None:
            target = list(urls)
        elif isinstance(model, Sequence) and not isinstance(model, str):
            target = list(model)
        elif isinstance(model, str) and not urls:
            target = [model]
        else:
            target = ["http://localhost:11434"]

        self._preload_calls.append(
            {
                "model": model,
                "urls": list(urls) if urls else None,
                "keep_alive": keep_alive,
                **kwargs,
            }
        )
        return {item: True for item in target}

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

    def chat(
        self,
        system_prompt: str = "",
        prompt: str = "",
        *,
        system: str | None = None,
        user: str | None = None,
        max_retries: int | None = None,
        **kwargs: Any,
    ) -> LLMResponse:
        """Execute a synchronous chat completion returning an `LLMResponse`."""
        eff_sys = system if system is not None else system_prompt
        eff_prompt = user if user is not None else prompt
        return self._dispatch_sync(
            prompt=eff_prompt,
            system_prompt=eff_sys,
            messages=(),
            max_retries=max_retries,
            **kwargs,
        )

    def chat_messages(
        self,
        system_prompt: str = "",
        messages: Sequence[Any] = (),
        *,
        system: str | None = None,
        max_retries: int | None = None,
        **kwargs: Any,
    ) -> LLMResponse:
        """Execute a chat completion over a sequence of messages."""
        eff_sys = system if system is not None else system_prompt
        prompt, extracted_sys = _extract_prompt_and_system(messages, system_prompt=eff_sys)
        return self._dispatch_sync(
            prompt=prompt,
            system_prompt=extracted_sys,
            messages=messages,
            max_retries=max_retries,
            **kwargs,
        )

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
        max_retries: int | None = None,
        **kwargs: Any,
    ) -> LLMResponse:
        self._record_call(
            prompt=prompt,
            system_prompt=system_prompt,
            messages=messages,
            stream=False,
            max_retries=max_retries,
            **kwargs,
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
            backend_info=self.backend_info,
        )

    def _record_call(
        self,
        *,
        prompt: str,
        system_prompt: str,
        messages: Sequence[Any],
        stream: bool,
        max_retries: int | None = None,
        **kwargs: Any,
    ) -> None:
        self.sent.append(
            ModelCall(
                prompt=prompt,
                system_prompt=system_prompt,
                messages=tuple(messages),
                model_name=self._model_name,
                stream=stream,
                max_retries=max_retries,
            )
        )

    def _resolve_answer(self, prompt: str) -> ModelAnswer:
        for predicate, candidate in self._routes:
            if predicate(prompt):
                return self._materialize_answer(candidate)

        if self._queue:
            candidate = self._queue.pop(0)
            self._last_answer = candidate
            return self._materialize_answer(candidate)

        if self._last_answer is not None:
            return self._materialize_answer(self._last_answer)

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
