"""The row `plan_drift`: a plan pull request that the default branch broke gets `plan/needs-fix`
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

A plan with problems gets the label `plan/needs-fix` and one marked comment that lists them. A
later round updates that comment in place, and a plan that passes again loses the label. A read
or write failure stops the round, since every later call would fail too.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass
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
from devops_cli.roadmap.stage.stage_paths import StagedTree
from devops_cli.roadmap.stage.stage_registry import registry_table
from devops_cli.roadmap.stage.stage_verify import PLAN_NEEDS_FIX_LABEL
from devops_cli.roadmap.stores.store import RoadmapStore, split_record

logger = logging.getLogger(__name__)

PLAN_DRIFT_MARKER: Final[str] = "<!-- devops roadmap plan drift -->"
PLAN_DRIFT_TITLE_PREFIX: Final[str] = "docs(openspec): plan #"
GIT_OPERATION: Final[str] = "roadmap.plan-drift"


class DriftReads(PlanReads, Protocol):
    """The GitHub reads and writes that the drift row makes."""

    def list_issue_comments(self, repo: str, number: int) -> list[IssueComment]:
        """The comments of issue or pull request `number`."""
        ...  # pragma: no cover - a protocol stub runs no code

    def create_issue_comment(self, repo: str, number: int, body: str) -> None:
        """Post `body` on issue or pull request `number`."""
        ...  # pragma: no cover - a protocol stub runs no code

    def update_issue_comment(self, repo: str, comment_id: int, body: str) -> None:
        """Replace the body of comment `comment_id`."""
        ...  # pragma: no cover - a protocol stub runs no code


@dataclass(frozen=True)
class PlanDriftRun:
    """What a round did: the plan pull requests it checked, and the ones whose plan changed
    against the default branch."""

    checked: tuple[int, ...] = ()
    failing: tuple[int, ...] = ()


def drift_comment(problems: Sequence[PlanProblem]) -> str:
    """The one marked comment of a drifted plan, which lists each problem (#3968)."""
    lines = [
        PLAN_DRIFT_MARKER,
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


def _update_comment(
    writes: DriftReads, repo: str, number: int, problems: Sequence[PlanProblem]
) -> None:
    """Keep one drift comment: create it when it is absent, and update it when its list
    changed (#3968)."""
    body = drift_comment(problems)
    listed = writes.list_issue_comments(repo, number)
    held = next((comment for comment in listed if PLAN_DRIFT_MARKER in comment.body), None)
    if held is None:
        writes.create_issue_comment(repo, number, body)
    elif held.body != body:
        writes.update_issue_comment(repo, held.id, body)


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
        if not pull.title.startswith(PLAN_DRIFT_TITLE_PREFIX):
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
        if not problems:
            if pull.number in store.labelled_pulls(PLAN_NEEDS_FIX_LABEL):
                store.unlabel_issue(pull.number, PLAN_NEEDS_FIX_LABEL)
            continue
        failing.append(pull.number)
        store.label_issue(pull.number, PLAN_NEEDS_FIX_LABEL)
        _update_comment(reads, repo, pull.number, problems)
        logger.info(
            MESSAGES.roadmap.plan_drift_failed.format(
                repo=repo, pull=pull.number, problems=len(problems)
            )
        )
    return PlanDriftRun(tuple(checked), tuple(failing))
