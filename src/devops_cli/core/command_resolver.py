"""Resolve `devops` command lines against the real command tree without running them.

`typer.main.get_command(main.app)` cannot see past the first segment: every top-level
command is a lazy proxy that accepts any arguments (`core/cli.py`). The walk therefore
starts where `main._delegate` does, at the module app `main._COMMAND_SPECS` names, and
descends it with `resolve_command`. Each node is parsed with `make_context`, which converts
values and runs parameter callbacks but never a command's own callback. An action option
-- eager, like `--help` and `--version`, or one whose value the command never sees, like
Typer's completion options -- runs its callback as it is parsed, to print, write a shell
profile or exit. A node given one, or a group given nothing, which prints its help, is
therefore not parsed: none of them names a missing command or option.

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
    """An argv token computed at runtime.

    By default it stands for any number of tokens, options included: a starred element, an
    extended runtime list, a documentation `[OPTIONS]`. `single_token` marks a value that is
    exactly one token, such as a computed list element, so one left over is reported.
    """

    model_config = ConfigDict(frozen=True)

    expression: str
    single_token: bool = False

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

    A placeholder where a subcommand belongs ends the walk. A literal or a single-token
    placeholder left over where the command takes no more arguments is reported; a placeholder
    for any number of tokens is not, since it may hold the options the caller computes.
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
) -> tuple[Any | None, CommandReferenceFinding | None]:
    """Parse `tokens` as `command`'s arguments: its context, or the defect that stopped it.

    No context means the walk stops here with nothing to report. Of the errors a strict
    parse raises, one naming an option is final: an unknown option is the defect, and a
    known option missing its value stopped the parser before it bound the positionals, so
    its leftovers are not extra arguments. Click converts values before it looks for extra
    arguments, so a value that fails conversion -- usually a placeholder -- hides them, and
    a lenient parse recovers the leftovers instead. Click's parser consumes the list it is
    given, so each parse gets its own. An exit is a fallback for any other callback that
    ends the command.
    """
    args = [str(token) for token in tokens]
    if not args or _gives_action_option(command, name, args, parent):
        return None, None
    try:
        strict = command.make_context(name, list(args), parent=parent, resilient_parsing=False)
        return strict, None
    except typer.Exit, SystemExit:
        return None, None
    except typer.TyperException as error:
        if hasattr(error, "option_name"):
            return None, _unknown_option(error, path)
    context = command.make_context(name, args, parent=parent, resilient_parsing=True)
    return context, _unexpected_argument(context, path, tokens)


def _gives_action_option(command: Any, name: str, args: list[str], parent: Any) -> bool:
    """Whether `args` hands `command` one of its own action options, without parsing them.

    An action option is eager, or keeps its value from the command, so it exists for its
    callback. Only the option parser runs, on a context parsed from no arguments, so no
    callback sees these tokens. A group's parser stops at its subcommand, so
    `scan gitleaks --help` gives `--help` to `gitleaks`, not to `scan`, and the missing
    `gitleaks` is still found.
    """
    probe = command.make_context(name, [], parent=parent, resilient_parsing=True)
    _, _, given = command.make_parser(probe).parse_args(list(args))
    return any(parameter.is_eager or not parameter.expose_value for parameter in given)


def _unknown_option(error: Exception, path: str) -> CommandReferenceFinding | None:
    """The unknown option a parse rejected, duck-typed on vendored Click's `NoSuchOption`.

    `BadOptionUsage` carries `option_name` too, for a known option missing its value; only
    `NoSuchOption` carries `possibilities`.
    """
    if not hasattr(error, "possibilities"):
        return None
    option = str(getattr(error, "option_name", ""))
    return _found(CommandReferenceDefect.UNKNOWN_OPTION, path, option)


def _unexpected_argument(
    context: Any, path: str, tokens: Sequence[ArgvToken]
) -> CommandReferenceFinding | None:
    """Report the literal or single-token arguments a command that takes no extra arguments
    left over."""
    single = {str(token) for token in tokens if isinstance(token, str) or token.single_token}
    stray = [argument for argument in context.args if argument in single]
    if context.allow_extra_args or not stray:
        return None
    return _found(CommandReferenceDefect.UNEXPECTED_ARGUMENT, path, " ".join(stray))


def _literal_subcommand(
    context: Any | None, tokens: Sequence[ArgvToken]
) -> tuple[str, Sequence[ArgvToken]] | None:
    """The literal subcommand name a group's parse left over, and the tokens after it."""
    if context is None:
        return None
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


