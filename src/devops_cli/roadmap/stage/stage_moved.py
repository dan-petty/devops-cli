"""The named paths of a plan that the default branch changed after the plan's base (#3309).

A staged plan can rest on a base that the default branch has moved past, and the reviewer then
reads facts about the files that the plan names that are no longer true. `moved_paths` gives the
commits that changed each named path after the base, from the clone that the stage job holds, so
the comment of the staged item can list them.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from devops_cli.roadmap.clone_git import git

# The short hash and the subject of a commit in one line, split by a NUL that no text holds, and
# then the files of the commit, one on each line.
_COMMIT_FORMAT: Final[str] = "--format=%h%x00%s"
_NULL: Final[str] = "\0"
_LOG_OPERATION: Final[str] = "roadmap.stage.moved"


@dataclass(frozen=True)
class MovedPath:
    """A path that a commit changed after the base, with the commits that changed it, as
    `<short hash> <subject>`, in log order."""

    path: str
    commits: tuple[str, ...]


def _commits_by_path(log: str) -> dict[str, list[str]]:
    """The commits of each path in the output of the log, in the order that the log gives them. A
    line with a NUL holds the hash and the subject of a commit, and a line without one holds a file
    of that commit."""
    commits: dict[str, list[str]] = {}
    commit = ""
    for line in log.splitlines():
        if _NULL in line:
            short, _, subject = line.partition(_NULL)
            commit = f"{short} {subject}".strip()
        elif line and commit:
            commits.setdefault(line, []).append(commit)
    return commits


def moved_paths(source: Path, base: str, branch: str, paths: Iterable[str]) -> list[MovedPath]:
    """The paths in `paths` that a commit of `base..branch` changed, in the order that `paths` gives
    them, each with its commits in log order. `source` is the clone, `base` the commit that the
    planner read, and `branch` the branch of the remote that the job fetched. A failed command
    raises `GitOperationError`, so the job never writes a comment on a comparison it could not
    read."""
    named = list(dict.fromkeys(path for path in paths if path))
    if not named:
        return []
    log = git(
        source,
        "log",
        _COMMIT_FORMAT,
        "--name-only",
        f"{base}..{branch}",
        "--",
        *named,
        operation=_LOG_OPERATION,
    )
    commits = _commits_by_path(log)
    return [MovedPath(path, tuple(commits[path])) for path in named if path in commits]
