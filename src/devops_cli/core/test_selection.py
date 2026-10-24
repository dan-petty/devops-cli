"""Map changed source files to the test modules that exercise them.

`devops ci test <paths>` narrows a run to the tests that cover the given files, so a person
or an agent checks a change quickly before the full gate runs.

Selection deliberately errs toward running too much: an extra test module costs seconds,
whereas missing the one test that covers a change gives a false green.
"""

from __future__ import annotations

import ast
import re
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from functools import cached_property, partial
from pathlib import Path

from devops_cli.config.constants import (
    CONST_CONFTEST_FILENAME,
    CONST_FULL_RUN_TRIGGER_NAMES,
    CONST_PYTEST_FIXTURE_NAME,
    CONST_PYTEST_HOOK_PREFIX,
    CONST_PYTHON_FILE_SUFFIX,
    CONST_SOURCE_ROOT_DIR,
    CONST_TEST_FILE_PREFIX,
    CONST_TESTS_ROOT_DIR,
)
from devops_cli.core.import_graph import build_import_graph, module_name


@dataclass
class TestSelection:
    """The outcome of mapping changed sources to their covering tests."""

    test_files: list[Path] = field(default_factory=list)
    mapped_sources: dict[str, list[str]] = field(default_factory=dict)
    unmapped_sources: list[str] = field(default_factory=list)
    passthrough_files: list[Path] = field(default_factory=list)
    source_selectors: dict[str, str] = field(default_factory=dict)

    @property
    def has_selection(self) -> bool:
        """Report whether anything was selected to run."""
        return bool(self.test_files or self.passthrough_files)

    def pytest_targets(self) -> list[str]:
        """Return the deduplicated pytest path arguments, in stable order."""
        ordered = dict.fromkeys(
            [str(path) for path in self.passthrough_files] + [str(p) for p in self.test_files]
        )
        return sorted(ordered)


def module_path_for_source(source: Path, repo_root: Path) -> str | None:
    """Derive the importable dotted module path for a file under the source root.

    Returns ``None`` for files outside the source tree or that are not Python modules.
    """
    try:
        relative = source.resolve().relative_to((repo_root / CONST_SOURCE_ROOT_DIR).resolve())
    except ValueError, OSError:
        return None
    if relative.suffix != CONST_PYTHON_FILE_SUFFIX:
        return None

    parts = list(relative.parts)
    if parts[-1] == f"__init__{CONST_PYTHON_FILE_SUFFIX}":
        parts.pop()
    else:
        parts[-1] = relative.stem
    return ".".join(parts) if parts else None


def _convention_candidates(module_path: str) -> set[str]:
    """Build the conventional test file names for a module.

    Mirrors how this suite is laid out: `devops_cli.security.secrets` is covered by
    `test_secrets.py`, `test_security_secrets.py`, or the broader `test_security.py`.
    """
    parts = module_path.split(".")[1:]  # Drop the top-level package name.
    if not parts:
        return set()

    names = {parts[-1]}
    if len(parts) >= 2:
        names.add(f"{parts[-2]}_{parts[-1]}")
        names.add(parts[-2])
    return {f"{CONST_TEST_FILE_PREFIX}{name}{CONST_PYTHON_FILE_SUFFIX}" for name in names}


def _reference_pattern(module_path: str) -> re.Pattern[str]:
    """Build a pattern matching any import of a module, dotted or from-import."""
    escaped = re.escape(module_path)
    package, _, leaf = module_path.rpartition(".")
    alternatives = [rf"\b{escaped}\b"]
    if package:
        alternatives.append(
            rf"from\s+{re.escape(package)}\s+import\s+\(?[^)\n]*\b{re.escape(leaf)}\b"
        )
    return re.compile("|".join(alternatives))


