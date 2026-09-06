"""AI/LLM Response Sanitizer and Output Repair Engine built on pydantic_ai.messages.

Repairs malformed outputs, extracts embedded tool calls, separates reasoning/thinking blocks,
and normalizes responses across all LLM providers using standard pydantic_ai.messages.
"""

from __future__ import annotations

import json
import re
from typing import Any, cast

import json_repair
from pydantic import BaseModel, Field, TypeAdapter
from pydantic_ai.messages import (
    ModelResponse,
    ModelResponsePart,
    TextPart,
    ThinkingPart,
    ToolCallPart,
)
from pydantic_ai.usage import RequestUsage

from devops_cli.ai.review_schema import normalize_unicode_text, unique_lines

__all__ = [
    "ExtractedToolCall",
    "FormattedLLMResponse",
    "extract_model_response_parts",
    "extract_tool_invocations",
    "fix_llm_response",
    "parse_model_response",
    "repair_json_string",
]

_TOOL_EXTRACT_PAGE_SIZE = 32 * 1024  # 32 KiB chunk window
_TOOL_EXTRACT_OVERLAP = 1024  # 1 KiB overlap to prevent boundary cuts


def repair_json_string(text: str) -> Any:
    """Extract and repair valid or partially-malformed JSON from text using json-repair."""
    if not text or not text.strip():
        return None

    from devops_cli.ai.thinking_stream import strip_think_blocks

    cleaned = strip_think_blocks(normalize_unicode_text(text)).strip()
    if not cleaned:
        return None

    # 1. First pass: use standard json_repair to parse JSON, objects, lists, or markdown fences
    try:
        data = json_repair.loads(cleaned)
        if data != "" and data is not None:
            return data
    except Exception:
        pass

    # 2. If surrounded by markdown fences, extract and repair candidate block
    for pattern in (r"```(?:json)?\s*([\s\S]*?)```",):
        matched_block = re.search(pattern, cleaned, re.DOTALL)
        if matched_block:
            candidate = matched_block.group(1).strip()
            try:
                data = json_repair.loads(candidate)
                if data != "" and data is not None:
                    return data
            except Exception:
                pass

    return None


class ExtractedToolCall(BaseModel):
    """Normalized tool call extracted from raw LLM output."""

    tool_name: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    raw_syntax: str = ""


class FormattedLLMResponse[T](BaseModel):
    """Standardized, repaired, and formatted LLM response backed by pydantic_ai.messages."""

    content: str
    raw_content: str
    thoughts: list[str] = Field(default_factory=list)
    thinking: str | None = None
    tool_calls: list[ExtractedToolCall] = Field(default_factory=list)
    model_response: ModelResponse | None = None
    json_data: Any = None
    parsed_model: T | None = None
    was_repaired: bool = False
    repair_notes: list[str] = Field(default_factory=list)


def _extract_json_dict_tool_call(
    json_dict: dict[str, Any], known_tool_names: set[str] | None
) -> ExtractedToolCall | None:
    """Extract ExtractedToolCall from JSON dictionary if it matches tool calling schema."""
    tool_name = json_dict.get("tool") or json_dict.get("name") or json_dict.get("function")
    if not (tool_name and isinstance(tool_name, str)):
        return None
    if known_tool_names and tool_name not in known_tool_names:
        return None

    args = json_dict.get("arguments") or json_dict.get("parameters") or {}
    if not isinstance(args, dict):
        args = {}
    return ExtractedToolCall(
        tool_name=tool_name,
        arguments=args,
        raw_syntax=json.dumps(json_dict, default=str),
    )


