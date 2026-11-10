"""The trace of one run of the implement job (#3032).

A Job that stops discards its checkout, and its log holds one line for each tool call. The trace
is the structured account that stays in the job record: one event for each model call, tool call,
exit check, retry and attempt, in order. `devops roadmap explain <issue> --trace` prints it, and the
comments of the job sum it up as a table.

The events are in the order of the run: the step adds a model event when the reply comes, so the
tool calls and the checks of a turn stand between the replies that asked for them (#4393). An event
holds no argument and no output. A tool call shows as the digest of its masked argument, so a
reader still sees that the model made the same call twice, and no path or secret reaches an issue
body. A shell call also holds the exit status of its command, when the shell reports one. Every
text of an event goes through `bounded_text` and `mask_private_hosts` and is escaped to one line.
The encoded trace is JSON with the events and the count `dropped`. It holds at most
`CONST_ROADMAP_IMPLEMENT_TRACE_CHARS` characters. The oldest model events go first, as they are
many and show no progress, then the oldest of the other events, as a run fails at its end. The
tool, check, retry and attempt events show what the run did, and the spend of the job record keeps
the tokens of the run (#4393).
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from pydantic_ai.messages import ToolCallPart

from devops_cli.config.constants import (
    CONST_ROADMAP_IMPLEMENT_LOG_COMMAND_CHARS,
    CONST_ROADMAP_IMPLEMENT_LOG_REASON_CHARS,
    CONST_ROADMAP_IMPLEMENT_TABLE_ROWS,
    CONST_ROADMAP_IMPLEMENT_TRACE_CHARS,
)
from devops_cli.lang import MESSAGES
from devops_cli.roadmap.agent_run import argument_json, bounded_text
from devops_cli.security.sanitizer import mask_private_hosts

__all__ = [
    "ImplementTrace",
    "SummaryRow",
    "TraceDecodeError",
    "TraceEvent",
    "TraceEventKind",
    "argument_digest",
    "decode",
    "last_failing_command",
    "summary_table",
]

_DIGEST_CHARS = 12


class TraceEventKind(StrEnum):
    """The five kinds of event of a trace."""

    MODEL = "model"
    TOOL = "tool"
    CHECK = "check"
    RETRY = "retry"
    ATTEMPT = "attempt"


class TraceDecodeError(ValueError):
    """The text is not the JSON of a trace."""


@dataclass(frozen=True)
class TraceEvent:
    """One event: its kind, the step that made it, and the fields of its kind. A field holds
    text, a number, a flag or nothing."""

    kind: TraceEventKind
    step: str
    fields: dict[str, Any] = field(default_factory=dict[str, Any])

    def as_dict(self) -> dict[str, Any]:
        """The event as the dict that `encode` writes."""
        return {"kind": str(self.kind), "step": self.step, **self.fields}


def argument_digest(call: ToolCallPart) -> str:
    """The first 12 hexadecimal characters of the SHA-256 of the masked argument of `call`. A
    secret-named value never enters it, as `argument_json` hides it first."""
    return hashlib.sha256(argument_json(call).encode()).hexdigest()[:_DIGEST_CHARS]


def _line(text: str, limit: int) -> str:
    """`text` masked, with private hosts hidden, escaped to one line and cut to `limit`."""
    masked = mask_private_hosts(bounded_text(text))
    return masked.encode("unicode_escape").decode("ascii")[:limit]


def _compact(value: object) -> str:
    return json.dumps(value, separators=(",", ":"), ensure_ascii=True)


@dataclass
class ImplementTrace:
    """The events of one run, in order. `step` labels the events that follow it. `dropped` counts
    the events that an earlier `encode` took out, so a trace that is read back and extended keeps
    its count."""

    step: str = ""
    events: list[TraceEvent] = field(default_factory=list[TraceEvent])
    dropped: int = 0

    def _add(self, kind: TraceEventKind, **fields: Any) -> None:
        self.events.append(TraceEvent(kind, _line(self.step, 64), fields))

    def model_call(self, model: str, tokens_in: int, tokens_out: int, seconds: float) -> None:
        """One model reply: the model, the tokens in and out, and the seconds of the call."""
        self._add(
            TraceEventKind.MODEL,
            model=_line(model, 80),
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            seconds=round(seconds, 1),
        )

    def tool_call(
        self,
        tool: str,
        program: str,
        digest: str,
        outcome: str,
        reason: str = "",
        status: int | None = None,
    ) -> None:
        """One tool call: the tool, the program of its command, the digest of its argument and
        its outcome. A retry holds the reason that the Job log shows. A shell call holds the exit
        status of its command in `status`, and none when the shell reported none."""
        fields: dict[str, Any] = {
            "tool": _line(tool, 64),
            "program": _line(program, 64),
            "digest": digest,
            "outcome": outcome,
        }
        if reason:
            fields["reason"] = _line(reason, CONST_ROADMAP_IMPLEMENT_LOG_REASON_CHARS)
        if status is not None:
            fields["status"] = status
        self._add(TraceEventKind.TOOL, **fields)

    def check(self, command: str, status: int | None) -> None:
        """One command run as an exit check. `status` is none when the command timed out."""
        fields: dict[str, Any] = {
            "command": _line(command, CONST_ROADMAP_IMPLEMENT_LOG_COMMAND_CHARS)
        }
        if status is None:
            fields["timeout"] = True
        else:
            fields["status"] = status
        self._add(TraceEventKind.CHECK, **fields)

    def retry(self, reason: str) -> None:
        """One repair round or one send again of a model request, with its reason."""
        self._add(
            TraceEventKind.RETRY, reason=_line(reason, CONST_ROADMAP_IMPLEMENT_LOG_REASON_CHARS)
        )

    def attempt(
        self,
        number: int,
        tier: str,
        failure_class: str,
        evidence: str,
        *,
        repair: bool,
    ) -> None:
        """One attempt of a step (#3053): the first run or a repair round. A passed attempt has
        no class and no evidence. `repair` says whether a repair round follows."""
        fields: dict[str, Any] = {
            "number": number,
            "tier": _line(tier, 80),
            "outcome": "failed" if failure_class else "passed",
            "next": "repair" if repair else "stop",
        }
        if failure_class:
            fields["class"] = _line(failure_class, 32)
            fields["evidence"] = _line(evidence, CONST_ROADMAP_IMPLEMENT_LOG_REASON_CHARS)
        self._add(TraceEventKind.ATTEMPT, **fields)

    def encode(self) -> str:
        """The trace as JSON, `{"events": [...], "dropped": n}`, not longer than
        `CONST_ROADMAP_IMPLEMENT_TRACE_CHARS` characters. The oldest model events go first, then
        the oldest of the other events (#4393). The kept events stay in the order of the run, and
        the others are added to `dropped`."""
        pieces = [_compact(event.as_dict()) for event in self.events]
        total = sum(len(piece) + 1 for piece in pieces)
        first = sorted(
            range(len(pieces)),
            key=lambda index: self.events[index].kind is not TraceEventKind.MODEL,
        )
        gone: set[int] = set()
        for index in first:
            if total + self._frame(len(gone)) <= CONST_ROADMAP_IMPLEMENT_TRACE_CHARS:
                break
            total -= len(pieces[index]) + 1
            gone.add(index)
        kept = ",".join(piece for index, piece in enumerate(pieces) if index not in gone)
        return f'{{"events":[{kept}],"dropped":{self.dropped + len(gone)}}}'

    def _frame(self, gone: int) -> int:
        """The characters of the JSON around the events when `gone` events are dropped."""
        return len(f'{{"events":[],"dropped":{self.dropped + gone}}}')


def decode(text: str) -> ImplementTrace:
    """The trace that `encode` wrote. Raises `TraceDecodeError` for text that is not JSON or not
    a list of events."""
    try:
        data = json.loads(text)
    except ValueError as error:
        raise TraceDecodeError(str(error)) from error
    if not isinstance(data, dict) or not isinstance(data.get("events"), list):
        raise TraceDecodeError("no list of events")
    dropped = data.get("dropped", 0)
    if not isinstance(dropped, int) or isinstance(dropped, bool):
        raise TraceDecodeError("dropped is not a number")
    events: list[TraceEvent] = []
    for raw in data["events"]:
        if not isinstance(raw, dict) or not isinstance(raw.get("step"), str):
            raise TraceDecodeError("an event is not an object with a step")
        try:
            kind = TraceEventKind(str(raw.get("kind")))
        except ValueError as error:
            raise TraceDecodeError(f"unknown kind {raw.get('kind')!r}") from error
        fields = {key: value for key, value in raw.items() if key not in ("kind", "step")}
        events.append(TraceEvent(kind, raw["step"], fields))
    return ImplementTrace(events=events, dropped=dropped)


@dataclass(frozen=True)
class SummaryRow:
    """One row of the table of the steps: the step, its status, its attempts (the first turn and
    the repair rounds), its tokens in and out, and its last failing command, or empty."""

    step: str
    status: str
    attempts: int
    tokens_in: int
    tokens_out: int
    command: str = ""


def last_failing_command(events: Sequence[TraceEvent], step: str, fallback: str = "") -> str:
    """The command of the last `check` event of `step` that did not exit 0 (a timeout has no exit
    status and did not exit 0 either), else `fallback`: the name of the failed check of the pull
    request, which has no command."""
    for event in reversed(events):
        if event.kind is TraceEventKind.CHECK and event.step == step:
            if event.fields.get("status") != 0:
                return str(event.fields["command"])
    return fallback


def _cell(text: str, limit: int) -> str:
    """`text` on one line, cut to `limit` characters, with the pipe escaped for a table cell."""
    one = " ".join(text.split())
    cut = one[:limit] + (MESSAGES.roadmap.implement_tool_cut if len(one) > limit else "")
    return cut.replace("|", "\\|")


def summary_table(rows: Iterable[SummaryRow]) -> str:
    """The table of the steps for a comment of the job (#3032): the header and one line for each
    row, at most `CONST_ROADMAP_IMPLEMENT_TABLE_ROWS` of them, the newest. Empty when there is no
    row. The command shows as code in its cell, cut to `CONST_ROADMAP_IMPLEMENT_LOG_COMMAND_CHARS`."""
    kept = list(rows)[-CONST_ROADMAP_IMPLEMENT_TABLE_ROWS:]
    if not kept:
        return ""
    texts = MESSAGES.roadmap
    lines = [texts.implement_table_header]
    for row in kept:
        command = row.command.replace("`", "'")
        lines.append(
            texts.implement_table_row.format(
                step=_cell(row.step, 64),
                status=_cell(row.status, 32),
                attempts=row.attempts,
                tokens_in=row.tokens_in,
                tokens_out=row.tokens_out,
                command=(
                    f"`{_cell(command, CONST_ROADMAP_IMPLEMENT_LOG_COMMAND_CHARS)}`"
                    if command
                    else texts.implement_table_no_command
                ),
            )
        )
    return "\n".join(lines)
