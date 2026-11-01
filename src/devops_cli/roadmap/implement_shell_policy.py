"""The shell policy of an implement step: one table for the guard, the prompt and the documents
(#3072).

`SHELL_PROGRAMS` lists the programs that the shell of the agent runs. Each one has an access class
(`read`, `write` or `network`: the most the program does by itself), what the agent uses it for,
and the arguments that the shell refuses. `SHELL_REFUSALS` lists the programs that the shell
refuses, with what to run instead. The allowlist of the shell, the hint that a refusal adds, the
prompt of the step and `docs/ROADMAP_WORKFLOW.md` all read these two tables, and a test fails when
one of them differs.

The shell of the harness reads the first word of a command only. `refused_argument` reads the
words of a command that starts a program of the table, so the read-only `find` can refuse the
arguments that run a program or change a file.
"""

from __future__ import annotations

import shlex
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
    ShellProgram("grep", ShellAccess.READ, "Search the text of files."),
    ShellProgram("cat", ShellAccess.READ, "Print files."),
    ShellProgram("ls", ShellAccess.READ, "List a directory."),
    ShellProgram("head", ShellAccess.READ, "Print the start of a file."),
    ShellProgram("tail", ShellAccess.READ, "Print the end of a file."),
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

PROGRAMS_PLACEHOLDER = "{{shell_programs}}"
REFUSALS_PLACEHOLDER = "{{shell_refusals}}"


def refused_argument(command: str) -> tuple[ShellProgram, str] | None:
    """The program and the argument that make the shell refuse `command`, or None. A command that
    `shlex` cannot read, or whose first word is not a program of the table, has none: the shell
    handles those."""
    try:
        words = shlex.split(command)
    except ValueError:
        return None
    if not words:
        return None
    program = next((p for p in SHELL_PROGRAMS if p.name == words[0]), None)
    if program is None:
        return None
    argument = next((word for word in words[1:] if word in program.refused_arguments), None)
    return None if argument is None else (program, argument)


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
