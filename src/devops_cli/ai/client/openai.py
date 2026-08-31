"""OpenAI and GitHub Copilot provider backend implementation."""

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
    _extract_openai_stream_chunk,
)
from devops_cli.config.constants import (
    CONST_URL_GITHUB_COPILOT_API_BASE,
    CONST_URL_OPENAI_API_BASE,
)
from devops_cli.models.ai import ChatMessage
from devops_cli.telemetry import inject_trace_context

logger = logging.getLogger(__name__)


class OpenAICompatProviderMixin(BaseLLMProviderMixin):
    """Mixin implementing OpenAI-compatible and GitHub Copilot completions."""

    def _api_base(self) -> str:
        if self._config.api_base_url:
            return self._validate_base_url(self._config.api_base_url, purpose="provider API")
        if self._config.provider == "copilot":
            return CONST_URL_GITHUB_COPILOT_API_BASE
        return CONST_URL_OPENAI_API_BASE

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
                raw_json = read_limited_json(response)
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
                    model_info["id"] for model_info in read_limited_json(response).get("data", [])
                ]
        except (httpx2.ConnectError, httpx2.ConnectTimeout) as exc:
            raise self._connection_error(exc) from exc
        except httpx2.HTTPError as exc:
            raise AIClientError(
                "Failed to list provider models. Check network access, API endpoint, and credentials."
            ) from exc
