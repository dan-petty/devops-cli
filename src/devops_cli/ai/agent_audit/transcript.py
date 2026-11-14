"""Read the Claude Code session transcripts into sanitized tool calls (#2346).

A transcript is one JSON record per line. The audit counts the shell commands that agents run and
the ones that fail, so the reader keeps a call whose input holds a `command`: an assistant record
holds the `tool_use` block, and the user record that answers it holds the `tool_result` block with
the output and the error flag. A subagent transcript, under `<session>/subagents/`, rolls into its
parent session, so a failure that a subagent met counts for the session that started it.

Each command and each output passes through `sanitize_text` before it leaves the reader: a secret,
a private host name or address, and an email address never reach the report, the store or a model
(#2346, AGENTS.md rule 10).
"""

from __future__ import annotations

import json
import re
import time
from collections.abc import Iterable, Iterator, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from devops_cli.security.sanitizer import mask_private_hosts, mask_secrets

# The record types of a Claude Code transcript that the reader knows: the two that hold a tool call
# or its result, and the ones that hold no tool call. A record of another type is skipped and
# counted, because the tool adds a record type from time to time (#2346).
_KNOWN_RECORD_TYPES: frozenset[str] = frozenset(
    {
        "assistant",
        "file-history-snapshot",
        "progress",
        "queue-operation",
        "summary",
        "system",
        "user",
    }
)
# The directory of the subagent transcripts of a session, whose records count for the parent.
_SUBAGENTS_DIR = "subagents"
_TOOL_USE = "tool_use"
_TOOL_RESULT = "tool_result"
# A personal email address is masked whole: no part of it leaves the host (SECURITY.md rule 13).
_EMAIL_ADDRESS_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
_MASKED_EMAIL = "<masked-email>"
_SECONDS_PER_DAY = 86_400


@dataclass(frozen=True, slots=True)
class ToolCall:
    """One shell command of a session, with the result that answered it."""

    session: str
    file: Path
    line: int
    timestamp: str
    command: str
    output: str
    is_error: bool


@dataclass(frozen=True, slots=True)
class TranscriptScan:
    """The tool calls that the reader kept, the records it did not know and the files it read."""

    calls: tuple[ToolCall, ...]
    unknown_records: int
    files_read: int


@dataclass(frozen=True, slots=True)
class _PendingCall:
    """A `tool_use` block whose `tool_result` block the reader has not read yet."""

    session: str
    file: Path
    line: int
    timestamp: str
    command: str


def sanitize_text(text: str) -> str:
    """Mask the secrets, the private hosts and the email addresses of a kept line (#2346)."""
    if not text:
        return ""
    return _EMAIL_ADDRESS_RE.sub(_MASKED_EMAIL, mask_private_hosts(mask_secrets(text)))


def read_transcripts(paths: Iterable[Path], since_days: int | None = None) -> TranscriptScan:
    """Read the transcripts of `paths` into one scan, skipping a file older than `since_days`.

    A file that the `since_days` cutoff leaves out is never opened, so a run over a host whose
    transcripts total gigabytes stays within the time budget of a check (AGENTS.md rule 5).
    """
    cutoff = _cutoff(since_days)
    calls: list[ToolCall] = []
    unknown_records = 0
    files_read = 0
    for path in _recent_files(paths, cutoff):
        file_calls, file_unknown_records = _read_file(path)
        calls.extend(file_calls)
        unknown_records += file_unknown_records
        files_read += 1
    return TranscriptScan(
        calls=tuple(calls), unknown_records=unknown_records, files_read=files_read
    )


def _cutoff(since_days: int | None) -> float | None:
    """The oldest modification time that `since_days` keeps, or None when it names no window."""
    if since_days is None:
        return None
    return time.time() - since_days * _SECONDS_PER_DAY


def _recent_files(paths: Iterable[Path], cutoff: float | None) -> Iterator[Path]:
    """Each named file once, in order, that exists and that `cutoff` keeps."""
    seen: set[Path] = set()
    for raw_path in paths:
        path = Path(raw_path)
        if path in seen:
            continue
        seen.add(path)
        if not path.is_file():
            continue
        if cutoff is not None and path.stat().st_mtime < cutoff:
            continue
        yield path


