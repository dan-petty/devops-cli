"""The shell policy of an implement step: one table for the guard, the prompt and the documents
(#3072).

`SHELL_PROGRAMS` lists the programs that the shell of the agent runs. Each one has an access class
(`read`, `write` or `network`: the most the program does by itself), what the agent uses it for,
and the arguments that the shell refuses. `SHELL_REFUSALS` lists the programs that the shell
refuses, with what to run instead. `LOCAL_COMMANDS` lists the commands of `devops` that the agent
runs through `uv run` (#3041). The allowlist of the shell and the hint that a refusal adds read
`SHELL_PROGRAMS` and `SHELL_REFUSALS`. The prompt of the step and `docs/ROADMAP_WORKFLOW.md` read
all three tables, and a test fails when one of them differs. The shell does not read
`LOCAL_COMMANDS`: it passes a call of `uv run devops ...` because `uv` is a program of the table.

The shell of the harness reads the first word of a command only. `refused_argument` reads the
words of a command that starts a program of the table. A program with access `read` changes no
file, so it refuses a redirect to a file. `find` also refuses the arguments that run a program or
change a file, and refuses a word with `$`, because the shell expands `-ex${U}ec` after the check.

A pipe is the one operator that the policy reads word by word (#3520). The harness matches an
operator as plain text, so it cannot tell a pipe from the escaped pipe of a `grep` pattern, and it cannot
admit `| head` and refuse `| sh`. `HARNESS_DENIED_OPERATORS` is the tuple of denied operators without
`|`. `pipe_refusal` splits a command into stages and admits a pipe only when each stage after the
first starts a program of `CONST_ROADMAP_IMPLEMENT_READ_PIPE_PROGRAMS` that does not redirect to a
file. `without_checkout_prefix` removes the exact prefix `cd <checkout> &&`, which changes to the
directory that every command already has.

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
from pathlib import Path

from devops_cli.config.commands import (
    BIN_DEVOPS,
    BIN_FIND,
    BIN_GIT,
    BIN_MYPY,
    BIN_OPENSPEC,
    BIN_RUFF,
    BIN_UV,
)
from devops_cli.config.constants import (
    CONST_ROADMAP_IMPLEMENT_DENIED_OPERATORS,
    CONST_ROADMAP_IMPLEMENT_READ_PIPE_PROGRAMS,
    CONST_ROADMAP_IMPLEMENT_VERIFY_CHARS,
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
class LocalCommand:
    """One command of `devops` that the agent runs through `uv run`. `words` are the words after
    `devops`. `access` is the most that the command does by itself, with the flags that the use
    text allows. No command of the table makes a request to a service: none needs a key."""

    words: tuple[str, ...]
    access: ShellAccess
    use: str

    @property
    def usage(self) -> str:
        """The command as the agent types it."""
        return " ".join([BIN_UV, "run", BIN_DEVOPS, *self.words])


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
# The first word of a negative search. No shell runs it: the step does (see below).
NEGATIVE_SEARCH_WORD = "!"
_BANG_INSTEAD = (
    "`git grep -n <literal> -- <paths>`. Read no output as a pass. The step runs a verification "
    "command that starts with `!` itself, after your run"
)

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
        "wc",
        ShellAccess.READ,
        "Count the lines, words and bytes of files.",
        argument_instead=_READ_INSTEAD,
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

# The commands of `devops` that the shell runs through `uv`, which it allows. A call of one passes
# the policy and is no refusal. A command that needs a key or a cluster is not here (#3562, #3563).
LOCAL_COMMANDS: tuple[LocalCommand, ...] = (
    LocalCommand(
        ("ci", "test"),
        ShellAccess.WRITE,
        "Run the tests of one file: `uv run devops ci test <file>`. It writes cache files in the "
        "checkout.",
    ),
    LocalCommand(
        ("ai", "repomap"),
        ShellAccess.READ,
        "Print a compact map of the symbols of the repository.",
    ),
    LocalCommand(
        ("ai", "ast"),
        ShellAccess.WRITE,
        "Parse one source file (`parse`) or build the symbol graph of the repository (`graph`). "
        "`graph --output <path>` writes a file: give it a path in the checkout.",
    ),
    LocalCommand(
        ("docs", "generate"),
        ShellAccess.WRITE,
        "Write the generated documents in the docs directory of the checkout: pass no "
        "`--output-dir`. Run it after a change to a command or a setting.",
    ),
    LocalCommand(
        ("openspec", "check"),
        ShellAccess.READ,
        "Check the changes and the specs of OpenSpec.",
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
    ShellRefusal(NEGATIVE_SEARCH_WORD, _BANG_INSTEAD),
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

PROGRAMS_PLACEHOLDER = "{{shell_programs}}"
LOCAL_COMMANDS_PLACEHOLDER = "{{local_commands}}"
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
    lexer.commenters = ""
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


# The tool of the harness that runs a command of the agent. It waits until the command ends, up to
# the command limit of the step, and returns the output (#4493). The persistent tool `shell`
# returned after 270 s with a PID and a log, and the agent read the log again and again.
IMPLEMENT_SHELL_TOOL = "run_command"

PIPE = "|"
# The denied operators that the harness checks as plain text: all but the pipe, which
# `pipe_refusal` reads word by word.
HARNESS_DENIED_OPERATORS: tuple[str, ...] = tuple(
    operator for operator in CONST_ROADMAP_IMPLEMENT_DENIED_OPERATORS if operator != PIPE
)
# The characters that `shlex` splits into words of their own, with `punctuation_chars=True`.
_PUNCTUATION = frozenset(shlex.shlex("", punctuation_chars=True).punctuation_chars)


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


def _pipe_text(program: str | None = None) -> str:
    """The refusal of a pipe, with the program after it when there is one, and the programs that a
    pipe may end in."""
    texts = MESSAGES.roadmap
    names = [f"`{name}`" for name in CONST_ROADMAP_IMPLEMENT_READ_PIPE_PROGRAMS]
    return texts.implement_refusal_pipe.format(
        before=texts.implement_refusal_pipe_before.format(program=shown(program))
        if program
        else "",
        programs=f"{', '.join(names[:-1])} or {names[-1]}",
    )


def pipe_refusal(command: str) -> str | None:
    """The text that refuses the pipes of `command`, or None when it holds no pipe or each stage
    after the first is a program of `CONST_ROADMAP_IMPLEMENT_READ_PIPE_PROGRAMS` that writes no file.
    A `|` in quotes or after a backslash is part of a word and starts no stage. A word made of
    operator characters that holds a `|` (`|&`, `||`, `)|`) is no plain pipe, so it is refused. A
    command that `shlex` cannot read is refused when it holds a `|` anywhere."""
    words = _words(command)
    if words is None:
        return _pipe_text() if PIPE in command else None
    stages: list[list[str]] = [[]]
    for word in words:
        if word == PIPE:
            stages.append([])
        elif PIPE in word and set(word) <= _PUNCTUATION:
            return _pipe_text()
        else:
            stages[-1].append(word)
    for stage in stages[1:]:
        program = next((p for p in SHELL_PROGRAMS if stage and p.name == stage[0]), None)
        if program is None or program.name not in CONST_ROADMAP_IMPLEMENT_READ_PIPE_PROGRAMS:
            return _pipe_text(stage[0] if stage else None)
        if (refused := _refused_word(program, stage)) is not None:
            return MESSAGES.roadmap.implement_refusal_argument.format(
                program=program.name, argument=refused, instead=program.argument_instead
            )
    return None


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
    verification list or the `!` of a negative search in the fixed shape. The step and the gate of
    the stage job read this function, so no command is refused by one side only."""
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
    if words[0] not in IMPLEMENT_ALLOWED_PROGRAMS:
        return texts.verify_reason_program.format(
            program=shown(words[0]), allowed=", ".join(IMPLEMENT_ALLOWED_PROGRAMS)
        )
    return Verification(words)


