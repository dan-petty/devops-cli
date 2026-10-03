"""Read the code in Markdown documents: shell fences, code spans, and the `devops` commands in them.

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
from itertools import takewhile
from pathlib import Path
from typing import NamedTuple

from markdown_it import MarkdownIt
from markdown_it.token import Token

from devops_cli.docs.command_resolver import ArgvPlaceholder, ArgvToken

# The fences whose lines a shell would run; a fence with no language is read as one too.
SHELL_FENCE_LANGUAGES = frozenset({"", "bash", "sh", "shell", "zsh", "console", "shell-session"})
# The characters a POSIX shell reads as operators, as the standard library's lexer lists them.
_SHELL_OPERATOR_CHARACTERS = frozenset(shlex.shlex(punctuation_chars=True).punctuation_chars)
# The ones the lexer splits from a word they touch: all but `<` and `>`, which `<session>` holds.
_SPLIT_OPERATOR_CHARACTERS = "".join(sorted(_SHELL_OPERATOR_CHARACTERS - set("<>")))
_PARSER = MarkdownIt("commonmark")


class CodeSnippet(NamedTuple):
    """Code a document shows: a shell fence's body or a code span, and the line it starts on."""

    line: int
    text: str
    fenced: bool


@cache
def _tokens(path: Path) -> tuple[Token, ...]:
    return tuple(_PARSER.parse(path.read_text(encoding="utf-8")))


def _fence_language(token: Token) -> str:
    return token.info.split(maxsplit=1)[0] if token.info.strip() else ""


def code_snippets(path: Path) -> list[CodeSnippet]:
    """Every shell fence and code span in the document, with the line it starts on.

    A code span gives the line its paragraph starts on.
    """
    snippets: list[CodeSnippet] = []
    for token in _tokens(path):
        line = (token.map[0] if token.map else 0) + 1
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