def _fixture_reach(rel_tests_path: Path, holds_tests: Callable[[Path], bool]) -> Path | None:
    """The tests a change to a file under the tests root reaches without being imported: its own
    directory for a conftest, whose fixtures reach every test beside and below it, and for a
    package's `__init__.py`, which each test module in the package runs first, when a test
    module lies there: a package that holds none, as a support package, is classified as a
    helper, since pytest collects nothing from its directory; None for any other file."""
    name = rel_tests_path.name
    if name == CONST_CONFTEST_FILENAME:
        return rel_tests_path.parent
    is_package_init = name == f"__init__{CONST_PYTHON_FILE_SUFFIX}"
    if is_package_init and holds_tests(rel_tests_path.parent):
        return rel_tests_path.parent
    return None


def _bound_names(tree: ast.Module) -> list[str]:
    """Every name the module binds by a definition, an import or an assignment, at any depth,
    `*` for a star import, whose names cannot be known; a superset of its module-level names."""
    names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
            names.append(node.name)
        elif isinstance(node, ast.alias):
            names.append(node.asname or node.name.split(".")[0])
        elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
            names.append(node.id)
    return names


def _binds_pytest_name(tree: ast.Module) -> bool:
    """Whether the module binds a name pytest reads as a hook, defined or imported, or imports
    `*`, whose names cannot be known."""
    return any(
        name == "*" or name.startswith(CONST_PYTEST_HOOK_PREFIX) for name in _bound_names(tree)
    )


def _parse(path: Path) -> ast.Module | None:
    """The module at `path`, or None when it cannot be read or parsed, as a deleted one cannot."""
    try:
        return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except OSError, SyntaxError, ValueError:
        return None


def _binds_hook(conftest: Path) -> bool:
    """Whether the conftest binds a name pytest reads as a hook, which it calls for every test;
    true when it cannot be read or parsed, so a change errs toward the whole suite."""
    tree = _parse(conftest)
    return tree is None or _binds_pytest_name(tree)


def _names_the_fixture_decorator(node: ast.AST) -> bool:
    """Whether a node names pytest's fixture decorator: `pytest.fixture`, or the name imported by
    `from pytest import fixture`; a docstring or a variable that holds a fixture file does not."""
    match node:
        case ast.Attribute(attr=name) | ast.alias(name=name):
            return name == CONST_PYTEST_FIXTURE_NAME
    return False


def _names_a_fixture_or_hook(tree: ast.Module) -> bool:
    """Whether the module names pytest's fixture decorator or binds a `pytest_*` name."""
    return _binds_pytest_name(tree) or any(map(_names_the_fixture_decorator, ast.walk(tree)))


def defines_fixture_or_hook(path: Path) -> bool:
    """Whether the module at `path` names pytest's fixture decorator or binds a `pytest_*` name,
    by which `SuiteImports` takes a plugin to reach every test; true when it cannot be read or
    parsed. The support registration holds every module it registers to this, so a fixture or
    hook that pytest finds and this cannot see fails the run (#1312)."""
    tree = _parse(path)
    return tree is None or _names_a_fixture_or_hook(tree)


def _reaches_every_test_itself(relative: Path, tree: ast.Module) -> bool:
    """Whether a module under the tests root reaches every test with no test importing it: a
    conftest, or a helper that defines a fixture or binds a `pytest_*` name, which pytest applies
    to every test once the helper is a plugin, as every submodule and subpackage of
    `tests.support` is, and as `pytest_plugins` or `-p` can make any other. A test module is
    never a plugin."""
    if relative.name == CONST_CONFTEST_FILENAME:
        return True
    if relative.name.startswith(CONST_TEST_FILE_PREFIX):
        return False
    return _names_a_fixture_or_hook(tree)


def _dotted(relative: Path) -> str:
    """The dotted module name of a Python file relative to the repository root."""
    return module_name(relative, Path())


def _helper_module(relative: Path) -> str | None:
    """The dotted name of a helper module: a Python file under the tests root that is neither a
    test module nor a conftest, a package's `__init__.py` included; None for any other path."""
    under_tests = relative.parts[:1] == (CONST_TESTS_ROOT_DIR,)
    if not under_tests or relative.suffix != CONST_PYTHON_FILE_SUFFIX:
        return None
    if relative.name.startswith(CONST_TEST_FILE_PREFIX) or relative.name == CONST_CONFTEST_FILENAME:
        return None
    return _dotted(relative)


