"""OpenAI and GitHub Copilot provider backend implementation."""

from __future__ import annotations

import logging
import time
from collections.abc import Generator
from contextlib import AbstractContextManager, nullcontext
from typing import TYPE_CHECKING, Any, cast

import httpx2

if TYPE_CHECKING:
    import openai

from devops_cli.ai.client import network
from devops_cli.ai.client.base import BaseLLMProviderMixin, _clean_http_error_body
from devops_cli.ai.client.models import (
    AIClientError,
    LLMResponse,
    credentials_error,
    provider_finish_reason,
)
from devops_cli.ai.client.network import (
    StreamUsage,
    _read_limited_body,
    acquire_gateway_slot,
    extract_served_by,
    extract_served_model,
    reply_schema,
    stream_finish_reason,
    stream_model,
    stream_served_by,
    stream_served_model,
    stream_slot_wait,
    stream_usage,
    uses_gateway_slots,
)
from devops_cli.config.constants import (
    CONST_AI_GATEWAY_PROVIDER,
    CONST_OPENAI_FINISH_REASONS,
    CONST_URL_GITHUB_COPILOT_API_BASE,
)
from devops_cli.exceptions import ConfigurationError
from devops_cli.models.ai import ChatMessage
from devops_cli.security.sanitizer import mask_secrets
from devops_cli.telemetry import inject_trace_context

logger = logging.getLogger(__name__)


