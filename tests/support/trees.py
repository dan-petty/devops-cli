"""Shared session-scoped parsed AST trees for repository source and test files (#1749).

Each file under `src/` and `tests/` is parsed at most once per test process.
Invariant and architectural tests read from these shared representations.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

import pytest

import tests

_REPO_ROOT = Path(tests.__file__).resolve().parent.parent
_PARSED_TREES: dict[Path, ast.Module] = {}
_PARSE_COUNTS: dict[Path, int] = {}


class ParsedTreeMap(dict[Path, ast.Module]):
    """A dictionary of parsed AST modules that resolves paths on key access (#1749)."""

    def __getitem__(self, key: Path) -> ast.Module:
        try:
            return super().__getitem__(key)
        except KeyError:
            resolved = key.resolve()
            if resolved in self:
                return super().__getitem__(resolved)
            raise

    def __contains__(self, key: object) -> bool:
        if super().__contains__(key):
            return True
        if isinstance(key, Path):
            return super().__contains__(key.resolve())
        return False

    def get(self, key: Any, default: Any = None) -> Any:
        if key in self:
            return self[key]
        return default


def parse_count(path: Path) -> int:
    """Return how many times `path` has been parsed in this process (#1749)."""
    return _PARSE_COUNTS.get(path.resolve(), 0)


def parse_python_file(path: Path) -> ast.Module:
    """Return the parsed AST for `path`, parsed at most once per test process (#1749)."""
    resolved = path.resolve()
    tree = _PARSED_TREES.get(resolved)
    if tree is None:
        tree = ast.parse(resolved.read_text(encoding="utf-8"), filename=str(resolved))
        _PARSED_TREES[resolved] = tree
        _PARSE_COUNTS[resolved] = _PARSE_COUNTS.get(resolved, 0) + 1
    return tree


def parse_source_trees(repo_root: Path | None = None) -> ParsedTreeMap:
    """Parse every Python file under `src/` once per test process (#1749)."""
    root = repo_root or _REPO_ROOT
    src_dir = root / "src"
    trees: dict[Path, ast.Module] = {}
    for py_file in sorted(src_dir.rglob("*.py")):
        trees[py_file] = parse_python_file(py_file)
    return ParsedTreeMap(trees)


def parse_test_trees(repo_root: Path | None = None) -> ParsedTreeMap:
    """Parse every Python file under `tests/` once per test process (#1749)."""
    root = repo_root or _REPO_ROOT
    tests_dir = root / "tests"
    trees: dict[Path, ast.Module] = {}
    for py_file in sorted(tests_dir.rglob("*.py")):
        trees[py_file] = parse_python_file(py_file)
    return ParsedTreeMap(trees)


def parse_repo_trees(repo_root: Path | None = None) -> ParsedTreeMap:
    """Parse every Python file under `src/` and `tests/` once per test process (#1749)."""
    src_trees = parse_source_trees(repo_root)
    test_trees = parse_test_trees(repo_root)
    return ParsedTreeMap({**src_trees, **test_trees})


@pytest.fixture(scope="session")
def parsed_source_trees() -> ParsedTreeMap:
    """Session fixture providing parsed AST modules for `src/` (#1749)."""
    return parse_source_trees()


@pytest.fixture(scope="session")
def parsed_test_trees() -> ParsedTreeMap:
    """Session fixture providing parsed AST modules for `tests/` (#1749)."""
    return parse_test_trees()


@pytest.fixture(scope="session")
def parsed_repo_trees(
    parsed_source_trees: ParsedTreeMap,
    parsed_test_trees: ParsedTreeMap,
) -> ParsedTreeMap:
    """Session fixture providing parsed AST modules for `src/` and `tests/` (#1749)."""
    return ParsedTreeMap({**parsed_source_trees, **parsed_test_trees})
