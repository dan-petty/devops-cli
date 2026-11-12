"""Whether a repository uses OpenSpec (#4629).

`openspec init` writes `openspec/config.yaml`, so that file marks a repository that plans with
OpenSpec. The roadmap jobs read it at a commit of the default branch, not in a checkout that an
agent edits, so a change on a branch cannot turn the switch. The stage job holds the items of a
repository without the file, and onboarding adds the file (#3770). `devops pr create` reads it on
the base branch of the pull request, and asks a body for the lines `Closes` and `Change:` only
where the file is (#3767). Each caller that must know whether a repository uses OpenSpec calls
`uses_openspec`, or `repository_uses_openspec` when it has no clone, so the repository has one
switch.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from devops_cli.config.constants import CONST_OPENSPEC_CONFIG_PATH
from devops_cli.exceptions.git import GitHubFileNotFoundError
from devops_cli.roadmap.clone_git import git

if TYPE_CHECKING:
    from devops_cli.roadmap.stores.store import RoadmapStore


def uses_openspec(source: Path, ref: str, *, operation: str) -> bool:
    """Whether commit `ref` of the clone at `source` holds `openspec/config.yaml`. A failed git
    command raises `GitOperationError` for `operation` with the reason of git, so a job never
    takes a read that failed as a repository without OpenSpec."""
    listed = git(
        source, "ls-tree", "--name-only", ref, "--", CONST_OPENSPEC_CONFIG_PATH, operation=operation
    )
    return bool(listed)


def repository_uses_openspec(store: RoadmapStore, *, ref: str | None) -> bool:
    """Whether branch `ref` (the default branch when None) of the repository of `store` holds
    `openspec/config.yaml`, read through the contents API. Only a missing file reads as False: a
    read that fails for another reason raises the error of the store, so a command never takes it
    as a repository without OpenSpec."""
    try:
        store.repository_file(CONST_OPENSPEC_CONFIG_PATH, ref=ref)
    except GitHubFileNotFoundError:
        return False
    return True


__all__ = ["repository_uses_openspec", "uses_openspec"]
