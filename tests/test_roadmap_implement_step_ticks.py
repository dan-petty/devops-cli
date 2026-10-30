"""The ticks of the other groups (#2767): a step restores the checkboxes of every group but its
own, and stops on any other change to another group.

The model is a pydantic-ai `FunctionModel` from `ModelScript`. Git runs for real on a checkout in
`tmp_path`; every other program is answered by `process_fake`.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from devops_cli.roadmap.implement_step import (
    FixRequest,
    StepStatus,
    build_step_inputs,
    run_fix_step,
    run_step,
)
from devops_cli.roadmap.memory_store import InMemoryRoadmapStore
from tests.support.fakes.process import ProcessFake
from tests.support.implement_step import (
    EVERY_TICK,
    LATER_OPEN,
    SHOUT_CODE,
    TASKS,
    TASKS_PATH,
    TEST_BODY,
    TICKED,
    WINDOW,
    git,
    is_clean_at,
    make_checkout,
    write_call,
)
from tests.support.model_script import ModelScript, say, tool_calls

pytestmark = pytest.mark.usefixtures("keyring_store")

WORK = (write_call("tests/test_sample.py", TEST_BODY), write_call("src/sample.py", SHOUT_CODE))
EDITED = "Group 2 changed. A step may change only its own group."
NOTE = "Restored the checkboxes of these groups: {groups}. A step ticks only its own group."


@pytest.fixture
def store(implement_store: InMemoryRoadmapStore) -> InMemoryRoadmapStore:
    return implement_store


@pytest.fixture
def programs(implement_programs: ProcessFake) -> ProcessFake:
    return implement_programs


@pytest.fixture
def later_open(tmp_path: Path) -> Path:
    """A checkout whose group 2 is unticked, as a change is before its second step."""
    return make_checkout(tmp_path, LATER_OPEN)


def _step(
    store: InMemoryRoadmapStore, checkout: Path, script: ModelScript, group: int = 1
) -> tuple[StepStatus, str]:
    outcome = run_step(
        store, item=1, group=group, source=checkout, model=script.model(), window=WINDOW
    )
    return outcome.status, outcome.reason


def _committed_tasks(checkout: Path) -> str:
    return git(checkout, "show", f"HEAD:{TASKS_PATH}") + "\n"


def test_a_step_that_ticks_a_later_group_ends_done_and_commits_the_later_group_unticked(
    store: InMemoryRoadmapStore, later_open: Path, programs: ProcessFake
) -> None:
    script = ModelScript(tool_calls(*WORK, write_call(TASKS_PATH, EVERY_TICK)), say("Done."))

    result = _step(store, later_open, script)

    assert (
        result,
        _committed_tasks(later_open),
        sorted(git(later_open, "show", "--name-only", "--format=", "HEAD").splitlines()),
        git(later_open, "status", "--porcelain"),
    ) == (
        (StepStatus.DONE, ""),
        TICKED.replace("- [x] Document", "- [ ] Document"),
        [TASKS_PATH, "src/sample.py", "tests/test_sample.py"],
        "",
    )


def test_the_working_tree_holds_the_restored_file_when_the_step_is_done(
    store: InMemoryRoadmapStore, later_open: Path, programs: ProcessFake
) -> None:
    script = ModelScript(tool_calls(*WORK, write_call(TASKS_PATH, EVERY_TICK)), say("Done."))

    _step(store, later_open, script)

    assert (later_open / TASKS_PATH).read_text(encoding="utf-8") == TICKED.replace(
        "- [x] Document", "- [ ] Document"
    )


def test_a_step_that_unticks_an_earlier_group_is_restored(
    store: InMemoryRoadmapStore, tmp_path: Path, programs: ProcessFake
) -> None:
    first_done = TASKS.replace("- [ ] Add", "- [x] Add").replace("- [x] Document", "- [ ] Document")
    checkout = make_checkout(tmp_path, first_done)
    unticked = EVERY_TICK.replace("- [x] Add", "- [ ] Add")
    script = ModelScript(
        tool_calls(
            write_call("docs/SAMPLE.md", "The sample shouts.\n"), write_call(TASKS_PATH, unticked)
        ),
        say("Done."),
    )

    result = _step(store, checkout, script, group=2)

    assert (result, _committed_tasks(checkout)) == ((StepStatus.DONE, ""), EVERY_TICK)


def test_the_extra_turn_that_ticks_a_later_group_is_restored(
    store: InMemoryRoadmapStore, later_open: Path, programs: ProcessFake
) -> None:
    script = ModelScript(
        tool_calls(*WORK),
        say("The work is done."),
        tool_calls(write_call(TASKS_PATH, EVERY_TICK)),
        say("Ticked."),
    )

    result = _step(store, later_open, script)

    assert (result, _committed_tasks(later_open)) == (
        (StepStatus.DONE, ""),
        TICKED.replace("- [x] Document", "- [ ] Document"),
    )


def test_a_text_edit_of_a_later_group_stops_the_step_with_the_group_named(
    store: InMemoryRoadmapStore, later_open: Path, programs: ProcessFake
) -> None:
    head = git(later_open, "rev-parse", "HEAD")
    edited = EVERY_TICK.replace("Document the function", "Describe the function")
    script = ModelScript(tool_calls(*WORK, write_call(TASKS_PATH, edited)), say("Done."))

    result = _step(store, later_open, script)

    assert (result, is_clean_at(later_open, head)) == ((StepStatus.STOPPED, EDITED), True)


def test_a_ticked_task_of_a_later_group_with_an_edited_command_stops_the_step(
    store: InMemoryRoadmapStore, later_open: Path, programs: ProcessFake
) -> None:
    edited = EVERY_TICK.replace(
        "Verification: `uv run devops docs check`\n\n## Workflow",
        "Verification: `uv run devops docs check --all`\n\n## Workflow",
    )
    script = ModelScript(tool_calls(*WORK, write_call(TASKS_PATH, edited)), say("Done."))

    assert _step(store, later_open, script) == (StepStatus.STOPPED, EDITED)


def test_a_text_edit_of_a_later_group_in_the_extra_turn_stops_the_step(
    store: InMemoryRoadmapStore, later_open: Path, programs: ProcessFake
) -> None:
    edited = EVERY_TICK.replace("Document the function", "Describe the function")
    script = ModelScript(
        tool_calls(*WORK),
        say("The work is done."),
        tool_calls(write_call(TASKS_PATH, edited)),
        say("Ok."),
    )

    assert _step(store, later_open, script) == (StepStatus.STOPPED, EDITED)


def test_a_group_that_the_model_adds_stops_the_step_with_the_group_named(
    store: InMemoryRoadmapStore, later_open: Path, programs: ProcessFake
) -> None:
    added = EVERY_TICK.replace(
        "## Workflow follow-up", "## 3. A third group\n\n- [x] Do more\n\n## Workflow follow-up"
    )
    script = ModelScript(tool_calls(*WORK, write_call(TASKS_PATH, added)), say("Done."))

    assert _step(store, later_open, script) == (
        StepStatus.STOPPED,
        "Group 3 changed. A step may change only its own group.",
    )


def test_the_step_prints_one_line_that_names_the_restored_groups(
    store: InMemoryRoadmapStore,
    later_open: Path,
    programs: ProcessFake,
    capsys: pytest.CaptureFixture[str],
) -> None:
    script = ModelScript(tool_calls(*WORK, write_call(TASKS_PATH, EVERY_TICK)), say("Done."))

    _step(store, later_open, script)

    notes = [line for line in capsys.readouterr().err.splitlines() if "Restored" in line]
    assert notes == [NOTE.format(groups="2")]


def test_the_step_prints_one_line_for_all_the_groups_it_restores_in_a_turn(
    store: InMemoryRoadmapStore,
    tmp_path: Path,
    programs: ProcessFake,
    capsys: pytest.CaptureFixture[str],
) -> None:
    three = LATER_OPEN.replace(
        "## Workflow follow-up", "## 3. A third group\n\n- [ ] Do more\n\n## Workflow follow-up"
    )
    checkout = make_checkout(tmp_path, three)
    ticked = three.replace("- [ ] Add", "- [x] Add").replace("- [ ] ", "- [x] ")
    script = ModelScript(tool_calls(*WORK, write_call(TASKS_PATH, ticked)), say("Done."))

    _step(store, checkout, script)

    notes = [line for line in capsys.readouterr().err.splitlines() if "Restored" in line]
    assert notes == [NOTE.format(groups="2, 3")]


def test_the_step_prints_no_note_when_no_other_group_changed(
    store: InMemoryRoadmapStore,
    later_open: Path,
    programs: ProcessFake,
    capsys: pytest.CaptureFixture[str],
) -> None:
    own = TICKED.replace("- [x] Document", "- [ ] Document")
    script = ModelScript(tool_calls(*WORK, write_call(TASKS_PATH, own)), say("Done."))

    _step(store, later_open, script)

    assert "Restored" not in capsys.readouterr().err


def test_a_tasks_file_with_crlf_line_ends_keeps_them_when_the_restore_writes_it(
    store: InMemoryRoadmapStore, tmp_path: Path, programs: ProcessFake
) -> None:
    crlf = LATER_OPEN.replace("\n", "\r\n")
    checkout = make_checkout(tmp_path, crlf)
    (checkout / TASKS_PATH).write_bytes(crlf.encode())
    git(checkout, "commit", "-q", "-a", "--amend", "--no-edit")
    ticked = EVERY_TICK.replace("\n", "\r\n")
    script = ModelScript(tool_calls(*WORK, write_call(TASKS_PATH, ticked)), say("Done."))

    result = _step(store, checkout, script)

    assert (result, (checkout / TASKS_PATH).read_bytes()) == (
        (StepStatus.DONE, ""),
        TICKED.replace("- [x] Document", "- [ ] Document").replace("\n", "\r\n").encode(),
    )


def test_a_fix_step_that_ticks_a_task_of_any_group_still_stops(
    store: InMemoryRoadmapStore, later_open: Path, programs: ProcessFake
) -> None:
    script = ModelScript(
        tool_calls(write_call("src/sample.py", SHOUT_CODE), write_call(TASKS_PATH, EVERY_TICK)),
        say("Fixed."),
    )
    fix = FixRequest(check="lint", log="E501")

    outcome = run_fix_step(
        store, item=1, fix=fix, source=later_open, model=script.model(), window=WINDOW
    )

    assert (outcome.status, outcome.reason) == (
        StepStatus.STOPPED,
        "The tasks changed. A fix step changes no task.",
    )


def test_the_instructions_say_to_tick_only_the_tasks_of_the_group_and_give_the_reason(
    store: InMemoryRoadmapStore, later_open: Path
) -> None:
    inputs = build_step_inputs(store, item=1, group=1, source=later_open, window=WINDOW)

    assert (
        "Tick only the tasks of your group. A later group runs in its own step and ticks its own."
        in inputs.instructions
    )
