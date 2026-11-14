"""The `plan_drift` row: an open plan pull request that the default branch broke (#3968)."""

from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from devops_cli.github.client import CommitRef, IssueComment, IssueView, PullRequest
from devops_cli.roadmap.plan_check import PlanProblem, PullFacts
from devops_cli.roadmap.stage import plan_drift
from devops_cli.roadmap.stage.plan_drift import (
    PLAN_DRIFT_MARKER,
    drift_comment,
    plan_drift_problems,
    run_plan_drift,
)
from devops_cli.roadmap.stage.stage_change import render_change
from devops_cli.roadmap.stores.store import OpenPull
from tests.support.builders import make_stage_proposal
from tests.support.roadmap_stage import StageRepo

REPO = "example/roadmap"
PULL = 7
ISSUE = 1
BRANCH = "plan/1-keep-the-last-comment"
CHANGE = "1-keep-the-last-comment"
NOW = datetime(2026, 11, 14, tzinfo=UTC)


def _pull(title: str, number: int = PULL) -> PullRequest:
    return PullRequest(
        title=title,
        head=CommitRef(sha="a" * 40, ref=BRANCH),
        base=CommitRef(sha="b" * 40, ref="main"),
    )


class _Reads:
    """The GitHub reads and writes of the row, held in memory."""

    def __init__(self, pulls: dict[int, PullRequest], issues: dict[int, IssueView]) -> None:
        self.pulls = pulls
        self.issues = issues
        self.comments: list[IssueComment] = []
        self.created: list[tuple[int, str]] = []
        self.updated: list[tuple[int, str]] = []

    def get_pull(self, repo: str, number: int) -> PullRequest:
        del repo
        return self.pulls[number]

    def get_issue(self, repo: str, number: int) -> IssueView:
        del repo
        return self.issues[number]

    def list_issue_comments(self, repo: str, number: int) -> list[IssueComment]:
        del repo, number
        return list(self.comments)

    def create_issue_comment(self, repo: str, number: int, body: str) -> None:
        del repo
        self.created.append((number, body))

    def update_issue_comment(self, repo: str, comment_id: int, body: str) -> None:
        del repo
        self.updated.append((comment_id, body))


class _Store:
    """The pull requests and labels of the row, held in memory."""

    def __init__(self, pulls: list[OpenPull], labelled: tuple[int, ...] = ()) -> None:
        self.pulls = pulls
        self.labelled = set(labelled)
        self.added: list[tuple[int, str]] = []
        self.removed: list[tuple[int, str]] = []

    def open_pulls(self) -> list[OpenPull]:
        return self.pulls

    def labelled_pulls(self, label: str) -> list[int]:
        del label
        return sorted(self.labelled)

    def label_issue(self, number: int, label: str) -> None:
        self.added.append((number, label))
        self.labelled.add(number)

    def unlabel_issue(self, number: int, label: str) -> None:
        self.removed.append((number, label))
        self.labelled.discard(number)


def _open(number: int, title: str) -> OpenPull:
    return OpenPull(
        number=number,
        title=title,
        url=f"https://example.test/pull/{number}",
        head_ref=BRANCH,
        updated_at=NOW,
    )


def test_the_drift_comment_lists_each_problem_under_one_marker() -> None:
    body = drift_comment(
        [
            PlanProblem("src/a.py", "paths", "not a file on the default branch"),
            PlanProblem("src/b.py", "paths", "not a file on the default branch"),
        ]
    )

    assert (
        body.count(PLAN_DRIFT_MARKER),
        "src/a.py: paths: not a file on the default branch" in body,
        "src/b.py: paths: not a file on the default branch" in body,
    ) == (1, True, True)


def test_the_row_labels_and_comments_a_drifted_plan_and_skips_a_delivery(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    problem = PlanProblem("src/a.py", "paths", "not a file on the default branch")
    reads = _Reads(
        {
            PULL: _pull("docs(openspec): plan #1 Keep the comment"),
            8: _pull("fix(roadmap): keep the comment", number=8),
        },
        {
            PULL: IssueView(number=PULL, state="open", title="plans", body="Plans #1"),
            ISSUE: IssueView(number=ISSUE, state="open", title="An issue", body=""),
        },
    )
    reads.comments = [IssueComment(id=11, body=f"{PLAN_DRIFT_MARKER}\n\nold")]
    store = _Store(
        [
            _open(PULL, "docs(openspec): plan #1 Keep the comment"),
            _open(8, "fix(roadmap): keep the comment"),
        ]
    )
    monkeypatch.setattr(plan_drift, "default_branch", lambda *args, **kwargs: "main")
    monkeypatch.setattr(plan_drift, "plan_drift_problems", lambda *args, **kwargs: [problem])

    run = run_plan_drift(store, repo=REPO, source=tmp_path, reads=reads)

    assert (
        run.checked,
        run.failing,
        store.added,
        reads.created,
        reads.updated,
        store.removed,
    ) == ((PULL,), (PULL,), [(PULL, "plan/needs-fix")], [], [(11, reads.updated[0][1])], [])


def test_the_row_clears_the_label_of_a_plan_that_passes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    reads = _Reads(
        {PULL: _pull("docs(openspec): plan #1 Keep the comment")},
        {PULL: IssueView(number=PULL, state="open", title="plans", body="Plans #1")},
    )
    store = _Store([_open(PULL, "docs(openspec): plan #1 Keep the comment")], labelled=(PULL,))
    monkeypatch.setattr(plan_drift, "default_branch", lambda *args, **kwargs: "main")
    monkeypatch.setattr(plan_drift, "plan_drift_problems", lambda *args, **kwargs: [])

    run = run_plan_drift(store, repo=REPO, source=tmp_path, reads=reads)

    assert (run.checked, run.failing, store.removed, store.added) == (
        (PULL,),
        (),
        [(PULL, "plan/needs-fix")],
        [],
    )


def test_a_plan_that_cites_a_path_moved_on_the_default_branch_is_a_problem(
    stage_repo: StageRepo,
) -> None:
    """The plan files come from the pull request head, and the tree comes from the default
    branch, where the moved path is gone (#3968)."""
    stage_repo.track({"src/devops_cli/sample.py": "def f():\n    return 1\n"})
    stage_repo.git("switch", "-q", "-c", BRANCH)
    files = render_change(
        CHANGE, make_stage_proposal(), {"comment-thread"}, created=date(2026, 11, 4)
    )
    for path, text in files.items():
        destination = stage_repo.clone / path
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(text, encoding="utf-8")
    stage_repo.git("add", "-A")
    stage_repo.git("commit", "-q", "-m", "plan")
    stage_repo.git("push", "-q", "origin", BRANCH)
    sha = stage_repo.origin_git("rev-parse", BRANCH)
    stage_repo.origin_git("update-ref", f"refs/pull/{PULL}/head", sha)
    stage_repo.git("switch", "-q", "main")
    stage_repo.untrack("src/devops_cli/sample.py")
    facts = PullFacts(
        number=PULL,
        title="docs(openspec): plan #1 Keep the comment",
        body="Plans #1",
        head_sha=sha,
        base_sha="b" * 40,
        base_ref="main",
    )
    reads = _Reads({}, {ISSUE: IssueView(number=ISSUE, state="open", title="An issue", body="")})

    problems = plan_drift_problems(
        stage_repo.clone,
        repo=REPO,
        number=PULL,
        facts=facts,
        issue=ISSUE,
        reads=reads,
        branch="main",
    )

    assert any("src/devops_cli/sample.py" in problem.message for problem in problems)
