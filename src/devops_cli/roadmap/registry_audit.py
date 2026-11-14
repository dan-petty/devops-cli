"""The registry audit of the test suite (#3332).

The `devops roadmap registries` command reads the module-level `REGISTRY_COUNTS` declarations of
the test modules with `ast` and imports none. It lists each declared entry, reports a declaration
whose value is not a tuple or a list of literal triples, and reports a `len(<NAME>) == <int>`
assertion and a tuple of upper-case constant names compared with a tuple of plain integers that no
declared entry of the module covers.
"""

from __future__ import annotations

import ast
import re
from collections.abc import Sequence
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Final

from devops_cli.roadmap.stage.stage_registry import (
    Declaration,
    RegistryCount,
    declarations_in,
)

_TESTS_DIRECTORY: Final[str] = "tests"
_CONSTANT_NAME: Final[re.Pattern[str]] = re.compile(r"^[A-Z][A-Z0-9_]*$")
_PREFIX_KIND: Final[str] = "prefix"

INVALID_DECLARATION: Final[str] = "invalid-declaration"
LENGTH_RATCHET: Final[str] = "length-ratchet"
LIMIT_TUPLE: Final[str] = "limit-tuple"


@dataclass(frozen=True)
class RegistryFinding:
    """One problem that the registry audit reports (#3332)."""

    kind: str
    path: str
    line: int
    message: str


@dataclass(frozen=True)
class RegistryAudit:
    """The entries and the findings of one registry audit (#3332)."""

    entries: tuple[RegistryCount, ...]
    findings: tuple[RegistryFinding, ...]
    valid_declarations: int

    @property
    def ok(self) -> bool:
        """True when the audit reports no finding."""
        return not self.findings


def _covered(entries: Sequence[RegistryCount], name: str) -> bool:
    """True when a declared entry covers `name`: its token equals the name, or its kind is
    `prefix` and the name starts with its token."""
    return any(
        entry.token == name or (entry.kind == _PREFIX_KIND and name.startswith(entry.token))
        for entry in entries
    )


def _is_int(node: ast.expr) -> bool:
    """True when `node` is an integer literal."""
    return (
        isinstance(node, ast.Constant)
        and isinstance(node.value, int)
        and not isinstance(node.value, bool)
    )


def _module_names(tree: ast.Module) -> set[str]:
    """The names that a module binds at module level, by an assignment or an import."""
    names: set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.Assign):
            names.update(t.id for t in node.targets if isinstance(t, ast.Name))
        elif isinstance(node, ast.AnnAssign):
            if isinstance(node.target, ast.Name):
                names.add(node.target.id)
        elif isinstance(node, ast.Import):
            names.update(alias.asname or alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            names.update(alias.asname or alias.name for alias in node.names)
    return names


def _module_tables(tree: ast.Module) -> set[str]:
    """The names that a module binds at module level to a tuple, list, dict or set literal."""
    tables: set[str] = set()
    for node in tree.body:
        value = getattr(node, "value", None)
        if not isinstance(value, (ast.Tuple, ast.List, ast.Dict, ast.Set)):
            continue
        if isinstance(node, ast.Assign):
            tables.update(t.id for t in node.targets if isinstance(t, ast.Name))
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            tables.add(node.target.id)
    return tables


def _is_ratchet_name(name: str, module_names: set[str], module_tables: set[str]) -> bool:
    """True when `name` is a module-level upper-case constant or a module-level table. A local
    name of a test function is no ratchet."""
    if name not in module_names:
        return False
    return bool(_CONSTANT_NAME.match(name)) or name in module_tables


def _length_name(test: ast.expr) -> str | None:
    """The name of a `len(<NAME>) == <int>` comparison, or None."""
    if not isinstance(test, ast.Compare) or len(test.ops) != 1 or len(test.comparators) != 1:
        return None
    if not isinstance(test.ops[0], ast.Eq):
        return None
    return _length_side(test.left, test.comparators[0]) or _length_side(
        test.comparators[0], test.left
    )


def _length_side(call_side: ast.expr, int_side: ast.expr) -> str | None:
    """The name of `len(<NAME>)` when `call_side` is that call and `int_side` is an integer."""
    if not _is_int(int_side):
        return None
    if not isinstance(call_side, ast.Call) or not isinstance(call_side.func, ast.Name):
        return None
    if call_side.func.id != "len" or len(call_side.args) != 1:
        return None
    argument = call_side.args[0]
    return argument.id if isinstance(argument, ast.Name) else None


def _limit_names(test: ast.expr) -> list[str] | None:
    """The upper-case names of a `(<NAME>, ...) == (<int>, ...)` comparison, or None."""
    if not isinstance(test, ast.Compare) or len(test.ops) != 1 or len(test.comparators) != 1:
        return None
    if not isinstance(test.ops[0], ast.Eq):
        return None
    left, right = test.left, test.comparators[0]
    names = _names_side(left) if _ints_side(right) else None
    if names is None:
        names = _names_side(right) if _ints_side(left) else None
    return names


def _names_side(node: ast.expr) -> list[str] | None:
    """The upper-case names of a non-empty tuple of plain names, or None."""
    if not isinstance(node, ast.Tuple) or not node.elts:
        return None
    names: list[str] = []
    for element in node.elts:
        if not isinstance(element, ast.Name) or not _CONSTANT_NAME.match(element.id):
            return None
        names.append(element.id)
    return names


def _ints_side(node: ast.expr) -> bool:
    """True when `node` is a non-empty tuple of integer literals."""
    return isinstance(node, ast.Tuple) and bool(node.elts) and all(_is_int(e) for e in node.elts)


def _assert_findings(
    tree: ast.Module,
    path: str,
    entries: Sequence[RegistryCount],
    module_names: set[str],
    module_tables: set[str],
) -> list[RegistryFinding]:
    """The findings of each ratchet assertion that no declared entry of the module covers."""
    findings: list[RegistryFinding] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assert):
            continue
        name = _length_name(node.test)
        if name is not None and _is_ratchet_name(name, module_names, module_tables):
            if not _covered(entries, name):
                findings.append(
                    RegistryFinding(
                        kind=LENGTH_RATCHET,
                        path=path,
                        line=node.lineno,
                        message=(
                            f"{path}:{node.lineno}: len({name}) has no REGISTRY_COUNTS entry "
                            f"for {name}."
                        ),
                    )
                )
        names = _limit_names(node.test)
        if names is not None:
            uncovered = [item for item in names if not _covered(entries, item)]
            if uncovered:
                findings.append(
                    RegistryFinding(
                        kind=LIMIT_TUPLE,
                        path=path,
                        line=node.lineno,
                        message=(
                            f"{path}:{node.lineno}: the limit tuple names "
                            f"{', '.join(uncovered)} with no REGISTRY_COUNTS entry."
                        ),
                    )
                )
    return findings


