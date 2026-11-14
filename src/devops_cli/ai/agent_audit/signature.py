"""Reduce a command and the failure that answered it to one signature (#2346).

A signature is the key of a finding. The audit counts one finding for each signature across the
sessions, so two runs of one command with another path or another number count as one problem,
and a failure of another exit status or another first error line counts as another problem.

A signature is also what reaches the stored counts, the report and the model, so each text passes
through `sanitize_text` first: a secret, a private host name and an email address never reach it
(#2346, AGENTS.md rule 10).
"""

from __future__ import annotations

import re
import shlex
from collections.abc import Sequence
from itertools import pairwise

from devops_cli.ai.agent_audit.transcript import ToolCall, sanitize_text

# The placeholders of a signature. A path, a number and the value of a flag differ between two
# runs of one problem, so each becomes a placeholder of its own.
_PATH = "<path>"
_NUMBER = "<n>"
_VALUE = "<value>"
_UNKNOWN_STATUS = "<unknown>"
# A signature stays bounded: a session can run a script of hundreds of words, and the signature
# reaches a model request and a stored file. Two long commands that share these words count as one
# problem, which is what a recurring-problem count asks for.
_MAX_WORDS = 24
# The line that the shell tool writes for the status of a command, as `Exit code 1`.
_EXIT_CODE_RE = re.compile(r"Exit code (\d+)")
# A word that is a number, with the sign of a counted flag, as the `-5` of `git log -5`.
_NUMBER_RE = re.compile(r"-?\d+")


def command_signature(text: str) -> str:
    """The signature of a command: its program, its subcommands and its flags (#2346).

    A path, a number and the value of a flag become a placeholder, so two runs of one command
    share a signature. A word of digits is a number only when it is the whole word: `k8s` is a
    subcommand of `devops`, and a word such as `python3.12` names a program.
    """
    words = _words(sanitize_text(text))
    if not words:
        return ""
    rest = (_command_word(word, previous) for previous, word in pairwise(words))
    return _bounded([words[0], *rest])


def error_signature(exit_status: int | None, first_error_line: str) -> str:
    """The signature of a failure: its exit status and its normalized first error line (#2346).

    `exit_status` is None when the tool result names no status. The signature then says that the
    status is unknown rather than giving a code that no tool result holds.
    """
    status = _UNKNOWN_STATUS if exit_status is None else str(exit_status)
    line = _normalized_line(first_error_line)
    return f"exit {status}: {line}" if line else f"exit {status}"


def first_error_line(output: str) -> str:
    """The first line of an output that is not the line of the exit status (#2346).

    The shell tool writes the status above the output, so the line below it is the first line
    that the command printed, which is the error of a failed command.
    """
    for line in output.splitlines():
        stripped = line.strip()
        if stripped and _EXIT_CODE_RE.match(stripped) is None:
            return stripped
    return ""


def tool_result_exit_status(output: str, is_error: bool) -> int | None:
    """The exit status of the command that a tool result answered (#2346).

    The reader keeps the `is_error` flag of the `tool_result` block. A result that the tool does
    not mark as an error answered a command that succeeded, so its status is 0. A failed result
    names its status on a line of its own; a failed result that names none keeps None.
    """
    if not is_error:
        return 0
    return _named_exit_status(output)


def call_signature(call: ToolCall) -> str:
    """The signature of one tool call: its command, and the failure that answered it (#2346)."""
    command = command_signature(call.command)
    if not call.is_error:
        return command
    status = tool_result_exit_status(call.output, is_error=True)
    return f"{command} | {error_signature(status, first_error_line(call.output))}"


def _command_word(word: str, previous: str) -> str:
    """A word of a command, with its number, its path or its flag value replaced."""
    if word.startswith("-"):
        return _flag(word)
    if _NUMBER_RE.fullmatch(word):
        return _NUMBER
    if _is_path(word):
        return _PATH
    if previous.startswith("-") and "=" not in previous:
        return _VALUE
    return word


def _flag(word: str) -> str:
    """A flag as written, with its inline value or its count replaced."""
    name, separator, _value = word.partition("=")
    if separator:
        return f"{name}={_VALUE}"
    if _NUMBER_RE.fullmatch(word):
        return _NUMBER
    return word


def _plain_word(word: str) -> str:
    """A word of free text, with its number or its path replaced."""
    if _NUMBER_RE.fullmatch(word):
        return _NUMBER
    if _is_path(word):
        return _PATH
    return word


def _normalized_line(text: str) -> str:
    """A line of free text in lower case, with its numbers and paths replaced."""
    return _bounded([_plain_word(word) for word in _words(sanitize_text(text).lower())])


def _named_exit_status(output: str) -> int | None:
    """The exit status that an output names, or None when it names none."""
    for line in output.splitlines():
        match = _EXIT_CODE_RE.search(line)
        if match is not None:
            return int(match.group(1))
    return None


def _is_path(word: str) -> bool:
    """Whether a word names a file or a directory rather than a word of a command."""
    return "/" in word or "\\" in word or word.startswith((".", "~"))


def _words(text: str) -> list[str]:
    """The words of a text as the shell reads them, or as the text splits them when it cannot."""
    try:
        return shlex.split(text)
    except ValueError:
        return text.split()


def _bounded(words: Sequence[str]) -> str:
    """The words joined, cut to the bound of a signature with a mark that it was cut."""
    if len(words) <= _MAX_WORDS:
        return " ".join(words)
    return " ".join([*words[:_MAX_WORDS], "..."])
