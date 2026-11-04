"""Which tests of a changed test file a pull request changed (#3124).

The fail-to-pass gate needs to tell a test that the fix changes from a test that it leaves alone:
a test that the fix leaves alone must pass on the base. A test is unchanged when its function in
the head file has the same syntax tree as the function of the same name in the base file, and the
rest of the file, which holds the imports, helpers and fixtures that the test runs, has the same
syntax tree too. Layout and comments are no part of a syntax tree, so they change no test.
"""

from __future__ import annotations

import ast
from typing import NamedTuple

from devops_cli.config.constants import CONST_TEST_FILE_PREFIX

_QualifiedName = tuple[str, ...]


class ParsedTests(NamedTuple):
    """The syntax trees of a test file, as dumps: its test functions by qualified name, and the
    rest of the file once those functions are taken out."""

    functions: dict[_QualifiedName, str]
    rest: str


class _WithoutTests(ast.NodeTransformer):
    """Takes the test functions out of a module, and leaves the imports, helpers and fixtures."""

    def visit_FunctionDef(self, node: ast.FunctionDef) -> ast.FunctionDef | None:
        return None if node.name.startswith(CONST_TEST_FILE_PREFIX) else node

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> ast.AsyncFunctionDef | None:
        return None if node.name.startswith(CONST_TEST_FILE_PREFIX) else node


def _collect(
    body: list[ast.stmt], prefix: _QualifiedName, found: dict[_QualifiedName, str]
) -> None:
    """Add the dump of each test function in `body`, and of each test method of its classes, to
    `found`, keyed by its class names and its name."""
    for node in body:
        if isinstance(node, ast.ClassDef):
            _collect(node.body, (*prefix, node.name), found)
        elif isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef) and node.name.startswith(
            CONST_TEST_FILE_PREFIX
        ):
            found[(*prefix, node.name)] = ast.dump(node)


def parse_tests(source: str | None) -> ParsedTests | None:
    """The syntax trees of `source`, or None when there is no source or it does not parse."""
    if source is None:
        return None
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return None
    functions: dict[_QualifiedName, str] = {}
    _collect(tree.body, (), functions)
    return ParsedTests(functions, ast.dump(_WithoutTests().visit(tree)))


def is_test_changed(
    class_path: tuple[str, ...], name: str, base: ParsedTests | None, head: ParsedTests | None
) -> bool:
    """Whether the test `name`, in the classes `class_path`, differs between the two parses of
    its file (`parse_tests`), or the file differs around its tests.

    A test that is new, or that a parse does not hold, counts as changed. A parse of None means
    that the source is missing or does not parse. A helper or fixture that changes makes every
    test of the file changed, since a test that runs other code can fail on the base for a reason
    that the fix adds. The gate refuses a replay for a test that it knows to be unchanged and for
    no other.
    """
    if base is None or head is None or base.rest != head.rest:
        return True
    key = (*class_path, name)
    return key not in head.functions or head.functions.get(key) != base.functions.get(key)
