"""The record of a usage error of the CLI: its kind and its names, and no argument value (#4839).

The root group of the CLI (`devops_cli.core.cli.UsageRecordingGroup`) gives each usage error of
Click to `record_usage_error`, and Typer then shows the error as before. Click's own error types
give the kind. Click raises a plain `UsageError` for an unknown command and for an extra argument,
so the group and the command classes of `new_typer` tag those two cases where they occur. The
command classes also mark the command path of a parse error, because the parser raises some
errors with no context, and Click then gives them the context of the parent group. No code
here reads the message of an error, because the message quotes what the caller typed.

One record goes to three sinks: the counter `devops_cli_usage_error_total` with the labels kind,
command_path and caller; the log record `cli_usage_error` on the logger `devops_cli.usage`, which
the OTLP log bridge exports and which no console shows; and one JSON line of the usage-error
ledger under the user data root, unless `telemetry.usage_ledger` is false. The typed name and the
suggestion go only to the log record and the ledger. A word that is not in the form of a CLI name
is recorded as `<value>`.
"""

from __future__ import annotations

import contextvars
import difflib
import logging
import os
import re
import sys
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from enum import StrEnum
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Final, override

from pydantic import BaseModel, ConfigDict, Field, ValidationError
from typer._click.exceptions import (
    BadOptionUsage,
    BadParameter,
    MissingParameter,
    NoSuchOption,
    UsageError,
)

LEDGER_NAME: Final = "usage-errors.jsonl"
LOG_BODY: Final = "cli_usage_error"
VALUE_PLACEHOLDER: Final = "<value>"

_LEDGER_MAX_BYTES: Final = 1024 * 1024
_LEDGER_BACKUPS: Final = 3
_PROGRAM: Final = "devops"
_NAME_MAX_LENGTH: Final = 40
# The form of a CLI name: a short option of one character, or lowercase words of letters and
# digits, each of at most 20 characters, joined by `-` or `_`, after an optional `-` or `--`. A
# token, a number or a path does not have this form.
_CLI_NAME: Final = re.compile(r"-[A-Za-z0-9]|(?:--?)?[a-z][a-z0-9]{0,19}(?:[-_][a-z0-9]{1,20})*")
_TAG_ATTRIBUTE: Final = "devops_cli_usage_tag"
_PATH_ATTRIBUTE: Final = "devops_cli_usage_command_path"
_CI_MARKERS: Final = ("CI", "GITHUB_ACTIONS")
_KILO_MARKER: Final = "KILO"
_OTHER_TOOL: Final = "other"
# The agent tools that a record names, each with the names that `detect_agent` or the `AI_AGENT`
# variable gives it, in lower case with `_` for `-`. A name that starts with one of them, then
# `_`, is that tool too: Claude Code sets `AI_AGENT` to `claude-code_<version>_agent`.
_AGENT_TOOLS: Final[tuple[tuple[str, str], ...]] = (
    ("claude_code", "claude_code"),
    ("cowork", "claude_code"),
    ("gemini_cli", "gemini_cli"),
    ("codex", "codex"),
    ("cursor", "cursor"),
    ("kilo", "kilo"),
    ("open_code", "opencode"),
    ("opencode", "opencode"),
    ("antigravity", "antigravity"),
    ("devops_implement", "devops_implement"),
)

_LOGGER: Final = logging.getLogger("devops_cli.usage")
# The record goes on to the handlers of the root logger, such as the OTLP log bridge. With no
# handler of its own, a warning would go to `logging.lastResort`, which prints it on stderr.
_LOGGER.addHandler(logging.NullHandler())

_MCP_CALL: Final[contextvars.ContextVar[bool]] = contextvars.ContextVar(
    "devops_cli_usage_mcp_call", default=False
)


class UsageErrorKind(StrEnum):
    """What the caller typed wrong."""

    UNKNOWN_COMMAND = "unknown_command"
    UNKNOWN_OPTION = "unknown_option"
    MISSING_ARGUMENT = "missing_argument"
    MISSING_OPTION = "missing_option"
    BAD_VALUE = "bad_value"
    OPTION_USAGE = "option_usage"
    EXTRA_ARGUMENT = "extra_argument"
    OTHER = "other"


class UsageCaller(StrEnum):
    """Who ran the command that failed."""

    PERSON = "person"
    AGENT = "agent"
    CI = "ci"
    MCP = "mcp"


