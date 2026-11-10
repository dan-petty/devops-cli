"""The test form that a step checks before it ticks a task (#3451).

The step reads the case count that a task names, collects the items of the named test file, and
stops the group when the two counts differ. The model is a pydantic-ai `FunctionModel` from
`ModelScript`. Git runs for real on a checkout in `tmp_path`, and `process_fake` answers every
other program, the pytest collection included.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from devops_cli.roadmap.failure import FailureClass
from devops_cli.roadmap.implement.implement_step import StepOutcome, StepStatus, run_step
from devops_cli.roadmap.implement.implement_trace import ImplementTrace, TraceEventKind
from tests.support.fakes.process import ProcessAnswer, ProcessFake
from tests.support.fakes.roadmap_store import InMemoryRoadmapStore
from tests.support.implement_step import (
    SHOUT_CODE,
    TASKS_PATH,
    WINDOW,
    command_text,
    make_checkout,
    programs_run,
    rounds_spent,
    the_whole_group,
    write_call,
)
from tests.support.model_script import ModelScript, say, tool_calls

pytestmark = pytest.mark.usefixtures("keyring_store")

COLLECT = "uv run pytest --collect-only -q"
COMMAND = f"{COLLECT} -- tests/test_sample.py"
PARAMETRIZED_TASKS = """\
# Tasks

## 1. The first group

- [ ] Add the failing test `tests/test_sample.py` with one parametrized test over six statuses
  - Verification: `$ uv run devops ci test tests/test_sample.py`
- [ ] Add `shout` to `src/sample.py`
  - Verification: `$ uv run devops ci test tests/test_sample.py`