class OpenAICompatProviderMixin(BaseLLMProviderMixin):
    """Mixin implementing OpenAI-compatible and GitHub Copilot completions."""

    def _openai_client(self) -> openai.OpenAI:
        import openai

        shared = self._shared_client()
        cached = getattr(self, "_cached_openai_client", None)
        if cached is not None and getattr(cached, "_client", None) is shared:
            return cast("openai.OpenAI", cached)

        if self._config.provider == "gateway":
            gw_url = getattr(self._config, "gateway_url", None)
            if not gw_url:
                raise ConfigurationError(
                    "No AI gateway URL configured. Run: devops config set ai.gateway_url <url>",
                    key="ai.gateway_url",
                )
            base_url: str | None = self._validate_base_url(gw_url, purpose="provider API")
        elif self._config.api_base_url:
            base_url = self._validate_base_url(self._config.api_base_url, purpose="provider API")
        elif self._config.provider in ("copilot", "github_copilot"):
            base_url = CONST_URL_GITHUB_COPILOT_API_BASE
        else:
            base_url = None

        client = openai.OpenAI(
            base_url=base_url,
            api_key=self._api_key or "none",
            http_client=shared,
            max_retries=0,
            timeout=self._request_timeout(),
        )
        self._cached_openai_client = client
        return client

    def _api_base(self) -> str:
        return str(self._openai_client().base_url).rstrip("/")

    def _map_openai_error(self, exc: Exception) -> AIClientError:
        import openai

        if isinstance(exc, openai.APIStatusError):
            status = exc.status_code
            if status in (401, 403):
                provider_name = getattr(self._config, "provider", "AI")
                has_key = bool(getattr(self, "_api_key", None))
                return credentials_error(
                    f"The {provider_name} provider", has_key=has_key, status=status
                )
            raw_body = getattr(getattr(exc, "response", None), "text", "") or ""
            cleaned = _clean_http_error_body(raw_body)
            detail = f": {mask_secrets(cleaned)}" if cleaned else ""
            return AIClientError(f"Provider request failed with HTTP {status}{detail}")
        if isinstance(exc, openai.APIConnectionError):
            return self._connection_error(exc)
        if isinstance(exc, AIClientError):
            return exc
        return AIClientError(f"Provider request failed: {exc}")

    def _supports_reasoning(self) -> bool:
        """Return True if model declared reasoning capability via gateway or direct config."""
        if getattr(self._config, "supports_reasoning", False):
            return True
        if self._config.provider == "gateway":
            from devops_cli.ai.gateway import is_gateway_model_reasoning

            gw_url = getattr(self._config, "gateway_url", None)
            if not gw_url:
                return False
            allow_private = getattr(self._config, "allow_private_network", False)
            return is_gateway_model_reasoning(
                self._config.model,
                gateway_url=gw_url,
                allow_private=allow_private,
                api_key=self._api_key,
            )
        return False

    def _apply_sampling_and_limits(self, params: dict[str, Any], *, enable_thinking: bool) -> None:
        limit = self._completion_limit()
        if self._supports_reasoning():
            if enable_thinking:
                effort = self._config.reasoning_effort or "medium"
                params["reasoning_effort"] = effort
            if limit is not None:
                params["max_completion_tokens"] = limit
            return

        if limit is not None:
            params["max_tokens"] = limit
        if not getattr(self._config, "use_model_sampling", False):
            temp = getattr(self._config, "temperature", None)
            if temp is not None:
                params["temperature"] = float(temp)
            top_p = getattr(self._config, "top_p", None)
            if top_p is not None:
                params["top_p"] = float(top_p)

    def _prepare_params(
        self,
        system: str,
        messages: list[ChatMessage],
        *,
        stream: bool = False,
        enable_thinking: bool = True,
    ) -> dict[str, Any]:
        extra_headers: dict[str, Any] = inject_trace_context({})
        if not self._api_key:
            import openai

            extra_headers["Authorization"] = openai.omit
        params: dict[str, Any] = {
            "model": self._config.model,
            "messages": [
                {"role": "system", "content": system},
                *[m.to_dict() for m in messages],
            ],
            "timeout": self._request_timeout(),
            "extra_headers": extra_headers,
        }
        if stream:
            params["stream"] = True
            params["stream_options"] = {"include_usage": True}

        self._apply_sampling_and_limits(params, enable_thinking=enable_thinking)

        schema = reply_schema.get()
        if schema is not None and self._config.provider == CONST_AI_GATEWAY_PROVIDER:
            params["response_format"] = {
                "type": "json_schema",
                "json_schema": {"name": schema.name, "schema": schema.json_schema},
            }
        return params

    @staticmethod
    def _extract_inline_thinking(content: str, thinking_str: str | None) -> tuple[str, str | None]:
        """Extract inline <think> tags from response body if present."""
        if "<think>" not in content:
            return content, thinking_str
        from devops_cli.ai.thinking_stream import extract_think_blocks

        inner_thinks, clean = extract_think_blocks(content)
        if not inner_thinks:
            return clean, thinking_str
        combined = (thinking_str + "\n" if thinking_str else "") + "\n".join(inner_thinks)
        return clean, combined.strip() or None

    def _gateway_slot(self) -> AbstractContextManager[float]:
        """One of the gateway's backend slots for a gateway chat call, yielding the seconds spent
        waiting for it; other providers take none and wait none.

        The slot is held across the transport's own retries, so one logical call is one slot.
        """
        if uses_gateway_slots(self._config):
            return acquire_gateway_slot()
        return nullcontext(0.0)

    def _openai_compat_messages(
        self,
        system: str,
        messages: list[ChatMessage],
        *,
        enable_thinking: bool = True,
    ) -> LLMResponse:
        import openai

        params = self._prepare_params(system, messages, enable_thinking=enable_thinking)
        with self._gateway_slot():
            start_time = time.monotonic()
            try:
                with self._openai_client().chat.completions.with_streaming_response.create(
                    **params
                ) as response:
                    body = _read_limited_body(
                        response.http_response, network.DEFAULT_AI_MAX_RESPONSE_BYTES
                    )
                    response.http_response._content = bytes(body)
                    reply_headers = response.headers
                    parsed = response.parse()
                wall_elapsed = time.monotonic() - start_time
            except (openai.APIStatusError, openai.APIConnectionError) as exc:
                raise self._map_openai_error(exc) from exc
            except (httpx2.ConnectError, httpx2.ConnectTimeout) as exc:
                raise self._connection_error(exc) from exc
            except httpx2.HTTPError as exc:
                raise self._provider_http_error(
                    exc,
                    "Provider request failed. Check network access, API endpoint, and credentials.",
                ) from exc

            choices = parsed.choices if parsed.choices else []
            first_choice = choices[0] if choices else None
            msg = first_choice.message if first_choice else None
            raw_content = str(getattr(msg, "content", "") or "")
            extra = getattr(msg, "model_extra", None) or {}
            choice_extra = getattr(first_choice, "model_extra", None) or {}
            raw_reasoning = (
                getattr(msg, "reasoning_content", None)
                or getattr(msg, "reasoning", None)
                or getattr(first_choice, "reasoning", None)
                or extra.get("reasoning_content")
                or extra.get("reasoning")
                or choice_extra.get("reasoning")
            )
            thinking_str = str(raw_reasoning).strip() if raw_reasoning else None
            content, thinking_str = self._extract_inline_thinking(raw_content, thinking_str)

            usage = parsed.usage
            details = getattr(usage, "completion_tokens_details", None) if usage else None
            reasoning_tokens = getattr(details, "reasoning_tokens", None) if details else None
            b_info = f"{self.backend_type} ({self.backend_host})"

            raw_finish = getattr(first_choice, "finish_reason", None) if first_choice else None
            finish_reason = provider_finish_reason(CONST_OPENAI_FINISH_REASONS, raw_finish)

            return LLMResponse(
                content,
                processing_seconds=None,
                wall_seconds=wall_elapsed,
                backend_info=b_info,
                thinking=thinking_str,
                prompt_tokens=getattr(usage, "prompt_tokens", None) if usage else None,
                completion_tokens=getattr(usage, "completion_tokens", None) if usage else None,
                total_tokens=getattr(usage, "total_tokens", None) if usage else None,
                served_by=extract_served_by(reply_headers),
                served_model=extract_served_model(reply_headers),
                model=parsed.model,
                finish_reason=finish_reason,
                reasoning_tokens=reasoning_tokens,
            )

    def _openai_compat_stream(
        self,
        system: str,
        messages: list[ChatMessage],
        *,
        enable_thinking: bool = True,
    ) -> Generator[str]:
        import openai

        params = self._prepare_params(
            system, messages, stream=True, enable_thinking=enable_thinking
        )
        try:
            with self._gateway_slot() as slot_wait:
                stream_slot_wait.set(slot_wait)
                stream = self._openai_client().chat.completions.create(**params)
                try:
                    yield from _consume_stream(stream)
                finally:
                    stream.close()
        except (openai.APIStatusError, openai.APIConnectionError) as exc:
            raise self._map_openai_error(exc) from exc
        except (httpx2.ConnectError, httpx2.ConnectTimeout) as exc:
            raise self._connection_error(exc) from exc
        except httpx2.HTTPError as exc:
            raise self._provider_http_error(exc, f"Provider streaming failed: {exc}") from exc

    def _openai_models(self) -> list[str]:
        import openai

        extra_headers: dict[str, Any] = inject_trace_context({})
        if not self._api_key:
            extra_headers["Authorization"] = openai.omit
        try:
            with self._openai_client().models.with_streaming_response.list(
                timeout=self._request_timeout(),
                extra_headers=extra_headers,
            ) as response:
                body = _read_limited_body(
                    response.http_response, network.DEFAULT_AI_MAX_RESPONSE_BYTES
                )
                response.http_response._content = bytes(body)
                listing = response.parse()
            return [model_info.id for model_info in listing.data]
        except (openai.APIStatusError, openai.APIConnectionError) as exc:
            raise self._map_openai_error(exc) from exc
        except (httpx2.ConnectError, httpx2.ConnectTimeout) as exc:
            raise self._connection_error(exc) from exc
        except httpx2.HTTPError as exc:
            raise self._provider_http_error(
                exc,
                "Failed to list provider models. Check network access, API endpoint, and credentials.",
            ) from exc


