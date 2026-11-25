"""The `plan_drift` row: an open plan pull request that the default branch broke (#3968). The row
removes only the label `verdict/fix-plan` that it added (#5884)."""

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
from devops_cli.roadmap.stage.stage_eval_cases import DefectType
from devops_cli.roadmap.stores.store import IssueComment as ItemComment
from devops_cli.roadmap.stores.store import OpenPull
from tests.support.builders import make_stage_proposal
from tests.support.roadmap_fix_plan import finding, stage_comment
from tests.support.roadmap_stage import StageRepo

REPO = "example/roadmap"
PULL = 7
ISSUE = 1
BRANCH = "plan/1-keep-the-last-comment"
CHANGE = "1-keep-the-last-comment"
NOW = datetime(2026, 11, 14, tzinfo=UTC)
LABEL = "verdict/fix-plan"
TITLE = "docs(spec): plan #1 Keep the comment"
PROBLEM = PlanProblem("src/a.py", "paths", "not a file on the default branch")


def _pull(title: str, number: int = PULL, *, base: str = "main") -> PullRequest:
    return PullRequest(
        title=title,
        head=CommitRef(sha="a" * 40, ref=BRANCH),
        base=CommitRef(sha="b" * 40, ref=base),
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
        self.comments.append(IssueComment(id=100 + len(self.comments), body=body))

    def update_issue_comment(self, repo: str, comment_id: int, body: str) -> None:
        del repo
        self.updated.append((comment_id, body))
        self.comments = [
            IssueComment(id=comment.id, body=body) if comment.id == comment_id else comment
            for comment in self.comments
        ]

    def drift_body(self) -> str:
        """The body of the one drift comment."""
        (body,) = [comment.body for comment in self.comments if PLAN_DRIFT_MARKER in comment.body]
        return body


class _Store:
    """The pull requests and labels of the row, held in memory."""

    def __init__(self, pulls: list[OpenPull], labelled: tuple[int, ...] = ()) -> None:
        self.pulls = pulls
        self.labelled = set(labelled)
        self.added: list[tuple[int, str]] = []
        self.removed: list[tuple[int, str]] = []
        self.item_comments: list[ItemComment] = []

    def comments_on(self, number: int) -> list[ItemComment]:
        del number
        return list(self.item_comments)

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
            PULL: _pull("docs(spec): plan #1 Keep the comment"),
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
            _open(PULL, "docs(spec): plan #1 Keep the comment"),
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
    ) == ((PULL,), (PULL,), [(PULL, "verdict/fix-plan")], [], [(11, reads.updated[0][1])], [])


def _plan(labelled: tuple[int, ...] = ()) -> tuple[_Reads, _Store]:
    """One open plan pull request of item #1, and the store that lists it."""
    reads = _Reads(
        {PULL: _pull(TITLE)},
        {
            PULL: IssueView(number=PULL, state="open", title="plans", body="Plans #1"),
            ISSUE: IssueView(number=ISSUE, state="open", title="An issue", body=""),
        },
    )
    return reads, _Store([_open(PULL, TITLE)], labelled=labelled)


def _claim(reads: _Reads) -> str:
    """The claim of the drift comment of the pull request."""
    return str(plan_drift.drift_claim(reads.drift_body()))


def _round(
    store: _Store,
    reads: _Reads,
    path: Path,
    monkeypatch: pytest.MonkeyPatch,
    problems: list[PlanProblem],
) -> None:
    """One round of the row, in which the plan check of the pull request gives `problems`."""
    monkeypatch.setattr(plan_drift, "default_branch", lambda *args, **kwargs: "main")
    monkeypatch.setattr(plan_drift, "plan_drift_problems", lambda *args, **kwargs: problems)
    run_plan_drift(store, repo=REPO, source=path, reads=reads)


def test_the_row_clears_the_label_that_it_added_and_marks_its_comment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    reads, store = _plan()
    _round(store, reads, tmp_path, monkeypatch, [PROBLEM])
    assert _claim(reads) == "added"

    _round(store, reads, tmp_path, monkeypatch, [])

    assert (store.added, store.removed, _claim(reads)) == (
        [(PULL, LABEL)],
        [(PULL, LABEL)],
        "cleared",
    )
    assert PROBLEM.path not in reads.drift_body()