def verification_problem(command: str) -> str | None:
    """Why the step cannot run the verification `command`, or None when it can."""
    found = read_verification(command)
    return found if isinstance(found, str) else None


def programs_table() -> str:
    """The Markdown table of the programs that the shell runs."""
    rows = [
        f"| `{program.name}` | {program.access} | {program.use} |" for program in SHELL_PROGRAMS
    ]
    return "\n".join(["| Program | Access | Use |", "| :--- | :--- | :--- |", *rows])


def local_commands_table() -> str:
    """The Markdown table of the `devops` commands that the shell runs through `uv`."""
    rows = [
        f"| `{command.usage}` | {command.access} | {command.use} |" for command in LOCAL_COMMANDS
    ]
    return "\n".join(["| Command | Access | Use |", "| :--- | :--- | :--- |", *rows])


def refusals_table() -> str:
    """The Markdown table of the programs that the shell refuses, with what to run instead."""
    rows = [f"| `{refusal.program}` | {refusal.instead} |" for refusal in SHELL_REFUSALS]
    return "\n".join(["| Program | Instead |", "| :--- | :--- |", *rows])


def fill_prompt(prompt: str) -> str:
    """The prompt with its three placeholders replaced by the three tables."""
    return (
        prompt.replace(PROGRAMS_PLACEHOLDER, programs_table())
        .replace(LOCAL_COMMANDS_PLACEHOLDER, local_commands_table())
        .replace(REFUSALS_PLACEHOLDER, refusals_table())
    )
