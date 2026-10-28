"""AI/LLM Response Sanitizer and Output Repair Engine built on pydantic_ai.messages.

Repairs malformed outputs, extracts embedded tool calls, separates reasoning/thinking blocks,
and normalizes responses across all LLM providers using standard pydantic_ai.messages.
"""

from __future__ import annotations

import json
import re
from collections.abc import Sequence
from typing import TYPE_CHECKING, Any

import json_repair
from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from pydantic_ai.messages import (
        ModelResponse,
        ModelResponsePart,
        TextPart,
        ThinkingPart,
        ToolCallPart,
    )
    from pydantic_ai.usage import RequestUsage
else:
    ModelResponse = Any
    ModelResponsePart = Any
    TextPart = Any
    ThinkingPart = Any
    ToolCallPart = Any
    RequestUsage = Any

from devops_cli.ai.text_utils import normalize_unicode_text, unique_lines
from devops_cli.config.constants import CONST_JSON_REPAIR_SOURCE_REPAIR_JSON_STRING
from devops_cli.config.defaults import (
    DEFAULT_JSON_REPAIR_MAX_LENGTH,
    DEFAULT_TOOL_EXTRACT_OVERLAP,
    DEFAULT_TOOL_EXTRACT_PAGE_SIZE,
)
from devops_cli.telemetry.instruments import AI_JSON_REPAIRS_TOTAL, emit

__all__ = [
    "ExtractedToolCall",
    "FormattedLLMResponse",
    "extract_model_response_parts",
    "extract_tool_invocations",
    "fix_llm_response",
    "parse_model_response",
    "repair_json",
    "repair_json_string",
]

_TOOL_EXTRACT_PAGE_SIZE = DEFAULT_TOOL_EXTRACT_PAGE_SIZE
_TOOL_EXTRACT_OVERLAP = DEFAULT_TOOL_EXTRACT_OVERLAP


# A ```json or bare ``` fence opening a line of its own and closed by a ``` line of its own; a
# fence naming another language holds code, not the answer.
_JSON_FENCE = re.compile(
    r"^[ \t]*```(?:json)?[ \t]*\r?\n(.*?)^[ \t]*```[ \t]*\r?$",
    re.IGNORECASE | re.MULTILINE | re.DOTALL,
)
# `strict=False` admits the raw newlines a model leaves inside a JSON string.
_LENIENT_JSON = json.JSONDecoder(strict=False)


def _clean_repair_text(text: str, max_length: int | None = None) -> str | None:
    effective_max = DEFAULT_JSON_REPAIR_MAX_LENGTH if max_length is None else max_length
    if not text or not text.strip() or len(text) > effective_max:
        return None
    cleaned = _strip_reasoning(normalize_unicode_text(text))
    return cleaned if cleaned else None


def _is_structured(value: Any) -> bool:
    """An object or a list of objects: the shapes a structured answer takes."""
    if isinstance(value, list):
        return all(isinstance(item, dict) for item in value)
    return isinstance(value, dict)


def _fenced_value(cleaned: str, block: re.Match[str]) -> Any:
    """The JSON value a fenced block opens with, or None when it holds none.

    The value is decoded to its own end, not to the fence that closed the block: a string
    holding a fence of its own on a line by itself would otherwise cut the block short.
    """
    body = block.group(1)
    start = block.start(1) + len(body) - len(body.lstrip())
    try:
        return _LENIENT_JSON.raw_decode(cleaned, start)[0]
    except ValueError, RecursionError:
        return None


def _fenced_json(cleaned: str) -> list[Any]:
    """The non-empty objects and lists of objects the reply's fenced blocks hold."""
    values = (_fenced_value(cleaned, block) for block in _JSON_FENCE.finditer(cleaned))
    return [value for value in values if value and _is_structured(value)]


def _lone_answer(values: Any) -> Any:
    """The one object or list of objects among the values json-repair read, or None.

    json-repair reads each bracketed run of prose as a value of its own and returns them with
    the answer as one list. A string among them means a bracket left open swallowed the rest
    of the reply instead, and none of it is taken.
    """
    if not (isinstance(values, list) and all(isinstance(value, dict | list) for value in values)):
        return None
    answers = [value for value in values if _is_structured(value)]
    return answers[0] if len(answers) == 1 else None


def _repair_cleaned_json(cleaned: str) -> Any:
    """Repair cleaned text via json-repair, extracting a lone structured answer when prose holds brackets."""
    whole = _repair_loads(cleaned)
    if _is_structured(whole):
        return whole
    answer = _lone_answer(whole)
    if answer is not None:
        return answer
    return whole if whole not in ("", None) else None


