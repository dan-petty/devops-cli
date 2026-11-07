"""The mechanical rewrite of a merged plan (#3556): it adds a `Verification:` line to a group that
has none, changes a sample path in a task to a bare name, and adds a `design.md` stub. It keeps
every task group."""

from __future__ import annotations

import difflib
from datetime import date

from devops_cli.roadmap.implement.implement_shell_policy import Verification, read_verification
from devops_cli.roadmap.plan_read import read_change
from devops_cli.roadmap.plan_rewrite import rewrite_plan
from devops_cli.roadmap.stage.stage_change import render_change
from devops_cli.roadmap.stage.stage_paths import StagedTree
from devops_cli.roadmap.step_files import parse_task_groups
from tests.support.builders import make_stage_proposal

CREATED = date(2026, 11, 6)
ROOT = "openspec/changes/7-a-merged-plan"
TASKS_PATH = f"{ROOT}/tasks.md"
DESIGN_PATH = f"{ROOT}/design.md"
TREE = StagedTree(["src/devops_cli/sample.py", "docs/guide.md", "README.md"])

NO_VERIFICATION = """# Tasks

## 1. Add the sample

Kind: behavior. Reads: none. Changes: `src/devops_cli/sample.py`, `tests/test_sample.py` (new).

- [ ] 1.1 Write the failing test in `tests/test_sample.py`
- [ ] 1.2 Add the function to `src/devops_cli/sample.py`

## 2. Keep the sample

Reads: none. Changes: `src/devops_cli/sample.py`, `tests/test_keep.py` (new), `tests/test_more.py` (new).

- [ ] 2.1 Keep the sample as it is in `src/devops_cli/sample.py`

## 3. Write the guide

Reads: `README.md`. Changes: `docs/guide.md`.

- [ ] 3.1 Describe the sample in `docs/guide.md`

## 4. Run a check by hand

Reads: none. Changes: scratch files only.

- [ ] 4.1 Run the sample and read its output
"""


def _files(tasks: str, *, design: bool = True) -> dict[str, str]:
    files = {TASKS_PATH: tasks, f"{ROOT}/proposal.md": "# Proposal\n"}
    if design:
        files[DESIGN_PATH] = "# Design\n"
    return files


def _added_lines(before: str, after: str) -> list[str]:
    """The lines that the rewrite adds, and none that it removes."""
    diff = list(difflib.unified_diff(before.splitlines(), after.splitlines(), lineterm="", n=0))
    assert [line for line in diff if line.startswith("-") and not line.startswith("---")] == []
    return [line[1:] for line in diff if line.startswith("+") and not line.startswith("+++")]


def test_a_rewrite_keeps_the_groups_and_adds_one_line_to_a_group_it_can_prove() -> None:
    before = parse_task_groups(NO_VERIFICATION)

    rewritten = rewrite_plan(ROOT, _files(NO_VERIFICATION), TREE).files[TASKS_PATH]

    after = parse_task_groups(rewritten)
    assert [(g.number, g.title) for g in after] == [(g.number, g.title) for g in before]
    assert [[task.text for task in g.tasks] for g in after] == [
        [task.text for task in g.tasks] for g in before
    ]
    assert [g.verification_commands for g in after] == [
        ("uv run devops ci test tests/test_sample.py",),
        ("uv run devops ci test tests/test_keep.py tests/test_more.py",),
        ("uv run devops ci docs",),
        (),
    ]


def test_each_new_line_names_a_command_that_the_step_can_run() -> None:
    rewritten = rewrite_plan(ROOT, _files(NO_VERIFICATION), TREE).files[TASKS_PATH]

    added = _added_lines(NO_VERIFICATION, rewritten)

    assert len(added) == 3
    assert all(line.startswith("  - Verification: ") for line in added)
    commands = [c for g in parse_task_groups(rewritten) for c in g.verification_commands]
    assert all(isinstance(read_verification(command), Verification) for command in commands)


def test_a_behavior_group_gets_the_fails_on_the_base_form_and_any_other_group_passes() -> None:
    rewritten = rewrite_plan(ROOT, _files(NO_VERIFICATION), TREE).files[TASKS_PATH]

    added = _added_lines(NO_VERIFICATION, rewritten)

    assert added == [
        "  - Verification: `$ uv run devops ci test tests/test_sample.py` fails on the base",
        "  - Verification: `$ uv run devops ci test tests/test_keep.py tests/test_more.py` passes",
        "  - Verification: `$ uv run devops ci docs` passes",
    ]
    first = parse_task_groups(rewritten)[0]
    assert first.tasks[0].verification == ("uv run devops ci test tests/test_sample.py",)
    assert first.tasks[0].fails_on_base


def test_the_new_line_sits_under_the_first_task_of_the_group() -> None:
    rewritten = rewrite_plan(ROOT, _files(NO_VERIFICATION), TREE).files[TASKS_PATH]

    lines = rewritten.splitlines()
    first = lines.index("- [ ] 1.1 Write the failing test in `tests/test_sample.py`")
    assert lines[first + 1].startswith("  - Verification: ")
    assert lines[first + 2] == "- [ ] 1.2 Add the function to `src/devops_cli/sample.py`"


