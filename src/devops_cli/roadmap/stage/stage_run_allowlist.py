"""The allow-list of the commands that the stage planner may run in its sandbox (#4004).

ADR 0018 gives the stage planner a run tool, and the tool runs one command in a separate Job. A
model writes the command line, so a command runs only when this module names it: the read-only
rows of `CONST_MCP_EXPOSURE_TABLE` of `src/devops_cli/config/constants.py`, with the parameters
that the MCP tool of the row publishes. `_PATH_PARAM_RESTRICTIONS` of
`src/devops_cli/ai/mcp/generator.py` sets the permitted parameters of a restricted command, and
`tests/ai/mcp/test_mcp_read_only_write_options.py` fails on a read-only tool that publishes an
option which writes.

A command that permits a parameter which holds a path is not an entry, even when the table marks
it read-only: a path that the planner gives is untrusted input, and a run reads only the mounted
copy of the staged commit. The parameter is found by its Click type, which Typer builds from a
`Path` annotation, and by `PATH_CONFINEMENTS` of `src/devops_cli/ai/mcp/path_confinement.py`,
which names a text parameter that holds a path under a name that no type shows.

The help form of a command path that the Click tree resolves is permitted, so the planner learns
the options of a write command without running it: Click prints the help and exits before the
command body runs. Every other refusal holds the command path and one reason word, so the planner
branches on it and plans without a run.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from typing import Any, Final

from typer._click.types import File as TyperFile
from typer.models import TyperPath

from devops_cli.ai.mcp.generator import (
    _IGNORED_PARAM_NAMES,
    _JSON_PARAM_NAMES,
    _PATH_PARAM_RESTRICTIONS,
    resolve_click_command,
)
from devops_cli.ai.mcp.path_confinement import PATH_CONFINEMENTS
from devops_cli.config.constants import CONST_MCP_EXPOSURE_TABLE

# One row of `CONST_MCP_EXPOSURE_TABLE`: the command path, the timeout of its tool, the read-only
# flag and the flag that its tool sets a JSON format itself.
type ExposureRow = tuple[tuple[str, ...], float, bool, bool]
# The lookup of a command path in the Click tree, which raises `LookupError` for a path that the
# tree lacks.
type CommandResolver = Callable[[tuple[str, ...]], Any]

# The reason words of a refusal. They are data for the planner and for a test, so they are no
# sentence of the message catalogue.
REASON_UNKNOWN_COMMAND: Final[str] = "unknown command"
REASON_NOT_READ_ONLY: Final[str] = "not read-only"
REASON_PATH_OPTION: Final[str] = "path option"
REASON_OPTION_NOT_PERMITTED: Final[str] = "option not permitted"

_HELP: Final[frozenset[str]] = frozenset({"help"})


@dataclass(frozen=True)
class RunRefusal:
    """The command path of a run that the allow-list refuses, and one reason word."""

    path: tuple[str, ...]
    reason: str
    option: str | None = None


def build_allowlist(
    rows: Sequence[ExposureRow] = CONST_MCP_EXPOSURE_TABLE,
    resolver: CommandResolver = resolve_click_command,
) -> dict[tuple[str, ...], frozenset[str]]:
    """The commands that a run may start, with the parameters that it may use.

    A row that is not read-only, a row whose command the Click tree no longer resolves, and a row
    that permits a parameter which holds a path are left out. A row that the tree lacks stays out
    of the table and is refused as an unknown command, so a stale row opens no run.
    """
    allowlist: dict[tuple[str, ...], frozenset[str]] = {}
    for row in rows:
        decision = _row_decision(row, resolver)
        if isinstance(decision, frozenset):
            allowlist[row[0]] = decision
    return allowlist


def check_command(
    path: tuple[str, ...],
    options: Iterable[str] = (),
    *,
    rows: Sequence[ExposureRow] = CONST_MCP_EXPOSURE_TABLE,
    resolver: CommandResolver = resolve_click_command,
) -> RunRefusal | None:
    """The refusal of a run of `path` with the parameter names `options`, or None if it may run.

    The help form of a path that the Click tree resolves runs, because Click prints the help and
    exits before the command body runs. A path that no row of the table names is refused as an
    unknown command, because the allow-list holds no command that the table does not name.
    """
    names = frozenset(options)
    if names == _HELP:
        if _resolve(path, resolver) is None:
            return RunRefusal(path, REASON_UNKNOWN_COMMAND)
        return None
    row = next((candidate for candidate in rows if candidate[0] == path), None)
    if row is None:
        return RunRefusal(path, REASON_UNKNOWN_COMMAND)
    decision = _row_decision(row, resolver)
    if isinstance(decision, str):
        return RunRefusal(path, decision)
    refused = sorted(names - decision)
    if refused:
        return RunRefusal(path, REASON_OPTION_NOT_PERMITTED, refused[0])
    return None


def _row_decision(row: ExposureRow, resolver: CommandResolver) -> frozenset[str] | str:
    """The parameters that a row permits, or the reason word that leaves its command out."""
    path, _timeout, read_only, format_json = row
    if not read_only:
        return REASON_NOT_READ_ONLY
    command = _resolve(path, resolver)
    if command is None:
        return REASON_UNKNOWN_COMMAND
    return _permitted_parameters(path, format_json, command)


def _resolve(path: tuple[str, ...], resolver: CommandResolver) -> Any | None:
    """The Click command of `path`, or None when the Click tree lacks the path."""
    try:
        return resolver(path)
    except LookupError:
        return None


def _permitted_parameters(
    path: tuple[str, ...], format_json: bool, command: Any
) -> frozenset[str] | str:
    """The parameters that a run of `command` may use, or the path-option reason word.

    A parameter that the tool ignores, a parameter that the tool sets itself as a JSON format, and
    a parameter that the entry of `_PATH_PARAM_RESTRICTIONS` does not allow are no permitted
    parameters. A permitted parameter that holds a path leaves the command out, whether Typer types
    it as a path or `PATH_CONFINEMENTS` names it.
    """
    restrictions = _PATH_PARAM_RESTRICTIONS.get(path)
    allowed: frozenset[str] | None = None if restrictions is None else restrictions["allowed"]
    confined = PATH_CONFINEMENTS.get(_tool_name(path), frozenset())
    names: list[str] = []
    for parameter in command.params:
        if not _keeps_parameter(parameter, format_json, allowed):
            continue
        if isinstance(parameter.type, (TyperPath, TyperFile)) or parameter.name in confined:
            return REASON_PATH_OPTION
        names.append(parameter.name)
    return frozenset(names)


def _keeps_parameter(parameter: Any, format_json: bool, allowed: frozenset[str] | None) -> bool:
    """Whether a tool publishes `parameter`, as `_introspect_command_parameters` publishes it."""
    if parameter.name in _IGNORED_PARAM_NAMES:
        return False
    if format_json and parameter.name in _JSON_PARAM_NAMES:
        return False
    return allowed is None or parameter.name in allowed


def _tool_name(path: tuple[str, ...]) -> str:
    """The name of the MCP tool of a command path, which keys `PATH_CONFINEMENTS`."""
    return "_".join(path).replace("-", "_")
