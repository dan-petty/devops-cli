"""The console of a roadmap run (#3076): the trace of the last implement run as the table of the
pull request comment.

The job record of an item holds one trace, which a new run replaces, so the console shows the steps
of the last run and no history of earlier runs. One read of the item gives the trace, the runner Job
and its state, so the command sends one GitHub request. The rows come from the events of the trace,
so the console parses no line of the pod log. Every text of a row goes through `mask_secrets`, as
the log lines of the runner do.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, replace
from typing import Final

from devops_cli.exceptions.roadmap import RoadmapImplementError
from devops_cli.lang import MESSAGES
from devops_cli.roadmap.implement.implement_step import StepStatus
from devops_cli.roadmap.implement.implement_trace import (
    ImplementTrace,
    SummaryRow,
    TraceDecodeError,
    TraceEvent,
    TraceEventKind,
    decode,
    last_failing_command,
    summary_table,
)
from devops_cli.roadmap.stores.store import ImplementRecordKey, Item, JobRecord
from devops_cli.security.sanitizer import mask_secrets

__all__ = [
    "FollowState",
    "follow_command",
    "follow_state",
    "recorded_rows",
    "render_recorded",
]

_PASSED: Final[str] = "passed"


@dataclass(frozen=True)
class FollowState:
    """What one read of an item gives the console: its number, the trace of the last implement run
    (None when the record holds none), the runner Job that runs or ran it, and the state that the
    Service recorded for the Job, which is None while the Job runs."""

    number: int
    trace: ImplementTrace | None = None
    job: str | None = None
    job_state: str | None = None


def follow_state(item: Item, number: int) -> FollowState:
    """The state of the console for `item`, whose number is `number`: the trace, the runner Job and
    the Job state of its job record. Raises `RoadmapImplementError` for a value of
    `implement.trace` that is no trace."""
    record = item.job_record
    return FollowState(
        number=number,
        trace=_trace_of(record, number),
        job=record.get(ImplementRecordKey.JOB),
        job_state=record.get(ImplementRecordKey.JOB_STATE),
    )


def _trace_of(record: JobRecord, number: int) -> ImplementTrace | None:
    """The trace of the job record `record`, or None when it holds none."""
    text = record.get(ImplementRecordKey.TRACE)
    if not text:
        return None
    try:
        return decode(text)
    except TraceDecodeError as error:
        raise RoadmapImplementError(
            MESSAGES.roadmap.explain_trace_unreadable.format(number=number, error=error)
        ) from error


def recorded_rows(trace: ImplementTrace) -> list[SummaryRow]:
    """One row for each step of `trace`, in the order of the run: the status and the attempts of
    its attempt events, the tokens of its model events, and its last failing command."""
    steps: dict[str, list[TraceEvent]] = {}
    for event in trace.events:
        steps.setdefault(event.step, []).append(event)
    return [_row(step, events) for step, events in steps.items()]


def _row(step: str, events: Sequence[TraceEvent]) -> SummaryRow:
    """The row of `step`, from its `events`."""
    attempts = [event for event in events if event.kind is TraceEventKind.ATTEMPT]
    command = last_failing_command(events, step)
    return SummaryRow(
        step=step,
        status=_status(attempts, command),
        attempts=max(1, len(attempts)),
        tokens_in=_tokens(events, "tokens_in"),
        tokens_out=_tokens(events, "tokens_out"),
        command=command,
    )


def _status(attempts: Sequence[TraceEvent], command: str) -> str:
    """How a step ended: its last attempt says whether it passed, and a step with no attempt event
    passed when no check of it failed."""
    passed = attempts[-1].fields.get("outcome") == _PASSED if attempts else not command
    return StepStatus.DONE.value if passed else StepStatus.STOPPED.value


def _tokens(events: Sequence[TraceEvent], key: str) -> int:
    """The sum of `key` over the model events of `events`."""
    values = (event.fields.get(key, 0) for event in events if event.kind is TraceEventKind.MODEL)
    return sum(value for value in values if isinstance(value, int) and not isinstance(value, bool))


def render_recorded(state: FollowState) -> str:
    """The table of the steps of the last run, in the shape of the pull request comment and with
    each text masked. An item with no trace and no runner Job has never run. A Job that has
    recorded no event yet has no table, so the live lines of the command follow it."""
    if state.trace is not None:
        return summary_table(_masked(row) for row in recorded_rows(state.trace))
    if state.job is None:
        return MESSAGES.roadmap.follow_never_run.format(number=state.number)
    return ""


def _masked(row: SummaryRow) -> SummaryRow:
    """`row` with each text masked as a secret, as the runner masks each line of its log."""
    return replace(
        row,
        step=mask_secrets(row.step),
        status=mask_secrets(row.status),
        command=mask_secrets(row.command),
    )


def follow_command(number: int) -> str:
    """The command that follows the run of issue `number`."""
    return MESSAGES.roadmap.follow_command.format(number=number)
