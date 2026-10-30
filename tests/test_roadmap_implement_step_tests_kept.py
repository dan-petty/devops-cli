"""A step keeps the tests that existed when it started (#2804): for each test file that the step
changed, every test of the file at the start is still in the checkout, by qualified name. A step
that loses one stops, before the formatter and the verification commands run.

The model is a pydantic-ai `FunctionModel` from `ModelScript`. Git runs for real on a checkout in
`tmp_path`, and every other program is answered by `process_fake`.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

import pytest

from devops_cli.config import constants
from devops_cli.roadmap.implement_step import (
    FixRequest,
    StepOutcome,
    StepStatus,
    run_fix_step,
    run_step,
)
from devops_cli.roadmap.memory_store import InMemoryRoadmapStore
from tests.support.fakes.process import ProcessAnswer, ProcessCall, ProcessFake
from tests.support.implement_step import (
    SHOUT_CODE,
    TASKS_PATH,
    TICKED,
    WINDOW,
    command_text,
    git,
    is_clean_at,
    programs_run,
    write_call,
)
from tests.support.model_script import ModelScript, say, tool_calls

pytestmark = pytest.mark.usefixtures("keyring_store")

OLD = '''\
"""The tests that exist."""


def test_a() -> None: ...


async def test_b() -> None: ...


class TestKept:
    def test_c(self) -> None: ...
'''
OLD_PATH = "tests/test_old.py"
SOURCE = write_call("src/sample.py", SHOUT_CODE)
TICK = write_call(TASKS_PATH, TICKED)
REASON = (
    "The agent removed tests that existed at the start of the step. A step may add tests. "
    "It may not remove or rename one.\n"
)
SYNTAX_ERROR = "def test_a(:\n"


@pytest.fixture
def store(implement_store: InMemoryRoadmapStore) -> InMemoryRoadmapStore:
    return implement_store


@pytest.fixture
def checkout(implement_checkout: Path) -> Path:
    """The sample checkout with one more commit: the test file `tests/test_old.py`."""
    (implement_checkout / OLD_PATH).write_text(OLD, encoding="utf-8")
    git(implement_checkout, "add", "-A")
    git(implement_checkout, "commit", "-q", "-m", "add the old tests")
    return implement_checkout


@pytest.fixture
def programs(implement_programs: ProcessFake) -> ProcessFake:
    return implement_programs


def _run(store: InMemoryRoadmapStore, checkout: Path, script: ModelScript) -> StepOutcome:
    return run_step(store, item=1, group=1, source=checkout, model=script.model(), window=WINDOW)


def _script(*work: tuple[str, dict[str, Any]], removes: Path | None = None) -> ModelScript:
    """The agent writes the files of `work` and ticks the tasks. When it also removes a file, the
    removal is scripted as an effect: the agent's shell is a process edge that a test fakes."""
    effects = {2: removes.unlink} if removes else None
    return ModelScript(tool_calls(*work, TICK), say("Done."), effects=effects)


def _lint_fails_on(word: str, programs: ProcessFake) -> None:
    def answer(call: ProcessCall) -> subprocess.CompletedProcess[str]:
        assert call.cwd is not None
        names = call.argv[call.argv.index("--") + 1 :]
        failed = any(word in (call.cwd / name).read_text(encoding="utf-8") for name in names)
        return subprocess.CompletedProcess(
            call.argv, 1 if failed else 0, stdout=f"{word}: bad\n" if failed else "", stderr=""
        )

    programs.answer(
        lambda call: command_text(call).startswith("uv run ruff check"),
        ProcessAnswer(side_effect=answer),
    )


def test_a_step_that_replaces_a_test_file_and_drops_tests_stops_and_names_them(
    store: InMemoryRoadmapStore, checkout: Path, programs: ProcessFake
) -> None:
    head = git(checkout, "rev-parse", "HEAD")
    script = _script(write_call(OLD_PATH, "def test_new() -> None: ...\n"), SOURCE)

    outcome = _run(store, checkout, script)

    assert (outcome.status, outcome.reason, outcome.commit) == (
        StepStatus.STOPPED,
        f"{REASON}{OLD_PATH}: TestKept.test_c, test_a, test_b",
        "",
    )
    assert is_clean_at(checkout, head)


def test_the_check_runs_before_the_formatter_and_the_verification_commands(
    store: InMemoryRoadmapStore, checkout: Path, programs: ProcessFake
) -> None:
    script = _script(write_call(OLD_PATH, "def test_new() -> None: ...\n"), SOURCE)

    outcome = _run(store, checkout, script)

    assert outcome.status is StepStatus.STOPPED
    assert programs_run(programs, "uv") == []
    assert len(script.seen) == 2


def test_a_step_that_adds_a_test_to_an_existing_file_ends_done(
    store: InMemoryRoadmapStore, checkout: Path, programs: ProcessFake
) -> None:
    script = _script(write_call(OLD_PATH, OLD + "\n\ndef test_added() -> None: ...\n"), SOURCE)

    outcome = _run(store, checkout, script)

    assert (outcome.status, outcome.reason) == (StepStatus.DONE, "")
    assert "test_added" in git(checkout, "show", f"HEAD:{OLD_PATH}")