def _packages_of(module: str) -> set[str]:
    """The packages whose `__init__.py` runs before the module does: `a` and `a.b` for `a.b.c`."""
    parts = module.split(".")
    return {".".join(parts[:end]) for end in range(1, len(parts))}


def _closure(seeds: Iterable[str], edges: Mapping[str, set[str]]) -> set[str]:
    """Every module reachable from `seeds` along `edges`, the seeds included."""
    reached = set(seeds)
    pending = list(reached)
    while pending:
        fresh = edges.get(pending.pop(), set()) - reached
        reached |= fresh
        pending.extend(fresh)
    return reached


@dataclass(frozen=True)
class _ParsedSuite:
    """The modules under the tests root that `ast` parsed, by dotted name with their paths
    relative to the repository root; for each, the modules that import it when they run, a
    package's own modules included; and the modules a change to which reaches every test."""

    paths: Mapping[str, Path]
    importers: Mapping[str, set[str]]
    whole_suite: frozenset[str]


def _parse_suite(root: Path) -> _ParsedSuite:
    """Parse every Python file under the tests root once and link what each imports, inside its
    functions too, since a fixture imports when it runs, and the packages each runs first."""
    trees = {
        path.relative_to(root): tree
        for path in sorted((root / CONST_TESTS_ROOT_DIR).rglob(f"*{CONST_PYTHON_FILE_SUFFIX}"))
        if (tree := _parse(path)) is not None
    }
    # Keyed relative to the root, the files name their modules from `tests` whatever the
    # checkout's directory is called.
    graph = build_import_graph(trees, root=Path(), function_bodies=True)
    paths = {_dotted(relative): relative for relative in trees}
    edges = {
        module: targets | (_packages_of(module) & paths.keys())
        for module, targets in graph.edges.items()
    }
    importers: dict[str, set[str]] = {module: set() for module in edges}
    for module, targets in edges.items():
        for target in targets:
            importers[target].add(module)
    roots = {module for module, rel in paths.items() if _reaches_every_test_itself(rel, trees[rel])}
    return _ParsedSuite(paths, importers, frozenset(_closure(roots, edges)))


class SuiteImports:
    """Which tests a change to a helper module under the tests root reaches, from what the
    modules there import when they run, read with `ast` on the first question and kept (#1312).

    Every submodule and subpackage of `tests.support` is a plugin, imported at session start;
    the package's own `__init__.py` is not. So a helper reaches every test when it defines a
    fixture or binds a `pytest_*` name, or when a conftest or such a helper imports it, or one of
    its modules, directly or through other modules. Any other helper reaches only the test
    modules that import it that way; an import-time failure in it still fails every run, since
    registration imports it. A helper `ast` cannot read, as one deleted or renamed away, reaches
    every test, since what it registered cannot be known; that holds only where the old path is
    among the changes. The registration fails a run in which pytest finds a fixture or hook that
    `defines_fixture_or_hook` does not, and a run with a test module or conftest under
    `tests.support`. An invariant holds a helper's top level and class bodies to docstrings,
    imports at the top level, defs, classes, assignments to names alone and `if TYPE_CHECKING:`
    blocks with no `else`. What still runs on import unchecked is each value bound to a name and
    each decorator, default argument, base class and metaclass, and what they do to tests that
    do not import the helper: a narrowed run does not see that, and the full gate does.
    """

    def __init__(self, repo_root: Path) -> None:
        self._root = repo_root

    def is_removed_helper(self, relative: Path) -> bool:
        """Whether `relative`, from the repository root, names a helper module whose file is
        gone, deleted or renamed away."""
        return _helper_module(relative) is not None and not (self._root / relative).exists()

    @cached_property
    def _suite(self) -> _ParsedSuite:
        return _parse_suite(self._root)

    def reaches_every_test(self, relative: Path) -> bool:
        """Whether a change to the file at `relative`, a path from the repository root, reaches
        every test through the suite's imports; false for anything not a helper module."""
        module = _helper_module(relative)
        if module is None:
            return False
        return module not in self._suite.paths or module in self._suite.whole_suite

    def importing_tests(self, relative: Path) -> list[Path]:
        """The test modules that import the helper module at `relative` when they run, directly
        or through other modules, as paths from the repository root; none for any other file."""
        module = _helper_module(relative)
        if module is None:
            return []
        suite = self._suite
        reached = _closure({module}, suite.importers) & suite.paths.keys()
        return sorted(
            path for path in map(suite.paths.__getitem__, reached) if is_test_module(path)
        )


