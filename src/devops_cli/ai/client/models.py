"""Models and exceptions for AI client."""

from __future__ import annotations

import json

from devops_cli.exceptions import LLMInferenceError

MAX_STREAM_BYTES = 50 * 1024 * 1024  # 50MB maximum streamed response size


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
