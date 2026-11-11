"""The task-prompt checks of the `test-tree` row find a missing prompt and an orphan prompt (#4630).

`tests/gate/tree_checks/task_prompts.py` runs in the `test-tree` row of `devops ci`. These cases
give it a small tree of modules and a small tasks folder.
"""

from __future__ import annotations

import ast
from pathlib import Path

from tests.gate.tree_checks.task_prompts import missing_prompts, unread_prompts

_CONSTANTS = 'from typing import Final\n\nPLAN_PROMPT: Final[str] = "plan.md"\n'
_READER = (
    "from pkg.constants import PLAN_PROMPT\n"
    "from pkg.loader import load_task_prompt\n\n"
    '_LOCAL = "gone.md"\n\n\n'
    "def run(task: str) -> str:\n"
    '    return load_task_prompt("chat.md") + load_task_prompt(PLAN_PROMPT)'
    " + load_task_prompt(_LOCAL) + load_task_prompt(task)\n"
)


def _tree(src: Path, sources: dict[str, str]) -> dict[Path, ast.Module]:
    """The parsed modules of a small `src` tree, keyed by path as the row keys them."""
    return {src / name: ast.parse(text) for name, text in sources.items()}


def _tasks(root: Path, *names: str) -> Path:
    """A tasks folder that holds one prompt file for each name."""
    tasks = root / "tasks"
    tasks.mkdir()
    for name in names:
        (tasks / name).write_text("Prompt.\n", encoding="utf-8")
    return tasks


def test_a_missing_prompt_is_found_through_a_literal_and_a_constant(tmp_path: Path) -> None:
    """Verify the check resolves literals and constants, also imported ones, and skips a parameter."""
    src = tmp_path / "src"
    trees = _tree(src, {"pkg/constants.py": _CONSTANTS, "pkg/reader.py": _READER})
    tasks = _tasks(tmp_path, "chat.md")

    missing = missing_prompts(trees, src, tasks)

    assert missing == {"plan.md": ["pkg/reader.py:8"], "gone.md": ["pkg/reader.py:8"]}


def test_code_that_loads_no_named_prompt_fails_the_check(tmp_path: Path) -> None:
    """Verify a tree with no prompt name given to the loader does not pass as complete."""
    src = tmp_path / "src"

    missing = missing_prompts(_tree(src, {"pkg/constants.py": _CONSTANTS}), src, _tasks(tmp_path))

    assert missing == {"<none>": []}


def test_a_prompt_file_that_no_literal_names_is_an_orphan(tmp_path: Path) -> None:
    """Verify a file of the tasks folder with no string literal that names it is reported."""
    src = tmp_path / "src"
    trees = _tree(src, {"pkg/constants.py": _CONSTANTS, "pkg/reader.py": _READER})
    tasks = _tasks(tmp_path, "chat.md", "plan.md", "orphan.md")

    assert unread_prompts(trees, tasks) == ["orphan.md"]
