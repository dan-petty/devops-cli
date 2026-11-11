"""The repair scope of a fix turn after a push (#4028): the paths of the plan and the change folder,
and the logs that name one of them."""

from __future__ import annotations

import pytest

from devops_cli.roadmap.implement.implement_fix_scope import RepairScope, repair_scope
from devops_cli.roadmap.step_files import parse_task_groups

FOLDER = "openspec/changes/archive/2026-11-11-7-a-change"
TASKS = """\
# Tasks

## 1. First

Reads: `CONTEXT.md`. Changes: `a.py` (new).

- [ ] 1.1 Add `a.py` and run `$ uv run devops ci test tests/test_a.py`

## 2. Second

Changes: `src/b.py`.

- [ ] 2.1 Change `src/b.py`
"""


def test_the_scope_holds_the_path_of_each_group_and_the_change_folder() -> None:
    scope = repair_scope(parse_task_groups(TASKS), FOLDER)

    assert scope.paths == ("CONTEXT.md", "a.py", "src/b.py")
    assert scope.folder == FOLDER


@pytest.mark.parametrize(
    "log",
    [
        "src/b.py:3:1: E501 line too long",
        "/home/runner/work/repo/repo/a.py:9: error",
        f"{FOLDER}/tasks.md is not valid",
    ],
)
def test_a_log_that_names_a_path_of_the_scope_is_in_scope(log: str) -> None:
    scope = repair_scope(parse_task_groups(TASKS), FOLDER)

    assert scope.names(log) is True


@pytest.mark.parametrize(
    "log", ["", "Process completed with exit code 1", "xa.py failed", "src/b.pyc failed"]
)
def test_a_log_that_names_no_path_of_the_scope_is_out_of_scope(log: str) -> None:
    scope = repair_scope(parse_task_groups(TASKS), FOLDER)

    assert scope.names(log) is False


def test_a_command_in_a_task_is_no_path_of_the_scope() -> None:
    scope = repair_scope(parse_task_groups(TASKS), FOLDER)

    assert all(" " not in path for path in scope.paths)


def test_an_empty_plan_holds_only_the_change_folder() -> None:
    assert RepairScope(paths=(), folder=FOLDER).names(f"{FOLDER}/design.md") is True
