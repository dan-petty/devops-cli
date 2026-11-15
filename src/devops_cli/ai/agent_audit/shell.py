"""Read the shell history of the person as the commands that the audit counts (#2346).

zsh writes its extended history as one entry for each command, `: <epoch>:<seconds>;<command>`, so
an entry holds the time that the command started and the text that the person typed. A command that
the person typed over several lines is one entry whose lines end with a backslash, and the entry is
joined here, so one command stays one record.

The history holds no exit status: it shows the commands that return, not the ones that fail, which
is why a transcript remains the default source of the audit (design.md). The audit still counts a
command that the history repeats in session after session.

Each command passes through `sanitize_text`, so a secret, a private host name and an email address
never reach the report, the store or a model (#2346, AGENTS.md rule 10).
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from pathlib import Path

from devops_cli.ai.agent_audit.transcript import ToolCall, sanitize_text

# The history that zsh writes, which is the one format that names the time of an entry.
_HISTORY_FILE = ".zsh_history"
# An entry of the extended format: the start time as an epoch and its seconds, then the command.
_EXTENDED_ENTRY_RE = re.compile(r"^: (?P<epoch>\d+):\d+;(?P<command>.*)$")
# A history of a long-lived host grows without a bound, and the audit reads within the time budget
# of a check (AGENTS.md rule 5), so it reads the start of the file and no more.
_MAX_BYTES = 4 * 1024 * 1024


def history_paths(home: Path) -> tuple[Path, ...]:
    """The shell history of `home`, or nothing when the person keeps none (#2346)."""
    path = home / _HISTORY_FILE
    return (path,) if path.is_file() else ()


def parse_shell_history(path: Path) -> tuple[ToolCall, ...]:
    """Each command of the shell history at `path`, with the time that its entry names (#2346).

    A line without the extended prefix is a command of a history that the shell wrote without
    time, and it keeps no timestamp. A file that the OS refuses to read gives no record, because
    the audit reports the problems of the sessions and not the permissions of the host.
    """
    if not path.is_file():
        return ()
    records: list[ToolCall] = []
    for number, line in _joined(_lines(path)):
        command, timestamp = _entry(line)
        if command:
            records.append(_record(path, number, command, timestamp))
    return tuple(records)


def _record(path: Path, number: int, command: str, timestamp: str) -> ToolCall:
    """The record of one command of the history at `path`, on its line `number`."""
    return ToolCall(
        session=path.name,
        file=path,
        line=number,
        timestamp=timestamp,
        command=sanitize_text(command),
        output="",
        is_error=False,
    )


def _entry(line: str) -> tuple[str, str]:
    """The command and the time of one history line, which the extended format prefixes."""
    match = _EXTENDED_ENTRY_RE.match(line)
    if match is None:
        return line.strip(), ""
    return match.group("command").strip(), _timestamp(match.group("epoch"))


def _timestamp(epoch: str) -> str:
    """The time of an extended entry as ISO 8601, or nothing when the value names no time."""
    try:
        return datetime.fromtimestamp(int(epoch), tz=UTC).isoformat()
    except OSError, OverflowError, ValueError:
        return ""


def _joined(lines: list[tuple[int, str]]) -> list[tuple[int, str]]:
    """The lines of a history, with each command that it wrote over several lines joined."""
    joined: list[tuple[int, str]] = []
    for number, line in lines:
        if joined and joined[-1][1].endswith("\\"):
            first, previous = joined[-1]
            joined[-1] = (first, previous[:-1] + line)
            continue
        joined.append((number, line))
    return joined


def _lines(path: Path) -> list[tuple[int, str]]:
    """The lines of the history at `path`, each with the number of its line, up to the bound."""
    try:
        with path.open("rb") as history:
            text = history.read(_MAX_BYTES).decode("utf-8", errors="replace")
    except OSError:
        return []
    return list(enumerate(text.splitlines(), start=1))


__all__ = ["history_paths", "parse_shell_history"]
