"""No module under `tests/` finds a path from its own file or imports a test module (#1312).

A module that builds a path from its own `__file__` reads another path once it moves to another
depth, and what a test module or a conftest defines belongs to it: what tests share lives in
`tests/support/`, whose modules may read `__file__`, as `tests/support/paths.py` does for the
rest. One check over every Python file under `tests/` but `tests/fixtures/` names each such read
and import as `path:line`.

The check parses every file under `tests/`, so it runs only in the full gate, `uv run devops ci`
and the pre-push hook. It lives in this module alone, which imports nothing from devops-cli and
no module under `tests/`, spells no devops-cli module's dotted name and is named for none, so no
narrowed selection over a changed source or helper module reaches it
(`tests/test_test_selection.py` checks both); a narrowed run reaches it only when given this
module, or when it runs the whole suite. It reads the repository root from pytest's `rootpath`
rather than from `tests.support.paths`, which would make every change to that module select it.
"""

from __future__ import annotations

import ast
import importlib.util
from collections.abc import Iterator, Mapping, Sequence
from fnmatch import fnmatch
from pathlib import Path

import pytest

_TESTS = Path("tests")
# The modules that may read `__file__`, and the test data, which is not code the suite imports.
_SUPPORT = _TESTS / "support"
_FIXTURES = _TESTS / "fixtures"
_CONFTEST = "conftest"


def _names_a_test_module_or_conftest(module: str, python_files: Sequence[str]) -> bool:
    """Whether a dotted module name under `tests`, or a top-level one, names a conftest or a file
    pytest collects as a test module by its `python_files` patterns."""
    package, _, leaf = module.rpartition(".")
    in_tests = not package or package.partition(".")[0] == _TESTS.name
    collected = any(fnmatch(f"{leaf}.py", pattern) for pattern in python_files)
    return in_tests and (leaf == _CONFTEST or collected)


def _submodules(base: str, names: Sequence[str], root: Path) -> Iterator[str]:
    """`X.n` for each name `from X import n` takes that may be a module: every name when `X` is
    a package under `root`, and otherwise a name whose file `X/n.py` lies there."""
    directory = root.joinpath(*base.split("."))
    package = (directory / "__init__.py").is_file()
    return (f"{base}.{name}" for name in names if package or (directory / f"{name}.py").is_file())


def _imported_modules(node: ast.Import | ast.ImportFrom, package: str, root: Path) -> Iterator[str]:
    """The modules an import may load: each name `import` lists, and for `from X import n` `X`
    and each `X.n` that may be a module, a relative `X` resolved against the importing module's
    package."""
    if isinstance(node, ast.Import):
        yield from (alias.name for alias in node.names)
        return
    base = importlib.util.resolve_name("." * node.level + (node.module or ""), package)
    yield base
    yield from _submodules(base, [alias.name for alias in node.names], root)


def _imports_a_test_module_or_conftest(
    node: ast.Import | ast.ImportFrom, package: str, root: Path, python_files: Sequence[str]
) -> bool:
    """Whether an import loads a test module or a conftest, or is a relative import past the
    top-level package, which names no module and fails when it runs."""
    try:
        modules = list(_imported_modules(node, package, root))
    except ImportError, ValueError:
        return True
    return any(_names_a_test_module_or_conftest(module, python_files) for module in modules)


def _offending_lines(
    tree: ast.Module, relative: Path, root: Path, python_files: Sequence[str]
) -> set[int]:
    """The lines of the module at `relative`, a path from `root`, that read its own `__file__`
    outside `tests/support/` or import a test module or a conftest."""
    package = ".".join(relative.parent.parts)
    may_read_its_file = relative.is_relative_to(_SUPPORT)
    lines: set[int] = set()
    for node in ast.walk(tree):
        match node:
            case ast.Name(id="__file__") if not may_read_its_file:
                lines.add(node.lineno)
            case ast.Import() | ast.ImportFrom() if _imports_a_test_module_or_conftest(
                node, package, root, python_files
            ):
                lines.add(node.lineno)
    return lines


def _violations(
    root: Path,
    python_files: Sequence[str],
    trees: Mapping[Path, ast.Module] | None = None,
) -> list[str]:
    """`path:line` of each read of a module's own `__file__` and each import of a test module or
    a conftest in the Python files under `root`'s `tests/` but `tests/fixtures/`, each parsed
    once."""
    found: list[str] = []
    if trees is not None:
        file_tree_pairs = [
            (path, tree)
            for path, tree in sorted(trees.items())
            if not path.relative_to(root).is_relative_to(_FIXTURES)
        ]
    else:
        file_tree_pairs = [
            (path, ast.parse(path.read_bytes()))
            for path in sorted((root / _TESTS).rglob("*.py"))
            if not path.relative_to(root).is_relative_to(_FIXTURES)
        ]
    for path, tree in file_tree_pairs:
        relative = path.relative_to(root)
        lines = _offending_lines(tree, relative, root, python_files)
        found.extend(f"{relative.as_posix()}:{line}" for line in sorted(lines))
    return found


