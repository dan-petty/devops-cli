"""The tasks file of a step (#2767, #2790): the job writes `tasks.md` back to its text before the
run, and applies only the ticks of the own group. No edit of the file stops the step.

The model is a pydantic-ai `FunctionModel` from `ModelScript`. Git runs for real on a checkout in
`tmp_path`; every other program is answered by `process_fake`.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from devops_cli.exceptions.roadmap import RoadmapImplementError
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
    make_checkout,
    write_call,
)
from tests.support.model_script import ModelScript, say, tool_calls

pytestmark = pytest.mark.usefixtures("keyring_store")

WORK = (write_call("tests/test_sample.py", TEST_BODY), write_call("src/sample.py", SHOUT_CODE))
NOTE = "Restored the tasks.md of the change 1-sample-change. A step only ticks the tasks of its own group."
BASE = TICKED.replace("- [x] Document", "- [ ] Document")


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


EDITS = {
    "text": EVERY_TICK.replace("Document the function", "Describe the function"),
    "command": EVERY_TICK.replace(
        "Verification: `uv run devops docs check`\n\n## Workflow",
        "Verification: `uv run devops docs check --all`\n\n## Workflow",
    ),
    "added group": EVERY_TICK.replace(
        "## Workflow follow-up", "## 3. A third group\n\n- [x] Do more\n\n## Workflow follow-up"
    ),
    "removed group": EVERY_TICK.split("## 2.")[0]
    + "## Workflow"
    + EVERY_TICK.split("## Workflow")[1],
    "bullet": EVERY_TICK.replace("- [x] Document", "* [x] Document"),
    "added line": EVERY_TICK.replace(
        "## Workflow follow-up", "Extra prose by the model.\n\n## Workflow follow-up"
    ),
    "outside every group": EVERY_TICK.replace("# Tasks\n", "# Tasks\n\nThe model was here.\n", 1),
    "follow-up section": EVERY_TICK.replace("A plain bullet", "A changed bullet"),
    "unticked group with a line": BASE.replace(
        "## Workflow follow-up", "Extra prose by the model.\n\n## Workflow follow-up"
    ).replace("- [ ] Add", "- [x] Add"),
}


@pytest.mark.parametrize("edited", EDITS.values(), ids=EDITS.keys())
def test_an_edit_of_the_tasks_file_beyond_the_ticks_of_the_group_is_undone(
    edited: str, store: InMemoryRoadmapStore, later_open: Path, programs: ProcessFake
) -> None:
    script = ModelScript(tool_calls(*WORK, write_call(TASKS_PATH, edited)), say("Done."))

    result = _step(store, later_open, script)

    assert (result, _committed_tasks(later_open)) == ((StepStatus.DONE, ""), BASE)


def test_a_number_that_the_model_deletes_from_a_task_of_a_later_group_is_restored(
    store: InMemoryRoadmapStore, tmp_path: Path, programs: ProcessFake
) -> None:
    numbered = LATER_OPEN.replace("- [ ] Document", "- [ ] 2.1 Document")
    checkout = make_checkout(tmp_path, numbered)
    edited = numbered.replace("- [ ] Add", "- [x] Add").replace(
        "- [ ] 2.1 Document", "- [x] Document"
    )
    script = ModelScript(tool_calls(*WORK, write_call(TASKS_PATH, edited)), say("Done."))

    result = _step(store, checkout, script)

    assert (result, _committed_tasks(checkout)) == (
        (StepStatus.DONE, ""),
        numbered.replace("- [ ] Add", "- [x] Add"),
    )


def test_an_edit_of_a_later_group_in_the_extra_turn_is_undone(
    store: InMemoryRoadmapStore, later_open: Path, programs: ProcessFake
) -> None:
    script = ModelScript(
        tool_calls(*WORK),
        say("The work is done."),
        tool_calls(write_call(TASKS_PATH, EDITS["text"])),
        say("Ok."),
    )

    assert (_step(store, later_open, script), _committed_tasks(later_open)) == (
        (StepStatus.DONE, ""),
        BASE,
    )


LONE = "# Tasks" + "\r" * 62 + "\n"


@pytest.mark.parametrize("written", [LONE, "# Tasks\n"], ids=["lone CR kept", "lone CR dropped"])
def test_a_tasks_file_with_lone_cr_line_ends_is_written_back_and_ticked_on_the_right_lines(
    written: str, store: InMemoryRoadmapStore, tmp_path: Path, programs: ProcessFake
) -> None:
    checkout = make_checkout(tmp_path, LATER_OPEN.replace("# Tasks\n", LONE, 1))
    ticked = EVERY_TICK.replace("# Tasks\n", written, 1)
    script = ModelScript(tool_calls(*WORK, write_call(TASKS_PATH, ticked)), say("Done."))

    result = _step(store, checkout, script)

    expected = BASE.replace("# Tasks\n", LONE, 1)
    assert (result, (checkout / TASKS_PATH).read_text(encoding="utf-8", newline="")) == (
        (StepStatus.DONE, ""),
        expected,
    )


def _hidden_edit() -> str:
    """The `tasks.md` of a model that edits group 2 and then adds a copy of the first group 2."""
    edited = LATER_OPEN.replace("Document the function", "Do evil things")
    original = LATER_OPEN.split("## 2.")[1].split("## Workflow")[0]
    return edited.replace("- [ ] Add", "- [x] Add") + f"\n## 2.{original}"


def test_a_copy_of_a_group_that_hides_an_edit_of_it_changes_nothing_in_the_commit(
    store: InMemoryRoadmapStore, later_open: Path, programs: ProcessFake
) -> None:
    script = ModelScript(tool_calls(*WORK, write_call(TASKS_PATH, _hidden_edit())), say("Done."))

    result = _step(store, later_open, script)

    assert (result, _committed_tasks(later_open)) == ((StepStatus.DONE, ""), BASE)


def test_a_fix_step_that_hides_an_edit_behind_a_copy_of_a_group_leaves_the_tasks_as_they_were(
    store: InMemoryRoadmapStore, later_open: Path, programs: ProcessFake
) -> None:
    script = ModelScript(
        tool_calls(
            write_call("src/sample.py", SHOUT_CODE),
            write_call(TASKS_PATH, _hidden_edit().replace("- [x] Add", "- [ ] Add")),
        ),
        say("Fixed."),
    )

    outcome = run_fix_step(
        store,
        item=1,
        fix=FixRequest(check="lint", log="E501"),
        source=later_open,
        model=script.model(),
        window=WINDOW,
    )

    assert (outcome.status, outcome.reason, _committed_tasks(later_open)) == (
        StepStatus.DONE,
        "",
        LATER_OPEN,
    )


def test_a_change_whose_tasks_file_numbers_a_group_twice_is_refused(
    store: InMemoryRoadmapStore, tmp_path: Path
) -> None:
    twice = TASKS.replace("## Workflow follow-up", "## 2. A copy\n\n- [ ] More\n\n## Workflow")
    checkout = make_checkout(tmp_path, twice)

    with pytest.raises(RoadmapImplementError, match="two groups numbered 2"):
        build_step_inputs(store, item=1, group=1, source=checkout, window=WINDOW)


def test_the_step_prints_one_line_that_names_the_change_it_restores(
    store: InMemoryRoadmapStore,
    later_open: Path,
    programs: ProcessFake,
    capsys: pytest.CaptureFixture[str],
) -> None:
    script = ModelScript(tool_calls(*WORK, write_call(TASKS_PATH, EVERY_TICK)), say("Done."))

    _step(store, later_open, script)

    notes = [line for line in capsys.readouterr().err.splitlines() if "Restored" in line]
    assert notes == [NOTE]


def test_the_step_prints_one_line_when_the_model_edits_many_groups_in_a_turn(
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
    assert notes == [NOTE]


def test_the_step_prints_no_note_when_the_model_only_ticks_its_own_group(
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


def test_a_fix_step_that_ticks_a_task_of_any_group_leaves_the_tasks_as_they_were(
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

    assert (outcome.status, outcome.reason, _committed_tasks(later_open)) == (
        StepStatus.DONE,
        "",
        LATER_OPEN,
    )


def test_a_link_in_place_of_the_tasks_file_is_replaced_and_the_target_is_not_written(
    store: InMemoryRoadmapStore, later_open: Path, tmp_path: Path, programs: ProcessFake
) -> None:
    target = tmp_path / "outside.txt"
    target.write_text("outside\n", encoding="utf-8")
    tasks = later_open / TASKS_PATH

    def link() -> None:
        tasks.unlink()
        tasks.symlink_to(target)

    script = ModelScript(tool_calls(*WORK), say("Done."), effects={2: link})

    result = _step(store, later_open, script)

    assert (result[0], target.read_text(encoding="utf-8"), tasks.is_symlink()) == (
        StepStatus.STOPPED,
        "outside\n",
        False,
    )


def test_a_link_to_a_file_with_the_wanted_text_is_replaced_by_the_file(
    store: InMemoryRoadmapStore, later_open: Path, tmp_path: Path, programs: ProcessFake
) -> None:
    wanted = TICKED.replace("- [x] Document", "- [ ] Document")
    target = tmp_path / "copy.md"
    target.write_text(wanted, encoding="utf-8")
    tasks = later_open / TASKS_PATH

    def link() -> None:
        tasks.unlink()
        tasks.symlink_to(target)

    script = ModelScript(
        tool_calls(*WORK, write_call(TASKS_PATH, wanted)), say("Done."), effects={2: link}
    )

    result = _step(store, later_open, script)

    assert (result, tasks.is_symlink(), git(later_open, "ls-tree", "HEAD", TASKS_PATH)[:6]) == (
        (StepStatus.DONE, ""),
        False,
        "100644",
    )


def test_a_directory_in_place_of_the_tasks_file_ends_the_step_with_a_stop_and_the_file(
    store: InMemoryRoadmapStore, later_open: Path, programs: ProcessFake
) -> None:
    tasks = later_open / TASKS_PATH

    def directory() -> None:
        tasks.unlink()
        tasks.mkdir()
        (tasks / "inner.txt").write_text("inner\n", encoding="utf-8")

    script = ModelScript(
        tool_calls(*WORK, write_call(TASKS_PATH, TICKED)), say("Done."), effects={2: directory}
    )

    result = _step(store, later_open, script)

    assert (result[0], tasks.is_file(), (later_open / TASKS_PATH).read_text(encoding="utf-8")) == (
        StepStatus.STOPPED,
        True,
        LATER_OPEN,
    )


def test_a_group_that_the_model_ticks_in_part_gets_the_extra_turn_for_the_rest(
    store: InMemoryRoadmapStore, later_open: Path, programs: ProcessFake
) -> None:
    first_only = LATER_OPEN.replace("- [ ] Add the failing", "- [x] Add the failing")
    script = ModelScript(
        tool_calls(*WORK, write_call(TASKS_PATH, first_only)),
        say("The work is done."),
        tool_calls(write_call(TASKS_PATH, EVERY_TICK)),
        say("Ticked."),
    )

    result = _step(store, later_open, script)

    last = [str(getattr(part, "content", "")) for part in script.seen[2][-1].parts][-1]
    assert (result, "- [ ] Add `shout`" in last, "Add the failing" in last) == (
        (StepStatus.DONE, ""),
        True,
        False,
    )
    assert _committed_tasks(later_open) == BASE


def test_a_group_that_the_model_ticks_in_part_and_not_more_stops_with_the_first_unticked_task(
    store: InMemoryRoadmapStore, later_open: Path, programs: ProcessFake
) -> None:
    first_only = LATER_OPEN.replace("- [ ] Add the failing", "- [x] Add the failing")
    script = ModelScript(tool_calls(*WORK, write_call(TASKS_PATH, first_only)), say("Done."))

    assert _step(store, later_open, script) == (
        StepStatus.STOPPED,
        "A task of the group is not ticked: [ ] Add `shout` to `src/sample.py`",
    )


def test_a_model_that_adds_a_task_to_its_group_and_ticks_all_gets_no_tick(
    store: InMemoryRoadmapStore, later_open: Path, programs: ProcessFake
) -> None:
    added = BASE.replace("- [x] Add `shout`", "- [x] Do more\n- [x] Add `shout`")
    script = ModelScript(tool_calls(*WORK, write_call(TASKS_PATH, added)), say("Done."))

    assert _step(store, later_open, script) == (
        StepStatus.STOPPED,
        "A task of the group is not ticked: [ ] Add the failing test `tests/test_sample.py` "
        "for `src/sample.py`",
    )


def test_a_step_that_unticks_a_task_of_its_own_done_group_keeps_it_ticked(
    store: InMemoryRoadmapStore, tmp_path: Path, programs: ProcessFake
) -> None:
    checkout = make_checkout(tmp_path, EVERY_TICK)
    script = ModelScript(tool_calls(*WORK, write_call(TASKS_PATH, LATER_OPEN)), say("Done."))

    result = _step(store, checkout, script)

    assert (result, _committed_tasks(checkout)) == ((StepStatus.DONE, ""), EVERY_TICK)


def test_the_instructions_say_to_tick_only_the_tasks_of_the_group_and_give_the_reason(
    store: InMemoryRoadmapStore, later_open: Path
) -> None:
    inputs = build_step_inputs(store, item=1, group=1, source=later_open, window=WINDOW)

    assert (
        "Tick only the tasks of your group. A later group runs in its own step and ticks its own."
        in inputs.instructions
    )
