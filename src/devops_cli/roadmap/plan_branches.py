"""The open plan branches of `devops roadmap plan-recheck --branches` (#3969).

A plan pull request is judged once, when the stage job writes it. A gate that a later pull request
adds can strand the plan of an open branch: the branch keeps the old format, and a person must
rebase it, edit it and push it by hand. `--branches` reads each open draft plan pull request whose
base is the default branch, computes the mechanical rewrite (`plan_rewrite.rewrite_plan`) of the
change folder at its head, and gives one result for the branch:

- `rewritten`: the rewrite changes a file of the change folder. The pass rebases the branch onto
  the default branch, writes the rewrite, checks it and pushes it once with a lease.
- `unchanged`: the rewrite changes no file. The pass pushes nothing, also when the default branch
  moved past the branch: a branch that only fell behind is left alone.
- `conflict`: the rebase conflicts with the default branch. The pass aborts the rebase and pushes
  nothing.
- `invalid`: a check refuses the rewritten plan, or the head holds no change folder of the plan.
  The pass commits nothing and pushes nothing.

The rewrite is judged against the default-branch tree and not against the tree of the branch: a
path that the default branch gained since the branch forked is a file that the plan may name, and
`rewrite_plan` turns a path that the tree lacks into a bare name. The pass reads the same plan
reader, gates and OpenSpec check as `devops roadmap plan-check`, and it calls no model.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Final

from devops_cli.lang import MESSAGES
from devops_cli.roadmap.clone_git import git
from devops_cli.roadmap.plan_check import PlanReads, is_plan, issue_number, read_pull
from devops_cli.roadmap.plan_read import change_root, files_at, tree_files
from devops_cli.roadmap.plan_rewrite import PlanRewrite, rewrite_plan
from devops_cli.roadmap.stage.stage_paths import StagedTree
from devops_cli.roadmap.stores.store import RoadmapStore

GIT_OPERATION: Final[str] = "roadmap.plan-branches"


class BranchResult(StrEnum):
    """The one result of an open plan branch."""

    REWRITTEN = "rewritten"
    """The rewrite changes a file of the change folder: the pass pushes the branch."""
    UNCHANGED = "unchanged"
    """The rewrite changes no file: the pass pushes nothing."""
    CONFLICT = "conflict"
    """The rebase conflicts with the default branch: the pass pushes nothing."""
    INVALID = "invalid"
    """The rewritten plan fails a check, or the head holds no folder: the pass pushes nothing."""


@dataclass(frozen=True)
class PlanBranch:
    """One open draft plan pull request whose base is the default branch: the number and the branch
    of the pull request, and the issue that its body plans."""

    number: int
    branch: str
    issue: int


@dataclass(frozen=True)
class BranchRewrite:
    """The mechanical rewrite of the change folder of one open plan branch, and what the pass must
    do with it. `head` is the commit of the branch that the pass read, and `root` is the change
    folder at that commit, which is empty when the head holds none. `rewrite` holds the files of
    the rewrite and the files that differ, and is None when the head holds no folder to rewrite.
    `reason` says why a result of `conflict` or `invalid` happened."""

    pull: PlanBranch
    head: str
    root: str
    result: BranchResult
    rewrite: PlanRewrite | None = None
    reason: str = ""


def open_plan_pulls(
    store: RoadmapStore, reads: PlanReads, repo: str, default: str
) -> tuple[PlanBranch, ...]:
    """Each open draft plan pull request of `repo` whose base is `default`, lowest number first.

    A pull request is a plan when `is_plan` says so, and the body of a plan holds the line
    `Plans #<issue>`, which names the change folder of the branch. So a pull request that the
    implement job took over as the delivery of the item, a plan pull request that a person made
    ready, and a plan pull request of another base are left out, and they get no result."""
    kept: list[PlanBranch] = []
    for pull in sorted(store.open_pulls(), key=lambda listed: listed.number):
        if not pull.draft:
            continue
        facts = read_pull(reads, repo, pull.number)
        if facts.base_ref != default or not is_plan(facts):
            continue
        issue = issue_number(facts.body)
        if issue is None:
            continue
        kept.append(PlanBranch(pull.number, pull.head_ref, issue))
    return tuple(kept)


def branch_rewrite(source: Path, pull: PlanBranch, default: str, tree: StagedTree) -> BranchRewrite:
    """The mechanical rewrite of the change folder of `pull`, judged against the default-branch
    tree `tree`.

    The pass fetches the branch and the default branch first, so it reads the head that `origin`
    holds and not a stale ref of the clone, and a rebase onto `origin/<default>` needs no second
    fetch. A head that holds no change folder of the issue of the plan is `invalid`: no rewrite
    can bring a folder that the branch lacks."""
    git(source, "fetch", "-q", "origin", pull.branch, default, operation=GIT_OPERATION)
    head = git(source, "rev-parse", f"origin/{pull.branch}", operation=GIT_OPERATION)
    paths = tree_files(source, head, operation=GIT_OPERATION)
    root, _ = change_root(paths, pull.issue)
    if root is None:
        reason = MESSAGES.roadmap.plan_branches_no_folder.format(
            number=pull.number, issue=pull.issue, branch=pull.branch
        )
        return BranchRewrite(pull, head, "", BranchResult.INVALID, reason=reason)
    files = files_at(
        source,
        head,
        [path for path in paths if path.startswith(f"{root}/")],
        operation=GIT_OPERATION,
    )
    rewrite = rewrite_plan(root, files, tree)
    result = BranchResult.REWRITTEN if rewrite.changes else BranchResult.UNCHANGED
    return BranchRewrite(pull, head, root, result, rewrite)


__all__ = [
    "BranchResult",
    "BranchRewrite",
    "PlanBranch",
    "branch_rewrite",
    "open_plan_pulls",
]
