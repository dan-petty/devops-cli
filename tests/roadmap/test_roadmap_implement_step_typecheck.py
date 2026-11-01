"""The type check of a step is the type check of the gate (#3090): `mypy` runs on the changed files
under the paths of `devops ci typecheck`, with its options, and never on a test file.

The model is a pydantic-ai `FunctionModel` from `ModelScript`. Git runs for real on a checkout in
`tmp_path`. `mypy` reads the files of the checkout through `process_fake`, so a file that holds
`BAD_TYPE` fails the type check, as a test file with old errors does.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from devops_cli.ci.typecheck import TYPECHECK_PATHS
from devops_cli.commands.ci import get_check_spec
from devops_cli.roadmap.implement_step import StepOutcome, StepStatus, run_step
from devops_cli.roadmap.memory_store import InMemoryRoadmapStore
from tests.support.fakes.process import ProcessAnswer, ProcessFake
from tests.support.implement_step import (
    SHOUT_CODE,
    TASKS_PATH,
    TEST_BODY,
    TICKED,
    WINDOW,
    command_text,
    git,
    is_clean_at,
    programs_run,
    tool_reads,
    write_call,
)
from tests.support.model_script import ModelScript, say, tool_calls

pytestmark = pytest.mark.usefixtures("keyring_store")

OLD_ERRORS = TEST_BODY + "\nBAD_TYPE = 1\n"
NEW_ERROR = SHOUT_CODE + "\nBAD_TYPE = 1\n"
BAD_TYPE = "src/sample.py:9: error: bad type"
GATE = "uv run mypy --python-version 3.14 --strict"
TICK = write_call(TASKS_PATH, TICKED)
OLD_TEST = write_call("tests/test_sample.py", OLD_ERRORS)


@pytest.fixture
def store(implement_store: InMemoryRoadmapStore) -> InMemoryRoadmapStore:
    return implement_store


@pytest.fixture
def checkout(implement_checkout: Path) -> Path:
    return implement_checkout


@pytest.fixture
def programs(implement_programs: ProcessFake) -> ProcessFake:
    """The process edge, whose `mypy` fails on any file that holds `BAD_TYPE`."""
    implement_programs.answer(
        lambda call: command_text(call).startswith("uv run mypy"),
        ProcessAnswer(side_effect=tool_reads("BAD_TYPE", BAD_TYPE)),
    )
    return implement_programs


def _step(store: InMemoryRoadmapStore, checkout: Path, script: ModelScript) -> StepOutcome:
    return run_step(store, item=1, group=1, source=checkout, model=script.model(), window=WINDOW)


def test_a_test_file_with_old_type_errors_does_not_stop_the_step(
    store: InMemoryRoadmapStore, checkout: Path, programs: ProcessFake
) -> None:
    script = ModelScript(
        tool_calls(OLD_TEST, write_call("src/sample.py", SHOUT_CODE), TICK), say("Done.")
    )

    outcome = _step(store, checkout, script)

    assert (outcome.status, outcome.reason) == (StepStatus.DONE, "")
    assert [line for line in programs_run(programs, "uv") if " mypy " in line] == [
        f"{GATE} -- src/sample.py"
    ]
    assert git(checkout, "show", "HEAD:tests/test_sample.py") + "\n" == OLD_ERRORS


def test_a_step_that_changes_only_test_files_runs_no_type_check_and_still_lints_them(
    store: InMemoryRoadmapStore, checkout: Path, programs: ProcessFake
) -> None:
    script = ModelScript(tool_calls(OLD_TEST, TICK), say("Done."))

    outcome = _step(store, checkout, script)

    uv = programs_run(programs, "uv")
    assert (outcome.status, outcome.reason) == (StepStatus.DONE, "")
    assert not [line for line in uv if "mypy" in line]
    assert "uv run ruff check -- tests/test_sample.py" in uv


def test_a_new_type_error_in_a_source_file_still_stops_the_step(
    store: InMemoryRoadmapStore, checkout: Path, programs: ProcessFake
) -> None:
    head = git(checkout, "rev-parse", "HEAD")
    work = tool_calls(OLD_TEST, write_call("src/sample.py", NEW_ERROR), TICK)
    script = ModelScript(work, say("Done."), say("I changed nothing."))

    outcome = _step(store, checkout, script)

    assert (outcome.status, outcome.reason, outcome.commit, len(script.seen)) == (
        StepStatus.STOPPED,
        f"{GATE} -- src/sample.py exited with status 1.\n{BAD_TYPE}",
        "",
        3,
    )
    assert is_clean_at(checkout, head)


def test_the_command_of_the_step_is_the_command_of_the_gate_with_the_files_in_place_of_the_paths(
    store: InMemoryRoadmapStore, checkout: Path, programs: ProcessFake
) -> None:
    script = ModelScript(tool_calls(write_call("src/sample.py", SHOUT_CODE), TICK), say("Done."))

    _step(store, checkout, script)

    gate = get_check_spec("typecheck").cmd
    assert gate[-len(TYPECHECK_PATHS) :] == list(TYPECHECK_PATHS)
    typed = [line for line in programs_run(programs, "uv") if " mypy " in line]
    assert typed == [" ".join([*gate[: -len(TYPECHECK_PATHS)], "--", "src/sample.py"])]