def test_a_step_that_renames_a_test_stops(
    store: InMemoryRoadmapStore, checkout: Path, programs: ProcessFake
) -> None:
    script = _script(write_call(OLD_PATH, OLD.replace("def test_a(", "def test_z(")), SOURCE)

    outcome = _run(store, checkout, script)

    assert (outcome.status, outcome.reason) == (StepStatus.STOPPED, f"{REASON}{OLD_PATH}: test_a")


def test_a_step_that_deletes_a_test_file_stops(
    store: InMemoryRoadmapStore, checkout: Path, programs: ProcessFake
) -> None:
    script = _script(SOURCE, removes=checkout / OLD_PATH)

    outcome = _run(store, checkout, script)

    assert (outcome.status, outcome.reason) == (
        StepStatus.STOPPED,
        f"{REASON}{OLD_PATH}: TestKept.test_c, test_a, test_b",
    )


def test_a_step_that_moves_the_tests_to_a_new_file_ends_done(
    store: InMemoryRoadmapStore, checkout: Path, programs: ProcessFake
) -> None:
    moved = "tests/test_moved.py"
    script = _script(write_call(moved, OLD), SOURCE, removes=checkout / OLD_PATH)

    outcome = _run(store, checkout, script)

    assert (outcome.status, outcome.reason) == (StepStatus.DONE, "")
    assert git(checkout, "show", f"HEAD:{moved}") + "\n" == OLD


def test_a_step_that_moves_only_some_of_the_tests_stops_with_the_rest(
    store: InMemoryRoadmapStore, checkout: Path, programs: ProcessFake
) -> None:
    script = _script(
        write_call("tests/test_moved.py", "def test_a() -> None: ...\n"),
        SOURCE,
        removes=checkout / OLD_PATH,
    )

    outcome = _run(store, checkout, script)

    assert (outcome.status, outcome.reason) == (
        StepStatus.STOPPED,
        f"{REASON}{OLD_PATH}: TestKept.test_c, test_b",
    )


def test_a_test_file_that_did_not_parse_at_the_start_does_not_crash_the_check(
    store: InMemoryRoadmapStore, checkout: Path, programs: ProcessFake
) -> None:
    (checkout / OLD_PATH).write_text(SYNTAX_ERROR, encoding="utf-8")
    git(checkout, "commit", "-q", "-am", "break the old tests")
    script = _script(write_call(OLD_PATH, OLD), SOURCE)

    outcome = _run(store, checkout, script)

    assert (outcome.status, outcome.reason) == (StepStatus.DONE, "")


def test_a_test_file_that_does_not_parse_after_the_run_is_judged_by_the_static_check_alone(
    store: InMemoryRoadmapStore, checkout: Path, programs: ProcessFake
) -> None:
    _lint_fails_on("def test_a(:", programs)
    script = ModelScript(
        tool_calls(write_call(OLD_PATH, SYNTAX_ERROR), SOURCE, TICK), say("Done."), say("No fix.")
    )

    outcome = _run(store, checkout, script)

    assert (outcome.status, outcome.reason) == (
        StepStatus.STOPPED,
        f"uv run ruff check -- src/sample.py {OLD_PATH} exited with status 1.\ndef test_a(:: bad",
    )


def test_the_reason_names_a_bounded_number_of_tests(
    store: InMemoryRoadmapStore, checkout: Path, programs: ProcessFake
) -> None:
    count = constants.CONST_ROADMAP_IMPLEMENT_REASON_TESTS + 2
    many = "".join(f"def test_{n:02d}() -> None: ...\n" for n in range(count))
    (checkout / OLD_PATH).write_text(many, encoding="utf-8")
    git(checkout, "commit", "-q", "-am", "many tests")
    script = _script(write_call(OLD_PATH, "def test_new() -> None: ...\n"), SOURCE)

    outcome = _run(store, checkout, script)

    names = ", ".join(
        f"test_{n:02d}" for n in range(constants.CONST_ROADMAP_IMPLEMENT_REASON_TESTS)
    )
    assert outcome.reason == f"{REASON}{OLD_PATH}: {names} and 2 more"


def test_a_fix_step_keeps_the_tests_as_well(
    store: InMemoryRoadmapStore, checkout: Path, programs: ProcessFake
) -> None:
    script = ModelScript(
        tool_calls(SOURCE), say("Done."), effects={2: (checkout / OLD_PATH).unlink}
    )

    outcome = run_fix_step(
        store,
        item=1,
        fix=FixRequest(check="Static Analysis", log="E501"),
        source=checkout,
        model=script.model(),
        window=WINDOW,
    )

    assert (outcome.status, outcome.commit) == (StepStatus.STOPPED, "")
    assert outcome.reason.startswith(REASON)


def test_the_extra_turn_for_a_static_failure_cannot_remove_a_test(
    store: InMemoryRoadmapStore, checkout: Path, programs: ProcessFake
) -> None:
    _lint_fails_on("import os", programs)
    added = OLD + "\n\ndef test_added() -> None: ...\n"
    script = ModelScript(
        tool_calls(write_call(OLD_PATH, "import os\n" + added), SOURCE, TICK),
        say("Done."),
        tool_calls(write_call(OLD_PATH, "def test_added() -> None: ...\n")),
        say("Fixed."),
    )

    outcome = _run(store, checkout, script)

    assert (outcome.status, outcome.reason) == (
        StepStatus.STOPPED,
        f"{REASON}{OLD_PATH}: TestKept.test_c, test_a, test_b",
    )
