"""Store the daily counts of the recurring problems that the agent audit finds (#2346).

The audit reads the same transcripts in run after run, so a count that grows with each run would
count runs rather than problems. The store keeps one file for each day under the store name
`agent/audit`, and `merge_counts` adds only the session file and the line that the file does not
hold yet: a second run over the same transcript leaves every count as it was, and a run that meets
a signature in a session that the store does not hold yet raises its count.

A stored record holds the signature, its counts and the pointer of each session, and no command
and no output, so no raw line of a transcript reaches the file. Each text passes through
`sanitize_text` before it is written: a secret, a private host name and an email address reach the
file masked (#2346, AGENTS.md rule 10).
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, TypeGuard

from devops_cli.ai.agent_audit.finding import Finding, Pointer
from devops_cli.ai.agent_audit.transcript import sanitize_text
from devops_cli.core.repo import resolve_store_path
from devops_cli.exceptions.validation import ValidationError
from devops_cli.output.file_writer import write_json_file

# The store of the daily counts: one file for each day, named by its ISO date.
_STORE = "agent/audit"
# The key that holds the records of one file.
_SIGNATURES = "signatures"
# A pointer is identified by the session file and the line that it names, which is what a second
# run over the same transcript reads again.
_PointerKey = tuple[str, int]
# The digits of the elapsed seconds that the store keeps.
_ELAPSED_DIGITS = 3


@dataclass(frozen=True, slots=True)
class StoredCounts:
    """The counts that the store of a day holds for one signature."""

    signature: str
    sessions: int
    recurrences: int
    elapsed_seconds: float
    pointers: tuple[Pointer, ...]


@dataclass(slots=True)
class _Entry:
    """The counts of one signature while the store is merged."""

    recurrences: int
    elapsed_seconds: float
    pointers: dict[_PointerKey, Pointer] = field(default_factory=dict)

    def sessions(self) -> int:
        """The number of sessions whose session file and line the entry holds."""
        return len({pointer.session for pointer in self.pointers.values()})

    def counts(self, signature: str) -> StoredCounts:
        """The counts of `signature` that the entry holds."""
        return StoredCounts(
            signature=signature,
            sessions=self.sessions(),
            recurrences=self.recurrences,
            elapsed_seconds=self.elapsed_seconds,
            pointers=tuple(self.pointers[key] for key in sorted(self.pointers)),
        )


def store_path(day: date) -> Path:
    """The file that holds the counts of `day`, under the store name `agent/audit` (#2346)."""
    return resolve_store_path(f"{_STORE}/{day.isoformat()}.json")


def merge_counts(path: Path, findings: Iterable[Finding]) -> tuple[StoredCounts, ...]:
    """Add the occurrences of `findings` that the store at `path` does not hold, and write it (#2346).

    A signature keeps its counts when the store already holds the session file and the line of each
    of its pointers, so a second run over the same transcripts changes nothing. A signature that a
    session, or a line, that the store does not hold met raises its count.
    """
    entries = {counts.signature: _entry_of(counts) for counts in _read(path)}
    for finding in findings:
        signature = sanitize_text(finding.signature)
        entries[signature] = _merged(entries.get(signature), finding)
    merged = tuple(entries[signature].counts(signature) for signature in sorted(entries))
    _write(path, merged)
    return merged


def _entry_of(counts: StoredCounts) -> _Entry:
    """The entry of a record that the store of a day holds."""
    return _Entry(
        recurrences=counts.recurrences,
        elapsed_seconds=counts.elapsed_seconds,
        pointers={_key(pointer): pointer for pointer in counts.pointers},
    )


def _merged(entry: _Entry | None, finding: Finding) -> _Entry:
    """The entry of a finding merged into the one that the store holds, if it holds one."""
    if entry is None:
        return _unseen_entry(finding)
    pointers = dict(entry.pointers)
    unseen = {
        _key(pointer): pointer for pointer in finding.pointers if _key(pointer) not in pointers
    }
    if not unseen:
        return entry
    pointers.update(unseen)
    return _Entry(
        recurrences=entry.recurrences + len(unseen),
        elapsed_seconds=max(entry.elapsed_seconds, finding.elapsed_seconds),
        pointers=pointers,
    )


def _unseen_entry(finding: Finding) -> _Entry:
    """The entry of a finding that the store holds no record of, with the counts that it gives."""
    return _Entry(
        recurrences=finding.recurrences,
        elapsed_seconds=finding.elapsed_seconds,
        pointers={_key(pointer): pointer for pointer in finding.pointers},
    )


def _key(pointer: Pointer) -> _PointerKey:
    """The identity of a pointer: the session file and the line that it names."""
    return (sanitize_text(str(pointer.file)), pointer.line)


def _read(path: Path) -> tuple[StoredCounts, ...]:
    """The counts that the store at `path` holds, or nothing when it holds no file."""
    if not path.is_file():
        return ()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as err:
        raise _malformed(path) from err
    records = payload.get(_SIGNATURES) if isinstance(payload, dict) else None
    if not isinstance(records, list):
        raise _malformed(path)
    return tuple(_stored_counts(record, path) for record in records)


def _stored_counts(record: Any, path: Path) -> StoredCounts:
    """One record of the counts file at `path`, as the store writes it."""
    if not isinstance(record, dict):
        raise _malformed(path)
    signature = record.get("signature")
    sessions = record.get("sessions")
    recurrences = record.get("recurrences")
    elapsed = record.get("elapsed_seconds")
    pointers = record.get("pointers")
    if (
        not isinstance(signature, str)
        or not _is_int(sessions)
        or not _is_int(recurrences)
        or not isinstance(elapsed, (int, float))
        or not isinstance(pointers, list)
    ):
        raise _malformed(path)
    return StoredCounts(
        signature=sanitize_text(signature),
        sessions=sessions,
        recurrences=recurrences,
        elapsed_seconds=float(elapsed),
        pointers=tuple(_stored_pointer(each, path) for each in pointers),
    )


def _stored_pointer(record: Any, path: Path) -> Pointer:
    """The pointer of one record of the counts file at `path`."""
    if not isinstance(record, dict):
        raise _malformed(path)
    session = record.get("session")
    file = record.get("file")
    line = record.get("line")
    if not isinstance(session, str) or not isinstance(file, str) or not _is_int(line):
        raise _malformed(path)
    return Pointer(session=session, file=Path(file), line=line)


def _is_int(value: Any) -> TypeGuard[int]:
    """Whether a stored value is a whole number rather than a flag or a text."""
    return isinstance(value, int) and not isinstance(value, bool)


def _malformed(path: Path) -> ValidationError:
    """The error of a counts file that holds no record that the store wrote."""
    return ValidationError(
        f"Cannot read the stored agent audit counts at {path}. Run the audit on another day, or "
        "remove the file.",
        field="path",
    )


def _write(path: Path, counts: Sequence[StoredCounts]) -> None:
    """Write the counts of the day at `path`, with each text masked."""
    path.parent.mkdir(parents=True, exist_ok=True)
    write_json_file(path, {_SIGNATURES: [_record(each) for each in counts]}, atomic=True)


def _record(counts: StoredCounts) -> dict[str, object]:
    """One record of the counts file, with each text masked and each pointer of a session."""
    return {
        "signature": sanitize_text(counts.signature),
        "sessions": counts.sessions,
        "recurrences": counts.recurrences,
        "elapsed_seconds": round(counts.elapsed_seconds, _ELAPSED_DIGITS),
        "pointers": [_pointer_record(pointer) for pointer in counts.pointers],
    }


def _pointer_record(pointer: Pointer) -> Mapping[str, object]:
    """One pointer of a record, with the session file masked."""
    return {
        "session": sanitize_text(pointer.session),
        "file": sanitize_text(str(pointer.file)),
        "line": pointer.line,
    }


__all__ = ["StoredCounts", "merge_counts", "store_path"]
