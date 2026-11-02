"""The refusal of the shell tool of an implement step names the replacement (#2773).

The shell of `pydantic-ai-harness` refuses a program outside the allowlist with a fixed text, such
as "Command 'python' is not in the allowed list.", and the harness has no setting for that text.
Each refusal counts against the retry limit of the tool, so a model that does not know what to run
in its place is refused until the step stops. `shell_refusal_hooks` is a pydantic-ai `Hooks`
capability that keeps the text of the shell and adds the replacement after it. It also refuses a
command whose program is in `SHELL_PROGRAMS` and whose words hold a refused argument, such as
`find -exec` (#3072). It adds only text from the table `IMPLEMENT_SHELL_REPLACEMENTS` and from the
messages, never a word of the command. It cuts the text of the shell to
`CONST_ROADMAP_RUN_ERROR_CHARS`, as the text echoes the first word of the command, or the
whole command for an interactive one, with no limit.
"""

from __future__ import annotations

from typing import Any

from pydantic_ai import RunContext
from pydantic_ai.capabilities import Hooks, ValidatedToolArgs, WrapToolExecuteHandler
from pydantic_ai.exceptions import ModelRetry, ToolRetryError
from pydantic_ai.messages import RetryPromptPart, ToolCallPart
from pydantic_ai.tools import ToolDefinition

from devops_cli.config.constants import CONST_ROADMAP_RUN_ERROR_CHARS
from devops_cli.lang import MESSAGES
from devops_cli.roadmap.implement_shell_policy import (
    IMPLEMENT_SHELL_PROGRAMS,
    IMPLEMENT_SHELL_REPLACEMENTS,
    refused_argument,
)
from devops_cli.roadmap.implement_tool_log import command_word, is_policy_refusal


def refusal_hint(word: str) -> str:
    """What to run in place of the refused first word of a command. A word of the table gets its
    replacement. An allowed program was refused for an operator, so it gets the rule of one command
    in each call. Any other word gets the allowed programs and the `uv run` form."""
    texts = MESSAGES.roadmap
    if replacement := IMPLEMENT_SHELL_REPLACEMENTS.get(word):
        return texts.implement_refusal_replacement.format(program=word, replacement=replacement)
    if word in IMPLEMENT_SHELL_PROGRAMS:
        return texts.implement_refusal_operator
    programs = ", ".join(f"`{program}`" for program in IMPLEMENT_SHELL_PROGRAMS)
    return texts.implement_refusal_allowed.format(programs=programs)


class _ArgumentRefused(PermissionError):
    """The cause of the retry for a refused argument. It is a `PermissionError`, so the log counts
    the call as a refused command, and the hint hook knows the text already says what to run."""


def _has_cause(error: BaseException, kind: type[BaseException]) -> bool:
    cause = error.__cause__
    while cause is not None:
        if isinstance(cause, kind):
            return True
        cause = cause.__cause__
    return False


async def _refuse_argument(
    _ctx: RunContext[Any],
    /,
    *,
    call: ToolCallPart,
    tool_def: ToolDefinition,
    args: ValidatedToolArgs,
    handler: WrapToolExecuteHandler,
) -> Any:
    """Refuse a command whose program is in the table and whose words hold a refused argument. The
    harness reads the first word only, so the table is checked here. The hook sits inside the log of
    the step, and it raises the retry error that the tool manager makes of a `ModelRetry` of a tool,
    so the log sees it and counts the refusal."""
    command = args.get("command")
    if isinstance(command, str) and (found := refused_argument(command)) is not None:
        program, argument = found
        text = MESSAGES.roadmap.implement_refusal_argument.format(
            program=program.name, argument=argument, instead=program.argument_instead
        )
        retry = RetryPromptPart(
            content=text, tool_name=call.tool_name, tool_call_id=call.tool_call_id
        )
        raise ToolRetryError(retry) from _ArgumentRefused(text)
    return await handler(args)


async def _execute(
    _ctx: RunContext[Any],
    /,
    *,
    call: ToolCallPart,
    tool_def: ToolDefinition,
    args: ValidatedToolArgs,
    handler: WrapToolExecuteHandler,
) -> Any:
    """Run the call. A refusal by policy of a shell command comes back as a retry with the hint
    after the text of the tool, which is cut to a fixed length. The retry keeps the refusal in its
    cause chain, so the log of the step still counts it as refused. The refusal of an argument
    has its own text and gets no hint, but it comes back as a retry in the same way. Any other result or error passes on."""
    try:
        return await handler(args)
    except ToolRetryError as error:
        word = command_word(args)
        text = error.tool_retry.content
        if word is None or not isinstance(text, str) or not is_policy_refusal(error):
            raise
        if _has_cause(error, _ArgumentRefused):
            raise ModelRetry(text) from error
        shown = text[:CONST_ROADMAP_RUN_ERROR_CHARS]
        raise ModelRetry(f"{shown} {refusal_hint(word)}") from error


def shell_refusal_hooks() -> Hooks[None]:
    """The capability that adds the hint to a refusal of the shell. It goes before the log."""
    return Hooks(tool_execute=_execute)


def argument_refusal_hooks() -> Hooks[None]:
    """The capability that refuses an argument of the table. It goes after the log."""
    return Hooks(tool_execute=_refuse_argument)
