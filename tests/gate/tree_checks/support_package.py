"""Only bootstrap imports the support package itself (#2164)."""

from __future__ import annotations

import ast
import importlib.util
from collections.abc import Mapping
from pathlib import Path

from devops_cli.config.constants import (
    CONST_TESTS_ROOT_DIR,
)
from devops_cli.core.import_graph import (
    module_name,
)
from tests.support.paths import REPO_ROOT
from tests.support.trees import (
    parse_python_file,
)

_SUPPORT_PACKAGE = "tests.support"


_SUPPORT_DIR = Path(*_SUPPORT_PACKAGE.split("."))


# The calls that import a module named by a string, which no import statement shows.
_DYNAMIC_IMPORTS = ("import_module", "__import__")


def _support_packages(root: Path) -> frozenset[str]:
    """`tests.support` and every package under it, by dotted name, from their `__init__.py`."""
    return frozenset(
        module_name(init.relative_to(root), Path())
        for init in (root / _SUPPORT_DIR).rglob("__init__.py")
    )


def _tests_aliases(tree: ast.Module) -> dict[str, str]:
    """Each name an `import` binds to a module of the tests package, with that module's dotted
    name: `import tests.x` and `import tests` bind `tests`, and `import tests.x as y` binds `y`
    to `tests.x`."""
    tests_package = _SUPPORT_PACKAGE.partition(".")[0]
    return {
        alias.asname or tests_package: alias.name if alias.asname else tests_package
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
        if alias.name.partition(".")[0] == tests_package
    }


def _imports_dynamically(func: ast.expr) -> bool:
    """Whether a call imports the module a string names: `importlib.import_module` or
    `__import__`."""
    match func:
        case ast.Attribute(attr=name) | ast.Name(id=name):
            return name in _DYNAMIC_IMPORTS
    return False


def _holds_a_support_package(
    node: ast.AST, package: str, packages: frozenset[str], aliases: dict[str, str]
) -> bool:
    """Whether a node gets hold of `tests.support` or a package under it, through which a module
    could read a module that registration loaded without importing it: by importing the package,
    by reaching it as an attribute of a name bound to the tests package, or by a dynamic import
    of anything under `tests.support`."""
    match node:
        case ast.ImportFrom(module=module, level=level, names=names):
            try:
                base = importlib.util.resolve_name("." * level + (module or ""), package)
            except ImportError, ValueError:
                return False
            return any(f"{base}.{alias.name}" in packages for alias in names)
        case ast.Import(names=names):
            return any(alias.name in packages for alias in names)
        case ast.Attribute(value=ast.Name(id=name), attr=attr):
            return name in aliases and f"{aliases[name]}.{attr}" in packages
        case ast.Call(func=func, args=[ast.Constant(value=str(target)), *_]):
            return _imports_dynamically(func) and target.startswith(_SUPPORT_PACKAGE)
    return False


def _support_package_imports(
    root: Path, exempt: Path, trees: Mapping[Path, ast.Module] | None = None
) -> list[str]:
    """`path:line` of each module under `root`'s tests root, but `exempt`, that gets hold of a
    support package; a module outside `tests/support/` is parsed only if it spells `support`,
    which every such form outside it needs."""
    packages = _support_packages(root)
    found: list[str] = []
    for path in sorted((root / CONST_TESTS_ROOT_DIR).rglob("*.py")):
        relative = path.relative_to(root)
        text = path.read_text(encoding="utf-8")
        spelled = _SUPPORT_DIR.name in text or relative.is_relative_to(_SUPPORT_DIR)
        if relative == exempt or not spelled:
            continue
        tree = trees[path] if trees and path in trees else parse_python_file(path)
        package = ".".join(relative.parent.parts)
        aliases = _tests_aliases(tree)
        found.extend(
            f"{relative.as_posix()}:{node.lineno}"
            for node in ast.walk(tree)
            if _holds_a_support_package(node, package, packages, aliases)
        )
    return sorted(found)


_BOOTSTRAP = Path(CONST_TESTS_ROOT_DIR, "support", "bootstrap.py")


def check_only_bootstrap_imports_the_support_package_itself(
    parsed_test_trees: dict[Path, ast.Module],
) -> None:
    """Registration loads every support module, so a module holding the `tests.support` package,
    or a package under it, could read one through it with no import of its own, which the test
    selector would not see. A module imports from a support module with `from tests.support[.x]
    import ...`, and only `bootstrap`, which registers them, holds a package (#1312)."""
    assert _support_package_imports(REPO_ROOT, _BOOTSTRAP, trees=parsed_test_trees) == []


def check_a_module_that_names_the_support_package_is_named_with_path_and_line(
    tmp_path: Path,
) -> None:
    """Each way to hold `tests.support` or a package under it is reported as `path:line`:
    `from tests import support`, `import tests.support`, a relative import, `support` reached
    as an attribute of `tests` under any name, a subpackage imported by name, and a dynamic
    import by `importlib.import_module` or `__import__`. An import from a support module, and
    `bootstrap`, are not (#1312)."""
    files = {
        "tests/__init__.py": "",
        "tests/support/__init__.py": "",
        "tests/support/fakes/__init__.py": "",
        "tests/support/bootstrap.py": "from tests import support\n",
        "tests/support/builders.py": "from . import fakes\n",
        "tests/test_a.py": "from tests import support\n",
        "tests/test_b.py": "import tests.support\n",
        "tests/test_c.py": "import tests\n\nFIXTURES = tests.support.paths.FIXTURES\n",
        "tests/ai/test_d.py": "from .. import support\n",
        "tests/test_alias.py": "import tests as t\n\nFIXTURES = t.support.paths.FIXTURES\n",
        "tests/test_dotted.py": (
            "import tests.support.paths\n\nFIXTURES = tests.support.paths.FIXTURES\n"
        ),
        "tests/test_fakes.py": "from tests.support import fakes\n\nSESSION = fakes.github\n",
        "tests/test_import_module.py": (
            "import importlib\n\nPATHS = importlib.import_module('tests.support.paths')\n"
        ),
        "tests/test_dunder.py": "PATHS = __import__('tests.support.paths')\n",
        "tests/test_ok.py": (
            "import tests\nfrom tests.support import paths\n"
            "from tests.support.paths import FIXTURES\n\nROOT = tests.__file__\n"
        ),
    }
    for relative, text in files.items():
        (tmp_path / relative).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / relative).write_text(text, encoding="utf-8")
    assert _support_package_imports(tmp_path, _BOOTSTRAP) == [
        "tests/ai/test_d.py:1",
        "tests/support/builders.py:1",
        "tests/test_a.py:1",
        "tests/test_alias.py:3",
        "tests/test_b.py:1",
        "tests/test_c.py:3",
        "tests/test_dotted.py:3",
        "tests/test_dunder.py:1",
        "tests/test_fakes.py:1",
        "tests/test_import_module.py:3",
    ]
