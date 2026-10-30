"""The tests that a step of `devops roadmap implement` keeps (#2804): the names of the tests in a
file, and the tests that a file lost. Every test stays in its own file.

A test is a function or an async function whose name starts with `test_`, at module level or in a
class, also inside an `if`, `try`, `with` or loop block. Its name is the qualified name: `test_x`,
or `Class.test_x`. The standard library `ast` lists them, so a decorator, a parameter and the body
do not matter. A function inside a function is a helper and is no test. A byte order mark at the
start of a file does not matter. The check has known limits: it reads names, so a test that keeps
its name and loses its body, and a test that an `if False:` block hides, are not found.
"""

from __future__ import annotations

import ast
from collections.abc import Iterator, Mapping
from typing import Protocol

_TEST_PREFIX = "test_"
_TESTS_DIR = "tests"
_BYTE_ORDER_MARK = "\ufeff"
_BLOCKS = (ast.stmt, ast.ExceptHandler, ast.match_case)

# The names of the tests of one file, or None when the file does not parse.
FileTests = frozenset[str] | None


def _walk(node: ast.AST, prefix: str) -> Iterator[str]:
    """The qualified names of the tests under `node`. The walk goes into statements only: a test is
    never inside an expression."""
    for child in ast.iter_child_nodes(node):
        if isinstance(child, ast.FunctionDef | ast.AsyncFunctionDef):
            if child.name.startswith(_TEST_PREFIX):
                yield prefix + child.name
        elif isinstance(child, ast.ClassDef):
            yield from _walk(child, f"{prefix}{child.name}.")
        elif isinstance(child, _BLOCKS):
            yield from _walk(child, prefix)


def defined_tests(text: str) -> FileTests:
    """The qualified names of the tests in the Python source `text`, or None when it does not
    parse. The caller skips such a file: the static check reports its error."""
    try:
        tree = ast.parse(text.removeprefix(_BYTE_ORDER_MARK))
    except SyntaxError, ValueError:
        return None
    return frozenset(_walk(tree, ""))


def lost_tests(
    before: Mapping[str, FileTests], after: Mapping[str, FileTests]
) -> dict[str, list[str]]:
    """The tests that each file lost, by path in sorted order, each list sorted. `before` maps a
    path to its tests at the start and `after` maps it to its tests after the run. A path that is
    not in `after` was deleted, and loses every test. A path that is not in `before` is new. A file
    that does not parse is skipped. Every test stays in its own file: a test that moves to another
    file is lost."""
    lost: dict[str, list[str]] = {}
    for path in sorted(before):
        started, now = before[path], after.get(path, frozenset())
        if started is None or now is None:
            continue
        gone = sorted(started - now)
        if gone:
            lost[path] = gone
    return lost


class GitOutput(Protocol):
    """A git command in the checkout. It returns what the command printed and raises when git
    fails."""

    def __call__(self, *args: str) -> str: ...


def _changes(git: GitOutput, start: str) -> Iterator[tuple[str, str]]:
    """The status and the path of each Python file under `tests/` that differs between the commit
    `start` and the index. Renames are off, so a move is a delete plus an add whatever the git
    settings are."""
    listing = git(
        "diff", "--cached", "--name-status", "--no-renames", "-z", start, "--", _TESTS_DIR
    ).split("\0")
    for status, path in zip(listing[0::2], listing[1::2], strict=False):
        if path.endswith(".py"):
            yield status, path


def lost_since(git: GitOutput, start: str) -> dict[str, list[str]]:
    """The tests that each test file lost between the commit `start` and the index, for the paths
    in sorted order (`lost_tests`). The index holds the files as the commit would. A file that was
    added has no tests at the start. A file that was deleted, or replaced by a link, has none
    after the run."""
    before: dict[str, FileTests] = {}
    after: dict[str, FileTests] = {}
    for status, path in _changes(git, start):
        if status != "A":
            before[path] = defined_tests(git("show", f"{start}:{path}"))
        if status not in ("D", "T"):
            after[path] = defined_tests(git("show", f":{path}"))
    return lost_tests(before, after)
