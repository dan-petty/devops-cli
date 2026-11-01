"""Models and exceptions for AI client."""

from __future__ import annotations

import json
import os
from collections.abc import Mapping
from enum import StrEnum
from http import HTTPStatus
from http.client import responses as http_phrases
from typing import TYPE_CHECKING, Any, NamedTuple

import httpx2

from devops_cli.config.constants import (
    CONST_GENAI_PROVIDER_NAMES,
)
from devops_cli.config.env import ENV_AGENT_GRANT, env_var_for_option
from devops_cli.exceptions.ai import LLMInferenceError
from devops_cli.http.urls import get_url_origin, read_url_or_authority

if TYPE_CHECKING:
    from pydantic_ai.messages import FinishReason

MAX_STREAM_BYTES = 50 * 1024 * 1024  # 50MB maximum streamed response size


class RequestPriority(StrEnum):
    """Priority classification for AI / LLM requests."""

    HIGH = "high"
    NORMAL = "normal"
    AS_AVAILABLE = "as_available"

    @property
    def weight(self) -> int:
        """Integer priority weight for comparison and ordering."""
        weights = {
            RequestPriority.HIGH: 30,
            RequestPriority.NORMAL: 20,
            RequestPriority.AS_AVAILABLE: 10,
        }
        return weights.get(self, 20)

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, RequestPriority):
            return NotImplemented
        return self.weight < other.weight

    def __le__(self, other: object) -> bool:
        if not isinstance(other, RequestPriority):
            return NotImplemented
        return self.weight <= other.weight

    def __gt__(self, other: object) -> bool:
        if not isinstance(other, RequestPriority):
            return NotImplemented
        return self.weight > other.weight

    def __ge__(self, other: object) -> bool:
        if not isinstance(other, RequestPriority):
            return NotImplemented
        return self.weight >= other.weight


# The HTTP statuses that say the call ran out of time: Request Timeout and Gateway Timeout.
_TIMEOUT_STATUSES = frozenset({HTTPStatus.REQUEST_TIMEOUT, HTTPStatus.GATEWAY_TIMEOUT})


class AIClientError(LLMInferenceError, RuntimeError):
    """Raised when an AI provider request fails with a user-actionable message.

    `status` is the HTTP status of the provider's reply, and `timed_out` says the call timed out;
    the code that builds the error sets them where it knows them (#2562).
    """

    def __init__(
        self, message: str, *, status: int | None = None, timed_out: bool = False, **kwargs: Any
    ) -> None:
        super().__init__(message, **kwargs)
        self.status = status
        self.timed_out = timed_out

    @property
    def reason(self) -> str:
        """The error code, then `timeout` when the call timed out or the status says so (408,
        504), then the HTTP status with its phrase when known. It holds none of the message, which
        can quote the provider's reply."""
        timed_out = self.timed_out or self.status in _TIMEOUT_STATUSES
        if self.status is None:
            return f"{self.error_code}, timeout" if timed_out else self.error_code
        phrase = http_phrases.get(self.status, "")
        status = f"HTTP {self.status} {phrase}".rstrip()
        return (
            f"{self.error_code}, timeout ({status})"
            if timed_out
            else f"{self.error_code}, {status}"
        )


class ReplyRejectedError(AIClientError):
    """Raised when the caller's validator refused a reply; it carries the reply, never cached.

    The message is the one a plain `AIClientError` for a refused reply has, and holds none of the
    reply, so a caller that logs the error logs no model text.
    """

    def __init__(self, message: str, *, reply: str = "", **kwargs: Any) -> None:
        super().__init__(message, **kwargs)
        self.reply = reply


class StructuredOutputValidationError(AIClientError):
    """Raised when the model answered, but no answer validated against the schema after retries.

    `violations` counts the last answer's schema violations, and is 0 when it held no JSON.
    """

    def __init__(self, message: str, *, violations: int = 0, **kwargs: Any) -> None:
        super().__init__(message, **kwargs)
        self.violations = violations


class AICredentialsError(AIClientError):
    """Raised when a provider rejects the request's credentials; retrying cannot help."""


def credentials_error(subject: str, *, has_key: bool, status: int) -> AICredentialsError:
    """Build the error for a 401/403, naming whether the key is missing and where it comes from.

    ``subject`` names what refused the request, e.g. "The gateway provider".
    """
    grant_id = os.environ.get(ENV_AGENT_GRANT)
    if grant_id:
        bounded_grant = grant_id[:256]
        return AICredentialsError(
            f"{subject} rejected agent grant '{bounded_grant}' (HTTP {status}): "
            "the grant expired or was revoked; a person issues a new grant."
        )
    problem = (
        "rejected the configured API key"
        if has_key
        else "requires an API key, but no API key is configured"
    )
    return AICredentialsError(
        f"{subject} {problem} (HTTP {status}). "
        f"Set {env_var_for_option('ai.api_key')} or run `devops config set ai.api_key`."
    )


def authority_label(host: str, port: int | None, scheme: str = "") -> str:
    """The `host[:port]` text of one server, as httpx2 writes the authority of a URL.

    The text never holds userinfo. httpx2 writes the host in lower case and an IDN host as its
    A-label. With a scheme, it leaves out the default port of that scheme. With no scheme, as for
    a bare served_by authority, every port stays.
    """
    return httpx2.URL(scheme=scheme, host=host, port=port).netloc.decode("ascii")


def origin_label(origin: httpx2.Origin) -> str:
    """The `host[:port]` text of an origin, from `authority_label`."""
    return authority_label(origin.host, origin.port, origin.scheme)


