"""The open plan branches of `devops roadmap plan-recheck --branches` (#3969)."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date

from devops_cli.github.client import CommitRef, IssueView, PullRequest
from devops_cli.roadmap.plan_read import tree_files
from devops_cli.roadmap.stage.stage_change import render_change
from devops_cli.roadmap.stage.stage_paths import StagedTree
from tests.support.builders import make_stage_proposal
from tests.support.fakes.roadmap_store import InMemoryRoadmapStore
from tests.support.roadmap_stage import StageRepo

REPO = "example/roadmap"
PULL = 7
ISSUE = 1
BRANCH = "docs/1-keep-the-last-comment"
AHEAD = "docs/1-ahead"
TITLE = f"docs(openspec): plan #{ISSUE} Keep the last comment"
TASKS = f"openspec/changes/{ISSUE}-keep-the-last-comment/tasks.md"
CREATED = date(2026, 11, 4)


def _plan(issue: int = ISSUE) -> dict[str, str]:
    """The stock plan of `issue`, which the mechanical rewrite does not change."""
    change = f"{issue}-keep-the-last-comment"
    return render_change(change, make_stage_proposal(), {"comment-thread"}, created=CREATED)


def _without_verification(files: Mapping[str, str], issue: int = ISSUE) -> dict[str, str]:
    """`files` with every `Verification:` line of its `tasks.md` removed, so the rewrite adds one."""
    path = f"openspec/changes/{issue}-keep-the-last-comment/tasks.md"
    kept = [line for line in files[path].splitlines(keepends=True) if "Verification:" not in line]
    return {**files, path: "".join(kept)}


def _push(repo: StageRepo, branch: str, files: Mapping[str, str]) -> None:
    """Commit `files` on the branch `branch` of `origin`, from `main`, and leave the clone on
    `main`."""
    repo.git("switch", "-q", "-c", branch)
    for path, text in files.items():
        target = repo.clone / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
    repo.git("add", "-A")
    repo.git("commit", "-q", "-m", f"plan on {branch}")
    repo.git("push", "-q", "origin", branch)
    repo.git("switch", "-q", "main")


def _tree(repo: StageRepo) -> StagedTree:
    """The tracked files of the default branch, as the pass judges a rewrite against them."""
    # A local import: the fail-to-pass replay runs this module on a base tree that has no
    # `plan_branches` module, so each test fails in its call phase and not at collection.
    from devops_cli.roadmap.plan_branches import GIT_OPERATION

    return StagedTree(tree_files(repo.clone, "origin/main", operation=GIT_OPERATION))


def test_a_plan_that_the_rewrite_does_not_change_is_unchanged(stage_repo: StageRepo) -> None:
    """A branch whose plan the rewrite does not change is `unchanged`, and a branch whose plan
    lacks a `Verification:` line is `rewritten` with the new task list."""
    from devops_cli.roadmap.plan_branches import BranchResult, PlanBranch, branch_rewrite

    stage_repo.track(_plan())
    stage_repo.push_branch(BRANCH)
    _push(stage_repo, AHEAD, _without_verification(_plan()))
    tree = _tree(stage_repo)

    same = branch_rewrite(stage_repo.clone, PlanBranch(PULL, BRANCH, ISSUE), "main", tree)
    changed = branch_rewrite(stage_repo.clone, PlanBranch(PULL, AHEAD, ISSUE), "main", tree)

    assert same.result is BranchResult.UNCHANGED
    assert same.rewrite is not None
    assert same.rewrite.changes == ()
    assert changed.result is BranchResult.REWRITTEN
    assert changed.rewrite is not None
    assert [change.path for change in changed.rewrite.changes] == [TASKS]
    assert (
        "  - Verification: `$ uv run devops ci test tests/test_sample.py` fails on the base"
        in changed.rewrite.files[TASKS]
    )


def _pull(number: int, branch: str, *, title: str = TITLE, base: str = "main") -> PullRequest:
    return PullRequest(
        title=title,
        head=CommitRef(sha="a" * 40, ref=branch),
        base=CommitRef(sha="b" * 40, ref=base),
    )


def _issue(number: int, body: str, *, title: str = TITLE) -> IssueView:
    return IssueView(number=number, state="open", title=title, body=body)


class _Reads:
    """The GitHub reads of the pass, held in memory."""

    def __init__(self, pulls: dict[int, PullRequest], issues: dict[int, IssueView]) -> None:
        self.pulls = pulls
        self.issues = issues

    def get_pull(self, repo: str, number: int) -> PullRequest:
        del repo
        return self.pulls[number]

    def get_issue(self, repo: str, number: int) -> IssueView:
        del repo
        return self.issues[number]


def test_a_delivery_branch_is_no_plan_branch() -> None:
    """A pull request that holds the body of a delivery and no plan line is left out."""
    from devops_cli.roadmap.plan_branches import PlanBranch, open_plan_pulls

    store = InMemoryRoadmapStore()
    plan = store.seed_pull(TITLE, head_ref=BRANCH, draft=True)
    delivery = store.seed_pull(
        "feat(roadmap): deliver the plan", head_ref="feat/2-deliver", draft=True
    )
    reads = _Reads(
        {
            plan: _pull(plan, BRANCH),
            delivery: _pull(delivery, "feat/2-deliver", title="feat(roadmap): deliver the plan"),
        },
        {
            plan: _issue(plan, f"Plans #{ISSUE}"),
            delivery: _issue(delivery, "Closes #2", title="feat(roadmap): deliver the plan"),
        },
    )

    assert open_plan_pulls(store, reads, REPO, "main") == (PlanBranch(plan, BRANCH, ISSUE),)


def test_only_an_open_draft_plan_of_the_default_branch_is_a_plan_branch() -> None:
    """A plan pull request that is ready, and a plan pull request of another base, are left out."""
    from devops_cli.roadmap.plan_branches import PlanBranch, open_plan_pulls

    store = InMemoryRoadmapStore()
    kept = store.seed_pull(TITLE, head_ref=BRANCH, draft=True)
    ready = store.seed_pull(TITLE, head_ref="docs/1-ready", draft=False)
    other = store.seed_pull(TITLE, head_ref="docs/1-release", draft=True)
    reads = _Reads(
        {
            kept: _pull(kept, BRANCH),
            ready: _pull(ready, "docs/1-ready"),
            other: _pull(other, "docs/1-release", base="release"),
        },
        {number: _issue(number, f"Plans #{ISSUE}") for number in (kept, ready, other)},
    )

    assert open_plan_pulls(store, reads, REPO, "main") == (PlanBranch(kept, BRANCH, ISSUE),)


def test_a_branch_with_no_change_folder_is_invalid(stage_repo: StageRepo) -> None:
    """A head that holds no change folder of the plan is `invalid`, and it names the reason."""
    from devops_cli.roadmap.plan_branches import BranchResult, PlanBranch, branch_rewrite

    stage_repo.track({"README.md": "The branch plans nothing.\n"})
    stage_repo.push_branch(BRANCH)

    record = branch_rewrite(
        stage_repo.clone, PlanBranch(PULL, BRANCH, ISSUE), "main", _tree(stage_repo)
    )

    assert (record.result, record.rewrite, record.root) == (BranchResult.INVALID, None, "")
    assert f"#{PULL}" in record.reason
    assert f"`{BRANCH}`" in record.reason
