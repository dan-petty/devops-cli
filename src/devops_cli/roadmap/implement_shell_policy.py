"""The shell policy of an implement step: one table for the guard, the prompt and the documents
(#3072).

`SHELL_PROGRAMS` lists the programs that the shell of the agent runs. Each one has an access class
(`read`, `write` or `network`: the most the program does by itself), what the agent uses it for,
and the arguments that the shell refuses. `SHELL_REFUSALS` lists the programs that the shell
refuses, with what to run instead. The allowlist of the shell, the hint that a refusal adds, the
prompt of the step and `docs/ROADMAP_WORKFLOW.md` all read these two tables, and a test fails when
one of them differs.

The shell of the harness reads the first word of a command only. `refused_argument` reads the
words of a command that starts a program of the table. A program with access `read` changes no
file, so it refuses a redirect to a file. `find` also refuses the arguments that run a program or
change a file, and refuses a word with `$`, because the shell expands `-ex${U}ec` after the check.

The step runs a verification command as a list of words, never through a shell. One form starts
with `!`: the negative search `! git grep [options] <literal> [--] <path>...`, which passes when
git finds no match (#3263). `read_negative_search` reads its words against one table: the
options below, a literal of plain characters and relative paths. The gate of the stage job reads
the same function, so a plan cannot pass the gate with a command that the step refuses.
"""

from __future__ import annotations

import re
import shlex
from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum

from devops_cli.config.commands import (
    BIN_DEVOPS,
    BIN_FIND,
    BIN_GIT,
    BIN_MYPY,
    BIN_OPENSPEC,
    BIN_RUFF,
    BIN_UV,
)
from devops_cli.lang import MESSAGES


class ShellAccess(StrEnum):
    """The most that a program does by itself: it reads files, it writes files, or it also uses
    the network."""

    READ = "read"
    WRITE = "write"
    NETWORK = "network"


@dataclass(frozen=True)
class ShellProgram:
    """One program that the shell runs. `refused_arguments` are the words that make the shell
    refuse the command, and `argument_instead` is what to run in their place."""

    name: str
    access: ShellAccess
    use: str
    refused_arguments: tuple[str, ...] = ()
    argument_instead: str = ""


@dataclass(frozen=True)
class ShellRefusal:
    """A program that the shell refuses, and the text of what to run in its place. The first
    sentence of `instead` is the replacement itself."""

    program: str
    instead: str


_READ_INSTEAD = (
    "This program only reads. To change a file, use the tools `write_file` and `edit_file`."
)
_FIND_INSTEAD = (
    "Use `find` to list paths only. To change a file, use the tools `write_file` and `edit_file`."
)
_PYTHON_INSTEAD = "`uv run python`. Do not run `python -m pip`: the lockfile gives the dependencies"
_LOCKFILE_INSTEAD = "nothing. The lockfile gives the dependencies"

SHELL_PROGRAMS: tuple[ShellProgram, ...] = (
    ShellProgram(BIN_GIT, ShellAccess.WRITE, "Read and change the repository."),
    ShellProgram(BIN_UV, ShellAccess.NETWORK, "Run the commands of the project: `uv run ...`."),
    ShellProgram(BIN_RUFF, ShellAccess.WRITE, "Check the style of Python files."),
    ShellProgram(BIN_MYPY, ShellAccess.WRITE, "Check the types of Python files."),
    ShellProgram(
        "grep", ShellAccess.READ, "Search the text of files.", argument_instead=_READ_INSTEAD
    ),
    ShellProgram("cat", ShellAccess.READ, "Print files.", argument_instead=_READ_INSTEAD),
    ShellProgram("ls", ShellAccess.READ, "List a directory.", argument_instead=_READ_INSTEAD),
    ShellProgram(
        "head", ShellAccess.READ, "Print the start of a file.", argument_instead=_READ_INSTEAD
    ),
    ShellProgram(
        "tail", ShellAccess.READ, "Print the end of a file.", argument_instead=_READ_INSTEAD
    ),
    ShellProgram(
        BIN_FIND,
        ShellAccess.READ,
        "List paths. The arguments `-exec`, `-execdir`, `-ok`, `-okdir`, `-delete`, `-fprint`, "
        "`-fprint0`, `-fprintf` and `-fls` are refused.",
        refused_arguments=(
            "-exec",
            "-execdir",
            "-ok",
            "-okdir",
            "-delete",
            "-fprint",
            "-fprint0",
            "-fprintf",
            "-fls",
        ),
        argument_instead=_FIND_INSTEAD,
    ),
)

