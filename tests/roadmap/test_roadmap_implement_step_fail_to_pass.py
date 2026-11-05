"""A behavior group proves its tests on the base commit of the group (#3042).

The step replays the test files of a behavior group on its base commit, with the head's tests
overlaid, and accepts the group only when one of its tests fails in its call phase there. A test
that passes on the base, or that cannot be collected there, is refused, and one repair round may
change only the test files. A group of kind `other` keeps the output of its verify commands.

Git runs for real on a checkout in `tmp_path`, and every other program is answered by
`process_fake`. The replay runs pytest, which is an edge, so the test answers it with the JUnit
report that the test gives.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from devops_cli.config.defaults import DEFAULT_ROADMAP_IMPLEMENT_REPAIR_ROUNDS
from devops_cli.roadmap.implement_step import StepOutcome, StepStatus, run_step
from devops_cli.roadmap.memory_store import InMemoryRoadmapStore
from tests.support.base_replay import answer_pytest_on_base, junit
from tests.support.fakes.process import ProcessAnswer, ProcessCall, ProcessFake
from tests.support.implement_step import (
    SHOUT_CODE,
    TASKS_PATH,
    WINDOW,
    git,
    make_checkout,
    rounds_spent,
    the_whole_group,
    write_call,
)
from tests.support.model_script import ModelScript, say, tool_calls

pytestmark = pytest.mark.usefixtures("keyring_store")

BEHAVIOR = """\
# Tasks

## 1. The first group

- [ ] Add the failing test `tests/test_sample.py` for `src/sample.py`
  - Verification: `uv run devops ci test tests/test_sample.py` fails on the base
- [ ] Add `shout` to `src/sample.py`
  - Verification: `uv run devops ci test tests/test_sample.py`
