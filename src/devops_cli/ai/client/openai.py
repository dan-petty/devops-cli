"""OpenAI and GitHub Copilot provider backend implementation."""

from __future__ import annotations

import logging
import time
from collections.abc import Generator
from typing import Any

import httpx2

from devops_cli.ai.client.base import BaseLLMProviderMixin
from devops_cli.ai.client.models import (
    LLMResponse,
    is_reasoning_model,
    provider_finish_reason,
)
from devops_cli.ai.client.network import reply_schema, request_limited_json, stream_served_by
from devops_cli.ai.client.streaming import _openai_stream_frame, _read_event_stream
from devops_cli.config.constants import (
    CONST_AI_GATEWAY_PROVIDER,
    CONST_AI_GATEWAY_SERVED_BY_HEADER,
    CONST_OPENAI_FINISH_REASONS,
    CONST_URL_GITHUB_COPILOT_API_BASE,
    CONST_URL_OPENAI_API_BASE,
)
from devops_cli.config.defaults import DEFAULT_AI_GATEWAY_URL
from devops_cli.models.ai import ChatMessage
from devops_cli.telemetry import inject_trace_context

logger = logging.getLogger(__name__)


class OpenAICompatProviderMixin(BaseLLMProviderMixin):
    """Mixin implementing OpenAI-compatible and GitHub Copilot completions."""

    def _api_base(self) -> str:
        # The gateway holds its own key, so its requests go only to gateway_url; api_base_url is
        # usually another provider's endpoint (a gateway task's own one is folded into gateway_url).
        if self._config.provider == "gateway":
            gw_url = getattr(self._config, "gateway_url", None) or DEFAULT_AI_GATEWAY_URL
            return self._validate_base_url(gw_url, purpose="provider API")
        if self._config.api_base_url:
            return self._validate_base_url(self._config.api_base_url, purpose="provider API")
        if self._config.provider == "copilot":
            return CONST_URL_GITHUB_COPILOT_API_BASE
        return CONST_URL_OPENAI_API_BASE

    def _openai_compat_headers(self) -> dict[str, str]:
        """Request headers; Authorization only when a key is set, since an empty bearer token is
        an illegal header value that fails before the request is sent."""
        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        return headers

    def _apply_reasoning_params(
        self, payload: dict[str, Any], limit: int | None, enable_thinking: bool
    ) -> None:
        """Apply reasoning-specific parameters to the request payload."""
        effort = self._config.reasoning_effort or ("medium" if enable_thinking else "low")
        if effort:
            payload["reasoning_effort"] = effort
        if limit is not None:
            payload["max_completion_tokens"] = limit

    def _apply_standard_params(
        self, payload: dict[str, Any], limit: int | None, stream: bool
    ) -> None:
        """Apply standard model parameters (tokens, temperature, top_p) to payload."""
        if limit is not None:
            payload["max_tokens"] = limit
        if stream:
            return
        temp = getattr(self._config, "temperature", None)
        if temp is not None:
            payload["temperature"] = float(temp)
        top_p = getattr(self._config, "top_p", None)
        if top_p is not None:
            payload["top_p"] = float(top_p)

    def _build_compat_payload(
        self,
        system: str,
        messages: list[ChatMessage],
        *,
        stream: bool = False,
        enable_thinking: bool = True,
    ) -> dict[str, Any]:
        """Construct JSON payload adhering strictly to model reasoning capabilities."""
        payload: dict[str, Any] = {
            "model": self._config.model,
            "messages": [
                {"role": "system", "content": system},
                *[m.to_dict() for m in messages],
            ],
        }
        if stream:
            payload["stream"] = True

        limit = self._completion_limit()
        if is_reasoning_model(self._config.model):
            self._apply_reasoning_params(payload, limit, enable_thinking)
        else:
            self._apply_standard_params(payload, limit, stream)
        self._apply_reply_schema(payload)
        return payload

    def _apply_reply_schema(self, payload: dict[str, Any]) -> None:
        """Ask the gateway to constrain the reply to a structured call's schema, if one is set.

        Only the gateway gets `response_format`, and without `strict`: LiteLLM maps it to an
        Ollama deployment's `format`, and drops it for a deployment that takes no such parameter
        (`drop_params`). The openai and copilot providers rely on the schema in the prompt, which
        `chat_structured` sends to every provider.
        """
        schema = reply_schema.get()
        if schema is None or self._config.provider != CONST_AI_GATEWAY_PROVIDER:
            return
        payload["response_format"] = {
            "type": "json_schema",
            "json_schema": {"name": schema.name, "schema": schema.json_schema},
        }

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

    def _parse_compat_response(
        self,
        raw_json: dict[str, Any],
        wall_elapsed: float,
        served_by: str | None,
    ) -> LLMResponse:
        """Parse raw OpenAI completion JSON into a structured LLMResponse."""
        choices = raw_json.get("choices", [{}])
        first_choice = choices[0] if choices else {}
        msg = first_choice.get("message", {})
        raw_content = str(msg.get("content") or "")
        raw_reasoning = (
            msg.get("reasoning_content") or msg.get("reasoning") or first_choice.get("reasoning")
        )
        thinking_str = str(raw_reasoning).strip() if raw_reasoning else None

        content, thinking_str = self._extract_inline_thinking(raw_content, thinking_str)
        usage = raw_json.get("usage", {})
        b_info = f"{self.backend_type} ({self.backend_host})"
        return LLMResponse(
            content,
            processing_seconds=None,
            wall_seconds=wall_elapsed,
            backend_info=b_info,
            thinking=thinking_str,
            prompt_tokens=usage.get("prompt_tokens"),
            completion_tokens=usage.get("completion_tokens"),
            total_tokens=usage.get("total_tokens"),
            served_by=served_by,
            model=raw_json.get("model"),
            finish_reason=provider_finish_reason(
                CONST_OPENAI_FINISH_REASONS, first_choice.get("finish_reason")
            ),
        )

    def _openai_compat_messages(
        self,
        system: str,
        messages: list[ChatMessage],
        *,
        enable_thinking: bool = True,
    ) -> LLMResponse:
        start_time = time.monotonic()
        headers = inject_trace_context(self._openai_compat_headers())
        payload = self._build_compat_payload(system, messages, enable_thinking=enable_thinking)
        try:
            raw_json, reply_headers = request_limited_json(
                self._shared_client(),
                "POST",
                f"{self._api_base()}/chat/completions",
                headers=headers,
                json=payload,
                timeout=self._request_timeout(),
            )
            wall_elapsed = time.monotonic() - start_time
            served_by = reply_headers.get(CONST_AI_GATEWAY_SERVED_BY_HEADER)
            return self._parse_compat_response(raw_json, wall_elapsed, served_by)
        except (httpx2.ConnectError, httpx2.ConnectTimeout) as exc:
            raise self._connection_error(exc) from exc
        except httpx2.HTTPError as exc:
            raise self._provider_http_error(
                exc, "Provider request failed. Check network access, API endpoint, and credentials."
            ) from exc

    def _openai_compat_stream(
        self,
        system: str,
        messages: list[ChatMessage],
        *,
        enable_thinking: bool = True,
    ) -> Generator[str]:
        headers = self._openai_compat_headers()
        payload = self._build_compat_payload(
            system, messages, stream=True, enable_thinking=enable_thinking
        )
        try:
            with (
                self._create_http_client() as http_client,
                http_client.stream(
                    "POST", f"{self._api_base()}/chat/completions", headers=headers, json=payload
                ) as response,
            ):
                if response.status_code >= 400:
                    response.read()
                response.raise_for_status()
                stream_served_by.set(response.headers.get(CONST_AI_GATEWAY_SERVED_BY_HEADER))
                yield from _read_event_stream(response, _openai_stream_frame, "Provider")
        except (httpx2.ConnectError, httpx2.ConnectTimeout) as exc:
            raise self._connection_error(exc) from exc
        except httpx2.HTTPError as exc:
            raise self._provider_http_error(exc, f"Provider streaming failed: {exc}") from exc

    def _openai_models(self) -> list[str]:
        try:
            listing, _headers = request_limited_json(
                self._shared_client(),
                "GET",
                f"{self._api_base()}/models",
                headers=self._openai_compat_headers(),
                timeout=self._request_timeout(),
            )
            return [model_info["id"] for model_info in listing.get("data", [])]
        except (httpx2.ConnectError, httpx2.ConnectTimeout) as exc:
            raise self._connection_error(exc) from exc
        except httpx2.HTTPError as exc:
            raise self._provider_http_error(
                exc,
                "Failed to list provider models. Check network access, API endpoint, and credentials.",
            ) from exc