def test_no_test_module_finds_a_path_from_its_own_file_or_imports_a_test_module(
    pytestconfig: pytest.Config,
    parsed_test_trees: dict[Path, ast.Module],
) -> None:
    """Every module under `tests/` reads the repository root and its test data through
    `tests.support.paths` and shares code only through `tests/support/`, so it reads the same
    paths at any depth and moves with no other edit (#1312)."""
    assert (
        _violations(
            pytestconfig.rootpath,
            pytestconfig.getini("python_files"),
            trees=parsed_test_trees,
        )
        == []
    )


# The seeded sources spell each banned form, and each devops-cli module name, in parts, so that
# a text search for them over `tests/`, or the test selector's import match, finds none here.
_OWN_FILE_PATH = "Path(" + "__file__" + ")"
_PACKAGE = "devops" + "_cli"
_SEEDED_TREE = {
    "tests/__init__.py": "",
    "tests/conftest.py": "from tests." + "test_b import Y\n",
    "tests/helpers.py": f"from pathlib import Path\n\nHERE = {_OWN_FILE_PATH}.parent\n",
    "tests/a/__init__.py": "",
    "tests/a/b/__init__.py": "",
    "tests/a/b/test_nested.py": f"from pathlib import Path\n\nHERE = {_OWN_FILE_PATH}.parent\n",
    "tests/test_a.py": "".join(
        (
            "from tests." + "conftest import X\n",
            "from tests." + "test_b import Y\n",
            "from tests import " + "conftest\n",
            "from tests." + "x_test import Y\n",
        )
    ),
    "tests/a/test_c.py": "".join(
        (
            "from ." + "test_d import Z\n",
            "from . import " + "conftest\n",
            "from .sub." + "test_x import Y\n",
        )
    ),
    "tests/test_e.py": "import " + "conftest\n" + "from .. import " + "helpers\n",
    "tests/test_f.py": "import os\n\nHERE = os.path.dirname(" + "__file__" + ")\n",
    "tests/support/__init__.py": "",
    "tests/support/builders.py": "def repo_under_test() -> None: ...\n",
    "tests/support/paths.py": f"from pathlib import Path\n\nROOT = {_OWN_FILE_PATH}.parent\n",
    "tests/test_allowed.py": (
        "import tests\n"
        f"from {_PACKAGE}.commands.test_cmd import app\n"
        f"from {_PACKAGE}.core.test_selection import select_tests_for_sources\n"
        f"from {_PACKAGE}.ai import test_gen\n"
        "from tests.support.builders import make_finding, repo_under_test\n\n"
        "ROOT = tests.__file__\n"
    ),
    "tests/fixtures/sample/test_sample.py": "import " + "conftest\n",
}


def test_a_path_from_its_own_file_and_an_import_of_a_test_module_are_named_with_path_and_line(
    tmp_path: Path, pytestconfig: pytest.Config
) -> None:
    """Each planted read of a module's own `__file__`, with `Path` or without, and each import of
    a test module or a conftest, by either `python_files` pattern and relative ones included, is
    named as `path:line`, in a conftest and a helper as in a test module, and so is a relative
    import past the top-level package. `__file__` under `tests/support/`, a module's `__file__`
    attribute, an import of a devops-cli module whose name starts `test_`, a name imported from a
    plain support module, though it ends `_test`, and anything under `tests/fixtures/` are not
    (#1312)."""
    for relative, text in _SEEDED_TREE.items():
        (tmp_path / relative).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / relative).write_text(text, encoding="utf-8")
    assert _violations(tmp_path, pytestconfig.getini("python_files")) == [
        "tests/a/b/test_nested.py:3",
        "tests/a/test_c.py:1",
        "tests/a/test_c.py:2",
        "tests/a/test_c.py:3",
        "tests/conftest.py:1",
        "tests/helpers.py:3",
        "tests/test_a.py:1",
        "tests/test_a.py:2",
        "tests/test_a.py:3",
        "tests/test_a.py:4",
        "tests/test_e.py:1",
        "tests/test_e.py:2",
        "tests/test_f.py:3",
    ]
