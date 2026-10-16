"""Whole-tree AST import graph, cycle detection, and interface-layer invariants (#848).

Builds module-level, non-`TYPE_CHECKING` dependency edges from parsed `ast.Module` trees using
stdlib `ast` and `graphlib` only. `from pkg import name` resolves to the submodule (`pkg.name`)
when `name` is a known submodule in the graph, and to the package (`pkg`) otherwise.

Note: String-based lazy imports (such as `importlib.import_module(...)` or lazy attribute dispatch
tables) are invisible to the static AST import graph.
"""

from __future__ import annotations

import ast
import os
from collections.abc import Collection, Iterator, Mapping, Sequence
from dataclasses import dataclass
from graphlib import CycleError, TopologicalSorter
from itertools import pairwise
from pathlib import Path

_FUNCTION_SCOPES = (ast.FunctionDef, ast.AsyncFunctionDef)
_STATEMENT_CONTAINERS = (ast.stmt, ast.excepthandler, ast.match_case)
_COMMANDS_PACKAGE = "devops_cli.commands"
_COMMANDS_PREFIX = "devops_cli.commands."
_MAIN_MODULE = "devops_cli.main"
_ROOT_PACKAGE = "devops_cli"
_INIT_FILENAME = "__init__.py"


@dataclass(frozen=True)
class ImportGraph:
    """Module-level dependency edges and the first `file:line` location for each directed edge."""

    edges: dict[str, set[str]]
    locations: dict[tuple[str, str], str]


def _infer_import_root(paths: Sequence[Path], root: Path | None) -> Path:
    """Determine the import root directory from which dotted module names are derived."""
    if not paths:
        return root or Path()
    candidate = root if root is not None else Path(os.path.commonpath(paths))
    path_set = set(paths)
    if (candidate / _INIT_FILENAME) in path_set or candidate.name == _ROOT_PACKAGE:
        return candidate.parent
    return candidate


def _module_name(path: Path, import_root: Path) -> str:
    """Convert a Python source path relative to `import_root` into its dotted module name."""
    parts = list(path.relative_to(import_root).with_suffix("").parts)
    if len(parts) > 1 and parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def _is_type_checking_guard(test: ast.expr) -> bool:
    """Return True when an `if` condition guards a `TYPE_CHECKING` block."""
    if isinstance(test, ast.Name):
        return test.id == "TYPE_CHECKING"
    if isinstance(test, ast.Attribute):
        return test.attr == "TYPE_CHECKING"
    return False


def _module_level_imports(tree: ast.Module) -> Iterator[ast.Import | ast.ImportFrom]:
    """Yield every import statement outside function bodies and `TYPE_CHECKING` blocks."""
    pending: list[ast.AST] = list(reversed(tree.body))
    while pending:
        node = pending.pop()
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            yield node
            continue
        if isinstance(node, _FUNCTION_SCOPES):
            continue
        if isinstance(node, ast.If) and _is_type_checking_guard(node.test):
            pending.extend(reversed(node.orelse))
            continue
        children = [
            child
            for child in ast.iter_child_nodes(node)
            if isinstance(child, _STATEMENT_CONTAINERS)
        ]
        pending.extend(reversed(children))


def _longest_known_module(dotted: str, known_modules: Collection[str]) -> str | None:
    """Return the longest prefix of `dotted` present in `known_modules`, or None."""
    candidate = dotted
    while candidate:
        if candidate in known_modules:
            return candidate
        if "." not in candidate:
            return None
        candidate = candidate.rsplit(".", 1)[0]
    return None


def _resolve_import_from_base(node: ast.ImportFrom, pkg_parts: Sequence[str]) -> str | None:
    """Resolve the base module path of an `ImportFrom` node using `pkg_parts` for relatives."""
    if node.level == 0:
        return node.module
    up = node.level - 1
    if up > len(pkg_parts):
        return None
    prefix = list(pkg_parts[: len(pkg_parts) - up])
    suffix = node.module.split(".") if node.module else []
    base = ".".join(prefix + suffix)
    return base or None


def _resolve_from_alias(base: str, alias_name: str, known_modules: Collection[str]) -> str | None:
    """Resolve `from <base> import <alias_name>` to the submodule when known, else the package."""
    submodule = f"{base}.{alias_name}"
    if submodule in known_modules:
        return submodule
    return _longest_known_module(base, known_modules)


def _resolve_statement_targets(
    node: ast.Import | ast.ImportFrom,
    pkg_parts: Sequence[str],
    known_modules: Collection[str],
) -> list[str]:
    """Resolve one import statement to target module names in `known_modules`."""
    if isinstance(node, ast.Import):
        return [
            target
            for alias in node.names
            if (target := _longest_known_module(alias.name, known_modules)) is not None
        ]
    base = _resolve_import_from_base(node, pkg_parts)
    if not base:
        return []
    return [
        target
        for alias in node.names
        if (target := _resolve_from_alias(base, alias.name, known_modules)) is not None
    ]


