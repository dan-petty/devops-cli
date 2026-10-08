"""Collect the `devops` command lines built in source and resolve them statically.

Code under `src/devops_cli` runs the CLI as `["devops", ...]` or `["uv", "run", "devops", ...]`:
the MCP tools and resources, the quality gate's steps, the release gate and the devcontainer
bootstrap. A command line that names a missing command or option fails only when it runs,
and the failure comes back as tool text or a warning. This module reads those lists from the
source of every module and hands each one to `resolve_devops_argv`; nothing runs.

Two rules decide what a list reads as:

- Branch-blind: a list assigned to a variable gains every token later appended or extended
  onto that variable in the same function, in source order, up to the next list assigned to
  it. Branches are not followed, so appends that exclude each other read as one command line.
- Single token: a computed list element or `.append` argument is exactly one token, so one
  left over where the command takes no more arguments is reported. A starred element, or an
  `.extend` of a runtime value, stands for any number of tokens and is not. An option name is
  therefore written as a literal, or as a conditional between literals (nested or not), which
  is resolved once per alternative.
"""

from __future__ import annotations

import ast
import sys
from collections.abc import Iterable, Iterator, Sequence
from itertools import product
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from devops_cli.config.constants import (
    CONST_ARGV_EXTENDING_METHODS,
    CONST_DEVOPS_ARGV_PREFIXES,
    CONST_DEVOPS_ARGV_QUOTED_COMMAND,
)
from devops_cli.core.repo import find_repo_root
from devops_cli.docs.command_resolver import ArgvPlaceholder, ArgvToken, resolve_devops_argv
from devops_cli.lang import MESSAGES

_SCOPE_NODES = (ast.FunctionDef, ast.AsyncFunctionDef)
_MODULE_SCOPE = "<module>"
_SOURCE_ROOT = Path(__file__).resolve().parents[1]
_LONGEST_PREFIX = max(len(prefix) for prefix in CONST_DEVOPS_ARGV_PREFIXES)


class ArgvChoice(BaseModel):
    """A token written as a conditional between string literals: one of its alternatives."""

    model_config = ConfigDict(frozen=True)

    alternatives: tuple[str, ...]


SourceArgvToken = ArgvToken | ArgvChoice


class DevopsArgvReference(BaseModel):
    """One `devops` command line in source or documentation, as the tokens after `devops`."""

    model_config = ConfigDict(frozen=True)

    path: str
    line: int
    owner: str
    tokens: tuple[SourceArgvToken, ...]

    def command_lines(self) -> Iterator[tuple[ArgvToken, ...]]:
        """The command lines this reference stands for, one per combination of its choices."""
        return product(
            *(
                token.alternatives if isinstance(token, ArgvChoice) else (token,)
                for token in self.tokens
            )
        )


def collect_devops_argv_references(source: str, path: str) -> list[DevopsArgvReference]:
    """Collect every list literal in `source` that starts with `devops` or `uv run devops`.

    A literal string is kept as written, a conditional between literals becomes a choice, a
    starred element or extended runtime value becomes a placeholder for any number of tokens,
    and any other element or added value becomes a single-token placeholder.
    """
    tree = ast.parse(source, filename=path)
    references = [
        reference
        for scope, nodes in _scopes(tree)
        for reference in _scope_references(scope, nodes, path)
    ]
    return sorted(references, key=lambda reference: reference.line)


def collect_source_argv_references(source_root: Path = _SOURCE_ROOT) -> list[DevopsArgvReference]:
    """Collect the `devops` argv lists of every module under `source_root`, `src/devops_cli`.

    A module whose text holds no quoted `devops` is skipped without being parsed, since every
    such list spells its head that way. A head written with an escape sequence or by implicit
    string concatenation is not seen. Each list is located by its path from the repository
    root, `src/` included, so an editor or a CI annotation can open it.
    """
    repo_root = find_repo_root(source_root)
    return [
        reference
        for module_path, source in _modules_quoting_devops(source_root)
        for reference in collect_devops_argv_references(
            source, module_path.relative_to(repo_root).as_posix()
        )
    ]


def describe_unresolved_references(references: Iterable[DevopsArgvReference]) -> list[str]:
    """One line per reference that does not resolve, at its `path:line`.

    A reference with choices is resolved once per command line and described at the first one
    that fails, so a source line is reported at most once.
    """
    return [
        description
        for reference in references
        if (description := _first_unresolved(reference)) is not None
    ]


def check_source_argv() -> list[str]:
    """Describe every `devops` argv list in `src/devops_cli` that names a missing command,
    option or argument."""
    return describe_unresolved_references(collect_source_argv_references())


def _first_unresolved(reference: DevopsArgvReference) -> str | None:
    """The description of the first command line of `reference` that does not resolve."""
    for tokens in reference.command_lines():
        if (finding := resolve_devops_argv(tokens)) is not None:
            return MESSAGES.docs.argv_unresolved.format(
                location=f"{reference.path}:{reference.line}",
                owner=reference.owner,
                command_line=" ".join(str(token) for token in tokens),
                problem=finding.describe(),
            )
    return None


def _modules_quoting_devops(source_root: Path) -> Iterator[tuple[Path, str]]:
    """Each module under `source_root` whose text holds `devops` as a quoted literal."""
    for module_path in sorted(source_root.rglob("*.py")):
        source = module_path.read_text(encoding="utf-8")
        if any(quoted in source for quoted in CONST_DEVOPS_ARGV_QUOTED_COMMAND):
            yield module_path, source


