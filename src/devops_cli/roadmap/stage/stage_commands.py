"""`devops roadmap stage`: check cited devops commands, options and MCP exposure table keys (#3302).

A plan that cites a `devops` command line in Feasibility or tasks is checked against the Click
command tree with `resolve_devops_argv`, without running any command. An unknown command, an
unknown option flag or an unexpected extra argument is refused. A code span marks where its
command ends. A command cited in a sentence ends at the first word that the command tree does not
take (`cited_command_length`, #4956), so the English words after it are no arguments. A quoted
tuple key cited in Feasibility or tasks, in a sentence that names the exposure table, is checked
against `CONST_MCP_EXPOSURE_TABLE` and refused when absent.
"""

from __future__ import annotations

import ast
import re
import shlex
from collections.abc import Iterator
from itertools import takewhile
from typing import TYPE_CHECKING, Final

from devops_cli.config.constants import CONST_MCP_EXPOSURE_TABLE
from devops_cli.core.command_resolver import (
    ArgvPlaceholder,
    ArgvToken,
    cited_command_length,
    resolve_devops_argv,
)
from devops_cli.lang.en.messages import MESSAGES

if TYPE_CHECKING:
    from devops_cli.roadmap.stage.stage_change import StageProposal

_EXPOSURE_KEYS: Final[frozenset[tuple[str, ...]]] = frozenset(
    entry[0] for entry in CONST_MCP_EXPOSURE_TABLE
)
_QUOTED_TUPLE: Final[re.Pattern[str]] = re.compile(
    r"\(\s*(?:(?:'[^']*'|\"[^\"]*\")\s*,\s*)+(?:'[^']*'|\"[^\"]*\")?\s*\)"
)
# The words that tie a quoted tuple to the MCP exposure table (#4255).
_EXPOSURE_CONTEXT: Final[re.Pattern[str]] = re.compile(
    r"CONST_MCP_EXPOSURE_TABLE|exposure[ _-]table", re.IGNORECASE
)
# The end of a sentence: a full stop, a question mark or an exclamation mark, then a space or the end.
_SENTENCE_BREAK: Final[re.Pattern[str]] = re.compile(r"[.!?](?:\s|$)")
_CODE_SPAN: Final[re.Pattern[str]] = re.compile(r"`([^`]+)`")
_SHELL_OPERATORS: Final[frozenset[str]] = frozenset(";|><&")
# The start of a command cited in a sentence: `uv run devops` anywhere, or `devops` that opens the
# text. A bare `devops` inside a sentence names the project, not a command.
_PROSE_COMMAND_START: Final[re.Pattern[str]] = re.compile(
    r"\A\s*(?:!\s+)?devops(?=\s)|\buv\s+run\s+devops(?![\w-])"
)
# The end of a sentence or a line, after which a cited command holds no more words.
_PROSE_COMMAND_END: Final[re.Pattern[str]] = re.compile(rf"{_SENTENCE_BREAK.pattern}|\n")


def _is_operator(word: str) -> bool:
    """Whether `word` is a shell operator that ends a command."""
    return bool(word) and set(word) <= _SHELL_OPERATORS


def _clean_word(word: str) -> str:
    """Strip trailing prose punctuation from `word`."""
    if len(word) > 1 and not (word.startswith("<") and word.endswith(">")):
        return word.rstrip(".,;:)]}")
    return word


def _is_placeholder(word: str) -> bool:
    """Whether `word` is a placeholder for an argument or value."""
    return (
        "$" in word
        or word.startswith(("<", "["))
        or word.endswith((">", "]", "..."))
        or word.isupper()
    )


def _argv_token(word: str) -> ArgvToken:
    """Convert `word` to an `ArgvToken`, wrapping a placeholder in `ArgvPlaceholder`."""
    cleaned = _clean_word(word)
    return ArgvPlaceholder(expression=cleaned) if _is_placeholder(cleaned) else cleaned


def _shell_words(line: str) -> list[str]:
    """Split `line` into words using shell syntax, falling back to whitespace split."""
    try:
        return list(shlex.split(line))
    except ValueError:
        return line.split()


