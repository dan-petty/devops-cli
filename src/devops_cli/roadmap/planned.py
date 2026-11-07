"""The plans on the default branch (#2714): which OpenSpec changes `origin/<default branch>` holds.

A person can merge the draft pull request of the stage job at any time. Its branch is then gone,
and the change folder `openspec/changes/<issue>-<slug>/` is on the default branch. The tree of
the default branch is the one record of that, so both roadmap jobs read it: stage leaves such an
item out, and implement takes it as a Planned item. A change that `openspec archive` moved to
`openspec/changes/archive/<date>-<issue>-<slug>/` is done work.

One `git ls-tree` of the two directories lists every folder of both. A folder belongs to the
issue that its name starts with, whatever its slug (`CONST_OPENSPEC_CHANGE_NAME_RE`).
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from devops_cli.config.constants import (
    CONST_OPENSPEC_ARCHIVE_DIR,
    CONST_OPENSPEC_ARCHIVED_DIR_RE,
    CONST_OPENSPEC_CHANGE_DIR_RE,
    CONST_OPENSPEC_CHANGES_DIR,
    CONST_ROADMAP_PLANNED_LIMIT_PRIORITIES,
    CONST_ROADMAP_STATUS_PLANNED,
)
from devops_cli.roadmap.clone_git import default_branch, git
from devops_cli.roadmap.plan_read import created_paths
from devops_cli.roadmap.stores.store import GitHubState, Item

if TYPE_CHECKING:
    from devops_cli.roadmap.stores.store import RoadmapStore

_ACTIVE = re.compile(CONST_OPENSPEC_CHANGE_DIR_RE)
_ARCHIVED = re.compile(CONST_OPENSPEC_ARCHIVED_DIR_RE)


@dataclass(frozen=True)
class PlannedChanges:
    """The change folders of `origin/<default>`, by issue number: the active ones
    (`<issue>-<slug>`) and the archived ones (`<date>-<issue>-<slug>`)."""

    default: str
    active: Mapping[int, str]
    archived: Mapping[int, str]


def planned_count(items: Iterable[Item]) -> int:
    """How many of `items` are open and Planned (#3487): the plans that wait for a delivery. The
    stage job and the inbox count the queue with this one function."""
    return sum(
        1
        for item in items
        if item.state is GitHubState.OPEN and item.status == CONST_ROADMAP_STATUS_PLANNED
    )


def planned_limit_priorities() -> str:
    """The priorities that the stage job plans at the limit (#3692), as the texts of the job and
    the inbox name them."""
    return " or ".join(CONST_ROADMAP_PLANNED_LIMIT_PRIORITIES)


def _folders(listing: str, pattern: re.Pattern[str]) -> dict[int, str]:
    """The folder name of each path in `listing` that `pattern` matches, by issue number. When two
    folders name one issue, the one that sorts first."""
    found: dict[int, str] = {}
    for path in sorted(listing.splitlines()):
        match = pattern.fullmatch(path)
        if match is not None:
            found.setdefault(int(match["issue"]), path.rpartition("/")[2])
    return found


def planned_changes_at(source: Path, rev: str, default: str, *, operation: str) -> PlannedChanges:
    """The plans at commit `rev` of the clone at `source`, named for the default branch `default`
    (#3498). One `git ls-tree` reads the folders of both directories. A failed command raises
    `GitOperationError` with the reason of git."""
    listing = git(
        source,
        "ls-tree",
        "--name-only",
        rev,
        f"{CONST_OPENSPEC_CHANGES_DIR}/",
        f"{CONST_OPENSPEC_ARCHIVE_DIR}/",
        operation=operation,
    )
    return PlannedChanges(default, _folders(listing, _ACTIVE), _folders(listing, _ARCHIVED))


def read_planned_changes(source: Path, *, operation: str) -> PlannedChanges:
    """The plans on the default branch of the clone at `source`, after a fetch of that branch. A
    failed command raises `GitOperationError` with the reason of git, so a job never judges an
    item on a tree it could not read."""
    default = default_branch(source, operation=operation)
    git(source, "fetch", "-q", "origin", default, operation=operation)
    return planned_changes_at(source, f"origin/{default}", default, operation=operation)


def tasks_on_default(source: Path, planned: PlannedChanges, folder: str, *, operation: str) -> str:
    """The text of `tasks.md` of the active change `folder` on `origin/<default>`."""
    path = f"{CONST_OPENSPEC_CHANGES_DIR}/{folder}/tasks.md"
    return git(source, "show", f"origin/{planned.default}:{path}", operation=operation)


def open_plan_creates(
    store: RoadmapStore, source: Path, planned: PlannedChanges, *, operation: str
) -> dict[str, int]:
    """The paths that the active change of each open item on the default branch marks `(new)`,
    each with the number of its item (#3418). A closed item and an archived change create nothing
    for this purpose, so a plan that a closed item left behind names no dependency."""
    found: dict[str, int] = {}
    for number, folder in sorted(planned.active.items()):
        item = store.item(number)
        if item is None or item.state is not GitHubState.OPEN:
            continue
        tasks = tasks_on_default(source, planned, folder, operation=operation)
        for path in created_paths(tasks):
            found.setdefault(path, number)
    return found
