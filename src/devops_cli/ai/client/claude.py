"""Anthropic Claude provider backend implementation."""

from __future__ import annotations

import logging
import time
from collections.abc import Generator, Iterator
from contextlib import contextmanager
from typing import TYPE_CHECKING, Any

import httpx2

from devops_cli.ai.client.base import BaseLLMProviderMixin, _clean_http_error_body
from devops_cli.ai.client.models import (
    AIClientError,
    CallSampling,
    LLMResponse,
    origin_label,
    provider_finish_reason,
)
from devops_cli.ai.client.network import (
    StreamUsage,
    reply_schema,
    stream_finish_reason,
    stream_usage,
)
from devops_cli.config.constants import CONST_ANTHROPIC_STOP_REASONS, CONST_URL_ANTHROPIC_API_BASE
from devops_cli.models.ai import ChatMessage
from devops_cli.telemetry import inject_trace_context

if TYPE_CHECKING:
    import anthropic

logger = logging.getLogger(__name__)

_CLAUDE_MODEL_CAPABILITIES: dict[str, Any] = {}


def reset_claude_model_capabilities() -> None:
    """Reset the process-wide cache of Claude model capabilities."""
    _CLAUDE_MODEL_CAPABILITIES.clear()


def _get_model_capabilities(sdk_client: Any, model: str) -> Any:
    """Retrieve capabilities for a model from Anthropic Models API, cached per process."""
    if not model:
        return None
    if model in _CLAUDE_MODEL_CAPABILITIES:
        return _CLAUDE_MODEL_CAPABILITIES[model]
    import anthropic

    try:
        info = sdk_client.models.retrieve(model)
        if info and getattr(info, "capabilities", None) is not None:
            _CLAUDE_MODEL_CAPABILITIES[model] = info.capabilities
            return info.capabilities
    except anthropic.APIError as exc:
        logger.debug("Failed to retrieve capabilities for Claude model %s: %s", model, exc)
    _CLAUDE_MODEL_CAPABILITIES[model] = None
    return None


def _capabilities_support_adaptive_thinking(capabilities: Any) -> bool:
    """Return True if model capabilities declare adaptive thinking support."""
    if capabilities is None:
        return False
    thinking = getattr(capabilities, "thinking", None)
    if thinking is None and isinstance(capabilities, dict):
        thinking = capabilities.get("thinking")
    if thinking is None:
        return False
    if isinstance(thinking, dict):
        types = thinking.get("types", {})
        adaptive = types.get("adaptive", {})
        return bool(adaptive.get("supported", False))
    types = getattr(thinking, "types", None)
    if types is not None:
        adaptive = getattr(types, "adaptive", None)
        if adaptive is not None:
            return bool(getattr(adaptive, "supported", False))
    return False


def _capabilities_support_sampling(capabilities: Any) -> bool:
    """Return True if model capabilities declare sampling support."""
    if capabilities is None:
        return False
    if isinstance(capabilities, dict):
        sampling = capabilities.get("sampling", {})
        if isinstance(sampling, dict):
            return bool(sampling.get("supported", False))
        return bool(getattr(sampling, "supported", False))
    extra = getattr(capabilities, "model_extra", None) or {}
    sampling = extra.get("sampling") or getattr(capabilities, "sampling", None)
    if isinstance(sampling, dict):
        return bool(sampling.get("supported", False))
    if sampling is not None:
        return bool(getattr(sampling, "supported", False))
    return False


def _build_anthropic_kwargs(
    config: Any,
    sdk_client: anthropic.Anthropic,
    system: str,
    messages: list[ChatMessage],
    completion_limit: int | None,
    *,
    enable_thinking: bool = True,
    sampling: CallSampling | None = None,
) -> dict[str, Any]:
    """Construct Messages API parameters with dynamic capabilities and sampling parity.

    A per-call `temperature` or `top_p` replaces the configured one under the same gate. The
    Messages API takes no seed, so a per-call seed is not sent."""
    model_name = getattr(config, "model", "") or ""
    clean_model = model_name.replace(":thinking", "").strip()
    caps = _get_model_capabilities(sdk_client, clean_model)

    supports_reasoning = bool(getattr(config, "supports_reasoning", False))
    adaptive_supported = supports_reasoning or _capabilities_support_adaptive_thinking(caps)
    use_adaptive = enable_thinking and adaptive_supported

    max_tok = completion_limit or 8192
    kwargs: dict[str, Any] = {
        "model": clean_model,
        "max_tokens": int(max_tok),
        "system": system,
        "messages": [m.to_dict() for m in messages],
    }

    output_config: dict[str, Any] = {}
    if use_adaptive:
        kwargs["thinking"] = {"type": "adaptive"}
        output_config["effort"] = getattr(config, "reasoning_effort", None) or "medium"
    schema = reply_schema.get()
    output_format = schema.anthropic_output_format(clean_model) if schema is not None else None
    if output_format is not None:
        output_config["format"] = output_format
    if output_config:
        kwargs["output_config"] = output_config

    send_sampling = (
        _capabilities_support_sampling(caps)
        and not use_adaptive
        and not getattr(config, "use_model_sampling", False)
    )
    extra_body: dict[str, Any] = {}
    if send_sampling:
        chosen = (sampling or CallSampling()).over(config)
        if chosen.temperature is not None:
            extra_body["temperature"] = float(chosen.temperature)
        if chosen.top_p is not None:
            extra_body["top_p"] = float(chosen.top_p)
    if extra_body:
        kwargs["extra_body"] = extra_body

    return kwargs


