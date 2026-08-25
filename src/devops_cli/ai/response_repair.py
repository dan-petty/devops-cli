"""AI/LLM Response Sanitizer and Output Repair Engine.

Repairs malformed outputs, extracts embedded tool calls, recovers answers from
reasoning/thinking blocks, heals malformed/truncated JSON, and standardizes responses
across all LLM providers and local models (Ollama, DeepSeek, Qwen, GPT-OSS).
"""

from __future__ import annotations

import json
import re
from typing import Any

import json_repair
from pydantic import BaseModel, Field

from devops_cli.ai.review_schema import normalize_unicode_text

__all__ = [
    "ExtractedToolCall",
    "FormattedLLMResponse",
    "extract_tool_invocations",
    "fix_llm_response",
    "repair_json_string",
]

_TOOL_EXTRACT_PAGE_SIZE = 32 * 1024  # 32 KiB chunk window
_TOOL_EXTRACT_OVERLAP = 1024  # 1 KiB overlap to prevent boundary cuts


def repair_json_string(text: str) -> Any:
    """Extract and repair valid or partially-malformed JSON from text using json-repair."""
    if not text or not text.strip():
        return None

    cleaned = normalize_unicode_text(text).strip()

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
    """Standardized, repaired, and formatted LLM response."""

    content: str
    raw_content: str
    thoughts: list[str] = Field(default_factory=list)
    tool_calls: list[ExtractedToolCall] = Field(default_factory=list)
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
    """Extract tool calls from a single text chunk with bounded regex processing."""
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

    # Paging with sliding window for complete coverage on large text
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


def _extract_tools_from_thoughts(
    thoughts: list[str], available_tools: list[str] | set[str] | None
) -> tuple[list[ExtractedToolCall], list[str]]:
    """Extract tool calls embedded inside reasoning/thinking blocks."""
    tool_calls: list[ExtractedToolCall] = []
    repair_notes: list[str] = []
    for thought in thoughts:
        extracted = extract_tool_invocations(thought, available_tools)
        for call in extracted:
            if not any(c.tool_name == call.tool_name for c in tool_calls):
                tool_calls.append(call)
                repair_notes.append(f"extracted_tool_call_from_thinking:{call.tool_name}")
    return tool_calls, repair_notes


def fix_llm_response[T = Any](
    raw_response: str | Any,
    schema: type[T] | None = None,
    available_tools: list[str] | set[str] | None = None,
) -> FormattedLLMResponse[T]:
    """Universal AI/LLM response fixer and formatter.

    Ensures zero-loss recovery of valid thoughts, answers, tool calls, and structured models.
    """
    raw_str = str(raw_response) if raw_response is not None else ""
    norm_text = normalize_unicode_text(raw_str)

    thoughts: list[str] = []
    repair_notes: list[str] = []
    was_repaired = False

    # Extract all <think>...</think> and unclosed <think> blocks
    think_matches = re.findall(r"<think>(.*?)(?:</think>|$)", norm_text, flags=re.DOTALL)
    for think_match in think_matches:
        think_clean = think_match.strip()
        if think_clean and think_clean not in thoughts:
            thoughts.append(think_clean)

    # Clean text outside <think> tags
    clean_text = re.sub(r"<think>.*?</think>", "", norm_text, flags=re.DOTALL).strip()
    if "<think>" in clean_text:
        # Strip unclosed <think>
        clean_text = re.sub(r"<think>[\s\S]*$", "", clean_text).strip()

    # Tool call extraction across both clean text and thoughts
    tool_calls = extract_tool_invocations(clean_text, available_tools)
    if not tool_calls and thoughts:
        extracted_tools, thought_notes = _extract_tools_from_thoughts(thoughts, available_tools)
        if extracted_tools:
            tool_calls.extend(extracted_tools)
            was_repaired = True
            repair_notes.extend(thought_notes)

    # Content Recovery Heuristic: Only recover if explicit user-facing conclusion/answer exists
    final_content = clean_text
    if not final_content.strip() and thoughts:
        combined_thoughts = "\n\n".join(thoughts)
        conclusion_pattern = (
            r"(?:###?\s*(?:Conclusion|Summary|Findings|Report|Analysis)|"
            r"(?:Conclusion|Answer|Summary|Final Response):)\s*\n*"
            r"([\s\S]+)$"
        )
        conclusion_match = re.search(conclusion_pattern, combined_thoughts, re.IGNORECASE)
        if conclusion_match and len(conclusion_match.group(1).strip()) > 10:
            final_content = conclusion_match.group(1).strip()
            was_repaired = True
            repair_notes.append("recovered_conclusion_from_thinking")

    # Structured JSON & Pydantic model parsing
    json_data = repair_json_string(final_content or norm_text)
    parsed_model: T | None = None

    if schema is not None:
        validator = getattr(schema, "model_validate", None)
        if callable(validator) and isinstance(json_data, dict | list):
            try:
                parsed_model = validator(json_data)
            except Exception:
                pass

    return FormattedLLMResponse[T](
        content=final_content,
        raw_content=raw_str,
        thoughts=thoughts,
        tool_calls=tool_calls,
        json_data=json_data,
        parsed_model=parsed_model,
        was_repaired=was_repaired,
        repair_notes=repair_notes,
    )