def build_import_graph(trees: Mapping[Path, ast.Module], root: Path | None = None) -> ImportGraph:
    """Build the module-level, non-`TYPE_CHECKING` import graph across `trees`."""
    paths = list(trees)
    import_root = _infer_import_root(paths, root)
    modules_by_path = {path: _module_name(path, import_root) for path in paths}
    known_modules = set(modules_by_path.values())
    edges: dict[str, set[str]] = {mod: set() for mod in known_modules}
    locations: dict[tuple[str, str], str] = {}

    for path, tree in trees.items():
        mod = modules_by_path[path]
        rel_posix = path.relative_to(import_root).as_posix()
        pkg_parts = path.relative_to(import_root).parent.parts
        for stmt in _module_level_imports(tree):
            for target in _resolve_statement_targets(stmt, pkg_parts, known_modules):
                if target != mod:
                    edges[mod].add(target)
                    locations.setdefault((mod, target), f"{rel_posix}:{stmt.lineno}")

    return ImportGraph(edges=edges, locations=locations)


def _orient_cycle(cycle: Sequence[str], locations: Mapping[tuple[str, str], str]) -> list[str]:
    """Orient `TopologicalSorter`'s cycle list so consecutive pairs follow the import direction."""
    items = list(cycle)
    if len(items) >= 2 and (items[0], items[1]) not in locations:
        items.reverse()
    return items


def verify_acyclic_imports(trees: Mapping[Path, ast.Module], root: Path | None = None) -> None:
    """Verify the import graph has no cycles via `TopologicalSorter(graph).prepare()`.

    Raises `graphlib.CycleError` naming the cycle, `file:line` locations, the rule, and the fix.
    """
    graph = build_import_graph(trees, root=root)
    try:
        TopologicalSorter(graph.edges).prepare()
    except CycleError as exc:
        ordered = _orient_cycle(exc.args[1], graph.locations)
        chain = " -> ".join(ordered)
        sites = ", ".join(
            f"{graph.locations.get((src_mod, dst_mod), src_mod)} ({src_mod} -> {dst_mod})"
            for src_mod, dst_mod in pairwise(ordered)
        )
        msg = (
            f"{sites}: circular import cycle {chain} "
            "(rule: no module-level circular imports; "
            "fix: move shared symbols to a lower module or guard type-only imports with "
            "`if TYPE_CHECKING:`)"
        )
        raise CycleError(msg, ordered) from exc


def import_cycle_violations(
    trees: Mapping[Path, ast.Module], root: Path | None = None
) -> list[str]:
    """Return a diagnostic message if `trees` contain a module-level import cycle, else `[]`."""
    try:
        verify_acyclic_imports(trees, root=root)
    except CycleError as exc:
        return [str(exc.args[0])]
    return []


def _is_commands_import_allowed(module_name: str) -> bool:
    """Return True if `module_name` is `devops_cli.main` or inside `devops_cli.commands`."""
    return (
        module_name == _MAIN_MODULE
        or module_name == _COMMANDS_PACKAGE
        or module_name.startswith(_COMMANDS_PREFIX)
    )


def _is_commands_target(module_name: str) -> bool:
    """Return True if `module_name` is `devops_cli.commands` or a submodule of it."""
    return module_name == _COMMANDS_PACKAGE or module_name.startswith(_COMMANDS_PREFIX)


def _statement_commands_targets(
    node: ast.Import | ast.ImportFrom, pkg_parts: Sequence[str]
) -> list[tuple[int, str]]:
    """Return `(lineno, target)` for any import of `devops_cli.commands` on `node`."""
    if isinstance(node, ast.Import):
        return [
            (node.lineno, alias.name) for alias in node.names if _is_commands_target(alias.name)
        ]
    base = _resolve_import_from_base(node, pkg_parts)
    if not base:
        return []
    if _is_commands_target(base):
        return [(node.lineno, base)]
    if base == _ROOT_PACKAGE:
        return [
            (node.lineno, _COMMANDS_PACKAGE) for alias in node.names if alias.name == "commands"
        ]
    return []


def _all_imports(tree: ast.Module) -> Iterator[ast.Import | ast.ImportFrom]:
    """Yield every import statement in `tree` at any scope, walking only statement containers."""
    pending: list[ast.AST] = list(tree.body)
    while pending:
        node = pending.pop()
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            yield node
            continue
        pending.extend(
            child
            for child in ast.iter_child_nodes(node)
            if isinstance(child, _STATEMENT_CONTAINERS)
        )


def interface_layer_violations(
    trees: Mapping[Path, ast.Module], root: Path | None = None
) -> list[str]:
    """Report any import of `devops_cli.commands` outside `devops_cli.commands.*` and `devops_cli.main`."""
    paths = list(trees)
    import_root = _infer_import_root(paths, root)
    violations: list[str] = []

    for path, tree in trees.items():
        rel = path.relative_to(import_root)
        mod = _module_name(path, import_root)
        if _is_commands_import_allowed(mod):
            continue
        rel_posix = rel.as_posix()
        pkg_parts = rel.parent.parts
        hits = sorted(
            hit
            for node in _all_imports(tree)
            for hit in _statement_commands_targets(node, pkg_parts)
        )
        violations.extend(
            f"{rel_posix}:{lineno}: {mod} imports {target} "
            "(rule: no module outside devops_cli.commands.* and devops_cli.main may import "
            "devops_cli.commands; fix: move the shared symbol into a domain module below "
            "devops_cli.commands)"
            for lineno, target in hits
        )

    return violations
