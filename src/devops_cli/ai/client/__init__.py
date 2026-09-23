"""Unified LLM client package for Ollama, Claude, GitHub Copilot, and OpenAI-compatible APIs."""

from __future__ import annotations

import httpx2

from devops_cli.ai.client.models import (
    MAX_STREAM_BYTES,
    AIClientError,
    AICredentialsError,
    LLMResponse,
    RequestPriority,
    _is_json_error_payload,
    is_reasoning_model,
)
from devops_cli.ai.client.network import (
    ALLOW_PRIVATE_NETWORK_ENV,
    acquire_ollama_slot,
    current_request_priority,
    get_ollama_active_leases,
    get_ollama_waiting_counts,
    read_limited_json,
    request_priority_scope,
    reset_ollama_slots,
    validate_base_url,
)
from devops_cli.ai.client.streaming import (
    StreamingReasoningSanitizer,
    StreamingTokenProcessor,
    _consume_streaming_lines,
    _extract_claude_stream_chunk,
    _extract_ollama_stream_chunk,
    _extract_ollama_stream_tuple,
    _extract_openai_stream_chunk,
)
from devops_cli.ai.client.structured import StructuredOutputMixin
from devops_cli.ai.client.unified import (
    LLMClient,
    model_request,
    model_request_sync,
)

__all__ = [
    "ALLOW_PRIVATE_NETWORK_ENV",
    "MAX_STREAM_BYTES",
    "AIClientError",
    "AICredentialsError",
    "LLMClient",
    "LLMResponse",
    "RequestPriority",
    "StreamingReasoningSanitizer",
    "StreamingTokenProcessor",
    "StructuredOutputMixin",
    "_consume_streaming_lines",
    "_extract_claude_stream_chunk",
    "_extract_ollama_stream_chunk",
    "_extract_ollama_stream_tuple",
    "_extract_openai_stream_chunk",
    "_is_json_error_payload",
    "acquire_ollama_slot",
    "current_request_priority",
    "get_ollama_active_leases",
    "get_ollama_waiting_counts",
    "httpx2",
    "is_reasoning_model",
    "model_request",
    "model_request_sync",
    "read_limited_json",
    "request_priority_scope",
    "reset_ollama_slots",
    "validate_base_url",
]
