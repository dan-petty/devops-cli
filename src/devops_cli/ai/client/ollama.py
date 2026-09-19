"""Ollama provider backend implementation."""

from __future__ import annotations

import logging
import time
from collections.abc import Callable, Generator
from concurrent.futures import as_completed
from typing import Any
from urllib.parse import urlparse

import httpx2

from devops_cli.ai.client.base import BaseLLMProviderMixin
from devops_cli.ai.client.models import AIClientError, LLMResponse, RequestPriority
from devops_cli.ai.client.network import (
    acquire_ollama_slot,
    active_ollama_requests,
    ollama_active_lock,
    read_limited_json,
    request_priority_scope,
)
from devops_cli.ai.client.streaming import (
    _consume_streaming_lines,
    _extract_ollama_stream_tuple,
)
from devops_cli.config.defaults import DEFAULT_AI_EVICT_KEEP_ALIVE
from devops_cli.models.ai import ChatMessage
from devops_cli.security.sanitizer import mask_secrets
from devops_cli.telemetry import ContextPropagatingThreadPoolExecutor as ThreadPoolExecutor
from devops_cli.telemetry import inject_trace_context

logger = logging.getLogger(__name__)


class OllamaProviderMixin(BaseLLMProviderMixin):
    """Mixin implementing Ollama chat, streaming, and model discovery methods."""

    def _preload_single_ollama_url(
        self,
        url: str,
        model: str | None = None,
        keep_alive: str | int = "1h",
    ) -> tuple[str, bool]:
        """Prewarm or evict model on a single Ollama endpoint."""
        target_model = model or self._config.model
        try:
            base = self._validate_base_url(
                url,
                purpose="Ollama",
                allow_loopback_for_local_tooling=True,
            )
            with httpx2.Client(timeout=self._request_timeout()) as http_client:
                res = http_client.post(
                    f"{base}/api/generate",
                    json={"model": target_model, "prompt": "", "keep_alive": keep_alive},
                )
                return (url, res.status_code == 200)
        except Exception:
            return (url, False)

    def _execute_preload_all(
        self,
        all_urls: list[str],
        on_complete: Callable[[dict[str, bool]], None] | None = None,
        model: str | None = None,
        keep_alive: str | int = "1h",
    ) -> dict[str, bool]:
        results: dict[str, bool] = {}
        with ThreadPoolExecutor(max_workers=max(len(all_urls), 1)) as executor:
            futures = [
                executor.submit(self._preload_single_ollama_url, url, model, keep_alive)
                for url in all_urls
            ]
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
        model: str | None = None,
        keep_alive: str | int = "1h",
        urls: list[str] | None = None,
        blocking: bool = True,
        on_complete: Callable[[dict[str, bool]], None] | None = None,
    ) -> dict[str, bool]:
        """Preload or evict model in VRAM across configured Ollama servers concurrently."""
        if self._config.provider != "ollama":
            return {}
        target_urls = urls if urls is not None else self._config.get_ollama_urls
        if not target_urls:
            return {}

        target_model = model or self._config.model
        with request_priority_scope(RequestPriority.AS_AVAILABLE):
            if not blocking:
                import threading

                thread = threading.Thread(
                    target=self._execute_preload_all,
                    args=(target_urls, on_complete, target_model, keep_alive),
                    name=f"ollama-prewarm-{target_model}",
                    daemon=True,
                )
                thread.start()
                return {}

            return self._execute_preload_all(
                target_urls,
                on_complete=on_complete,
                model=target_model,
                keep_alive=keep_alive,
            )

    def prewarm_models(
        self,
        *,
        model: str | None = None,
        keep_alive: str | int = "1h",
        urls: list[str] | None = None,
        blocking: bool = True,
        on_complete: Callable[[dict[str, bool]], None] | None = None,
    ) -> dict[str, bool]:
        """Prewarm model in VRAM across Ollama servers concurrently."""
        return self.preload_models(
            model=model,
            keep_alive=keep_alive,
            urls=urls,
            blocking=blocking,
            on_complete=on_complete,
        )

    def evict_models(
        self,
        *,
        model: str | None = None,
        urls: list[str] | None = None,
        blocking: bool = True,
        on_complete: Callable[[dict[str, bool]], None] | None = None,
    ) -> dict[str, bool]:
        """Evict model from VRAM immediately across Ollama nodes (keep_alive=0)."""
        return self.preload_models(
            model=model,
            keep_alive=DEFAULT_AI_EVICT_KEEP_ALIVE,
            urls=urls,
            blocking=blocking,
            on_complete=on_complete,
        )

    def prewarm_async(
        self,
        on_complete: Callable[[dict[str, bool]], None] | None = None,
        model: str | None = None,
        keep_alive: str | int = "1h",
    ) -> None:
        """Non-blocking helper to prewarm model in a background daemon thread."""
        self.preload_models(
            blocking=False,
            on_complete=on_complete,
            model=model,
            keep_alive=keep_alive,
        )

    def _get_ollama_urls_loop(self) -> list[tuple[int, str]]:
        """Return list of (index, url) tuples for Ollama failover sorted by active requests."""
        all_urls = self._config.get_ollama_urls
        n = len(all_urls)
        if n == 0:
            return [(0, "http://localhost:11434")]
        start = self._load_and_increment_rr_index(n)
        from devops_cli.ai.client import network

        self._ollama_url_index = getattr(
            self, "_global_ollama_url_index", network.global_ollama_url_index
        )
        candidate_urls = [all_urls[(start + i) % n] for i in range(n)]
        indexed_urls = list(enumerate(candidate_urls))

        max_par = getattr(self._config, "ollama_max_parallel", 2)
        with ollama_active_lock:
            sorted_candidates = sorted(
                indexed_urls,
                key=lambda item: (
                    1 if active_ollama_requests.get(item[1], 0) >= max_par else 0,
                    active_ollama_requests.get(item[1], 0),
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
        max_par: int = 1,
    ) -> LLMResponse:
        """Attempt single Ollama request with fallback if thinking is unsupported."""
        try:
            return self._ollama_request(base, system, messages, use_thinking)
        except httpx2.HTTPStatusError as exc:
            if exc.response.status_code == 400 and "does not support thinking" in exc.response.text:
                self._ollama_thinking_supported = False
                return self._ollama_request(base, system, messages, think=False)
            if exc.response.status_code == 404 and "not found" in exc.response.text.lower():
                raise httpx2.RequestError(
                    f"Model '{self._config.model}' not found on {candidate_url}: {exc.response.text.strip()}",
                    request=exc.request,
                ) from exc
            msg_text = mask_secrets(exc.response.text[:300].strip()) or "(empty)"
            raise AIClientError(
                f"Ollama returned HTTP {exc.response.status_code}. Response: {msg_text}"
            ) from exc

    def _ollama_messages(
        self,
        system: str,
        messages: list[ChatMessage],
        *,
        enable_thinking: bool = True,
        priority: RequestPriority | str | None = None,
    ) -> LLMResponse:
        candidates = [url for _idx, url in self._get_ollama_urls_loop()]
        max_par = getattr(self._config, "ollama_max_parallel", 2)
        last_exc: Exception | None = None
        remaining_candidates = list(candidates)

        while remaining_candidates:
            leased_url: str | None = None
            try:
                with acquire_ollama_slot(
                    remaining_candidates, max_parallel=max_par, priority=priority
                ) as leased_url:
                    base = self._validate_base_url(
                        leased_url,
                        purpose="Ollama",
                        allow_loopback_for_local_tooling=True,
                    )
                    use_thinking = enable_thinking and self._ollama_thinking_supported is not False
                    return self._try_single_ollama_request(
                        base, leased_url, system, messages, use_thinking
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
                if leased_url and leased_url in remaining_candidates:
                    remaining_candidates.remove(leased_url)
                continue
            except httpx2.HTTPError as exc:
                raise AIClientError(
                    f"Ollama request failed ({type(exc).__name__}). Check provider connectivity and configuration."
                ) from exc

        raise self._connection_error(last_exc or RuntimeError("All Ollama servers unreachable"))

    def _ollama_request(
        self, base: str, system: str, messages: list[ChatMessage], think: bool
    ) -> LLMResponse:
        start_time = time.monotonic()
        with httpx2.Client(timeout=self._request_timeout()) as http_client:
            payload: dict[str, Any] = {
                "model": self._config.model,
                "stream": False,
                "messages": [
                    {"role": "system", "content": system},
                    *[m.to_dict() for m in messages],
                ],
            }
            payload["think"] = bool(think)
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

            raw_res = read_limited_json(response)
            wall_elapsed = time.monotonic() - start_time

            msg = raw_res.get("message", {})
            content = str(msg.get("content", ""))
            raw_thinking = msg.get("thinking")
            thinking_str = str(raw_thinking).strip() if raw_thinking is not None else None

            from devops_cli.ai.thinking_stream import extract_think_blocks

            if "<think>" in content:
                inner_thinks, clean = extract_think_blocks(content)
                if inner_thinks:
                    combined = (thinking_str + "\n" if thinking_str else "") + "\n".join(
                        inner_thinks
                    )
                    thinking_str = combined.strip() or None
                content = clean

            text = self._strip_think_blocks(content)

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

    def _try_single_ollama_stream(
        self,
        base: str,
        candidate_url: str,
        system: str,
        messages: list[ChatMessage],
        use_thinking: bool,
        max_par: int = 1,
    ) -> Generator[str]:
        """Attempt single Ollama stream with fallback if thinking unsupported."""
        try:
            yield from self._ollama_stream_request(base, system, messages, think=use_thinking)
            return
        except httpx2.HTTPStatusError as exc:
            if exc.response.status_code == 400 and "does not support thinking" in exc.response.text:
                self._ollama_thinking_supported = False
                yield from self._ollama_stream_request(base, system, messages, think=False)
                return
            if exc.response.status_code == 404 and "not found" in exc.response.text.lower():
                raise httpx2.RequestError(
                    f"Model '{self._config.model}' not found on {candidate_url}: {exc.response.text.strip()}",
                    request=exc.request,
                ) from exc
            body = mask_secrets(exc.response.text[:300].strip())
            msg_text = body or "(empty)"
            raise AIClientError(
                f"Ollama returned HTTP {exc.response.status_code}. Response: {msg_text}"
            ) from exc

    def _ollama_stream(
        self,
        system: str,
        messages: list[ChatMessage],
        *,
        enable_thinking: bool = True,
        priority: RequestPriority | str | None = None,
    ) -> Generator[str]:
        candidates = [url for _idx, url in self._get_ollama_urls_loop()]
        max_par = getattr(self._config, "ollama_max_parallel", 2)
        last_exc: Exception | None = None
        remaining_candidates = list(candidates)

        while remaining_candidates:
            leased_url: str | None = None
            try:
                with acquire_ollama_slot(
                    remaining_candidates, max_parallel=max_par, priority=priority
                ) as leased_url:
                    base = self._validate_base_url(
                        leased_url,
                        purpose="Ollama",
                        allow_loopback_for_local_tooling=True,
                    )
                    use_thinking = enable_thinking and self._ollama_thinking_supported is not False
                    yield from self._try_single_ollama_stream(
                        base, leased_url, system, messages, use_thinking
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
                if leased_url and leased_url in remaining_candidates:
                    remaining_candidates.remove(leased_url)
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
        payload["think"] = bool(think)
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

    def _fetch_ollama_tags(self, base: str) -> list[str]:
        """Fetch available model tags from single Ollama host."""
        with httpx2.Client(timeout=self._request_timeout()) as http_client:
            response = http_client.get(f"{base}/api/tags")
            response.raise_for_status()
            models_data = read_limited_json(response).get("models", [])
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
