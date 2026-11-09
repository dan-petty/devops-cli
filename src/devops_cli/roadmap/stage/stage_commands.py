"""`devops roadmap stage`: check cited devops commands, options and MCP exposure table keys (#3302).

A plan that cites a `devops` command line in Feasibility or tasks is checked against the Click
command tree with `resolve_devops_argv`, without running any command. An unknown command, an
unknown option flag or an unexpected extra argument is refused. A quoted tuple key cited in
Feasibility or tasks is checked against `CONST_MCP_EXPOSURE_TABLE` and refused when absent.
"""

from __future__ import annotations

import ast
import re
import shlex
from collections.abc import Iterator
from itertools import takewhile
from typing import TYPE_CHECKING, Final

from devops_cli.config.constants import CONST_MCP_EXPOSURE_TABLE
from devops_cli.core.command_resolver import ArgvPlaceholder, ArgvToken, resolve_devops_argv
from devops_cli.lang.en.messages import MESSAGES

if TYPE_CHECKING:
    from devops_cli.roadmap.stage.stage_change import StageProposal

_EXPOSURE_KEYS: Final[frozenset[tuple[str, ...]]] = frozenset(
    entry[0] for entry in CONST_MCP_EXPOSURE_TABLE
)
_QUOTED_TUPLE: Final[re.Pattern[str]] = re.compile(
    r"\(\s*(?:(?:'[^']*'|\"[^\"]*\")\s*,\s*)+(?:'[^']*'|\"[^\"]*\")?\s*\)"
)
_CODE_SPAN: Final[re.Pattern[str]] = re.compile(r"`([^`]+)`")
_SHELL_OPERATORS: Final[frozenset[str]] = frozenset(";|><&")
_COMMAND_PREFIXES: Final[tuple[str, ...]] = (
    "uv run devops",
    "devops ",
    "! uv run devops",
    "! devops ",
)
_COMMAND_PROSE_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"\b(?:!\s+)?uv\s+run\s+devops\b[^\n.!?]*"
)


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


def _command_spans(text: str) -> list[str]:
    """Find all devops command spans in `text`."""
    code_spans = [m.group(1).strip() for m in _CODE_SPAN.finditer(text)]
    devops_code_spans = [cs for cs in code_spans if "devops" in cs]
    if devops_code_spans:
        return devops_code_spans
    trimmed = text.strip()
    if trimmed.startswith(_COMMAND_PREFIXES):
        return [trimmed]
    spans: list[str] = []
    for match in _COMMAND_PROSE_PATTERN.finditer(text):
        cmd = match.group(0).strip()
        if cmd:
            spans.append(cmd)
    return spans


def _resolve_command_span(span: str) -> Iterator[str]:
    """Check each devops command in `span` and yield any problem."""
    words = _shell_words(span)
    for idx, word in enumerate(words):
        if word == "devops":
            raw_tokens = list(takewhile(lambda w: not _is_operator(w), words[idx + 1 :]))
            tokens = [_argv_token(w) for w in raw_tokens]
            finding = resolve_devops_argv(tokens)
            if finding is not None:
                start = idx - 2 if idx >= 2 and words[idx - 2 : idx] == ["uv", "run"] else idx
                cmd_str = " ".join(words[start : idx + 1 + len(raw_tokens)])
                yield MESSAGES.roadmap.stage_problem_command_reference.format(
                    command=cmd_str,
                    problem=finding.describe(),
                )


def _mcp_exposure_problems(text: str) -> Iterator[str]:
    """Find quoted tuples in `text` and check against `CONST_MCP_EXPOSURE_TABLE`."""
    for match in _QUOTED_TUPLE.finditer(text):
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
        for span in _command_spans(text):
            problems.extend(_resolve_command_span(span))
        problems.extend(_mcp_exposure_problems(text))
    return list(dict.fromkeys(problems))
