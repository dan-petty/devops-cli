"""Usage error hints, option error contextualization, and cross-group command lookup."""

from __future__ import annotations

import importlib.resources
import re
from functools import cache
from typing import Any, Final, Literal

import yaml
from pydantic import BaseModel, ConfigDict
from typer._click.core import Context
from typer._click.exceptions import MissingParameter, NoSuchOption, UsageError

HintReason = Literal["by_design", "other_tool", "other_name"]

_CLI_WORD_RE: Final = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]*")
_SPLIT_DELIM_RE: Final = re.compile(r"[-_]+")
_DEFAULT_HELP_OPTIONS: Final = frozenset({"--help", "-h"})
_MAX_LISTED_OPTIONS: Final = 6
_MAX_CROSS_GROUP_MATCHES: Final = 3


class UsageHintEntry(BaseModel):
    """One declarative hint row loaded from `usage_hints.yaml`."""

    model_config = ConfigDict(frozen=True)

    command_path: str
    typed: str
    reason: HintReason
    hint: str


class _UsageHintCatalog(BaseModel):
    model_config = ConfigDict(frozen=True)

    hints: tuple[UsageHintEntry, ...]


@cache
def load_usage_hints() -> tuple[UsageHintEntry, ...]:
    """Load and validate the static CLI hint catalog bundled with `devops_cli.core`."""
    raw = (
        importlib.resources.files("devops_cli.core")
        .joinpath("usage_hints.yaml")
        .read_text(encoding="utf-8")
    )
    loaded = yaml.safe_load(raw)
    return _UsageHintCatalog.model_validate(loaded).hints


@cache
def _hint_index() -> dict[tuple[str, str], str]:
    return {(entry.command_path, entry.typed): entry.hint for entry in load_usage_hints()}


def _help_names(ctx: Context | None) -> frozenset[str]:
    if ctx is None:
        return _DEFAULT_HELP_OPTIONS
    return frozenset(ctx.help_option_names) | _DEFAULT_HELP_OPTIONS


def _relative_command_path(error: UsageError) -> str:
    if error.ctx is None:
        return ""
    tokens = error.ctx.command_path.split()
    return " ".join(tokens[1:]) if len(tokens) > 1 else ""


def strip_help_possibilities(error: UsageError) -> None:
    """Remove `--help` and `-h` from Click's `Possible options` list on an unknown option."""
    if not isinstance(error, NoSuchOption) or not error.possibilities:
        return
    help_names = _help_names(error.ctx)
    kept = [option for option in error.possibilities if option not in help_names]
    setattr(error, "possibilities", kept or None)


def _walk_command_paths(cmd: Any, prefix: tuple[str, ...], out: list[tuple[str, ...]]) -> None:
    if prefix:
        out.append(prefix)
    commands = getattr(cmd, "commands", None)
    if not commands:
        return
    ctx = Context(cmd)
    names = sorted(set(cmd.list_commands(ctx)) | set(commands.keys()))
    for name in names:
        sub = cmd.get_command(ctx, name) or commands.get(name)
        if sub is not None:
            _walk_command_paths(sub, (*prefix, name), out)


@cache
def _all_command_paths() -> tuple[tuple[str, ...], ...]:
    from devops_cli.config.constants import CONST_CLI_ROOT_LEVEL_COMMANDS
    from devops_cli.core.command_resolver import _root_command, module_click_command
    from devops_cli.main import _COMMAND_SPECS

    root = _root_command()
    out: list[tuple[str, ...]] = []
    for name in sorted(root.commands.keys()):
        target = (
            module_click_command(_COMMAND_SPECS[name][0])
            if name in _COMMAND_SPECS
            else root.commands[name]
        )
        if target is None:
            continue
        if name in CONST_CLI_ROOT_LEVEL_COMMANDS:
            sub = getattr(target, "commands", {}).get(name)
            if sub is not None:
                _walk_command_paths(sub, (name,), out)
        else:
            _walk_command_paths(target, (name,), out)
    return tuple(out)


def _matches_word_or_split(path: tuple[str, ...], typed: str, split_parts: tuple[str, ...]) -> bool:
    if path[-1] == typed:
        return True
    if len(split_parts) <= 1:
        return False
    if "-".join(split_parts) == path[-1]:
        return True
    return len(path) >= len(split_parts) and path[-len(split_parts) :] == split_parts


def _deduplicate_pr_aliases(
    matches: list[tuple[str, ...]], prefix: tuple[str, ...]
) -> list[tuple[str, ...]]:
    if prefix[:1] == ("gh",):
        return matches
    match_set = set(matches)
    return [
        path
        for path in matches
        if not (len(path) >= 2 and path[:2] == ("gh", "pr") and path[1:] in match_set)
    ]


