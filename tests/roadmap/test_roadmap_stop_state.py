"""The state of a stop of an item (#3648): the step, the class, the attempts and the action left,
read from the job record alone.

The module that reads the state is imported in each case, so the file collects on a tree that has
no such module and each case fails in its call phase there (#3648)."""

from __future__ import annotations

from devops_cli.roadmap.implement.implement_trace import ImplementTrace
from devops_cli.roadmap.stores.store import ImplementRecordKey, Item


def _item(record: dict[str, str]) -> Item:
    return Item(
        number=7,
        title="fix(roadmap): a step stops",
        url="https://github.com/example/repo/issues/7",
        job_record=record,
    )


def _stop_record() -> dict[str, str]:
    """The job record of a stopped item: the step, the class and the action that is left."""
    return {
        ImplementRecordKey.STOPPED: "group 2",
        ImplementRecordKey.FAILURE: "check_failed",
        ImplementRecordKey.LEFT_ACTION: "wait",
    }


def _attempts_trace(count: int) -> str:
    """The trace of a run that stopped in `group 2`, with `count` attempt events of that step."""
    trace = ImplementTrace(step="group 2")
    for number in range(1, count + 1):
        failed = number < count
        trace.attempt(
            number,
            "standard",
            "check_failed" if failed else "",
            "ruff check . exited 1" if failed else "",
            repair=failed,
        )
    return trace.encode()


def test_stop_state_reads_the_class_the_attempts_and_the_action_left() -> None:
    from devops_cli.roadmap.stop_state import StopState, stop_state_of

    item = _item({**_stop_record(), ImplementRecordKey.TRACE: _attempts_trace(2)})

    state = stop_state_of(item)

    assert state == StopState(
        step="group 2",
        failure_class="check_failed",
        attempts=2,
        action_left="wait",
    )


def test_a_record_with_no_stop_gives_no_state() -> None:
    from devops_cli.roadmap.stop_state import stop_state_of

    assert stop_state_of(_item({ImplementRecordKey.FAILURE: "check_failed"})) is None


def test_a_record_with_no_class_and_no_action_left_states_both() -> None:
    from devops_cli.roadmap.stop_state import StopState, stop_state_of

    item = _item({ImplementRecordKey.STOPPED: "group 2"})

    state = stop_state_of(item)

    assert state == StopState(step="group 2")


def test_a_trace_that_is_not_a_trace_counts_no_attempt() -> None:
    from devops_cli.roadmap.stop_state import stop_state_of

    item = _item({**_stop_record(), ImplementRecordKey.TRACE: "not json"})

    state = stop_state_of(item)

    assert state is not None
    assert state.attempts == 0
    assert state.failure_class == "check_failed"
