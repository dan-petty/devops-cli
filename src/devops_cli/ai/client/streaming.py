"""Streaming utilities for token chunks and SSE event streams."""

from __future__ import annotations

import json
from collections.abc import Callable, Generator

import httpx2

from devops_cli.ai.client.models import MAX_STREAM_BYTES, AIClientError


def _extract_ollama_stream_chunk(line: str) -> str | None:
    """Extract content or thinking chunk from an Ollama stream line."""
    if not line:
        return None
    try:
        line_data = json.loads(line)
    except json.JSONDecodeError:
        return None
    msg = line_data.get("message", {})
    content = msg.get("content", "")
    thinking = msg.get("thinking", "")
    if thinking:
        return f"<think>{thinking}</think>"
    if content:
        return str(content)
    return None


def _extract_claude_stream_chunk(line: str) -> tuple[str | None, bool]:
    """Extract content chunk from Claude SSE stream line. Returns (chunk, is_done)."""
    if not line or not line.startswith("data:"):
        return (None, False)
    raw_data = line.removeprefix("data:").strip()
    if raw_data == "[DONE]":
        return (None, True)
    try:
        event_json = json.loads(raw_data)
    except json.JSONDecodeError:
        return (None, False)
    if event_json.get("type") == "content_block_delta":
        delta = event_json.get("delta", {})
        if delta.get("type") == "text_delta":
            text_val = delta.get("text", "")
            if text_val:
                return (str(text_val), False)
    return (None, False)


def _extract_openai_stream_chunk(line: str) -> tuple[str | None, bool]:
    """Extract content chunk from OpenAI SSE stream line. Returns (chunk, is_done)."""
    if not line or not line.startswith("data:"):
        return (None, False)
    raw_data = line.removeprefix("data:").strip()
    if raw_data == "[DONE]":
        return (None, True)
    try:
        event_json = json.loads(raw_data)
    except json.JSONDecodeError:
        return (None, False)
    choices = event_json.get("choices", [])
    if choices:
        delta = choices[0].get("delta", {})
        content = delta.get("content")
        if content:
            return (str(content), False)
    return (None, False)


def _extract_ollama_stream_tuple(line: str) -> tuple[str | None, bool]:
    """Extract content or thinking chunk from Ollama stream line as (chunk, is_done)."""
    return (_extract_ollama_stream_chunk(line), False)


def _consume_streaming_lines(
    response: httpx2.Response,
    chunk_extractor: Callable[[str], tuple[str | None, bool]],
    provider_name: str,
) -> Generator[str]:
    """Yield extracted tokens from an HTTP streaming response with size bounds."""
    import devops_cli.ai.client as client_pkg
    import devops_cli.ai.client.models as client_models

    max_bytes = getattr(
        client_pkg,
        "MAX_STREAM_BYTES",
        getattr(client_models, "MAX_STREAM_BYTES", MAX_STREAM_BYTES),
    )
    total_bytes = 0
    for line in response.iter_lines():
        chunk_str, is_done = chunk_extractor(line)
        if is_done:
            break
        if chunk_str is None:
            continue
        total_bytes += len(chunk_str.encode("utf-8"))
        if total_bytes > max_bytes:
            raise AIClientError(f"{provider_name} response exceeded maximum stream size (50MB).")
        yield chunk_str
