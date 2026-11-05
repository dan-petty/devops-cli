"""No helper module under tests acts on import (#2164)."""

from __future__ import annotations

import ast
from collections.abc import Iterator, Mapping
from pathlib import Path

from devops_cli.config.constants import (
    CONST_CONFTEST_FILENAME,
    CONST_TEST_FILE_PREFIX,
    CONST_TESTS_ROOT_DIR,
)
from devops_cli.core.import_graph import (
    is_type_checking_guard,
)
from tests.support.paths import REPO_ROOT
from tests.support.trees import (
    parse_python_file,
)


def _binds_names_only(node: ast.stmt, *, in_class: bool) -> bool:
    """Whether a statement of a module or class body does nothing on import but bind names: a
    docstring, a def, an assignment to names alone, an `if TYPE_CHECKING:` block with no `else`,
    an import at the top level, and `pass` in a class body. A class is checked by its body."""
    match node:
        case ast.Expr(value=ast.Constant(value=str())):
            return True
        case ast.Import() | ast.ImportFrom():
            return not in_class
        case ast.Pass():
            return in_class
        case ast.FunctionDef() | ast.AsyncFunctionDef():
            return True
        case ast.Assign(targets=targets):
            return all(isinstance(target, ast.Name) for target in targets)
        case ast.AnnAssign(target=ast.Name()):
            return True
        case ast.If(test=test, orelse=[]):
            return is_type_checking_guard(test)
    return False


def _acting_statements(body: list[ast.stmt], *, in_class: bool = False) -> Iterator[ast.stmt]:
    """Each statement of a module or class body, nested class bodies included, that does more on
    import than bind names."""
    for node in body:
        if isinstance(node, ast.ClassDef):
            yield from _acting_statements(node.body, in_class=True)
        elif not _binds_names_only(node, in_class=in_class):
            yield node


def _helper_modules(tests_root: Path) -> list[Path]:
    """Every Python file under the tests root that is neither a test module nor a conftest."""
    return sorted(
        path
        for path in tests_root.rglob("*.py")
        if not path.name.startswith(CONST_TEST_FILE_PREFIX) and path.name != CONST_CONFTEST_FILENAME
    )


def _acting_on_import(root: Path, trees: Mapping[Path, ast.Module] | None = None) -> list[str]:
    """`path:line` of each statement of a helper module under `root`'s tests root, at its top
    level or in a class body, that does more on import than bind names."""
    return [
        f"{path.relative_to(root).as_posix()}:{node.lineno}"
        for path in _helper_modules(root / CONST_TESTS_ROOT_DIR)
        for node in _acting_statements(
            (trees[path] if trees and path in trees else parse_python_file(path)).body
        )
    ]


def check_no_helper_module_under_tests_acts_on_import(
    parsed_test_trees: dict[Path, ast.Module],
) -> None:
    """Registration imports every support module into every run, and any helper runs on import
    for whichever test imports it first, so the top level of a helper under `tests/`, and each
    class body in it, holds only docstrings, imports at the top level, defs, classes,
    assignments to names alone and `if TYPE_CHECKING:` blocks with no `else`; the test selector
    then reaches every test such a change can (#1312). What still runs on import unchecked is
    each value bound to a name, each decorator, default argument, base class and metaclass, and
    only the full gate catches what those do to tests that do not import the helper."""
    assert _acting_on_import(REPO_ROOT, trees=parsed_test_trees) == []


_BINDS_NAMES_ONLY = (
    '"""A helper."""\n\nimport os\nfrom typing import TYPE_CHECKING\n\nif TYPE_CHECKING:\n'
    "    import sys\n\nVALUE = 1\nCOUNT: int = 2\n"
    '"""The count."""\n\n\ndef read() -> int:\n    return VALUE\n\n\n'
    "async def wait() -> None:\n    pass\n\n\nclass Holder:\n    pass\n\n\n"
    'class Settings:\n    """Settings."""\n\n    LIMIT = 3\n    name: str = "x"\n\n'
    "    if TYPE_CHECKING:\n        size: int\n\n    def read(self) -> int:\n"
    "        return self.LIMIT\n\n    class Inner:\n        pass\n"
)


# Each form that acts on import, with the line within it that the check names.
_ACTS_ON_IMPORT = (
    ("os.getcwd()\n", 0),
    ("os.environ['HOME'] = '/'\n", 0),
    ("os.sep = '/'\n", 0),
    ("VALUE += 1\n", 0),
    ("with open('x'):\n    pass\n", 0),
    ("for item in ():\n    pass\n", 0),
    ("while False:\n    pass\n", 0),
    ("try:\n    pass\nexcept OSError:\n    pass\n", 0),
    ("match VALUE:\n    case _:\n        pass\n", 0),
    ("if VALUE:\n    pass\n", 0),
    ("if TYPE_CHECKING:\n    pass\nelse:\n    pass\n", 0),
    ("del VALUE\n", 0),
    ("global VALUE\n", 0),
    ("FIRST, SECOND = 1, 2\n", 0),
    ("class Patched:\n    LIMIT = 1\n    os.sep = '/'\n", 2),
    ("class Imports:\n    import json\n", 1),
    ("class Nested:\n    class Inner:\n        os.getcwd()\n", 2),
)


def check_a_helper_statement_that_acts_on_import_is_named_with_path_and_line(
    tmp_path: Path,
) -> None:
    """Each form that acts on import, at the top level or in a class body, is reported as
    `path:line` in a helper module, and neither the forms that only bind names nor a test
    module or conftest are (#1312)."""
    start = _BINDS_NAMES_ONLY.count("\n") + 1
    lines = [
        start + sum(form.count("\n") for form, _ in _ACTS_ON_IMPORT[:index]) + offset
        for index, (_, offset) in enumerate(_ACTS_ON_IMPORT)
    ]
    tests_root = tmp_path / CONST_TESTS_ROOT_DIR
    (tests_root / "support").mkdir(parents=True)
    (tests_root / "support" / "helper.py").write_text(
        _BINDS_NAMES_ONLY + "".join(form for form, _ in _ACTS_ON_IMPORT), encoding="utf-8"
    )
    for exempt in ("test_helper.py", CONST_CONFTEST_FILENAME):
        (tests_root / exempt).write_text("import os\n\nos.getcwd()\n", encoding="utf-8")
    assert _acting_on_import(tmp_path) == [f"tests/support/helper.py:{line}" for line in lines]
