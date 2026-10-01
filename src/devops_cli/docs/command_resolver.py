"""Resolve `devops` command lines against the real command tree without running them.

`typer.main.get_command(main.app)` cannot see past the first segment: every top-level
command is a lazy proxy that accepts any arguments (`core/cli.py`). The walk therefore
starts where `main._delegate` does, at the module app `main._COMMAND_SPECS` names, and
descends it with `resolve_command`. Each node is parsed with `make_context`, which converts
values and runs parameter callbacks but never a command's own callback.

Typer vendors its own copy of Click, so nothing here imports a Click class: a group is
whatever has `resolve_command`, and an unknown option is the parse error that carries
`possibilities`. The resolver tests hold one defect at each depth as a negative control, so
a Typer upgrade that changes the walk fails them instead of resolving everything.
"""

from __future__ import annotations

from collections.abc import Sequence
from enum import StrEnum
from functools import cache
from importlib import import_module
from typing import Any

import typer
from pydantic import BaseModel, ConfigDict

from devops_cli.config.constants import CONST_CLI_ROOT_LEVEL_COMMANDS
from devops_cli.lang import MESSAGES

_ROOT = "devops"


class ArgvPlaceholder(BaseModel):
    """An argv token computed at runtime, so it may stand for any value or option."""

    model_config = ConfigDict(frozen=True)

    expression: str

    def __str__(self) -> str:
        return f"<{self.expression}>"


ArgvToken = str | ArgvPlaceholder


class CommandReferenceDefect(StrEnum):
    """The defects a command line is checked for."""

    UNKNOWN_COMMAND = "unknown_command"
    UNKNOWN_OPTION = "unknown_option"
    UNEXPECTED_ARGUMENT = "unexpected_argument"


class CommandReferenceFinding(BaseModel):
    """The token a command line's parse rejected, and the command it was given to."""

    model_config = ConfigDict(frozen=True)

    defect: CommandReferenceDefect
    command_path: str
    token: str

    def describe(self) -> str:
        """Name the rejected token and the command it was given to."""
        template = {
            CommandReferenceDefect.UNKNOWN_COMMAND: MESSAGES.docs.argv_unknown_command,
            CommandReferenceDefect.UNKNOWN_OPTION: MESSAGES.docs.argv_unknown_option,
            CommandReferenceDefect.UNEXPECTED_ARGUMENT: MESSAGES.docs.argv_unexpected_argument,
        }[self.defect]
        return template.format(token=self.token, command_path=self.command_path)


def resolve_devops_argv(tokens: Sequence[ArgvToken]) -> CommandReferenceFinding | None:
    """Return the first defect in the command line `devops <tokens>`, or None if it parses.

    Only literal tokens are reported. A placeholder where a subcommand belongs ends the walk,
    and a placeholder left over as an argument may be an option the caller computes.
    """
    context, finding = _parse(_root_command(), _ROOT, _ROOT, tokens, parent=None)
    subcommand = _literal_subcommand(context, tokens) if finding is None else None
    return finding if subcommand is None else _walk_delegated(*subcommand)


def _walk_delegated(command_name: str, args: Sequence[ArgvToken]) -> CommandReferenceFinding | None:
    """Walk a top-level command as `main._delegate` runs it: its module app, from the top."""
    command = _module_command(command_name)
    if command is None:
        return _found(CommandReferenceDefect.UNKNOWN_COMMAND, _ROOT, command_name)
    if command_name in CONST_CLI_ROOT_LEVEL_COMMANDS:
        return _walk(command, _ROOT, _ROOT, [command_name, *args], parent=None)
    return _walk(command, command_name, f"{_ROOT} {command_name}", args, parent=None)


def _walk(
    command: Any, name: str, path: str, tokens: Sequence[ArgvToken], parent: Any
) -> CommandReferenceFinding | None:
    """Parse `tokens` on `command` and, for a group, descend into the subcommand they name."""
    context, finding = _parse(command, name, path, tokens, parent)
    is_group = callable(getattr(command, "resolve_command", None))
    subcommand = _literal_subcommand(context, tokens) if finding is None and is_group else None
    if subcommand is None:
        return finding
    child_name, child_tokens = subcommand
    child = _child(command, context, child_name)
    if child is None:
        return _found(CommandReferenceDefect.UNKNOWN_COMMAND, path, child_name)
    return _walk(child, child_name, f"{path} {child_name}", child_tokens, context)


