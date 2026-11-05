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

from collections.abc import Callable
from typing import TYPE_CHECKING

from devops_cli.roadmap.refine import SYMBOL_PATHSPEC, git_result

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


__all__ = ["defines", "definition_lines"]
