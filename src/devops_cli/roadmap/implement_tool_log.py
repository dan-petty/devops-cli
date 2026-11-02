"""The log of the tool calls of a step (#2758).

A step that stops discards its checkout, so the Job log is the only evidence of what the agent
did. `ToolCallLog` is a pydantic-ai `Hooks` capability. It writes one line to the standard error
stream for each tool call: the tool name, the program of a shell command, and the outcome. A call
that has a command writes one more line before it runs, with the program and its first arguments
(#2806), so a call that the kernel kills leaves its cause in the log. `logged_command` masks that
command, bounds it and escapes it to one line. The line after the call holds no argument, no file
content, no output and no text of a refusal, as an argument can hold a path or a secret and the
text of one refusal repeats the whole command. A retry is the one exception (#2866): its line
holds the reason that the tool returned, which `logged_reason` masks, escapes and cuts, as that
reason is the only evidence of why a tool kept refusing a call. The reason shows the `path`
argument of the call only when the checkout holds that path, as the model chose the text of the
argument. A refusal by policy and a failed validation have no reason. The program is the
first word of the command, as the shell reads it, and only when it is a program that the project
knows: a program of the allowlist, or a program of the table of replacements (#2773). Any other
first word is written as "other", also a short bare word, as the model can read a password or a
token from a file and run it as a command. The tool name and the program tell a refused program
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
from collections import Counter, deque
from collections.abc import Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
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

from devops_cli.config.constants import (
    CONST_ROADMAP_IMPLEMENT_LOG_COMMAND_CHARS,
    CONST_ROADMAP_IMPLEMENT_LOG_COMMAND_READ_CHARS,
    CONST_ROADMAP_IMPLEMENT_LOG_COMMAND_WORDS,
    CONST_ROADMAP_IMPLEMENT_LOG_REASON_CHARS,
    CONST_ROADMAP_IMPLEMENT_REASON_PATHS,
    CONST_ROADMAP_IMPLEMENT_REFUSED_PROGRAMS,
    CONST_ROADMAP_IMPLEMENT_STOP_REASONS,
)
from devops_cli.lang import MESSAGES
from devops_cli.output import print_muted
from devops_cli.roadmap.agent_run import bounded_text
from devops_cli.roadmap.implement_shell_policy import (
    IMPLEMENT_ALLOWED_PROGRAMS,
    IMPLEMENT_SHELL_REPLACEMENTS,
)
from devops_cli.security.sanitizer import sanitize_command_args_for_display

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


def _logged_word(word: str) -> str:
    """What the log shows of one argument. The mask of secrets finds a secret by its form, and
    the value of `name=value` has none, so the line keeps the name and hides the value, except for
    a number such as `--numprocesses=48`. A word with a space is free text, such as a message of a
    commit, and the line hides it (#2806)."""
    name, separator, value = word.partition("=")
    if any(char.isspace() for char in name):
        return MESSAGES.roadmap.implement_tool_masked
    if separator and name and value and not value.isdecimal():
        return f"{name}={MESSAGES.roadmap.implement_tool_masked}"
    return word


def _logged_words(words: list[str]) -> list[str]:
    """The words through `_logged_word`, then through the mask of secrets for the words that
    `_logged_word` left as they were. The mask of secrets reads a flag and its next word, such as
    `--password hunter2`, and it never rewrites the name of a word that `_logged_word` masked."""
    masked = sanitize_command_args_for_display(words)
    return [
        shown if (shown := _logged_word(word)) != word else other
        for word, other in zip(words, masked, strict=True)
    ]


def logged_command(args: ValidatedToolArgs) -> str:
    """What the log shows of a command before the call runs (#2806): the first word and the words
    after it, at most `CONST_ROADMAP_IMPLEMENT_LOG_COMMAND_WORDS`, through `_logged_words`, with
    control characters escaped and the text cut to `CONST_ROADMAP_IMPLEMENT_LOG_COMMAND_CHARS`.
    Empty when the call has no command word. The word "other" when the first word is no known
    program: it can be a password or a token, and the words after it mean nothing without it. Each
    word is read to a fixed length before the mask, so that the cut cannot split a secret."""
    word = command_word(args)
    if word is None:
        return ""
    if word not in _KNOWN_PROGRAMS:
        return MESSAGES.roadmap.implement_tool_other
    words = shlex.split(str(args["command"]))
    shown = _logged_words(
        [
            argument[:CONST_ROADMAP_IMPLEMENT_LOG_COMMAND_READ_CHARS]
            for argument in words[:CONST_ROADMAP_IMPLEMENT_LOG_COMMAND_WORDS]
        ]
    )
    escaped = " ".join(shown).encode("unicode_escape").decode("ascii")
    cut = (
        len(words) > CONST_ROADMAP_IMPLEMENT_LOG_COMMAND_WORDS
        or len(escaped) > CONST_ROADMAP_IMPLEMENT_LOG_COMMAND_CHARS
    )
    return escaped[:CONST_ROADMAP_IMPLEMENT_LOG_COMMAND_CHARS] + (
        MESSAGES.roadmap.implement_tool_cut if cut else ""
    )


def retry_text(error: BaseException) -> str:
    """The message of the `ModelRetry` behind `error` (#2866): the content of the `ToolRetryError`
    that pydantic-ai makes of it, or the retry in the cause chain of the error that ends the run
    when a tool exceeds its retries. Empty when the content is no string: the content of a failed
    validation is a list of errors, and each holds the input of the model."""
    cause: BaseException | None = error
    while cause is not None:
        if isinstance(cause, ToolRetryError):
            content = cause.tool_retry.content
            return content if isinstance(content, str) else ""
        if isinstance(cause, ModelRetry):
            return cause.message
        cause = cause.__cause__
    return ""


def checkout_path(root: Path | None, path: str) -> str:
    """The path that `path` names inside the checkout `root`, relative to it, or empty when it names
    no file or directory there: a path that does not exist, one that leaves the root, and any path
    when there is no root. The `path` argument is text that the model chose, so it can be a password
    or a token that the mask of secrets cannot find. Only a path that the checkout holds is safe to
    show, and the text shown is the one that the file system gives."""
    if root is None or not (candidate := root / path).exists():
        return ""
    base = root.resolve()
    resolved = candidate.resolve()
    return resolved.relative_to(base).as_posix() if resolved.is_relative_to(base) else ""


def _escaped(text: str) -> str:
    """`text` masked and cut to a fixed length by `bounded_text`, then escaped to one line."""
    return bounded_text(text).encode("unicode_escape").decode("ascii")


def _cut(text: str, limit: int) -> str:
    """`text`, or its first `limit` characters and the mark of a cut when it is longer."""
    if len(text) <= limit:
        return text
    return text[:limit] + MESSAGES.roadmap.implement_tool_cut


def logged_reason(error: BaseException, args: ValidatedToolArgs, root: Path | None = None) -> str:
    """What the log shows of the reason that a tool returned with a retry (#2866): its message,
    with the `path` argument after it when the message lacks the path, masked, escaped to one line
    and cut to `CONST_ROADMAP_IMPLEMENT_LOG_REASON_CHARS`. The path always shows: the cut takes the
    end of the message, not the path. The path shows only when it names a file or a directory of the
    checkout `root` (`checkout_path`). Any other path is text that the model chose, so every place
    that the message names it shows "<path>" instead, and no path follows the message. Empty for a
    refusal by policy, as its text repeats the command or names a path outside the root, and for a
    message that is no string. A message of the file tools holds a path, a pattern, a count or a
    hash, and no content of a file, so the text of the model's `old_text` never shows."""
    if is_policy_refusal(error) or not (text := retry_text(error)):
        return ""
    texts = MESSAGES.roadmap
    path = args.get("path")
    shown = ""
    if isinstance(path, str) and path:
        shown = checkout_path(root, path)
        text = text.replace(path, shown or texts.implement_tool_path_hidden)
    limit = CONST_ROADMAP_IMPLEMENT_LOG_REASON_CHARS
    suffix = ""
    if shown and shown not in text:
        suffix = " " + _cut(_escaped(texts.implement_tool_reason_path.format(path=shown)), limit)
    return _cut(_escaped(text), max(limit - len(suffix), 0)) + suffix


@dataclass
class ToolCallLog:
    """The counters of one step, and the hooks that fill them. `refused` counts the refused shell
    commands by program, and `retried` the other retries, over all turns of the step. `reasons`
    holds the last reasons of the retries of each tool (#2866), and `ended_on` the tool whose
    retries ended the run. `root` is the checkout: a reason shows the `path` argument of a call
    only when the checkout holds that path. A log with no root shows no path."""

    root: Path | None = None
    refused: Counter[str] = field(default_factory=Counter[str])
    retried: int = 0
    reasons: dict[str, deque[str]] = field(default_factory=dict[str, deque[str]])
    ended_on: str = ""
    removed: list[str] = field(default_factory=list[str])

    def removed_strays(self, names: Sequence[str]) -> None:
        """Keep the names of the stray files that the step deleted (#3092), masked and cut as the
        text of an error is, and write one line to the Job log that names them."""
        if not names:
            return
        self.removed.extend(bounded_text(name) for name in names)
        line = MESSAGES.roadmap.implement_tool_stray.format(paths=self.removed_text(names))
        print_muted(line, to_stderr=True, safe=True)

    def removed_text(self, names: Sequence[str] | None = None) -> str:
        """The deleted stray files on one line: `names`, or all of them when there is no `names`.
        The text is masked and escaped. It lists at most `CONST_ROADMAP_IMPLEMENT_REASON_PATHS`
        names, then the count of the rest."""
        shown = [_escaped(name) for name in (self.removed if names is None else names)]
        limit = CONST_ROADMAP_IMPLEMENT_REASON_PATHS
        text = ", ".join(shown[:limit])
        if len(shown) > limit:
            text += MESSAGES.roadmap.implement_paths_more.format(count=len(shown) - limit)
        return text

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

    def retries_text(self) -> str:
        """The last reasons of the tool that exceeded its retries, for the reason of a stop
        (#2866), or empty when no tool did or the tool gave no reason."""
        if not (reasons := self.reasons.get(self.ended_on)):
            return ""
        return MESSAGES.roadmap.implement_stop_retries.format(
            tool=self.ended_on,
            reasons=MESSAGES.roadmap.implement_stop_reasons_separator.join(reasons),
        )

    def hooks(self) -> Hooks[None]:
        """The capability for the agent of the step."""
        return Hooks(tool_execute=self._execute, tool_validate_error=self._invalid)

    def _note(self, tool: str, program: str, outcome: ToolOutcome, reason: str = "") -> None:
        """Count a refusal or a retry, keep its reason, and write the line of the call."""
        if outcome is ToolOutcome.REFUSED:
            self.refused[program] += 1
        self.retried += outcome is ToolOutcome.RETRY
        texts = MESSAGES.roadmap
        if reason:
            self.reasons.setdefault(
                tool, deque(maxlen=CONST_ROADMAP_IMPLEMENT_STOP_REASONS)
            ).append(reason)
        ended = (
            texts.implement_tool_reason.format(outcome=outcome, reason=reason)
            if reason
            else outcome
        )
        line = (
            texts.implement_tool_line_program.format(tool=tool, program=program, outcome=ended)
            if program
            else texts.implement_tool_line.format(tool=tool, outcome=ended)
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
            if isinstance(error, UnexpectedModelBehavior):
                self.ended_on = call.tool_name
            self._note(
                call.tool_name,
                program,
                ToolOutcome.REFUSED if refused else ToolOutcome.RETRY,
                logged_reason(error, args, self.root),
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