def _extract_claude_content(content: Any) -> tuple[str, str | None]:
    """Extract text and thinking strings from Anthropic response content blocks."""
    text_parts: list[str] = []
    thinking_parts: list[str] = []
    for block in content or []:
        b_type = getattr(block, "type", None) or (
            block.get("type") if isinstance(block, dict) else None
        )
        if b_type == "text":
            text_parts.append(
                getattr(block, "text", "") if hasattr(block, "text") else str(block.get("text", ""))
            )
        elif b_type == "thinking":
            thinking_parts.append(
                getattr(block, "thinking", "")
                if hasattr(block, "thinking")
                else str(block.get("thinking", ""))
            )
    text = "\n".join(text_parts).strip()
    thinking_str = "\n".join(thinking_parts).strip() or None
    return text, thinking_str


def _extract_claude_usage(usage: Any) -> tuple[int | None, int | None, int | None]:
    """Extract input, output, and total token usage from Anthropic usage structure."""
    if not usage:
        return None, None, None
    prompt = getattr(usage, "input_tokens", None)
    completion = getattr(usage, "output_tokens", None)
    total = (prompt + completion) if prompt is not None and completion is not None else None
    return prompt, completion, total


def _update_stream_telemetry(event: Any) -> None:
    """Record input tokens, output tokens, and finish reason from streaming events."""
    ev_type = getattr(event, "type", None)
    if ev_type == "message_start":
        msg = getattr(event, "message", None)
        usage = getattr(msg, "usage", None) if msg else None
        if usage and getattr(usage, "input_tokens", None) is not None:
            stream_usage.set(StreamUsage(prompt_tokens=usage.input_tokens))
    elif ev_type == "message_delta":
        delta = getattr(event, "delta", None)
        stop_reason = getattr(delta, "stop_reason", None) if delta else None
        if stop_reason:
            stream_finish_reason.set(
                provider_finish_reason(CONST_ANTHROPIC_STOP_REASONS, stop_reason)
            )
        usage = getattr(event, "usage", None)
        if usage and getattr(usage, "output_tokens", None) is not None:
            curr = stream_usage.get()
            in_tok = curr.prompt_tokens if curr else None
            out_tok = usage.output_tokens
            tot = (in_tok + out_tok) if in_tok is not None else None
            stream_usage.set(
                StreamUsage(prompt_tokens=in_tok, completion_tokens=out_tok, total_tokens=tot)
            )


def _handle_stream_event(event: Any) -> str | None:
    """Extract chunk text/thinking or update telemetry from a stream event."""
    ev_type = getattr(event, "type", None)
    if ev_type == "text":
        return str(event.text)
    if ev_type == "thinking":
        return f"<think>{event.thinking}</think>"
    _update_stream_telemetry(event)
    return None


def _finalize_stream_telemetry(stream: Any) -> None:
    """Update stream usage and finish reason with final message data if available."""
    import anthropic

    try:
        final_msg = stream.get_final_message()
        if not final_msg:
            return
        stop_reason = getattr(final_msg, "stop_reason", None)
        if stop_reason:
            stream_finish_reason.set(
                provider_finish_reason(CONST_ANTHROPIC_STOP_REASONS, stop_reason)
            )
        usage = getattr(final_msg, "usage", None)
        if usage:
            in_tok = getattr(usage, "input_tokens", None)
            out_tok = getattr(usage, "output_tokens", None)
            tot = (in_tok + out_tok) if in_tok is not None and out_tok is not None else None
            stream_usage.set(
                StreamUsage(prompt_tokens=in_tok, completion_tokens=out_tok, total_tokens=tot)
            )
    except (anthropic.AnthropicError, RuntimeError, ValueError) as exc:
        logger.debug("Could not finalize Claude stream telemetry: %s", exc)