def _read_file(path: Path) -> tuple[list[ToolCall], int]:
    """The tool calls of one transcript, and the number of its records of an unknown type."""
    session = _session_of(path)
    pending: dict[str, _PendingCall] = {}
    calls: list[ToolCall] = []
    unknown_records = 0
    with path.open(encoding="utf-8", errors="replace") as transcript:
        for number, raw in enumerate(transcript, start=1):
            record = _record(raw)
            if record is None:
                continue
            record_type = record.get("type")
            if record_type not in _KNOWN_RECORD_TYPES:
                unknown_records += 1
                continue
            match record_type:
                case "assistant":
                    _collect_tool_uses(record, session, path, number, pending)
                case "user":
                    _collect_tool_results(record, pending, calls)
                case _:
                    continue
    calls.extend(_unanswered_calls(pending))
    return calls, unknown_records


def _record(raw: str) -> Mapping[str, Any] | None:
    """One record of a transcript line, or None when the line holds no JSON object."""
    line = raw.strip()
    if not line:
        return None
    try:
        record = json.loads(line)
    except json.JSONDecodeError:
        return None
    return record if isinstance(record, dict) else None


def _session_of(path: Path) -> str:
    """The session of a transcript: the parent session of a subagent file, else the file's stem."""
    if path.parent.name == _SUBAGENTS_DIR:
        return path.parent.parent.name
    return path.stem


def _collect_tool_uses(
    record: Mapping[str, Any],
    session: str,
    path: Path,
    number: int,
    pending: dict[str, _PendingCall],
) -> None:
    """Hold each shell command of an assistant record until its result arrives."""
    timestamp = _text(record.get("timestamp"))
    for block in _content_blocks(record):
        if block.get("type") != _TOOL_USE:
            continue
        command = _command_of(block)
        if command is None:
            continue
        pending[_text(block.get("id"))] = _PendingCall(
            session=session,
            file=path,
            line=number,
            timestamp=timestamp,
            command=sanitize_text(command),
        )


def _command_of(block: Mapping[str, Any]) -> str | None:
    """The shell command that a `tool_use` block names, or None for another tool."""
    tool_input = block.get("input")
    if not isinstance(tool_input, dict):
        return None
    command = tool_input.get("command")
    if not isinstance(command, str) or not command.strip():
        return None
    return command


def _collect_tool_results(
    record: Mapping[str, Any], pending: dict[str, _PendingCall], calls: list[ToolCall]
) -> None:
    """Pair each result of a user record with the command that it answers."""
    for block in _content_blocks(record):
        if block.get("type") != _TOOL_RESULT:
            continue
        call = pending.pop(_text(block.get("tool_use_id")), None)
        if call is None:
            continue
        calls.append(
            ToolCall(
                session=call.session,
                file=call.file,
                line=call.line,
                timestamp=call.timestamp,
                command=call.command,
                output=sanitize_text(_result_text(block.get("content"))),
                is_error=block.get("is_error") is True,
            )
        )


def _content_blocks(record: Mapping[str, Any]) -> Iterator[Mapping[str, Any]]:
    """Each content block of the message of a record."""
    message = record.get("message")
    if not isinstance(message, dict):
        return
    content = message.get("content")
    if not isinstance(content, list):
        return
    for block in content:
        if isinstance(block, dict):
            yield block


def _result_text(content: Any) -> str:
    """The text of a `tool_result` block, which the format writes as text or as blocks."""
    match content:
        case str():
            return content
        case list():
            return "\n".join(
                block["text"]
                for block in content
                if isinstance(block, dict) and isinstance(block.get("text"), str)
            )
        case _:
            return ""


def _unanswered_calls(pending: Mapping[str, _PendingCall]) -> list[ToolCall]:
    """The commands whose result the transcript does not hold, with no output."""
    return [
        ToolCall(
            session=call.session,
            file=call.file,
            line=call.line,
            timestamp=call.timestamp,
            command=call.command,
            output="",
            is_error=False,
        )
        for call in pending.values()
    ]


def _text(value: Any) -> str:
    """A record field as text, or the empty string when it holds no string."""
    return value if isinstance(value, str) else ""