# The programs that the step runs for the verification commands of a group, on top of the shell's.
# The agent cannot start them: `devops` can write to GitHub, and `openspec` can change the change.
VERIFICATION_PROGRAMS: tuple[str, ...] = (BIN_OPENSPEC, BIN_DEVOPS)

SHELL_REFUSALS: tuple[ShellRefusal, ...] = (
    ShellRefusal("python", _PYTHON_INSTEAD),
    ShellRefusal("python3", _PYTHON_INSTEAD),
    ShellRefusal("pytest", "`uv run pytest`"),
    ShellRefusal("pip", _LOCKFILE_INSTEAD),
    ShellRefusal("pip3", _LOCKFILE_INSTEAD),
    ShellRefusal("rg", "the tool `grep`, or `grep` in the shell"),
    ShellRefusal("cd", "nothing. Every command runs in the checkout"),
)

# The views of the two tables that the guard, the log and the tests read.
IMPLEMENT_SHELL_PROGRAMS: tuple[str, ...] = tuple(program.name for program in SHELL_PROGRAMS)
IMPLEMENT_ALLOWED_PROGRAMS: tuple[str, ...] = (*IMPLEMENT_SHELL_PROGRAMS, *VERIFICATION_PROGRAMS)
IMPLEMENT_SHELL_REPLACEMENTS: dict[str, str] = {
    refusal.program: refusal.instead for refusal in SHELL_REFUSALS
}

# The negative search: `! git grep [options] <literal> [--] <path>...`. The step runs the words
# after `!` and the search passes when git exits 1, which means no match. An option is one word of
# these letters: line numbers, no binary files, fixed strings, any case, whole words, file names,
# counts and a quiet run. No option reads a file (`-f`), opens a program (`-O`), leaves the
# repository (`--no-index`) or takes a value (`-e`), so every other option is refused.
NEGATIVE_SEARCH_WORD = "!"
NEGATIVE_SEARCH_START: tuple[str, ...] = (NEGATIVE_SEARCH_WORD, BIN_GIT, "grep")
NEGATIVE_SEARCH_OPTION_LETTERS = "nIFiwlcq"
NEGATIVE_SEARCH_LITERAL_SIGNS = "_ . : / = @ + , # % ~ -"
_OPTION = re.compile(rf"-[{NEGATIVE_SEARCH_OPTION_LETTERS}]+")
_LITERAL = re.compile(r"[\w .:/=@+,#%~-]+", re.ASCII)
_PATH = re.compile(r"[\w.+@~*/-]+", re.ASCII)
_PATHS_MARK = "--"

PROGRAMS_PLACEHOLDER = "{{shell_programs}}"
REFUSALS_PLACEHOLDER = "{{shell_refusals}}"


# The tokens of a redirect that writes a file. A target of `/dev/null` is allowed, and so is a
# copy of a stream (`2>&1`, `>&2`).
_FILE_REDIRECTS = frozenset({">", ">>", ">|", "&>", "&>>"})
_NULL_DEVICE = "/dev/null"


def _words(command: str) -> list[str] | None:
    """The words of `command`, with a redirect operator as a word of its own, or None when the text
    cannot be read."""
    lexer = shlex.shlex(command, posix=True, punctuation_chars=True)
    lexer.whitespace_split = True
    try:
        return list(lexer)
    except ValueError:
        return None


def _file_redirect(words: list[str]) -> str | None:
    """The first redirect of `words` that writes a file, or None."""
    for word, target in zip(words, [*words[1:], ""], strict=True):
        if word in _FILE_REDIRECTS and target != _NULL_DEVICE:
            return word
        if word == ">&" and target != _NULL_DEVICE and not (target.isdigit() or target == "-"):
            return word
    return None