def _cross_group_hint(command_path: str, typed: str) -> str | None:
    if not _CLI_WORD_RE.fullmatch(typed):
        return None
    split_parts = tuple(part for part in _SPLIT_DELIM_RE.split(typed) if part)
    matches = [
        path for path in _all_command_paths() if _matches_word_or_split(path, typed, split_parts)
    ]
    prefix = tuple(command_path.split())
    if prefix:
        scoped = [path for path in matches if path[: len(prefix)] == prefix]
        if scoped:
            matches = scoped
    matches = _deduplicate_pr_aliases(matches, prefix)
    if not matches or len(matches) > _MAX_CROSS_GROUP_MATCHES:
        return None
    suggestions = ", ".join(f"devops {' '.join(path)}" for path in matches)
    return f"Did you mean: {suggestions}"


def _ci_rows_hint(
    error: UsageError, command_path: str, kind: object, typed: str | None
) -> str | None:
    from devops_cli.config.constants import CONST_CI_CHECK_ROW_NAMES
    from devops_cli.telemetry.usage_errors import UsageErrorKind

    if command_path != "ci":
        return None
    is_list_cmd = kind == UsageErrorKind.UNKNOWN_COMMAND and typed == "list"
    is_list_opt = isinstance(error, NoSuchOption) and error.option_name == "--list"
    if not (is_list_cmd or is_list_opt):
        return None
    return f"Gate rows: {', '.join(CONST_CI_CHECK_ROW_NAMES)}"


def resolve_usage_hint(error: UsageError) -> str | None:
    """Resolve one hint line for `error`, or `None` when no hint applies."""
    from devops_cli.telemetry.usage_errors import UsageErrorKind, classify_usage_error

    command_path = _relative_command_path(error)
    kind, typed, _ = classify_usage_error(error)
    if (ci_hint := _ci_rows_hint(error, command_path, kind, typed)) is not None:
        return ci_hint

    if isinstance(error, NoSuchOption):
        return _hint_index().get((command_path, error.option_name))

    if kind != UsageErrorKind.UNKNOWN_COMMAND or not isinstance(typed, str):
        return None
    if (table_hint := _hint_index().get((command_path, typed))) is not None:
        return table_hint
    return _cross_group_hint(command_path, typed)


def _small_command_options(ctx: Context) -> list[str]:
    help_names = _help_names(ctx)
    non_help = [
        param
        for param in ctx.command.params
        if getattr(param, "param_type_name", None) == "option"
        and getattr(param, "opts", None)
        and not set(param.opts).issubset(help_names)
        and not getattr(param, "hidden", False)
    ]
    if not (1 <= len(non_help) <= _MAX_LISTED_OPTIONS):
        return []
    return sorted(
        next((opt for opt in param.opts if opt.startswith("--")), param.opts[0])
        for param in non_help
    )


def _is_missing_option(error: MissingParameter) -> bool:
    if error.param_type == "option":
        return True
    return error.param_type is None and getattr(error.param, "param_type_name", None) == "option"


def enrich_error_for_display(error: UsageError) -> None:
    """Add contextual option lists and missing-option help before rendering Click's panel."""
    if isinstance(error, NoSuchOption) and not error.possibilities and error.ctx is not None:
        options = _small_command_options(error.ctx)
        if options:
            setattr(error, "possibilities", options)
        return

    if isinstance(error, MissingParameter) and _is_missing_option(error):
        help_text = (getattr(error.param, "help", None) or "").strip()
        if help_text and help_text not in (error.message or ""):
            error.message = f"{error.message} {help_text}".strip() if error.message else help_text


def prepare_usage_error(error: UsageError) -> str | None:
    """Normalize `error` before telemetry recording and return any hint line to show."""
    strip_help_possibilities(error)
    return resolve_usage_hint(error)


def command_for_path(command_path: str) -> Any:
    """Resolve the Click command or group at space-separated path below `devops`."""
    from devops_cli.config.constants import CONST_CLI_ROOT_LEVEL_COMMANDS
    from devops_cli.core.command_resolver import _root_command, module_click_command
    from devops_cli.main import _COMMAND_SPECS

    parts = [part for part in command_path.split() if part]
    if not parts:
        return _root_command()
    head, *rest = parts
    cmd: Any = (
        module_click_command(_COMMAND_SPECS[head][0])
        if head in _COMMAND_SPECS
        else _root_command().commands[head]
    )
    if head in CONST_CLI_ROOT_LEVEL_COMMANDS:
        cmd = cmd.commands[head]
    for part in rest:
        cmd = cmd.commands[part]
    return cmd


def reset_usage_hint_caches() -> None:
    """Clear cached hint tables and command-path indexes between isolated test runs."""
    load_usage_hints.cache_clear()
    _hint_index.cache_clear()
    _all_command_paths.cache_clear()


__all__ = [
    "HintReason",
    "UsageHintEntry",
    "command_for_path",
    "enrich_error_for_display",
    "load_usage_hints",
    "prepare_usage_error",
    "reset_usage_hint_caches",
    "resolve_usage_hint",
    "strip_help_possibilities",
]
