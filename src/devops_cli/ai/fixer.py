"""AI/LLM Response Fixer and Formatter.

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

_UNICODE_MAP: dict[str, str] = {
    "\u202f": " ",
    "\u00a0": " ",
    "\u200b": "",
    "\u2009": " ",
    "\u200a": " ",
    "\u2002": " ",
    "\u2003": " ",
    "\u3000": " ",
    "\ufeff": "",
    "\u2011": "-",
    "\u201c": '"',
    "\u201d": '"',
    "\u2018": "'",
    "\u2019": "'",
}


def normalize_raw_llm_text(text: str) -> str:
    """Normalize unicode spaces, smart quotes, zero-width characters, and control codes."""
    if not text:
        return ""
    for char, replacement in _UNICODE_MAP.items():
        if char in text:
            text = text.replace(char, replacement)
    return text


def repair_json_string(text: str) -> Any:
    """Extract and repair valid or partially-malformed JSON from text using json-repair."""
    if not text or not text.strip():
        return None

    cleaned = normalize_raw_llm_text(text).strip()

    # 1. First pass: use standard json_repair to parse JSON, objects, lists, or markdown fences
    try:
        data = json_repair.loads(cleaned)
        if data != "" and data is not None:
            return data
    except Exception:
        pass

    # 2. If surrounded by markdown fences, extract and repair candidate block
    for pattern in (r"```(?:json)?\s*([\s\S]*?)```",):
        m = re.search(pattern, cleaned, re.DOTALL)
        if m:
            candidate = m.group(1).strip()
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


def extract_tool_invocations(
    text: str, available_tools: list[str] | set[str] | None = None
) -> list[ExtractedToolCall]:
    """Extract tool calls from JSON structures, function signatures, or XML tags."""
    if not text:
        return []

    calls: list[ExtractedToolCall] = []
    known = set(available_tools) if available_tools else set()

    # 1. JSON-based tool call detection
    json_obj = repair_json_string(text)
    if isinstance(json_obj, dict):
        tool_name = json_obj.get("tool") or json_obj.get("name") or json_obj.get("function")
        if tool_name and isinstance(tool_name, str):
            args = json_obj.get("arguments") or json_obj.get("parameters") or {}
            if not isinstance(args, dict):
                args = {}
            if not known or tool_name in known:
                calls.append(
                    ExtractedToolCall(
                        tool_name=tool_name,
                        arguments=args,
                        raw_syntax=json.dumps(json_obj, default=str),
                    )
                )

    if isinstance(json_obj, list):
        for item in json_obj:
            if isinstance(item, dict):
                t_name = item.get("tool") or item.get("name") or item.get("function")
                if t_name and isinstance(t_name, str):
                    args = item.get("arguments") or item.get("parameters") or {}
                    if not isinstance(args, dict):
                        args = {}
                    if not known or t_name in known:
                        calls.append(
                            ExtractedToolCall(
                                tool_name=t_name,
                                arguments=args,
                                raw_syntax=json.dumps(item, default=str),
                            )
                        )

    # 2. Function-style call extraction: tool_name({"arg": "val"}) or tool_name(arg="val")
    fn_pattern = (
        r"(?:invoke|call|run|execute)?\s*`?([a-zA-Z0-9_]+)`?\s*\(\s*(\{[\s\S]*?\}|[^\)]*)\s*\)"
    )
    for m in re.finditer(fn_pattern, text):
        fn_name = m.group(1).strip()
        raw_args = m.group(2).strip()
        if known and fn_name not in known:
            continue
        if any(c.tool_name == fn_name for c in calls):
            continue

        parsed_args: dict[str, Any] = {}
        if raw_args.startswith("{") and raw_args.endswith("}"):
            parsed_json = repair_json_string(raw_args)
            if isinstance(parsed_json, dict):
                parsed_args = parsed_json
        else:
            # Parse keyword arguments: k="v", k=123
            kw_matches = re.findall(
                r'([a-zA-Z0-9_]+)\s*=\s*(?:"([^"]*)"|\'([^\']*)\'|([^\s,]+))', raw_args
            )
            for kw in kw_matches:
                k = kw[0]
                v = kw[1] or kw[2] or kw[3]
                parsed_args[k] = v

        if parsed_args or not raw_args or raw_args == "":
            calls.append(
                ExtractedToolCall(tool_name=fn_name, arguments=parsed_args, raw_syntax=m.group(0))
            )

    # 3. Intent call extraction: "We need to call tool scan_osv", "We'll invoke scan_osv"
    if not calls and known:
        intent_pattern = r"(?:call|invoke|use|run|execute)\s+(?:tool\s+)?`?([a-zA-Z0-9_]+)`?"
        for m in re.finditer(intent_pattern, text, re.IGNORECASE):
            candidate_tool = m.group(1).strip()
            if candidate_tool in known and not any(c.tool_name == candidate_tool for c in calls):
                inferred_args: dict[str, Any] = {}
                pkg_match = re.search(
                    r"(?:package|for|pkg)?\s*`?([a-zA-Z0-9_\-\.]+)(?:>=|==|<=|~=|>|<)?([0-9\.]*)?`?",
                    text,
                    re.IGNORECASE,
                )
                if pkg_match and pkg_match.group(1) not in (
                    "tool",
                    "that",
                    "this",
                    "the",
                    candidate_tool,
                ):
                    inferred_args["package_name"] = pkg_match.group(1).strip()
                    if pkg_match.group(2):
                        inferred_args["version"] = pkg_match.group(2).strip()

                calls.append(
                    ExtractedToolCall(
                        tool_name=candidate_tool,
                        arguments=inferred_args,
                        raw_syntax=m.group(0),
                    )
                )

    return calls


def fix_llm_response[T = Any](
    raw_response: str | Any,
    schema: type[T] | None = None,
    available_tools: list[str] | set[str] | None = None,
) -> FormattedLLMResponse[T]:
    """Universal AI/LLM response fixer and formatter.

    Ensures zero-loss recovery of valid thoughts, answers, tool calls, and structured models.
    """
    raw_str = str(raw_response) if raw_response is not None else ""
    norm_text = normalize_raw_llm_text(raw_str)

    thoughts: list[str] = []
    repair_notes: list[str] = []
    was_repaired = False

    # Extract all <think>...</think> and unclosed <think> blocks
    think_matches = re.findall(r"<think>(.*?)(?:</think>|$)", norm_text, flags=re.DOTALL)
    for tm in think_matches:
        t_clean = tm.strip()
        if t_clean and t_clean not in thoughts:
            thoughts.append(t_clean)

    # Clean text outside <think> tags
    clean_text = re.sub(r"<think>.*?</think>", "", norm_text, flags=re.DOTALL).strip()
    if "<think>" in clean_text:
        # Strip unclosed <think>
        clean_text = re.sub(r"<think>[\s\S]*$", "", clean_text).strip()

    # Tool call extraction across both clean text and thoughts
    tool_calls = extract_tool_invocations(clean_text, available_tools)
    if not tool_calls and thoughts:
        # Check thoughts for tool calls
        for th in thoughts:
            extracted_th_tools = extract_tool_invocations(th, available_tools)
            for tc in extracted_th_tools:
                if not any(c.tool_name == tc.tool_name for c in tool_calls):
                    tool_calls.append(tc)
                    was_repaired = True
                    repair_notes.append(f"extracted_tool_call_from_thinking:{tc.tool_name}")

    # Content Recovery Heuristic: If clean_text is empty, recover answer from thinking
    final_content = clean_text
    if not final_content.strip() and thoughts:
        combined_th = "\n\n".join(thoughts)
        # 1. Look for conclusion paragraphs or direct answers inside thinking
        concl_pattern = (
            r"(?:Conclusion|Summary|Answer|Response|Result|In summary|To summarize)[:\n]\s*"
            r"([\s\S]+)$"
        )
        concl_match = re.search(concl_pattern, combined_th, re.IGNORECASE)
        if concl_match and len(concl_match.group(1).strip()) > 10:
            final_content = concl_match.group(1).strip()
            was_repaired = True
            repair_notes.append("recovered_conclusion_from_thinking")
        else:
            # 2. Extract the last markdown paragraph or readable text block from thoughts
            paragraphs = [p.strip() for p in combined_th.split("\n\n") if p.strip()]
            non_meta_paragraphs = [
                p
                for p in paragraphs
                if not p.lower().startswith(
                    (
                        "we need to",
                        "let's check",
                        "let's invoke",
                        "i will run",
                        "function signature",
                    )
                )
            ]
            if non_meta_paragraphs:
                final_content = non_meta_paragraphs[-1]
                was_repaired = True
                repair_notes.append("recovered_last_paragraph_from_thinking")
            elif paragraphs:
                final_content = paragraphs[-1]
                was_repaired = True
                repair_notes.append("recovered_thinking_paragraph")

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
