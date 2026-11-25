"""The open plan branches of `devops roadmap plan-recheck --branches` (#3969)."""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from datetime import date
from typing import TYPE_CHECKING

import pytest

from devops_cli.github.client import CommitRef, IssueView, PullRequest
from devops_cli.openspec.tool import isolated_openspec
from devops_cli.roadmap.plan_read import tree_files
from devops_cli.roadmap.stage.stage_change import render_change
from devops_cli.roadmap.stage.stage_paths import StagedTree
from tests.support.builders import make_stage_proposal
from tests.support.fakes.roadmap_store import InMemoryRoadmapStore
from tests.support.roadmap_stage import VALID_REPORT, StageRepo, validate_args

if TYPE_CHECKING:
    from devops_cli.openspec.tool import OpenSpecTool
    from tests.support.fakes.openspec import OpenSpecFake

REPO = "example/roadmap"
PULL = 7
ISSUE = 1
BRANCH = "docs/1-keep-the-last-comment"
AHEAD = "docs/1-ahead"
TITLE = f"docs(spec): plan #{ISSUE} Keep the last comment"
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


REJECTION = "The change breaks a rule of OpenSpec."


@pytest.fixture
def tool(openspec_fake: OpenSpecFake) -> Iterator[OpenSpecTool]:
    """The pinned OpenSpec, which accepts the change folder of each of the issues 1 to 3."""
    for issue in range(1, 4):
        openspec_fake.script(validate_args(f"{issue}-keep-the-last-comment"), 0, VALID_REPORT)
    with isolated_openspec() as pinned:
        yield pinned


def _head(repo: StageRepo, branch: str) -> str:
    """The commit that `branch` holds on `origin`."""
    return repo.origin_git("rev-parse", f"refs/heads/{branch}")


def _judge(repo: StageRepo) -> dict[str, object]:
    """The facts that the validation of a rewritten plan reads at the default branch."""
    from devops_cli.roadmap.plan_branches import GIT_OPERATION
    from devops_cli.roadmap.plan_read import scenario_names_at, specs_at

    rev = "origin/main"
    known, requirements = specs_at(repo.clone, rev, operation=GIT_OPERATION)
    return {
        "tree": _tree(repo),
        "known": known,
        "requirements": requirements,
        "base_scenarios": scenario_names_at(repo.clone, rev, operation=GIT_OPERATION),
    }


def _plan_pull(branch: str) -> tuple[InMemoryRoadmapStore, _Reads, int]:
    """A store with one open draft plan pull request on `branch`, its reads, and its number."""
    store = InMemoryRoadmapStore()
    number = store.seed_pull(TITLE, head_ref=branch, draft=True)
    reads = _Reads({number: _pull(number, branch)}, {number: _issue(number, f"Plans #{ISSUE}")})
    return store, reads, number


def _edited(files: Mapping[str, str], old: str, new: str) -> dict[str, str]:
    """`files` with `old` replaced by `new` in the `tasks.md` of the plan of `ISSUE`."""
    return {**files, TASKS: files[TASKS].replace(old, new)}


def test_a_rewrite_pushes_exactly_once(stage_repo: StageRepo, tool: OpenSpecTool) -> None:
    """A branch whose plan the rewrite changes is rebased, written and pushed as one commit, with a
    lease on the head that the pass read."""
    from devops_cli.roadmap.plan_branches import (
        BranchResult,
        PlanBranch,
        branch_rewrite,
        push_rewrite,
    )

    stage_repo.track(_plan())
    _push(stage_repo, AHEAD, _without_verification(_plan()))
    record = branch_rewrite(
        stage_repo.clone, PlanBranch(PULL, AHEAD, ISSUE), "main", _tree(stage_repo)
    )
    before = _head(stage_repo, AHEAD)
    assert record.result is BranchResult.REWRITTEN
    assert record.rewrite is not None

    pushed = push_rewrite(
        stage_repo.clone, record, record.rewrite, "main", tool=tool, **_judge(stage_repo)
    )

    assert pushed.result is BranchResult.REWRITTEN
    after = _head(stage_repo, AHEAD)
    assert after == pushed.head
    assert stage_repo.origin_git("rev-list", "--count", f"{before}..{after}") == "1"
    assert "Verification: `$ uv run devops ci test tests/test_sample.py`" in stage_repo.origin_git(
        "show", f"{after}:{TASKS}"
    )


