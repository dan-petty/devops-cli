"""Unified LLM client: Ollama, Claude (Anthropic), GitHub Copilot, and OpenAI-compatible APIs.

Architecture:
- Maps `ai.provider` settings (`ollama`, `claude`, `copilot`, `openai`) to unified REST chat calls.
- Validates base URLs before making HTTP requests, refusing non-public endpoints unless
  `allow_private_network=True` or `DEVOPS_CLI_AI_ALLOW_PRIVATE_NETWORK=true` is set.
- Wraps provider-specific error responses into `AIClientError` with user-actionable instructions.
"""

from __future__ import annotations

import ipaddress
import json
import logging
import os
import socket
import tempfile
import threading
import time
from collections.abc import Callable, Generator
from concurrent.futures import ThreadPoolExecutor, as_completed
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
from devops_cli.config.defaults import DEFAULT_HTTP_TIMEOUT_SECONDS
from devops_cli.config.settings import AIConfig
from devops_cli.http.client import request_timeout
from devops_cli.models.ai import ChatMessage
from devops_cli.telemetry import inject_trace_context, record_metric, trace_span

MAX_STREAM_BYTES = 50 * 1024 * 1024  # 50MB maximum streamed response size
logger = logging.getLogger(__name__)


class AIClientError(RuntimeError):
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
        return obj


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
        return self._config.provider

    @property
    def backend_host(self) -> str:
        """Return the endpoint host for the current AI provider."""
        p = self._config.provider
        if p == "ollama":
            urls = self._config.get_ollama_urls
            hosts: list[str] = []
            for u in urls:
                parsed = urlparse(u)
                hosts.append(parsed.netloc or parsed.path or u)
            return ", ".join(hosts)
        base_url = self._config.api_base_url
        if not base_url:
            if p == "claude":
                base_url = CONST_URL_ANTHROPIC_API_BASE
            elif p == "copilot":
                base_url = CONST_URL_GITHUB_COPILOT_API_BASE
            elif p == "openai":
                base_url = CONST_URL_OPENAI_API_BASE
        if base_url:
            parsed = urlparse(base_url)
            return str(parsed.netloc or parsed.path or base_url)
        return "unknown"

    @property
    def backend_info(self) -> str:
        """Return formatted backend type and host string, e.g. 'ollama (localhost:11434)'."""
        return f"{self.backend_type} ({self.backend_host})"

    @staticmethod
    def _strip_think_blocks(text: str) -> str:
        """Remove <think>...</think> chain-of-thought blocks emitted by thinking models."""
        return strip_think_blocks(text)

    def preload_models(
        self,
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

        def _do_preload() -> dict[str, bool]:
            results: dict[str, bool] = {}

            def _preload_single(url: str) -> tuple[str, bool]:
                try:
                    base = self._validate_base_url(
                        url,
                        purpose="Ollama",
                        allow_loopback_for_local_tooling=True,
                    )
                    with httpx2.Client(timeout=60.0) as http_client:
                        res = http_client.post(
                            f"{base}/api/generate",
                            json={"model": self._config.model, "keep_alive": "1h"},
                        )
                        return (url, res.status_code == 200)
                except Exception:
                    return (url, False)

            with ThreadPoolExecutor(max_workers=max(len(all_urls), 1)) as executor:
                futures = [executor.submit(_preload_single, url) for url in all_urls]
                for future in as_completed(futures):
                    url, ok = future.result()
                    results[url] = ok

            if on_complete is not None:
                try:
                    on_complete(results)
                except Exception as exc:
                    logger.debug("Preload on_complete callback failed: %s", exc)

            return results

        if not blocking:
            thread = threading.Thread(
                target=_do_preload,
                name=f"ollama-prewarm-{self._config.model}",
                daemon=True,
            )
            thread.start()
            return {}

        return _do_preload()

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
        if raw_str.startswith("{") and raw_str.endswith("}"):
            try:
                data = json.loads(raw_str)
                if isinstance(data, dict):
                    err_val = data.get("error")
                    err_code = data.get("error_code")
                    if (
                        isinstance(err_val, str | dict)
                        and bool(err_val)
                        and str(err_val).lower() not in ("none", "null", "no error", "0", "")
                    ) or (err_code is not None and bool(err_code)):
                        return False
            except (json.JSONDecodeError, TypeError, ValueError):
                pass

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
        with trace_span(
            "ai.llm.dispatch",
            {"provider": p, "model": self._config.model},
        ) as span_handle:
            if p == "ollama":
                res = self._ollama_messages(system, messages, enable_thinking=enable_thinking)
            elif p == "claude":
                res = self._claude_messages(system, messages)
            elif p in ("copilot", "openai"):
                res = self._openai_compat_messages(system, messages)
            else:
                raise ValueError(
                    f"Unknown provider: {p!r}. Choose: ollama, claude, copilot, openai"
                )

            if res.backend_info:
                span_handle.set_attribute("gen_ai.server.address", res.backend_info)
            if res.prompt_tokens is not None:
                span_handle.set_attribute("gen_ai.usage.prompt_tokens", res.prompt_tokens)
            if res.completion_tokens is not None:
                span_handle.set_attribute("gen_ai.usage.completion_tokens", res.completion_tokens)
            if res.total_tokens is not None:
                span_handle.set_attribute("gen_ai.usage.total_tokens", res.total_tokens)
            if res.eval_duration_ms is not None:
                span_handle.set_attribute("llm.eval_duration_ms", res.eval_duration_ms)
            if res.prompt_eval_duration_ms is not None:
                span_handle.set_attribute(
                    "llm.prompt_eval_duration_ms", res.prompt_eval_duration_ms
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
    ) -> LLMResponse:
        """Send a single-turn chat message and return the assistant reply."""
        return self.chat_messages(
            system,
            [ChatMessage(role="user", content=user)],
            enable_thinking=enable_thinking,
            validator=validator,
            max_retries=max_retries,
        )

    def chat_messages(
        self,
        system: str,
        messages: list[ChatMessage],
        *,
        enable_thinking: bool = True,
        validator: Callable[[str], bool] | None = None,
        max_retries: int | None = None,
    ) -> LLMResponse:
        """Send a multi-turn chat request with response validation and retries."""
        retries = max_retries if max_retries is not None else self._config.max_retries
        attempts = max(1, retries + 1)
        last_exc: Exception | None = None

        for attempt in range(1, attempts + 1):
            try:
                res = self._dispatch_messages(system, messages, enable_thinking=enable_thinking)
                if self._validate_response_text(res, validator):
                    return res
                last_exc = AIClientError(
                    f"Response validation failed for model '{self._config.model}' "
                    f"(attempt {attempt}/{attempts})."
                )
            except Exception as exc:
                last_exc = exc
            if attempt < attempts:
                time.sleep(0.5 * attempt)

        if isinstance(last_exc, AIClientError):
            raise last_exc
        if last_exc is not None:
            raise self._connection_error(last_exc)
        raise AIClientError("AI request failed with no valid response.")

    def chat_stream(
        self, system: str, user: str, *, enable_thinking: bool = True
    ) -> Generator[str]:
        """Send a single-turn chat message and yield streaming tokens as they arrive."""
        yield from self.chat_messages_stream(
            system,
            [ChatMessage(role="user", content=user)],
            enable_thinking=enable_thinking,
        )

    def chat_messages_stream(
        self,
        system: str,
        messages: list[ChatMessage],
        *,
        enable_thinking: bool = True,
    ) -> Generator[str]:
        """Send a multi-turn conversation and yield streaming tokens as they arrive."""
        p = self._config.provider
        if p == "ollama":
            yield from self._ollama_stream(system, messages, enable_thinking=enable_thinking)
        elif p == "claude":
            yield from self._claude_stream(system, messages)
        elif p in ("copilot", "openai"):
            yield from self._openai_compat_stream(system, messages)
        else:
            raise ValueError(f"Unknown provider: {p!r}. Choose: ollama, claude, copilot, openai")

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
        value = os.environ.get(self._ALLOW_PRIVATE_NETWORK_ENV, "")
        return value.strip().lower() in {"1", "true", "yes", "on"}

    @staticmethod
    def _is_non_public_ip(address: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
        return not address.is_global

    def _validate_base_url(
        self,
        base_url: str,
        *,
        purpose: str,
        allow_loopback_for_local_tooling: bool = False,
    ) -> str:
        parsed = urlparse(base_url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise AIClientError(f"Invalid {purpose} URL. Use a full URL with scheme and host.")

        host = parsed.hostname

        if host == "localhost" and allow_loopback_for_local_tooling:
            return base_url.rstrip("/")

        try:
            literal_ip = ipaddress.ip_address(host)
        except ValueError:
            literal_ip = None

        if literal_ip is not None:
            if allow_loopback_for_local_tooling and literal_ip.is_loopback:
                return base_url.rstrip("/")
            if self._is_non_public_ip(literal_ip) and not self._allow_private_network():
                raise AIClientError(
                    f"Refusing non-public {purpose} URL by default. "
                    f"Set {self._ALLOW_PRIVATE_NETWORK_ENV}=true to override intentionally."
                )
            return base_url.rstrip("/")

        try:
            addrinfos = socket.getaddrinfo(host, parsed.port, type=socket.SOCK_STREAM)
        except socket.gaierror:
            h_lower = host.lower()
            if (
                h_lower.endswith(".local") or h_lower.endswith(".internal")
            ) and not self._allow_private_network():
                raise AIClientError(
                    f"Refusing non-public {purpose} URL by default. "
                    f"Set {self._ALLOW_PRIVATE_NETWORK_ENV}=true to override intentionally."
                )
            return base_url.rstrip("/")

        for addrinfo in addrinfos:
            ip_str = addrinfo[4][0]
            resolved = ipaddress.ip_address(ip_str)
            if allow_loopback_for_local_tooling and resolved.is_loopback:
                continue
            if self._is_non_public_ip(resolved) and not self._allow_private_network():
                raise AIClientError(
                    f"Refusing non-public {purpose} URL by default. "
                    f"Set {self._ALLOW_PRIVATE_NETWORK_ENV}=true to override intentionally."
                )

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

    def _ollama_messages(
        self, system: str, messages: list[ChatMessage], *, enable_thinking: bool = True
    ) -> LLMResponse:
        candidates = self._get_ollama_urls_loop()
        max_par = getattr(self._config, "ollama_max_parallel", 2)
        last_exc: Exception | None = None

        for idx, candidate_url in candidates:
            try:
                base = self._validate_base_url(
                    candidate_url,
                    purpose="Ollama",
                    allow_loopback_for_local_tooling=True,
                )
                use_thinking = enable_thinking and self._ollama_thinking_supported is not False
                try:
                    with self._track_ollama_url(candidate_url, max_parallel=max_par):
                        res = self._ollama_request(base, system, messages, use_thinking)
                        return res
                except httpx2.HTTPStatusError as exc:
                    if (
                        exc.response.status_code == 400
                        and "does not support thinking" in exc.response.text
                    ):
                        self._ollama_thinking_supported = False
                        with self._track_ollama_url(candidate_url, max_parallel=max_par):
                            res = self._ollama_request(base, system, messages, think=False)
                            return res
                    msg_text = exc.response.text[:300].strip() or "(empty)"
                    raise AIClientError(
                        f"Ollama returned HTTP {exc.response.status_code}. Response: {msg_text}"
                    ) from exc
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

    def _ollama_models(self) -> list[str]:
        candidates = self._get_ollama_urls_loop()
        last_exc: Exception | None = None

        for idx, candidate_url in candidates:
            try:
                base = self._validate_base_url(
                    candidate_url,
                    purpose="Ollama",
                    allow_loopback_for_local_tooling=True,
                )
                with httpx2.Client(timeout=request_timeout()) as http_client:
                    response = http_client.get(f"{base}/api/tags")
                    response.raise_for_status()
                    return [
                        model_info["name"]
                        for model_info in self._read_limited_json(response).get("models", [])
                    ]
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
        try:
            with httpx2.Client(timeout=self._request_timeout()) as http_client:
                headers = inject_trace_context(
                    {
                        "x-api-key": self._api_key,
                        "anthropic-version": "2023-06-01",
                        "content-type": "application/json",
                    }
                )
                response = http_client.post(
                    f"{base}/v1/messages",
                    headers=headers,
                    json={
                        "model": self._config.model,
                        "max_tokens": 8192,
                        "system": system,
                        "messages": [m.to_dict() for m in messages],
                    },
                )
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
        try:
            with httpx2.Client(timeout=self._request_timeout()) as http_client:
                headers = inject_trace_context(
                    {
                        "Authorization": f"Bearer {self._api_key}",
                        "Content-Type": "application/json",
                    }
                )
                response = http_client.post(
                    f"{self._api_base()}/chat/completions",
                    headers=headers,
                    json={
                        "model": self._config.model,
                        "messages": [
                            {"role": "system", "content": system},
                            *[m.to_dict() for m in messages],
                        ],
                    },
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

    def _ollama_stream(
        self, system: str, messages: list[ChatMessage], *, enable_thinking: bool = True
    ) -> Generator[str]:
        candidates = self._get_ollama_urls_loop()
        max_par = getattr(self._config, "ollama_max_parallel", 2)
        last_exc: Exception | None = None

        for idx, candidate_url in candidates:
            try:
                base = self._validate_base_url(
                    candidate_url,
                    purpose="Ollama",
                    allow_loopback_for_local_tooling=True,
                )
                use_thinking = enable_thinking and self._ollama_thinking_supported is not False
                try:
                    with self._track_ollama_url(candidate_url, max_parallel=max_par):
                        yield from self._ollama_stream_request(
                            base, system, messages, think=use_thinking
                        )
                        return
                except httpx2.HTTPStatusError as exc:
                    if (
                        exc.response.status_code == 400
                        and "does not support thinking" in exc.response.text
                    ):
                        self._ollama_thinking_supported = False
                        with self._track_ollama_url(candidate_url, max_parallel=max_par):
                            yield from self._ollama_stream_request(
                                base, system, messages, think=False
                            )
                            return
                    body = exc.response.text[:300].strip()
                    msg_text = body or "(empty)"
                    raise AIClientError(
                        f"Ollama returned HTTP {exc.response.status_code}. Response: {msg_text}"
                    ) from exc
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
        with httpx2.Client(timeout=self._request_timeout()) as http_client:
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
            with http_client.stream("POST", f"{base}/api/chat", json=payload) as response:
                if response.status_code >= 400:
                    response.read()
                response.raise_for_status()
                if think and self._ollama_thinking_supported is None:
                    self._ollama_thinking_supported = True
                total_bytes = 0
                for line in response.iter_lines():
                    if not line:
                        continue
                    try:
                        line_data = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    msg = line_data.get("message", {})
                    content = msg.get("content", "")
                    thinking = msg.get("thinking", "")
                    if thinking:
                        chunk_str = f"<think>{thinking}</think>"
                    elif content:
                        chunk_str = str(content)
                    else:
                        continue

                    total_bytes += len(chunk_str.encode("utf-8"))
                    if total_bytes > MAX_STREAM_BYTES:
                        raise AIClientError("LLM response exceeded maximum stream size (50MB).")
                    yield chunk_str

    def _claude_stream(self, system: str, messages: list[ChatMessage]) -> Generator[str]:
        base = self._validate_base_url(
            self._config.api_base_url or CONST_URL_ANTHROPIC_API_BASE,
            purpose="Claude API",
        )
        try:
            with httpx2.Client(timeout=self._request_timeout()) as http_client:
                with http_client.stream(
                    "POST",
                    f"{base}/v1/messages",
                    headers={
                        "x-api-key": self._api_key,
                        "anthropic-version": "2023-06-01",
                        "content-type": "application/json",
                    },
                    json={
                        "model": self._config.model,
                        "max_tokens": 8192,
                        "system": system,
                        "messages": [m.to_dict() for m in messages],
                        "stream": True,
                    },
                ) as response:
                    if response.status_code >= 400:
                        response.read()
                    response.raise_for_status()
                    total_bytes = 0
                    for line in response.iter_lines():
                        if not line or not line.startswith("data:"):
                            continue
                        raw_data = line.removeprefix("data:").strip()
                        if raw_data == "[DONE]":
                            break
                        try:
                            event_json = json.loads(raw_data)
                        except json.JSONDecodeError:
                            continue
                        if event_json.get("type") == "content_block_delta":
                            delta = event_json.get("delta", {})
                            if delta.get("type") == "text_delta":
                                text_val = delta.get("text", "")
                                if text_val:
                                    chunk_str = str(text_val)
                                    total_bytes += len(chunk_str.encode("utf-8"))
                                    if total_bytes > MAX_STREAM_BYTES:
                                        raise AIClientError(
                                            "Claude response exceeded maximum stream size (50MB)."
                                        )
                                    yield chunk_str
        except (httpx2.ConnectError, httpx2.ConnectTimeout) as exc:
            raise self._connection_error(exc) from exc
        except httpx2.HTTPError as exc:
            raise AIClientError(f"Claude streaming failed: {exc}") from exc

    def _openai_compat_stream(self, system: str, messages: list[ChatMessage]) -> Generator[str]:
        try:
            with httpx2.Client(timeout=self._request_timeout()) as http_client:
                with http_client.stream(
                    "POST",
                    f"{self._api_base()}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self._api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": self._config.model,
                        "messages": [
                            {"role": "system", "content": system},
                            *[m.to_dict() for m in messages],
                        ],
                        "stream": True,
                    },
                ) as response:
                    if response.status_code >= 400:
                        response.read()
                    response.raise_for_status()
                    total_bytes = 0
                    for line in response.iter_lines():
                        if not line or not line.startswith("data:"):
                            continue
                        raw_data = line.removeprefix("data:").strip()
                        if raw_data == "[DONE]":
                            break
                        try:
                            event_json = json.loads(raw_data)
                        except json.JSONDecodeError:
                            continue
                        choices = event_json.get("choices", [])
                        if choices:
                            delta = choices[0].get("delta", {})
                            content = delta.get("content")
                            if content:
                                chunk_str = str(content)
                                total_bytes += len(chunk_str.encode("utf-8"))
                                if total_bytes > MAX_STREAM_BYTES:
                                    raise AIClientError(
                                        "Provider response exceeded maximum stream size (50MB)."
                                    )
                                yield chunk_str
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
