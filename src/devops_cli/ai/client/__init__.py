"""Unified LLM client package for Ollama, Claude, GitHub Copilot, and OpenAI-compatible APIs."""

from __future__ import annotations

import httpx2

from devops_cli.ai.client.models import (
    MAX_STREAM_BYTES,
    AIClientError,
    LLMResponse,
    _is_json_error_payload,
    is_reasoning_model,
)
from devops_cli.ai.client.network import (
    ALLOW_PRIVATE_NETWORK_ENV,
    read_limited_json,
    validate_base_url,
)
from devops_cli.ai.client.streaming import (
    _consume_streaming_lines,
    _extract_claude_stream_chunk,
    _extract_ollama_stream_chunk,
    _extract_ollama_stream_tuple,
    _extract_openai_stream_chunk,
)
from devops_cli.ai.client.unified import (
    LLMClient,
    model_request,
    model_request_sync,
)

__all__ = [
    "ALLOW_PRIVATE_NETWORK_ENV",
    "AIClientError",
    "LLMClient",
    "LLMResponse",
    "MAX_STREAM_BYTES",
    "_consume_streaming_lines",
    "_extract_claude_stream_chunk",
    "_extract_ollama_stream_chunk",
    "_extract_ollama_stream_tuple",
    "_extract_openai_stream_chunk",
    "_is_json_error_payload",
    "httpx2",
    "is_reasoning_model",
    "model_request",
    "model_request_sync",
    "read_limited_json",
    "validate_base_url",
]
