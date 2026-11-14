"""Render the findings of the agent audit as a table or as JSON (#2346).

The report holds only sanitized text: a signature, its counts, its elapsed time, the group that the
model gave it, and the pointer of each session. A transcript line, an output and a secret never
reach it, because a finding holds a signature and no raw line (#2346, AGENTS.md rule 10).

A finding that an open issue names is rendered apart from the new findings, so a reader sees the
problems that no issue holds yet.
"""

from __future__ import annotations

import json
from collections.abc import Sequence

from devops_cli.ai.agent_audit.finding import Finding
from devops_cli.ai.agent_audit.transcript import sanitize_text
from devops_cli.exceptions.validation import ValidationError

_NEW_TITLE = "Recurring problems"
_TRACKED_TITLE = "Tracked by an open issue"
_EMPTY = "No recurring problem was found."
# The columns of the table. The group column appears only when the model gave a finding a group.
_COLUMNS = ("SESSIONS", "COUNT", "ELAPSED", "SIGNATURE", "GROUP")
_SECONDS_PER_MINUTE = 60
_SECONDS_PER_HOUR = 3_600
_SECONDS_PER_DAY = 86_400
_UNITS: tuple[tuple[int, str], ...] = (
    (_SECONDS_PER_DAY, "d"),
    (_SECONDS_PER_HOUR, "h"),
    (_SECONDS_PER_MINUTE, "m"),
)
_MAX_UNITS = 2


def render_report(findings: Sequence[Finding], output_format: str = "table") -> str:
    """The report of `findings` as an aligned table or as JSON (#2346)."""
    match output_format:
        case "json":
            return _json_report(findings)
        case "table":
            return _table_report(findings)
        case _:
            raise ValidationError(
                f"Unknown report format {output_format!r}. Choose one of: json, table."
            )


def _table_report(findings: Sequence[Finding]) -> str:
    """The report as a table, with the new findings above the tracked ones."""
    lines = [
        *_section(_NEW_TITLE, [each for each in findings if not each.tracked]),
        *_section(_TRACKED_TITLE, [each for each in findings if each.tracked]),
    ]
    if not lines:
        return _EMPTY + "\n"
    return "\n".join(lines).rstrip("\n") + "\n"


def _section(title: str, findings: Sequence[Finding]) -> list[str]:
    """The title and the table of one section, or nothing when it holds no finding."""
    if not findings:
        return []
    with_group = any(each.group for each in findings)
    rows = [_columns(with_group), *(_row(each, with_group=with_group) for each in findings)]
    return [title, *_aligned(rows), ""]


def _columns(with_group: bool) -> list[str]:
    """The header of the table, with the group column when a finding holds a group."""
    return list(_COLUMNS) if with_group else list(_COLUMNS[:-1])


def _row(finding: Finding, *, with_group: bool) -> list[str]:
    """The cells of one finding, each of them sanitized."""
    row = [
        str(finding.sessions),
        str(finding.recurrences),
        _elapsed(finding.elapsed_seconds),
        sanitize_text(finding.signature),
    ]
    if with_group:
        row.append(sanitize_text(finding.group or ""))
    return row


def _aligned(rows: Sequence[Sequence[str]]) -> list[str]:
    """The rows padded to one width for each column, with no trailing space."""
    widths = [max(len(row[index]) for row in rows) for index in range(len(rows[0]))]
    return [
        "  ".join(cell.ljust(width) for cell, width in zip(row, widths, strict=True)).rstrip()
        for row in rows
    ]


def _elapsed(seconds: float) -> str:
    """A span in seconds as at most two units, such as `2d 3h`, `4m 5s` or `7s`."""
    total = max(int(seconds), 0)
    parts: list[str] = []
    rest = total
    for size, suffix in _UNITS:
        count, rest = divmod(rest, size)
        if count:
            parts.append(f"{count}{suffix}")
    if rest or not parts:
        parts.append(f"{rest}s")
    return " ".join(parts[:_MAX_UNITS])


def _json_report(findings: Sequence[Finding]) -> str:
    """The report as JSON, with the new findings and the tracked ones in two lists."""
    payload = {
        "findings": [_json_finding(each) for each in findings if not each.tracked],
        "tracked": [_json_finding(each) for each in findings if each.tracked],
    }
    return json.dumps(payload, indent=2) + "\n"


def _json_finding(finding: Finding) -> dict[str, object]:
    """One finding as JSON, with each text sanitized."""
    return {
        "signature": sanitize_text(finding.signature),
        "sessions": finding.sessions,
        "recurrences": finding.recurrences,
        "elapsed_seconds": round(finding.elapsed_seconds, 3),
        "pointers": [
            {
                "session": sanitize_text(pointer.session),
                "file": sanitize_text(str(pointer.file)),
                "line": pointer.line,
            }
            for pointer in finding.pointers
        ],
        "group": sanitize_text(finding.group) if finding.group else None,
    }


__all__ = ["render_report"]
