"""The audit of the test registry declarations (#3332).

The stage plan reads the module-level `REGISTRY_COUNTS` declarations of the test modules to find
the registry and ratchet entries that a plan needs. This audit lists those declarations, reports a
declaration that is no plain literal tuple of triples, and reports a ratchet assertion that no
declaration of its module covers. It reads each module with `ast` and imports none, so a module
that raises at import is still read.
"""

from __future__ import annotations

import ast
import re
from collections.abc import Iterator, Sequence
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Final

from devops_cli.roadmap.stage.stage_registry import (
    Declaration,
    RegistryCount,
    declarations_in,
)

_TESTS_DIRECTORY: Final[str] = "tests"
_CONSTANT_NAME: Final[re.Pattern[str]] = re.compile(r"[A-Z][A-Z0-9_]*")
_TABLE_CALLS: Final[frozenset[str]] = frozenset({"dict", "frozenset", "list", "set", "tuple"})
_PREFIX_KIND: Final[str] = "prefix"

_INVALID_DECLARATION: Final[str] = "invalid-declaration"
_LENGTH_ASSERTION: Final[str] = "length-assertion"
_LIMIT_TUPLE: Final[str] = "limit-tuple"
_ERROR: Final[str] = "error"
_WARNING: Final[str] = "warning"
_ASSERTION_LABELS: Final[dict[str, str]] = {
    _LENGTH_ASSERTION: "length assertion",
    _LIMIT_TUPLE: "limit tuple",
}


@dataclass(frozen=True)
class RegistryFinding:
    """One problem of the test registry declarations (#3332).

    `kind` is `invalid-declaration`, `length-assertion` or `limit-tuple`, and `severity` is `error`
    for a declaration that is no plain literal and `warning` for a ratchet assertion that no
    declaration covers."""

    kind: str
    severity: str
    path: str
    line: int
    message: str

    @property
    def source(self) -> str:
        """The `path:line` of the finding."""
        return f"{self.path}:{self.line}"


@dataclass(frozen=True)
class RegistryAudit:
    """The declarations of a test tree and the findings of its audit (#3332)."""

    declarations: tuple[Declaration, ...]
    findings: tuple[RegistryFinding, ...]

    @property
    def valid_declarations(self) -> tuple[Declaration, ...]:
        """The declarations whose value is a plain literal tuple of triples."""
        return tuple(declaration for declaration in self.declarations if not declaration.problem)

    @property
    def entries(self) -> tuple[RegistryCount, ...]:
        """Each entry of the valid declarations."""
        return tuple(
            entry for declaration in self.valid_declarations for entry in declaration.entries
        )

    @property
    def ok(self) -> bool:
        """Whether the audit reports no finding."""
        return not self.findings


def audit_registries(root: Path) -> RegistryAudit:
    """Read each module-level `REGISTRY_COUNTS` declaration of the test tree under `root` and
    report a declaration that is no plain literal and a ratchet assertion that no declaration of
    its module covers."""
    declarations: list[Declaration] = []
    findings: list[RegistryFinding] = []
    for module, declaring in _test_modules(root):
        found = tuple(_rebase(declaration, declaring) for declaration in declarations_in(module))
        declarations.extend(found)
        findings.extend(_declaration_findings(found))
        findings.extend(_assertion_findings(module, declaring, found))
    return RegistryAudit(
        declarations=tuple(declarations),
        findings=tuple(sorted(findings, key=lambda item: (item.path, item.line, item.kind))),
    )


def _test_modules(root: Path) -> list[tuple[Path, str]]:
    """Each Python module of the test tree of `root`, with its path relative to `root`."""
    search_dir = root / _TESTS_DIRECTORY if (root / _TESTS_DIRECTORY).is_dir() else root
    if not search_dir.is_dir():
        return []
    return [
        (module, module.relative_to(root).as_posix())
        for module in sorted(search_dir.rglob("*.py"))
        if module.is_file()
    ]


def _rebase(declaration: Declaration, declaring: str) -> Declaration:
    """The declaration with its path, and the path of its entries, relative to the audited root."""
    return replace(
        declaration,
        path=declaring,
        entries=tuple(replace(entry, declaring_path=declaring) for entry in declaration.entries),
    )


def _declaration_findings(declarations: Sequence[Declaration]) -> list[RegistryFinding]:
    """One error for each declaration whose value is no plain literal tuple of triples."""
    return [
        RegistryFinding(
            kind=_INVALID_DECLARATION,
            severity=_ERROR,
            path=declaration.path,
            line=declaration.line,
            message=f"REGISTRY_COUNTS is no plain literal: {declaration.problem}",
        )
        for declaration in declarations
        if declaration.problem
    ]


