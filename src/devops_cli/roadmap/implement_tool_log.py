"""The log of the tool calls of a step (#2758).

A step that stops discards its checkout, so the Job log is the only evidence of what the agent
did. `ToolCallLog` is a pydantic-ai `Hooks` capability. It writes one line to the standard error
stream for each tool call: the tool name, the first word of a shell command, and the outcome. A
line holds no other argument, no file content, no output and no text of a refusal, as an argument
can hold a path or a secret and the text of one refusal repeats the whole command.

It also counts the calls that a tool refused by its policy and the calls that came back as a
retry for another cause. The reason of a stopped step holds both counts, so a person sees at once
that the model kept asking for a program that the shell refuses.

The line goes to the console stream, not to `logging`: a `devops` process has no handler for the
level INFO, so such a line would never reach the Job log.
"""

from __future__ import annotations

from dataclasses import dataclass
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

from devops_cli.config.constants import CONST_ROADMAP_IMPLEMENT_PROGRAM_CHARS
from devops_cli.security.sanitizer import mask_secrets


class ToolOutcome(StrEnum):
    """How a tool call ended: it returned, the tool refused it by its policy, it came back as
    another retry, or the tool reported a failed call."""

    OK = "ok"
    REFUSED = "refused"
    RETRY = "retry"
    FAILED = "failed"


def _refused(error: BaseException) -> bool:
    """Whether a `PermissionError` is in the cause chain of `error`: the shell of the harness
    raises its refusals as a `ModelRetry` from a `PermissionError`, and pydantic-ai raises the
    retry error from that."""
    cause = error.__cause__
    while cause is not None:
        if isinstance(cause, PermissionError):
            return True
        cause = cause.__cause__
    return False


def _program(args: ValidatedToolArgs) -> str:
    """The first word of the `command` argument of a call, masked and cut, or empty when the call
    has none."""
    command = args.get("command")
    words = command.split(maxsplit=1) if isinstance(command, str) else []
    return mask_secrets(words[0])[:CONST_ROADMAP_IMPLEMENT_PROGRAM_CHARS] if words else ""


@dataclass
class ToolCallLog:
    """The counters of one step, and the hooks that fill them. `refused` and `retried` count the
    calls over all turns of the step."""

    refused: int = 0
    retried: int = 0

    def hooks(self) -> Hooks[None]:
        """The capability for the agent of the step."""
        return Hooks(tool_execute=self._execute, tool_validate_error=self._invalid)

    def _note(self, tool: str, program: str, outcome: ToolOutcome) -> None:
        """Count a refusal or a retry."""
        self.refused += outcome is ToolOutcome.REFUSED
        self.retried += outcome is ToolOutcome.RETRY

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
        program = _program(args)
        try:
            result = await handler(args)
        except (ToolRetryError, UnexpectedModelBehavior) as error:
            retry = ToolOutcome.REFUSED if _refused(error) else ToolOutcome.RETRY
            self._note(call.tool_name, program, retry)
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