def origin_span_attributes(origin: httpx2.Origin | None) -> dict[str, Any]:
    """`server.address` and `server.port` of the one server that a request went to.

    The origin holds the default port of its scheme when the URL has no port. With no origin,
    the request names no single server, so the span gets neither attribute.
    """
    if origin is None:
        return {}
    attributes: dict[str, Any] = {"server.address": origin.host}
    if origin.port is not None:
        attributes["server.port"] = origin.port
    return attributes


class CallSampling(NamedTuple):
    """The sampling that a caller passes to one chat call. A field that is None keeps the
    configured value; the configuration has no seed, so a None seed sends none."""

    temperature: float | None = None
    top_p: float | None = None
    seed: int | None = None

    def over(self, config: Any) -> CallSampling:
        """This sampling, with the configured `temperature` and `top_p` in each None field."""
        return CallSampling(
            self.temperature
            if self.temperature is not None
            else getattr(config, "temperature", None),
            self.top_p if self.top_p is not None else getattr(config, "top_p", None),
            self.seed,
        )


class ServedByAuthority(NamedTuple):
    """The server that a gateway's served_by value names: its host and its `host[:port]` text."""

    host: str
    label: str


def served_by_authority(served_by: str) -> ServedByAuthority | None:
    """The server that a stored served_by value names, or None when the value names no server.

    httpx2, the client that sends, reads an absolute URL. The shared URL-or-authority reader
    reads a bare `host[:port]`, which a reply header can hold; with no scheme, its port stays in
    the text. Neither keeps userinfo.
    """
    origin = get_url_origin(served_by)
    if origin is not None:
        return ServedByAuthority(origin.host, origin_label(origin))
    parts = read_url_or_authority(served_by)
    if parts is None or not parts.hostname:
        return None
    try:
        return ServedByAuthority(parts.hostname, authority_label(parts.hostname, parts.port))
    except ValueError, httpx2.InvalidURL:
        return None


class LLMResponse(str):
    """String response from LLM with optional execution timing and backend metadata."""

    processing_seconds: float | None
    wall_seconds: float
    backend_info: str | None
    origin: httpx2.Origin | None
    thinking: str | None
    prompt_tokens: int | None
    completion_tokens: int | None
    total_tokens: int | None
    reasoning_tokens: int | None
    cached: bool
    eval_duration_ms: float | None
    prompt_eval_duration_ms: float | None
    served_by: str | None
    served_model: str | None
    model: str | None
    finish_reason: FinishReason | None

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
        served_by: str | None = None,
        model: str | None = None,
        finish_reason: FinishReason | None = None,
        reasoning_tokens: int | None = None,
        served_model: str | None = None,
        origin: httpx2.Origin | None = None,
    ) -> LLMResponse:
        obj = str.__new__(cls, content)
        obj.processing_seconds = processing_seconds
        obj.wall_seconds = wall_seconds
        obj.backend_info = backend_info
        # The scheme, host and port of the URL that the provider called, never its userinfo;
        # None for a reply that no endpoint sent, such as a cache hit.
        obj.origin = origin
        obj.thinking = thinking
        obj.prompt_tokens = prompt_tokens
        obj.completion_tokens = completion_tokens
        obj.total_tokens = total_tokens
        obj.reasoning_tokens = reasoning_tokens
        obj.eval_duration_ms = eval_duration_ms
        obj.prompt_eval_duration_ms = prompt_eval_duration_ms
        obj.cached = cached
        # The backend a gateway routed the call to; None when no gateway named one.
        obj.served_by = served_by
        # The deployment model a gateway named as the model that served the call; None when no
        # gateway named one. `model` is the model the reply body names: the route name for the
        # gateway (#2031).
        obj.served_model = served_model
        obj.model = model
        # Why the provider says the reply ended; None when it did not say.
        obj.finish_reason = finish_reason
        return obj

    @property
    def text(self) -> str:
        """Return the string response content."""
        return str(self)

    @property
    def content(self) -> str:
        """Return the string response content."""
        return str(self)

    def to_model_response(self, model_name: str | None = None) -> Any:
        """Convert LLMResponse to standard pydantic_ai.messages.ModelResponse."""
        from pydantic_ai.messages import ModelResponse, TextPart, ThinkingPart
        from pydantic_ai.usage import RequestUsage

        parts: list[Any] = []
        if self.thinking and self.thinking.strip():
            parts.append(ThinkingPart(content=self.thinking.strip()))
        if str(self):
            parts.append(TextPart(content=str(self)))
        details = (
            {"reasoning_tokens": self.reasoning_tokens}
            if self.reasoning_tokens is not None
            else None
        )
        usage = RequestUsage(
            input_tokens=self.prompt_tokens or 0,
            output_tokens=self.completion_tokens or 0,
            details=details,
        )
        return ModelResponse(
            parts=parts,
            model_name=model_name or self.backend_info,
            usage=usage,
            finish_reason=self.finish_reason,
        )


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


def provider_finish_reason(
    table: Mapping[str, FinishReason | None], value: object
) -> FinishReason | None:
    """A provider's own stop value as a FinishReason; None when it is absent or unmapped."""
    return table.get(value) if isinstance(value, str) else None


def genai_provider_name(provider: str) -> str:
    """The conventions' `gen_ai.provider.name` for a provider id: its well-known value or the id."""
    return CONST_GENAI_PROVIDER_NAMES.get(provider, provider)


def is_reasoning_model(model: str | None = None, *, config: Any = None) -> bool:
    """Return True if model is declared as a reasoning/thinking model via config or capability."""
    if config is not None:
        return bool(getattr(config, "supports_reasoning", False))
    return False
