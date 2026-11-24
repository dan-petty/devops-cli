"""Verification commands for an implement step and the stage gates (#3262, #3263, #3577).

The step runs a verification command as a list of words, never through a shell. One form starts
with `!`: the negative search `! git grep [options] <literal> [--] <path>...`, which passes when
git finds no match (#3263). `read_negative_search` reads its words against one table: the
options below, a literal of plain characters and relative paths. The gate of the stage job reads
the same function, so a plan cannot pass the gate with a command that the step refuses.
`verification_class` reads the program of a failed verification command, so the step gives its
failure the class of that program (#3577).
"""

from __future__ import annotations

import re
import shlex
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Final

from devops_cli.config.commands import (
    BIN_DEVOPS,
    BIN_FIND,
    BIN_GIT,
    BIN_MYPY,
    BIN_OPENSPEC,
    BIN_PYTEST,
    BIN_RUFF,
    BIN_UV,
)
from devops_cli.config.constants import CONST_ROADMAP_IMPLEMENT_VERIFY_CHARS
from devops_cli.lang import MESSAGES
from devops_cli.roadmap.failure import FailureClass

NEGATIVE_SEARCH_WORD = "!"

# The first words of a verification command other than the `!` of a negative search. git is not
# one: the step runs a verification command in the checkout, where git reads the configuration that
# the agent can write, and the process runner gives each git call the token of the process (GHSA).
# So a verification command runs git only as the negative search, which reaches no remote.
VERIFICATION_FIRST_WORDS: tuple[str, ...] = (
    BIN_UV,
    BIN_RUFF,
    BIN_MYPY,
    "grep",
    "cat",
    "ls",
    "head",
    "tail",
    "wc",
    BIN_FIND,
    BIN_OPENSPEC,
    BIN_DEVOPS,
)

# The negative search: `! git grep [options] <literal> [--] <path>...`. The step runs the words
# after `!` and the search passes when git exits 1, which means no match. An option is one word of
# these letters: line numbers, no binary files, fixed strings, any case, whole words, file names,
# counts and a quiet run. The option `-e` takes one literal, and a search may repeat it: git matches
# any of the literals. No other option reads a file (`-f`), opens a program (`-O`), leaves the
# repository (`--no-index`) or takes a value, so every other option is refused.
NEGATIVE_SEARCH_START: tuple[str, ...] = (NEGATIVE_SEARCH_WORD, BIN_GIT, "grep")
NEGATIVE_SEARCH_OPTION_LETTERS = "nIFiwlcq"
NEGATIVE_SEARCH_LITERAL_SIGNS = "_ . : / = @ + , # % ~ -"
_OPTION = re.compile(rf"-[{NEGATIVE_SEARCH_OPTION_LETTERS}]+")
_LITERAL = re.compile(r"[\w .:/=@+,#%~-]+", re.ASCII)
_PATH = re.compile(r"[\w.+@~*/-]+", re.ASCII)
_E_OPTION = "-e"
_PATHS_MARK = "--"
_SHOWN_CHARS = 60


def without_checkout_prefix(command: str, checkout: Path | str) -> str:
    """`command` without the prefix `cd <checkout> &&`, when it starts with exactly that: the path
    of the checkout alone, in plain or in quotes. Every command runs in the checkout, so the prefix
    changes nothing. Any other `cd` and any other `&&` stay, and the shell refuses them."""
    path = re.escape(str(checkout))
    found = re.match(rf"""\s*cd +(?:{path}|'{path}'|"{path}") +&& +""", command)
    return command if found is None else command[found.end() :]


def _is_path(word: str) -> bool:
    """Whether `word` is a relative path inside the checkout: plain characters, no leading `-` or
    `/`, no `..` part."""
    return (
        _PATH.fullmatch(word) is not None
        and not word.startswith(("-", "/"))
        and ".." not in word.split("/")
    )


