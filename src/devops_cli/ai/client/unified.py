"""Unified AI client orchestrating provider backends, response cache, and telemetry."""

from __future__ import annotations

import logging
import time
from collections.abc import Callable, Generator
from functools import cached_property
from typing import TYPE_CHECKING, Any

import httpx2

from devops_cli.ai.client import network
from devops_cli.ai.client.claude import ClaudeProviderMixin
from devops_cli.ai.client.models import (
    AIClientError,
    AICredentialsError,
    LLMResponse,
    ReplyRejectedError,
    RequestPriority,
    _is_json_error_payload,
    genai_provider_name,
    origin_label,
    origin_span_attributes,
)
from devops_cli.ai.client.network import validate_base_url
from devops_cli.ai.client.ollama import OllamaProviderMixin
from devops_cli.ai.client.openai import OpenAICompatProviderMixin
from devops_cli.ai.client.structured import StructuredOutputMixin
from devops_cli.ai.client.style_request import with_style_request
from devops_cli.ai.thinking_stream import strip_think_blocks
from devops_cli.config.constants import (
    CONST_AI_BACKEND_HOST_UNKNOWN,
    CONST_AI_GATEWAY_PROVIDER,
    CONST_FINISH_REASON_ERROR,
    CONST_OTEL_SPAN_KIND_CLIENT,
    CONST_RESPONSE_CACHE_SERVER,
    CONST_UNCACHED_FINISH_REASONS,
    CONST_URL_ANTHROPIC_API_BASE,
    CONST_URL_GITHUB_COPILOT_API_BASE,
)
from devops_cli.config.defaults import (
    DEFAULT_AI_CONNECT_TIMEOUT_SECONDS,
    DEFAULT_HTTP_TIMEOUT_SECONDS,
)
from devops_cli.config.settings import AIConfig
from devops_cli.exceptions import ConfigurationError
from devops_cli.exceptions.ai import LLMInferenceError
from devops_cli.http.client import request_timeout
from devops_cli.http.urls import get_url_origin
from devops_cli.models.ai import ChatMessage
from devops_cli.telemetry import get_tracer, trace_span
from devops_cli.telemetry.instruments import AI_CHAT_DURATION, emit

if TYPE_CHECKING:
    from pydantic_ai.messages import FinishReason

logger = logging.getLogger(__name__)


def _set_timing_span_attributes(span_handle: Any, res: LLMResponse) -> None:
    """Set latency, duration, and token rate attributes on response span."""
    if res.eval_duration_ms is not None:
        span_handle.set_attribute("llm.eval_duration_ms", res.eval_duration_ms)
        if res.completion_tokens and res.eval_duration_ms > 0:
            tok_rate = round(res.completion_tokens / (res.eval_duration_ms / 1000.0), 2)
            span_handle.set_attribute("llm.tokens_per_second", tok_rate)
    elif res.wall_seconds and res.wall_seconds > 0 and res.completion_tokens:
        tok_rate = round(res.completion_tokens / res.wall_seconds, 2)
        span_handle.set_attribute("llm.tokens_per_second", tok_rate)
    if res.prompt_eval_duration_ms is not None:
        span_handle.set_attribute("llm.prompt_eval_duration_ms", res.prompt_eval_duration_ms)
    if res.processing_seconds is not None:
        span_handle.set_attribute("llm.processing_seconds", res.processing_seconds)
    if res.wall_seconds is not None:
        span_handle.set_attribute("llm.wall_seconds", res.wall_seconds)


def _set_finish_reason_attribute(span_handle: Any, reason: FinishReason | None) -> None:
    """Name why the reply ended; an unknown reason sets nothing, as truncation is never guessed."""
    if reason is not None:
        span_handle.set_attribute("gen_ai.response.finish_reasons", [reason])


def _set_stream_sanitizer_attributes(span_handle: Any, processor: Any) -> None:
    """Record sanitizer telemetry metrics on the active stream trace span."""
    span_handle.set_attribute("llm.stream.unopened_close_tags", processor.unopened_close_tags)
    span_handle.set_attribute("llm.stream.unclosed_stream", processor.unclosed_stream)
    span_handle.set_attribute(
        "llm.stream.discarded_thought_chars", processor.discarded_thought_chars
    )


def _response_event_payload(res: LLMResponse, p: str) -> dict[str, Any]:
    """The `llm_response_received` event's summary of a reply."""
    event_payload: dict[str, Any] = {
        "total_tokens": res.total_tokens or 0,
        "wall_seconds": res.wall_seconds or 0.0,
        "backend": res.backend_info or p,
    }
    if getattr(res, "served_by", None):
        event_payload["served_by"] = res.served_by
    if getattr(res, "model", None):
        event_payload["model"] = res.model
    return event_payload


