"""The log of the tool calls of a step (#2758).

A step that stops discards its checkout, so the Job log is the only evidence of what the agent
did. `ToolCallLog` is a pydantic-ai `Hooks` capability. It writes one line to the standard error
stream for each tool call: the tool name, the program of a shell command, and the outcome. A call
that has a command writes one more line before it runs, with the program and its first arguments
(#2806), so a call that the kernel kills leaves its cause in the log. `logged_command` masks that
command, bounds it and escapes it to one line. The line after the call holds no argument, no file
content, no output and no text of a refusal, as an argument can hold a path or a secret and the
text of one refusal repeats the whole command. The program is the
first word of the command, as the shell reads it, and only when it is a program that the project
knows: a program of the allowlist, or a program of the table of replacements (#2773). Any other
first word is written as "other", also a short bare word, as the model can read a password or a
token from a file and run it as a command. The line has no reason for a refusal. The tool name and the program tell a refused program
from a refused path.

It also counts the shell commands that the shell refused by its policy, by program, and the calls
that came back as a retry for another cause. A refusal of a file tool, such as a path outside the
root, is an other retry. The reason of a stopped step holds both counts, so a person sees at once
which program the model kept asking for.

The line goes to the console stream, not to `logging`: a `devops` process has no handler for the
level INFO, so such a line would never reach the Job log.
"""

from __future__ import annotations

import shlex
from collections import Counter
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from pydantic import ValidationError
from pydantic_ai import RunContext
from pydantic_ai.capabilities import Hooks, RawToolArgs, ValidatedToolArgs, WrapToolExecuteHandler
from pydantic_ai.exceptions import (
    ModelRetry,
    ToolFailedError,
    ToolRetryError,
    UnexpectedModelBehavior,
)
from pydantic_ai.messages import ToolCallPart
from pydantic_ai.tools import ToolDefinition

from devops_cli.config.commands import IMPLEMENT_ALLOWED_PROGRAMS, IMPLEMENT_SHELL_REPLACEMENTS
from devops_cli.config.constants import (
    CONST_ROADMAP_IMPLEMENT_LOG_COMMAND_CHARS,
    CONST_ROADMAP_IMPLEMENT_LOG_COMMAND_READ_CHARS,
    CONST_ROADMAP_IMPLEMENT_LOG_COMMAND_WORDS,
    CONST_ROADMAP_IMPLEMENT_REFUSED_PROGRAMS,
)
from devops_cli.lang import MESSAGES
from devops_cli.output import print_muted
from devops_cli.security.sanitizer import mask_secrets

# The first words that the log may show. They are fixed in the code, so no text of the model
# reaches the log, and the count of the programs in the reason stays small by design.
_KNOWN_PROGRAMS = frozenset((*IMPLEMENT_ALLOWED_PROGRAMS, *IMPLEMENT_SHELL_REPLACEMENTS))


class ToolOutcome(StrEnum):
    """How a tool call ended: it returned, the tool refused it by its policy, it came back as
    another retry, or the tool reported a failed call."""

    OK = "ok"
    REFUSED = "refused"
    RETRY = "retry"
    FAILED = "failed"


def is_policy_refusal(error: BaseException) -> bool:
    """Whether a `PermissionError` is in the cause chain of `error`: the shell and the file tools of
    the harness raise their refusals as a `ModelRetry` from a `PermissionError`, and pydantic-ai
    raises the retry error from that. The caller tells a shell command from a file path."""
    cause = error.__cause__
    while cause is not None:
        if isinstance(cause, PermissionError):
            return True
        cause = cause.__cause__
    return False


def command_word(args: ValidatedToolArgs) -> str | None:
    """The first word of the `command` argument of a call, as the shell of the harness reads it
    with `shlex`. `None` when the call has no command or the command has no word. The empty string
    when `shlex` cannot read the command: no word of it is a program."""
    command = args.get("command")
    if not isinstance(command, str):
        return None
    try:
        words = shlex.split(command)
    except ValueError:
        return ""
    return words[0] if words else None


def logged_program(word: str | None) -> str:
    """What the log shows for the first word of a command: the word when it is a known program,
    else the word "other". Empty when there is no word. A first word can be an assignment with a
    secret in it, a path, an escape sequence or a password, so no other word is written."""
    if word is None:
        return ""
    if word in _KNOWN_PROGRAMS:
        return word
    return MESSAGES.roadmap.implement_tool_other


