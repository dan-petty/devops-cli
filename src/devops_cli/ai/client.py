"""Unified LLM client: Ollama, Claude (Anthropic), GitHub Copilot, and OpenAI-compatible APIs.

Architecture:
- Maps `ai.provider` settings (`ollama`, `claude`, `copilot`, `openai`) to unified REST chat calls.
- Validates base URLs before making HTTP requests, refusing non-public endpoints unless
  `allow_private_network=True` or `DEVOPS_CLI_AI_ALLOW_PRIVATE_NETWORK=true` is set.
- Wraps provider-specific error responses into `AIClientError` with user-actionable instructions.
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
import threading
import time
from collections.abc import Callable, Generator
from concurrent.futures import as_completed
from contextlib import contextmanager
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx2

from devops_cli.ai.thinking import strip_think_blocks
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
from devops_cli.telemetry import ContextPropagatingThreadPoolExecutor as ThreadPoolExecutor
from devops_cli.telemetry import inject_trace_context, record_metric, trace_span

MAX_STREAM_BYTES = 50 * 1024 * 1024  # 50MB maximum streamed response size
logger = logging.getLogger(__name__)


class AIClientError(LLMInferenceError, RuntimeError):
    """Raised when an AI provider request fails with a user-actionable message."""


class LLMResponse(str):
    """String response from LLM with optional execution timing and backend metadata."""

    processing_seconds: float | None
    wall_seconds: float
    backend_info: str | None
    thinking: str | None
    prompt_tokens: int | None
    completion_tokens: int | None
    total_tokens: int | None
    cached: bool
    eval_duration_ms: float | None
    prompt_eval_duration_ms: float | None

    def __new__(
        cls,
        content: str,
        processing_seconds: float | None = None,
        wall_seconds: float = 0.0,
        backend_info: str | None = None,
        thinking: str | None = None,
        prompt_tokens: int | None = None,
        completion_tokens: int | None = None,
        total_tokens: int | None = None,
        eval_duration_ms: float | None = None,
        prompt_eval_duration_ms: float | None = None,
        cached: bool = False,
    ) -> LLMResponse:
        obj = str.__new__(cls, content)
        obj.processing_seconds = processing_seconds
        obj.wall_seconds = wall_seconds
        obj.backend_info = backend_info
        obj.thinking = thinking
        obj.prompt_tokens = prompt_tokens
        obj.completion_tokens = completion_tokens
        obj.total_tokens = total_tokens
        obj.eval_duration_ms = eval_duration_ms
        obj.prompt_eval_duration_ms = prompt_eval_duration_ms
        obj.cached = cached
        return obj

    @property
    def text(self) -> str:
        """Return the string response content."""
        return str(self)

    @property
    def content(self) -> str:
        """Return the string response content."""
        return str(self)


def _is_json_error_payload(raw_str: str) -> bool:
    """Check if raw JSON text represents an error dictionary."""
    if not (raw_str.startswith("{") and raw_str.endswith("}")):
        return False
    try:
        data = json.loads(raw_str)
        if not isinstance(data, dict):
            return False
        err_val = data.get("error")
        err_code = data.get("error_code")
        has_err_val = (
            isinstance(err_val, str | dict)
            and bool(err_val)
            and str(err_val).lower() not in ("none", "null", "no error", "0", "")
        )
        return has_err_val or (err_code is not None and bool(err_code))
    except json.JSONDecodeError, TypeError, ValueError:
        return False


def _extract_ollama_stream_chunk(line: str) -> str | None:
    """Extract content or thinking chunk from an Ollama stream line."""
    if not line:
        return None
    try:
        line_data = json.loads(line)
    except json.JSONDecodeError:
        return None
    msg = line_data.get("message", {})
    content = msg.get("content", "")
    thinking = msg.get("thinking", "")
    if thinking:
        return f"<think>{thinking}</think>"
    if content:
        return str(content)
    return None


def _extract_claude_stream_chunk(line: str) -> tuple[str | None, bool]:
    """Extract content chunk from Claude SSE stream line. Returns (chunk, is_done)."""
    if not line or not line.startswith("data:"):
        return (None, False)
    raw_data = line.removeprefix("data:").strip()
    if raw_data == "[DONE]":
        return (None, True)
    try:
        event_json = json.loads(raw_data)
    except json.JSONDecodeError:
        return (None, False)
    if event_json.get("type") == "content_block_delta":
        delta = event_json.get("delta", {})
        if delta.get("type") == "text_delta":
            text_val = delta.get("text", "")
            if text_val:
                return (str(text_val), False)
    return (None, False)


def _extract_openai_stream_chunk(line: str) -> tuple[str | None, bool]:
    """Extract content chunk from OpenAI SSE stream line. Returns (chunk, is_done)."""
    if not line or not line.startswith("data:"):
        return (None, False)
    raw_data = line.removeprefix("data:").strip()
    if raw_data == "[DONE]":
        return (None, True)
    try:
        event_json = json.loads(raw_data)
    except json.JSONDecodeError:
        return (None, False)
    choices = event_json.get("choices", [])
    if choices:
        delta = choices[0].get("delta", {})
        content = delta.get("content")
        if content:
            return (str(content), False)
    return (None, False)


def _extract_ollama_stream_tuple(line: str) -> tuple[str | None, bool]:
    """Extract content or thinking chunk from Ollama stream line as (chunk, is_done)."""
    return (_extract_ollama_stream_chunk(line), False)


def _consume_streaming_lines(
    response: httpx2.Response,
    chunk_extractor: Callable[[str], tuple[str | None, bool]],
    provider_name: str,
) -> Generator[str]:
    """Yield extracted tokens from an HTTP streaming response with size bounds."""
    total_bytes = 0
    for line in response.iter_lines():
        chunk_str, is_done = chunk_extractor(line)
        if is_done:
            break
        if chunk_str is None:
            continue
        total_bytes += len(chunk_str.encode("utf-8"))
        if total_bytes > MAX_STREAM_BYTES:
            raise AIClientError(f"{provider_name} response exceeded maximum stream size (50MB).")
        yield chunk_str


class LLMClient:
    """Unified client for interacting with AI models across different providers."""

    _ALLOW_PRIVATE_NETWORK_ENV = "DEVOPS_CLI_AI_ALLOW_PRIVATE_NETWORK"
    _active_ollama_requests: dict[str, int] = {}
    _ollama_active_lock = threading.Lock()
    _ollama_semaphores: dict[str, threading.Semaphore] = {}
    _ollama_sem_lock = threading.Lock()
    _global_ollama_url_index: int = 0
    _global_ollama_url_lock = threading.Lock()

    @classmethod
    def _load_and_increment_rr_index(cls, n: int) -> int:
        """Atomically fetch and increment the round-robin server index across runs."""
        if n <= 1:
            return 0
        uid = os.getuid() if hasattr(os, "getuid") else 0
        state_file = Path(tempfile.gettempdir()) / f"devops_cli_ollama_rr_{uid}"
        with cls._global_ollama_url_lock:
            idx = cls._global_ollama_url_index
            try:
                if state_file.exists():
                    idx = int(state_file.read_text(encoding="utf-8").strip())
            except Exception:
                pass
            next_idx = (idx + 1) % n
            cls._global_ollama_url_index = next_idx
            try:
                state_file.write_text(str(next_idx), encoding="utf-8")
            except Exception:
                pass
            return idx % n

    @classmethod
    def _get_ollama_semaphore(cls, url: str, max_parallel: int) -> threading.Semaphore:
        with cls._ollama_sem_lock:
            if (
                url not in cls._ollama_semaphores
                or getattr(cls._ollama_semaphores[url], "_max_parallel", None) != max_parallel
            ):
                sem = threading.Semaphore(max(1, max_parallel))
                setattr(sem, "_max_parallel", max_parallel)
                cls._ollama_semaphores[url] = sem
            return cls._ollama_semaphores[url]

    @classmethod
    @contextmanager
    def _track_ollama_url(cls, url: str, max_parallel: int = 2) -> Generator[None]:
        """Acquire concurrency slot and track active in-flight requests per Ollama server node."""
        sem = cls._get_ollama_semaphore(url, max_parallel)
        sem.acquire()
        try:
            with cls._ollama_active_lock:
                cls._active_ollama_requests[url] = cls._active_ollama_requests.get(url, 0) + 1
            yield
        finally:
            with cls._ollama_active_lock:
                cls._active_ollama_requests[url] = max(
                    0, cls._active_ollama_requests.get(url, 0) - 1
                )
            sem.release()

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
                "Cannot connect to Ollama. "
                "Start Ollama, or run: "
                "devops ai config --provider ollama --ollama-urls <urls>"
            )
        if provider == "claude":
            return AIClientError(
                "Cannot connect to Claude API. Check network access and api_base_url "
                "(devops ai config --provider claude --api-base-url <url>)."
            )
        return AIClientError(
            "Cannot connect to AI provider API. Check network access, api_base_url, and API key."
        )

    # ── public API ────────────────────────────────────────────────────────────

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

    def _preload_single_ollama_url(self, url: str) -> tuple[str, bool]:
        """Prewarm model on a single Ollama endpoint."""
        try:
            base = self._validate_base_url(
                url,
                purpose="Ollama",
                allow_loopback_for_local_tooling=True,
            )
            with httpx2.Client(timeout=self._request_timeout()) as http_client:
                res = http_client.post(
                    f"{base}/api/generate",
                    json={"model": self._config.model, "keep_alive": "1h"},
                )
                return (url, res.status_code == 200)
        except Exception:
            return (url, False)

    def _execute_preload_all(
        self,
        all_urls: list[str],
        on_complete: Callable[[dict[str, bool]], None] | None,
    ) -> dict[str, bool]:
        results: dict[str, bool] = {}
        with ThreadPoolExecutor(max_workers=max(len(all_urls), 1)) as executor:
            futures = [executor.submit(self._preload_single_ollama_url, url) for url in all_urls]
            for future in as_completed(futures):
                url, ok = future.result()
                results[url] = ok

        if on_complete is not None:
            try:
                on_complete(results)
            except Exception as exc:
                logger.debug("Preload on_complete callback failed: %s", exc)

        return results

    def preload_models(
        self,
        *,
        blocking: bool = True,
        on_complete: Callable[[dict[str, bool]], None] | None = None,
    ) -> dict[str, bool]:
        """Preload model into VRAM across all configured Ollama servers concurrently.

        When blocking=False, prewarming runs in a background thread without blocking.
        """
        if self._config.provider != "ollama":
            return {}
        all_urls = self._config.get_ollama_urls
        if not all_urls:
            return {}

        if not blocking:
            thread = threading.Thread(
                target=self._execute_preload_all,
                args=(all_urls, on_complete),
                name=f"ollama-prewarm-{self._config.model}",
                daemon=True,
            )
            thread.start()
            return {}

        return self._execute_preload_all(all_urls, on_complete)

    def prewarm_async(
        self,
        on_complete: Callable[[dict[str, bool]], None] | None = None,
    ) -> None:
        """Non-blocking helper to prewarm model in a background daemon thread."""
        self.preload_models(blocking=False, on_complete=on_complete)

    @staticmethod
    def _validate_response_text(
        content: str,
        validator: Callable[[str], bool] | None = None,
    ) -> bool:
        """Quick and effective validation of AI response content."""
        if not isinstance(content, str):
            return False
        raw_str = content.strip()
        thinking_val = getattr(content, "thinking", None)
        if not raw_str and not (thinking_val and str(thinking_val).strip()):
            return False
        if _is_json_error_payload(raw_str):
            return False

        if validator is not None:
            try:
                return bool(validator(content))
            except Exception:
                return False
        return True

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
                res = self._claude_messages(system, messages)
            elif p in ("copilot", "openai"):
                res = self._openai_compat_messages(system, messages)
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
            content=res.text,
            thinking=res.thinking,
            context_tag=context_tag,
            wall_seconds=res.wall_seconds,
            backend_info=res.backend_info,
            tokens={
                "prompt": res.prompt_tokens,
                "completion": res.completion_tokens,
                "total": res.total_tokens,
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
            content=cached_entry.content,
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
            return self._claude_stream(system, messages)
        if p in ("copilot", "openai"):
            return self._openai_compat_stream(system, messages)
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

    # ── Ollama ────────────────────────────────────────────────────────────────

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
        """Validate base URL against SSRF and network egress rules."""
        if not base_url or not base_url.strip():
            raise AIClientError(f"Missing {purpose} base URL.")

        try:
            parsed = urlparse(base_url.strip())
        except Exception as exc:
            raise AIClientError(f"Invalid {purpose} base URL format: {base_url!r}") from exc

        if parsed.scheme not in ("http", "https"):
            raise AIClientError(
                f"Invalid {purpose} URL scheme '{parsed.scheme}'. "
                "Only http and https are permitted."
            )

        host = parsed.hostname
        if not host:
            raise AIClientError(f"Missing hostname in {purpose} base URL: {base_url!r}")

        is_allowed_local = allow_loopback_for_local_tooling and host in (
            "localhost",
            "127.0.0.1",
            "::1",
        )
        if not self._allow_private_network() and not is_allowed_local:
            try:
                from devops_cli.core.validation import validate_service_url

                validate_service_url(base_url, purpose=purpose, allow=False)
            except ValueError as exc:
                raise AIClientError(str(exc)) from exc

        return base_url.rstrip("/")

    @staticmethod
    def _read_limited_json(
        response: httpx2.Response, limit_bytes: int = 20 * 1024 * 1024
    ) -> dict[str, Any]:
        """Parse JSON response while enforcing a maximum response body size limit."""
        headers = getattr(response, "headers", {})
        content_length = headers.get("content-length") if hasattr(headers, "get") else None
        if content_length and content_length.isdigit() and int(content_length) > limit_bytes:
            raise AIClientError(
                f"Response body exceeded maximum size ({limit_bytes // (1024 * 1024)}MB)."
            )
        if hasattr(response, "content") and response.content is not None:
            body = response.content
            if len(body) > limit_bytes:
                raise AIClientError(
                    f"Response body exceeded maximum size ({limit_bytes // (1024 * 1024)}MB)."
                )
            try:
                res: dict[str, Any] = json.loads(body)
                return res
            except json.JSONDecodeError as exc:
                raise AIClientError(
                    f"Invalid JSON response payload from AI provider: {exc}"
                ) from exc

        try:
            raw_res: dict[str, Any] = response.json()
            return raw_res
        except Exception as exc:
            raise AIClientError(
                f"Failed to parse JSON response body from AI provider: {exc}"
            ) from exc

    def _get_ollama_urls_loop(self) -> list[tuple[int, str]]:
        """Return list of (index, url) tuples for Ollama failover sorted by active requests."""
        all_urls = self._config.get_ollama_urls
        n = len(all_urls)
        if n == 0:
            return [(0, "http://localhost:11434")]
        start = self._load_and_increment_rr_index(n)
        self._ollama_url_index = LLMClient._global_ollama_url_index
        candidate_urls = [all_urls[(start + i) % n] for i in range(n)]
        indexed_urls = list(enumerate(candidate_urls))

        max_par = getattr(self._config, "ollama_max_parallel", 2)
        with LLMClient._ollama_active_lock:
            sorted_candidates = sorted(
                indexed_urls,
                key=lambda item: (
                    1 if LLMClient._active_ollama_requests.get(item[1], 0) >= max_par else 0,
                    LLMClient._active_ollama_requests.get(item[1], 0),
                    item[0],
                ),
            )

        return [(idx, url) for idx, url in sorted_candidates]

    def _try_single_ollama_request(
        self,
        base: str,
        candidate_url: str,
        system: str,
        messages: list[ChatMessage],
        use_thinking: bool,
        max_par: int,
    ) -> LLMResponse:
        """Attempt single Ollama request with fallback if thinking is unsupported."""
        try:
            with self._track_ollama_url(candidate_url, max_parallel=max_par):
                return self._ollama_request(base, system, messages, use_thinking)
        except httpx2.HTTPStatusError as exc:
            if exc.response.status_code == 400 and "does not support thinking" in exc.response.text:
                self._ollama_thinking_supported = False
                with self._track_ollama_url(candidate_url, max_parallel=max_par):
                    return self._ollama_request(base, system, messages, think=False)
            msg_text = exc.response.text[:300].strip() or "(empty)"
            raise AIClientError(
                f"Ollama returned HTTP {exc.response.status_code}. Response: {msg_text}"
            ) from exc

    def _ollama_messages(
        self, system: str, messages: list[ChatMessage], *, enable_thinking: bool = True
    ) -> LLMResponse:
        candidates = self._get_ollama_urls_loop()
        max_par = getattr(self._config, "ollama_max_parallel", 2)
        last_exc: Exception | None = None

        for _idx, candidate_url in candidates:
            try:
                base = self._validate_base_url(
                    candidate_url,
                    purpose="Ollama",
                    allow_loopback_for_local_tooling=True,
                )
                use_thinking = enable_thinking and self._ollama_thinking_supported is not False
                return self._try_single_ollama_request(
                    base, candidate_url, system, messages, use_thinking, max_par
                )
            except (
                httpx2.ConnectError,
                httpx2.ConnectTimeout,
                httpx2.ReadTimeout,
                httpx2.WriteTimeout,
                httpx2.PoolTimeout,
                httpx2.TimeoutException,
                httpx2.RequestError,
                httpx2.TransportError,
                OSError,
            ) as exc:
                last_exc = exc
                continue
            except httpx2.HTTPError as exc:
                raise AIClientError(
                    f"Ollama request failed ({type(exc).__name__}). "
                    "Check provider connectivity and configuration."
                ) from exc

        raise self._connection_error(last_exc or RuntimeError("All Ollama servers unreachable"))

    def _ollama_request(
        self, base: str, system: str, messages: list[ChatMessage], think: bool
    ) -> LLMResponse:
        t0 = time.monotonic()
        with httpx2.Client(timeout=self._request_timeout()) as http_client:
            payload: dict[str, Any] = {
                "model": self._config.model,
                "stream": False,
                "messages": [
                    {"role": "system", "content": system},
                    *[m.to_dict() for m in messages],
                ],
            }
            if think:
                payload["think"] = True
            if self._config.reasoning_effort:
                payload["reasoning_effort"] = self._config.reasoning_effort
            ollama_opts: dict[str, Any] = {}
            temp = getattr(self._config, "temperature", None)
            if temp is not None:
                ollama_opts["temperature"] = float(temp)
            top_p = getattr(self._config, "top_p", None)
            if top_p is not None:
                ollama_opts["top_p"] = float(top_p)
            ctx_win = getattr(self._config, "num_ctx", None) or getattr(
                self._config, "context_window", None
            )
            if ctx_win:
                ollama_opts["num_ctx"] = int(ctx_win)
            if ollama_opts:
                payload["options"] = ollama_opts
            headers = inject_trace_context({"Content-Type": "application/json"})
            response = http_client.post(f"{base}/api/chat", json=payload, headers=headers)
            response.raise_for_status()
            if think and self._ollama_thinking_supported is None:
                self._ollama_thinking_supported = True

            raw_res = self._read_limited_json(response)
            wall_elapsed = time.monotonic() - t0

            msg = raw_res.get("message", {})
            content = str(msg.get("content", ""))
            raw_thinking = msg.get("thinking")
            thinking_str = str(raw_thinking) if raw_thinking is not None else None

            if thinking_str and not content:
                content = f"<think>\n{thinking_str}\n</think>"

            text = content if think else self._strip_think_blocks(content)

            prompt_eval_ns = int(raw_res.get("prompt_eval_duration") or 0)
            eval_ns = int(raw_res.get("eval_duration") or 0)
            if prompt_eval_ns or eval_ns:
                proc_sec: float | None = (prompt_eval_ns + eval_ns) / 1_000_000_000.0
            elif "total_duration" in raw_res:
                load_ns = int(raw_res.get("load_duration") or 0)
                tot_ns = int(raw_res["total_duration"])
                proc_sec = max((tot_ns - load_ns) / 1_000_000_000.0, 0.0)
            else:
                proc_sec = None

            prompt_tokens = raw_res.get("prompt_eval_count")
            completion_tokens = raw_res.get("eval_count")
            total_tokens = (
                (prompt_tokens + completion_tokens)
                if prompt_tokens is not None and completion_tokens is not None
                else None
            )
            eval_dur_ms = (eval_ns / 1_000_000.0) if eval_ns else None
            prompt_eval_dur_ms = (prompt_eval_ns / 1_000_000.0) if prompt_eval_ns else None

            parsed = urlparse(base)
            host_str = parsed.netloc or parsed.path or base
            b_info = f"ollama ({host_str})"
            return LLMResponse(
                text,
                processing_seconds=proc_sec,
                wall_seconds=wall_elapsed,
                backend_info=b_info,
                thinking=thinking_str,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens,
                eval_duration_ms=eval_dur_ms,
                prompt_eval_duration_ms=prompt_eval_dur_ms,
            )

    def _fetch_ollama_tags(self, base: str) -> list[str]:
        """Fetch available model tags from single Ollama host."""
        with httpx2.Client(timeout=self._request_timeout()) as http_client:
            response = http_client.get(f"{base}/api/tags")
            response.raise_for_status()
            models_data = self._read_limited_json(response).get("models", [])
            return [model_info["name"] for model_info in models_data]

    def _ollama_models(self) -> list[str]:
        candidates = self._get_ollama_urls_loop()
        last_exc: Exception | None = None

        for _idx, candidate_url in candidates:
            try:
                base = self._validate_base_url(
                    candidate_url,
                    purpose="Ollama",
                    allow_loopback_for_local_tooling=True,
                )
                return self._fetch_ollama_tags(base)
            except (
                httpx2.ConnectError,
                httpx2.ConnectTimeout,
                httpx2.ReadTimeout,
                httpx2.WriteTimeout,
                httpx2.PoolTimeout,
                httpx2.TimeoutException,
                httpx2.RequestError,
                httpx2.TransportError,
                OSError,
            ) as exc:
                last_exc = exc
                continue
            except httpx2.HTTPError as exc:
                raise AIClientError(
                    "Failed to list Ollama models. Check provider connectivity and configuration."
                ) from exc

        raise self._connection_error(last_exc or RuntimeError("All Ollama servers unreachable"))

    # ── Anthropic Claude ──────────────────────────────────────────────────────

    def _claude_messages(self, system: str, messages: list[ChatMessage]) -> LLMResponse:
        base = self._validate_base_url(
            self._config.api_base_url or CONST_URL_ANTHROPIC_API_BASE,
            purpose="Claude API",
        )
        t0 = time.monotonic()
        headers = inject_trace_context(
            {
                "x-api-key": self._api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            }
        )
        max_tok = getattr(self._config, "max_tokens", None) or 8192
        payload: dict[str, Any] = {
            "model": self._config.model,
            "max_tokens": int(max_tok),
            "system": system,
            "messages": [m.to_dict() for m in messages],
        }
        claude_temp = getattr(self._config, "temperature", None)
        if claude_temp is not None:
            payload["temperature"] = float(claude_temp)
        claude_top_p = getattr(self._config, "top_p", None)
        if claude_top_p is not None:
            payload["top_p"] = float(claude_top_p)
        try:
            with httpx2.Client(timeout=self._request_timeout()) as http_client:
                response = http_client.post(f"{base}/v1/messages", headers=headers, json=payload)
                response.raise_for_status()
                wall_elapsed = time.monotonic() - t0
                raw_json = self._read_limited_json(response)
                text = str(raw_json["content"][0]["text"])
                usage = raw_json.get("usage", {})
                prompt_tokens = usage.get("input_tokens")
                completion_tokens = usage.get("output_tokens")
                total_tokens = (
                    (prompt_tokens + completion_tokens)
                    if prompt_tokens is not None and completion_tokens is not None
                    else None
                )
                b_info = f"claude ({self.backend_host})"
                return LLMResponse(
                    text,
                    processing_seconds=None,
                    wall_seconds=wall_elapsed,
                    backend_info=b_info,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    total_tokens=total_tokens,
                )
        except (httpx2.ConnectError, httpx2.ConnectTimeout) as exc:
            raise self._connection_error(exc) from exc
        except httpx2.HTTPError as exc:
            raise AIClientError(
                "Claude request failed. Check provider connectivity and configuration."
            ) from exc

    # ── OpenAI-compatible (GitHub Copilot, OpenAI, Azure OpenAI) ─────────────

    def _openai_compat_messages(self, system: str, messages: list[ChatMessage]) -> LLMResponse:
        t0 = time.monotonic()
        headers = inject_trace_context(
            {
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            }
        )
        payload: dict[str, Any] = {
            "model": self._config.model,
            "messages": [
                {"role": "system", "content": system},
                *[m.to_dict() for m in messages],
            ],
        }
        if self._config.reasoning_effort:
            payload["reasoning_effort"] = self._config.reasoning_effort
        max_tok = getattr(self._config, "max_tokens", None)
        if max_tok is not None:
            payload["max_tokens"] = int(max_tok)
        openai_temp = getattr(self._config, "temperature", None)
        if openai_temp is not None:
            payload["temperature"] = float(openai_temp)
        openai_top_p = getattr(self._config, "top_p", None)
        if openai_top_p is not None:
            payload["top_p"] = float(openai_top_p)
        try:
            with httpx2.Client(timeout=self._request_timeout()) as http_client:
                response = http_client.post(
                    f"{self._api_base()}/chat/completions", headers=headers, json=payload
                )
                response.raise_for_status()
                wall_elapsed = time.monotonic() - t0
                raw_json = self._read_limited_json(response)
                text = str(raw_json["choices"][0]["message"]["content"])
                usage = raw_json.get("usage", {})
                prompt_tokens = usage.get("prompt_tokens")
                completion_tokens = usage.get("completion_tokens")
                total_tokens = usage.get("total_tokens")
                b_info = f"{self.backend_type} ({self.backend_host})"
                return LLMResponse(
                    text,
                    processing_seconds=None,
                    wall_seconds=wall_elapsed,
                    backend_info=b_info,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    total_tokens=total_tokens,
                )
        except (httpx2.ConnectError, httpx2.ConnectTimeout) as exc:
            raise self._connection_error(exc) from exc
        except httpx2.HTTPError as exc:
            raise AIClientError(
                "Provider request failed. Check network access, API endpoint, and credentials."
            ) from exc

    def _try_single_ollama_stream(
        self,
        base: str,
        candidate_url: str,
        system: str,
        messages: list[ChatMessage],
        use_thinking: bool,
        max_par: int,
    ) -> Generator[str]:
        """Attempt single Ollama stream with fallback if thinking unsupported."""
        try:
            with self._track_ollama_url(candidate_url, max_parallel=max_par):
                yield from self._ollama_stream_request(base, system, messages, think=use_thinking)
                return
        except httpx2.HTTPStatusError as exc:
            if exc.response.status_code == 400 and "does not support thinking" in exc.response.text:
                self._ollama_thinking_supported = False
                with self._track_ollama_url(candidate_url, max_parallel=max_par):
                    yield from self._ollama_stream_request(base, system, messages, think=False)
                    return
            body = exc.response.text[:300].strip()
            msg_text = body or "(empty)"
            raise AIClientError(
                f"Ollama returned HTTP {exc.response.status_code}. Response: {msg_text}"
            ) from exc

    def _ollama_stream(
        self, system: str, messages: list[ChatMessage], *, enable_thinking: bool = True
    ) -> Generator[str]:
        candidates = self._get_ollama_urls_loop()
        max_par = getattr(self._config, "ollama_max_parallel", 2)
        last_exc: Exception | None = None

        for _idx, candidate_url in candidates:
            try:
                base = self._validate_base_url(
                    candidate_url,
                    purpose="Ollama",
                    allow_loopback_for_local_tooling=True,
                )
                use_thinking = enable_thinking and self._ollama_thinking_supported is not False
                yield from self._try_single_ollama_stream(
                    base, candidate_url, system, messages, use_thinking, max_par
                )
                return
            except (
                httpx2.ConnectError,
                httpx2.ConnectTimeout,
                httpx2.ReadTimeout,
                httpx2.WriteTimeout,
                httpx2.PoolTimeout,
                httpx2.TimeoutException,
                httpx2.RequestError,
                httpx2.TransportError,
                OSError,
            ) as exc:
                last_exc = exc
                continue
            except httpx2.HTTPError as exc:
                raise AIClientError(f"Ollama streaming failed: {exc}") from exc

        raise self._connection_error(last_exc or RuntimeError("All Ollama servers unreachable"))

    def _ollama_stream_request(
        self, base: str, system: str, messages: list[ChatMessage], think: bool
    ) -> Generator[str]:
        payload: dict[str, Any] = {
            "model": self._config.model,
            "stream": True,
            "messages": [
                {"role": "system", "content": system},
                *[m.to_dict() for m in messages],
            ],
        }
        if think:
            payload["think"] = True
        if self._config.reasoning_effort:
            payload["reasoning_effort"] = self._config.reasoning_effort
        with (
            httpx2.Client(timeout=self._request_timeout()) as http_client,
            http_client.stream("POST", f"{base}/api/chat", json=payload) as response,
        ):
            if response.status_code >= 400:
                response.read()
            response.raise_for_status()
            if think and self._ollama_thinking_supported is None:
                self._ollama_thinking_supported = True
            yield from _consume_streaming_lines(response, _extract_ollama_stream_tuple, "LLM")

    def _claude_stream(self, system: str, messages: list[ChatMessage]) -> Generator[str]:
        base = self._validate_base_url(
            self._config.api_base_url or CONST_URL_ANTHROPIC_API_BASE,
            purpose="Claude API",
        )
        headers = {
            "x-api-key": self._api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        payload = {
            "model": self._config.model,
            "max_tokens": 8192,
            "system": system,
            "messages": [m.to_dict() for m in messages],
            "stream": True,
        }
        try:
            with (
                httpx2.Client(timeout=self._request_timeout()) as http_client,
                http_client.stream(
                    "POST", f"{base}/v1/messages", headers=headers, json=payload
                ) as response,
            ):
                if response.status_code >= 400:
                    response.read()
                response.raise_for_status()
                yield from _consume_streaming_lines(
                    response, _extract_claude_stream_chunk, "Claude"
                )
        except (httpx2.ConnectError, httpx2.ConnectTimeout) as exc:
            raise self._connection_error(exc) from exc
        except httpx2.HTTPError as exc:
            raise AIClientError(f"Claude streaming failed: {exc}") from exc

    def _openai_compat_stream(self, system: str, messages: list[ChatMessage]) -> Generator[str]:
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        payload: dict[str, Any] = {
            "model": self._config.model,
            "messages": [
                {"role": "system", "content": system},
                *[m.to_dict() for m in messages],
            ],
            "stream": True,
        }
        if self._config.reasoning_effort:
            payload["reasoning_effort"] = self._config.reasoning_effort
        try:
            with (
                httpx2.Client(timeout=self._request_timeout()) as http_client,
                http_client.stream(
                    "POST", f"{self._api_base()}/chat/completions", headers=headers, json=payload
                ) as response,
            ):
                if response.status_code >= 400:
                    response.read()
                response.raise_for_status()
                yield from _consume_streaming_lines(
                    response, _extract_openai_stream_chunk, "Provider"
                )
        except (httpx2.ConnectError, httpx2.ConnectTimeout) as exc:
            raise self._connection_error(exc) from exc
        except httpx2.HTTPError as exc:
            raise AIClientError(f"Provider streaming failed: {exc}") from exc

    def _openai_models(self) -> list[str]:
        try:
            with httpx2.Client(timeout=self._request_timeout()) as http_client:
                response = http_client.get(
                    f"{self._api_base()}/models",
                    headers={"Authorization": f"Bearer {self._api_key}"},
                )
                response.raise_for_status()
                return [
                    model_info["id"]
                    for model_info in self._read_limited_json(response).get("data", [])
                ]
        except (httpx2.ConnectError, httpx2.ConnectTimeout) as exc:
            raise self._connection_error(exc) from exc
        except httpx2.HTTPError as exc:
            raise AIClientError(
                "Failed to list provider models. Check network access, API endpoint, "
                "and credentials."
            ) from exc

    def _api_base(self) -> str:
        if self._config.api_base_url:
            return self._validate_base_url(self._config.api_base_url, purpose="provider API")
        if self._config.provider == "copilot":
            return CONST_URL_GITHUB_COPILOT_API_BASE
        return CONST_URL_OPENAI_API_BASE


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