def _set_response_span_attributes(
    span_handle: Any, res: LLMResponse, p: str, configured: httpx2.Origin | None = None
) -> None:
    """Set the reply's GenAI attributes on the `ai.llm.dispatch` inference span.

    This is the only writer of the usage and response model keys, so a request's tokens are
    counted once, on the span that made it. The server is the reply's origin, else
    ``configured``, the one origin that the client is configured with.
    """
    for key, value in origin_span_attributes(res.origin or configured).items():
        span_handle.set_attribute(key, value)
    if getattr(res, "served_by", None):
        span_handle.set_attribute("llm.served_by", res.served_by)
    response_model = getattr(res, "served_model", None) or getattr(res, "model", None)
    if response_model:
        span_handle.set_attribute("gen_ai.response.model", response_model)
    if res.prompt_tokens is not None:
        span_handle.set_attribute("gen_ai.usage.input_tokens", res.prompt_tokens)
    if res.completion_tokens is not None:
        span_handle.set_attribute("gen_ai.usage.output_tokens", res.completion_tokens)
    if getattr(res, "reasoning_tokens", None) is not None:
        span_handle.set_attribute("gen_ai.usage.reasoning.output_tokens", res.reasoning_tokens)
    _set_timing_span_attributes(span_handle, res)
    _set_finish_reason_attribute(span_handle, res.finish_reason)
    if get_tracer().capture_llm_content:
        span_handle.set_attribute("llm.response_preview", res.text[:200].replace("\n", " ").strip())
    span_handle.set_attribute("llm.response.thinking", bool(res.thinking))
    span_handle.add_event("llm_response_received", _response_event_payload(res, p))


def _resolve_llm_cache(config: AIConfig | None, cache_enabled: bool | None) -> Any:
    """The shared response cache, or a disabled one when `cache_enabled` or the client's
    `ai.cache.enabled` turns it off. Its other values come from the settings (#2447)."""
    from devops_cli.ai.response_cache import LLMResponseCache, get_llm_response_cache

    if cache_enabled is None and config is not None:
        cache_enabled = config.cache.enabled
    if cache_enabled is False:
        return LLMResponseCache(enabled=False)
    return get_llm_response_cache()


