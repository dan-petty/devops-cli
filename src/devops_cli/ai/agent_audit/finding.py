"""Count the recurring problems of the agent sessions from their signatures (#2346).

One finding is one signature across every session that the audit read: the number of sessions that
met it, the number of its recurrences, the time over which it returned, and one pointer for each
session. A signature that three sessions met is one problem with a count of 3, not three problems,
which is what makes a recurring problem visible.

The elapsed time of a finding is the span between its first and its last occurrence. A transcript
names the time of each call, so the span is the time over which the problem returned, which ranks a
problem that stayed for weeks above one that a single session met.

A signature reaches the report, the stored counts and the model, so each one passes through
`sanitize_text` here: a secret, a private host name and an email address never leave this module
(#2346, AGENTS.md rule 10).
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from devops_cli.ai.agent_audit.signature import call_signature
from devops_cli.ai.agent_audit.transcript import ToolCall, sanitize_text


@dataclass(frozen=True, slots=True)
class Pointer:
    """One place that a finding occurs: its session, its transcript file and its line."""

    session: str
    file: Path
    line: int


@dataclass(frozen=True, slots=True)
class Finding:
    """One recurring problem: its signature, its counts, its span and its pointers.

    `tracked` marks a finding that an open issue names, and `group` names the group that the model
    gave it, so the report renders each of them apart from the new problems.
    """

    signature: str
    sessions: int
    recurrences: int
    elapsed_seconds: float
    pointers: tuple[Pointer, ...]
    tracked: bool = False
    group: str | None = None


@dataclass(slots=True)
class _Counts:
    """The counts of one signature while the records are read."""

    recurrences: int = 0
    first: datetime | None = None
    last: datetime | None = None
    pointers: dict[str, Pointer] = field(default_factory=dict)

    def add(self, call: ToolCall) -> None:
        """Count one occurrence of the signature of this accumulator."""
        self.recurrences += 1
        self.pointers.setdefault(
            call.session, Pointer(session=call.session, file=call.file, line=call.line)
        )
        at = _timestamp(call.timestamp)
        if at is not None:
            self.first = at if self.first is None or at < self.first else self.first
            self.last = at if self.last is None or at > self.last else self.last

    def finding(self, signature: str) -> Finding:
        """The finding of the counts that this accumulator holds."""
        elapsed = 0.0
        if self.first is not None and self.last is not None:
            elapsed = (self.last - self.first).total_seconds()
        return Finding(
            signature=signature,
            sessions=len(self.pointers),
            recurrences=self.recurrences,
            elapsed_seconds=elapsed,
            pointers=tuple(self.pointers.values()),
        )


def build_findings(records: Iterable[ToolCall]) -> tuple[Finding, ...]:
    """One finding for each signature of `records`, in the order that the audit met it."""
    counts: dict[str, _Counts] = {}
    for call in records:
        signature = sanitize_text(call_signature(call))
        counts.setdefault(signature, _Counts()).add(call)
    return tuple(each.finding(signature) for signature, each in counts.items())


def rank_findings(findings: Iterable[Finding]) -> tuple[Finding, ...]:
    """The findings in the order of the report: most sessions, then recurrences, then time spent.

    The signature breaks a tie, so two runs over the same records give the same order.
    """
    return tuple(
        sorted(
            findings,
            key=lambda each: (
                -each.sessions,
                -each.recurrences,
                -each.elapsed_seconds,
                each.signature,
            ),
        )
    )


def _timestamp(text: str) -> datetime | None:
    """The time that a record names, or None when it names none."""
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=UTC)


__all__ = ["Finding", "Pointer", "build_findings", "rank_findings"]
