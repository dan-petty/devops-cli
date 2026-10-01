"""Collect the `devops` command lines the MCP server builds and resolve them statically.

The MCP tools and resources shell out through `_run_mcp_cmd`, and a command that does not
exist comes back as ordinary tool text, not as an error. Nothing ran these lists against
the CLI, so this module reads them from the server's source and hands each one to
`resolve_devops_argv`; no tool and no command runs.
"""

from __future__ import annotations

import ast
import inspect
import sys
from collections.abc import Iterable, Iterator, Sequence
from importlib import import_module
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from devops_cli.config.constants import (
    CONST_ARGV_EXTENDING_METHODS,
    CONST_DEVOPS_ARGV_PREFIX,
    CONST_MCP_SERVER_MODULE,
)
from devops_cli.core.repo import find_repo_root
from devops_cli.docs.command_resolver import ArgvPlaceholder, ArgvToken, resolve_devops_argv
from devops_cli.lang import MESSAGES

_SCOPE_NODES = (ast.FunctionDef, ast.AsyncFunctionDef)
_MODULE_SCOPE = "<module>"


class DevopsArgvReference(BaseModel):
    """One `uv run devops` argv list in source, as the tokens that follow `devops`."""

    model_config = ConfigDict(frozen=True)

    path: str
    line: int
    owner: str
    tokens: tuple[ArgvToken, ...]

    @property
    def command_line(self) -> str:
        """The tokens after `devops`, placeholders shown as `<expression>`."""
        return " ".join(str(token) for token in self.tokens)


def collect_devops_argv_references(source: str, path: str) -> list[DevopsArgvReference]:
    """Collect every list literal in `source` that starts with `uv run devops`.

    A list assigned to a variable also gains every token later appended or extended onto
    that variable in the same function, in source order, up to the next list assigned to
    it. A literal string is kept as written and any other element or added value becomes a
    placeholder. Branches are not followed, so appends that exclude each other read as one
    command line.
    """
    tree = ast.parse(source, filename=path)
    scopes = [tree, *(node for node in ast.walk(tree) if isinstance(node, _SCOPE_NODES))]
    references = [ref for scope in scopes for ref in _scope_references(scope, path)]
    return sorted(references, key=lambda reference: reference.line)


def collect_mcp_server_argv_references() -> list[DevopsArgvReference]:
    """Collect the `uv run devops` argv lists of the FastMCP server's tools and resources.

    Each is located by its path from the repository root, `src/` included, so an editor or
    a CI annotation can open it.
    """
    module = import_module(CONST_MCP_SERVER_MODULE)
    source_file = Path(inspect.getsourcefile(module) or "").resolve()
    path = source_file.relative_to(find_repo_root(source_file)).as_posix()
    return collect_devops_argv_references(inspect.getsource(module), path)


def describe_unresolved_references(references: Iterable[DevopsArgvReference]) -> list[str]:
    """One line per reference that does not resolve, at its `path:line`."""
    return [
        MESSAGES.docs.argv_unresolved.format(
            location=f"{reference.path}:{reference.line}",
            owner=reference.owner,
            command_line=reference.command_line,
            problem=finding.describe(),
        )
        for reference in references
        if (finding := resolve_devops_argv(reference.tokens)) is not None
    ]


def check_mcp_server_argv() -> list[str]:
    """Describe every MCP server argv list that names a missing command or option."""
    return describe_unresolved_references(collect_mcp_server_argv_references())


def _scope_references(scope: ast.AST, path: str) -> Iterator[DevopsArgvReference]:
    """The argv lists written directly in one module or function body."""
    nodes = list(_own_nodes(scope))
    bindings = [binding for node in nodes if (binding := _argv_binding(node)) is not None]
    calls = [node for node in nodes if isinstance(node, ast.Call) and _extended_name(node)]
    owner = getattr(scope, "name", _MODULE_SCOPE)
    for node in nodes:
        if isinstance(node, ast.List) and _is_devops_argv(node):
            listed = [_token(element) for element in node.elts[len(CONST_DEVOPS_ARGV_PREFIX) :]]
            added = _added_tokens(node, bindings, calls)
            yield DevopsArgvReference(
                path=path, line=node.lineno, owner=owner, tokens=(*listed, *added)
            )


def _own_nodes(scope: ast.AST) -> Iterator[ast.AST]:
    """The nodes of a scope, without descending into the functions defined in it."""
    for child in ast.iter_child_nodes(scope):
        yield child
        if not isinstance(child, _SCOPE_NODES):
            yield from _own_nodes(child)


def _is_devops_argv(node: ast.List) -> bool:
    head = node.elts[: len(CONST_DEVOPS_ARGV_PREFIX)]
    literals = (element.value for element in head if isinstance(element, ast.Constant))
    return tuple(literals) == CONST_DEVOPS_ARGV_PREFIX


def _argv_binding(node: ast.AST) -> tuple[str, ast.List] | None:
    """The variable name and argv list of an assignment such as `cmd = ["uv", ...]`."""
    if not isinstance(node, ast.Assign | ast.AnnAssign):
        return None
    target = node.targets[0] if isinstance(node, ast.Assign) else node.target
    value = node.value
    if isinstance(target, ast.Name) and isinstance(value, ast.List) and _is_devops_argv(value):
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
) -> list[ArgvToken]:
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


def _call_tokens(call: ast.Call) -> list[ArgvToken]:
    """The tokens `.append(value)` or `.extend(values)` adds, a placeholder per runtime value.

    An extend of a list or tuple literal adds its elements; any other extend adds tokens
    that are not known until it runs, which one placeholder stands for.
    """
    if len(call.args) != 1:
        return []
    added = call.args[0]
    if not isinstance(call.func, ast.Attribute) or call.func.attr != "extend":
        return [_token(added)]
    if isinstance(added, ast.List | ast.Tuple):
        return [_token(element) for element in added.elts]
    return [ArgvPlaceholder(expression=ast.unparse(added))]


def _token(element: ast.expr) -> ArgvToken:
    if isinstance(element, ast.Constant) and isinstance(element.value, str):
        return element.value
    return ArgvPlaceholder(expression=ast.unparse(element))


def _position(node: ast.expr) -> tuple[int, int]:
    return node.lineno, node.col_offset
