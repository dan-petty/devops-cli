"""The strength check of the implement job (#3051): how strong the tests of an item are.

The scoped checks of `implement_scoped_ci.py` run the tests of an item, and a test that asserts
nothing passes. This check measures the strength of the new tests in three parts:

- the assertion scan of the new test files, with the rule `test-function-has-assertion`: a test
  function that holds no `assert`, no `pytest.raises` or `pytest.warns` call and no `self.assert*`
  call proves nothing.

The parts after it, the bounded mutation run and the coverage delta of the changed files, come with
the later groups of #3051.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

from devops_cli.config.commands import BIN_UV
from devops_cli.config.constants import CONST_PYTHON_FILE_SUFFIX, CONST_TESTS_ROOT_DIR
from devops_cli.core.process import run_subprocess

_ASSERTION_RULE = ".ast-grep/rules/test-function-has-assertion.yml"
_TEST_MODULE_PREFIX = "test_"


@dataclass(frozen=True)
class AssertionFinding:
    """A test function that asserts nothing: its file, the line of the function, and the message
    of the rule that found it."""

    path: str
    line: int
    message: str


def new_test_files(names: Iterable[str]) -> list[str]:
    """The new test modules of the changed paths `names`: a Python file under `tests/` whose name
    starts with `test_`. The assertion rule scans only those, and a helper such as `conftest.py` or
    `tests/support/` holds no test function of its own."""
    files: list[str] = []
    for name in names:
        path = PurePosixPath(name)
        if (
            path.suffix == CONST_PYTHON_FILE_SUFFIX
            and path.parts
            and path.parts[0] == CONST_TESTS_ROOT_DIR
            and path.name.startswith(_TEST_MODULE_PREFIX)
        ):
            files.append(name)
    return files


def _assertion_command(files: Sequence[str]) -> list[str]:
    """The command line of the assertion scan over `files`: each path is one argument, so no shell
    reads it."""
    return [
        BIN_UV,
        "run",
        "ast-grep",
        "scan",
        "--rule",
        _ASSERTION_RULE,
        "--json",
        *files,
    ]


def assertion_failures(source: Path, files: Sequence[str]) -> tuple[AssertionFinding, ...]:
    """The test functions of `files` that assert nothing, in the checkout `source`.

    The rule `test-function-has-assertion` holds the definition of an assertion, so a second parser
    would define it twice. The scan exits 1 when it finds one, and prints the file, the start line
    and the message of each match as JSON.
    """
    if not files:
        return ()
    done = run_subprocess(_assertion_command(files), cwd=source, quiet=True)
    matches: list[dict[str, Any]] = json.loads(done.stdout or "[]")
    return tuple(
        AssertionFinding(
            path=str(match["file"]),
            line=int(match["range"]["start"]["line"]) + 1,
            message=str(match["message"]),
        )
        for match in matches
    )