def _command_declares_dry_run(cmd: Any) -> bool:
    """Whether a Click command declares a --dry-run option."""
    return any(
        param.name == "dry_run" or "--dry-run" in getattr(param, "opts", [])
        for param in getattr(cmd, "params", [])
    )


def _build_forwarded_args(
    initial_tokens: list[str], consumed: int, is_root_level: bool
) -> list[str]:
    """Insert --dry-run directly after the command path in tokens."""
    inserted = [*initial_tokens[:consumed], "--dry-run", *initial_tokens[consumed:]]
    return inserted[1:] if is_root_level else inserted


def _descend_subcommand(
    curr_cmd: Any, curr_name: str, tokens: list[str], parent_ctx: Any
) -> tuple[Any, str, list[str], Any, int] | None:
    """Descend one group level if a subcommand is named in tokens."""
    if (
        not hasattr(curr_cmd, "resolve_command")
        or not callable(curr_cmd.resolve_command)
        or not tokens
    ):
        return None
    ctx = curr_cmd.make_context(curr_name, tokens, parent=parent_ctx, resilient_parsing=False)
    sub_name, sub_cmd, remaining_args = curr_cmd.resolve_command(ctx, list(tokens))
    if sub_name is None:
        return None
    consumed = len(tokens) - len(remaining_args)
    return sub_cmd, sub_name, remaining_args, ctx, consumed


def _walk_to_leaf(
    top_cmd: Any, initial_name: str, initial_tokens: list[str]
) -> tuple[Any, Any | None, int]:
    """Walk subcommands down to the leaf command and parse its arguments."""
    curr_cmd = top_cmd
    curr_name = initial_name
    tokens = list(initial_tokens)
    parent_ctx = None
    consumed = 0

    while True:
        step = _descend_subcommand(curr_cmd, curr_name, tokens, parent_ctx)
        if step is None:
            break
        curr_cmd, curr_name, tokens, parent_ctx, step_consumed = step
        consumed += step_consumed

    if not _command_declares_dry_run(curr_cmd):
        return curr_cmd, None, consumed

    leaf_ctx = curr_cmd.make_context(curr_name, tokens, parent=parent_ctx, resilient_parsing=False)
    return curr_cmd, leaf_ctx, consumed


def resolve_proxy_dry_run(
    mod_path: str, cmd_name: str, args: list[str]
) -> tuple[bool, list[str] | None]:
    """Resolve a delegated command under dry-run and prepare forwarded arguments.

    Returns (True, forwarded_args) if the leaf command declares --dry-run, or (False, None)
    if it does not declare --dry-run (so the caller prints the generic preview line).
    Raises ClickException if the command does not resolve or its arguments do not parse.
    """
    is_root_level = cmd_name in CONST_CLI_ROOT_LEVEL_COMMANDS
    initial_tokens = [cmd_name, *args] if is_root_level else list(args)
    top_cmd = module_click_command(mod_path)
    if top_cmd is None:
        return False, None

    prog_name = "devops" if is_root_level else cmd_name
    leaf_cmd, leaf_ctx, consumed = _walk_to_leaf(top_cmd, prog_name, initial_tokens)

    if not _command_declares_dry_run(leaf_cmd) or leaf_ctx is None:
        return False, None

    if bool(leaf_ctx.params.get("dry_run", False)):
        return True, list(args)

    return True, _build_forwarded_args(initial_tokens, consumed, is_root_level)