def _scopes(tree: ast.Module) -> Iterator[tuple[ast.AST, list[ast.AST]]]:
    """The module and each function in it, with the nodes written directly in its body.

    One pass over the tree: a function node belongs to the scope it is defined in, and the
    nodes inside it to its own scope.
    """
    scopes: list[ast.AST] = [tree]
    while scopes:
        scope = scopes.pop()
        nodes: list[ast.AST] = []
        pending = list(ast.iter_child_nodes(scope))
        while pending:
            node = pending.pop()
            nodes.append(node)
            if isinstance(node, _SCOPE_NODES):
                scopes.append(node)
            else:
                pending.extend(ast.iter_child_nodes(node))
        yield scope, nodes


def _scope_references(
    scope: ast.AST, nodes: Sequence[ast.AST], path: str
) -> Iterator[DevopsArgvReference]:
    """The argv lists written directly in one module or function body."""
    argv_lists = [
        (node, head)
        for node in nodes
        if isinstance(node, ast.List) and (head := _devops_prefix_length(node))
    ]
    if not argv_lists:
        return
    bindings = [binding for node in nodes if (binding := _argv_binding(node)) is not None]
    calls = sorted(
        (node for node in nodes if isinstance(node, ast.Call) and _extended_name(node)),
        key=_position,
    )
    owner = getattr(scope, "name", _MODULE_SCOPE)
    for argv, head in argv_lists:
        listed = [_token(element) for element in argv.elts[head:]]
        added = _added_tokens(argv, bindings, calls)
        yield DevopsArgvReference(
            path=path, line=argv.lineno, owner=owner, tokens=(*listed, *added)
        )


def _devops_prefix_length(node: ast.List) -> int:
    """The length of the `devops` prefix `node` starts with, or 0 when it starts with none."""
    head = tuple(
        element.value if isinstance(element, ast.Constant) else None
        for element in node.elts[:_LONGEST_PREFIX]
    )
    return next(
        (len(prefix) for prefix in CONST_DEVOPS_ARGV_PREFIXES if head[: len(prefix)] == prefix),
        0,
    )


def _argv_binding(node: ast.AST) -> tuple[str, ast.List] | None:
    """The variable name and argv list of an assignment such as `cmd = ["devops", ...]`."""
    if not isinstance(node, ast.Assign | ast.AnnAssign):
        return None
    target = node.targets[0] if isinstance(node, ast.Assign) else node.target
    value = node.value
    if (
        isinstance(target, ast.Name)
        and isinstance(value, ast.List)
        and _devops_prefix_length(value)
    ):
        return target.id, value
    return None


def _extended_name(call: ast.Call) -> str | None:
    """The variable a call such as `cmd.append(...)` or `cmd.extend(...)` adds tokens to."""
    method = call.func
    if not isinstance(method, ast.Attribute) or method.attr not in CONST_ARGV_EXTENDING_METHODS:
        return None
    return method.value.id if isinstance(method.value, ast.Name) else None


def _added_tokens(
    argv: ast.List, bindings: Sequence[tuple[str, ast.List]], calls: Sequence[ast.Call]
) -> list[SourceArgvToken]:
    """The tokens added to `argv`'s variable before the variable is reassigned."""
    name = next((bound for bound, value in bindings if value is argv), None)
    if name is None:
        return []
    start = _position(argv)
    end = min(
        (
            _position(value)
            for bound, value in bindings
            if bound == name and _position(value) > start
        ),
        default=(sys.maxsize, 0),
    )
    return [
        token
        for call in calls
        if _extended_name(call) == name and start < _position(call) < end
        for token in _call_tokens(call)
    ]


def _call_tokens(call: ast.Call) -> list[SourceArgvToken]:
    """The tokens `.append(value)` or `.extend(values)` adds.

    An append adds one token, and an extend of a list or tuple literal adds its elements. Any
    other extend adds tokens that are not known until it runs, which one placeholder for any
    number of tokens stands for.
    """
    if len(call.args) != 1:
        return []
    added = call.args[0]
    if not isinstance(call.func, ast.Attribute) or call.func.attr != "extend":
        return [_token(added)]
    if isinstance(added, ast.List | ast.Tuple):
        return [_token(element) for element in added.elts]
    return [ArgvPlaceholder(expression=ast.unparse(added))]


def _token(element: ast.expr) -> SourceArgvToken:
    """A literal as written, a choice between literals, or a placeholder for a runtime value.

    A starred element stands for any number of tokens; any other runtime value for one.
    """
    alternatives = _literal_alternatives(element)
    if alternatives is not None:
        return alternatives[0] if len(alternatives) == 1 else ArgvChoice(alternatives=alternatives)
    return ArgvPlaceholder(
        expression=ast.unparse(element), single_token=not isinstance(element, ast.Starred)
    )


def _literal_alternatives(element: ast.expr) -> tuple[str, ...] | None:
    """The strings a string literal, or a conditional whose branches all are such, can give."""
    if isinstance(element, ast.Constant) and isinstance(element.value, str):
        return (element.value,)
    if not isinstance(element, ast.IfExp):
        return None
    body, orelse = _literal_alternatives(element.body), _literal_alternatives(element.orelse)
    return None if body is None or orelse is None else (*body, *orelse)


def _position(node: ast.expr) -> tuple[int, int]:
    return node.lineno, node.col_offset