@contextmanager
def _map_anthropic_errors(self_obj: Any, failure: str) -> Iterator[None]:
    """Map Anthropic SDK exceptions to standardized AI client errors."""
    import anthropic

    try:
        yield
    except anthropic.APIConnectionError as exc:
        error = self_obj._connection_error(exc)
        error.timed_out = isinstance(exc, anthropic.APITimeoutError)
        raise error from exc
    except anthropic.APIStatusError as exc:
        if exc.status_code in (401, 403):
            from devops_cli.ai.client.models import credentials_error

            raise credentials_error(
                "The Claude provider", has_key=bool(self_obj._api_key), status=exc.status_code
            ) from exc
        from devops_cli.security.sanitizer import mask_secrets

        resp_text = exc.response.text if exc.response is not None else ""
        cleaned = _clean_http_error_body(resp_text)
        detail = f": {mask_secrets(cleaned)}" if cleaned else ""
        raise AIClientError(
            f"Provider request failed with HTTP {exc.status_code}{detail}", status=exc.status_code
        ) from exc
    except (httpx2.ConnectError, httpx2.ConnectTimeout) as exc:
        raise self_obj._connection_error(exc) from exc
    except httpx2.HTTPError as exc:
        raise self_obj._provider_http_error(exc, failure) from exc


class ClaudeProviderMixin(BaseLLMProviderMixin):
    """Mixin implementing Claude Anthropic Messages API calls and streams."""

    @property
    def _anthropic_client(self) -> anthropic.Anthropic:
        """Construct Anthropic SDK client bound to the factory-built shared HTTP client."""
        import anthropic

        base = self._validate_base_url(
            self._config.api_base_url or CONST_URL_ANTHROPIC_API_BASE,
            purpose="Claude API",
        )
        base = base.rstrip("/")
        if base.endswith("/v1"):
            base = base[:-3]
        timeout_val = getattr(self._request_timeout(), "read", None) or 60.0
        return anthropic.Anthropic(
            api_key=self._api_key or "none",
            base_url=base,
            http_client=self._shared_client(),
            default_headers=inject_trace_context({}),
            max_retries=0,
            timeout=float(timeout_val),
        )

    def _claude_messages(
        self,
        system: str,
        messages: list[ChatMessage],
        *,
        enable_thinking: bool = True,
        sampling: CallSampling | None = None,
    ) -> LLMResponse:
        sdk_client = self._anthropic_client
        kwargs = _build_anthropic_kwargs(
            self._config,
            sdk_client,
            system,
            messages,
            self._completion_limit(),
            enable_thinking=enable_thinking,
            sampling=sampling,
        )
        start_time = time.monotonic()
        with _map_anthropic_errors(
            self, "Claude request failed. Check provider connectivity and configuration."
        ):
            res = sdk_client.messages.create(**kwargs)
        wall_elapsed = time.monotonic() - start_time

        text, thinking_str = _extract_claude_content(getattr(res, "content", None))
        prompt_tokens, completion_tokens, total_tokens = _extract_claude_usage(
            getattr(res, "usage", None)
        )
        model_name = getattr(res, "model", None) or kwargs.get("model")
        stop_reason = getattr(res, "stop_reason", None)
        origin = httpx2.URL(str(sdk_client.base_url)).origin
        return LLMResponse(
            text,
            processing_seconds=None,
            wall_seconds=wall_elapsed,
            backend_info=f"claude ({origin_label(origin)})",
            origin=origin,
            thinking=thinking_str,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            model=model_name,
            finish_reason=provider_finish_reason(CONST_ANTHROPIC_STOP_REASONS, stop_reason),
        )

    def _claude_stream(
        self,
        system: str,
        messages: list[ChatMessage],
        *,
        enable_thinking: bool = True,
    ) -> Generator[str]:
        sdk_client = self._anthropic_client
        kwargs = _build_anthropic_kwargs(
            self._config,
            sdk_client,
            system,
            messages,
            self._completion_limit(),
            enable_thinking=enable_thinking,
        )
        with _map_anthropic_errors(self, "Claude streaming failed."):
            with sdk_client.messages.stream(**kwargs) as stream:
                for event in stream:
                    chunk = _handle_stream_event(event)
                    if chunk is not None:
                        yield chunk
                _finalize_stream_telemetry(stream)
