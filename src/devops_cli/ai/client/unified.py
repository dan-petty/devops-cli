"""Unified AI client orchestrating provider backends, response cache, and telemetry."""

from __future__ import annotations

import logging
import os
import threading
import time
from collections.abc import AsyncGenerator, Callable, Generator, Sequence
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx2

from devops_cli.ai.client import network
from devops_cli.ai.client.claude import ClaudeProviderMixin
from devops_cli.ai.client.models import (
    AIClientError,
    LLMResponse,
    _is_json_error_payload,
)
from devops_cli.ai.client.network import (
    ALLOW_PRIVATE_NETWORK_ENV,
    read_limited_json,
    validate_base_url,
)
from devops_cli.ai.client.ollama import OllamaProviderMixin
from devops_cli.ai.client.openai import OpenAICompatProviderMixin
from devops_cli.ai.thinking_stream import strip_think_blocks
from devops_cli.config.constants import (
    CONST_URL_ANTHROPIC_API_BASE,
    CONST_URL_GITHUB_COPILOT_API_BASE,
    CONST_URL_OPENAI_API_BASE,
)
from devops_cli.config.defaults import (
    DEFAULT_AI_CONTEXT_WINDOW,
    DEFAULT_HTTP_TIMEOUT_SECONDS,
)
from devops_cli.config.settings import AIConfig
from devops_cli.exceptions import LLMInferenceError
from devops_cli.http.client import request_timeout
from devops_cli.models.ai import ChatMessage
from devops_cli.telemetry import record_metric, trace_span

logger = logging.getLogger(__name__)


