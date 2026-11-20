"""The state of a stop of an item (#3648): its step, the class of its failure, the attempts of that
step and the action that is left.

`devops roadmap explain` and `devops roadmap inbox` read the state from the job record of the item
that they read already, so the state costs no GitHub request. `stop_state_of` takes an `Item` and
reads no client and no network. The attempts are the `attempt` events of `implement.trace` whose
step is the recorded `implement.stopped`, so the record needs no second count key. The class and
the action left print as the record holds them, with no lookup of a table, so a value that a hand
edit or an earlier runner image wrote still prints. A trace that cannot be read counts no attempt,
so a corrupt value of one item stops neither report.
"""

from __future__ import annotations

from dataclasses import dataclass

from devops_cli.roadmap.implement.implement_trace import (
    TraceDecodeError,
    TraceEventKind,
    decode,
)
from devops_cli.roadmap.stores.store import ImplementRecordKey, Item

__all__ = ["StopState", "stop_state_of"]


@dataclass(frozen=True)
class StopState:
    """The state of a stop of an item: the step that stopped it, the class of its failure, the
    count of the attempts of that step, and the action that is left. A class and an action that
    the record does not hold are empty, and a count that the record does not hold is zero."""

    step: str
    failure_class: str = ""
    attempts: int = 0
    action_left: str = ""


def stop_state_of(item: Item) -> StopState | None:
    """The state of the stop in the job record of `item`, or None when the record holds no
    `implement.stopped`."""
    record = item.job_record
    step = record.get(ImplementRecordKey.STOPPED)
    if not step:
        return None
    return StopState(
        step=step,
        failure_class=record.get(ImplementRecordKey.FAILURE) or "",
        attempts=_attempts(record.get(ImplementRecordKey.TRACE), step),
        action_left=record.get(ImplementRecordKey.LEFT_ACTION) or "",
    )


def _attempts(text: str | None, step: str) -> int:
    """The count of the `attempt` events of `step` in the trace `text`. A record that holds no
    trace, or a value that is no trace, counts none."""
    if not text:
        return 0
    try:
        trace = decode(text)
    except TraceDecodeError:
        return 0
    return sum(
        1 for event in trace.events if event.kind is TraceEventKind.ATTEMPT and event.step == step
    )