def test_a_label_of_the_stage_review_stays_when_the_plan_passes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The stage review labelled the plan and the row never found drift: the label stays, so
    `stage_ready` keeps the draft (#5884)."""
    reads, store = _plan(labelled=(PULL,))

    _round(store, reads, tmp_path, monkeypatch, [])

    assert (store.removed, store.labelled, reads.created, reads.updated) == ([], {PULL}, [], [])


def test_a_label_held_before_the_drift_stays_when_the_plan_passes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    reads, store = _plan(labelled=(PULL,))
    _round(store, reads, tmp_path, monkeypatch, [PROBLEM])
    assert _claim(reads) == "held"

    _round(store, reads, tmp_path, monkeypatch, [])

    assert (store.removed, store.labelled, _claim(reads)) == (
        [],
        {PULL},
        "cleared",
    )


def test_the_label_stays_while_the_last_plan_comment_lists_an_open_finding(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The row added the label, and the fix-plan step later kept it for an open finding of its
    review: the plan passes the drift check, and the label stays."""
    reads, store = _plan()
    _round(store, reads, tmp_path, monkeypatch, [PROBLEM])
    store.item_comments = [
        ItemComment(
            body=stage_comment(PULL, [finding(DefectType.TASK_ORDER)]),
            created_at=NOW,
            author_association="OWNER",
        )
    ]

    _round(store, reads, tmp_path, monkeypatch, [])

    assert (store.removed, store.labelled, _claim(reads)) == (
        [],
        {PULL},
        "cleared",
    )


def test_a_cleared_comment_leaves_a_later_label_of_another_check(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    reads, store = _plan()
    _round(store, reads, tmp_path, monkeypatch, [PROBLEM])
    _round(store, reads, tmp_path, monkeypatch, [])
    store.labelled.add(PULL)
    updates = len(reads.updated)

    _round(store, reads, tmp_path, monkeypatch, [])

    assert (store.removed, store.labelled, len(reads.updated)) == (
        [(PULL, LABEL)],
        {PULL},
        updates,
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
        title="docs(spec): plan #1 Keep the comment",
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


def test_the_row_posts_a_new_comment_and_skips_a_plan_of_another_base_and_no_issue(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    problem = PlanProblem("src/a.py", "paths", "not a file on the default branch")
    reads = _Reads(
        {
            PULL: _pull("docs(openspec): plan #1 Keep the comment"),
            9: _pull("docs(openspec): plan #1 Keep the comment", number=9, base="release"),
            10: _pull("docs(openspec): plan #1 Keep the comment", number=10),
        },
        {
            PULL: IssueView(number=PULL, state="open", title="plans", body="Plans #1"),
            9: IssueView(number=9, state="open", title="plans", body="Plans #1"),
            10: IssueView(number=10, state="open", title="plans", body="No plan line"),
            ISSUE: IssueView(number=ISSUE, state="open", title="An issue", body=""),
        },
    )
    store = _Store(
        [
            _open(PULL, "docs(openspec): plan #1 Keep the comment"),
            _open(9, "docs(openspec): plan #1 Keep the comment"),
            _open(10, "docs(openspec): plan #1 Keep the comment"),
        ]
    )
    monkeypatch.setattr(plan_drift, "default_branch", lambda *args, **kwargs: "main")
    monkeypatch.setattr(plan_drift, "plan_drift_problems", lambda *args, **kwargs: [problem])

    run = run_plan_drift(store, repo=REPO, source=tmp_path, reads=reads)

    assert (run.checked, run.failing, [number for number, _ in reads.created]) == (
        (PULL,),
        (PULL,),
        [PULL],
    )
    assert reads.updated == []
    assert PLAN_DRIFT_MARKER in reads.created[0][1]


def test_the_row_takes_the_github_client_when_no_reads_is_given(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class _Session:
        client = _Reads({}, {})

    monkeypatch.setattr("devops_cli.github.session.get_github_session", lambda: _Session())
    monkeypatch.setattr(plan_drift, "default_branch", lambda *args, **kwargs: "main")

    run = run_plan_drift(_Store([]), repo=REPO, source=tmp_path)

    assert run.checked == ()


def test_a_plan_head_without_a_change_folder_is_a_problem(stage_repo: StageRepo) -> None:
    stage_repo.git("switch", "-q", "-c", BRANCH)
    (stage_repo.clone / "README.md").write_text("No change folder.\n", encoding="utf-8")
    stage_repo.git("add", "-A")
    stage_repo.git("commit", "-q", "-m", "no plan")
    stage_repo.git("push", "-q", "origin", BRANCH)
    sha = stage_repo.origin_git("rev-parse", BRANCH)
    stage_repo.origin_git("update-ref", f"refs/pull/{PULL}/head", sha)
    facts = PullFacts(
        number=PULL,
        title="docs(spec): plan #1 Keep the comment",
        body="Plans #1",
        head_sha=sha,
        base_sha="b" * 40,
        base_ref="main",
    )

    problems = plan_drift_problems(
        stage_repo.clone,
        repo=REPO,
        number=PULL,
        facts=facts,
        issue=ISSUE,
        reads=_Reads({}, {}),
        branch="main",
    )

    assert [problem.rule for problem in problems] == ["change-folder"]


def test_the_adapter_runs_the_round_on_the_job_clone(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from devops_cli.roadmap import run as roadmap_run
    from devops_cli.roadmap.run import JobOutcome
    from devops_cli.roadmap.stage.plan_drift import PlanDriftRun

    seen: list[tuple[str, str]] = []

    def fake_run(store: object, *, repo: str, source: Path) -> PlanDriftRun:
        seen.append((repo, str(source)))
        return PlanDriftRun(checked=(7,), failing=())

    monkeypatch.setattr(roadmap_run, "_job_clone", lambda name, clone: tmp_path)
    monkeypatch.setattr(roadmap_run, "run_plan_drift", fake_run)

    outcome = roadmap_run._run_plan_drift_adapter(_Store([]), repo=REPO, clone_path=tmp_path)

    assert (seen, outcome) == ([(REPO, str(tmp_path))], JobOutcome())
