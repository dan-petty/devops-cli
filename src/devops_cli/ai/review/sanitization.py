"""Sanitization, prompt boundary tag escaping, and secret masking utilities."""

from __future__ import annotations

import re


def balance_markdown_fences(text: str) -> tuple[str, bool]:
    """Inspect line-start code fence delimiters and ensure any unclosed code block is closed.

    Returns:
        tuple[str, bool]: (balanced_text, has_fences) where has_fences indicates
        whether any line-start code fences were detected.
    """
    lines = text.split("\n")
    open_fence_char: str | None = None
    open_fence_len = 0
    has_fences = False
    fence_pattern = re.compile(r"^[ ]{0,3}(`{3,}|~{3,})(.*)$")

    for line in lines:
        m = fence_pattern.match(line)
        if not m:
            continue
        delimiter = m.group(1)
        char = delimiter[0]
        length = len(delimiter)
        rest = m.group(2).strip()

        if open_fence_char is None:
            open_fence_char = char
            open_fence_len = length
            has_fences = True
        elif char == open_fence_char and length >= open_fence_len and not rest:
            open_fence_char = None
            open_fence_len = 0

    if open_fence_char is not None:
        closing_fence = open_fence_char * open_fence_len
        return f"{text}\n{closing_fence}", True

    return text, has_fences


def escape_markdown_title(title: str, is_table: bool = False) -> str:
    """Escape un-backticked asterisks and control characters in finding titles."""
    clean = title.replace("\n", " ").strip()
    if is_table:
        clean = clean.replace("|", "\\|")
    if clean.count("`") % 2 != 0:
        clean += "`"

    parts = clean.split("`")
    escaped_parts: list[str] = []
    for idx, part in enumerate(parts):
        if idx % 2 == 0:
            escaped_part = re.sub(r"(?<!\\)\*", r"\*", part)
            escaped_parts.append(escaped_part)
        else:
            escaped_parts.append(part)

    return "`".join(escaped_parts)