def logged_command(args: ValidatedToolArgs) -> str:
    """What the log shows of a command before the call runs (#2806): the first word and the words
    after it, at most `CONST_ROADMAP_IMPLEMENT_LOG_COMMAND_WORDS`, with secrets masked, control
    characters escaped and the text cut to `CONST_ROADMAP_IMPLEMENT_LOG_COMMAND_CHARS`. Empty when
    the call has no command word. The word "other" when the first word is no known program: it can
    be a password or a token, and the words after it mean nothing without it. The mask runs on a
    fixed length of text before the cut, so that the cut cannot split a secret."""
    word = command_word(args)
    if word is None:
        return ""
    if word not in _KNOWN_PROGRAMS:
        return MESSAGES.roadmap.implement_tool_other
    words = shlex.split(str(args["command"]))
    shown = mask_secrets(
        " ".join(words[:CONST_ROADMAP_IMPLEMENT_LOG_COMMAND_WORDS])[
            :CONST_ROADMAP_IMPLEMENT_LOG_COMMAND_READ_CHARS
        ]
    )
    escaped = shown.encode("unicode_escape").decode("ascii")
    cut = (
        len(words) > CONST_ROADMAP_IMPLEMENT_LOG_COMMAND_WORDS
        or len(escaped) > CONST_ROADMAP_IMPLEMENT_LOG_COMMAND_CHARS
    )
    return escaped[:CONST_ROADMAP_IMPLEMENT_LOG_COMMAND_CHARS] + (
        MESSAGES.roadmap.implement_tool_cut if cut else ""
    )


@dataclass
class ToolCallLog:
    """The counters of one step, and the hooks that fill them. `refused` counts the refused shell
    commands by program, and `retried` the other retries, over all turns of the step."""

    refused: Counter[str] = field(default_factory=Counter[str])
    retried: int = 0

    def refused_text(self) -> str:
        """The refused commands for the reason of a stop: the programs from the most refused to the
        least, such as "python 4, cd 2", or "0" when none. It lists at most
        `CONST_ROADMAP_IMPLEMENT_REFUSED_PROGRAMS` programs. The rest join the count of "other"."""
        if not self.refused:
            return "0"
        ranked = self.refused.most_common()
        shown = Counter(dict(ranked[:CONST_ROADMAP_IMPLEMENT_REFUSED_PROGRAMS]))
        if rest := sum(count for _, count in ranked[CONST_ROADMAP_IMPLEMENT_REFUSED_PROGRAMS:]):
            shown[MESSAGES.roadmap.implement_tool_other] += rest
        return ", ".join(f"{program} {count}" for program, count in shown.most_common())

    def hooks(self) -> Hooks[None]:
        """The capability for the agent of the step."""
        return Hooks(tool_execute=self._execute, tool_validate_error=self._invalid)

    def _note(self, tool: str, program: str, outcome: ToolOutcome) -> None:
        """Count a refusal or a retry, and write the line of the call."""
        if outcome is ToolOutcome.REFUSED:
            self.refused[program] += 1
        self.retried += outcome is ToolOutcome.RETRY
        texts = MESSAGES.roadmap
        line = (
            texts.implement_tool_line_program.format(tool=tool, program=program, outcome=outcome)
            if program
            else texts.implement_tool_line.format(tool=tool, outcome=outcome)
        )
        print_muted(line, to_stderr=True, safe=True)

    async def _execute(
        self,
        _ctx: RunContext[Any],
        /,
        *,
        call: ToolCallPart,
        tool_def: ToolDefinition,
        args: ValidatedToolArgs,
        handler: WrapToolExecuteHandler,
    ) -> Any:
        """Run the call, write its line, and pass on the result or the error. The call that
        exceeds the limit of retries reaches here as `UnexpectedModelBehavior`."""
        program = logged_program(command_word(args))
        if command := logged_command(args):
            print_muted(
                MESSAGES.roadmap.implement_tool_started.format(
                    tool=call.tool_name, command=command
                ),
                to_stderr=True,
                safe=True,
            )
        try:
            result = await handler(args)
        except (ToolRetryError, UnexpectedModelBehavior) as error:
            refused = bool(program) and is_policy_refusal(error)
            self._note(
                call.tool_name, program, ToolOutcome.REFUSED if refused else ToolOutcome.RETRY
            )
            raise
        except ToolFailedError:
            self._note(call.tool_name, program, ToolOutcome.FAILED)
            raise
        self._note(call.tool_name, program, ToolOutcome.OK)
        return result

    async def _invalid(
        self,
        _ctx: RunContext[Any],
        /,
        *,
        call: ToolCallPart,
        tool_def: ToolDefinition,
        args: RawToolArgs,
        error: ValidationError | ModelRetry,
    ) -> ValidatedToolArgs:
        """Write the line of a call whose arguments failed validation, and pass on the error. The
        arguments are not valid, so the line has no program."""
        self._note(call.tool_name, "", ToolOutcome.RETRY)
        raise error
