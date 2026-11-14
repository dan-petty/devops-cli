"""The registry audit of a test tree (#3332).

`audit_registries` reads each test module with `ast` and imports none. It lists the entries of
the module-level `REGISTRY_COUNTS` declarations, reports a declaration whose value is not a
tuple of literal triples, and reports a ratchet assertion that no declared entry of its own
module covers: a `len(<name>) == <int>` assertion on an upper-case constant or a module-level
name, or a tuple of upper-case constant names compared with a tuple of plain integers.
"""

from __future__ import annotations

import ast
import re
from collections.abc import Iterator
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Final, TypeGuard

from devops_cli.roadmap.stage.stage_registry import RegistryCount, declarations_in

CONST_SEVERITY_ERROR: Final[str] = "error"
CONST_SEVERITY_WARNING: Final[str] = "warning"

_FINDING_INVALID: Final[str] = "The REGISTRY_COUNTS declaration is not a tuple of literal triples."
_FINDING_LENGTH: Final[str] = (
    "A length ratchet counts {names} and no REGISTRY_COUNTS entry of this module covers it."
)
_FINDING_LIMITS: Final[str] = (
    "A limit tuple counts {names} and no REGISTRY_COUNTS entry of this module covers it."
)
_TESTS_DIRECTORY: Final[str] = "tests"
_UPPER_NAME: Final[re.Pattern[str]] = re.compile(r"[A-Z][A-Z0-9_]*")


@dataclass(frozen=True)
class RegistryFinding:
    """One finding of the audit: an invalid declaration or an uncovered ratchet assertion."""

    severity: str
    path: str
    line: int
    message: str

    @property
    def location(self) -> str:
        """The `path:line` of the finding."""
        return f"{self.path}:{self.line}"


@dataclass(frozen=True)
class RegistryAudit:
    """The result of one audit: the declared entries, the count of valid declarations and the
    findings."""

    entries: tuple[RegistryCount, ...]
    declarations: int
    findings: tuple[RegistryFinding, ...]


def _is_upper(name: str) -> bool:
    """Whether `name` is an upper-case constant name."""
    return _UPPER_NAME.fullmatch(name) is not None


def _is_plain_int(node: ast.expr) -> bool:
    """Whether `node` is a literal integer."""
    return (
        isinstance(node, ast.Constant)
        and isinstance(node.value, int)
        and not isinstance(node.value, bool)
    )


def _bound_names(target: ast.expr) -> Iterator[str]:
    """Each name that one assignment target binds."""
    if isinstance(target, ast.Name):
        yield target.id
    elif isinstance(target, (ast.Tuple, ast.List)):
        for element in target.elts:
            yield from _bound_names(element)


def _module_level_names(tree: ast.Module) -> set[str]:
    """Each name that the module binds at its top level: an assignment or an import."""
    names: set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                names.update(_bound_names(target))
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names.add(node.target.id)
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            for alias in node.names:
                names.add((alias.asname or alias.name).split(".")[0])
    return names


def _covers(entries: tuple[RegistryCount, ...], name: str) -> bool:
    """An entry covers `name` when its token equals the name, or its kind is `prefix` and the
    name starts with the token."""
    return any(
        entry.token == name or (entry.kind == "prefix" and name.startswith(entry.token))
        for entry in entries
    )


def _length_names(compare: ast.Compare, module_names: set[str]) -> tuple[str, ...]:
    """The counted name of a `len(<name>) == <int>` assertion on an upper-case constant or a
    module-level name, or an empty tuple for another assertion."""
    if (
        len(compare.ops) != 1
        or not isinstance(compare.ops[0], ast.Eq)
        or len(compare.comparators) != 1
        or not _is_plain_int(compare.comparators[0])
    ):
        return ()
    call = compare.left
    if (
        not isinstance(call, ast.Call)
        or not isinstance(call.func, ast.Name)
        or call.func.id != "len"
        or call.keywords
        or len(call.args) != 1
        or not isinstance(call.args[0], ast.Name)
    ):
        return ()
    name = call.args[0].id
    if not (_is_upper(name) or name in module_names):
        return ()
    return (name,)


