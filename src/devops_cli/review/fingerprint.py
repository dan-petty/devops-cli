"""Fingerprint v2 computation for review findings (#871, #1141).

A stable finding identity independent of line insertions and cosmetic changes.
"""

from __future__ import annotations

import ast
import hashlib
import re

_WHITESPACE_RE = re.compile(r"\s+")


def extract_enclosing_symbol(file_content: str, start_line: int) -> str:
    """Extract enclosing qualified symbol from Python AST, falling back to '<module>'."""
    try:
        tree = ast.parse(file_content)
    except Exception:
        return "<module>"

    matched: list[tuple[int, str]] = []

    def _walk(node: ast.AST, prefix: list[str]) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                c_start = getattr(child, "lineno", None)
                c_end = getattr(child, "end_lineno", None)
                current_prefix = prefix + [child.name]
                if c_start is not None and c_end is not None and c_start <= start_line <= c_end:
                    span = c_end - c_start
                    matched.append((span, ".".join(current_prefix)))
                _walk(child, current_prefix)

    _walk(tree, [])
    if not matched:
        return "<module>"
    matched.sort(key=lambda item: item[0])
    return matched[0][1]


def compute_window_hash(file_content: str, start_line: int, window_chars: int = 100) -> str:
    """Compute hash over the first N non-whitespace characters starting at the flagged line."""
    lines = file_content.splitlines()
    if not (1 <= start_line <= len(lines)):
        return ""
    # Slice from start_line - 1 onwards
    relevant_text = "\n".join(lines[start_line - 1 :])
    non_ws = _WHITESPACE_RE.sub("", relevant_text)
    window = non_ws[:window_chars]
    return hashlib.sha256(window.encode("utf-8")).hexdigest()[:16]


def compute_fingerprint_v2(
    *,
    tool: str,
    rule_id: str,
    path: str = "",
    start_line: int | None = None,
    file_content: str | None = None,
    enclosing_symbol: str | None = None,
    logical_location: str | None = None,
    occurrence_index: int = 0,
) -> str:
    """Compute stable fingerprint v2 for a finding.

    - For results with a file region: sha256 of tool, rule_id, repo-relative path,
      enclosing symbol (or '<module>'), and 100-char non-whitespace window hash.
    - For results without a region: sha256 of tool, rule_id, and logical_location.
    - An occurrence index is appended if non-zero.
    """
    clean_tool = tool.strip()
    clean_rule = rule_id.strip()

    if path and start_line is not None and file_content is not None:
        if enclosing_symbol:
            symbol = enclosing_symbol.strip()
        else:
            symbol = extract_enclosing_symbol(file_content, start_line)
        win_hash = compute_window_hash(file_content, start_line)
        elements = [clean_tool, clean_rule, path.strip(), symbol, win_hash]
    elif logical_location:
        elements = [clean_tool, clean_rule, logical_location.strip()]
    elif enclosing_symbol:
        elements = [clean_tool, clean_rule, path.strip(), enclosing_symbol.strip()]
    else:
        elements = [clean_tool, clean_rule, path.strip()]

    if occurrence_index > 0:
        elements.append(str(occurrence_index))

    raw = "␟".join(elements)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


__all__ = [
    "compute_fingerprint_v2",
    "compute_window_hash",
    "extract_enclosing_symbol",
]
