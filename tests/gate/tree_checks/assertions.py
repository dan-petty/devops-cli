"""No test certifies a failure without checking it (#2164)."""

from __future__ import annotations

import ast
import tomllib
from collections.abc import Mapping
from pathlib import Path
from typing import Final

from devops_cli.config.constants import (
    CONST_PRESENCE_CHECK_NAMES,
)
from tests.gate.ruff_selection import ruff_enforces
from tests.support.paths import REPO_ROOT
from tests.support.trees import (
    parse_python_file,
)

CONST_BLIND_EXCEPTION_TYPES: Final[frozenset[str]] = frozenset({"Exception", "BaseException"})


CONST_TEST_ASSERTION_LINT_RULES: Final[frozenset[str]] = frozenset(
    {"B011", "B015", "B017", "B018", "PT011", "PT015", "PT017", "PT018", "RUF043"}
)


def _expected_exception_name(call: ast.Call) -> str | None:
    """Name the exception type a `pytest.raises` call expects, when it is a plain name."""
    is_raises = isinstance(call.func, ast.Attribute) and call.func.attr == "raises"
    expected = call.args[0] if (is_raises and call.args) else None
    return expected.id if isinstance(expected, ast.Name) else None


def _blind_exception_assertions(
    tests_dir: Path, trees: Mapping[Path, ast.Module] | None = None
) -> list[str]:
    """Report every `file:line` in the suite that expects a root exception type."""
    sites: list[str] = []
    for path in sorted(tests_dir.rglob("test_*.py")):
        tree = trees[path] if trees and path in trees else parse_python_file(path)
        sites.extend(
            f"{path.name}:{node.lineno}"
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and _expected_exception_name(node) in CONST_BLIND_EXCEPTION_TYPES
        )
    return sites


def _is_bool_literal(node: ast.AST) -> bool:
    return isinstance(node, ast.Constant) and isinstance(node.value, bool)


def _is_presence_call(node: ast.AST) -> bool:
    if not isinstance(node, ast.Call):
        return False
    if isinstance(node.func, ast.Name):
        return node.func.id in CONST_PRESENCE_CHECK_NAMES
    if isinstance(node.func, ast.Attribute):
        return node.func.attr in CONST_PRESENCE_CHECK_NAMES
    return False


def _is_opaque_tuple_assert(node: ast.Assert) -> bool:
    if not isinstance(node.test, ast.Compare):
        return False
    cmp = node.test
    if len(cmp.ops) != 1 or not isinstance(cmp.ops[0], ast.Eq):
        return False
    left, right = cmp.left, cmp.comparators[0]
    if isinstance(left, (ast.Tuple, ast.List)) and isinstance(right, (ast.Tuple, ast.List)):
        for el_l, el_r in zip(left.elts, right.elts, strict=False):
            for el, other in [(el_l, el_r), (el_r, el_l)]:
                if _is_presence_call(el) and _is_bool_literal(other):
                    return True
    return False


def _is_none_comparison(test: ast.Compare) -> bool:
    if len(test.ops) != 1 or not isinstance(test.ops[0], (ast.IsNot, ast.NotEq)):
        return False
    left, right = test.left, test.comparators[0]
    return (isinstance(right, ast.Constant) and right.value is None) or (
        isinstance(left, ast.Constant) and left.value is None
    )


def _is_presence_bool_comparison(test: ast.Compare) -> bool:
    if len(test.ops) != 1:
        return False
    left, right = test.left, test.comparators[0]
    for el, other in [(left, right), (right, left)]:
        if _is_presence_call(el) and _is_bool_literal(other):
            return True
    return False


def _is_presence_pair(elt_a: ast.expr, elt_b: ast.expr) -> bool:
    for el, other in [(elt_a, elt_b), (elt_b, elt_a)]:
        if _is_presence_call(el) and _is_bool_literal(other):
            return True
        if isinstance(el, ast.Compare) and _is_none_comparison(el) and _is_bool_literal(other):
            return True
    return False


def _is_all_presence_tuple_comparison(test: ast.Compare) -> bool:
    if len(test.ops) != 1 or not isinstance(test.ops[0], ast.Eq):
        return False
    left, right = test.left, test.comparators[0]
    if not (isinstance(left, (ast.Tuple, ast.List)) and isinstance(right, (ast.Tuple, ast.List))):
        return False
    if len(left.elts) == 0 or len(left.elts) != len(right.elts):
        return False
    return all(
        _is_presence_pair(elt_a, elt_b) for elt_a, elt_b in zip(left.elts, right.elts, strict=False)
    )


def _is_presence_check(node: ast.Assert) -> bool:
    test = node.test
    if isinstance(test, ast.Compare):
        return (
            _is_none_comparison(test)
            or _is_presence_bool_comparison(test)
            or _is_all_presence_tuple_comparison(test)
        )
    return _is_presence_call(test) or isinstance(test, (ast.Name, ast.Attribute))