def _is_name_tuple(node: ast.expr) -> TypeGuard[ast.Tuple]:
    """Whether `node` is a non-empty tuple of upper-case constant names."""
    return (
        isinstance(node, ast.Tuple)
        and bool(node.elts)
        and all(isinstance(element, ast.Name) and _is_upper(element.id) for element in node.elts)
    )


def _is_int_tuple(node: ast.expr) -> bool:
    """Whether `node` is a non-empty tuple of literal integers."""
    return isinstance(node, ast.Tuple) and bool(node.elts) and all(map(_is_plain_int, node.elts))


def _limit_names(compare: ast.Compare) -> tuple[str, ...]:
    """The names of a tuple of upper-case constant names compared with a tuple of plain
    integers, in either order, or an empty tuple for another assertion."""
    if (
        len(compare.ops) != 1
        or not isinstance(compare.ops[0], ast.Eq)
        or len(compare.comparators) != 1
    ):
        return ()
    left, right = compare.left, compare.comparators[0]
    for name_side, int_side in ((left, right), (right, left)):
        if _is_name_tuple(name_side) and _is_int_tuple(int_side):
            return tuple(element.id for element in name_side.elts if isinstance(element, ast.Name))
    return ()


def _ratchet_assertions(
    tree: ast.Module,
    module_names: set[str],
) -> Iterator[tuple[int, tuple[str, ...], str]]:
    """Each ratchet assertion of the tree: its line, the names it counts and the message of a
    finding on it."""
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assert) or not isinstance(node.test, ast.Compare):
            continue
        names = _length_names(node.test, module_names)
        if names:
            yield node.lineno, names, _FINDING_LENGTH
            continue
        names = _limit_names(node.test)
        if names:
            yield node.lineno, names, _FINDING_LIMITS


def _ratchet_findings(
    path: Path,
    relative: str,
    entries: tuple[RegistryCount, ...],
) -> Iterator[RegistryFinding]:
    """The ratchet findings of one module: each assertion that no entry of the module covers.
    A module that cannot be read or parsed reports nothing."""
    try:
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))
    except OSError, UnicodeDecodeError, SyntaxError:
        return
    module_names = _module_level_names(tree)
    for line, names, message in _ratchet_assertions(tree, module_names):
        uncovered = [name for name in names if not _covers(entries, name)]
        if uncovered:
            yield RegistryFinding(
                severity=CONST_SEVERITY_WARNING,
                path=relative,
                line=line,
                message=message.format(names=", ".join(uncovered)),
            )


def audit_registries(root: Path) -> RegistryAudit:
    """Audit each Python module under `<root>/tests`, or under `root` when it holds no `tests`
    folder: list the declared entries with their source, count the valid declarations and report
    each finding. The audit reads the modules with `ast` and imports none."""
    search_dir = root / _TESTS_DIRECTORY if (root / _TESTS_DIRECTORY).is_dir() else root
    if not search_dir.is_dir():
        return RegistryAudit(entries=(), declarations=0, findings=())

    entries: list[RegistryCount] = []
    findings: list[RegistryFinding] = []
    declarations = 0
    for file_path in sorted(search_dir.rglob("*.py")):
        if not file_path.is_file():
            continue
        relative = file_path.relative_to(root).as_posix()
        module_entries: list[RegistryCount] = []
        for declaration in declarations_in(file_path):
            if declaration.valid:
                declarations += 1
                module_entries.extend(declaration.entries)
            else:
                findings.append(
                    RegistryFinding(
                        severity=CONST_SEVERITY_ERROR,
                        path=relative,
                        line=declaration.line,
                        message=_FINDING_INVALID,
                    )
                )
        entries.extend(replace(entry, declaring_path=relative) for entry in module_entries)
        findings.extend(_ratchet_findings(file_path, relative, tuple(module_entries)))

    ordered = tuple(sorted(entries, key=lambda item: (item.declaring_path, item.line, item.token)))
    return RegistryAudit(entries=ordered, declarations=declarations, findings=tuple(findings))