def _extract_tool_invocations_from_chunk(
    text: str,
    known_tool_names: set[str],
) -> list[ExtractedToolCall]:
    """Extract tool calls from a single text chunk with bounded parsing."""
    calls: list[ExtractedToolCall] = []

    # 1. JSON-based tool call detection
    json_obj = repair_json_string(text)
    if isinstance(json_obj, dict):
        call = _extract_json_dict_tool_call(json_obj, known_tool_names)
        if call:
            calls.append(call)
    elif isinstance(json_obj, list):
        for item in json_obj:
            if isinstance(item, dict):
                call = _extract_json_dict_tool_call(item, known_tool_names)
                if call:
                    calls.append(call)

    # 2. Function-style call extraction: tool_name({"arg": "val"}) or tool_name(arg="val")
    fn_pattern = (
        r"(?:invoke|call|run|execute)?\s*`?([a-zA-Z0-9_]+)`?\s*\(\s*(\{.*?\}|[^()\n]*)\s*\)"
    )
    for match in re.finditer(fn_pattern, text):
        function_name = match.group(1).strip()
        raw_args = match.group(2).strip()
        if known_tool_names and function_name not in known_tool_names:
            continue
        if any(c.tool_name == function_name for c in calls):
            continue

        parsed_args: dict[str, Any] = {}
        if raw_args.startswith("{") and raw_args.endswith("}"):
            parsed_json = repair_json_string(raw_args)
            if isinstance(parsed_json, dict):
                parsed_args = parsed_json
        else:
            kw_matches = re.findall(
                r'([a-zA-Z0-9_]+)\s*=\s*(?:"([^"]*)"|\'([^\']*)\'|([^\s,]+))', raw_args
            )
            for kw in kw_matches:
                arg_key = kw[0]
                arg_value = kw[1] or kw[2] or kw[3]
                parsed_args[arg_key] = arg_value

        if parsed_args or (
            raw_args == "" and not function_name.lower().startswith(("the", "we", "this", "that"))
        ):
            calls.append(
                ExtractedToolCall(
                    tool_name=function_name, arguments=parsed_args, raw_syntax=match.group(0)
                )
            )

    return calls


def extract_tool_invocations(
    text: str, available_tools: list[str] | set[str] | None = None
) -> list[ExtractedToolCall]:
    """Extract tool calls across full text using sliding window paging."""
    if not text or not text.strip():
        return []

    known_tool_names = set(available_tools) if available_tools else set()

    if len(text) <= _TOOL_EXTRACT_PAGE_SIZE:
        return _extract_tool_invocations_from_chunk(text, known_tool_names)

    all_calls: list[ExtractedToolCall] = []
    seen_calls: set[tuple[str, str]] = set()
    offset = 0
    step = _TOOL_EXTRACT_PAGE_SIZE - _TOOL_EXTRACT_OVERLAP

    while offset < len(text):
        chunk = text[offset : offset + _TOOL_EXTRACT_PAGE_SIZE]
        chunk_calls = _extract_tool_invocations_from_chunk(chunk, known_tool_names)
        for call in chunk_calls:
            key = (call.tool_name, call.raw_syntax)
            if key not in seen_calls:
                seen_calls.add(key)
                all_calls.append(call)
        offset += step

    return all_calls


def parse_model_response(
    raw_response: str | Any,
    model_name: str | None = None,
) -> ModelResponse:
    """Parse raw response, string, or LLMResponse into standard pydantic_ai.messages.ModelResponse."""
    if isinstance(raw_response, ModelResponse):
        return raw_response

    if hasattr(raw_response, "to_model_response") and callable(raw_response.to_model_response):
        res = raw_response.to_model_response(model_name=model_name)
        if isinstance(res, ModelResponse):
            return res

    raw_str = str(raw_response) if raw_response is not None else ""
    norm_text = normalize_unicode_text(raw_str)

    parts: list[ModelResponsePart] = []

    # Check for direct thinking attribute on response object
    raw_thinking = getattr(raw_response, "thinking", None)
    if raw_thinking and isinstance(raw_thinking, str) and raw_thinking.strip():
        parts.append(ThinkingPart(content=unique_lines(raw_thinking.strip())))

    # Extract all <think>...</think> and unclosed <think> blocks
    think_matches = re.findall(r"<think>(.*?)(?:</think>|$)", norm_text, flags=re.DOTALL)
    for think_match in think_matches:
        think_clean = unique_lines(think_match.strip())
        if think_clean and not any(
            isinstance(p, ThinkingPart) and p.content == think_clean for p in parts
        ):
            parts.append(ThinkingPart(content=think_clean))

    # Clean text outside <think> tags
    clean_text = re.sub(r"<think>.*?</think>", "", norm_text, flags=re.DOTALL).strip()
    if "<think>" in clean_text:
        clean_text = re.sub(r"<think>[\s\S]*$", "", clean_text).strip()

    # Extract tool calls from clean text, or fall back to full normalized text if tool calls were inside reasoning
    tool_calls = extract_tool_invocations(clean_text)
    if not tool_calls and norm_text != clean_text:
        tool_calls = extract_tool_invocations(norm_text)

    for tc in tool_calls:
        parts.append(ToolCallPart(tool_name=tc.tool_name, args=tc.arguments))

    if clean_text:
        parts.append(TextPart(content=clean_text))

    return ModelResponse(parts=parts, model_name=model_name, usage=RequestUsage())