@dataclass(frozen=True)
class NegativeSearch:
    """A negative search in the fixed shape, read from its words. `literals` holds one literal, or
    each `-e` literal when `by_e` is set."""

    options: tuple[str, ...]
    literals: tuple[str, ...]
    paths: tuple[str, ...]
    by_e: bool = False

    @property
    def argv(self) -> list[str]:
        """The command that the step runs: each literal follows its own `-e` when `by_e` is set,
        and the paths follow `--`, so git never reads one as a revision."""
        patterns = (
            [word for literal in self.literals for word in (_E_OPTION, literal)]
            if self.by_e
            else list(self.literals)
        )
        return [BIN_GIT, "grep", *self.options, *patterns, _PATHS_MARK, *self.paths]


def shown(text: str, limit: int = _SHOWN_CHARS) -> str:
    """`text` for a reason or a problem: control characters (a line break, a NUL byte, ESC) and
    characters outside ASCII (a bidi override, NEL) are escaped, and a long text is cut with `...`.
    A reason never holds a raw control character. Every word and every command that a reason
    names goes through this function, for the step and for the gate."""
    escaped = text.encode("unicode_escape").decode("ascii")
    return escaped if len(escaped) <= limit else f"{escaped[:limit]}..."


def _read_e_literals(options: tuple[str, ...], rest: list[str]) -> NegativeSearch | str:
    """The negative search whose literals are `-e` options, read from `rest`, which starts with the
    first `-e`. Each value is a plain literal and never a word that starts with `-`. `--` comes
    after the last value and before the paths, and no word may stand between them."""
    texts = MESSAGES.roadmap
    literals: list[str] = []
    while rest[:1] == [_E_OPTION]:
        rest.pop(0)
        if not rest or rest[0] == _PATHS_MARK:
            return texts.search_reason_e_value
        value = rest.pop(0)
        if value.startswith("-"):
            return texts.search_reason_e_dash.format(word=shown(value))
        if _LITERAL.fullmatch(value) is None:
            return texts.search_reason_literal.format(
                word=shown(value), signs=NEGATIVE_SEARCH_LITERAL_SIGNS
            )
        literals.append(value)
    if not rest:
        return texts.search_reason_no_path
    if rest[0] != _PATHS_MARK:
        return texts.search_reason_e_forms.format(word=shown(rest[0]))
    del rest[0]
    if not rest:
        return texts.search_reason_no_path
    bad = next((word for word in rest if not _is_path(word)), None)
    if bad is not None:
        return texts.search_reason_path.format(word=shown(bad))
    return NegativeSearch(options, tuple(literals), tuple(rest), by_e=True)


def read_negative_search(words: Sequence[str]) -> NegativeSearch | str:
    """The negative search in `words`, or the reason that the step refuses it. The words are `!`,
    `git`, `grep`, options of `NEGATIVE_SEARCH_OPTION_LETTERS`, then either one literal or one or
    more `-e` literals, an optional `--` (required with `-e`) and at least one path. The reason is a
    sentence for the reason of the step and for the gate."""
    texts = MESSAGES.roadmap
    if tuple(words[:3]) != NEGATIVE_SEARCH_START:
        return texts.search_reason_start
    rest = list(words[3:])
    options: list[str] = []
    while rest and rest[0].startswith("-") and rest[0] != _E_OPTION:
        if _OPTION.fullmatch(rest[0]) is None:
            return texts.search_reason_option.format(
                word=shown(rest[0]),
                letters=" ".join(f"-{c}" for c in NEGATIVE_SEARCH_OPTION_LETTERS),
            )
        options.append(rest.pop(0))
    if rest[:1] == [_E_OPTION]:
        return _read_e_literals(tuple(options), rest)
    if not rest:
        return texts.search_reason_no_text
    literal = rest.pop(0)
    if _LITERAL.fullmatch(literal) is None:
        return texts.search_reason_literal.format(
            word=shown(literal), signs=NEGATIVE_SEARCH_LITERAL_SIGNS
        )
    if rest[:1] == [_PATHS_MARK]:
        del rest[0]
    if not rest:
        return texts.search_reason_no_path
    bad = next((word for word in rest if not _is_path(word)), None)
    if bad is not None:
        return texts.search_reason_path.format(word=shown(bad))
    return NegativeSearch(tuple(options), (literal,), tuple(rest))