def _classify_test_node(
    item: ast.AST,
    test_funcs: list[ast.FunctionDef | ast.AsyncFunctionDef],
    same_module_helpers: set[str],
) -> None:
    if not isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
        return
    if item.name.startswith("test_"):
        test_funcs.append(item)
        return
    if any(isinstance(c, ast.Assert) for c in ast.walk(item)):
        same_module_helpers.add(item.name)


def _collect_test_funcs_and_helpers(
    tree: ast.Module,
) -> tuple[list[ast.FunctionDef | ast.AsyncFunctionDef], set[str]]:
    test_funcs: list[ast.FunctionDef | ast.AsyncFunctionDef] = []
    same_module_helpers: set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            for item in node.body:
                _classify_test_node(item, test_funcs, same_module_helpers)
        else:
            _classify_test_node(node, test_funcs, same_module_helpers)
    return test_funcs, same_module_helpers


def _scan_test_function(
    path_name: str,
    fn: ast.FunctionDef | ast.AsyncFunctionDef,
    same_module_helpers: set[str],
) -> list[str]:
    sites: list[str] = []
    fn_asserts: list[ast.Assert] = []
    delegates = False
    for c in ast.walk(fn):
        if isinstance(c, ast.Assert):
            fn_asserts.append(c)
        elif (
            not delegates
            and isinstance(c, ast.Call)
            and isinstance(c.func, ast.Name)
            and c.func.id in same_module_helpers
        ):
            delegates = True
    for a in fn_asserts:
        if _is_opaque_tuple_assert(a):
            sites.append(f"{path_name}:{a.lineno}")
    if fn_asserts and not delegates and all(_is_presence_check(a) for a in fn_asserts):
        for a in fn_asserts:
            sites.append(f"{path_name}:{a.lineno}")
    return sites


def _opaque_or_presence_assertions(
    tests_dir: Path, trees: Mapping[Path, ast.Module] | None = None
) -> list[str]:
    """Report every `file:line` of an opaque tuple assert or presence-only test in `tests/`."""
    sites: set[str] = set()
    test_paths = (
        [p for p in trees.keys() if p.name.startswith("test_") and p.name.endswith(".py")]
        if trees
        else sorted(tests_dir.rglob("test_*.py"))
    )
    for path in sorted(test_paths):
        tree = trees[path] if trees and path in trees else parse_python_file(path)
        test_funcs, helpers = _collect_test_funcs_and_helpers(tree)
        for fn in test_funcs:
            sites.update(_scan_test_function(path.name, fn, helpers))
    return sorted(sites, key=lambda s: (s.split(":")[0], int(s.split(":")[1])))


def check_no_test_certifies_a_failure_without_checking_it(
    parsed_test_trees: dict[Path, ast.Module],
) -> None:
    """A test must specify expected failures and test values or object identity.

    `pytest.raises(Exception)` is satisfied by an unrelated `TypeError`.
    A test whose assertions check only presence or hide presence calls in tuple equality
    certifies an object exists without verifying its values or behavior.
    Neither defect is visible in review.
    Ruff rules and AST invariant checks prevent these defects.
    """
    config = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    lint = config["tool"]["ruff"]["lint"]
    unenforced = sorted(
        rule
        for rule in CONST_TEST_ASSERTION_LINT_RULES
        if not ruff_enforces(rule, lint["select"], lint.get("ignore", []))
    )

    assert (
        _blind_exception_assertions(REPO_ROOT / "tests", trees=parsed_test_trees),
        _opaque_or_presence_assertions(REPO_ROOT / "tests", trees=parsed_test_trees),
        unenforced,
    ) == ([], [], [])


def check_opaque_and_presence_assertions_fixtures(tmp_path: Path) -> None:
    """The presence and opaque tuple assert invariant reports file:line on acceptance fixtures."""
    code = (
        "def _helper_with_assert() -> None:\n"
        "    assert 1 == 1\n"
        "\n"
        "def test_only_is_not_none() -> None:\n"
        "    assert x is not None\n"
        "\n"
        "def test_only_bare_truthiness() -> None:\n"
        "    assert x\n"
        "\n"
        "def test_only_opaque_tuple() -> None:\n"
        "    assert (isinstance(x, Y),) == (True,)\n"
        "\n"
        "def test_delegates_to_helper() -> None:\n"
        "    _helper_with_assert()\n"
        "\n"
        "def test_does_not_raise() -> None:\n"
        "    pass\n"
        "\n"
        "def test_valid_checks() -> None:\n"
        "    assert x is not None\n"
        "    assert x.value == 42\n"
    )
    test_file = tmp_path / "test_fixtures.py"
    test_file.write_text(code, encoding="utf-8")
    violations = _opaque_or_presence_assertions(tmp_path)
    assert violations == [
        "test_fixtures.py:5",
        "test_fixtures.py:8",
        "test_fixtures.py:11",
    ]