"""
NO_COUNT_TASKS = PARAMETRIZED_TASKS.replace(
    "with one parametrized test over six statuses",
    "with a parametrized test over the statuses",
)
TICKED = PARAMETRIZED_TASKS.replace("- [ ] Add", "- [x] Add")
NO_COUNT_TICKED = NO_COUNT_TASKS.replace("- [ ] Add", "- [x] Add")
PARAMETRIZED_TEST = '''\
import pytest


@pytest.mark.parametrize("status", ["a", "b", "c", "d", "e", "f"])
def test_the_status(status: str) -> None:
    assert status
'''
MISMATCH = (
    "The test tests/test_sample.py collects 11 items, and the task names 6 cases. A parametrized "
    "test collects one item for each case, and a loop over the cases collects one item. Write the "
    "test in the form that the task names."
)
LOOP = (
    "The test tests/test_sample.py collects 1 item, and the task names a parametrized test with no "
    "case count. A parametrized test collects one item for each case, and a loop over the cases "
    "collects one item. Write the test in the form that the task names."
)


@pytest.fixture
def store(implement_store: InMemoryRoadmapStore) -> InMemoryRoadmapStore:
    return implement_store


@pytest.fixture
def programs(implement_programs: ProcessFake) -> ProcessFake:
    return implement_programs


def _collects(items: int) -> ProcessAnswer:
    """A collection that reports `items` items of the named test file."""
    lines = "".join(f"tests/test_sample.py::test_the_status[{number}]\n" for number in range(items))
    return ProcessAnswer(stdout=f"{lines}\n{items} tests collected in 0.01s\n")


def _collects_with(programs: ProcessFake, answer: ProcessAnswer) -> None:
    programs.answer(lambda call: command_text(call).startswith(COLLECT), answer)


def _step(
    store: InMemoryRoadmapStore,
    checkout: Path,
    *,
    tasks: str = TICKED,
    trace: ImplementTrace | None = None,
) -> StepOutcome:
    script = ModelScript(
        tool_calls(
            write_call("tests/test_sample.py", PARAMETRIZED_TEST),
            write_call("src/sample.py", SHOUT_CODE),
            write_call(TASKS_PATH, tasks),
        ),
        say("Done."),
    )
    return run_step(
        store,
        item=1,
        group=1,
        source=checkout,
        model=script.model(),
        window=WINDOW,
        trace=trace,
    )


def test_a_test_that_collects_eleven_items_for_six_named_cases_stops_the_group_with_both_counts(
    store: InMemoryRoadmapStore,
    programs: ProcessFake,
    tmp_path: Path,
) -> None:
    checkout = make_checkout(tmp_path, PARAMETRIZED_TASKS)
    _collects_with(programs, _collects(11))

    outcome = _step(store, checkout)

    assert (outcome.status, outcome.failure_class, outcome.reason) == (
        StepStatus.STOPPED,
        FailureClass.TEST,
        MISMATCH + rounds_spent(3),
    )


def test_the_collection_is_a_check_event_that_names_the_file_and_both_counts(
    store: InMemoryRoadmapStore,
    programs: ProcessFake,
    tmp_path: Path,
) -> None:
    checkout = make_checkout(tmp_path, PARAMETRIZED_TASKS)
    _collects_with(programs, _collects(11))
    trace = ImplementTrace(step="group 1")

    _step(store, checkout, trace=trace)

    checks = [
        event.fields["command"]
        for event in trace.events
        if event.kind is TraceEventKind.CHECK and "collect-only" in event.fields["command"]
    ]
    assert set(checks) == {"pytest --collect-only tests/test_sample.py: 6 cases, 11 items"}


def test_a_test_that_collects_the_six_named_cases_ends_done(
    store: InMemoryRoadmapStore,
    programs: ProcessFake,
    tmp_path: Path,
) -> None:
    checkout = make_checkout(tmp_path, PARAMETRIZED_TASKS)
    _collects_with(programs, _collects(6))

    outcome = _step(store, checkout)

    assert (outcome.status, outcome.failure_class, outcome.reason) == (
        StepStatus.DONE,
        None,
        "",
    )


def test_a_parametrized_task_with_no_count_that_collects_one_item_stops_the_group(
    store: InMemoryRoadmapStore,
    programs: ProcessFake,
    tmp_path: Path,
) -> None:
    checkout = make_checkout(tmp_path, NO_COUNT_TASKS)
    _collects_with(programs, _collects(1))

    outcome = _step(store, checkout, tasks=NO_COUNT_TICKED)

    assert (outcome.status, outcome.failure_class, outcome.reason) == (
        StepStatus.STOPPED,
        FailureClass.TEST,
        LOOP + rounds_spent(3),
    )


def test_a_collection_that_fails_stops_the_group_with_the_class_test(
    store: InMemoryRoadmapStore,
    programs: ProcessFake,
    tmp_path: Path,
) -> None:
    checkout = make_checkout(tmp_path, PARAMETRIZED_TASKS)
    error = "ERROR: not found: tests/test_sample.py"
    _collects_with(programs, ProcessAnswer(returncode=2, stderr=f"{error}\n"))

    outcome = _step(store, checkout)

    assert (outcome.status, outcome.failure_class, outcome.reason) == (
        StepStatus.STOPPED,
        FailureClass.TEST,
        f"{COMMAND} exited with status 2.\n{error}" + rounds_spent(3),
    )


def test_a_collection_that_runs_out_of_time_stops_the_group_with_the_class_timeout(
    store: InMemoryRoadmapStore,
    programs: ProcessFake,
    tmp_path: Path,
) -> None:
    checkout = make_checkout(tmp_path, PARAMETRIZED_TASKS)
    _collects_with(programs, ProcessAnswer(side_effect=subprocess.TimeoutExpired("uv", 1)))

    outcome = _step(store, checkout)

    assert (outcome.status, outcome.failure_class) == (StepStatus.STOPPED, FailureClass.TIMEOUT)
    assert outcome.reason.startswith(f"{COMMAND} ran out of time after ")


def test_a_group_that_names_no_parametrized_test_runs_no_collection(
    store: InMemoryRoadmapStore,
    programs: ProcessFake,
    tmp_path: Path,
) -> None:
    checkout = make_checkout(tmp_path)
    script = ModelScript(tool_calls(*the_whole_group()), say("Done."))

    outcome = run_step(
        store, item=1, group=1, source=checkout, model=script.model(), window=WINDOW
    )

    assert (outcome.status, programs_run(programs, "uv")) == (
        StepStatus.DONE,
        [
            "uv run devops ci test tests/test_sample.py",
            "uv run devops ci test tests/test_sample.py",
            "uv run devops docs check",
            "uv run ruff format -- src/sample.py tests/test_sample.py",
            "uv run devops ci test tests/test_sample.py",
            "uv run devops docs check",
            "uv run ruff check -- src/sample.py tests/test_sample.py",
            "uv run mypy --python-version 3.14 --strict -- src/sample.py",
        ],
    )