def is_test_module(path: Path | str) -> bool:
    """Whether a path names a test module, a `test_*.py` file; the one test the selector, the
    coverage index and `devops ci test` share."""
    named = Path(path)
    return (
        named.name.startswith(CONST_TEST_FILE_PREFIX) and named.suffix == CONST_PYTHON_FILE_SUFFIX
    )


def forces_full_run(path: str, imports: SuiteImports) -> bool:
    """Whether a change to `path`, from the repository root, can alter the outcome of tests that
    never import it, so it defeats the coverage index and forces a full run: a fixture file, the
    project's dependencies or interpreter, or a helper module under the tests root that reaches
    every test (`SuiteImports`), which is read only for such a helper (#1312)."""
    relative = Path(path.replace("\\", "/"))
    return relative.name in CONST_FULL_RUN_TRIGGER_NAMES or imports.reaches_every_test(relative)


def _repo_relative(raw: Path, root: Path) -> Path | None:
    """`raw` from the repository root, or None for an absolute path outside it."""
    try:
        return raw.resolve().relative_to(root) if raw.is_absolute() else raw
    except ValueError, OSError:
        return None


def _triggers_by_name(relative: Path, root: Path) -> bool:
    """Whether a change reaches every test by what the file is: a full-run trigger name, except
    that a conftest below the tests root does so only when it binds a `pytest_*` hook, and
    otherwise reaches its own directory."""
    tests_root = Path(CONST_TESTS_ROOT_DIR)
    nested_conftest = (
        relative.name == CONST_CONFTEST_FILENAME
        and relative.parent != tests_root
        and relative.is_relative_to(tests_root)
    )
    if nested_conftest:
        return _binds_hook(root / relative)
    return relative.name in CONST_FULL_RUN_TRIGGER_NAMES


def _first_reaching_every_test(
    candidates: Sequence[Path], root: Path, imports: SuiteImports
) -> Path | None:
    """The first change that reaches every test, those that do by their name found before any
    module under the tests root is read for a helper that may reach every test by its imports."""
    relative = [
        (path, rel) for path in candidates if (rel := _repo_relative(path, root)) is not None
    ]
    by_name = (path for path, rel in relative if _triggers_by_name(rel, root))
    by_imports = (path for path, rel in relative if imports.reaches_every_test(rel))
    return next(by_name, None) or next(by_imports, None)


def _iter_test_files(tests_root: Path) -> list[Path]:
    """List every test module under the tests root."""
    if not tests_root.is_dir():
        return []
    return sorted(tests_root.rglob(f"{CONST_TEST_FILE_PREFIX}*{CONST_PYTHON_FILE_SUFFIX}"))


def _referencing_tests(
    module_path: str, test_files: Sequence[Path], contents: dict[Path, str]
) -> set[Path]:
    """Find test modules that import or reference the given module."""
    pattern = _reference_pattern(module_path)
    return {path for path in test_files if pattern.search(contents.get(path, ""))}


def _holds_tests(directory: Path, root: Path, all_tests: Sequence[Path]) -> bool:
    """Whether a test module lies in `directory`, a path from the repository root, or below it."""
    return any(path.is_relative_to(root / directory) for path in all_tests)