def _parse(
    command: Any, name: str, path: str, tokens: Sequence[ArgvToken], parent: Any
) -> tuple[Any, CommandReferenceFinding | None]:
    """Parse `tokens` as `command`'s arguments: its context, or the defect that stopped it.

    Of the errors a strict parse raises, only an unknown option is final. Click converts
    values before it looks for extra arguments, so a value that fails conversion -- usually
    a placeholder -- hides them, and a lenient parse recovers the leftovers instead. Click's
    parser consumes the list it is given, so each parse gets its own.
    """
    args = [str(token) for token in tokens]
    try:
        strict = command.make_context(name, list(args), parent=parent, resilient_parsing=False)
        return strict, None
    except typer.TyperException as error:
        option = _unknown_option(error)
        if option is not None:
            return None, _found(CommandReferenceDefect.UNKNOWN_OPTION, path, option)
    context = command.make_context(name, args, parent=parent, resilient_parsing=True)
    return context, _unexpected_argument(context, path, tokens)


def _unknown_option(error: Exception) -> str | None:
    """The option a parse rejected as unknown, duck-typed on vendored Click's `NoSuchOption`.

    `BadOptionUsage` carries `option_name` too, for a known option missing its value; only
    `NoSuchOption` carries `possibilities`.
    """
    if not hasattr(error, "possibilities"):
        return None
    return str(getattr(error, "option_name", ""))


def _unexpected_argument(
    context: Any, path: str, tokens: Sequence[ArgvToken]
) -> CommandReferenceFinding | None:
    """Report the literal arguments a command that takes no extra arguments left over."""
    literals = {token for token in tokens if isinstance(token, str)}
    stray = [argument for argument in context.args if argument in literals]
    if context.allow_extra_args or not stray:
        return None
    return _found(CommandReferenceDefect.UNEXPECTED_ARGUMENT, path, " ".join(stray))


def _literal_subcommand(
    context: Any, tokens: Sequence[ArgvToken]
) -> tuple[str, Sequence[ArgvToken]] | None:
    """The literal subcommand name a group's parse left over, and the tokens after it."""
    # Vendored Click keeps the subcommand name in `_protected_args`, with no public
    # accessor. A group parses no positionals of its own, so what it leaves is a suffix of
    # its tokens. If Typer renames the attribute, the walk fails here, loudly.
    leftover = len(context._protected_args) + len(context.args)
    tail = tokens[len(tokens) - leftover :]
    head = tail[0] if tail else None
    if head is None or isinstance(head, ArgvPlaceholder):
        return None
    return head, tail[1:]


def _child(group: Any, context: Any, name: str) -> Any | None:
    """The subcommand `name` of `group`, or None when the group has no such command."""
    try:
        _, child, _ = group.resolve_command(context, [name])
    except typer.TyperException:
        return None
    return child


def _found(defect: CommandReferenceDefect, path: str, token: str) -> CommandReferenceFinding:
    return CommandReferenceFinding(defect=defect, command_path=path, token=token)


@cache
def _root_command() -> Any:
    """The `devops` group itself, whose own options precede the command name."""
    from devops_cli.main import app

    return typer.main.get_command(app)


def _module_command(command_name: str) -> Any | None:
    """The command `main._delegate` hands a top-level command's arguments to, if any."""
    from devops_cli.main import _COMMAND_SPECS

    spec = _COMMAND_SPECS.get(command_name)
    return None if spec is None else module_click_command(spec[0])


@cache
def module_click_command(module_path: str) -> Any | None:
    """The command Typer builds from a command module's `app`, built once per process.

    A build evaluates every parameter annotation in the module, most of a second across all
    of them, and documentation generation and the resolver share each build.
    """
    app = getattr(import_module(module_path), "app", None)
    return None if app is None else typer.main.get_command(app)
