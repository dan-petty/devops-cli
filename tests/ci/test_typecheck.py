"""The one definition of the type check of the gate (#3090): the row `typecheck` of `devops ci` and
the implement step build their command from it, and the step keeps the files that the gate checks.
"""

from __future__ import annotations

import pytest

from devops_cli.ci.typecheck import (
    TYPECHECK_OPTIONS,
    TYPECHECK_PATHS,
    typecheck_argv,
    typecheck_files,
)
from devops_cli.commands.ci import get_check_spec


def test_the_row_typecheck_runs_strict_mypy_on_the_paths_of_the_definition() -> None:
    assert get_check_spec("typecheck").cmd == [
        "uv",
        "run",
        "mypy",
        "--python-version",
        "3.14",
        "--strict",
        "src",
    ]
    assert get_check_spec("typecheck").cmd == typecheck_argv(TYPECHECK_PATHS)


def test_the_options_of_the_definition_are_the_options_of_the_gate() -> None:
    gate = get_check_spec("typecheck").cmd
    assert gate[3 : 3 + len(TYPECHECK_OPTIONS)] == list(TYPECHECK_OPTIONS)


@pytest.mark.parametrize("root", TYPECHECK_PATHS)
def test_a_changed_python_file_below_a_path_of_the_gate_is_checked(root: str) -> None:
    changed = [f"{root}/devops_cli/x.py", f"{root}/y.py", f"{root}/y.txt", f"{root}x/z.py"]

    assert typecheck_files(changed) == [f"{root}/devops_cli/x.py", f"{root}/y.py"]


def test_a_test_file_and_a_document_are_not_checked() -> None:
    assert typecheck_files(["tests/x.py", "docs/y.md", "z.py", "openspec/changes/a/tasks.md"]) == []
