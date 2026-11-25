"""The row `plan_drift`: a plan pull request that the default branch broke gets `verdict/fix-plan`
(#3968).

The Service opens one plan pull request for each staged item. A later merge can make an open plan
invalid: a module moves, or a new rule refuses a task that was legal when the planner wrote it.
GitHub re-runs no check without a push, so the draft waits until a person finds the drift.

This row reads every open pull request of the repository. It keeps the plan pull requests: the
title holds the plan form, the base is the default branch, and `is_plan` excludes a pull request
that the implement job has taken over as a delivery. For each plan it reads the change folder at
the pull request head and runs the deterministic gates of the plan check against the head of the
default branch, which is where a moved path is missing. It calls no model, and it runs before
`stage_ready`, so a drifted draft holds its label before readiness is decided.

A plan with problems gets the label `verdict/fix-plan` and one marked comment that lists them. A
later round updates that comment in place. The stage review, the step fix-plan and a vet write the
same label, so the comment also holds the claim of the row (`DriftClaim`): `added` when the row
added the label, `held` when another check held it at the first round with problems (#5884). A
plan that passes again gets the claim `cleared`, and it loses the label only when the claim was
`added` and the last plan comment of the item lists no open finding (`plan_comment`). A label of
another check stays until that check clears it, so `stage_ready` keeps the draft. A read or write
failure stops the round, since every later call would fail too.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Final, Protocol

from devops_cli.config.settings import load_settings
from devops_cli.github.client import IssueComment
from devops_cli.lang import MESSAGES
from devops_cli.roadmap.clone_git import checkout_at, default_branch, git
from devops_cli.roadmap.plan_check import (
    PlanFolder,
    PlanProblem,
    PlanReads,
    PullFacts,
    folder_problems,
    is_plan,
    issue_number,
    read_pull,
)
from devops_cli.roadmap.plan_read import change_root, scenario_names_at, specs_at, tree_files
from devops_cli.roadmap.pr_verdict import PLAN_TITLE_PREFIX, is_plan_title
from devops_cli.roadmap.stage.stage_paths import StagedTree
from devops_cli.roadmap.stage.stage_registry import registry_table
from devops_cli.roadmap.stage.stage_verify import FIX_PLAN_LABEL
from devops_cli.roadmap.steps.fix_plan import comment_open_findings, plan_comment
from devops_cli.roadmap.stores.store import RoadmapStore, split_record

logger = logging.getLogger(__name__)

PLAN_DRIFT_MARKER: Final[str] = "<!-- devops roadmap plan drift -->"
PLAN_DRIFT_TITLE_PREFIX: Final[str] = PLAN_TITLE_PREFIX
GIT_OPERATION: Final[str] = "roadmap.plan-drift"


class DriftClaim(StrEnum):
    """What the drift comment says about the label `verdict/fix-plan` (#5884)."""

    ADDED = "added"
    """The plan has problems, and the row added the label: a passing round removes it."""
    HELD = "held"
    """The plan has problems, and another check held the label first: the label stays."""
    CLEARED = "cleared"
    """The plan passes again: the comment gives no claim."""


# The hidden line of the drift comment for each claim but `added`. A comment with the marker and
# neither line lists problems that the row labelled.
_CLAIM_LINES: Final[dict[DriftClaim, str]] = {
    DriftClaim.HELD: "<!-- devops roadmap plan drift: label held -->",
    DriftClaim.CLEARED: "<!-- devops roadmap plan drift: cleared -->",
}


class DriftReads(PlanReads, Protocol):
    """The GitHub reads and writes that the drift row makes."""

    def list_issue_comments(self, repo: str, number: int) -> list[IssueComment]: ...
    def create_issue_comment(self, repo: str, number: int, body: str) -> None: ...
    def update_issue_comment(self, repo: str, comment_id: int, body: str) -> None: ...


@dataclass(frozen=True)
class PlanDriftRun:
    """What a round did: the plan pull requests it checked, and the ones whose plan changed
    against the default branch."""

    checked: tuple[int, ...] = ()
    failing: tuple[int, ...] = ()


def drift_claim(body: str) -> DriftClaim:
    """The claim of the drift comment `body` (#5884)."""
    return next((claim for claim, line in _CLAIM_LINES.items() if line in body), DriftClaim.ADDED)


def drift_cleared_comment() -> str:
    """The drift comment of a plan that passes again (#5884)."""
    return "\n".join(
        [
            PLAN_DRIFT_MARKER,
            _CLAIM_LINES[DriftClaim.CLEARED],
            "",
            MESSAGES.roadmap.plan_drift_comment_cleared,
        ]
    )


def drift_comment(problems: Sequence[PlanProblem], *, held: bool = False) -> str:
    """The one marked comment of a drifted plan, which lists each problem (#3968). `held` says
    that another check held the label `verdict/fix-plan` first (#5884)."""
    lines = [
        PLAN_DRIFT_MARKER,
        *([_CLAIM_LINES[DriftClaim.HELD]] if held else []),
        "",
        MESSAGES.roadmap.plan_drift_comment_intro,
        "",
        *(
            MESSAGES.roadmap.plan_drift_comment_item.format(problem=problem.line)
            for problem in problems
        ),
    ]
    return "\n".join(lines)


def plan_drift_problems(
    source: Path,
    *,
    repo: str,
    number: int,
    facts: PullFacts,
    issue: int,
    reads: PlanReads,
    branch: str,
) -> list[PlanProblem]:
    """The problems of plan pull request `number` against the head of `branch`: the change folder
    comes from the pull request head, and the tree and the base specs come from the default
    branch."""
    git(source, "fetch", "--quiet", "origin", f"refs/pull/{number}/head", operation=GIT_OPERATION)
    head = git(source, "rev-parse", "FETCH_HEAD", operation=GIT_OPERATION)
    files = tree_files(source, head, operation=GIT_OPERATION)
    root, root_problems = change_root(files, issue)
    if root is None:
        return [
            PlanProblem("openspec/changes", "change-folder", message) for message in root_problems
        ]
    changed = [path for path in files if path == root or path.startswith(f"{root}/")]
    base = git(source, "rev-parse", f"origin/{branch}", operation=GIT_OPERATION)
    base_files = tree_files(source, base, operation=GIT_OPERATION)
    known, requirements = specs_at(source, base, operation=GIT_OPERATION, files=base_files)
    base_scenarios = scenario_names_at(source, base, operation=GIT_OPERATION, files=base_files)
    planned = reads.get_issue(repo, issue)
    body, _ = split_record(planned.body or "", issue=f"#{issue}")
    item_title = planned.title
    with checkout_at(source, head, operation=GIT_OPERATION) as plan_tree:
        texts = {
            path: (plan_tree / path).read_text(encoding="utf-8", errors="replace")
            for path in changed
        }
    with checkout_at(source, base, operation=GIT_OPERATION) as tree:
        folder = PlanFolder(
            root=root,
            files=texts,
            checkout=tree,
            tree=StagedTree(base_files),
            known=known,
            requirements=requirements,
            base_scenarios=base_scenarios,
            item_title=item_title,
            item_body=body,
            budget=load_settings().roadmap.stage.step_tokens,
            registry=registry_table(tree),
        )
        _, problems = folder_problems(folder)
    return problems


def _drift_comment_of(reads: DriftReads, repo: str, number: int) -> IssueComment | None:
    """The drift comment of pull request `number`, or None when the row never wrote one."""
    listed = reads.list_issue_comments(repo, number)
    return next((comment for comment in listed if PLAN_DRIFT_MARKER in comment.body), None)


def _has_open_finding(store: RoadmapStore, issue: int, pull: int) -> bool:
    """Whether the last plan comment of item `issue` for pull request `pull` lists an open finding
    (#5884). A line that does not read as a finding counts as one."""
    listed = comment_open_findings(plan_comment(store, issue, pull))
    return bool(listed.findings or listed.unreadable)


def _clear(
    store: RoadmapStore,
    writes: DriftReads,
    *,
    repo: str,
    pull: int,
    issue: int,
    comment: IssueComment | None,
) -> None:
    """Clear the claim of the drift comment `comment` of a plan that passes, and remove the label
    `verdict/fix-plan` only when the row added it and no open finding of the plan comment keeps it
    (#5884)."""
    if comment is None:
        return
    claim = drift_claim(comment.body)
    if claim is DriftClaim.CLEARED:
        return
    if (
        claim is DriftClaim.ADDED
        and pull in store.labelled_pulls(FIX_PLAN_LABEL)
        and not _has_open_finding(store, issue, pull)
    ):
        store.unlabel_issue(pull, FIX_PLAN_LABEL)
    writes.update_issue_comment(repo, comment.id, drift_cleared_comment())


def run_plan_drift(
    store: RoadmapStore,
    *,
    repo: str,
    source: Path,
    reads: DriftReads | None = None,
) -> PlanDriftRun:
    """Check each open plan pull request of `repo` against the default branch, and label, comment
    or clear it (#3968)."""
    if reads is None:
        from devops_cli.github.session import get_github_session

        reads = get_github_session().client
    branch = default_branch(source, operation=GIT_OPERATION)
    checked: list[int] = []
    failing: list[int] = []
    for pull in store.open_pulls():
        if not is_plan_title(pull.title):
            continue
        facts = read_pull(reads, repo, pull.number)
        if not is_plan(facts) or facts.base_ref != branch:
            continue
        issue = issue_number(facts.body)
        if issue is None:
            continue
        checked.append(pull.number)
        problems = plan_drift_problems(
            source,
            repo=repo,
            number=pull.number,
            facts=facts,
            issue=issue,
            reads=reads,
            branch=branch,
        )
        comment = _drift_comment_of(reads, repo, pull.number)
        if not problems:
            _clear(store, reads, repo=repo, pull=pull.number, issue=issue, comment=comment)
            continue
        failing.append(pull.number)
        added = comment is not None and drift_claim(comment.body) is DriftClaim.ADDED
        labelled = pull.number in store.labelled_pulls(FIX_PLAN_LABEL)
        body = drift_comment(problems, held=labelled and not added)
        store.label_issue(pull.number, FIX_PLAN_LABEL)
        if comment is None:
            reads.create_issue_comment(repo, pull.number, body)
        elif comment.body != body:
            reads.update_issue_comment(repo, comment.id, body)
        logger.info(
            MESSAGES.roadmap.plan_drift_failed.format(
                repo=repo, pull=pull.number, problems=len(problems)
            )
        )
    return PlanDriftRun(tuple(checked), tuple(failing))
