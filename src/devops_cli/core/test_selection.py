"""Map changed source files to the test modules that exercise them.

Pre-commit hands a hook the list of staged files. Running the whole suite for a one-line
change is the reason people start passing `--no-verify`, so this narrows the run to the
tests that actually cover the changed sources.

Selection deliberately errs toward running too much: an extra test module costs seconds,
whereas missing the one test that covers a change gives a false green.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from pathlib import Path

from devops_cli.config.constants import (
    CONST_PYTHON_FILE_SUFFIX,
    CONST_SOURCE_ROOT_DIR,
    CONST_TEST_FILE_PREFIX,
    CONST_TESTS_ROOT_DIR,
)
from devops_cli.core.coverage_index import _find_tests_importing_helper


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


def _handle_test_tree_entry(
    candidate: Path,
    rel_tests_path: Path,
    root: Path,
    all_tests: Sequence[Path],
    selection: TestSelection,
) -> set[Path]:
    """Handle a candidate path located under the tests/ directory."""
    display = str(candidate)
    name = rel_tests_path.name
    if name.startswith(CONST_TEST_FILE_PREFIX) and name.endswith(CONST_PYTHON_FILE_SUFFIX):
        selection.passthrough_files.append(rel_tests_path)
        selection.source_selectors[display] = "direct"
        return set()
    selection.source_selectors[display] = "text-based selector"
    if name == "conftest.py" or not name.endswith(CONST_PYTHON_FILE_SUFFIX):
        selection.unmapped_sources.append(display)
        return set()
    known_tests = [str(p.relative_to(root)) for p in all_tests]
    importing = _find_tests_importing_helper(rel_tests_path.as_posix(), root, known_tests)
    if importing:
        selection.mapped_sources[display] = sorted(importing)
        return {root / imp for imp in importing}
    selection.unmapped_sources.append(display)
    return set()


def select_tests_for_sources(
    paths: Iterable[Path | str], repo_root: Path | None = None
) -> TestSelection:
    """Select the test modules covering a set of changed files.

    Paths already inside the tests tree pass straight through. Source modules are matched
    both by naming convention and by which tests import them, and the union is run.
    """
    root = (repo_root or Path.cwd()).resolve()
    tests_root = root / CONST_TESTS_ROOT_DIR
    all_tests = _iter_test_files(tests_root)
    contents: dict[Path, str] = {}

    selection = TestSelection()
    selected: set[Path] = set()

    for raw in paths:
        candidate = Path(raw)
        absolute = candidate if candidate.is_absolute() else root / candidate

        # A path supplied under the tests tree
        try:
            relative_to_tests = absolute.resolve().relative_to(tests_root.resolve())
        except ValueError, OSError:
            relative_to_tests = None
        if relative_to_tests is not None:
            rel_tests_path = Path(CONST_TESTS_ROOT_DIR) / relative_to_tests
            selected |= _handle_test_tree_entry(
                candidate, rel_tests_path, root, all_tests, selection
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
    "TestSelection",
    "module_path_for_source",
    "select_tests_for_sources",
]
