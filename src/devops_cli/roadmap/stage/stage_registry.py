"""The registry and ratchet declarations of the test suite (#3254).

Each test module declares the counted items that it tests in a module-level `REGISTRY_COUNTS`
tuple of literals. The table builder reads the declarations with `ast` and never imports a test
module.
"""

from __future__ import annotations

import ast
import re
from collections.abc import Sequence
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Final

_TARGET_CONSTANT: Final[str] = "REGISTRY_COUNTS"
_TESTS_DIRECTORY: Final[str] = "tests"
_TEST_MODULE_NAME: Final[re.Pattern[str]] = re.compile(
    r"\btests/(?:[a-zA-Z0-9_.-]+/)*[a-zA-Z0-9_.-]+\.py\b"
)


@dataclass(frozen=True)
class RegistryCount:
    """One counted registry or ratchet entry (#3254)."""

    kind: str
    token: str
    path: str
    line: int = 0
    declaring_path: str = ""


@dataclass(frozen=True)
class Declaration:
    """One module-level `REGISTRY_COUNTS` declaration of a test module (#3332).

    `entries` holds the entries that the value declares, and `problem` says why the value is no
    plain literal tuple of triples, or "" when it is one."""

    path: str
    line: int
    entries: tuple[RegistryCount, ...] = ()
    problem: str = ""

    @property
    def source(self) -> str:
        """The `path:line` of the declaration."""
        return f"{self.path}:{self.line}"


def _literal_triple(
    node: ast.expr,
) -> tuple[ast.Constant, ast.Constant, ast.Constant] | None:
    """The kind, token and path literals of one entry, or None when the node is no such triple."""
    if not isinstance(node, (ast.Tuple, ast.List)) or len(node.elts) < 3:
        return None
    first, second, third = node.elts[:3]
    if (
        isinstance(first, ast.Constant)
        and isinstance(second, ast.Constant)
        and isinstance(third, ast.Constant)
    ):
        return (first, second, third)
    return None


def _extract_entries(value_node: ast.expr, declaring_path: str) -> list[RegistryCount]:
    """Extract `RegistryCount` records from an AST tuple or list literal."""
    if not isinstance(value_node, (ast.Tuple, ast.List)):
        return []

    entries: list[RegistryCount] = []
    for elt in value_node.elts:
        triple = _literal_triple(elt)
        if triple is None:
            continue
        first, second, third = triple
        entries.append(
            RegistryCount(
                kind=str(first.value),
                token=str(second.value),
                path=str(third.value),
                line=elt.lineno,
                declaring_path=declaring_path,
            )
        )
    return entries


def _declaration_problem(value_node: ast.expr) -> str:
    """Why the value of a declaration is no plain literal tuple of triples, or "" when it is."""
    if not isinstance(value_node, (ast.Tuple, ast.List)):
        return "the value is no tuple or list of entries"
    for element in value_node.elts:
        if _literal_triple(element) is None:
            return (
                f"the entry at line {element.lineno} is no literal triple of kind, token and path"
            )
    return ""


def _declared_values(tree: ast.Module) -> list[tuple[int, ast.expr]]:
    """Each value that the module assigns to `REGISTRY_COUNTS` at its top level, with its line."""
    values: list[tuple[int, ast.expr]] = []
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == _TARGET_CONSTANT:
                    values.append((node.lineno, node.value))
        elif isinstance(node, ast.AnnAssign):
            if isinstance(node.target, ast.Name) and node.target.id == _TARGET_CONSTANT:
                if node.value is not None:
                    values.append((node.lineno, node.value))
    return values


def _declaring_source(path: Path) -> str:
    """The text of the module at `path`, or "" when the file cannot be read or its text does not
    hold `REGISTRY_COUNTS`. A module that does not hold the name declares nothing (#4509)."""
    try:
        source = path.read_text(encoding="utf-8")
    except OSError, UnicodeDecodeError:
        return ""
    return source if _TARGET_CONSTANT in source else ""


def declarations_in(path: Path) -> tuple[Declaration, ...]:
    """Parse one Python module and read each module-level `REGISTRY_COUNTS` declaration. A module
    whose text does not hold the name is not parsed."""
    source = _declaring_source(path)
    if not source:
        return ()

    try:
        tree = ast.parse(source, filename=str(path))
    except SyntaxError:
        return ()

    declaring = path.as_posix()
    return tuple(
        Declaration(
            path=declaring,
            line=line,
            entries=tuple(_extract_entries(value, declaring)),
            problem=_declaration_problem(value),
        )
        for line, value in _declared_values(tree)
    )


def counts_in(path: Path) -> tuple[RegistryCount, ...]:
    """The entries of each module-level `REGISTRY_COUNTS` declaration of one module. A module
    whose text does not hold the name is not parsed."""
    return tuple(entry for declaration in declarations_in(path) for entry in declaration.entries)


def registry_table(root: Path) -> tuple[RegistryCount, ...]:
    """Walk test modules under `root` and return all declared registry entries with their lines."""
    search_dir = root / _TESTS_DIRECTORY if (root / _TESTS_DIRECTORY).is_dir() else root
    if not search_dir.is_dir():
        return ()

    all_entries: list[RegistryCount] = []
    for file_path in sorted(search_dir.rglob("*.py")):
        if not file_path.is_file():
            continue
        entries = counts_in(file_path)
        if not entries:
            continue
        rel_path = file_path.relative_to(root).as_posix()
        all_entries.extend(replace(entry, declaring_path=rel_path) for entry in entries)

    return tuple(sorted(all_entries, key=lambda item: (item.declaring_path, item.line, item.token)))


def matches(
    table: Sequence[RegistryCount],
    texts: Sequence[str],
    paths: Sequence[str],
) -> list[RegistryCount]:
    """Return each entry whose token appears in `texts` or in `paths`, with `path:line`."""
    matched: list[RegistryCount] = []
    seen: set[tuple[str, int, str]] = set()
    for entry in table:
        if any(entry.token in text for text in texts) or any(entry.token in path for path in paths):
            key = (entry.declaring_path, entry.line, entry.token)
            if key not in seen:
                seen.add(key)
                matched.append(entry)
    return matched


def missing_test_paths(
    root: Path | Any,
    texts: Sequence[str],
) -> list[str]:
    """Read the test module names of each text, keep the ones that name no file of the commit,
    and return them sorted."""
    found: set[str] = set()
    for text in texts:
        for match in _TEST_MODULE_NAME.finditer(text):
            path = match.group(0)
            if hasattr(root, "has") and callable(root.has):
                exists = bool(root.has(path))
            elif isinstance(root, Path):
                exists = (root / path).is_file()
            else:
                exists = path in root
            if not exists:
                found.add(path)
    return sorted(found)
