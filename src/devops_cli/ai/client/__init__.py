"""Unified LLM client package for Ollama, Claude, GitHub Copilot, and OpenAI-compatible APIs."""

from __future__ import annotations

import httpx2

from devops_cli.ai.client.models import (
    MAX_STREAM_BYTES,
    AIClientError,
    AICredentialsError,
    LLMResponse,
    ReplyRejectedError,
    RequestPriority,
    StructuredOutputValidationError,
    _is_json_error_payload,
    is_reasoning_model,
)
from devops_cli.ai.client.network import (
    acquire_ollama_slot,
    current_request_priority,
    get_ollama_active_leases,
    get_ollama_waiting_counts,
    request_limited_json,
    request_priority_scope,
    reset_ollama_slots,
    validate_base_url,
)
from devops_cli.ai.client.streaming import (
    StreamingReasoningSanitizer,
    StreamingTokenProcessor,
)
from devops_cli.ai.client.structured import StructuredOutputMixin
from devops_cli.ai.client.unified import (
    LLMClient,
    model_request,
    model_request_sync,
)

__all__ = [
    "MAX_STREAM_BYTES",
    "AIClientError",
    "AICredentialsError",
    "LLMClient",
    "LLMResponse",
    "ReplyRejectedError",
    "RequestPriority",
    "StreamingReasoningSanitizer",
    "StreamingTokenProcessor",
    "StructuredOutputMixin",
    "StructuredOutputValidationError",
    "_is_json_error_payload",
    "acquire_ollama_slot",
    "current_request_priority",
    "get_ollama_active_leases",
    "get_ollama_waiting_counts",
    "httpx2",
    "is_reasoning_model",
    "model_request",
    "model_request_sync",
    "request_limited_json",
    "request_priority_scope",
    "reset_ollama_slots",
    "validate_base_url",
]