class LLMClient(
    OllamaProviderMixin,
    ClaudeProviderMixin,
    OpenAICompatProviderMixin,
    StructuredOutputMixin,
):
    """Unified client for interacting with AI models across different providers."""

    @classmethod
    def _load_and_increment_rr_index(cls, n: int) -> int:
        return network.load_and_increment_rr_index(n)

    @classmethod
    def _track_ollama_url(cls, url: str, max_parallel: int = 2) -> Any:
        return network.track_ollama_url(url, max_parallel)

    def __init__(
        self,
        config: AIConfig | None = None,
        api_key: str | None = None,
        *,
        custom_endpoint: str | None = None,
        request_timeout_seconds: float | None = None,
        cache_enabled: bool | None = None,
        append_cache: bool | None = None,
        transport: httpx2.BaseTransport | None = None,
        http_client: httpx2.Client | None = None,
    ) -> None:
        if config is None:
            from devops_cli.config.settings import get_ai_api_key, load_settings

            settings = load_settings()
            config = settings.ai
            if not api_key:
                api_key = get_ai_api_key(settings)

        self._config = config
        self._validate_resolved_config(self._config)
        self._api_key = api_key or getattr(config, "api_key", None) or ""
        self._custom_endpoint = custom_endpoint
        self._request_timeout_seconds = request_timeout_seconds

        self._cache = _resolve_llm_cache(config, cache_enabled)
        if append_cache is None:
            cache_config = getattr(config, "cache", None)
            append_cache = (
                getattr(cache_config, "append_cache", False) if cache_config is not None else False
            )
        self._append_cache = bool(append_cache)
        self._transport = transport
        self._http_client = http_client
        self._transport_client: httpx2.Client | None = None

    @staticmethod
    def _validate_resolved_config(cfg: AIConfig) -> None:
        """Ensure resolved configuration does not contain disallowed options for the provider."""
        if cfg.provider == "claude" and not (cfg.model and cfg.model.strip()):
            task_label = f"task '{cfg.task_name}'" if cfg.task_name else "task"
            key = f"ai.tasks.{cfg.task_name}.model" if cfg.task_name else "ai.model"
            raise ConfigurationError(
                f"The {task_label} requires a configured model for provider 'claude'. "
                f"Set ai.model or configure ai.tasks.{cfg.task_name}.model.",
                key=key,
            )
        if cfg.num_ctx is not None and cfg.provider in (
            CONST_AI_GATEWAY_PROVIDER,
            "gateway",
            "openai",
            "copilot",
        ):
            task_label = f"task '{cfg.task_name}'" if cfg.task_name else "task"
            key = f"ai.tasks.{cfg.task_name}.num_ctx" if cfg.task_name else "ai.num_ctx"
            raise ConfigurationError(
                f"The {task_label} cannot set num_ctx on provider '{cfg.provider}'. "
                f"The server's context comes from the tier's OLLAMA_CONTEXT_LENGTH, and "
                f"context_window sizes pages.",
                key=key,
            )

    @property
    def cache(self) -> Any:
        """Return the underlying LLM response cache instance."""
        return self._cache

    def _connection_error(self, exc: Exception) -> AIClientError:
        """The error for a provider that cannot be reached; `timed_out` says the cause was a
        timeout (#2562)."""
        return AIClientError(
            self._unreachable_message(), timed_out=isinstance(exc, httpx2.TimeoutException)
        )

    def _unreachable_message(self) -> str:
        provider = self._config.provider
        if provider == "ollama":
            return "Cannot connect to Ollama. Start Ollama, or run: devops ai config --provider ollama --ollama-urls <urls>"
        if provider == "claude":
            return "Cannot connect to Claude API. Check network access and api_base_url (devops ai config --provider claude --api-base-url <url>)."
        return "Cannot connect to AI provider API. Check network access, api_base_url, and API key."

    @property
    def backend_type(self) -> str:
        """Return the AI provider backend type (e.g. ollama, claude, copilot, openai)."""
        p = getattr(self._config, "provider", "ollama")
        return str(p or "ollama")

    def _configured_urls(self) -> list[str]:
        """The endpoint URLs that the configuration gives the current provider."""
        p = str(getattr(self._config, "provider", "ollama") or "ollama")
        if p == "ollama":
            urls = getattr(self._config, "get_ollama_urls", [])
            if not isinstance(urls, (list, tuple)):
                return []
            return [u for u in urls if isinstance(u, str) and u]
        base_url = getattr(self._config, "api_base_url", None) if p != "gateway" else None
        if not isinstance(base_url, str) or not base_url:
            if p == "openai":
                base_url = str(self._openai_client().base_url)
            else:
                provider_defaults = {
                    "claude": CONST_URL_ANTHROPIC_API_BASE,
                    "copilot": CONST_URL_GITHUB_COPILOT_API_BASE,
                    "gateway": getattr(self._config, "gateway_url", None),
                }
                base_url = provider_defaults.get(p)
        return [base_url] if isinstance(base_url, str) and base_url else []

    @cached_property
    def _configured_origins(self) -> tuple[httpx2.Origin | None, ...]:
        """The origin of each configured endpoint URL, read once; None for a URL with none."""
        return tuple(get_url_origin(url) for url in self._configured_urls())

    @property
    def _configured_origin(self) -> httpx2.Origin | None:
        """The origin of the one configured endpoint; None when there are several or none."""
        origins = self._configured_origins
        return origins[0] if len(origins) == 1 else None

    @property
    def backend_host(self) -> str:
        """The `host[:port]` text of each configured endpoint, joined with ", ".

        It holds no userinfo. An endpoint URL with no origin shows as `unknown`, and an Ollama
        provider with no URL as `unconfigured`.
        """
        labels = [
            origin_label(origin) if origin is not None else CONST_AI_BACKEND_HOST_UNKNOWN
            for origin in self._configured_origins
        ]
        if labels:
            return ", ".join(labels)
        if str(getattr(self._config, "provider", "ollama") or "ollama") == "ollama":
            return "unconfigured"
        return CONST_AI_BACKEND_HOST_UNKNOWN

    @property
    def backend_info(self) -> str:
        """Return formatted backend type and host string, e.g. 'ollama (localhost:11434)'."""
        return f"{self.backend_type} ({self.backend_host})"

    @property
    def model(self) -> str:
        """Return the active AI model identifier."""
        return str(getattr(self._config, "model", "") or "")

    def get_context_window(self, task: str | None = None) -> int:
        """Return the effective token context window for the configured model/task."""
        cfg = self._config.for_task(task) if task else self._config
        self._validate_resolved_config(cfg)
        return int(cfg.num_ctx or cfg.context_window)

    @staticmethod
    def _strip_think_blocks(text: str) -> str:
        """Remove <think>...</think> chain-of-thought blocks emitted by thinking models."""
        return strip_think_blocks(text)

    @staticmethod
    def _validate_response_text(
        content: str | LLMResponse,
        validator: Callable[[str], bool] | None = None,
    ) -> bool:
        """Quick and effective validation of AI response content."""
        raw_str = (content.content if isinstance(content, LLMResponse) else str(content)).strip()
        thinking_val = getattr(content, "thinking", None)
        if not raw_str and not (thinking_val and str(thinking_val).strip()):
            return False
        if raw_str and _is_json_error_payload(raw_str):
            return False

        if validator is not None:
            try:
                return bool(validator(raw_str))
            except Exception:
                return False
        return True

    def _request_timeout(self) -> httpx2.Timeout:
        """The caller's timeout, else the task's configured `timeout`, else the HTTP default."""
        return request_timeout(
            read=(
                self._request_timeout_seconds
                or self._config.timeout
                or DEFAULT_HTTP_TIMEOUT_SECONDS
            ),
            connect=DEFAULT_AI_CONNECT_TIMEOUT_SECONDS,
        )

    def _validate_base_url(self, base_url: str, purpose: str = "API") -> str:
        return validate_base_url(
            base_url, purpose=purpose, allow_private_network=self._config.allow_private_network
        )

    def _dispatch_messages(
        self,
        system: str,
        messages: list[ChatMessage],
        *,
        enable_thinking: bool = True,
        priority: RequestPriority | str | None = None,
    ) -> LLMResponse:
        p = self._config.provider
        start = time.perf_counter()
        prompt_preview = ""
        for m in reversed(messages):
            if m.role == "user":
                prompt_preview = m.content[:200].replace("\n", " ").strip()
                break

        resolved_priority = (
            RequestPriority(priority)
            if isinstance(priority, str)
            else (priority or network.current_request_priority.get())
        )

        dispatch_attrs: dict[str, Any] = {
            "gen_ai.operation.name": "chat",
            "gen_ai.provider.name": genai_provider_name(p),
            "gen_ai.request.model": self._config.model,
            "llm.request.message_count": len(messages),
            "llm.request.system_prompt_length": len(system),
            "llm.request.enable_thinking": enable_thinking,
            "llm.request.priority": resolved_priority.value,
            "provider": p,
            "model": self._config.model,
        }
        if get_tracer().capture_llm_content:
            dispatch_attrs["llm.prompt_preview"] = prompt_preview
        if getattr(self._config, "temperature", None) is not None:
            dispatch_attrs["gen_ai.request.temperature"] = self._config.temperature
        if getattr(self._config, "top_p", None) is not None:
            dispatch_attrs["gen_ai.request.top_p"] = self._config.top_p

        with (
            network.model_call_slot(),
            trace_span(
                "ai.llm.dispatch", dispatch_attrs, kind=CONST_OTEL_SPAN_KIND_CLIENT
            ) as span_handle,
            network.bind_dispatch_context(
                provider=p,
                model=self._config.model,
                request_type="chat_dispatch",
                task_name=getattr(self._config, "task_name", None),
                server=self.backend_host,
                backend_info=self.backend_info,
            ),
        ):
            res = self._invoke_provider_messages(
                p, system, messages, enable_thinking, resolved_priority
            )
            duration = time.perf_counter() - start
            self._record_response_telemetry_and_spend(
                span_handle, res, p, messages, system, duration
            )

        duration = time.perf_counter() - start
        emit(AI_CHAT_DURATION, duration, {"provider": p, "model": self._config.model})
        return res

    def _invoke_provider_messages(
        self,
        p: str,
        system: str,
        messages: list[ChatMessage],
        enable_thinking: bool,
        resolved_priority: RequestPriority,
    ) -> LLMResponse:
        """Dispatch messages to configured provider driver."""
        if p == "ollama":
            return self._ollama_messages(
                system, messages, enable_thinking=enable_thinking, priority=resolved_priority
            )
        if p == "claude":
            return self._claude_messages(system, messages, enable_thinking=enable_thinking)
        if p in ("copilot", "github_copilot", "openai", "gateway"):
            return self._openai_compat_messages(system, messages, enable_thinking=enable_thinking)
        raise LLMInferenceError(
            f"Unknown provider: {p!r}. Choose: ollama, claude, copilot, openai, gateway",
            provider=p,
        )

    def _record_response_telemetry_and_spend(
        self,
        span_handle: Any,
        res: LLMResponse,
        p: str,
        messages: list[ChatMessage],
        system: str,
        duration: float,
    ) -> None:
        """Record response attributes, spend calculation, and OpenTelemetry metrics.

        The server is the reply's origin. A reply with no origin, such as one from an adapter
        that sets none, names the configured endpoints.
        """
        _set_response_span_attributes(span_handle, res, p, self._configured_origin)
        srv = origin_label(res.origin) if res.origin is not None else self.backend_host
        from devops_cli.ai.context_budget import count_tokens
        from devops_cli.ai.spend import resolve_spend_stage, track_request_spend

        p_tokens = (
            res.prompt_tokens
            if res.prompt_tokens is not None
            else sum(count_tokens(m.content) for m in messages)
            + (count_tokens(system) if system else 0)
        )
        c_tokens = (
            res.completion_tokens if res.completion_tokens is not None else count_tokens(res.text)
        )
        r_tokens = (
            res.reasoning_tokens
            if res.reasoning_tokens is not None
            else (count_tokens(res.thinking) if res.thinking else 0)
        )
        resolved_served_model = getattr(res, "served_model", None)
        if (
            not resolved_served_model
            and getattr(res, "model", None)
            and res.model != self._config.model
        ):
            resolved_served_model = res.model
        rec = track_request_spend(
            provider=p,
            model=self._config.model,
            server=srv,
            backend_info=res.backend_info or self.backend_info,
            served_by=getattr(res, "served_by", None),
            served_model=resolved_served_model,
            prompt_tokens=p_tokens,
            completion_tokens=c_tokens,
            cached=res.cached,
            request_type="chat_dispatch",
            duration_seconds=res.wall_seconds or duration,
            stage=resolve_spend_stage(None, getattr(self._config, "task_name", None)),
            finish_reason=res.finish_reason,
            reasoning_tokens=r_tokens,
        )
        if rec is not None:
            span_handle.set_attribute("llm.usage.cost_usd", rec.cost_usd)

    def chat(
        self,
        system: str,
        user: str,
        *,
        enable_thinking: bool = True,
        validator: Callable[[str], bool] | None = None,
        max_retries: int | None = None,
        use_cache: bool = True,
        starting_point: str | None = None,
        context_tag: str | None = None,
        append_cache: bool | None = None,
        priority: RequestPriority | str | None = RequestPriority.HIGH,
        **kwargs: Any,
    ) -> LLMResponse:
        """Send a single-turn chat message and return the assistant reply."""
        return self.chat_messages(
            system,
            [ChatMessage(role="user", content=user)],
            enable_thinking=enable_thinking,
            validator=validator,
            max_retries=max_retries,
            use_cache=use_cache,
            starting_point=starting_point,
            context_tag=context_tag,
            append_cache=append_cache,
            priority=priority,
            **kwargs,
        )

    def _record_chat_telemetry(self, span_h: Any, res: LLMResponse) -> None:
        """Record cache and timing on the `ai.llm.chat` wrapper span.

        Usage and the response model stay on the `ai.llm.dispatch` span below it, so a
        request's tokens are counted once.
        """
        span_h.set_attribute("llm.cached", res.cached)
        span_h.set_attribute("llm.processing_seconds", res.processing_seconds)
        span_h.set_attribute("llm.wall_seconds", res.wall_seconds)

    def _cache_chat_entry(
        self,
        cache_key: str,
        system: str,
        out_messages: list[ChatMessage],
        res: LLMResponse,
        context_tag: str | None,
    ) -> None:
        """Store validated response in cache."""
        prompt_preview = ""
        for m in reversed(out_messages):
            if m.role == "user":
                prompt_preview = m.content[:200]
                break
        self._cache.set(
            key=cache_key,
            provider=self._config.provider,
            model=self._config.model,
            system=system,
            prompt=prompt_preview,
            content=str(res),
            thinking=getattr(res, "thinking", None),
            context_tag=context_tag,
            wall_seconds=getattr(res, "wall_seconds", 0.0),
            backend_info=getattr(res, "backend_info", None),
            served_by=getattr(res, "served_by", None),
            response_model=getattr(res, "model", None),
            tokens={
                "prompt": getattr(res, "prompt_tokens", None),
                "completion": getattr(res, "completion_tokens", None),
                "total": getattr(res, "total_tokens", None),
            },
        )

    def _augment_messages(
        self, messages: list[ChatMessage], starting_point: str | None
    ) -> list[ChatMessage]:
        """Augment last user message with starting point if provided."""
        out = list(messages)
        if not starting_point:
            return out
        for idx in reversed(range(len(out))):
            if out[idx].role == "user":
                augmented = self._cache.format_starting_point_prompt(
                    out[idx].content, starting_point
                )
                out[idx] = ChatMessage(role="user", content=augmented)
                break
        return out

    def _check_chat_cache(
        self,
        cache_key: str,
        validator: Callable[[str], bool] | None,
        span_h: Any,
    ) -> LLMResponse | None:
        """Check cache for existing valid response."""
        cached_entry = self._cache.get(cache_key)
        if cached_entry is None:
            return None
        if not self._validate_response_text(cached_entry.content, validator):
            self._cache.delete(cache_key)
            return None
        span_h.set_attribute("llm.cached", True)
        span_h.set_attribute("llm.wall_seconds", 0.0)
        return LLMResponse(
            cached_entry.content,
            processing_seconds=0.0,
            wall_seconds=0.0,
            backend_info=CONST_RESPONSE_CACHE_SERVER,
            thinking=cached_entry.thinking,
            cached=True,
            served_by=cached_entry.served_by,
            model=cached_entry.response_model,
        )

    def _record_cache_hit(self) -> None:
        """Record a reply the response cache answered as one cached request.

        No model processed it, so it carries no tokens and no cost, and names the cache as its
        server. The dispatch recorder is not reused: it would estimate the missing tokens.
        """
        from devops_cli.ai.spend import resolve_spend_stage, track_request_spend

        track_request_spend(
            provider=self._config.provider,
            model=self._config.model,
            server=CONST_RESPONSE_CACHE_SERVER,
            backend_info=CONST_RESPONSE_CACHE_SERVER,
            prompt_tokens=0,
            completion_tokens=0,
            cached=True,
            request_type="chat_cache_hit",
            stage=resolve_spend_stage(None, getattr(self._config, "task_name", None)),
        )

    def _handle_successful_chat_dispatch(
        self,
        res: LLMResponse,
        cache_key: str,
        system: str,
        out_messages: list[ChatMessage],
        use_cache: bool,
        context_tag: str | None,
        span_h: Any,
    ) -> LLMResponse:
        """Record telemetry, optionally cache successful response, and return.

        A reply cut at its cap, filtered or failed is returned but never cached, so the next
        identical call reaches the provider again rather than the cut reply.
        """
        self._record_chat_telemetry(span_h, res)
        if (
            use_cache
            and res.finish_reason not in CONST_UNCACHED_FINISH_REASONS
            and bool(res.content and res.content.strip())
        ):
            self._cache_chat_entry(cache_key, system, out_messages, res, context_tag)
        return res

    def _rejection(self, res: LLMResponse, attempt: int, attempts: int) -> AIClientError:
        """The error for a reply that failed validation, which is never cached.

        A reply the caller's validator refused comes back on `ReplyRejectedError`, so a caller
        can reflect on it. An empty reply or a provider's error payload never reached the
        validator, so it stays a plain `AIClientError`.
        """
        model = self._config.model
        msg = f"Response validation failed for model '{model}' (attempt {attempt}/{attempts})."
        if self._validate_response_text(res):
            return ReplyRejectedError(msg, reply=res)
        return AIClientError(msg)

    def _retry_chat_dispatch(
        self,
        system: str,
        out_messages: list[ChatMessage],
        cache_key: str,
        validator: Callable[[str], bool] | None,
        attempts: int,
        use_cache: bool,
        enable_thinking: bool,
        context_tag: str | None,
        span_h: Any,
        priority: RequestPriority | str | None = None,
    ) -> LLMResponse:
        """Execute chat dispatch across retries with validation and error tracking."""
        last_exc: Exception | None = None
        for attempt in range(1, attempts + 1):
            try:
                res = self._dispatch_messages(
                    system,
                    out_messages,
                    enable_thinking=enable_thinking,
                    priority=priority,
                )
                if not self._validate_response_text(res, validator):
                    last_exc = self._rejection(res, attempt, attempts)
                    continue
                return self._handle_successful_chat_dispatch(
                    res, cache_key, system, out_messages, use_cache, context_tag, span_h
                )
            except AICredentialsError as exc:
                # Retrying cannot fix missing or rejected credentials.
                span_h.record_exception(exc)
                raise
            except AIClientError as exc:
                # The HTTP transport is the single retry layer; do not retry dispatch exceptions.
                span_h.record_exception(exc)
                raise
            except httpx2.TransportError as exc:
                err = self._connection_error(exc)
                span_h.record_exception(err)
                raise err from exc
            except Exception as exc:
                err = AIClientError(f"{type(exc).__name__}: {exc}")
                span_h.record_exception(err)
                raise err from exc

        if isinstance(last_exc, AIClientError):
            span_h.record_exception(last_exc)
            raise last_exc
        if isinstance(last_exc, httpx2.TransportError):
            err = self._connection_error(last_exc)
            span_h.record_exception(err)
            raise err
        if last_exc is not None:
            err = AIClientError(f"{type(last_exc).__name__}: {last_exc}")
            span_h.record_exception(err)
            raise err
        fallback_err = AIClientError("AI request failed with no valid response.")
        span_h.record_exception(fallback_err)
        raise fallback_err

    def chat_messages(
        self,
        system: str = "",
        messages: list[ChatMessage] | None = None,
        *,
        system_prompt: str | None = None,
        enable_thinking: bool = True,
        validator: Callable[[str], bool] | None = None,
        max_retries: int | None = None,
        use_cache: bool = True,
        starting_point: str | None = None,
        context_tag: str | None = None,
        append_cache: bool | None = None,
        priority: RequestPriority | str | None = None,
        **kwargs: Any,
    ) -> LLMResponse:
        """Send a multi-turn chat request with response validation, caching, and retries.

        The style request joins `system` first, so the cache key holds the system prompt as sent.
        """
        if system_prompt and not system:
            system = system_prompt
        system = with_style_request(system)
        eff_messages = list(messages) if messages is not None else []
        eff_append = self._append_cache if append_cache is None else append_cache
        eff_start = starting_point
        if eff_start is None and context_tag:
            eff_start = self._cache.get_starting_point(context_tag=context_tag)

        resolved_p = (
            RequestPriority(priority)
            if isinstance(priority, str)
            else (priority or network.current_request_priority.get())
        )

        cache_opts = {
            "enable_thinking": enable_thinking,
            "temperature": (
                None
                if (
                    getattr(self._config, "use_model_sampling", False)
                    or getattr(self._config, "supports_reasoning", False)
                )
                else getattr(self._config, "temperature", None)
            ),
            "top_p": (
                None
                if (
                    getattr(self._config, "use_model_sampling", False)
                    or getattr(self._config, "supports_reasoning", False)
                )
                else getattr(self._config, "top_p", None)
            ),
            "reasoning_effort": (
                getattr(self._config, "reasoning_effort", None)
                if getattr(self._config, "supports_reasoning", False)
                else None
            ),
            "max_tokens": self._completion_limit(),
        }

        if eff_append and eff_start is None and use_cache:
            unaugmented_key = self._cache.generate_key(
                provider=str(getattr(self._config, "provider", "ollama")),
                model=str(getattr(self._config, "model", "default")),
                system=system,
                messages_or_prompt=eff_messages,
                options=cache_opts,
            )
            cached_candidate = self._cache.get(unaugmented_key)
            if cached_candidate is not None:
                eff_start = cached_candidate.content

        out_messages = self._augment_messages(eff_messages, eff_start)
        cache_key = self._cache.generate_key(
            provider=str(getattr(self._config, "provider", "ollama")),
            model=str(getattr(self._config, "model", "default")),
            system=system,
            messages_or_prompt=out_messages,
            options=cache_opts,
        )

        with trace_span(
            "ai.llm.chat",
            attributes={
                "gen_ai.provider.name": genai_provider_name(self._config.provider),
                "gen_ai.request.model": self._config.model,
                "llm.request.priority": resolved_p.value,
                "llm.request.enable_thinking": enable_thinking,
                "use_cache": use_cache,
                "append_cache": eff_append,
            },
        ) as span_h:
            if use_cache and not eff_start and not eff_append:
                hit = self._check_chat_cache(cache_key, validator, span_h)
                if hit is not None:
                    self._record_cache_hit()
                    return hit

            retries = max_retries if max_retries is not None else self._config.max_retries
            return self._retry_chat_dispatch(
                system=system,
                out_messages=out_messages,
                cache_key=cache_key,
                validator=validator,
                attempts=max(1, retries + 1),
                use_cache=use_cache,
                enable_thinking=enable_thinking,
                context_tag=context_tag,
                span_h=span_h,
                priority=resolved_p,
            )

    def _dispatch_stream(
        self,
        system: str,
        messages: list[ChatMessage],
        *,
        enable_thinking: bool = True,
        priority: RequestPriority | str | None = None,
    ) -> Generator[str]:
        """Dispatch streaming request to appropriate provider handler."""
        p = self._config.provider
        if p == "ollama":
            return self._ollama_stream(
                system, messages, enable_thinking=enable_thinking, priority=priority
            )
        if p == "claude":
            return self._claude_stream(system, messages, enable_thinking=enable_thinking)
        if p in ("copilot", "github_copilot", "openai", "gateway"):
            return self._openai_compat_stream(system, messages, enable_thinking=enable_thinking)
        raise LLMInferenceError(
            f"Unknown provider: {p!r}. Choose: ollama, claude, copilot, openai, gateway", provider=p
        )

    def chat_stream(
        self,
        system: str,
        user: str,
        *,
        enable_thinking: bool = True,
        sanitize: bool = False,
        priority: RequestPriority | str | None = RequestPriority.HIGH,
    ) -> Generator[str]:
        """Send a single-turn chat message and yield streaming tokens as they arrive."""
        yield from self.chat_messages_stream(
            system,
            [ChatMessage(role="user", content=user)],
            enable_thinking=enable_thinking,
            sanitize=sanitize,
            priority=priority,
        )

    @staticmethod
    def _stream_seconds(t_start: float) -> float:
        """Seconds a stream has run since `t_start`, less its wait for a gateway slot.

        A plain call is timed from when it holds its slot, so a stream is too: a review starved
        of slots must not read as slow inference. The wait is its own span and metric.
        """
        return time.perf_counter() - t_start - network.stream_slot_wait.get()

    def _record_first_token(
        self, span_h: Any, t_start: float, first_token_time: float | None
    ) -> float:
        """Record the time to the first chunk, in seconds, on the stream span once."""
        if first_token_time is not None:
            return first_token_time
        ttft = self._stream_seconds(t_start)
        span_h.set_attribute("gen_ai.response.time_to_first_chunk", ttft)
        return ttft

    def chat_messages_stream(
        self,
        system: str,
        messages: list[ChatMessage],
        *,
        enable_thinking: bool = True,
        sanitize: bool = False,
        priority: RequestPriority | str | None = None,
    ) -> Generator[str]:
        """Send a multi-turn conversation and yield streaming tokens as they arrive.

        The style request joins `system` first. A stream that fails after yielding output records
        its spend with finish reason `error` and re-raises; one that fails before its first chunk
        records nothing, as a failed non-streamed call records nothing.
        """
        system = with_style_request(system)
        p = self._config.provider
        t_start = time.perf_counter()
        first_token_time: float | None = None
        resolved_p = (
            RequestPriority(priority)
            if isinstance(priority, str)
            else (priority or network.current_request_priority.get())
        )

        stream_attrs: dict[str, Any] = {
            "gen_ai.operation.name": "chat",
            "gen_ai.provider.name": genai_provider_name(p),
            "gen_ai.request.model": self._config.model,
            "gen_ai.request.stream": True,
            "llm.request.priority": resolved_p.value,
            "llm.request.enable_thinking": enable_thinking,
            "llm.stream.sanitize": sanitize,
        }
        stream_attrs.update(origin_span_attributes(self._configured_origin))
        with (
            trace_span(
                "ai.llm.stream", attributes=stream_attrs, kind=CONST_OTEL_SPAN_KIND_CLIENT
            ) as span_h,
            network.bind_dispatch_context(
                provider=p,
                model=self._config.model,
                request_type="stream",
                task_name=getattr(self._config, "task_name", None),
                server=self.backend_host,
                backend_info=self.backend_info,
            ),
        ):
            network.stream_served_by.set(None)
            network.stream_served_model.set(None)
            network.stream_model.set(None)
            network.stream_finish_reason.set(None)
            network.stream_slot_wait.set(0.0)
            network.stream_server.set(None)
            network.stream_usage.set(None)
            accumulated_chunks: list[str] = []
            processor: Any = None
            spend_recorded = False
            try:
                gen = self._dispatch_stream(
                    system, messages, enable_thinking=enable_thinking, priority=resolved_p
                )
                if sanitize:
                    from devops_cli.ai.client.streaming import StreamingTokenProcessor
                    from devops_cli.ai.profiles import get_model_thinking_tags

                    tags = get_model_thinking_tags(self._config.model)
                    processor = StreamingTokenProcessor(thinking_tags=tags)
                    gen = processor.sanitize_stream(gen)
                for chunk in gen:
                    first_token_time = self._record_first_token(span_h, t_start, first_token_time)
                    accumulated_chunks.append(chunk)
                    yield chunk
            except Exception as exc:
                if processor is not None:
                    _set_stream_sanitizer_attributes(span_h, processor)
                span_h.record_exception(exc)
                if accumulated_chunks and not spend_recorded:
                    spend_recorded = True
                    self._record_stream_spend(
                        span_h,
                        p,
                        messages,
                        system,
                        "".join(accumulated_chunks),
                        self._stream_seconds(t_start),
                        CONST_FINISH_REASON_ERROR,
                    )
                raise
            finally:
                if accumulated_chunks and not spend_recorded:
                    spend_recorded = True
                    total_dur = self._stream_seconds(t_start)
                    finish_reason = network.stream_finish_reason.get()
                    _set_finish_reason_attribute(span_h, finish_reason)
                    span_h.set_attribute("llm.stream.chunk_count", len(accumulated_chunks))
                    span_h.set_attribute("llm.wall_seconds", total_dur)
                    if processor is not None:
                        _set_stream_sanitizer_attributes(span_h, processor)
                    self._record_stream_spend(
                        span_h,
                        p,
                        messages,
                        system,
                        "".join(accumulated_chunks),
                        total_dur,
                        finish_reason,
                    )

    def _record_stream_spend(
        self,
        span_h: Any,
        p: str,
        messages: list[ChatMessage],
        system: str,
        accumulated_text: str,
        total_dur: float,
        finish_reason: FinishReason | None,
    ) -> None:
        """Record streaming request spend to ledger and telemetry."""
        from devops_cli.ai.context_budget import count_tokens
        from devops_cli.ai.spend import resolve_spend_stage, track_request_spend

        leased = network.stream_server.get()
        srv = origin_label(leased) if leased is not None else self.backend_host
        usage = network.stream_usage.get()
        if (
            usage is not None
            and usage.prompt_tokens is not None
            and usage.completion_tokens is not None
        ):
            p_tokens = usage.prompt_tokens
            c_tokens = usage.completion_tokens
            r_tokens = usage.reasoning_tokens or 0
        else:
            p_tokens = sum(count_tokens(m.content) for m in messages) + (
                count_tokens(system) if system else 0
            )
            c_tokens = count_tokens(accumulated_text)
            r_tokens = 0
            from devops_cli.ai.thinking_stream import extract_think_blocks

            inner_thinks, _ = extract_think_blocks(accumulated_text)
            if inner_thinks:
                r_tokens = min(count_tokens("\n".join(inner_thinks)), c_tokens)

        served_model = network.stream_served_model.get()
        if not served_model:
            s_model = network.stream_model.get()
            if s_model and s_model != self._config.model:
                served_model = s_model

        rec = track_request_spend(
            provider=p,
            model=self._config.model,
            server=srv,
            backend_info=self.backend_info,
            served_by=network.stream_served_by.get(),
            served_model=served_model,
            prompt_tokens=p_tokens,
            completion_tokens=c_tokens,
            cached=False,
            request_type="stream",
            duration_seconds=total_dur,
            stage=resolve_spend_stage(None, getattr(self._config, "task_name", None)),
            finish_reason=finish_reason,
            reasoning_tokens=r_tokens,
        )
        if rec is not None:
            span_h.set_attribute("llm.usage.cost_usd", rec.cost_usd)
        if p_tokens is not None:
            span_h.set_attribute("gen_ai.usage.input_tokens", p_tokens)
        if c_tokens is not None:
            span_h.set_attribute("gen_ai.usage.output_tokens", c_tokens)
        if r_tokens:
            span_h.set_attribute("gen_ai.usage.reasoning.output_tokens", r_tokens)

    def list_models(self) -> list[str]:
        """List available models for the current provider."""
        p = self._config.provider
        if p == "ollama":
            return self._ollama_models()
        if p in ("copilot", "openai", "gateway"):
            return self._openai_models()
        return [self._config.model]
