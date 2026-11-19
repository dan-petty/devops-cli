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
- `conflict`: the rebase conflicts with the default branch, or the rebased tree does not hold the
  plan that the rewrite expects. The pass aborts the rebase and pushes nothing.
- `invalid`: a check refuses the rewritten plan, or the head holds no change folder of the plan.
  The pass commits nothing and pushes nothing.

`--confirm` pushes each rewritten branch once, with `--force-with-lease` on the head that the pass
read, so a push that another session made is refused and never overwritten. The push event starts
the checks of the pull request, so the pass dispatches no workflow.

The rewrite is judged against the default-branch tree and not against the tree of the branch: a
path that the default branch gained since the branch forked is a file that the plan may name, and
`rewrite_plan` turns a path that the tree lacks into a bare name. The pass reads the same plan
reader, gates and OpenSpec check as `devops roadmap plan-check`, and it calls no model.
"""

from __future__ import annotations

import logging
from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass, replace
from enum import StrEnum
from pathlib import Path, PurePosixPath
from typing import Final

from devops_cli.exceptions.git import GitOperationError
from devops_cli.exceptions.roadmap import RoadmapPlanRewriteError
from devops_cli.lang import MESSAGES
from devops_cli.openspec.tool import OpenSpecTool
from devops_cli.roadmap.clone_git import checkout_at, default_branch, git
from devops_cli.roadmap.plan_check import PlanReads, is_plan, issue_number, read_pull
from devops_cli.roadmap.plan_read import (
    PlanReadError,
    change_root,
    files_at,
    read_change,
    scenario_names_at,
    specs_at,
    tree_files,
)
from devops_cli.roadmap.plan_rewrite import PlanRewrite, rewrite_plan, write_rewrite
from devops_cli.roadmap.stage.stage_change import check_gates
from devops_cli.roadmap.stage.stage_paths import StagedTree
from devops_cli.roadmap.stage.stage_registry import RegistryCount, registry_table
from devops_cli.roadmap.stage.stage_validate import validate_change
from devops_cli.roadmap.stores.store import RoadmapStore

GIT_OPERATION: Final[str] = "roadmap.plan-branches"
logger = logging.getLogger(__name__)


class BranchResult(StrEnum):
    """The one result of an open plan branch."""

    REWRITTEN = "rewritten"
    """The rewrite changes a file of the change folder: the pass pushes the branch."""
    UNCHANGED = "unchanged"
    """The rewrite changes no file: the pass pushes nothing."""
    CONFLICT = "conflict"
    """The rebase conflicts, or the rebased tree does not hold the rewrite: the pass pushes nothing."""
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

    @property
    def folder(self) -> str:
        """The name of the change folder, as `openspec validate` reads it."""
        return PurePosixPath(self.root).name


@dataclass(frozen=True)
class BranchRun:
    """The result of the pass over the open plan branches of `repo`: the default branch, whether
    the run confirmed a push, and one record for each open plan branch, lowest number first."""

    repo: str
    default: str
    confirm: bool
    branches: tuple[BranchRewrite, ...]

    def count(self, result: BranchResult) -> int:
        """How many branches got `result`."""
        return sum(1 for branch in self.branches if branch.result is result)


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


def _unmerged(worktree: Path) -> tuple[str, ...]:
    """The paths that a rebase left unmerged in `worktree`."""
    listing = git(worktree, "diff", "--name-only", "--diff-filter=U", operation=GIT_OPERATION)
    return tuple(path for path in listing.splitlines() if path)


def _abort(worktree: Path) -> None:
    """Abort the rebase of `worktree`. A rebase that failed before it started has nothing to
    abort, and `checkout_at` removes the worktree either way."""
    try:
        git(worktree, "rebase", "--abort", operation=GIT_OPERATION)
    except GitOperationError as exc:
        logger.warning("Could not abort the rebase of %s: %s", worktree, exc)


def _conflict_reason(target: BranchRewrite, default: str, paths: tuple[str, ...]) -> str:
    """The reason of a conflict: the branch, the default branch, and the files that are not
    merged."""
    texts = MESSAGES.roadmap
    reason = texts.plan_branches_conflict.format(branch=target.pull.branch, default=default)
    if paths:
        listed = ", ".join(f"`{path}`" for path in paths)
        reason += texts.plan_branches_conflict_paths.format(paths=listed)
    return reason


def _rebase(worktree: Path, target: BranchRewrite, default: str) -> str | None:
    """Rebase the detached `worktree` onto `origin/<default>`, and give the reason of a conflict, or
    None when the rebase went through. A conflict aborts the rebase, so no rebase stays open."""
    try:
        git(worktree, "rebase", "-q", f"origin/{default}", operation=GIT_OPERATION)
    except GitOperationError:
        paths = _unmerged(worktree)
        _abort(worktree)
        return _conflict_reason(target, default, paths)
    return None


def _plan_problem(
    worktree: Path,
    target: BranchRewrite,
    rewrite: PlanRewrite,
    *,
    tool: OpenSpecTool,
    tree: StagedTree,
    known: Collection[str],
    requirements: Mapping[str, Collection[str]],
    base_scenarios: Mapping[str, Collection[str]],
    issue_body: str,
    registry: Sequence[RegistryCount] = (),
) -> str | None:
    """What the plan reader, the gates or `openspec validate` find wrong in the rewritten plan, or
    None when every check passes."""
    texts = MESSAGES.roadmap
    try:
        proposal = read_change(rewrite.files)
    except PlanReadError as exc:
        return texts.plan_check_read.format(path=exc.path, reason=exc.reason)
    found = check_gates(
        proposal,
        known,
        tree,
        requirements=requirements,
        base_scenarios=base_scenarios,
        issue_body=issue_body,
        registry=registry,
    )
    problems = [problem for gate in found.values() for problem in gate]
    if problems:
        return " ".join(problems)
    report = validate_change(tool, worktree, target.folder, rewrite.files)
    if report is None:
        return None
    return texts.plan_recheck_openspec.format(problem=" ".join(report.split()))


def push_rewrite(
    source: Path,
    target: BranchRewrite,
    rewrite: PlanRewrite,
    default: str,
    *,
    tool: OpenSpecTool,
    tree: StagedTree,
    known: Collection[str],
    requirements: Mapping[str, Collection[str]],
    base_scenarios: Mapping[str, Collection[str]],
    issue_body: str = "",
    registry: Sequence[RegistryCount] = (),
) -> BranchRewrite:
    """Rebase the branch of `target` onto `default` in a detached worktree, write `rewrite` there,
    check it, and push it as one commit with a lease on the head that the pass read.

    A rebase that conflicts, and a rebased tree that the rewrite does not fit because the default
    branch changed the same file, give `BranchResult.CONFLICT`. A rewritten plan that the reader,
    a gate or `openspec validate` refuses gives `BranchResult.INVALID`. Neither commits and neither
    pushes. The worktree goes at the end of the call, so a stopped run changes nothing in the
    checkout of the caller."""
    branch, head = target.pull.branch, target.head
    texts = MESSAGES.roadmap
    with checkout_at(source, head, operation=GIT_OPERATION) as worktree:
        conflict = _rebase(worktree, target, default)
        if conflict is not None:
            return replace(target, result=BranchResult.CONFLICT, reason=conflict)
        try:
            paths = write_rewrite(worktree, [rewrite])
        except RoadmapPlanRewriteError as exc:
            reason = texts.plan_branches_unfit.format(
                branch=branch, default=default, reason=exc.message
            )
            return replace(target, result=BranchResult.CONFLICT, reason=reason)
        problem = _plan_problem(
            worktree,
            target,
            rewrite,
            tool=tool,
            tree=tree,
            known=known,
            requirements=requirements,
            base_scenarios=base_scenarios,
            issue_body=issue_body,
            registry=registry,
        )
        if problem is not None:
            reason = texts.plan_branches_invalid.format(
                number=target.pull.number, branch=branch, reason=problem
            )
            return replace(target, result=BranchResult.INVALID, reason=reason)
        git(worktree, "add", "--", *paths, operation=GIT_OPERATION)
        git(
            worktree,
            "commit",
            "-q",
            "-m",
            texts.plan_branches_commit.format(issue=target.pull.issue),
            "-m",
            texts.plan_branches_commit_body,
            operation=GIT_OPERATION,
        )
        pushed = git(worktree, "rev-parse", "HEAD", operation=GIT_OPERATION)
        lease = f"--force-with-lease=refs/heads/{branch}:{head}"
        git(
            worktree,
            "push",
            "-q",
            lease,
            "origin",
            f"HEAD:refs/heads/{branch}",
            operation=GIT_OPERATION,
        )
    return replace(target, result=BranchResult.REWRITTEN, head=pushed)


def rewrite_open_branches(
    store: RoadmapStore,
    reads: PlanReads,
    repo: str,
    source: Path,
    *,
    tool: OpenSpecTool,
    confirm: bool = False,
) -> BranchRun:
    """Judge the change folder of each open plan branch of `repo`, and with `confirm`, push each
    branch whose rewrite changes a file.

    The pass reads the tree, the base specs and the scenarios of the default branch once, and it
    fetches that branch first, so the rewrite sees the files that the branch will hold after the
    rebase. A run without `confirm` pushes nothing, and so does a branch whose result is
    `unchanged`, `conflict` or `invalid`."""
    default = default_branch(source, operation=GIT_OPERATION)
    git(source, "fetch", "-q", "origin", default, operation=GIT_OPERATION)
    rev = f"origin/{default}"
    paths = tree_files(source, rev, operation=GIT_OPERATION)
    tree = StagedTree(paths)
    known, requirements = specs_at(source, rev, operation=GIT_OPERATION, files=paths)
    base_scenarios = scenario_names_at(source, rev, operation=GIT_OPERATION, files=paths)
    registry = registry_table(source)
    records: list[BranchRewrite] = []
    for pull in open_plan_pulls(store, reads, repo, default):
        record = branch_rewrite(source, pull, default, tree)
        if confirm and record.result is BranchResult.REWRITTEN and record.rewrite is not None:
            item = store.item(pull.issue)
            record = push_rewrite(
                source,
                record,
                record.rewrite,
                default,
                tool=tool,
                tree=tree,
                known=known,
                requirements=requirements,
                base_scenarios=base_scenarios,
                issue_body=item.body if item is not None else "",
                registry=registry,
            )
        records.append(record)
    return BranchRun(repo, default, confirm, tuple(records))


def render_branch_run(run: BranchRun) -> str:
    """The report of the pass: one line for each open plan branch with its result, the files that
    its rewrite changes and the reason that it left the branch as it is, then the counts."""
    texts = MESSAGES.roadmap
    lines: list[str] = []
    for record in run.branches:
        lines.append(
            texts.plan_branches_line.format(
                number=record.pull.number, branch=record.pull.branch, result=record.result.value
            )
        )
        changes = record.rewrite.changes if record.rewrite is not None else ()
        lines.extend(texts.plan_branches_change.format(path=change.path) for change in changes)
        if record.reason:
            lines.append(texts.plan_branches_reason.format(reason=record.reason))
    if not run.branches:
        lines.append(texts.plan_branches_none)
    lines.append(
        texts.plan_branches_results.format(
            branches=len(run.branches),
            rewritten=run.count(BranchResult.REWRITTEN),
            unchanged=run.count(BranchResult.UNCHANGED),
            conflict=run.count(BranchResult.CONFLICT),
            invalid=run.count(BranchResult.INVALID),
        )
    )
    return "\n".join(lines)


__all__ = [
    "BranchResult",
    "BranchRewrite",
    "BranchRun",
    "PlanBranch",
    "branch_rewrite",
    "open_plan_pulls",
    "push_rewrite",
    "render_branch_run",
    "rewrite_open_branches",
]
