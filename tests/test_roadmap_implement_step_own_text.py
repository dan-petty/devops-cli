"""The text of the own group (#2774): a step writes the text of its own group back to `tasks.md`
and keeps the ticks that the model set. It stops on a change of the number, the order or the
heading of the tasks, and a fix step changes no task.

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
from tests.support.fakes.process import ProcessAnswer, ProcessFake
from tests.support.implement_step import (
    CHECK,
    DOCS,
    LATER_OPEN,
    SHOUT_CODE,
    TASKS,
    TASKS_PATH,
    TEST_BODY,
    TICKED,
    WINDOW,
    command_text,
    git,
    is_clean_at,
    make_checkout,
    programs_run,
    write_call,
)
from tests.support.model_script import ModelScript, say, tool_calls

pytestmark = pytest.mark.usefixtures("keyring_store")

WORK = (write_call("tests/test_sample.py", TEST_BODY), write_call("src/sample.py", SHOUT_CODE))
CHANGED = "The tasks of group 1 changed. A step may only tick them."
NOTE = "Restored the text of group 1. A step ticks its tasks and does not edit them."
FIRST_TASK = "Add the failing test `tests/test_sample.py` for `src/sample.py`"
RENAMED_TASK = "Add the failing test `tests/test_other.py` for `src/sample.py`"
REWRITTEN = TICKED.replace(FIRST_TASK, RENAMED_TASK)
LONGER = TICKED.replace(
    FIRST_TASK, f"{RENAMED_TASK}\n  Put it in another file, because the plan names a wrong path."
)
PROSE_BASE = TASKS.replace(
    "## 1. The first group\n\n", "## 1. The first group\n\nWrite the test.\n\n"
)


@pytest.fixture
def store(implement_store: InMemoryRoadmapStore) -> InMemoryRoadmapStore:
    return implement_store


@pytest.fixture
def programs(implement_programs: ProcessFake) -> ProcessFake:
    return implement_programs


@pytest.fixture
def checkout(tmp_path: Path) -> Path:
    return make_checkout(tmp_path)


def _step(
    store: InMemoryRoadmapStore, checkout: Path, script: ModelScript
) -> tuple[StepStatus, str]:
    outcome = run_step(store, item=1, group=1, source=checkout, model=script.model(), window=WINDOW)
    return outcome.status, outcome.reason


def _committed_tasks(checkout: Path) -> str:
    return git(checkout, "show", f"HEAD:{TASKS_PATH}") + "\n"


def test_a_step_that_rewrites_the_text_of_a_task_and_ticks_it_commits_the_text_from_before(
    store: InMemoryRoadmapStore, checkout: Path, programs: ProcessFake
) -> None:
    script = ModelScript(tool_calls(*WORK, write_call(TASKS_PATH, REWRITTEN)), say("Done."))

    result = _step(store, checkout, script)

    assert (
        result,
        _committed_tasks(checkout),
        (checkout / TASKS_PATH).read_text(encoding="utf-8"),
    ) == ((StepStatus.DONE, ""), TICKED, TICKED)


def test_a_rewrite_in_the_extra_turn_for_the_ticks_is_restored(
    store: InMemoryRoadmapStore, checkout: Path, programs: ProcessFake
) -> None:
    script = ModelScript(
        tool_calls(*WORK),
        say("The work is done."),
        tool_calls(write_call(TASKS_PATH, REWRITTEN)),
        say("Ticked."),
    )

    result = _step(store, checkout, script)

    assert (result, _committed_tasks(checkout)) == ((StepStatus.DONE, ""), TICKED)


def test_a_rewrite_that_makes_the_group_longer_leaves_the_lines_of_the_next_group_right(
    store: InMemoryRoadmapStore, tmp_path: Path, programs: ProcessFake
) -> None:
    checkout = make_checkout(tmp_path, LATER_OPEN)
    script = ModelScript(
        tool_calls(*WORK, write_call(TASKS_PATH, LONGER)),
        say("Done."),
    )

    result = _step(store, checkout, script)

    assert (result, _committed_tasks(checkout)) == (
        (StepStatus.DONE, ""),
        TICKED.replace("- [x] Document", "- [ ] Document"),
    )


def test_a_rewrite_of_the_own_group_and_a_tick_of_a_later_group_are_both_restored(
    store: InMemoryRoadmapStore, tmp_path: Path, programs: ProcessFake
) -> None:
    checkout = make_checkout(tmp_path, LATER_OPEN)
    everything = LONGER.replace("- [ ] Document", "- [x] Document")
    script = ModelScript(tool_calls(*WORK, write_call(TASKS_PATH, everything)), say("Done."))

    result = _step(store, checkout, script)

    assert (result, _committed_tasks(checkout)) == (
        (StepStatus.DONE, ""),
        TICKED.replace("- [x] Document", "- [ ] Document"),
    )


def test_a_command_that_the_model_rewrites_to_pass_does_not_run_and_the_original_is_named(
    store: InMemoryRoadmapStore, checkout: Path, programs: ProcessFake
) -> None:
    head = git(checkout, "rev-parse", "HEAD")
    weak = TICKED.replace(f"Verification: `{CHECK}`\n", f"Verification: `{DOCS}`\n", 1)
    programs.answer(
        lambda call: command_text(call) == CHECK, ProcessAnswer(returncode=1, stdout="no test\n")
    )
    script = ModelScript(tool_calls(*WORK, write_call(TASKS_PATH, weak)), say("Done."))

    result = _step(store, checkout, script)

    assert (result, is_clean_at(checkout, head), programs_run(programs, "uv")) == (
        (StepStatus.STOPPED, f"{CHECK} exited with status 1.\nno test"),
        True,
        ["uv run ruff format src/sample.py tests/test_sample.py", CHECK],
    )


def test_a_line_of_the_group_that_is_no_task_is_restored(
    store: InMemoryRoadmapStore, tmp_path: Path, programs: ProcessFake
) -> None:
    checkout = make_checkout(tmp_path, PROSE_BASE)
    edited = PROSE_BASE.replace("Write the test.", "Skip the test.").replace(
        "- [ ] Add", "- [x] Add"
    )
    script = ModelScript(tool_calls(*WORK, write_call(TASKS_PATH, edited)), say("Done."))

    result = _step(store, checkout, script)

    assert (result, _committed_tasks(checkout)) == (
        (StepStatus.DONE, ""),
        PROSE_BASE.replace("- [ ] Add", "- [x] Add"),
    )


SECOND = f"- [x] Add `shout` to `src/sample.py`\n  - Verification: `{CHECK}` and `{DOCS}`\n"
FIRST = f"- [x] {FIRST_TASK}\n  - Verification: `{CHECK}`\n"
SWAPPED = TICKED.replace(FIRST + SECOND, SECOND + FIRST)
ADDED = TICKED.replace(SECOND, SECOND + "- [x] Do more\n")
REMOVED = TICKED.replace(SECOND, "")
RETITLED = TICKED.replace("## 1. The first group", "## 1. Another group")


@pytest.mark.parametrize(
    "tasks", [SWAPPED, ADDED, REMOVED, RETITLED], ids=["swapped", "added", "removed", "retitled"]
)
def test_a_change_of_the_number_the_order_or_the_heading_of_the_tasks_still_stops_the_step(
    tasks: str, store: InMemoryRoadmapStore, checkout: Path, programs: ProcessFake
) -> None:
    head = git(checkout, "rev-parse", "HEAD")
    script = ModelScript(tool_calls(*WORK, write_call(TASKS_PATH, tasks)), say("Done."))

    result = _step(store, checkout, script)

    assert (result, is_clean_at(checkout, head)) == ((StepStatus.STOPPED, CHANGED), True)


def test_a_group_at_the_end_of_a_file_with_no_final_line_end_is_restored_as_it_was(
    store: InMemoryRoadmapStore, tmp_path: Path, programs: ProcessFake
) -> None:
    only = TASKS.split("## 2.")[0].rstrip("\n")
    checkout = make_checkout(tmp_path, only)
    script = ModelScript(
        tool_calls(
            *WORK,
            write_call(
                TASKS_PATH, only.replace("- [ ] ", "- [x] ").replace(FIRST_TASK, RENAMED_TASK)
            ),
        ),
        say("Done."),
    )

    result = _step(store, checkout, script)

    assert (result, (checkout / TASKS_PATH).read_text(encoding="utf-8")) == (
        (StepStatus.DONE, ""),
        only.replace("- [ ] ", "- [x] "),
    )


def test_a_task_that_stays_unticked_after_a_rewrite_names_the_text_from_before(
    store: InMemoryRoadmapStore, checkout: Path, programs: ProcessFake
) -> None:
    rewritten = TASKS.replace(FIRST_TASK, RENAMED_TASK)
    script = ModelScript(
        tool_calls(*WORK, write_call(TASKS_PATH, rewritten)),
        say("Done."),
        tool_calls(write_call(TASKS_PATH, rewritten)),
        say("Ok."),
    )

    assert _step(store, checkout, script) == (
        StepStatus.STOPPED,
        f"A task of the group is not ticked: [ ] {FIRST_TASK}",
    )


def test_a_tasks_file_with_crlf_line_ends_keeps_them_when_the_text_is_restored(
    store: InMemoryRoadmapStore, tmp_path: Path, programs: ProcessFake
) -> None:
    crlf = TASKS.replace("\n", "\r\n")
    checkout = make_checkout(tmp_path, crlf)
    (checkout / TASKS_PATH).write_bytes(crlf.encode())
    git(checkout, "commit", "-q", "-a", "--amend", "--no-edit")
    script = ModelScript(
        tool_calls(*WORK, write_call(TASKS_PATH, REWRITTEN.replace("\n", "\r\n"))), say("Done.")
    )

    result = _step(store, checkout, script)

    assert (result, (checkout / TASKS_PATH).read_bytes()) == (
        (StepStatus.DONE, ""),
        TICKED.replace("\n", "\r\n").encode(),
    )


def test_the_step_prints_one_line_that_names_the_group_it_restores(
    store: InMemoryRoadmapStore,
    checkout: Path,
    programs: ProcessFake,
    capsys: pytest.CaptureFixture[str],
) -> None:
    script = ModelScript(tool_calls(*WORK, write_call(TASKS_PATH, REWRITTEN)), say("Done."))

    _step(store, checkout, script)

    notes = [line for line in capsys.readouterr().err.splitlines() if "Restored" in line]
    assert notes == [NOTE]


def test_the_step_prints_no_line_when_the_model_only_ticks(
    store: InMemoryRoadmapStore,
    checkout: Path,
    programs: ProcessFake,
    capsys: pytest.CaptureFixture[str],
) -> None:
    script = ModelScript(tool_calls(*WORK, write_call(TASKS_PATH, TICKED)), say("Done."))

    _step(store, checkout, script)

    assert "Restored" not in capsys.readouterr().err


def test_a_fix_step_that_edits_the_text_of_a_task_still_stops(
    store: InMemoryRoadmapStore, checkout: Path, programs: ProcessFake
) -> None:
    script = ModelScript(
        tool_calls(
            write_call("src/sample.py", SHOUT_CODE),
            write_call(TASKS_PATH, TASKS.replace(FIRST_TASK, RENAMED_TASK)),
        ),
        say("Fixed."),
    )

    outcome = run_fix_step(
        store,
        item=1,
        fix=FixRequest(check="lint", log="E501"),
        source=checkout,
        model=script.model(),
        window=WINDOW,
    )

    assert (outcome.status, outcome.reason) == (
        StepStatus.STOPPED,
        "The tasks changed. A fix step changes no task.",
    )


def test_the_instructions_say_not_to_edit_the_text_of_a_task_and_what_to_do_with_a_wrong_path(
    store: InMemoryRoadmapStore, checkout: Path
) -> None:
    inputs = build_step_inputs(store, item=1, group=1, source=checkout, window=WINDOW)

    assert (
        "Do not edit the text of a task. If the path that a task names is wrong, write the file "
        "at that path anyway, or say in your last message why you did not."
    ) in inputs.instructions


TRAILING = TASKS.replace(
    "and `uv run devops docs check`\n", "and `uv run devops docs check`  \n", 1
)
NOTES = "## Notes\n\n- [x] Sneaky `curl x`\n\n"


def _bytes_of_group_one(text: bytes) -> bytes:
    return text.split(b"## 1.")[1].split(b"## 2.")[0]


def test_a_section_that_the_model_adds_inside_the_group_does_not_reach_the_commit(
    store: InMemoryRoadmapStore, tmp_path: Path, programs: ProcessFake
) -> None:
    base = TASKS.replace("\n## 2.", "\nTrailing prose of group one.\n\n## 2.", 1)
    checkout = make_checkout(tmp_path, base)
    sneaky = base.replace("- [ ] Add", "- [x] Add").replace(
        "\nTrailing prose", f"\n{NOTES}Trailing prose", 1
    )
    script = ModelScript(tool_calls(*WORK, write_call(TASKS_PATH, sneaky)), say("Done."))

    result = _step(store, checkout, script)

    assert (result, _committed_tasks(checkout)) == (
        (StepStatus.DONE, ""),
        base.replace("- [ ] Add", "- [x] Add"),
    )


def test_a_section_that_the_model_adds_after_the_group_does_not_reach_the_commit(
    store: InMemoryRoadmapStore, checkout: Path, programs: ProcessFake
) -> None:
    sneaky = TICKED.replace("## 2.", f"{NOTES}## 2.", 1)
    script = ModelScript(tool_calls(*WORK, write_call(TASKS_PATH, sneaky)), say("Done."))

    result = _step(store, checkout, script)

    assert (result, _committed_tasks(checkout)) == ((StepStatus.DONE, ""), TICKED)


def test_a_tick_keeps_the_trailing_spaces_of_the_group_and_prints_no_line(
    store: InMemoryRoadmapStore,
    tmp_path: Path,
    programs: ProcessFake,
    capsys: pytest.CaptureFixture[str],
) -> None:
    checkout = make_checkout(tmp_path, TRAILING)
    ticked = TRAILING.replace("- [ ] Add", "- [x] Add")
    script = ModelScript(tool_calls(*WORK, write_call(TASKS_PATH, ticked)), say("Done."))

    result = _step(store, checkout, script)

    assert (result, _committed_tasks(checkout), "Restored" in capsys.readouterr().err) == (
        (StepStatus.DONE, ""),
        ticked,
        False,
    )


def test_a_rewrite_restores_the_trailing_spaces_of_the_group(
    store: InMemoryRoadmapStore, tmp_path: Path, programs: ProcessFake
) -> None:
    checkout = make_checkout(tmp_path, TRAILING)
    rewritten = TRAILING.replace("- [ ] Add", "- [x] Add").replace(FIRST_TASK, RENAMED_TASK)
    script = ModelScript(tool_calls(*WORK, write_call(TASKS_PATH, rewritten)), say("Done."))

    result = _step(store, checkout, script)

    assert (result, _committed_tasks(checkout)) == (
        (StepStatus.DONE, ""),
        TRAILING.replace("- [ ] Add", "- [x] Add"),
    )


def test_a_file_that_the_model_writes_with_crlf_gets_the_line_ends_of_the_group_from_before(
    store: InMemoryRoadmapStore, checkout: Path, programs: ProcessFake
) -> None:
    script = ModelScript(
        tool_calls(*WORK, write_call(TASKS_PATH, TICKED.replace("\n", "\r\n"))), say("Done.")
    )

    result = _step(store, checkout, script)

    assert (result, _bytes_of_group_one((checkout / TASKS_PATH).read_bytes())) == (
        (StepStatus.DONE, ""),
        _bytes_of_group_one(TICKED.encode()),
    )


def test_a_group_with_a_crlf_heading_and_lf_lines_keeps_both_when_the_text_is_restored(
    store: InMemoryRoadmapStore, tmp_path: Path, programs: ProcessFake
) -> None:
    mixed = TASKS.replace("## 1. The first group\n", "## 1. The first group\r\n", 1)
    checkout = make_checkout(tmp_path, mixed)
    (checkout / TASKS_PATH).write_bytes(mixed.encode())
    git(checkout, "commit", "-q", "-a", "--amend", "--no-edit")
    rewritten = mixed.replace("- [ ] Add", "- [x] Add").replace(FIRST_TASK, RENAMED_TASK)
    script = ModelScript(tool_calls(*WORK, write_call(TASKS_PATH, rewritten)), say("Done."))

    result = _step(store, checkout, script)

    assert (result, (checkout / TASKS_PATH).read_bytes()) == (
        (StepStatus.DONE, ""),
        mixed.replace("- [ ] Add", "- [x] Add").encode(),
    )