def _proposal_citation_texts(proposal: StageProposal) -> list[str]:
    """The texts of `proposal` that hold Feasibility and task descriptions."""
    texts: list[str] = list(proposal.feasibility)
    for group in proposal.groups:
        for field_name in ("title", "test", "implementation", "documentation", "process"):
            value = getattr(group, field_name, None)
            if value:
                texts.append(value)
    return texts


def _command_words(words: list[str]) -> list[str]:
    """The words of `words` up to the first shell operator, which ends a command."""
    return list(takewhile(lambda word: not _is_operator(word), words))


def _code_span_commands(span: str) -> Iterator[tuple[str, list[str]]]:
    """Each devops command in the code span `span`: its prefix and all the words after `devops`."""
    words = _shell_words(span)
    for idx, word in enumerate(words):
        if word == "devops":
            start = idx - 2 if idx >= 2 and words[idx - 2 : idx] == ["uv", "run"] else idx
            yield " ".join(words[start : idx + 1]), _command_words(words[idx + 1 :])


def _prose_commands(text: str) -> Iterator[tuple[str, list[str]]]:
    """Each devops command that `text` cites in a sentence: its prefix and the words after
    `devops` that the command tree lists (#4956). A command ends at the next cited command too."""
    starts = list(_PROSE_COMMAND_START.finditer(text))
    for index, match in enumerate(starts):
        stop = starts[index + 1].start() if index + 1 < len(starts) else len(text)
        end = _PROSE_COMMAND_END.search(text, match.end(), stop)
        words = _command_words(_shell_words(text[match.end() : end.start() if end else stop]))
        length = cited_command_length([_clean_word(word) for word in words])
        prefix = " ".join(word for word in match.group(0).split() if word != "!")
        yield prefix, words[:length]


def _cited_commands(text: str) -> Iterator[tuple[str, list[str]]]:
    """Each devops command cited in `text`: from its code spans when one names `devops`, else
    from its sentences."""
    code_spans = [m.group(1).strip() for m in _CODE_SPAN.finditer(text)]
    devops_code_spans = [cs for cs in code_spans if "devops" in cs]
    if not devops_code_spans:
        return _prose_commands(text)
    return (command for span in devops_code_spans for command in _code_span_commands(span))


def _command_problem(prefix: str, words: list[str]) -> str | None:
    """The problem of the cited command `<prefix> <words>`, or None when it resolves."""
    finding = resolve_devops_argv([_argv_token(word) for word in words])
    if finding is None:
        return None
    return MESSAGES.roadmap.stage_problem_command_reference.format(
        command=" ".join([prefix, *words]), problem=finding.describe()
    )


def _sentence_around(text: str, start: int, end: int) -> str:
    """The sentence of `text` that holds the span from `start` to `end`."""
    left, right = 0, len(text)
    for found in _SENTENCE_BREAK.finditer(text):
        if found.end() <= start:
            left = found.end()
        elif found.start() >= end:
            right = found.start()
            break
    return text[left:right]


def _mcp_exposure_problems(text: str) -> Iterator[str]:
    """Find quoted tuples in `text` and check against `CONST_MCP_EXPOSURE_TABLE`. A quoted tuple is
    a common literal (a fixture table, a parameter list), so only a tuple in a sentence that names
    the exposure table is a cited key (#4255)."""
    for match in _QUOTED_TUPLE.finditer(text):
        if not _EXPOSURE_CONTEXT.search(_sentence_around(text, match.start(), match.end())):
            continue
        raw = match.group(0)
        try:
            parsed = ast.literal_eval(raw)
        except SyntaxError, ValueError:
            continue
        if isinstance(parsed, tuple) and all(isinstance(x, str) for x in parsed):
            if parsed not in _EXPOSURE_KEYS:
                yield MESSAGES.roadmap.stage_problem_mcp_exposure_key.format(key=raw)


def command_citation_problems(proposal: StageProposal) -> list[str]:
    """The problems of commands, options and MCP exposure table keys cited in `proposal` (#3302)."""
    problems: list[str] = []
    for text in _proposal_citation_texts(proposal):
        for prefix, words in _cited_commands(text):
            if problem := _command_problem(prefix, words):
                problems.append(problem)
        problems.extend(_mcp_exposure_problems(text))
    return list(dict.fromkeys(problems))
