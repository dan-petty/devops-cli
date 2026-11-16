"""The definition check that the stage probe, the refine context and the implement job share
(#3417, #4638).

A name is defined at a commit when a source file of that commit defines it. One `git grep` finds
the lines of the source files that name it as a whole word. A Python line defines it when it holds
its `def`, `async def` or `class`, or an assignment of it at the start of a line. When no Python
line defines it, one more `git grep` reads the files of the other languages that name it, and the
tree-sitter grammar of the language of each file confirms a definition, as `TreeSitterEngine` reads
the symbols of a file for the code map. The stage probe asks the staging commit whether an
identifier that the issue cites is defined (#3011). The implement job asks the branch tip whether a
name of the `Adds:` line of a behavior group is already there (#3417, #3453). Both ask one
question, so both call this module.

The check reads the commit, never the working tree: a line that only an uncommitted change holds
is no definition of the commit.
"""

from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Callable, Iterator
from itertools import islice
from typing import TYPE_CHECKING

from devops_cli.ai.ast.engine import TreeSitterEngine, detect_language
from devops_cli.config.constants import CONST_ROADMAP_DEFINITION_READ_FILES
from devops_cli.lang import MESSAGES
from devops_cli.roadmap.refine.refine import SYMBOL_PATHSPECS, git_result
from devops_cli.roadmap.step_files import TaskGroup

if TYPE_CHECKING:
    from pathlib import Path

# One git command in a checkout: the arguments after `git -C <checkout>`, and its exit code with its
# standard output.
GitResult = Callable[..., tuple[int, str]]

# The commands of a full check: the search of the source files, and the read of the files of the
# other languages.
_FULL_CHECK_COMMANDS = 2

# The lines of each file that name a name: the number and the text of each line, by path.
_Named = dict[str, list[tuple[int, str]]]


def _python_definition(name: str) -> re.Pattern[str]:
    """A `def`, an `async def` or a `class` of `name`, or an assignment of it at the start of a
    line, with or without an annotation. `name` is an identifier, so it holds no character that the
    expression reads."""
    return re.compile(
        rf"(^|[^A-Za-z0-9_])(def|class)\s+{name}([^A-Za-z0-9_]|$)|^\s*{name}\s*(:[^=]*)?=",
        re.ASCII,
    )


def _grep_lines(out: str, sha: str) -> Iterator[tuple[str, int, str]]:
    """The path, the number and the text of each line that `git grep -n -z` at `sha` printed."""
    for row in out.split("\n"):
        fields = row.split("\0", 2)
        if len(fields) == 3 and fields[1].isdigit():
            yield fields[0].removeprefix(f"{sha}:"), int(fields[1]), fields[2]


def _grep(source: Path, sha: str, git: GitResult, *args: str) -> Iterator[tuple[str, int, str]]:
    """The lines that one `git grep -n -z -I <args>` at `sha` prints, none when it finds none."""
    code, out = git(source, "grep", "-n", "-z", "-I", *args)
    return _grep_lines(out, sha) if code == 0 and out else iter(())


def _parsed_definitions(
    source: Path, sha: str, name: str, named: _Named, git: GitResult
) -> Iterator[str]:
    """The lines of `named` that hold a definition of `name` that tree-sitter confirms: the line
    of each symbol of that name that names it first. One `git grep` reads the files whole."""
    paths = [f":(literal){path}" for path in named]
    texts: dict[str, list[str]] = defaultdict(list)
    for path, _, text in _grep(source, sha, git, "-e", "^", sha, "--", *paths):
        texts[path].append(text)
    engine = TreeSitterEngine()
    for path, lines in named.items():
        content = "\n".join(texts[path])
        language = detect_language(path, content)
        if language is None:
            continue
        for symbol in engine.parse_code(content, language, path).symbols:
            span = symbol.span
            hits = (line for line in lines if span.line_start <= line[0] <= span.line_end)
            if symbol.name == name and (hit := next(hits, None)):
                yield f"{sha}:{path}:{hit[0]}:{hit[1]}"


def definition_lines(
    source: Path,
    sha: str,
    name: str,
    git: GitResult = git_result,
    *,
    commands: int = _FULL_CHECK_COMMANDS,
) -> tuple[str, ...] | None:
    """The lines of the definitions of `name` at commit `sha` of the checkout `source`, as
    `<sha>:<path>:<line>:<text>`: those of the Python files when there are any, else those of the
    other source files, at most `CONST_ROADMAP_DEFINITION_READ_FILES` of them. Empty when the commit
    defines no such name. `git` runs each command of a caller that keeps a budget of them, and
    `commands` is the number of them the caller has left. None when the check is undecided: the
    files of other languages name `name` and the budget leaves no command to read them, or more of
    them name it than the bound lets the check read and none of those it reads defines it."""
    python = _python_definition(name)
    found: list[str] = []
    named: _Named = defaultdict(list)
    for path, number, text in _grep(
        source, sha, git, "-F", "-w", "-e", name, sha, "--", *SYMBOL_PATHSPECS
    ):
        if detect_language(path) != "python":
            named[path].append((number, text))
        elif python.search(text):
            found.append(f"{sha}:{path}:{number}:{text}")
    if found or not named:
        return tuple(found)
    if commands < _FULL_CHECK_COMMANDS:
        return None
    read = dict(islice(named.items(), CONST_ROADMAP_DEFINITION_READ_FILES))
    parsed = tuple(dict.fromkeys(_parsed_definitions(source, sha, name, read, git)))
    return parsed if parsed or len(read) == len(named) else None


def defines(source: Path, sha: str, name: str, git: GitResult = git_result) -> bool:
    """Whether the commit `sha` of the checkout `source` defines `name`."""
    return bool(definition_lines(source, sha, name, git))


def false_premises(
    source: Path, sha: str, group: TaskGroup, git: GitResult = git_result
) -> tuple[str, ...]:
    """The evidence for each name of the `Adds:` line of `group` that commit `sha` already
    defines: the group, the name and the definition line. Empty when the premise of the group
    holds. The plan states the names in that line (#3453), so no rule reads the prose of a task: a
    task that names a guard only as the place of a change, or as the text of a test, adds nothing.
    A code span of the line that is no identifier, such as `TaskGroup.added_names`, gets no check,
    because the lookup reads a definition of one identifier. The check reads the commit and writes
    nothing."""
    found: list[str] = []
    for name in group.added_names:
        if not name.isidentifier():
            continue
        if lines := definition_lines(source, sha, name, git):
            found.append(
                MESSAGES.roadmap.premise_guard_defined.format(
                    group=group.number, name=name, line=lines[0]
                )
            )
    return tuple(found)


__all__ = ["defines", "definition_lines", "false_premises"]