def _refused_word(program: ShellProgram, words: list[str]) -> str | None:
    """The first word of `words` that `program` refuses, or None."""
    if program.access is ShellAccess.READ and (redirect := _file_redirect(words)) is not None:
        return redirect
    if not program.refused_arguments:
        return None
    return next(
        (w for w in words[1:] if w in program.refused_arguments or "$" in w),
        None,
    )


def refused_argument(command: str) -> tuple[ShellProgram, str] | None:
    """The program and the word that make the shell refuse `command`, or None. A command that
    `shlex` cannot read, or whose first word is not a program of the table, has none: the shell
    handles those."""
    words = _words(command)
    if not words:
        return None
    program = next((p for p in SHELL_PROGRAMS if p.name == words[0]), None)
    if program is None:
        return None
    word = _refused_word(program, words)
    return None if word is None else (program, word)


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
    """A negative search in the fixed shape, read from its words."""

    options: tuple[str, ...]
    literal: str
    paths: tuple[str, ...]

    @property
    def argv(self) -> list[str]:
        """The command that the step runs: the paths follow `--`, so git never reads one as a
        revision."""
        return [BIN_GIT, "grep", *self.options, self.literal, _PATHS_MARK, *self.paths]


def read_negative_search(words: Sequence[str]) -> NegativeSearch | str:
    """The negative search in `words`, or the reason that the step refuses it. The words are `!`,
    `git`, `grep`, options of `NEGATIVE_SEARCH_OPTION_LETTERS`, one literal, an optional `--` and at
    least one path. The reason is a sentence for the reason of the step and for the gate."""
    texts = MESSAGES.roadmap
    if tuple(words[:3]) != NEGATIVE_SEARCH_START:
        return texts.search_reason_start
    rest = list(words[3:])
    options: list[str] = []
    while rest and rest[0].startswith("-"):
        if _OPTION.fullmatch(rest[0]) is None:
            return texts.search_reason_option.format(
                word=rest[0], letters=" ".join(f"-{c}" for c in NEGATIVE_SEARCH_OPTION_LETTERS)
            )
        options.append(rest.pop(0))
    if not rest:
        return texts.search_reason_no_text
    literal = rest.pop(0)
    if _LITERAL.fullmatch(literal) is None:
        return texts.search_reason_literal.format(word=literal, signs=NEGATIVE_SEARCH_LITERAL_SIGNS)
    if rest[:1] == [_PATHS_MARK]:
        del rest[0]
    if not rest:
        return texts.search_reason_no_path
    bad = next((word for word in rest if not _is_path(word)), None)
    if bad is not None:
        return texts.search_reason_path.format(word=bad)
    return NegativeSearch(tuple(options), literal, tuple(rest))


def verification_problem(command: str) -> str | None:
    """Why the step cannot run the verification `command`, or None when it can: the words are
    readable, and the first word is a program of the verification list or the negative search is
    in the fixed shape."""
    texts = MESSAGES.roadmap
    try:
        words = shlex.split(command)
    except ValueError:
        return texts.verify_reason_unparsed
    if not words:
        return texts.verify_reason_unparsed
    if words[0] == NEGATIVE_SEARCH_WORD:
        found = read_negative_search(words)
        return found if isinstance(found, str) else None
    if words[0] not in IMPLEMENT_ALLOWED_PROGRAMS:
        return texts.verify_reason_program.format(program=words[0])
    return None


def programs_table() -> str:
    """The Markdown table of the programs that the shell runs."""
    rows = [
        f"| `{program.name}` | {program.access} | {program.use} |" for program in SHELL_PROGRAMS
    ]
    return "\n".join(["| Program | Access | Use |", "| :--- | :--- | :--- |", *rows])


def refusals_table() -> str:
    """The Markdown table of the programs that the shell refuses, with what to run instead."""
    rows = [f"| `{refusal.program}` | {refusal.instead} |" for refusal in SHELL_REFUSALS]
    return "\n".join(["| Program | Instead |", "| :--- | :--- |", *rows])


def fill_prompt(prompt: str) -> str:
    """The prompt with its two placeholders replaced by the two tables."""
    return prompt.replace(PROGRAMS_PLACEHOLDER, programs_table()).replace(
        REFUSALS_PLACEHOLDER, refusals_table()
    )