def _handle_test_tree_entry(
    candidate: Path,
    rel_tests_path: Path,
    root: Path,
    imports: SuiteImports,
    selection: TestSelection,
    all_tests: Sequence[Path],
) -> set[Path]:
    """Handle a candidate path under the tests root: a test module selects itself, a conftest
    or a package's `__init__.py` its directory when a test module lies there, and a helper module
    the test modules importing it, outside that directory for a package's `__init__.py`, whose
    modules all run it."""
    display = str(candidate)
    test_module = is_test_module(rel_tests_path)
    holds_tests = partial(_holds_tests, root=root, all_tests=all_tests)
    direct = _fixture_reach(rel_tests_path, holds_tests) or (
        rel_tests_path if test_module else None
    )
    importing = [
        path
        for path in imports.importing_tests(rel_tests_path)
        if direct is None or not path.is_relative_to(direct)
    ]
    if direct is not None:
        selection.passthrough_files.append(direct)
    selection.source_selectors[display] = "text-based selector" if direct is None else "direct"
    if importing:
        selection.mapped_sources[display] = [str(path) for path in importing]
    elif direct is None:
        selection.unmapped_sources.append(display)
    return {root / path for path in importing}


def select_tests_for_sources(
    paths: Iterable[Path | str], repo_root: Path | None = None
) -> TestSelection:
    """Select the test modules covering a set of changed files.

    A change that reaches every test selects the whole suite at once: one that forces a full
    `devops ci test` run by its name, found before any test module is listed or read, where a
    conftest below the tests root counts only when it binds a `pytest_*` hook, then a helper
    module under the tests root that reaches every test through the suite's imports
    (`SuiteImports`). Paths already inside the tests tree pass straight through, except that a
    conftest or a package's `__init__.py` selects its directory when a test module lies there,
    and a helper module the test modules that import it. Source modules are matched by naming convention, at any depth, and
    by which tests import them, and the union is run; a test module merely beside the module's
    own does not run, since replayed over 15 commits none such ran the module (#1312).
    """
    root = (repo_root or Path.cwd()).resolve()
    candidates = [Path(raw) for raw in paths]
    imports = SuiteImports(root)
    whole_suite = _first_reaching_every_test(candidates, root, imports)
    if whole_suite is not None:
        return TestSelection(
            passthrough_files=[Path(CONST_TESTS_ROOT_DIR)],
            source_selectors={str(whole_suite): "direct"},
        )

    tests_root = root / CONST_TESTS_ROOT_DIR
    all_tests = _iter_test_files(tests_root)
    contents: dict[Path, str] = {}

    selection = TestSelection()
    selected: set[Path] = set()

    for candidate in candidates:
        absolute = candidate if candidate.is_absolute() else root / candidate

        # A path supplied under the tests tree
        try:
            relative_to_tests = absolute.resolve().relative_to(tests_root.resolve())
        except ValueError, OSError:
            relative_to_tests = None
        if relative_to_tests is not None:
            rel_tests_path = Path(CONST_TESTS_ROOT_DIR) / relative_to_tests
            selected |= _handle_test_tree_entry(
                candidate, rel_tests_path, root, imports, selection, all_tests
            )
            continue

        module_path = module_path_for_source(absolute, root)
        if module_path is None:
            continue

        if not contents:
            contents = {
                path: path.read_text(encoding="utf-8", errors="replace") for path in all_tests
            }

        conventional = {
            path for path in all_tests if path.name in _convention_candidates(module_path)
        }
        matched = conventional | _referencing_tests(module_path, all_tests, contents)

        display = str(candidate)
        selection.source_selectors[display] = "text-based selector"
        if matched:
            selected |= matched
            selection.mapped_sources[display] = sorted(
                str(path.relative_to(root)) for path in matched
            )
        else:
            selection.unmapped_sources.append(display)

    selection.test_files = sorted(path.relative_to(root) for path in selected)
    return selection


__all__ = [
    "SuiteImports",
    "TestSelection",
    "defines_fixture_or_hook",
    "forces_full_run",
    "is_test_module",
    "module_path_for_source",
    "select_tests_for_sources",
]