"""
TICKED_BEHAVIOR = BEHAVIOR.replace("- [ ] Add", "- [x] Add")
TEST_PATH = "tests/test_sample.py"
TEST_BODY = "def test_shout() -> None:\n    assert True\n"
FIXED_BODY = "def test_shout() -> None:\n    assert shout('a') == 'A!'\n"
TEST_ID = "tests.test_sample::test_shout"
WORK = (
    write_call(TEST_PATH, TEST_BODY),
    write_call("src/sample.py", SHOUT_CODE),
    write_call(TASKS_PATH, TICKED_BEHAVIOR),
)
PASSES_REASON = (
    "No test of the group fails on the base commit. The tests of tests/test_sample.py pass there, "
    "so they prove nothing. Write a test that fails on the base commit first."
)
COLLECTION_REASON = (
    "The tests of tests/test_sample.py cannot be collected on the base commit, so no test fails "
    "there. Import the new code inside the test function, so that the test fails on an assertion."
)
NO_TEST_REASON = (
    "A behavior group changed no test file. Write the failing test first, in a file under tests/."
)


def _replay(outcome: StepOutcome) -> tuple[str, tuple[str, ...]]:
    """The status of the replay on base, and the tests that failed there."""
    replay = outcome.fail_to_pass
    assert replay is not None
    return replay.status, replay.failed


@pytest.fixture
def store(implement_store: InMemoryRoadmapStore) -> InMemoryRoadmapStore:
    return implement_store


@pytest.fixture
def checkout(tmp_path: Path) -> Path:
    return make_checkout(tmp_path, BEHAVIOR)


def _run(store: InMemoryRoadmapStore, checkout: Path, script: ModelScript) -> StepOutcome:
    return run_step(store, item=1, group=1, source=checkout, model=script.model(), window=WINDOW)


def _pytest_runs(programs: ProcessFake) -> list[ProcessCall]:
    return [call for call in programs.calls if "pytest" in call.argv]


def test_a_behavior_group_whose_tests_pass_on_base_is_refused_with_the_files_named(
    store: InMemoryRoadmapStore, checkout: Path, implement_programs: ProcessFake
) -> None:
    answer_pytest_on_base(implement_programs, junit((TEST_ID, "passed")))
    script = ModelScript(tool_calls(*WORK), say("Done."))

    outcome = _run(store, checkout, script)

    budget = DEFAULT_ROADMAP_IMPLEMENT_REPAIR_ROUNDS
    assert (outcome.status, outcome.reason) == (
        StepStatus.STOPPED,
        PASSES_REASON + rounds_spent(budget),
    )


def test_a_test_that_passes_on_base_gets_one_repair_turn_that_writes_a_failing_test(
    store: InMemoryRoadmapStore, checkout: Path, implement_programs: ProcessFake
) -> None:
    answer_pytest_on_base(
        implement_programs, junit((TEST_ID, "passed")), junit((TEST_ID, "failed"))
    )
    script = ModelScript(
        tool_calls(*WORK),
        say("Done."),
        tool_calls(write_call(TEST_PATH, FIXED_BODY)),
        say("Done."),
    )

    outcome = _run(store, checkout, script)

    assert (outcome.status, outcome.repair_rounds, _replay(outcome)) == (
        StepStatus.DONE,
        1,
        ("fails_on_base", (TEST_ID,)),
    )


def test_a_repair_turn_of_a_behavior_group_may_not_change_source(
    store: InMemoryRoadmapStore, checkout: Path, implement_programs: ProcessFake
) -> None:
    answer_pytest_on_base(implement_programs, junit((TEST_ID, "passed")))
    script = ModelScript(
        tool_calls(*WORK),
        say("Done."),
        tool_calls(write_call("src/sample.py", SHOUT_CODE + "\n# more\n")),
        say("Done."),
    )

    outcome = _run(store, checkout, script)

    assert (outcome.status, "src/sample.py" in outcome.reason) == (StepStatus.STOPPED, True)


def test_a_collection_error_on_base_does_not_count_as_a_failure_on_base(
    store: InMemoryRoadmapStore, checkout: Path, implement_programs: ProcessFake
) -> None:
    answer_pytest_on_base(implement_programs, junit((TEST_PATH, "errored")))
    script = ModelScript(tool_calls(*WORK), say("Done."))

    outcome = _run(store, checkout, script)

    assert (outcome.status, outcome.reason.startswith(COLLECTION_REASON)) == (
        StepStatus.STOPPED,
        True,
    )
    assert _replay(outcome) == ("errors_on_base", ())


def test_a_test_that_fails_on_base_and_passes_after_the_change_is_accepted(
    store: InMemoryRoadmapStore, checkout: Path, implement_programs: ProcessFake
) -> None:
    answer_pytest_on_base(implement_programs, junit((TEST_ID, "failed")))
    script = ModelScript(tool_calls(*WORK), say("Done."))

    outcome = _run(store, checkout, script)

    assert (outcome.status, outcome.repair_rounds, outcome.commit) == (
        StepStatus.DONE,
        0,
        git(checkout, "rev-parse", "HEAD"),
    )
    assert _replay(outcome) == ("fails_on_base", (TEST_ID,))


def test_a_behavior_group_that_changes_no_test_file_is_refused_without_a_repair_turn(
    store: InMemoryRoadmapStore, checkout: Path, implement_programs: ProcessFake
) -> None:
    answer_pytest_on_base(implement_programs, junit((TEST_ID, "failed")))
    script = ModelScript(
        tool_calls(
            write_call("src/sample.py", SHOUT_CODE), write_call(TASKS_PATH, TICKED_BEHAVIOR)
        ),
        say("Done."),
    )

    outcome = _run(store, checkout, script)

    assert (outcome.status, outcome.reason, outcome.repair_rounds) == (
        StepStatus.STOPPED,
        NO_TEST_REASON,
        0,
    )
    assert _pytest_runs(implement_programs) == []


def test_an_other_group_runs_its_verify_commands_and_keeps_their_output(
    store: InMemoryRoadmapStore, implement_programs: ProcessFake, tmp_path: Path
) -> None:
    checkout = make_checkout(tmp_path)

    def ran(call: ProcessCall) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(call.argv, 0, stdout="ran\n", stderr="")

    implement_programs.answer("uv", ProcessAnswer(side_effect=ran))
    outcome = _run(store, checkout, ModelScript(tool_calls(*the_whole_group()), say("Done.")))

    assert [(c.command, c.status, c.output) for c in outcome.verified] == [
        ("uv run devops ci test tests/test_sample.py", 0, "ran"),
        ("uv run devops docs check", 0, "ran"),
    ]
