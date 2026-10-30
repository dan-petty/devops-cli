"""The log of the tool calls of a step (#2758).

A step that stops discards its checkout, so the Job log is the only evidence of what the agent
did. `ToolCallLog` is a pydantic-ai `Hooks` capability. It writes one line to the standard error
stream for each tool call: the tool name, the program of a shell command, and the outcome. A line
holds no other argument, no file content, no output and no text of a refusal, as an argument can
hold a path or a secret and the text of one refusal repeats the whole command. The program is the
first word of the command, as the shell reads it, and only when it is a bare word: letters, digits,
`_`, `.` and `-`, from a letter, in 24 characters at most, that the mask of secrets leaves as it is
(#2773). Any other first word, such as an assignment with a secret in it or a path, is written as
"other". The line has no reason for a refusal. The tool name and the program tell a refused program
from a refused path.

It also counts the shell commands that the shell refused by its policy, by program, and the calls
that came back as a retry for another cause. A refusal of a file tool, such as a path outside the
root, is an other retry. The reason of a stopped step holds both counts, so a person sees at once
which program the model kept asking for.

The line goes to the console stream, not to `logging`: a `devops` process has no handler for the
level INFO, so such a line would never reach the Job log.
"""

from __future__ import annotations

import re
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

from devops_cli.config.constants import CONST_ROADMAP_IMPLEMENT_REFUSED_PROGRAMS
from devops_cli.lang import MESSAGES
from devops_cli.output import print_muted
from devops_cli.security.sanitizer import mask_secrets

# A program that the log may show: the shell reads it as one word, and it holds no path, no quote,
# no space and no assignment.
_BARE_WORD = re.compile(r"[A-Za-z][A-Za-z0-9_.-]{0,23}")


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
    """What the log shows for the first word of a command: the word when it is a bare word that
    the mask of secrets leaves as it is, else the word "other". Empty when there is no word. A first
    word can be an assignment with a secret in it, or a path, or an escape sequence, so no other
    word is written."""
    if word is None:
        return ""
    if _BARE_WORD.fullmatch(word) and mask_secrets(word) == word:
        return word
    return MESSAGES.roadmap.implement_tool_other


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
