"""Read the code in Markdown documents: fences, code spans, headings, tables and the `devops` commands in them.

Documents are parsed with markdown-it-py's CommonMark parser, so a fence inside a list item or a
code span inside a table cell is found where a reader sees it, and a command line is split into
words and operators by the standard library's shell lexer (`shlex.shlex` with `punctuation_chars`),
as a POSIX shell splits it. The documents write values a reader fills in as placeholders
(`<session>`, `$R/b`, `[OPTIONS]`, `COMMAND`, `"..."`); each becomes an `ArgvPlaceholder`, which
`resolve_devops_argv` accepts wherever a value or a subcommand may go. Because the documents write
`<name>` for such a value, the lexer splits only the control operators' characters from the words
they touch; `<` and `>` stay inside a word, so a redirection ends a command only when it is spaced.
"""

from __future__ import annotations

import shlex
from collections.abc import Iterator
from functools import cache
from itertools import pairwise, takewhile
from pathlib import Path
from typing import NamedTuple

from markdown_it import MarkdownIt
from markdown_it.token import Token

from devops_cli.core.command_resolver import ArgvPlaceholder, ArgvToken

# The fences whose lines a shell would run; a fence with no language is read as one too.
SHELL_FENCE_LANGUAGES = frozenset({"", "bash", "sh", "shell", "zsh", "console", "shell-session"})
# The fences that hold YAML; the language is the first word of the fence's info string.
YAML_FENCE_LANGUAGES = frozenset({"yaml", "yml"})
# The characters a POSIX shell reads as operators, as the standard library's lexer lists them.
_SHELL_OPERATOR_CHARACTERS = frozenset(shlex.shlex(punctuation_chars=True).punctuation_chars)
# The ones the lexer splits from a word they touch: all but `<` and `>`, which `<session>` holds.
_SPLIT_OPERATOR_CHARACTERS = "".join(sorted(_SHELL_OPERATOR_CHARACTERS - set("<>")))
_PARSER = MarkdownIt("commonmark")
# CommonMark with GitHub's tables, which CommonMark itself does not have.
_TABLE_PARSER = MarkdownIt("commonmark").enable("table")


class CodeSnippet(NamedTuple):
    """Code a document shows: a shell fence's body or a code span, and the line it starts on."""

    line: int
    text: str
    fenced: bool


class Heading(NamedTuple):
    """A heading a document shows: the line it is on, its level (1 for `#`) and its text."""

    line: int
    level: int
    text: str


@cache
def _tokens(path: Path) -> tuple[Token, ...]:
    return tuple(_PARSER.parse(path.read_text(encoding="utf-8")))


def _fence_language(token: Token) -> str:
    return token.info.split(maxsplit=1)[0] if token.info.strip() else ""


def _line(token: Token) -> int:
    return (token.map[0] if token.map else 0) + 1


def fences(path: Path, languages: frozenset[str]) -> list[CodeSnippet]:
    """Every fence in the document written in one of `languages`, with the line its body starts on.

    A fence is in a language when that is the first word of its info string, so
    ```` ```yml title=x ```` is `yml`.
    """
    return [
        CodeSnippet(_line(token) + 1, token.content, True)
        for token in _tokens(path)
        if token.type == "fence" and _fence_language(token) in languages
    ]


def headings(path: Path) -> list[Heading]:
    """Every heading in the document, in order, with the line it is on."""
    return [
        Heading(_line(opening), int(opening.tag.removeprefix("h")), title.content)
        for opening, title in pairwise(_tokens(path))
        if opening.type == "heading_open"
    ]


def tables(path: Path) -> list[list[list[str]]]:
    """Every table in the document, as rows of the source text of each cell, the header row
    first."""
    found: list[list[list[str]]] = []
    for token, following in pairwise(_TABLE_PARSER.parse(path.read_text(encoding="utf-8"))):
        match token.type:
            case "table_open":
                found.append([])
            case "tr_open":
                found[-1].append([])
            case "th_open" | "td_open":
                found[-1][-1].append(following.content)
    return found


def code_snippets(path: Path) -> list[CodeSnippet]:
    """Every shell fence and code span in the document, with the line it starts on.

    A code span gives the line its paragraph starts on.
    """
    snippets: list[CodeSnippet] = []
    for token in _tokens(path):
        line = _line(token)
        if token.type == "fence" and _fence_language(token) in SHELL_FENCE_LANGUAGES:
            snippets.append(CodeSnippet(line + 1, token.content, True))
        elif token.type == "inline":
            snippets.extend(
                CodeSnippet(line, child.content, False)
                for child in token.children or ()
                if child.type == "code_inline"
            )
    return snippets


def shell_words(line: str) -> list[str]:
    """The words and operators a shell reads in `line`, comments left out; prose with an
    unbalanced quote is split at whitespace instead."""
    lexer = shlex.shlex(line, posix=True, punctuation_chars=_SPLIT_OPERATOR_CHARACTERS)
    lexer.whitespace_split = True
    try:
        return list(lexer)
    except ValueError:
        return line.split()


def _is_operator(word: str) -> bool:
    """Whether `word` is a shell operator (`;`, `|`, `&&`, a spaced `>`), at which a command ends."""
    return bool(word) and set(word) <= _SHELL_OPERATOR_CHARACTERS


def _is_placeholder(word: str) -> bool:
    """Whether a document wrote `word` for the reader to fill in.

    A shell expansion (`$R/b`, `"${files[@]}"`), a name in angle brackets (`<session>`), a
    synopsis part in square brackets or with Click's ellipsis (`[OPTIONS]`, `[ARGS]...`, `"..."`)
    or an upper-case metavariable (`COMMAND`, `STATUS`).
    """
    return (
        "$" in word
        or word.startswith(("<", "["))
        or word.endswith((">", "]", "..."))
        or word.isupper()
    )


def _argv_token(word: str) -> ArgvToken:
    return ArgvPlaceholder(expression=word) if _is_placeholder(word) else word


def devops_commands(snippet: CodeSnippet) -> Iterator[tuple[int, list[ArgvToken]]]:
    """Each `devops` command in a snippet: its line in the document and the words after `devops`.

    A line that ends in a backslash continues on the next, as in a shell.
    """
    if "devops" not in snippet.text:
        return
    lines = snippet.text.replace("\\\n", " ").splitlines() if snippet.fenced else [snippet.text]
    for offset, line in enumerate(lines):
        words = shell_words(line)
        for start, word in enumerate(words):
            if word == "devops":
                command = takewhile(lambda w: not _is_operator(w), words[start + 1 :])
                yield snippet.line + offset, [_argv_token(w) for w in command]
