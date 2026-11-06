"""The definition check that the stage probe and the implement job share (#3417).

A name is defined at a commit when a Python file of that commit holds its `def`, `async def` or
`class`, or an assignment of it at the start of a line. The stage probe asks the staging commit
whether an identifier that the issue cites is defined (#3011). The implement job asks the branch
tip whether a guard that a behavior group adds is already there (#3417). Both ask one question, so
both call this module and run one `git grep` at the commit.

The check reads the commit, never the working tree: a line that only an uncommitted change holds
is no definition of the commit.
"""

from __future__ import annotations

import keyword
import re
from collections.abc import Callable
from typing import TYPE_CHECKING

from devops_cli.lang import MESSAGES
from devops_cli.roadmap.refine import SYMBOL_PATHSPEC, git_result
from devops_cli.roadmap.step_files import TaskGroup

if TYPE_CHECKING:
    from pathlib import Path

# One git command in a checkout: the arguments after `git -C <checkout>`, and its exit code with its
# standard output.
GitResult = Callable[..., tuple[int, str]]


def _definition_pattern(name: str) -> str:
    """The extended expression for a definition of `name`: a `def`, an `async def` or a `class`, or
    an assignment at the start of a line, with or without an annotation. `name` is an identifier,
    so it holds no character that the expression reads."""
    return (
        rf"(^|[^A-Za-z0-9_])(def|class)[[:space:]]+{name}([^A-Za-z0-9_]|$)"
        rf"|^[[:space:]]*{name}[[:space:]]*(:[^=]*)?="
    )


def definition_lines(
    source: Path, sha: str, name: str, git: GitResult = git_result
) -> tuple[str, ...]:
    """The lines of the definitions of `name` at commit `sha` of the checkout `source`, as
    `<sha>:<path>:<line>:<text>`. Empty when the commit defines no such name. `git` runs one
    command of a caller that keeps a budget of them."""
    code, out = git(
        source, "grep", "-n", "-E", "-e", _definition_pattern(name), sha, "--", SYMBOL_PATHSPEC
    )
    return tuple(out.splitlines()) if code == 0 and out else ()


def defines(source: Path, sha: str, name: str, git: GitResult = git_result) -> bool:
    """Whether the commit `sha` of the checkout `source` defines `name`."""
    return bool(definition_lines(source, sha, name, git))


# A task names the guard it adds when the code span directly follows the word guard or check, as in
# "Add the guard `name`" or "Create a check named `name`". A span after a preposition ("Add a check
# to `run_step`") names code that the task changes, not code that it adds.
_ADD_VERB = re.compile(r"\b(?:add|adds|create|creates|introduce|introduces)\b", re.IGNORECASE)
_GUARD_SPAN = re.compile(
    r"\b(?:guards?|checks?)\s+(?:(?:named|called)\s+)?`([^`]*)`", re.IGNORECASE
)


def added_guard(task_text: str) -> str | None:
    """The name of the guard that the task adds, or None. A task adds a guard when an add verb is
    followed by the word guard or check and then by one code span that holds an identifier (a path,
    a command or a phrase is no identifier). A span after any other word names code that the task
    changes. A task with two such names does not say which one it adds, so it names none."""
    verb = _ADD_VERB.search(task_text)
    if verb is None:
        return None
    names = {
        span
        for span in _GUARD_SPAN.findall(task_text, verb.end())
        if span.isidentifier() and not keyword.iskeyword(span)
    }
    return names.pop() if len(names) == 1 else None


def false_premises(
    source: Path, sha: str, group: TaskGroup, git: GitResult = git_result
) -> tuple[str, ...]:
    """The evidence for each task of `group` that adds a guard which commit `sha` already defines:
    the task, the name and the definition line. Empty when the premise of the group holds. The
    check reads the commit and writes nothing."""
    found: list[str] = []
    for task in group.tasks:
        name = added_guard(task.text)
        if name is None:
            continue
        if lines := definition_lines(source, sha, name, git):
            found.append(
                MESSAGES.roadmap.premise_guard_defined.format(
                    task=task.text.strip(), name=name, line=lines[0]
                )
            )
    return tuple(found)


__all__ = ["added_guard", "defines", "definition_lines", "false_premises"]
