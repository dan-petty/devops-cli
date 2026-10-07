"""Fingerprint v2 computation for review findings (#871, #1141).

A stable finding identity independent of line insertions and cosmetic changes.
"""

from __future__ import annotations

import hashlib
import re

_WHITESPACE_RE = re.compile(r"\s+")


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
        symbol = enclosing_symbol.strip() if enclosing_symbol else "<module>"
        win_hash = compute_window_hash(file_content, start_line)
        elements = [clean_tool, clean_rule, path.strip(), symbol, win_hash]
    elif logical_location:
        elements = [clean_tool, clean_rule, logical_location.strip()]
    else:
        elements = [clean_tool, clean_rule, path.strip()]

    if occurrence_index > 0:
        elements.append(str(occurrence_index))

    raw = "␟".join(elements)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()