def repair_json(
    text: str,
    *,
    source: str,
    max_length: int | None = None,
) -> tuple[Any, bool]:
    """Parse JSON strictly first, falling back to json-repair and counting repairs by entry point (#875)."""
    cleaned = _clean_repair_text(text, max_length)
    if cleaned is None:
        return None, False
    try:
        return json.loads(cleaned), False
    except json.JSONDecodeError, RecursionError:
        pass
    fenced = _fenced_json(cleaned)
    if len(fenced) == 1:
        return fenced[0], False
    repaired = _repair_cleaned_json(cleaned)
    if repaired is None:
        return None, False
    emit(AI_JSON_REPAIRS_TOTAL, 1.0, attributes={"source": source})
    return repaired, True


def repair_json_string(text: str, *, max_length: int | None = None) -> Any:
    """Extract and repair valid or partially-malformed JSON from text using json-repair.

    A lone fenced block holding an object or a list of objects is the answer, read exactly.
    Otherwise the whole reply is repaired. json-repair reads bracketed prose, such as a
    markdown link or `items[0]`, as values beside the answer, so a list of such values
    yields its one object or list of objects.
    """
    value, _ = repair_json(
        text,
        source=CONST_JSON_REPAIR_SOURCE_REPAIR_JSON_STRING,
        max_length=max_length,
    )
    return value


def _strip_reasoning(text: str) -> str:
    """Remove <think> blocks from a complete reply.

    An unclosed <think> counts as reasoning cut off mid-stream only when it opens the reply;
    anywhere else it is literal text, such as a finding that quotes the tag, and must not
    truncate the reply.
    """
    clean = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
    return "" if clean.startswith("<think>") else clean


def _repair_loads(text: str) -> Any:
    try:
        return json_repair.loads(text)
    except Exception:
        return None


class ExtractedToolCall(BaseModel):
    """Normalized tool call extracted from raw LLM output."""

    tool_name: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    raw_syntax: str = ""


class FormattedLLMResponse(BaseModel):
    """Standardized, repaired, and formatted LLM response backed by pydantic_ai.messages."""

    content: str
    raw_content: str
    thoughts: list[str] = Field(default_factory=list)
    thinking: str | None = None
    tool_calls: list[ExtractedToolCall] = Field(default_factory=list)
    model_response: ModelResponse | None = None
    json_data: Any = None
    was_repaired: bool = False


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


def _extract_json_tool_calls(json_obj: Any, known_tool_names: set[str]) -> list[ExtractedToolCall]:
    """Extract structured tool calls from parsed JSON structures."""
    items = (
        [json_obj]
        if isinstance(json_obj, dict)
        else (json_obj if isinstance(json_obj, list) else [])
    )
    calls: list[ExtractedToolCall] = []
    for item in items:
        if isinstance(item, dict):
            call = _extract_json_dict_tool_call(item, known_tool_names)
            if call:
                calls.append(call)
    return calls


def _parse_fn_args(raw_args: str) -> dict[str, Any]:
    """Parse function-style arguments into a key-value dictionary."""
    if raw_args.startswith("{") and raw_args.endswith("}"):
        parsed_json = repair_json_string(raw_args)
        return parsed_json if isinstance(parsed_json, dict) else {}
    parsed_args: dict[str, Any] = {}
    kw_matches = re.findall(r'([a-zA-Z0-9_]+)\s*=\s*(?:"([^"]*)"|\'([^\']*)\'|([^\s,]+))', raw_args)
    for kw in kw_matches:
        parsed_args[kw[0]] = kw[1] or kw[2] or kw[3]
    return parsed_args


def _extract_tool_invocations_from_chunk(
    text: str,
    known_tool_names: set[str],
) -> list[ExtractedToolCall]:
    """Extract tool calls from a single text chunk with bounded parsing."""
    calls = _extract_json_tool_calls(repair_json_string(text), known_tool_names)

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

        parsed_args = _parse_fn_args(raw_args)
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


def _extract_thinking_parts(norm_text: str, raw_response: Any) -> list[ThinkingPart]:
    from pydantic_ai.messages import ThinkingPart

    parts: list[ThinkingPart] = []
    seen: set[str] = set()

    raw_thinking = getattr(raw_response, "thinking", None)
    if raw_thinking and isinstance(raw_thinking, str) and raw_thinking.strip():
        clean_raw = unique_lines(raw_thinking.strip())
        parts.append(ThinkingPart(content=clean_raw))
        seen.add(clean_raw)

    for think_match in re.findall(r"<think>(.*?)(?:</think>|$)", norm_text, flags=re.DOTALL):
        think_clean = unique_lines(think_match.strip())
        if think_clean and think_clean not in seen:
            seen.add(think_clean)
            parts.append(ThinkingPart(content=think_clean))
    return parts


