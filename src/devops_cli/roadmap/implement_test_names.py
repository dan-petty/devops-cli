"""The tests that a step of `devops roadmap implement` keeps (#2804): the names of the tests in a
file, and the tests that a file lost.

A test is a function or an async function whose name starts with `test_`, at module level or in a
class, also inside an `if`, `try`, `with` or loop block. Its name is the qualified name: `test_x`,
or `Class.test_x`. The standard library `ast` lists them, so a decorator, a parameter and the body
do not matter. A function inside a function is a helper and is no test.
"""

from __future__ import annotations

import ast
from collections import Counter
from collections.abc import Iterator, Mapping

_TEST_PREFIX = "test_"
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
        tree = ast.parse(text)
    except SyntaxError, ValueError:
        return None
    return frozenset(_walk(tree, ""))


def _new_names(before: Mapping[str, FileTests], after: Mapping[str, FileTests]) -> Counter[str]:
    """How many files hold each name that the run added to them. A file that does not parse, at the
    start or after the run, adds none: its list is not known."""
    added: Counter[str] = Counter()
    for path, names in after.items():
        if names is None or (path in before and before[path] is None):
            continue
        added.update(names - (before.get(path) or frozenset()))
    return added


def lost_tests(
    before: Mapping[str, FileTests], after: Mapping[str, FileTests]
) -> dict[str, list[str]]:
    """The tests that each file lost, by path in sorted order, each list sorted. `before` maps a
    path to its tests at the start and `after` maps it to its tests after the run. A path that is
    not in `after` was deleted, and loses every test. A path that is not in `before` is new. A file
    that does not parse is skipped. A lost test is excused by a test of the same qualified name
    that is new in another file, once: the test moved."""
    excuses = _new_names(before, after)
    lost: dict[str, list[str]] = {}
    for path in sorted(before):
        started, now = before[path], after.get(path, frozenset())
        if started is None or now is None:
            continue
        gone = []
        for name in sorted(started - now):
            if excuses[name] > 0:
                excuses[name] -= 1
            else:
                gone.append(name)
        if gone:
            lost[path] = gone
    return lost
