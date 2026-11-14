"""The audit of the test registry declarations of a tree (#3332).

The stage planner reads module-level `REGISTRY_COUNTS` declarations with the `ast` reader in
`roadmap/stage/stage_registry.py`. This audit reuses that reader, reads each test module without
importing it, and reports a declaration whose value is not a plain literal and a ratchet assertion
that names no declared entry of its own module: a `len(<NAME>) == <int>` assertion on an
upper-case constant name or a module-level table, and a tuple of upper-case constant names
compared with a tuple of plain integers. A name covered by an entry whose kind is `prefix` and
whose token starts the name is declared.
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Final

from devops_cli.roadmap.stage.stage_registry import RegistryCount, declarations_in

_TESTS_DIRECTORY: Final[str] = "tests"
_UPPER_CASE_NAME: Final[re.Pattern[str]] = re.compile(r"^[A-Z][A-Z0-9_]*$")

KIND_INVALID_DECLARATION: Final[str] = "invalid-declaration"
KIND_MISSING_DECLARATION: Final[str] = "missing-declaration"

_INVALID_VALUE_DETAIL: Final[str] = (
    "REGISTRY_COUNTS holds a value that is not a tuple or list of literal triples."
)
_RATCHET_DETAIL: Final[str] = "The assertion {expr} names no REGISTRY_COUNTS entry for {names}."


@dataclass(frozen=True)
class RegistryFinding:
    """One audit finding: its kind, its source `path:line` and the words that name it."""

    kind: str
    path: str
    line: int
    detail: str


@dataclass(frozen=True)
class RegistryAudit:
    """The result of one audit: every declared entry of the tree and every finding."""

    entries: tuple[RegistryCount, ...] = ()
    findings: tuple[RegistryFinding, ...] = ()


def _covers(entries: tuple[RegistryCount, ...], name: str) -> bool:
    """Whether one entry declares `name`: its token equals the name, or its kind is `prefix` and
    the name starts with the token."""
    return any(
        entry.token == name or (entry.kind == "prefix" and name.startswith(entry.token))
        for entry in entries
    )


def _is_int_constant(node: ast.expr) -> bool:
    return (
        isinstance(node, ast.Constant)
        and isinstance(node.value, int)
        and not isinstance(node.value, bool)
    )


def _is_upper_name(node: ast.expr) -> bool:
    return isinstance(node, ast.Name) and bool(_UPPER_CASE_NAME.match(node.id))


def _module_level_names(tree: ast.Module) -> set[str]:
    """The names that the module assigns at module level."""
    names: set[str] = set()
    for node in tree.body:
        names.update(_bound_names(node))
    return names


def _bound_names(node: ast.AST) -> tuple[str, ...]:
    """The plain names that a binding node binds."""
    if isinstance(node, ast.Assign):
        return tuple(target.id for target in node.targets if isinstance(target, ast.Name))
    if isinstance(node, (ast.AnnAssign, ast.AugAssign)) and isinstance(node.target, ast.Name):
        return (node.target.id,)
    if isinstance(node, (ast.For, ast.AsyncFor)) and isinstance(node.target, ast.Name):
        return (node.target.id,)
    if isinstance(node, ast.NamedExpr) and isinstance(node.target, ast.Name):
        return (node.target.id,)
    if isinstance(node, ast.ExceptHandler) and node.name:
        return (node.name,)
    if isinstance(node, ast.comprehension) and isinstance(node.target, ast.Name):
        return (node.target.id,)
    return ()


def _local_names(function: ast.FunctionDef | ast.AsyncFunctionDef) -> set[str]:
    """The names that the function binds: its parameters and every name it assigns inside,
    including the functions nested in it."""
    names: set[str] = set()
    arguments = function.args
    for argument in [*arguments.posonlyargs, *arguments.args, *arguments.kwonlyargs]:
        names.add(argument.arg)
    if arguments.vararg:
        names.add(arguments.vararg.arg)
    if arguments.kwarg:
        names.add(arguments.kwarg.arg)
    for node in ast.walk(function):
        names.update(_bound_names(node))
    return names


def _uncovered_names(
    node: ast.Compare, module_names: set[str], entries: tuple[RegistryCount, ...]
) -> list[str]:
    """The ratcheted names that no entry of the module covers, or an empty list when the
    comparison is no ratchet pattern."""
    if len(node.ops) != 1 or len(node.comparators) != 1 or not isinstance(node.ops[0], ast.Eq):
        return []
    right = node.comparators[0]
    if isinstance(node.left, ast.Call):
        call = node.left
        if (
            isinstance(call.func, ast.Name)
            and call.func.id == "len"
            and len(call.args) == 1
            and not call.keywords
            and isinstance(call.args[0], ast.Name)
            and _is_int_constant(right)
        ):
            name = call.args[0].id
            if _UPPER_CASE_NAME.match(name) or name in module_names:
                return [name] if not _covers(entries, name) else []
        return []
    if (
        isinstance(node.left, ast.Tuple)
        and isinstance(right, ast.Tuple)
        and len(node.left.elts) >= 2
        and all(_is_upper_name(elt) for elt in node.left.elts)
        and all(_is_int_constant(elt) for elt in right.elts)
    ):
        names = [element.id for element in node.left.elts if isinstance(element, ast.Name)]
        return [name for name in names if not _covers(entries, name)]
    return []


class _RatchetVisitor(ast.NodeVisitor):
    """Collect the ratchet assertions of one module that no declared entry of that module covers."""

    def __init__(
        self, path: str, module_names: set[str], entries: tuple[RegistryCount, ...]
    ) -> None:
        self.path = path
        self.module_names = module_names
        self.entries = entries
        self.findings: list[RegistryFinding] = []
        self._locals: list[set[str]] = []

    def _visit_function(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        self._locals.append(_local_names(node))
        self.generic_visit(node)
        self._locals.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._visit_function(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._visit_function(node)

    def visit_Assert(self, node: ast.Assert) -> None:
        for compare in ast.walk(node.test):
            if not isinstance(compare, ast.Compare):
                continue
            uncovered = _uncovered_names(compare, self.module_names, self.entries)
            if not uncovered:
                continue
            if any(name in scope for name in uncovered for scope in self._locals):
                continue
            self.findings.append(
                RegistryFinding(
                    kind=KIND_MISSING_DECLARATION,
                    path=self.path,
                    line=compare.lineno,
                    detail=_RATCHET_DETAIL.format(
                        expr=ast.unparse(compare), names=", ".join(uncovered)
                    ),
                )
            )
        self.generic_visit(node)


def _audit_module(
    file_path: Path, rel_path: str
) -> tuple[list[RegistryCount], list[RegistryFinding]]:
    """The declared entries and the findings of one test module, read without import."""
    entries: list[RegistryCount] = []
    findings: list[RegistryFinding] = []
    for declaration in declarations_in(file_path):
        if declaration.invalid:
            findings.append(
                RegistryFinding(
                    kind=KIND_INVALID_DECLARATION,
                    path=rel_path,
                    line=declaration.line,
                    detail=_INVALID_VALUE_DETAIL,
                )
            )
        entries.extend(replace(entry, declaring_path=rel_path) for entry in declaration.entries)
    try:
        source = file_path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=rel_path)
    except OSError, UnicodeDecodeError, SyntaxError:
        return entries, findings
    visitor = _RatchetVisitor(rel_path, _module_level_names(tree), tuple(entries))
    visitor.visit(tree)
    findings.extend(visitor.findings)
    return entries, findings


def audit_registries(root: Path) -> RegistryAudit:
    """Walk each `.py` module under the tests folder of `root`, read its `REGISTRY_COUNTS`
    declarations with `ast` and import none, and report the findings of the tree."""
    search_dir = root / _TESTS_DIRECTORY if (root / _TESTS_DIRECTORY).is_dir() else root
    if not search_dir.is_dir():
        return RegistryAudit()

    entries: list[RegistryCount] = []
    findings: list[RegistryFinding] = []
    for file_path in sorted(search_dir.rglob("*.py")):
        if not file_path.is_file():
            continue
        file_entries, file_findings = _audit_module(
            file_path, file_path.relative_to(root).as_posix()
        )
        entries.extend(file_entries)
        findings.extend(file_findings)

    return RegistryAudit(
        entries=tuple(
            sorted(entries, key=lambda item: (item.declaring_path, item.line, item.token))
        ),
        findings=tuple(sorted(findings, key=lambda item: (item.path, item.line))),
    )