class LLMClient(OllamaProviderMixin, ClaudeProviderMixin, OpenAICompatProviderMixin):
    """Unified client for interacting with AI models across different providers."""

    _ALLOW_PRIVATE_NETWORK_ENV = ALLOW_PRIVATE_NETWORK_ENV
    _active_ollama_requests = network.active_ollama_requests
    _ollama_active_lock = network.ollama_active_lock
    _ollama_semaphores = network.ollama_semaphores
    _ollama_sem_lock = network.ollama_sem_lock
    _global_ollama_url_index = network.global_ollama_url_index
    _global_ollama_url_lock = network.global_ollama_url_lock

    @classmethod
    def _load_and_increment_rr_index(cls, n: int) -> int:
        return network.load_and_increment_rr_index(n)

    @classmethod
    def _get_ollama_semaphore(cls, url: str, max_parallel: int) -> threading.Semaphore:
        return network.get_ollama_semaphore(url, max_parallel)

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
    ) -> None:
        if config is None:
            from devops_cli.config.settings import get_ai_api_key, load_settings

            settings = load_settings()
            config = settings.ai
            if not api_key:
                api_key = get_ai_api_key(settings)

        self._config = config
        self._api_key = api_key or ""
        self._custom_endpoint = custom_endpoint
        self._request_timeout_seconds = request_timeout_seconds
        self._ollama_thinking_supported: bool | None = None
        self._ollama_url_index = 0
        self._ollama_url_lock = threading.Lock()

        cache_cfg = getattr(config, "cache", None)
        if cache_enabled is None:
            cache_enabled = getattr(cache_cfg, "enabled", True) if cache_cfg is not None else True
        if not isinstance(cache_enabled, bool):
            cache_enabled = True
        cache_dir_raw = getattr(cache_cfg, "dir", None) if cache_cfg is not None else None
        cache_dir: Path | None = None
        if isinstance(cache_dir_raw, Path):
            cache_dir = cache_dir_raw
        elif isinstance(cache_dir_raw, str):
            cache_dir = Path(cache_dir_raw)
        cache_ttl = (
            getattr(cache_cfg, "ttl_seconds", 86400 * 7) if cache_cfg is not None else 86400 * 7
        )
        if not isinstance(cache_ttl, (int, float)):
            cache_ttl = 86400 * 7
        cache_max = getattr(cache_cfg, "max_entries", 1000) if cache_cfg is not None else 1000
        if not isinstance(cache_max, int):
            cache_max = 1000

        from devops_cli.ai.response_cache import get_llm_response_cache

        self._cache = get_llm_response_cache(
            cache_dir=cache_dir,
            enabled=cache_enabled,
            ttl_seconds=cache_ttl,
            max_entries=cache_max,
        )
        if append_cache is None:
            append_cache = getattr(config, "append_cache", False) or getattr(
                getattr(config, "cache", None), "append_cache", False
            )
        self._append_cache = bool(append_cache)

    @property
    def cache(self) -> Any:
        """Return the underlying LLM response cache instance."""
        return self._cache

    def _connection_error(self, exc: Exception) -> AIClientError:
        provider = self._config.provider
        if provider == "ollama":
            return AIClientError(
                "Cannot connect to Ollama. Start Ollama, or run: devops ai config --provider ollama --ollama-urls <urls>"
            )
        if provider == "claude":
            return AIClientError(
                "Cannot connect to Claude API. Check network access and api_base_url (devops ai config --provider claude --api-base-url <url>)."
            )
        return AIClientError(
            "Cannot connect to AI provider API. Check network access, api_base_url, and API key."
        )

    @property
    def backend_type(self) -> str:
        """Return the AI provider backend type (e.g. ollama, claude, copilot, openai)."""
        p = getattr(self._config, "provider", "ollama")
        return str(p) if isinstance(p, str) else "mock"

    @property
    def backend_host(self) -> str:
        """Return the endpoint host for the current AI provider."""
        p = getattr(self._config, "provider", "ollama")
        if not isinstance(p, str):
            p = "ollama"
        if p == "ollama":
            urls = getattr(self._config, "get_ollama_urls", ["http://localhost:11434"])
            if not isinstance(urls, (list, tuple)):
                urls = ["http://localhost:11434"]
            hosts: list[str] = []
            for u in urls:
                if isinstance(u, str):
                    parsed = urlparse(u)
                    hosts.append(parsed.netloc or parsed.path or u)
            return ", ".join(hosts) or "localhost:11434"
        base_url = getattr(self._config, "api_base_url", None)
        if not isinstance(base_url, str) or not base_url:
            if p == "claude":
                base_url = CONST_URL_ANTHROPIC_API_BASE
            elif p == "copilot":
                base_url = CONST_URL_GITHUB_COPILOT_API_BASE
            elif p == "openai":
                base_url = CONST_URL_OPENAI_API_BASE
        if isinstance(base_url, str) and base_url:
            parsed = urlparse(base_url)
            return str(parsed.netloc or parsed.path or base_url)
        return "unknown"

    @property
    def backend_info(self) -> str:
        """Return formatted backend type and host string, e.g. 'ollama (localhost:11434)'."""
        return f"{self.backend_type} ({self.backend_host})"

    def get_context_window(self, task: str | None = None) -> int:
        """Return the effective token context window for the configured model/task."""
        cfg = self._config.for_task(task) if task else self._config
        win = (
            getattr(cfg, "num_ctx", None)
            or getattr(cfg, "context_window", None)
            or DEFAULT_AI_CONTEXT_WINDOW
        )
        return int(win)

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
        return request_timeout(read=self._request_timeout_seconds or DEFAULT_HTTP_TIMEOUT_SECONDS)

    def _allow_private_network(self) -> bool:
        if self._config.allow_private_network:
            return True
        return os.environ.get(self._ALLOW_PRIVATE_NETWORK_ENV, "").strip().lower() in (
            "1",
            "true",
            "yes",
            "on",
        )

    def _validate_base_url(
        self,
        base_url: str,
        purpose: str = "API",
        *,
        allow_loopback_for_local_tooling: bool = False,
    ) -> str:
        return validate_base_url(
            base_url,
            purpose=purpose,
            allow_private_network=self._allow_private_network(),
            allow_loopback_for_local_tooling=allow_loopback_for_local_tooling,
        )

    @staticmethod
    def _read_limited_json(
        response: httpx2.Response, limit_bytes: int = 20 * 1024 * 1024
    ) -> dict[str, Any]:
        return read_limited_json(response, limit_bytes=limit_bytes)

    def _dispatch_messages(
        self,
        system: str,
        messages: list[ChatMessage],
        *,
        enable_thinking: bool = True,
    ) -> LLMResponse:
        p = self._config.provider
        start = time.perf_counter()
        prompt_preview = ""
        for m in reversed(messages):
            if m.role == "user":
                prompt_preview = m.content[:200].replace("\n", " ").strip()
                break

        with trace_span(
            "ai.llm.dispatch",
            {
                "gen_ai.system": p,
                "gen_ai.operation.name": "chat",
                "gen_ai.request.model": self._config.model,
                "gen_ai.request.message_count": len(messages),
                "gen_ai.request.system_prompt_length": len(system),
                "gen_ai.request.enable_thinking": enable_thinking,
                "gen_ai.prompt_preview": prompt_preview,
                "provider": p,
                "model": self._config.model,
            },
        ) as span_handle:
            if p == "ollama":
                res = self._ollama_messages(system, messages, enable_thinking=enable_thinking)
            elif p == "claude":
                res = self._claude_messages(system, messages, enable_thinking=enable_thinking)
            elif p in ("copilot", "github_copilot", "openai"):
                res = self._openai_compat_messages(
                    system, messages, enable_thinking=enable_thinking
                )
            else:
                raise LLMInferenceError(
                    f"Unknown provider: {p!r}. Choose: ollama, claude, copilot, openai",
                    provider=p,
                )

            if res.backend_info:
                span_handle.set_attribute("gen_ai.server.address", res.backend_info)
            if res.prompt_tokens is not None:
                span_handle.set_attribute("gen_ai.usage.prompt_tokens", res.prompt_tokens)
                span_handle.set_attribute("gen_ai.usage.input_tokens", res.prompt_tokens)
            if res.completion_tokens is not None:
                span_handle.set_attribute("gen_ai.usage.completion_tokens", res.completion_tokens)
                span_handle.set_attribute("gen_ai.usage.output_tokens", res.completion_tokens)
            if res.total_tokens is not None:
                span_handle.set_attribute("gen_ai.usage.total_tokens", res.total_tokens)
            if res.eval_duration_ms is not None:
                span_handle.set_attribute("llm.eval_duration_ms", res.eval_duration_ms)
                if res.completion_tokens and res.eval_duration_ms > 0:
                    tok_rate = res.completion_tokens / (res.eval_duration_ms / 1000.0)
                    span_handle.set_attribute("gen_ai.token_rate_tok_per_sec", round(tok_rate, 2))
            if res.prompt_eval_duration_ms is not None:
                span_handle.set_attribute(
                    "llm.prompt_eval_duration_ms", res.prompt_eval_duration_ms
                )
            if res.processing_seconds is not None:
                span_handle.set_attribute("llm.processing_seconds", res.processing_seconds)
            if res.wall_seconds is not None:
                span_handle.set_attribute("llm.wall_seconds", res.wall_seconds)

            span_handle.set_attribute("gen_ai.response.finish_reasons", ["stop"])
            span_handle.set_attribute(
                "gen_ai.response_preview", res.text[:200].replace("\n", " ").strip()
            )
            span_handle.set_attribute("gen_ai.thinking", bool(res.thinking))

            span_handle.add_event(
                "llm_response_received",
                {
                    "total_tokens": res.total_tokens or 0,
                    "wall_seconds": res.wall_seconds or 0.0,
                    "backend": res.backend_info or p,
                },
            )

        duration = time.perf_counter() - start
        record_metric(
            "devops_cli_llm_inference_seconds",
            duration,
            unit="s",
            attributes={"provider": p, "model": self._config.model},
        )
        return res

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
        )

    def _record_chat_telemetry(self, span_h: Any, res: LLMResponse) -> None:
        """Record response metrics and tokens on the telemetry span."""
        span_h.set_attribute("gen_ai.response.model", res.backend_info)
        span_h.set_attribute("gen_ai.cached", res.cached)
        span_h.set_attribute("gen_ai.processing_seconds", res.processing_seconds)
        span_h.set_attribute("gen_ai.wall_seconds", res.wall_seconds)
        if res.total_tokens:
            span_h.set_attribute("gen_ai.usage.total_tokens", res.total_tokens)
            span_h.set_attribute("gen_ai.usage.prompt_tokens", res.prompt_tokens)
            span_h.set_attribute("gen_ai.usage.completion_tokens", res.completion_tokens)

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
        if cached_entry is None or not self._validate_response_text(
            cached_entry.content, validator
        ):
            return None
        span_h.set_attribute("gen_ai.response.model", "cache")
        span_h.set_attribute("gen_ai.cached", True)
        span_h.set_attribute("gen_ai.wall_seconds", 0.0)
        return LLMResponse(
            cached_entry.content,
            processing_seconds=0.0,
            wall_seconds=0.0,
            backend_info="cache",
            thinking=cached_entry.thinking,
            cached=True,
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
        """Record telemetry, optionally cache successful response, and return."""
        self._record_chat_telemetry(span_h, res)
        if use_cache:
            self._cache_chat_entry(cache_key, system, out_messages, res, context_tag)
        return res

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
    ) -> LLMResponse:
        """Execute chat dispatch across retries with validation and error tracking."""
        last_exc: Exception | None = None
        for attempt in range(1, attempts + 1):
            try:
                res = self._dispatch_messages(system, out_messages, enable_thinking=enable_thinking)
                if not self._validate_response_text(res, validator):
                    m = self._config.model
                    msg = f"Response validation failed for model '{m}' (attempt {attempt}/{attempts})."
                    last_exc = AIClientError(msg)
                    continue
                return self._handle_successful_chat_dispatch(
                    res, cache_key, system, out_messages, use_cache, context_tag, span_h
                )
            except Exception as exc:
                last_exc = exc
            if attempt < attempts:
                time.sleep(0.5 * attempt)

        if isinstance(last_exc, AIClientError):
            span_h.record_exception(last_exc)
            raise last_exc
        if last_exc is not None:
            err = self._connection_error(last_exc)
            span_h.record_exception(err)
            raise err
        fallback_err = AIClientError("AI request failed with no valid response.")
        span_h.record_exception(fallback_err)
        raise fallback_err

    def chat_messages(
        self,
        system: str,
        messages: list[ChatMessage],
        *,
        enable_thinking: bool = True,
        validator: Callable[[str], bool] | None = None,
        max_retries: int | None = None,
        use_cache: bool = True,
        starting_point: str | None = None,
        context_tag: str | None = None,
        append_cache: bool | None = None,
    ) -> LLMResponse:
        """Send a multi-turn chat request with response validation, caching, and retries."""
        eff_append = self._append_cache if append_cache is None else append_cache
        eff_start = starting_point
        if eff_start is None and context_tag:
            eff_start = self._cache.get_starting_point(context_tag=context_tag)

        if eff_append and eff_start is None and use_cache:
            unaugmented_key = self._cache.generate_key(
                provider=str(getattr(self._config, "provider", "ollama")),
                model=str(getattr(self._config, "model", "default")),
                system=system,
                messages_or_prompt=messages,
                options={"enable_thinking": enable_thinking},
            )
            cached_candidate = self._cache.get(unaugmented_key)
            if cached_candidate is not None:
                eff_start = cached_candidate.content

        out_messages = self._augment_messages(messages, eff_start)
        cache_key = self._cache.generate_key(
            provider=str(getattr(self._config, "provider", "ollama")),
            model=str(getattr(self._config, "model", "default")),
            system=system,
            messages_or_prompt=out_messages,
            options={"enable_thinking": enable_thinking},
        )

        with trace_span(
            "gen_ai.chat",
            attributes={
                "gen_ai.system": self._config.provider,
                "gen_ai.request.model": self._config.model,
                "gen_ai.enable_thinking": enable_thinking,
                "use_cache": use_cache,
                "append_cache": eff_append,
            },
        ) as span_h:
            if use_cache and not eff_start and not eff_append:
                hit = self._check_chat_cache(cache_key, validator, span_h)
                if hit is not None:
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
            )

    def _dispatch_stream(
        self,
        system: str,
        messages: list[ChatMessage],
        *,
        enable_thinking: bool = True,
    ) -> Generator[str]:
        """Dispatch streaming request to appropriate provider handler."""
        p = self._config.provider
        if p == "ollama":
            return self._ollama_stream(system, messages, enable_thinking=enable_thinking)
        if p == "claude":
            return self._claude_stream(system, messages, enable_thinking=enable_thinking)
        if p in ("copilot", "github_copilot", "openai"):
            return self._openai_compat_stream(system, messages, enable_thinking=enable_thinking)
        raise LLMInferenceError(
            f"Unknown provider: {p!r}. Choose: ollama, claude, copilot, openai", provider=p
        )

    def chat_stream(
        self, system: str, user: str, *, enable_thinking: bool = True
    ) -> Generator[str]:
        """Send a single-turn chat message and yield streaming tokens as they arrive."""
        yield from self.chat_messages_stream(
            system,
            [ChatMessage(role="user", content=user)],
            enable_thinking=enable_thinking,
        )

    def _record_first_token(
        self, span_h: Any, t_start: float, first_token_time: float | None
    ) -> float:
        """Record time to first token on trace span if not already recorded."""
        if first_token_time is not None:
            return first_token_time
        ttft = time.perf_counter() - t_start
        span_h.set_attribute("gen_ai.ttft_seconds", ttft)
        return ttft

    def chat_messages_stream(
        self,
        system: str,
        messages: list[ChatMessage],
        *,
        enable_thinking: bool = True,
    ) -> Generator[str]:
        """Send a multi-turn conversation and yield streaming tokens as they arrive."""
        p = self._config.provider
        t_start = time.perf_counter()
        first_token_time: float | None = None
        token_chunks_count = 0

        with trace_span(
            "gen_ai.stream",
            attributes={
                "gen_ai.system": p,
                "gen_ai.request.model": self._config.model,
                "gen_ai.enable_thinking": enable_thinking,
            },
        ) as span_h:
            try:
                gen = self._dispatch_stream(system, messages, enable_thinking=enable_thinking)
                for chunk in gen:
                    first_token_time = self._record_first_token(span_h, t_start, first_token_time)
                    token_chunks_count += 1
                    yield chunk

                total_dur = time.perf_counter() - t_start
                span_h.set_attribute("gen_ai.stream_chunks_count", token_chunks_count)
                span_h.set_attribute("gen_ai.wall_seconds", total_dur)
            except Exception as exc:
                span_h.record_exception(exc)
                raise

    def list_models(self) -> list[str]:
        """List available models for the current provider."""
        p = self._config.provider
        if p == "ollama":
            return self._ollama_models()
        if p in ("copilot", "openai"):
            return self._openai_models()
        return [self._config.model]

    def direct_request_sync(
        self,
        prompt: str | Sequence[Any],
        model: Any = None,
        *,
        system_prompt: str = "",
        model_concurrency: Any = None,
        **kwargs: Any,
    ) -> Any:
        """Make a synchronous direct model request via native Pydantic AI."""
        from devops_cli.ai.direct import direct_model_request_sync

        target_model = model or getattr(self._config, "model", "default")
        return direct_model_request_sync(
            prompt,
            target_model,
            system_prompt=system_prompt,
            model_concurrency=model_concurrency,
            **kwargs,
        )

    async def direct_request(
        self,
        prompt: str | Sequence[Any],
        model: Any = None,
        *,
        system_prompt: str = "",
        model_concurrency: Any = None,
        **kwargs: Any,
    ) -> Any:
        """Make an asynchronous direct model request via native Pydantic AI."""
        from devops_cli.ai.direct import direct_model_request

        target_model = model or getattr(self._config, "model", "default")
        return await direct_model_request(
            prompt,
            target_model,
            system_prompt=system_prompt,
            model_concurrency=model_concurrency,
            **kwargs,
        )

    def direct_stream_sync(
        self,
        prompt: str | Sequence[Any],
        model: Any = None,
        *,
        system_prompt: str = "",
        model_concurrency: Any = None,
        **kwargs: Any,
    ) -> Generator[str]:
        """Make a synchronous streamed direct request via native Pydantic AI."""
        from devops_cli.ai.direct import direct_model_request_stream_sync

        target_model = model or getattr(self._config, "model", "default")
        yield from direct_model_request_stream_sync(
            prompt,
            target_model,
            system_prompt=system_prompt,
            model_concurrency=model_concurrency,
            **kwargs,
        )

    async def direct_stream(
        self,
        prompt: str | Sequence[Any],
        model: Any = None,
        *,
        system_prompt: str = "",
        model_concurrency: Any = None,
        **kwargs: Any,
    ) -> AsyncGenerator[str]:
        """Make an asynchronous streamed direct request via native Pydantic AI."""
        from devops_cli.ai.direct import direct_model_request_stream

        target_model = model or getattr(self._config, "model", "default")
        async for chunk in direct_model_request_stream(
            prompt,
            target_model,
            system_prompt=system_prompt,
            model_concurrency=model_concurrency,
            **kwargs,
        ):
            yield chunk


def model_request_sync(
    model: str,
    prompt_or_messages: str | list[ChatMessage],
    *,
    system_prompt: str = "You are a helpful assistant.",
    enable_thinking: bool = True,
    client: LLMClient | None = None,
    **kwargs: Any,
) -> LLMResponse:
    """Make a direct, synchronous request to a model without an agent wrapper."""
    llm_client = client or LLMClient(config=AIConfig(model=model, **kwargs))
    if isinstance(prompt_or_messages, str):
        return llm_client.chat(system_prompt, prompt_or_messages, enable_thinking=enable_thinking)
    return llm_client.chat_messages(
        system_prompt, prompt_or_messages, enable_thinking=enable_thinking
    )


async def model_request(
    model: str,
    prompt_or_messages: str | list[ChatMessage],
    *,
    system_prompt: str = "You are a helpful assistant.",
    enable_thinking: bool = True,
    client: LLMClient | None = None,
    **kwargs: Any,
) -> LLMResponse:
    """Make a direct asynchronous request to a model without an agent wrapper."""
    return model_request_sync(
        model,
        prompt_or_messages,
        system_prompt=system_prompt,
        enable_thinking=enable_thinking,
        client=client,
        **kwargs,
    )
