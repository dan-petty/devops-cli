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
import os
import re
import socket
import threading
import time
from collections.abc import Generator
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any
from urllib.parse import urlparse

import httpx2

from devops_cli.config.constants import (
    CONST_URL_ANTHROPIC_API_BASE,
    CONST_URL_GITHUB_COPILOT_API_BASE,
    CONST_URL_OPENAI_API_BASE,
)
from devops_cli.config.defaults import DEFAULT_HTTP_TIMEOUT_SECONDS
from devops_cli.config.settings import AIConfig
from devops_cli.http.client import request_timeout
from devops_cli.models.ai import ChatMessage

MAX_STREAM_BYTES = 50 * 1024 * 1024  # 50MB maximum streamed response size


class AIClientError(RuntimeError):
    """Raised when an AI provider request fails with a user-actionable message."""


class LLMResponse(str):
    """String response from LLM with optional execution timing metadata."""

    processing_seconds: float | None
    wall_seconds: float

    def __new__(
        cls,
        content: str,
        processing_seconds: float | None = None,
        wall_seconds: float = 0.0,
    ) -> LLMResponse:
        obj = super().__new__(cls, content)
        obj.processing_seconds = processing_seconds
        obj.wall_seconds = wall_seconds
        return obj


class LLMClient:
    """Unified chat-completion client across AI providers."""

    _ALLOW_PRIVATE_NETWORK_ENV = "DEVOPS_CLI_AI_ALLOW_PRIVATE_NETWORK"

    def __init__(
        self,
        config: AIConfig,
        api_key: str | None = None,
        *,
        request_timeout_seconds: float | None = None,
    ) -> None:
        self._config = config
        self._api_key = api_key or ""
        self._request_timeout_seconds = request_timeout_seconds
        self._ollama_thinking_supported: bool | None = None  # None = unknown
        self._ollama_url_index: int = 0
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

    @staticmethod
    def _strip_think_blocks(text: str) -> str:
        """Remove <think>...</think> chain-of-thought blocks emitted by thinking models."""
        return re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()

    def preload_models(self) -> dict[str, bool]:
        """Preload configured model into VRAM across all configured Ollama servers concurrently."""
        if self._config.provider != "ollama":
            return {}
        all_urls = self._config.get_ollama_urls
        if not all_urls:
            return {}

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

        return results

    def chat(self, system: str, user: str, *, enable_thinking: bool = True) -> LLMResponse:
        """Send a single-turn chat message and return the assistant reply."""
        return self.chat_messages(
            system,
            [ChatMessage(role="user", content=user)],
            enable_thinking=enable_thinking,
        )

    def chat_messages(
        self,
        system: str,
        messages: list[ChatMessage],
        *,
        enable_thinking: bool = True,
    ) -> LLMResponse:
        """Send a multi-turn conversation and return the assistant reply."""
        p = self._config.provider
        if p == "ollama":
            return self._ollama_messages(system, messages, enable_thinking=enable_thinking)
        if p == "claude":
            res_claude = self._claude_messages(system, messages)
            return LLMResponse(
                self._strip_think_blocks(res_claude),
                processing_seconds=res_claude.processing_seconds,
                wall_seconds=res_claude.wall_seconds,
            )
        if p in ("copilot", "openai"):
            res_openai = self._openai_compat_messages(system, messages)
            return LLMResponse(
                self._strip_think_blocks(res_openai),
                processing_seconds=res_openai.processing_seconds,
                wall_seconds=res_openai.wall_seconds,
            )
        raise ValueError(f"Unknown provider: {p!r}. Choose: ollama, claude, copilot, openai")

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

        raw_res: dict[str, Any] = response.json()
        return raw_res

    def _get_ollama_urls_loop(self) -> list[tuple[int, str]]:
        """Return list of (index, url) tuples for Ollama failover, advancing starting index."""
        all_urls = self._config.get_ollama_urls
        n = len(all_urls)
        if n == 0:
            return [(0, "http://localhost:11434")]
        with self._ollama_url_lock:
            start = self._ollama_url_index % n
            self._ollama_url_index = (start + 1) % n
        return [((start + i) % n, all_urls[(start + i) % n]) for i in range(n)]

    def _ollama_messages(
        self, system: str, messages: list[ChatMessage], *, enable_thinking: bool = True
    ) -> LLMResponse:
        candidates = self._get_ollama_urls_loop()
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
                    res = self._ollama_request(base, system, messages, use_thinking)
                    return res
                except httpx2.HTTPStatusError as exc:
                    if (
                        exc.response.status_code == 400
                        and "does not support thinking" in exc.response.text
                    ):
                        self._ollama_thinking_supported = False
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
                httpx2.TimeoutException,
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
            response = http_client.post(f"{base}/api/chat", json=payload)
            response.raise_for_status()
            if think and self._ollama_thinking_supported is None:
                self._ollama_thinking_supported = True

            raw_res = self._read_limited_json(response)
            wall_elapsed = time.monotonic() - t0

            msg = raw_res.get("message", {})
            content = str(msg.get("content", ""))
            text = content if "thinking" in msg else self._strip_think_blocks(content)

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

            return LLMResponse(text, processing_seconds=proc_sec, wall_seconds=wall_elapsed)

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
                httpx2.TimeoutException,
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
                response = http_client.post(
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
                    },
                )
                response.raise_for_status()
                wall_elapsed = time.monotonic() - t0
                text = str(self._read_limited_json(response)["content"][0]["text"])
                return LLMResponse(text, processing_seconds=None, wall_seconds=wall_elapsed)
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
                response = http_client.post(
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
                    },
                )
                response.raise_for_status()
                wall_elapsed = time.monotonic() - t0
                text = str(self._read_limited_json(response)["choices"][0]["message"]["content"])
                return LLMResponse(text, processing_seconds=None, wall_seconds=wall_elapsed)
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
                        yield from self._ollama_stream_request(base, system, messages, think=False)
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
                httpx2.TimeoutException,
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
