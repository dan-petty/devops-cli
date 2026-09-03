"""Anthropic Claude provider backend implementation."""

from __future__ import annotations

import logging
import time
from collections.abc import Generator
from typing import Any

import httpx2

from devops_cli.ai.client.base import BaseLLMProviderMixin
from devops_cli.ai.client.models import AIClientError, LLMResponse
from devops_cli.ai.client.network import read_limited_json
from devops_cli.ai.client.streaming import (
    _consume_streaming_lines,
    _extract_claude_stream_chunk,
)
from devops_cli.config.constants import CONST_URL_ANTHROPIC_API_BASE
from devops_cli.models.ai import ChatMessage
from devops_cli.telemetry import inject_trace_context

logger = logging.getLogger(__name__)


class ClaudeProviderMixin(BaseLLMProviderMixin):
    """Mixin implementing Claude Anthropic Messages API calls and streams."""

    def _claude_messages(
        self,
        system: str,
        messages: list[ChatMessage],
        *,
        enable_thinking: bool = True,
    ) -> LLMResponse:
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
        model_name = self._config.model or "claude-3-5-sonnet"
        clean_model = model_name.replace(":thinking", "").strip()
        supports_thinking = "claude-3-7" in model_name.lower() or ":thinking" in model_name.lower()
        use_thinking = enable_thinking and supports_thinking

        max_tok = getattr(self._config, "max_tokens", None) or 8192
        payload: dict[str, Any] = {
            "model": clean_model,
            "max_tokens": int(max_tok),
            "system": system,
            "messages": [m.to_dict() for m in messages],
        }

        if use_thinking:
            budget_tokens = min(4096, max(1024, int(max_tok) // 2))
            payload["thinking"] = {"type": "enabled", "budget_tokens": budget_tokens}
            payload["max_tokens"] = max(int(max_tok), budget_tokens + 1024)
        else:
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
                raw_json = read_limited_json(response)
                content_blocks = raw_json.get("content", [])
                text_parts: list[str] = []
                thinking_parts: list[str] = []
                for block in content_blocks:
                    if not isinstance(block, dict):
                        continue
                    b_type = block.get("type")
                    if b_type == "text":
                        text_parts.append(str(block.get("text", "")))
                    elif b_type == "thinking":
                        thinking_parts.append(str(block.get("thinking", "")))

                text = "\n".join(text_parts).strip()
                thinking_str = "\n".join(thinking_parts).strip() or None

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
                    thinking=thinking_str,
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

    def _claude_stream(
        self,
        system: str,
        messages: list[ChatMessage],
        *,
        enable_thinking: bool = True,
    ) -> Generator[str]:
        base = self._validate_base_url(
            self._config.api_base_url or CONST_URL_ANTHROPIC_API_BASE,
            purpose="Claude API",
        )
        headers = {
            "x-api-key": self._api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        model_name = self._config.model or "claude-3-5-sonnet"
        clean_model = model_name.replace(":thinking", "").strip()
        supports_thinking = "claude-3-7" in model_name.lower() or ":thinking" in model_name.lower()
        use_thinking = enable_thinking and supports_thinking

        max_tok = getattr(self._config, "max_tokens", None) or 8192
        payload: dict[str, Any] = {
            "model": clean_model,
            "max_tokens": int(max_tok),
            "system": system,
            "messages": [m.to_dict() for m in messages],
            "stream": True,
        }
        if use_thinking:
            budget_tokens = min(4096, max(1024, int(max_tok) // 2))
            payload["thinking"] = {"type": "enabled", "budget_tokens": budget_tokens}
            payload["max_tokens"] = max(int(max_tok), budget_tokens + 1024)
        else:
            claude_temp = getattr(self._config, "temperature", None)
            if claude_temp is not None:
                payload["temperature"] = float(claude_temp)

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