def _declaration_findings(declaration: Declaration, path: str) -> list[RegistryFinding]:
    """The finding of one declaration whose value is not a tuple or a list of literal triples."""
    if declaration.valid:
        return []
    return [
        RegistryFinding(
            kind=INVALID_DECLARATION,
            path=path,
            line=declaration.line,
            message=(
                f"{path}:{declaration.line}: the REGISTRY_COUNTS value is not a tuple or a list "
                f"of literal triples."
            ),
        )
    ]


def audit_registries(root: Path) -> RegistryAudit:
    """Read each test module under `root` with `ast` and return its entries and its findings."""
    search_dir = root / _TESTS_DIRECTORY if (root / _TESTS_DIRECTORY).is_dir() else root
    entries: list[RegistryCount] = []
    findings: list[RegistryFinding] = []
    valid_declarations = 0
    if not search_dir.is_dir():
        return RegistryAudit((), (), 0)

    for file_path in sorted(search_dir.rglob("*.py")):
        if not file_path.is_file():
            continue
        relative = file_path.relative_to(root).as_posix()
        tree = _parse(file_path)
        if tree is None:
            continue
        module_entries: list[RegistryCount] = []
        for declaration in declarations_in(file_path):
            findings.extend(_declaration_findings(declaration, relative))
            if declaration.valid:
                valid_declarations += 1
            module_entries.extend(declaration.entries)
        entries.extend(replace(entry, declaring_path=relative) for entry in module_entries)
        findings.extend(
            _assert_findings(
                tree,
                relative,
                module_entries,
                _module_names(tree),
                _module_tables(tree),
            )
        )

    ordered = tuple(sorted(entries, key=lambda item: (item.declaring_path, item.line, item.token)))
    return RegistryAudit(ordered, tuple(findings), valid_declarations)


def _parse(path: Path) -> ast.Module | None:
    """The parsed module at `path`, or None when it cannot be read or parsed."""
    try:
        source = path.read_text(encoding="utf-8")
    except OSError, UnicodeDecodeError:
        return None
    try:
        return ast.parse(source, filename=str(path))
    except SyntaxError:
        return None


def entry_rows(audit: RegistryAudit) -> list[list[str]]:
    """The table rows of the declared entries, each with its source `path:line`."""
    return [
        [entry.token, entry.kind, entry.path, f"{entry.declaring_path}:{entry.line}"]
        for entry in audit.entries
    ]


def entry_payload(audit: RegistryAudit) -> list[dict[str, object]]:
    """The JSON objects of the declared entries, each with its source `path:line`."""
    return [
        {
            "token": entry.token,
            "kind": entry.kind,
            "target": entry.path,
            "source": f"{entry.declaring_path}:{entry.line}",
        }
        for entry in audit.entries
    ]
