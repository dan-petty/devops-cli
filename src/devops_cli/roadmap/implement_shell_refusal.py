"""The refusal of the shell tool of an implement step names the replacement (#2773).

The shell of `pydantic-ai-harness` refuses a program outside the allowlist with a fixed text, such
as "Command 'python' is not in the allowed list.", and the harness has no setting for that text.
Each refusal counts against the retry limit of the tool, so a model that does not know what to run
in its place is refused until the step stops. `shell_refusal_hooks` is a pydantic-ai `Hooks`
capability that keeps the text of the shell and adds the replacement after it. It changes nothing
that the shell allows. It adds only text from the table `IMPLEMENT_SHELL_REPLACEMENTS` and from the
messages, never a word of the command. It cuts the text of the shell to
`CONST_ROADMAP_IMPLEMENT_ERROR_CHARS`, as the text echoes the first word of the command, or the
whole command for an interactive one, with no limit.
"""

from __future__ import annotations

from typing import Any

from pydantic_ai import RunContext
from pydantic_ai.capabilities import Hooks, ValidatedToolArgs, WrapToolExecuteHandler
from pydantic_ai.exceptions import ModelRetry, ToolRetryError
from pydantic_ai.messages import ToolCallPart
from pydantic_ai.tools import ToolDefinition

from devops_cli.config.commands import IMPLEMENT_SHELL_PROGRAMS, IMPLEMENT_SHELL_REPLACEMENTS
from devops_cli.config.constants import CONST_ROADMAP_IMPLEMENT_ERROR_CHARS
from devops_cli.lang import MESSAGES
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
    after the text of the tool, which is cut to a fixed length. The retry keeps the refusal in its cause chain, so the log of the
    step still counts it as refused. Any other result or error passes on."""
    try:
        return await handler(args)
    except ToolRetryError as error:
        word = command_word(args)
        text = error.tool_retry.content
        if word is None or not isinstance(text, str) or not is_policy_refusal(error):
            raise
        shown = text[:CONST_ROADMAP_IMPLEMENT_ERROR_CHARS]
        raise ModelRetry(f"{shown} {refusal_hint(word)}") from error


def shell_refusal_hooks() -> Hooks[None]:
    """The capability for the agent of the step."""
    return Hooks(tool_execute=_execute)