@dataclass(frozen=True)
class Verification:
    """A verification command that the step runs: the `argv` of the process, and whether it is a
    negative search, which passes on exit 1 and not on exit 0."""

    argv: list[str]
    negative: bool = False


def _is_argument(word: str) -> bool:
    """Whether `word` can be an argument of a process: no NUL byte, and it encodes to UTF-8."""
    if "\0" in word:
        return False
    try:
        word.encode("utf-8")
    except UnicodeEncodeError:
        return False
    return True


def read_verification(command: str) -> Verification | str:
    """The process that the step starts for the verification `command`, or the reason that it
    refuses. The words are readable and can be arguments (no NUL byte, no lone surrogate: both
    raise in `execve`), they hold at most `CONST_ROADMAP_IMPLEMENT_VERIFY_CHARS` characters in all
    (a longer argument list fails `execve` with E2BIG), and the first word is a program of the
    verification list (`VERIFICATION_FIRST_WORDS`) or the `!` of a negative search in the fixed
    shape. git runs only as that search. The step and the gate of the stage job read this function,
    so no command is refused by one side only."""
    texts = MESSAGES.roadmap
    try:
        words = shlex.split(command)
    except ValueError:
        return texts.verify_reason_unparsed
    if not words:
        return texts.verify_reason_unparsed
    if any(not _is_argument(word) for word in words):
        return texts.verify_reason_bytes
    if sum(len(word) for word in words) > CONST_ROADMAP_IMPLEMENT_VERIFY_CHARS:
        return texts.verify_reason_long.format(limit=CONST_ROADMAP_IMPLEMENT_VERIFY_CHARS)
    if words[0] == NEGATIVE_SEARCH_WORD:
        found = read_negative_search(words)
        return found if isinstance(found, str) else Verification(found.argv, negative=True)
    if words[0] == BIN_GIT:
        return texts.verify_reason_git
    if words[0] not in VERIFICATION_FIRST_WORDS:
        return texts.verify_reason_program.format(
            program=shown(words[0]), allowed=", ".join(VERIFICATION_FIRST_WORDS)
        )
    return Verification(words)


_UV_RUN: Final[tuple[str, ...]] = (BIN_UV, "run")
_CI_WORDS: Final[tuple[str, ...]] = (BIN_DEVOPS, "ci")
# The class of a verification command, by the program after `uv run`. A program that is not here
# names no class, and its failure still gets a repair turn (#3577).
_PROGRAM_CLASS: Final[Mapping[str, FailureClass]] = MappingProxyType(
    {
        BIN_PYTEST: FailureClass.TEST,
        BIN_MYPY: FailureClass.TYPES,
        BIN_RUFF: FailureClass.LINT,
    }
)
# The class of a row of `devops ci`, read after `uv run devops ci` (#3577).
_CI_ROW_CLASS: Final[Mapping[str, FailureClass]] = MappingProxyType(
    {"test": FailureClass.TEST, "lint": FailureClass.LINT, "typecheck": FailureClass.TYPES}
)


def verification_class(argv: Sequence[str]) -> FailureClass | None:
    """The class of the verification command `argv`: `pytest` is a test, `mypy` is types and `ruff`
    is lint, and the row after `devops ci` gives the same three. A program that names none of them,
    such as `devops docs check`, has no class: its failure still gets a repair turn, and its message
    names no class."""
    words = list(argv)
    if tuple(words[:2]) == _UV_RUN:
        del words[:2]
    if tuple(words[:2]) == _CI_WORDS:
        return _CI_ROW_CLASS.get(words[2]) if len(words) > 2 else None
    return _PROGRAM_CLASS.get(words[0]) if words else None


def verification_problem(command: str) -> str | None:
    """Why the step cannot run the verification `command`, or None when it can."""
    found = read_verification(command)
    return found if isinstance(found, str) else None