def test_a_group_that_changes_no_test_and_no_document_gets_no_line() -> None:
    result = rewrite_plan(ROOT, _files(NO_VERIFICATION), TREE)

    fourth = parse_task_groups(result.files[TASKS_PATH])[3]
    assert fourth.verification_commands == ()
    assert not any("Group 4" in note for note in result.notes)


def test_a_group_that_has_a_verification_line_is_left_as_it_is() -> None:
    tasks = NO_VERIFICATION.replace(
        "- [ ] 3.1 Describe the sample in `docs/guide.md`",
        "- [ ] 3.1 Describe the sample in `docs/guide.md`\n"
        "  - Verification: `$ uv run devops ci docs` passes",
    )

    rewritten = rewrite_plan(ROOT, _files(tasks), TREE).files[TASKS_PATH]

    assert len(_added_lines(tasks, rewritten)) == 2
    assert rewritten.count("`$ uv run devops ci docs`") == 1


def test_a_command_that_the_step_refuses_is_not_written() -> None:
    tasks = NO_VERIFICATION.replace(
        "`tests/test_keep.py` (new), `tests/test_more.py` (new)", "`tests/test keep.py` (new)"
    )

    rewritten = rewrite_plan(ROOT, _files(tasks), TREE).files[TASKS_PATH]

    assert parse_task_groups(rewritten)[1].verification_commands == ()


SAMPLE_PATH = """# Tasks

## 1. Add the sample

Reads: none. Changes: `src/devops_cli/sample.py`, `tests/test_real.py` (new).

- [ ] 1.1 Write the failing test in `tests/test_real.py`, and let it write `tests/test_sample.py` and
  read `src/devops_cli/sample.py` and `tests/test_late.py`
  - Verification: `$ uv run devops ci test tests/test_real.py` passes
- [ ] 1.2 Add `src/devops_cli/missing.py` (new)

## 2. Add the late test

Reads: none. Changes: `tests/test_late.py` (new).

- [ ] 2.1 Write the late test
  - Verification: `$ uv run devops ci test tests/test_late.py` passes
"""


def test_a_sample_path_in_a_task_becomes_a_bare_name() -> None:
    result = rewrite_plan(ROOT, _files(SAMPLE_PATH), TREE)

    rewritten = result.files[TASKS_PATH]

    assert "`test_sample.py`" in rewritten
    assert "`tests/test_sample.py`" not in rewritten
    assert any("tests/test_sample.py" in note for note in result.notes)
    assert [g.number for g in parse_task_groups(rewritten)] == [1, 2]


def test_a_path_that_the_tree_has_or_a_group_lists_or_creates_stays_as_it_is() -> None:
    rewritten = rewrite_plan(ROOT, _files(SAMPLE_PATH), TREE).files[TASKS_PATH]

    for kept in (
        "`tests/test_real.py`",
        "`src/devops_cli/sample.py`",
        "`tests/test_late.py`",
        "`src/devops_cli/missing.py` (new)",
    ):
        assert kept in rewritten


def test_a_path_on_a_reads_line_stays_and_a_verification_line_is_never_edited() -> None:
    tasks = (
        SAMPLE_PATH.replace(
            "Reads: none. Changes: `src/devops_cli/sample.py`",
            "Reads: `docs/note.md`. Changes: `src/devops_cli/sample.py`",
        )
        .replace("read `src/devops_cli/sample.py`", "read `docs/note.md`")
        .replace(
            "passes\n- [ ] 1.2",
            "passes\n  - Verification: `$ uv run devops ci test tests/test_sample.py` passes\n- [ ] 1.2",
        )
    )

    rewritten = rewrite_plan(ROOT, _files(tasks), TREE).files[TASKS_PATH]

    assert "read `docs/note.md`" in rewritten
    assert "  - Verification: `$ uv run devops ci test tests/test_sample.py` passes" in rewritten


def test_a_folder_with_no_design_gets_a_stub_that_the_plan_reader_accepts() -> None:
    proposal = make_stage_proposal()
    files = render_change("7-a-merged-plan", proposal, {"comment-thread"}, created=CREATED)
    del files[DESIGN_PATH]

    result = rewrite_plan(ROOT, files, StagedTree(["src/devops_cli/sample.py"]))

    assert DESIGN_PATH in result.files
    assert [change.path for change in result.changes] == [DESIGN_PATH]
    assert result.changes[0].before is None
    assert (
        read_change(result.files).groups == read_change({**files, DESIGN_PATH: "# Design\n"}).groups
    )


def test_a_plan_that_needs_no_change_comes_back_as_it_was() -> None:
    files = render_change(
        "7-a-merged-plan", make_stage_proposal(), {"comment-thread"}, created=CREATED
    )

    result = rewrite_plan(ROOT, files, StagedTree(["src/devops_cli/sample.py"]))

    assert result.files == files
    assert result.changes == ()
    assert result.notes == ()
