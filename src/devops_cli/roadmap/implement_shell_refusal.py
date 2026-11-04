"""The refusal of the shell tool of an implement step names the replacement (#2773, #3271).

The shell of `pydantic-ai-harness` refuses a program outside the allowlist with a fixed text, such
as "Command 'python' is not in the allowed list.", and the harness has no setting for that text.
The harness raises the text as a `ModelRetry`, and the tool manager of pydantic-ai counts that
raise against the retry limit of the tool before any hook sees it. A model that does not know what
to run in its place would be refused until the step stops, for a refusal is no failure of the
tool. `ShellRefusal` is a pydantic-ai capability that wraps the toolset. It catches the refusal in
the toolset, so no retry is counted, and returns the text of the shell with the replacement after
it as a normal tool result. The retry count of a tool is of failures in a row, so a real failure
of a tool still counts. It also refuses a command whose program is in `SHELL_PROGRAMS` and whose
words hold a refused argument, such as `find -exec` (#3072). It adds only text from the table
`IMPLEMENT_SHELL_REPLACEMENTS` and from the messages, never a word of the command. It cuts the text
of the shell to `CONST_ROADMAP_RUN_ERROR_CHARS`, as the text echoes the first word of the command,
or the whole command for an interactive one, with no limit. It tells the log of the step about
each refusal, and the log counts it and ends the step at `CONST_ROADMAP_IMPLEMENT_MAX_REFUSALS`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pydantic_ai import RunContext
from pydantic_ai.capabilities import AbstractCapability
from pydantic_ai.exceptions import ModelRetry
from pydantic_ai.toolsets import AbstractToolset, WrapperToolset
from pydantic_ai.toolsets.abstract import ToolsetTool

from devops_cli.config.constants import CONST_ROADMAP_RUN_ERROR_CHARS
from devops_cli.lang import MESSAGES
from devops_cli.roadmap.implement_shell_policy import (
    IMPLEMENT_SHELL_PROGRAMS,
    IMPLEMENT_SHELL_REPLACEMENTS,
    refused_argument,
)
from devops_cli.roadmap.implement_tool_log import ToolCallLog, command_word


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


@dataclass
class _RefusingToolset(WrapperToolset[None]):
    """The toolset of the agent, with the refusals of a command returned as tool results."""

    log: ToolCallLog

    async def call_tool(
        self, name: str, tool_args: dict[str, Any], ctx: RunContext[None], tool: ToolsetTool[None]
    ) -> Any:
        """Run the call. A command with a refused argument, and a command that the shell refuses
        by policy (a `PermissionError` is the cause of its `ModelRetry`), come back as text and
        are noted in the log. Any other result or error passes on."""
        command = tool_args.get("command")
        if isinstance(command, str) and (found := refused_argument(command)) is not None:
            program, argument = found
            return self._refused(
                ctx,
                MESSAGES.roadmap.implement_refusal_argument.format(
                    program=program.name, argument=argument, instead=program.argument_instead
                ),
            )
        try:
            return await self.wrapped.call_tool(name, tool_args, ctx, tool)
        except ModelRetry as retry:
            word = command_word(tool_args)
            if word is None or not isinstance(retry.__cause__, PermissionError):
                raise
            shown = retry.message[:CONST_ROADMAP_RUN_ERROR_CHARS]
            return self._refused(ctx, f"{shown} {refusal_hint(word)}")

    def _refused(self, ctx: RunContext[None], text: str) -> str:
        """`text`, after the log has noted that this call was refused."""
        self.log.refuse(ctx.tool_call_id)
        return text


@dataclass
class ShellRefusal(AbstractCapability[None]):
    """The capability that returns a refusal of the shell as a tool result with the hint. It adds
    no tool retry. `log` counts the refusals and ends the step when they pass the limit."""

    log: ToolCallLog

    def get_wrapper_toolset(self, toolset: AbstractToolset[None]) -> AbstractToolset[None]:
        return _RefusingToolset(toolset, self.log)