def extract_model_response_parts(
    response: ModelResponse,
) -> tuple[str, str | None, list[ToolCallPart]]:
    """Extract clean content, isolated thinking, and tool calls from ModelResponse."""
    texts = [p.content for p in response.parts if isinstance(p, TextPart) and p.has_content()]
    thinks = [p.content for p in response.parts if isinstance(p, ThinkingPart) and p.has_content()]
    tool_calls = [p for p in response.parts if isinstance(p, ToolCallPart)]
    clean_text = "\n".join(texts)
    thinking_text = unique_lines("\n\n".join(thinks)) if thinks else None
    return clean_text, thinking_text, tool_calls


def fix_llm_response[T = Any](
    raw_response: str | Any,
    schema: type[T] | None = None,
    available_tools: list[str] | set[str] | None = None,
) -> FormattedLLMResponse[T]:
    """Universal AI/LLM response parser and formatter built on pydantic_ai.messages.ModelResponse."""
    resp = parse_model_response(raw_response)
    final_content, thinking_str, tool_parts = extract_model_response_parts(resp)

    tool_calls = [
        ExtractedToolCall(
            tool_name=p.tool_name,
            arguments=p.args if isinstance(p.args, dict) else {},
            raw_syntax=f'{{"tool": "{p.tool_name}", "arguments": {json.dumps(p.args if isinstance(p.args, dict) else {})}}}',
        )
        for p in tool_parts
    ]
    if available_tools:
        known = set(available_tools)
        tool_calls = [c for c in tool_calls if c.tool_name in known]

    thoughts = [p.content for p in resp.parts if isinstance(p, ThinkingPart) and p.has_content()]

    json_data = repair_json_string(final_content)
    parsed_model: T | None = None

    if schema is not None:
        from devops_cli.ai.output import TextOutput, unwrap_output_spec

        if isinstance(schema, TextOutput):
            try:
                parsed_model = cast(T, schema.output_function(final_content))
            except Exception:
                pass
        else:
            unwrapped = unwrap_output_spec(schema)
            target_schema = unwrapped[0] if unwrapped else schema
            validator = getattr(target_schema, "model_validate", None)
            if callable(validator) and isinstance(json_data, dict | list):
                try:
                    parsed_model = validator(json_data)
                except Exception:
                    pass
            if parsed_model is None and json_data is not None:
                try:
                    parsed_model = cast(T, TypeAdapter(target_schema).validate_python(json_data))
                except Exception:
                    pass
            if parsed_model is None and final_content:
                try:
                    parsed_model = TypeAdapter(target_schema).validate_json(final_content)
                except Exception:
                    pass

    raw_str = str(raw_response) if raw_response is not None else ""
    was_repaired = bool(
        tool_calls
        or thoughts
        or (json_data is not None and json_data != final_content)
        or (final_content.strip() != raw_str.strip())
    )

    return FormattedLLMResponse[T](
        content=final_content,
        raw_content=raw_str,
        thoughts=thoughts,
        thinking=thinking_str,
        tool_calls=tool_calls,
        model_response=resp,
        json_data=json_data,
        parsed_model=parsed_model,
        was_repaired=was_repaired,
        repair_notes=[],
    )