def _record_stream_response_headers(stream: Any) -> None:
    if not hasattr(stream, "response") or stream.response is None:
        return
    resp_headers = getattr(stream.response, "headers", None)
    if resp_headers:
        stream_served_by.set(extract_served_by(resp_headers))
        stream_served_model.set(extract_served_model(resp_headers))


def _record_stream_chunk_usage(chunk: Any) -> None:
    model = getattr(chunk, "model", None)
    if model and stream_model.get() is None:
        stream_model.set(str(model))

    usage = getattr(chunk, "usage", None)
    if usage is None:
        return
    details = getattr(usage, "completion_tokens_details", None)
    r_tok = getattr(details, "reasoning_tokens", None) if details else None
    p_tok = getattr(usage, "prompt_tokens", None)
    c_tok = getattr(usage, "completion_tokens", None)
    t_tok = getattr(usage, "total_tokens", None)
    if p_tok is not None or c_tok is not None:
        stream_usage.set(
            StreamUsage(
                prompt_tokens=p_tok,
                completion_tokens=c_tok,
                total_tokens=t_tok,
                reasoning_tokens=r_tok,
            )
        )


def _process_stream_choice(choice: Any) -> Generator[str]:
    reason = getattr(choice, "finish_reason", None)
    if reason is not None:
        stream_finish_reason.set(provider_finish_reason(CONST_OPENAI_FINISH_REASONS, reason))

    delta = getattr(choice, "delta", None)
    if delta is None:
        return
    extra = getattr(delta, "model_extra", None) or {}
    reasoning = (
        getattr(delta, "reasoning_content", None)
        or extra.get("reasoning_content")
        or extra.get("reasoning")
    )
    if reasoning:
        yield f"<think>{reasoning}</think>"
    content = getattr(delta, "content", None)
    if content:
        yield str(content)


def _consume_stream(stream: Any) -> Generator[str]:
    _record_stream_response_headers(stream)
    seen_done = [False]
    orig_iter_events = getattr(stream, "_iter_events", None)
    if callable(orig_iter_events):

        def _wrapped_iter_events() -> Any:
            for sse in orig_iter_events():
                if getattr(sse, "data", "").startswith("[DONE]"):
                    seen_done[0] = True
                yield sse

        stream._iter_events = _wrapped_iter_events

    for chunk in stream:
        _record_stream_chunk_usage(chunk)
        choices = getattr(chunk, "choices", None)
        if choices:
            yield from _process_stream_choice(choices[0])

    if not seen_done[0] and stream_finish_reason.get() is None:
        raise AIClientError("Provider stream ended before its final frame.")
