"""Whether a repository uses OpenSpec (#4629).

`openspec init` writes `openspec/config.yaml`, so that file marks a repository that plans with
OpenSpec. The roadmap jobs read it at a commit of the default branch, not in a checkout that an
agent edits, so a change on a branch cannot turn the switch. The stage job holds the items of a
repository without the file, and onboarding adds the file (#3770). Each caller that must know
whether a repository uses OpenSpec calls `uses_openspec`, so the repository has one switch.
"""

from __future__ import annotations

from pathlib import Path

from devops_cli.config.constants import CONST_OPENSPEC_CONFIG_PATH
from devops_cli.roadmap.clone_git import git


def uses_openspec(source: Path, ref: str, *, operation: str) -> bool:
    """Whether commit `ref` of the clone at `source` holds `openspec/config.yaml`. A failed git
    command raises `GitOperationError` for `operation` with the reason of git, so a job never
    takes a read that failed as a repository without OpenSpec."""
    listed = git(
        source, "ls-tree", "--name-only", ref, "--", CONST_OPENSPEC_CONFIG_PATH, operation=operation
    )
    return bool(listed)


__all__ = ["uses_openspec"]