def _extract_response_tool_parts(clean_text: str, norm_text: str) -> list[ToolCallPart]:
    from pydantic_ai.messages import ToolCallPart

    tool_calls = extract_tool_invocations(clean_text)
    if not tool_calls and norm_text != clean_text:
        tool_calls = extract_tool_invocations(norm_text)
    return [ToolCallPart(tool_name=tc.tool_name, args=tc.arguments) for tc in tool_calls]


def parse_model_response(
    raw_response: str | Any,
    model_name: str | None = None,
) -> ModelResponse:
    """Parse raw response, string, or LLMResponse into standard pydantic_ai.messages.ModelResponse."""
    from pydantic_ai.messages import (
        ModelResponse,
        TextPart,
    )
    from pydantic_ai.usage import RequestUsage

    if isinstance(raw_response, ModelResponse):
        return raw_response

    if hasattr(raw_response, "to_model_response") and callable(raw_response.to_model_response):
        res = raw_response.to_model_response(model_name=model_name)
        if isinstance(res, ModelResponse):
            return res

    raw_str = str(raw_response) if raw_response is not None else ""
    norm_text = normalize_unicode_text(raw_str)
    clean_text = _strip_reasoning(norm_text)

    parts: list[ModelResponsePart] = []
    parts.extend(_extract_thinking_parts(norm_text, raw_response))
    parts.extend(_extract_response_tool_parts(clean_text, norm_text))
    if clean_text:
        parts.append(TextPart(content=clean_text))

    return ModelResponse(parts=parts, model_name=model_name, usage=RequestUsage())


def extract_model_response_parts(
    response: ModelResponse,
) -> tuple[str, str | None, list[ToolCallPart]]:
    """Extract clean content, isolated thinking, and tool calls from ModelResponse."""
    from pydantic_ai.messages import TextPart, ThinkingPart, ToolCallPart

    texts = [p.content for p in response.parts if isinstance(p, TextPart) and p.has_content()]
    thinks = [p.content for p in response.parts if isinstance(p, ThinkingPart) and p.has_content()]
    tool_calls = [p for p in response.parts if isinstance(p, ToolCallPart)]
    clean_text = "\n".join(texts)
    thinking_text = unique_lines("\n\n".join(thinks)) if thinks else None
    return clean_text, thinking_text, tool_calls


def _build_extracted_tool_calls(
    tool_parts: Sequence[ToolCallPart],
    available_tools: list[str] | set[str] | None,
) -> list[ExtractedToolCall]:
    """Construct and filter ExtractedToolCall list from model response parts."""
    calls = [
        ExtractedToolCall(
            tool_name=p.tool_name,
            arguments=p.args if isinstance(p.args, dict) else {},
            raw_syntax=f'{{"tool": "{p.tool_name}", "arguments": {json.dumps(p.args if isinstance(p.args, dict) else {})}}}',
        )
        for p in tool_parts
    ]
    if available_tools:
        known = set(available_tools)
        return [c for c in calls if c.tool_name in known]
    return calls


def fix_llm_response(
    raw_response: str | Any,
    available_tools: list[str] | set[str] | None = None,
) -> FormattedLLMResponse:
    """Universal AI/LLM response parser and formatter built on pydantic_ai.messages.ModelResponse."""
    from pydantic_ai.messages import ThinkingPart

    resp = parse_model_response(raw_response)
    final_content, thinking_str, tool_parts = extract_model_response_parts(resp)
    tool_calls = _build_extracted_tool_calls(tool_parts, available_tools)
    thoughts = [p.content for p in resp.parts if isinstance(p, ThinkingPart) and p.has_content()]

    json_data = repair_json_string(final_content)

    raw_str = str(raw_response) if raw_response is not None else ""
    was_repaired = bool(
        tool_calls
        or thoughts
        or (json_data is not None and json_data != final_content)
        or (final_content.strip() != raw_str.strip())
    )

    return FormattedLLMResponse(
        content=final_content,
        raw_content=raw_str,
        thoughts=thoughts,
        thinking=thinking_str,
        tool_calls=tool_calls,
        model_response=resp,
        json_data=json_data,
        was_repaired=was_repaired,
    )
