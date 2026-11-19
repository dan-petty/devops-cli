"""Which tests of a changed test file a pull request changed (#3124).

The fail-to-pass gate needs to tell a test that the fix changes from a test that it leaves alone:
a test that the fix leaves alone must pass on the base. A test is unchanged when its function in
the head file has the same syntax tree as the function of the same name in the base file, and the
rest of the file, which holds the imports, helpers and fixtures that the test runs, has the same
syntax tree too. Layout and comments are no part of a syntax tree, so they change no test.

A collection error names a whole file and no test, so the gate asks whether the file changed: a
file is unchanged when its head and its base have the same syntax tree (#6372).

A gate check module that only loses checks needs no proof, since a deleted check runs on neither
tree (#6456). Its head keeps the top-level statements of its base in the same order, by syntax
tree and with no module docstring, and leaves out at least one `def check_*`. Each statement that
it leaves out is an import, an assignment to names, a function or a class, and the head uses no
name that such a statement binds. So no kept case can see the change.
"""

from __future__ import annotations

import ast
from typing import NamedTuple

from devops_cli.config.constants import CONST_GATE_CHECK_PREFIX, CONST_TEST_FILE_PREFIX

_QualifiedName = tuple[str, ...]
# The top-level statements that bind a name with no assignment.
_DEFINITIONS = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Import, ast.ImportFrom)


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


def is_file_changed(base: ParsedTests | None, head: ParsedTests | None) -> bool:
    """Whether a test file differs between its two parses (`parse_tests`): in a test, in a helper,
    an import or a fixture. A file that is new, or that a parse does not hold, counts as changed,
    as `is_test_changed` counts such a test (#6372)."""
    return base is None or head is None or base != head


def _statements(source: str | None) -> list[ast.stmt] | None:
    """The top-level statements of `source` without its module docstring, or None when there is
    no source or it does not parse."""
    if source is None:
        return None
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return None
    return tree.body[1:] if ast.get_docstring(tree, clean=False) is not None else tree.body


def _target_names(target: ast.expr) -> set[str] | None:
    """The names that an assignment to `target` binds, or None when it sets an attribute or an
    item."""
    match target:
        case ast.Name(id=name):
            return {name}
        case ast.Starred(value=value):
            return _target_names(value)
        case ast.Tuple(elts=elements) | ast.List(elts=elements):
            names: set[str] = set()
            for element in elements:
                if (bound := _target_names(element)) is None:
                    return None
                names |= bound
            return names
    return None


def _bound_names(node: ast.stmt) -> set[str] | None:
    """The names that a top-level statement binds, when it only binds names: a function, a class,
    an import other than `from __future__` or `*`, or an assignment to names. Else None."""
    match node:
        case ast.FunctionDef(name=name) | ast.AsyncFunctionDef(name=name) | ast.ClassDef(name=name):
            return {name}
        case ast.Import(names=aliases):
            return {alias.asname or alias.name.partition(".")[0] for alias in aliases}
        case ast.ImportFrom(module=module, names=aliases) if module != "__future__" and all(
            alias.name != "*" for alias in aliases
        ):
            return {alias.asname or alias.name for alias in aliases}
        case ast.Assign(targets=targets):
            names: set[str] = set()
            for target in targets:
                if (bound := _target_names(target)) is None:
                    return None
                names |= bound
            return names
        case ast.AnnAssign(target=target):
            return _target_names(target)
    return None


def _left_out(base: list[ast.stmt], head: list[ast.stmt]) -> list[ast.stmt] | None:
    """The statements of `base` that `head` leaves out, when `head` is `base` in the same order
    with some statements left out. Else None: the head adds, changes or moves a statement."""
    head_dumps = [ast.dump(node) for node in head]
    kept = 0
    left_out: list[ast.stmt] = []
    for node in base:
        if kept < len(head_dumps) and ast.dump(node) == head_dumps[kept]:
            kept += 1
        else:
            left_out.append(node)
    return left_out if kept == len(head_dumps) else None


def _used_names(head: list[ast.stmt]) -> set[str]:
    """Each name that the statements of `head` read or bind."""
    names = {node.id for stmt in head for node in ast.walk(stmt) if isinstance(node, ast.Name)}
    for stmt in head:
        if isinstance(stmt, _DEFINITIONS):
            names |= _bound_names(stmt) or set()
    return names


def only_deleted_checks(module: str, base: str | None, head: str | None) -> tuple[str, ...]:
    """The checks that a gate check module deletes, named `<module>.<check>` as
    `tests/gate/runner.py` names a case, in the order of the base, when the module only loses
    checks (#6456). Else an empty tuple: the module is new or deleted, a side does not parse, or
    the head adds, changes or moves a statement, or leaves out a statement that a kept case can
    see."""
    if (base_body := _statements(base)) is None or (head_body := _statements(head)) is None:
        return ()
    if (left_out := _left_out(base_body, head_body)) is None:
        return ()
    bound: set[str] = set()
    for node in left_out:
        if (names := _bound_names(node)) is None:
            return ()
        bound |= names
    if bound & _used_names(head_body):
        return ()
    return tuple(
        f"{module}.{node.name}"
        for node in left_out
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
        and node.name.startswith(CONST_GATE_CHECK_PREFIX)
    )