def test_a_rewrite_rebases_the_branch(stage_repo: StageRepo, tool: OpenSpecTool) -> None:
    """The pushed head holds the default branch as its base, so the pass rebases the branch before
    it writes the rewrite."""
    from devops_cli.roadmap.plan_branches import (
        BranchResult,
        PlanBranch,
        branch_rewrite,
        push_rewrite,
    )

    stage_repo.track(_plan())
    _push(stage_repo, AHEAD, _without_verification(_plan()))
    stage_repo.track({"docs/note.md": "A note that the branch lacks.\n"})
    record = branch_rewrite(
        stage_repo.clone, PlanBranch(PULL, AHEAD, ISSUE), "main", _tree(stage_repo)
    )
    assert record.rewrite is not None

    pushed = push_rewrite(
        stage_repo.clone, record, record.rewrite, "main", tool=tool, **_judge(stage_repo)
    )

    base = stage_repo.origin_git("rev-parse", "refs/heads/main")
    assert pushed.result is BranchResult.REWRITTEN
    assert stage_repo.origin_git("merge-base", base, pushed.head) == base
    assert stage_repo.origin_git("cat-file", "-e", f"{pushed.head}:docs/note.md") == ""


def test_only_the_base_moved_pushes_nothing(stage_repo: StageRepo, tool: OpenSpecTool) -> None:
    """A branch whose plan the rewrite does not change gets no rebase and no push, also when the
    default branch moved past it."""
    from devops_cli.roadmap.plan_branches import (
        BranchResult,
        render_branch_run,
        rewrite_open_branches,
    )

    stage_repo.track(_plan())
    stage_repo.push_branch(BRANCH)
    before = _head(stage_repo, BRANCH)
    stage_repo.track({"docs/note.md": "A note that the branch lacks.\n"})
    store, reads, number = _plan_pull(BRANCH)

    run = rewrite_open_branches(store, reads, REPO, stage_repo.clone, tool=tool, confirm=True)

    assert [record.result for record in run.branches] == [BranchResult.UNCHANGED]
    assert _head(stage_repo, BRANCH) == before
    report = render_branch_run(run)
    assert f"#{number}" in report
    assert "unchanged" in report


def test_a_conflicting_branch_pushes_nothing(stage_repo: StageRepo, tool: OpenSpecTool) -> None:
    """A branch that conflicts with the default branch is left as it is, and the reason names the
    conflict."""
    from devops_cli.roadmap.plan_branches import (
        BranchResult,
        render_branch_run,
        rewrite_open_branches,
    )

    stage_repo.track(_plan())
    _push(stage_repo, AHEAD, _without_verification(_edited(_plan(), "Write", "Write the case")))
    before = _head(stage_repo, AHEAD)
    stage_repo.track(_edited(_plan(), "Write", "Write the failing case"))
    store, reads, _ = _plan_pull(AHEAD)

    run = rewrite_open_branches(store, reads, REPO, stage_repo.clone, tool=tool, confirm=True)

    (record,) = run.branches
    assert record.result is BranchResult.CONFLICT
    assert "conflicts" in record.reason
    assert _head(stage_repo, AHEAD) == before
    assert "conflict" in render_branch_run(run)


def test_a_refused_rewrite_pushes_nothing(
    stage_repo: StageRepo, tool: OpenSpecTool, openspec_fake: OpenSpecFake
) -> None:
    """A rewritten plan that OpenSpec refuses is committed nowhere and pushed nowhere."""
    from devops_cli.roadmap.plan_branches import (
        BranchResult,
        PlanBranch,
        branch_rewrite,
        push_rewrite,
    )

    stage_repo.track(_plan())
    _push(stage_repo, AHEAD, _without_verification(_plan()))
    before = _head(stage_repo, AHEAD)
    openspec_fake.script(validate_args(f"{ISSUE}-keep-the-last-comment"), 1, "", REJECTION)
    record = branch_rewrite(
        stage_repo.clone, PlanBranch(PULL, AHEAD, ISSUE), "main", _tree(stage_repo)
    )
    assert record.rewrite is not None

    pushed = push_rewrite(
        stage_repo.clone, record, record.rewrite, "main", tool=tool, **_judge(stage_repo)
    )

    assert pushed.result is BranchResult.INVALID
    assert REJECTION in pushed.reason
    assert _head(stage_repo, AHEAD) == before


def test_a_run_with_no_open_plan_branch_says_so() -> None:
    """A run over no branch gives the counts, and says that no open plan branch holds the default
    branch as its base."""
    from devops_cli.roadmap.plan_branches import BranchRun, render_branch_run

    report = render_branch_run(BranchRun(REPO, "main", False, ()))

    assert "No open draft plan pull request" in report
    assert "0 open plan branches" in report