def _assertion_findings(
    module: Path,
    declaring: str,
    declarations: Sequence[Declaration],
) -> list[RegistryFinding]:
    """One warning for each ratchet assertion that no declaration of its module covers."""
    tree = _module_tree(module)
    if tree is None:
        return []
    entries = tuple(entry for declaration in declarations for entry in declaration.entries)
    module_names = _module_names(tree)
    findings: list[RegistryFinding] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assert):
            continue
        for names, kind in _asserted_names(node.test, module_names):
            missing = tuple(name for name in names if not _covers(entries, name))
            if missing:
                findings.append(_assertion_finding(kind, declaring, node.lineno, missing))
    return findings


def _assertion_finding(
    kind: str,
    declaring: str,
    line: int,
    names: Sequence[str],
) -> RegistryFinding:
    """The warning for one ratchet assertion that names no declared entry."""
    return RegistryFinding(
        kind=kind,
        severity=_WARNING,
        path=declaring,
        line=line,
        message=f"the {_ASSERTION_LABELS[kind]} of {', '.join(names)} has no REGISTRY_COUNTS entry",
    )


def _module_tree(path: Path) -> ast.Module | None:
    """The parsed module at `path`, or None when the file cannot be read or does not parse."""
    try:
        source = path.read_text(encoding="utf-8")
    except OSError, UnicodeDecodeError:
        return None
    try:
        return ast.parse(source, filename=str(path))
    except SyntaxError:
        return None


def _module_names(tree: ast.Module) -> frozenset[str]:
    """Each name that the module binds at its top level as an upper-case constant or as a table."""
    return frozenset(
        name
        for node in tree.body
        for name, value in _bindings(node)
        if _CONSTANT_NAME.fullmatch(name) or (value is not None and _is_table(value))
    )


def _bindings(node: ast.stmt) -> Iterator[tuple[str, ast.expr | None]]:
    """Each name that one top-level statement binds, with the value that it binds to it."""
    if isinstance(node, ast.Assign):
        for target in node.targets:
            if isinstance(target, ast.Name):
                yield target.id, node.value
    elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
        yield node.target.id, node.value


def _is_table(node: ast.expr) -> bool:
    """Whether the value is a table literal, or a call that builds one."""
    if isinstance(node, (ast.Tuple, ast.List, ast.Set, ast.Dict)):
        return True
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id in _TABLE_CALLS
    )


def _asserted_names(
    test: ast.expr,
    module_names: frozenset[str],
) -> Iterator[tuple[tuple[str, ...], str]]:
    """The names that one assertion ratchets, with the kind of the assertion."""
    if (
        not isinstance(test, ast.Compare)
        or len(test.ops) != 1
        or not isinstance(test.ops[0], ast.Eq)
    ):
        return
    left, right = test.left, test.comparators[0]
    counted = _length_name(left, right) or _length_name(right, left)
    if counted is not None:
        if counted in module_names:
            yield (counted,), _LENGTH_ASSERTION
        return
    names = _constant_names(left)
    if names and _is_integer_tuple(right, len(names)):
        yield names, _LIMIT_TUPLE


def _length_name(left: ast.expr, right: ast.expr) -> str | None:
    """The name whose length a `len(<NAME>) == <int>` comparison counts, or None."""
    if not isinstance(left, ast.Call) or not isinstance(left.func, ast.Name):
        return None
    if left.func.id != "len" or len(left.args) != 1 or left.keywords:
        return None
    counted = left.args[0]
    if not isinstance(counted, ast.Name) or not _is_integer(right):
        return None
    return counted.id


def _constant_names(node: ast.expr) -> tuple[str, ...]:
    """Each name of a tuple or list that holds only upper-case names, or () for any other node."""
    if not isinstance(node, (ast.Tuple, ast.List)) or not node.elts:
        return ()
    names: list[str] = []
    for element in node.elts:
        if not isinstance(element, ast.Name) or not _CONSTANT_NAME.fullmatch(element.id):
            return ()
        names.append(element.id)
    return tuple(names)


def _is_integer(node: ast.expr) -> bool:
    """Whether the node is a plain integer literal."""
    return (
        isinstance(node, ast.Constant)
        and isinstance(node.value, int)
        and not isinstance(node.value, bool)
    )


def _is_integer_tuple(node: ast.expr, count: int) -> bool:
    """Whether the node is a tuple or list of `count` plain integer literals."""
    if not isinstance(node, (ast.Tuple, ast.List)) or len(node.elts) != count:
        return False
    return all(_is_integer(element) for element in node.elts)


def _covers(entries: Sequence[RegistryCount], name: str) -> bool:
    """Whether a declared entry covers the name: its token is the name, or its kind is `prefix`
    and the name starts with its token."""
    return any(
        entry.token == name or (entry.kind == _PREFIX_KIND and name.startswith(entry.token))
        for entry in entries
    )