class UsageErrorRecord(BaseModel):
    """One usage error of the CLI, as the ledger line and the log record hold it."""

    model_config = ConfigDict(frozen=True)

    at: datetime = Field(description="When the error occurred, in UTC")
    kind: UsageErrorKind = Field(description="What the caller typed wrong")
    command_path: str = Field(
        description="The declared names of the command below devops, such as `pr view`"
    )
    name: str | None = Field(
        description=f"The typed command word, the option name or the parameter name, or "
        f"`{VALUE_PLACEHOLDER}` for a word that is not in the form of a CLI name"
    )
    suggestion: str | None = Field(description="The close name that Click suggests")
    caller: UsageCaller = Field(description="Who ran the command")
    agent_tool: str | None = Field(description="The agent tool that ran the command")
    version: str = Field(description="The version of devops-cli")


def tag_unknown_command(error: UsageError, typed: str, choices: Iterable[str]) -> None:
    """Mark the error of an unknown command word with the typed word and the close match that
    Typer's suggestion also takes from `difflib`."""
    matches = difflib.get_close_matches(typed, list(choices))
    _tag(error, UsageErrorKind.UNKNOWN_COMMAND, typed, matches[0] if matches else None)


def tag_parse_error(error: UsageError, command_path: str) -> None:
    """Mark an error of the parse of a command with the command path of that command, and a
    plain `UsageError` there as an argument that the command does not take. The first mark of
    the path stays: it is the one of the command that parsed."""
    if getattr(error, _PATH_ATTRIBUTE, None) is None:
        setattr(error, _PATH_ATTRIBUTE, command_path)
    if type(error) is UsageError:
        _tag(error, UsageErrorKind.EXTRA_ARGUMENT, None, None)


def _tag(error: UsageError, kind: UsageErrorKind, name: str | None, suggestion: str | None) -> None:
    setattr(error, _TAG_ATTRIBUTE, (kind, name, suggestion))


@contextmanager
def mcp_call() -> Iterator[None]:
    """Mark the commands that run in the block as calls of an MCP tool."""
    token = _MCP_CALL.set(True)
    try:
        yield
    finally:
        _MCP_CALL.reset(token)


def ledger_path() -> Path:
    """The usage-error ledger: `usage-errors.jsonl` under the user data root."""
    from devops_cli.core.repo import user_data_root

    return user_data_root() / LEDGER_NAME


def usage_error_record(error: UsageError) -> UsageErrorRecord:
    """The record of `error`: its kind, its names and its caller, and no argument value."""
    from devops_cli import __version__

    kind, name, suggestion = _classified(error)
    agent_tool = _agent_tool()
    return UsageErrorRecord(
        at=datetime.now(UTC).replace(microsecond=0),
        kind=kind,
        command_path=_command_path(error),
        name=_cli_name(name),
        suggestion=_cli_name(suggestion),
        caller=_caller(agent_tool),
        agent_tool=agent_tool,
        version=__version__,
    )


def record_usage_error(error: UsageError) -> None:
    """Count `error`, log it and add it to the ledger. A ledger that cannot be written gives one
    warning, and the error goes on to Typer as before."""
    from devops_cli.telemetry.instruments import USAGE_ERROR_TOTAL, emit

    record = usage_error_record(error)
    emit(
        USAGE_ERROR_TOTAL,
        1.0,
        {
            "kind": record.kind.value,
            "command_path": record.command_path,
            "caller": record.caller.value,
        },
    )
    fields = record.model_dump(mode="json", exclude={"at"})
    _LOGGER.warning(LOG_BODY, extra={f"usage.{key}": value for key, value in fields.items()})
    if _ledger_on():
        _add_to_ledger(record)


def _classified(error: UsageError) -> tuple[UsageErrorKind, str | None, str | None]:
    """The kind, the name and the suggestion of `error`, from its tag or from its type."""
    tag: tuple[UsageErrorKind, str | None, str | None] | None = getattr(error, _TAG_ATTRIBUTE, None)
    if tag is not None:
        return tag
    match error:
        case NoSuchOption():
            return UsageErrorKind.UNKNOWN_OPTION, error.option_name, _first(error.possibilities)
        case MissingParameter() if _param_type(error) == "argument":
            return UsageErrorKind.MISSING_ARGUMENT, _param_name(error), None
        case MissingParameter():
            return UsageErrorKind.MISSING_OPTION, _param_name(error), None
        case BadParameter():
            return UsageErrorKind.BAD_VALUE, _param_name(error), None
        case BadOptionUsage():
            return UsageErrorKind.OPTION_USAGE, error.option_name, None
        case _:
            return UsageErrorKind.OTHER, None, None


def _first(names: Iterable[str] | None) -> str | None:
    return next(iter(names or ()), None)


def _param_type(error: MissingParameter) -> str | None:
    return error.param.param_type_name if error.param is not None else error.param_type


def _param_name(error: BadParameter) -> str | None:
    return error.param.name if error.param is not None else None


def _command_path(error: UsageError) -> str:
    """The command path of the command that failed, below the program name: declared names
    only. The mark of the parse comes first, then the context of `error`."""
    path: str | None = getattr(error, _PATH_ATTRIBUTE, None)
    if path is None:
        path = error.ctx.command_path if error.ctx is not None else ""
    words = path.split()
    return " ".join(words[1:] if words[:1] == [_PROGRAM] else words)


def _cli_name(word: str | None) -> str | None:
    """`word` when it has the form of a CLI name and the secret mask leaves it as it is, else
    `<value>`."""
    if not word:
        return None
    from devops_cli.security.sanitizer import mask_secrets

    if len(word) <= _NAME_MAX_LENGTH and _CLI_NAME.fullmatch(word) and mask_secrets(word) == word:
        return word
    return VALUE_PLACEHOLDER


def _agent_tool() -> str | None:
    """The agent tool that runs devops-cli, from the markers that `detect_agent` reads, or None."""
    from detect_agent import determine_agent

    agent = determine_agent()["agent"]
    if agent is None:
        return None
    name = agent["name"].strip().lower().replace("-", "_")
    # Kilo is a fork of OpenCode: its shell sets `OPENCODE`, which `detect_agent` reads, and `KILO`.
    if name == "open_code" and os.environ.get(_KILO_MARKER):
        name = "kilo"
    return next(
        (tool for prefix, tool in _AGENT_TOOLS if name == prefix or name.startswith(f"{prefix}_")),
        _OTHER_TOOL,
    )


def _caller(agent_tool: str | None) -> UsageCaller:
    if _MCP_CALL.get():
        return UsageCaller.MCP
    if agent_tool is not None:
        return UsageCaller.AGENT
    if any(os.environ.get(marker) for marker in _CI_MARKERS):
        return UsageCaller.CI
    return UsageCaller.PERSON


def _ledger_on() -> bool:
    """Whether `telemetry.usage_ledger` is on. Settings that cannot load can be the ones that turn
    the ledger off, so the ledger then stays off, as export does (#956)."""
    from devops_cli.config.settings import load_settings
    from devops_cli.exceptions.base import DevOpsCLIError

    try:
        return load_settings().telemetry.usage_ledger
    except DevOpsCLIError, ValidationError:
        return False


class _LedgerFile(RotatingFileHandler):
    """The rotating file of the ledger. A write error goes to the caller of `handle`, in place of
    the traceback that `logging` prints for a handler error."""

    @override
    def handleError(self, record: logging.LogRecord) -> None:
        error = sys.exception()
        if error is not None:
            raise error


def _add_to_ledger(record: UsageErrorRecord) -> None:
    """Append `record` to the ledger as one JSON line: 1 MiB a file, and 3 older files."""
    path = ledger_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        ledger = _LedgerFile(
            path,
            maxBytes=_LEDGER_MAX_BYTES,
            backupCount=_LEDGER_BACKUPS,
            encoding="utf-8",
            delay=True,
        )
        try:
            ledger.handle(logging.makeLogRecord({"msg": record.model_dump_json()}))
        finally:
            ledger.close()
    except OSError as exc:
        from devops_cli.lang import MESSAGES
        from devops_cli.output import print_warning

        print_warning(
            MESSAGES.telemetry.usage_ledger_unwritable.format(path=path, reason=exc.strerror),
            safe=True,
        )


__all__ = [
    "LEDGER_NAME",
    "LOG_BODY",
    "VALUE_PLACEHOLDER",
    "UsageCaller",
    "UsageErrorKind",
    "UsageErrorRecord",
    "ledger_path",
    "mcp_call",
    "record_usage_error",
    "tag_parse_error",
    "tag_unknown_command",
    "usage_error_record",
]
