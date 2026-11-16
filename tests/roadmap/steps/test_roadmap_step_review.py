"""Tests for the roadmap step `review` (#5969).

The rules are pure functions of `ReviewFacts`, so most cases need no fake. The calls of
`run_review` fake GitHub's REST and GraphQL API at the HTTP edge, `gh pr ready` at the process
edge, and the roadmap store in memory. The model judge and the delete of a branch are given to the
step as parameters.
"""

from __future__ import annotations

import json
import logging
import subprocess
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from devops_cli.config.settings import Settings
from devops_cli.exceptions import DevOpsCLIError, GitOperationError, RoadmapImplementError
from devops_cli.github.check_verdict import CheckBucket, CheckVerdictSummary, PRCheckItem
from devops_cli.github.session import get_github_session
from devops_cli.roadmap.body_hash import body_hashes
from devops_cli.roadmap.pr_verdict import (
    KIND_JOBS,
    VERDICT_LABEL_NAMES,
    PullKind,
    Verdict,
    grade_verdicts,
    pull_kind,
    read_bot_pulls,
    verdict_label,
    verdict_of,
)
from devops_cli.roadmap.steps.review import (
    DueFix,
    Judgement,
    ReviewCall,
    ReviewResult,
    Waiting,
    model_judgement,
    rule_judgement,
    run_review,
    write_verdict,
)
from devops_cli.roadmap.steps.review_facts import (
    RelatedPull,
    ReplyEvidence,
    ReplyVerdict,
    ReviewCase,
    ReviewFacts,
    ReviewReply,
)
from devops_cli.roadmap.stores.store import (
    ImplementRecordKey,
    ReviewRecordKey,
    StageRecordKey,
)
from tests.support.fakes.github import (
    GitHubApiFake,
    github_json,
    route_compare_diff,
    route_compare_files,
    route_file,
)
from tests.support.fakes.process import ProcessAnswer, ProcessCall, ProcessFake
from tests.support.fakes.roadmap_store import InMemoryRoadmapStore

pytestmark = pytest.mark.usefixtures("keyring_store")

REPO = "example/project"
BOT = "devops-cli-service[bot]"
HEAD = "1111111111111111111111111111111111111111"
NEW_HEAD = "2222222222222222222222222222222222222222"
BASE = "3333333333333333333333333333333333333333"
CODE = "src/devops_cli/sample.py"
TICKED = "# Tasks\n\n## 1. Group\n\n- [x] 1.1 Do it\n"
BODY = "## Problem\n\nThe sample does not work.\n"
_RUN_PASSED = {"name": "Tests", "status": "completed", "conclusion": "success"}


def _check(name: str, bucket: CheckBucket = CheckBucket.PASS) -> PRCheckItem:
    return PRCheckItem(name=name, bucket=bucket, state=bucket.value)


def _checks(*items: PRCheckItem) -> CheckVerdictSummary:
    return CheckVerdictSummary(items=list(items or (_check("Tests"),)))


def _facts(**fields: Any) -> ReviewFacts:
    base: dict[str, Any] = {
        "pull": 20,
        "kind": PullKind.DELIVERY,
        "head": HEAD,
        "item_number": 12,
        "checks": _checks(),
        "files": (CODE,),
    }
    return ReviewFacts(**(base | fields))


# ── The rules ────────────────────────────────────────────────────────────────────────────────


def test_a_closed_item_is_issue_changed() -> None:
    judged = rule_judgement(_facts(item_open=False))

    assert judged is not None
    assert not isinstance(judged, Waiting)
    assert (judged.verdict, judged.source) == (Verdict.ISSUE_CHANGED, "rule")


def test_an_issue_text_changed_since_the_plan_is_issue_changed() -> None:
    judged = rule_judgement(_facts(text_changed=True))

    assert judged is not None
    assert not isinstance(judged, Waiting)
    assert judged.verdict is Verdict.ISSUE_CHANGED
    assert "stage.text_hash" in judged.evidence[0]


def test_merged_work_on_the_change_folder_of_the_item_is_issue_changed() -> None:
    folder = "openspec/changes/12-sample/tasks.md"
    judged = rule_judgement(_facts(related=(RelatedPull(7, (CODE, folder)),)))

    assert judged is not None
    assert not isinstance(judged, Waiting)
    assert judged.verdict is Verdict.ISSUE_CHANGED
    assert judged.evidence == (f"#7 changed `{folder}`",)


def test_the_merged_plan_of_the_item_and_other_shared_files_leave_the_model_to_decide() -> None:
    plan = RelatedPull(5, ("openspec/changes/12-sample/tasks.md",))
    other = RelatedPull(7, (CODE,))

    assert rule_judgement(_facts(own_plan=5, related=(plan, other))) is None


@pytest.mark.parametrize(
    ("kind", "due"),
    [(PullKind.DELIVERY, DueFix.FIX_CONFLICT), (PullKind.PLAN, DueFix.FIX_PLAN)],
)
def test_a_merge_conflict_needs_a_fix(kind: PullKind, due: DueFix) -> None:
    judged = rule_judgement(_facts(kind=kind, mergeable=False, mergeable_state="dirty"))

    assert judged is not None
    assert not isinstance(judged, Waiting)
    assert (judged.verdict, judged.due) == (Verdict.NEEDS_FIX, due)


@pytest.mark.parametrize(
    ("kind", "due"),
    [(PullKind.DELIVERY, DueFix.FIX_CHECKS), (PullKind.PLAN, DueFix.FIX_PLAN)],
)
def test_a_failed_check_needs_a_fix_and_names_the_check(kind: PullKind, due: DueFix) -> None:
    checks = _checks(_check("Tests"), _check("Static Analysis", CheckBucket.FAIL))

    judged = rule_judgement(_facts(kind=kind, checks=checks))

    assert judged is not None
    assert not isinstance(judged, Waiting)
    assert (judged.verdict, judged.due) == (Verdict.NEEDS_FIX, due)
    assert judged.evidence == ("check `Static Analysis` failed",)


def test_only_a_failed_check_of_ci_infrastructure_waits() -> None:
    checks = _checks(_check("Tests"), _check("Test Job Duration", CheckBucket.FAIL))

    assert rule_judgement(_facts(checks=checks)) == Waiting(
        "Only CI infrastructure failed: Test Job Duration.", infra=True
    )


@pytest.mark.parametrize(
    ("checks", "reason"),
    [
        (_checks(_check("Tests", CheckBucket.PENDING)), "1 check(s) still run."),
        (
            CheckVerdictSummary(
                items=[
                    PRCheckItem(
                        name="no checks reported", state="pending", bucket=CheckBucket.PENDING
                    )
                ]
            ),
            "The head reports no check run yet.",
        ),
        (CheckVerdictSummary(unread_reason="The read answered 502"), "The read answered 502"),
    ],
    ids=("pending", "no-check-run", "unread"),
)
def test_a_check_that_runs_or_cannot_be_read_waits(
    checks: CheckVerdictSummary, reason: str
) -> None:
    assert rule_judgement(_facts(checks=checks)) == Waiting(reason)


def test_a_plan_with_open_findings_needs_fix_plan() -> None:
    judged = rule_judgement(_facts(kind=PullKind.PLAN, findings=("major `scope`: too wide",)))

    assert judged is not None
    assert not isinstance(judged, Waiting)
    assert (judged.verdict, judged.due, judged.evidence) == (
        Verdict.NEEDS_FIX,
        DueFix.FIX_PLAN,
        ("major `scope`: too wide",),
    )


def test_a_plan_that_holds_the_fix_plan_label_of_another_check_needs_fix_plan() -> None:
    judged = rule_judgement(_facts(kind=PullKind.PLAN, labels=("verdict/fix-plan",)))

    assert judged is not None
    assert not isinstance(judged, Waiting)
    assert (judged.verdict, judged.due) == (Verdict.NEEDS_FIX, DueFix.FIX_PLAN)


def test_an_unresolved_thread_needs_a_fix_and_names_its_place() -> None:
    judged = rule_judgement(_facts(threads=(f"{CODE}:4",)))

    assert judged is not None
    assert not isinstance(judged, Waiting)
    assert (judged.verdict, judged.due, judged.evidence) == (
        Verdict.NEEDS_FIX,
        None,
        (f"thread at `{CODE}:4`",),
    )


def test_an_incomplete_delivery_needs_a_fix() -> None:
    judged = rule_judgement(_facts(incomplete="Task group 1 is not ticked."))

    assert judged is not None
    assert not isinstance(judged, Waiting)
    assert (judged.verdict, judged.reason) == (Verdict.NEEDS_FIX, "Task group 1 is not ticked.")


def test_a_green_complete_pull_request_goes_to_the_model() -> None:
    assert rule_judgement(_facts()) is None


# ── The verdict of the model ─────────────────────────────────────────────────────────────────


def _reply(verdict: ReplyVerdict, *paths: str) -> ReviewReply:
    evidence = [ReplyEvidence(path=path, line=3, note="The task is not done.") for path in paths]
    return ReviewReply(verdict=verdict, reason="The diff misses task 1.2.", evidence=evidence)


@pytest.mark.parametrize(
    ("kind", "verdict"),
    [(PullKind.DELIVERY, Verdict.DISCARD_IMPLEMENTATION), (PullKind.PLAN, Verdict.DISCARD_PLAN)],
)
def test_a_discard_with_evidence_in_the_diff_is_the_discard_of_its_kind(
    kind: PullKind, verdict: Verdict
) -> None:
    judged = model_judgement(_facts(kind=kind), _reply(ReplyVerdict.DISCARD, CODE))

    assert (judged.verdict, judged.source) == (verdict, "model")
    assert judged.evidence == (f"`{CODE}:3`: The task is not done.",)


def test_a_discard_with_no_evidence_in_the_diff_becomes_needs_fix() -> None:
    judged = model_judgement(_facts(), _reply(ReplyVerdict.DISCARD, "src/other.py"))

    assert (judged.verdict, judged.evidence) == (Verdict.NEEDS_FIX, ())
    assert "no evidence" in judged.reason


def test_the_model_text_is_made_safe_for_a_comment() -> None:
    reply = ReviewReply(verdict=ReplyVerdict.MERGEABLE, reason="Ask @someone, key ghp_" + "a" * 36)

    judged = model_judgement(_facts(), reply)

    assert judged.verdict is Verdict.MERGEABLE
    assert "ghp_" + "a" * 36 not in judged.reason
    assert "`@someone`" in judged.reason


def test_needs_fix_of_the_model_on_a_plan_leaves_fix_plan() -> None:
    judged = model_judgement(_facts(kind=PullKind.PLAN), _reply(ReplyVerdict.NEEDS_FIX))

    assert (judged.verdict, judged.due) == (Verdict.NEEDS_FIX, DueFix.FIX_PLAN)


# ── The grades read the label that the step writes ──────────────────────────────────────────


@pytest.mark.parametrize(
    "title", ["docs(openspec): plan #12 Add the sample", "feat(roadmap): Add the sample"]
)
@pytest.mark.parametrize("verdict", list(Verdict))
def test_each_label_that_the_step_writes_reads_back_as_its_verdict(
    title: str, verdict: Verdict
) -> None:
    kind = pull_kind(title)
    label = verdict_label(kind, verdict)

    if label is None:
        other = Verdict.DISCARD_IMPLEMENTATION if kind is PullKind.PLAN else Verdict.DISCARD_PLAN
        assert verdict is other
    else:
        assert verdict_of(kind, label) is verdict


# ── The calls ────────────────────────────────────────────────────────────────────────────────


@dataclass
class FakeJudge:
    """A judge that gives `reply`, or raises `error`, and records each case."""

    reply: ReviewReply | None = None
    error: DevOpsCLIError | None = None
    cases: list[ReviewCase] = field(default_factory=list)

    def judge(self, case: ReviewCase) -> ReviewReply:
        self.cases.append(case)
        if self.error is not None:
            raise self.error
        assert self.reply is not None
        return self.reply


def _commit(oid: str, number: int | None = None, *paths: str) -> dict[str, Any]:
    pulls = (
        []
        if number is None
        else [{"number": number, "merged": True, "files": {"nodes": [{"path": p} for p in paths]}}]
    )
    return {"oid": oid, "associatedPullRequests": {"nodes": pulls}}


@dataclass
class World:
    """A bot pull request of an item of `REPO`, as GitHub, `gh` and the store answer for it."""

    api: GitHubApiFake
    gh: ProcessFake
    store: InMemoryRoadmapStore = field(default_factory=lambda: InMemoryRoadmapStore(repo=REPO))
    withdrawn: list[tuple[str, str]] = field(default_factory=list)
    closes_before_withdraw: list[int] = field(default_factory=list)
    ready: list[tuple[str, ...]] = field(default_factory=list)

    def item(self, *labels: str, record: dict[Any, str | None] | None = None, **seed: Any) -> int:
        number = self.store.seed_issue(
            "Add the sample", body=BODY, labels=["priority/p2-medium", *labels], **seed
        )
        held = self.store.item(number)
        assert held is not None
        marks: dict[Any, str | None] = {StageRecordKey.TEXT_HASH: body_hashes(BODY)[0]}
        self.store.set_marks(held, marks | (record or {}))
        return number

    def pull(
        self,
        item: int,
        *,
        title: str = "feat(roadmap): Add the sample",
        author: str = BOT,
        labels: Sequence[str] = (),
        runs: Sequence[tuple[str, str]] = (("Tests", "success"),),
        heads: Sequence[str] = (HEAD,),
        draft: bool = True,
        files: Sequence[str] = (),
        threads: Sequence[dict[str, Any]] = (),
        history: Sequence[dict[str, Any]] = (),
        kind: PullKind = PullKind.DELIVERY,
        ready_by: str | None = None,
        state: str = "open",
    ) -> int:
        """The pull request of `item` on its branch, with its check runs, its diff, its threads,
        the history of the base branch, the login that marked it ready, and the change folder of
        the item."""
        branch = f"{'docs' if kind is PullKind.PLAN else 'feat'}/{item}-sample"
        number = self.store.seed_pull(
            title, head_ref=branch, head_sha=HEAD, draft=draft, labels=labels
        )
        key = StageRecordKey.PR if kind is PullKind.PLAN else ImplementRecordKey.PR
        held = self.store.item(item)
        assert held is not None
        self.store.set_marks(held, {key: str(number)})
        self.status(
            number,
            heads=heads,
            state=state,
            draft=draft,
            title=title,
            branch=branch,
            author=author,
            labels=labels,
        )
        check_runs = [
            {"name": name, "status": "completed", "conclusion": conclusion}
            for name, conclusion in runs
        ]
        self.api.route(
            "GET",
            f"/repos/{REPO}/commits/{HEAD}/check-runs?per_page=100",
            github_json({"total_count": len(check_runs), "check_runs": check_runs}),
        )
        folder = (
            f"openspec/changes/{item}-sample"
            if kind is PullKind.PLAN
            else f"openspec/changes/archive/2026-11-16-{item}-sample"
        )
        changed = list(files) or [CODE, f"{folder}/tasks.md"]
        route_compare_files(
            self.api,
            REPO,
            "main",
            HEAD,
            *({"filename": name, "status": "modified"} for name in changed),
            merge_base=BASE,
        )
        route_compare_diff(self.api, REPO, "main", HEAD, f"diff --git a/{CODE} b/{CODE}\n")
        route_file(self.api, REPO, f"{folder}/tasks.md", HEAD, TICKED)
        graph = {
            "data": {
                "repository": {
                    "pullRequest": {
                        "reviewThreads": {"nodes": list(threads)},
                        "timelineItems": {
                            "nodes": [{"actor": {"login": ready_by}}] if ready_by else []
                        },
                    },
                    "ref": {"target": {"history": {"nodes": [*history, _commit(BASE)]}}},
                }
            }
        }
        self.api.route("POST", "/graphql", github_json(graph))
        self.api.route(
            "GET", f"/repos/{REPO}/issues/{number}/comments?per_page=100", github_json([])
        )
        self.api.route(
            "POST", f"/repos/{REPO}/issues/{number}/comments", github_json({"id": 1}, status=201)
        )
        self.api.route("PATCH", f"/repos/{REPO}/pulls/{number}", github_json({}))

        def ready(call: ProcessCall) -> subprocess.CompletedProcess[str]:
            self.ready.append(tuple(call.argv[1:]))
            return subprocess.CompletedProcess(call.argv, 0, stdout="")

        self.gh.answer(
            lambda call: call.argv[1:3] == ("pr", "ready"), ProcessAnswer(side_effect=ready)
        )
        return number

    def status(
        self,
        number: int,
        *,
        heads: Sequence[str] = (HEAD,),
        state: str = "open",
        draft: bool = True,
        title: str = "feat(roadmap): Add the sample",
        branch: str = "",
        author: str = BOT,
        labels: Sequence[str] = (),
    ) -> None:
        """Answer the reads of pull request `number` with these fields, one answer for each of
        `heads`."""
        self.api.route(
            "GET",
            f"/repos/{REPO}/pulls/{number}",
            *(
                github_json(
                    {
                        "state": state,
                        "draft": draft,
                        "title": title,
                        "head": {"ref": branch, "sha": head},
                        "base": {"ref": "main"},
                        "user": {"login": author},
                        "labels": [{"name": name} for name in labels],
                        "mergeable": True,
                        "mergeable_state": "clean",
                    }
                )
                for head in heads
            ),
        )

    def withdraw(self, branch: str, lease: str) -> None:
        """Record the delete of `branch` and how many closes were sent before it."""
        self.withdrawn.append((branch, lease))
        self.closes_before_withdraw.append(len(self.closed()))

    def run(self, pull: int, judge: FakeJudge | None = None, **kwargs: Any) -> Any:
        return run_review(
            self.store,
            REPO,
            pull,
            judge=judge or FakeJudge(_reply(ReplyVerdict.MERGEABLE)),
            withdraw=self.withdraw,
            **kwargs,
        )

    def comments(self) -> list[str]:
        return [
            json.loads(request.content)["body"]
            for request in self.api.sent
            if request.method == "POST" and request.url.path.endswith("/comments")
        ]

    def closed(self) -> list[int]:
        return [
            int(request.url.path.rsplit("/", 1)[-1])
            for request in self.api.sent
            if request.method == "PATCH" and "/pulls/" in request.url.path
        ]

    def labels(self, number: int) -> tuple[str, ...]:
        """The verdict labels that the open pull request `number` holds."""
        return tuple(
            name
            for name in sorted(VERDICT_LABEL_NAMES)
            if number in self.store.labelled_pulls(name)
        )

    def record(self, item: int) -> dict[str, str | None]:
        held = self.store.item(item)
        assert held is not None
        return {key.value: held.job_record.get(key) for key in ReviewRecordKey}


@pytest.fixture
def world(github_api_and_gh: tuple[GitHubApiFake, ProcessFake]) -> World:
    api, gh = github_api_and_gh
    return World(api, gh)


def test_the_settings_start_in_plan_with_three_rounds_and_a_generous_cap() -> None:
    review = Settings().roadmap.review

    assert (review.mode, review.rounds, review.token_budget) == ("plan", 3, 16_000_000)


def test_the_mode_off_sends_no_request(world: World) -> None:
    report = world.run(1, mode="off", confirm=True)

    assert (report.result, world.api.sent) == (ReviewResult.SKIPPED, [])


def test_a_pull_request_of_a_person_is_stopped(world: World) -> None:
    pull = world.pull(world.item(), author="person")

    report = world.run(pull, mode="on", confirm=True)

    assert report.result is ReviewResult.STOPPED
    assert world.comments() == []


def test_an_item_that_a_live_runner_job_holds_is_skipped(world: World) -> None:
    item = world.item(record={ImplementRecordKey.JOB: "implement-12-abc"})
    pull = world.pull(item)
    judge = FakeJudge(_reply(ReplyVerdict.MERGEABLE))

    report = world.run(pull, judge, mode="on", confirm=True)

    assert report.result is ReviewResult.SKIPPED
    assert "implement-12-abc" in report.reason
    assert (judge.cases, world.comments()) == ([], [])


def test_a_head_that_moved_from_the_judged_head_is_skipped(world: World) -> None:
    pull = world.pull(world.item())

    report = world.run(pull, head=NEW_HEAD, mode="on", confirm=True)

    assert report.result is ReviewResult.SKIPPED
    assert world.comments() == []


def test_without_confirm_the_step_returns_the_verdict_and_writes_nothing(world: World) -> None:
    item = world.item()
    pull = world.pull(item)
    judge = FakeJudge(_reply(ReplyVerdict.MERGEABLE))

    report = world.run(pull, judge, mode="on")

    assert (report.result, report.verdict, report.label, report.written) == (
        ReviewResult.JUDGED,
        Verdict.MERGEABLE,
        "verdict/mergeable",
        False,
    )
    assert report.action.startswith("Plan: mark the draft ready")
    assert len(judge.cases) == 1
    assert CODE in judge.cases[0].diff
    assert "1.1 Do it" in judge.cases[0].plan
    assert (world.comments(), world.ready, world.labels(pull)) == ([], [], ())
    assert set(world.record(item).values()) == {None}


def test_the_mode_plan_writes_nothing_also_with_confirm(world: World) -> None:
    item = world.item()
    pull = world.pull(item)

    report = world.run(pull, mode="plan", confirm=True)

    assert (report.result, report.written) == (ReviewResult.JUDGED, False)
    assert (world.comments(), world.ready) == ([], [])


def test_mergeable_marks_the_draft_ready_labels_comments_and_counts_a_round(world: World) -> None:
    item = world.item()
    pull = world.pull(item, labels=("verdict/fix-implementation",))

    report = world.run(pull, mode="on", confirm=True)

    assert (report.result, report.verdict, report.written) == (
        ReviewResult.JUDGED,
        Verdict.MERGEABLE,
        True,
    )
    assert world.ready == [("pr", "ready", str(pull), "--repo", REPO)]
    assert world.labels(pull) == ("verdict/mergeable",)
    [comment] = world.comments()
    assert "**Verdict: Mergeable** (`verdict/mergeable`), review 1 of 3" in comment
    record = world.record(item)
    assert (record["review.pull"], record["review.rounds"], record["review.verdict"]) == (
        str(pull),
        "1",
        "mergeable",
    )


def test_a_second_call_on_the_same_head_and_text_is_skipped(world: World) -> None:
    item = world.item()
    pull = world.pull(item)
    world.run(pull, mode="on", confirm=True)
    judge = FakeJudge(_reply(ReplyVerdict.MERGEABLE))

    report = world.run(pull, judge, mode="on", confirm=True)

    assert (report.result, judge.cases) == (ReviewResult.SKIPPED, [])


def test_a_failed_check_leaves_fix_checks_with_no_model_call(world: World) -> None:
    item = world.item()
    pull = world.pull(item, runs=(("Tests", "success"), ("Static Analysis", "failure")))
    judge = FakeJudge(_reply(ReplyVerdict.MERGEABLE))

    report = world.run(pull, judge, mode="on", confirm=True)

    assert (report.verdict, report.due, report.label) == (
        Verdict.NEEDS_FIX,
        DueFix.FIX_CHECKS,
        "verdict/fix-implementation",
    )
    assert judge.cases == []
    [comment] = world.comments()
    assert "check `Static Analysis` failed" in comment
    assert "fix-checks" in comment
    assert world.ready == []
    assert world.labels(pull) == ("verdict/fix-implementation",)


def test_an_issue_text_edit_after_the_plan_is_issue_changed_and_scores_nothing(
    world: World,
) -> None:
    item = world.item(record={StageRecordKey.TEXT_HASH: "0" * 64})
    pull = world.pull(item)

    report = world.run(pull, mode="on", confirm=True)

    assert (report.verdict, report.label) == (Verdict.ISSUE_CHANGED, "verdict/issue-changed")
    assert world.ready == []


@pytest.mark.parametrize(
    ("runs", "record"),
    [
        ((("Static Analysis", "failure"),), {}),
        ((("Tests", "success"),), {StageRecordKey.TEXT_HASH: "0" * 64}),
    ],
    ids=("needs-fix", "issue-changed"),
)
def test_a_ready_pull_request_that_needs_work_goes_back_to_draft(
    world: World, runs: tuple[tuple[str, str], ...], record: dict[Any, str | None]
) -> None:
    """A verdict that sends the work back makes a ready pull request a draft again, so the fix
    rows take it and no person merges work that needs a change."""
    item = world.item(record=record)
    pull = world.pull(item, runs=runs, draft=False)

    report = world.run(pull, mode="on", confirm=True)

    assert report.written
    assert world.ready == [("pr", "ready", str(pull), "--undo", "--repo", REPO)]


@pytest.mark.parametrize(
    ("kind", "title", "verdict", "label"),
    [
        (
            PullKind.DELIVERY,
            "feat(roadmap): Add the sample",
            Verdict.DISCARD_IMPLEMENTATION,
            "verdict/discard-implementation",
        ),
        (
            PullKind.PLAN,
            "docs(openspec): plan #1 Add the sample",
            Verdict.DISCARD_PLAN,
            "verdict/discard-plan",
        ),
    ],
)
def test_a_discard_of_the_model_alone_labels_and_comments_and_leaves_the_close_to_a_person(
    world: World, kind: PullKind, title: str, verdict: Verdict, label: str
) -> None:
    """Issue text can steer the model, so a discard of the model alone closes nothing and needs
    no withdraw (#6024, items 7 and 8)."""
    item = world.item()
    pull = world.pull(item, title=title, kind=kind)
    judge = FakeJudge(_reply(ReplyVerdict.DISCARD, CODE))

    report = run_review(world.store, REPO, pull, judge=judge, mode="on", confirm=True)

    assert (report.result, report.verdict, report.label, report.written) == (
        ReviewResult.JUDGED,
        verdict,
        label,
        True,
    )
    assert report.action.startswith("a person decides the discard")
    assert (world.closed(), world.withdrawn, world.labels(pull)) == ([], [], (label,))
    [comment] = world.comments()
    assert "a person decides the discard" in comment
    held = world.store.item(item)
    assert held is not None
    assert held.status != "New"
    assert world.record(item)["review.source"] == "model"


def _rule_discard(world: World, item: int, pull: int, kind: PullKind) -> ReviewCall:
    """The call of the step on `pull`, as `run_review` builds it, for a discard of a rule."""
    held = world.store.item(item)
    assert held is not None
    status = get_github_session().client.get_pull_status(REPO, pull)
    return ReviewCall(world.store, REPO, pull, status, held, kind, "on", True, 0, BOT)


_RULE_DISCARD = Judgement(Verdict.DISCARD_IMPLEMENTATION, "The work cannot be fixed.")


@pytest.mark.parametrize(
    ("kind", "title", "verdict", "key"),
    [
        (
            PullKind.DELIVERY,
            "feat(roadmap): Add the sample",
            Verdict.DISCARD_IMPLEMENTATION,
            ImplementRecordKey.PR,
        ),
        (PullKind.PLAN, "docs(openspec): plan #1 Add", Verdict.DISCARD_PLAN, StageRecordKey.PR),
    ],
)
def test_a_discard_deletes_the_branch_first_then_closes_then_returns_the_item(
    world: World, kind: PullKind, title: str, verdict: Verdict, key: Any
) -> None:
    """A delete that fails would leave a closed pull request and an item that never goes back
    (#6024, item 2)."""
    item = world.item(record={ImplementRecordKey.BRANCH: "feat/0-other"})
    pull = world.pull(item, title=title, kind=kind)
    branch = f"{'docs' if kind is PullKind.PLAN else 'feat'}/{item}-sample"

    report = write_verdict(
        _rule_discard(world, item, pull, kind),
        Judgement(verdict, "The work cannot be fixed."),
        withdraw=world.withdraw,
    )

    assert (report.result, report.verdict) == (ReviewResult.JUDGED, verdict)
    assert (world.withdrawn, world.closes_before_withdraw, world.closed()) == (
        [(branch, HEAD)],
        [0],
        [pull],
    )
    held = world.store.item(item)
    assert held is not None
    assert (held.status, held.job_record.get(key)) == ("New", None)
    assert set(world.record(item).values()) == {None}


def test_a_failed_delete_closes_nothing_and_the_next_call_can_try_again(world: World) -> None:
    item = world.item(record={ImplementRecordKey.BRANCH: "feat/0-other"})
    pull = world.pull(item)

    def refuse(branch: str, lease: str) -> None:
        raise GitOperationError("the lease of the delete broke", operation="roadmap.review")

    with pytest.raises(GitOperationError, match="lease"):
        write_verdict(
            _rule_discard(world, item, pull, PullKind.DELIVERY), _RULE_DISCARD, withdraw=refuse
        )

    assert world.closed() == []
    held = world.store.item(item)
    assert held is not None
    assert held.job_record.get(ImplementRecordKey.PR) == str(pull)
    assert world.record(item)["review.discard"] == f"{pull}:{HEAD}"


def test_a_call_on_the_closed_pull_request_ends_a_discard_that_stopped(world: World) -> None:
    """The delete ran, and GitHub closed the pull request, but the return did not (#6024)."""
    item = world.item()
    pull = world.pull(item, state="closed")
    unmarked = world.run(pull, mode="on", confirm=True)
    held = world.store.item(item)
    assert held is not None
    world.store.set_marks(held, {ReviewRecordKey.DISCARD: f"{pull}:{HEAD}"})

    report = world.run(pull, mode="on", confirm=True)

    assert unmarked.result is ReviewResult.SKIPPED

    assert (report.result, report.verdict, report.written) == (
        ReviewResult.JUDGED,
        Verdict.DISCARD_IMPLEMENTATION,
        True,
    )
    assert world.withdrawn == [(f"feat/{item}-sample", HEAD)]
    held = world.store.item(item)
    assert held is not None
    assert (held.status, held.job_record.get(ImplementRecordKey.PR)) == ("New", None)
    assert held.job_record.get(ReviewRecordKey.DISCARD) is None


def test_a_discard_without_a_withdraw_writes_nothing(world: World) -> None:
    """The check of the withdraw comes before the first write (#6024, item 8)."""
    item = world.item(record={ImplementRecordKey.BRANCH: "feat/0-other"})
    pull = world.pull(item)

    with pytest.raises(RoadmapImplementError, match="withdraw"):
        write_verdict(_rule_discard(world, item, pull, PullKind.DELIVERY), _RULE_DISCARD)

    assert (world.comments(), world.labels(pull), world.closed()) == ([], (), [])


@pytest.mark.parametrize(
    ("kind", "record"),
    [
        (PullKind.PLAN, "implement.branch"),
        (PullKind.DELIVERY, "stage.pr"),
    ],
)
def test_a_discard_of_a_branch_that_holds_other_work_is_left_for_a_person(
    world: World, kind: PullKind, record: str
) -> None:
    """A plan branch that the implement job builds on, or a delivery on the branch of its plan,
    keeps its branch (#6024, item 6)."""
    title = "docs(openspec): plan #1 Add" if kind is PullKind.PLAN else "feat(roadmap): Add"
    item = world.item()
    pull = world.pull(item, title=title, kind=kind)
    branch = f"{'docs' if kind is PullKind.PLAN else 'feat'}/{item}-sample"
    held = world.store.item(item)
    assert held is not None
    shared = ImplementRecordKey.BRANCH if record == "implement.branch" else StageRecordKey.PR
    world.store.set_marks(held, {shared: branch if record == "implement.branch" else str(pull)})
    verdict = Verdict.DISCARD_PLAN if kind is PullKind.PLAN else Verdict.DISCARD_IMPLEMENTATION

    report = write_verdict(
        _rule_discard(world, item, pull, kind),
        Judgement(verdict, "The work cannot be fixed."),
        withdraw=world.withdraw,
    )

    assert report.result is ReviewResult.STOPPED
    assert (world.withdrawn, world.closed(), world.labels(pull)) == ([], [], ())
    [comment] = world.comments()
    assert "a person decides the discard" in comment


def test_a_new_fact_on_a_judged_head_gives_a_new_verdict(world: World) -> None:
    """A plan is judged Mergeable and marked ready; plan drift then adds `verdict/fix-plan`. The
    rules run again on the same head, the model is not asked again, and the plan goes back to
    draft for fix-plan (#6024, item 1)."""
    item = world.item()
    title = "docs(openspec): plan #1 Add the sample"
    pull = world.pull(item, title=title, kind=PullKind.PLAN)
    judge = FakeJudge(_reply(ReplyVerdict.MERGEABLE))
    world.run(pull, judge, mode="on", confirm=True)
    branch = f"docs/{item}-sample"
    labels = ("verdict/mergeable", "verdict/fix-plan")
    world.store.label_issue(pull, "verdict/fix-plan")
    world.status(pull, draft=False, title=title, branch=branch, labels=labels)

    report = world.run(pull, judge, mode="on", confirm=True)

    assert (report.result, report.verdict, report.due) == (
        ReviewResult.JUDGED,
        Verdict.NEEDS_FIX,
        DueFix.FIX_PLAN,
    )
    assert len(judge.cases) == 1
    assert world.ready[-1] == ("pr", "ready", str(pull), "--undo", "--repo", REPO)
    assert world.labels(pull) == ("verdict/fix-plan",)
    assert world.record(item)["review.rounds"] == "2"


def test_a_ready_pull_request_that_a_person_marked_ready_stays_ready(world: World) -> None:
    """The step does not take back the ready mark of a person (#6024, item 3)."""
    item = world.item()
    pull = world.pull(item, runs=(("Static Analysis", "failure"),), draft=False, ready_by="person")

    report = world.run(pull, mode="on", confirm=True)

    assert (report.verdict, report.written) == (Verdict.NEEDS_FIX, True)
    assert report.action.startswith("a person marked the pull request ready")
    assert world.ready == []


def test_an_item_that_a_live_stage_job_holds_is_skipped(world: World) -> None:
    """The watch row and the open row skip a live `stage.job` too (#6024, item 4)."""
    item = world.item(record={StageRecordKey.JOB: "stage-12-abc"})
    pull = world.pull(item)
    judge = FakeJudge(_reply(ReplyVerdict.MERGEABLE))

    report = world.run(pull, judge, mode="on", confirm=True)

    assert (report.result, judge.cases, world.comments()) == (ReviewResult.SKIPPED, [], [])
    assert "stage-12-abc" in report.reason


def test_the_claim_of_the_service_does_not_stop_the_review(world: World) -> None:
    """`owner/service` holds nothing against the jobs of the Service (`claim_labels`, item 5)."""
    pull = world.pull(world.item("owner/service"), labels=("owner/service",))

    report = world.run(pull, mode="on")

    assert (report.result, report.verdict) == (ReviewResult.JUDGED, Verdict.MERGEABLE)


def test_a_wait_on_ci_infrastructure_logs_and_ends_after_its_limit(
    world: World, caplog: pytest.LogCaptureFixture
) -> None:
    """The first wait of a head records its time; after `infra_wait_hours` the step comments once
    for a person (#6024, item 9)."""
    item = world.item()
    pull = world.pull(item, runs=(("Tests", "success"), ("Test Job Duration", "failure")))
    start = datetime(2026, 11, 16, 8, 0, tzinfo=UTC)

    with caplog.at_level(logging.INFO, logger="devops_cli.roadmap.steps.review"):
        first = world.run(pull, mode="on", confirm=True, now=start)
    later = world.run(pull, mode="on", confirm=True, now=start + timedelta(hours=6))

    assert (first.result, later.result) == (ReviewResult.WAIT, ReviewResult.STOPPED)
    assert world.record(item)["review.wait"] == f"{HEAD} {start.isoformat()}"
    assert "waits on CI infrastructure" in caplog.text
    [comment] = world.comments()
    assert "a person runs the failed check again" in comment


def test_an_issue_text_that_an_issue_changed_verdict_answered_is_not_judged_again(
    world: World,
) -> None:
    """After an issue edit, the updated work of that text gets its own verdict, not Issue changed
    on each new head (#6024, item 9)."""
    item = world.item(record={StageRecordKey.TEXT_HASH: "0" * 64})
    pull = world.pull(item)
    world.run(pull, mode="on", confirm=True)
    assert world.record(item)["review.text"] == body_hashes(BODY)[0]
    world.status(pull, heads=(NEW_HEAD,), branch=f"feat/{item}-sample")
    world.api.route(
        "GET",
        f"/repos/{REPO}/commits/{NEW_HEAD}/check-runs?per_page=100",
        github_json({"total_count": 1, "check_runs": [_RUN_PASSED]}),
    )
    route_compare_files(
        world.api,
        REPO,
        "main",
        NEW_HEAD,
        {"filename": CODE, "status": "modified"},
        {
            "filename": f"openspec/changes/archive/2026-11-16-{item}-sample/tasks.md",
            "status": "added",
        },
        merge_base=BASE,
    )
    route_compare_diff(world.api, REPO, "main", NEW_HEAD, "diff")
    route_file(
        world.api,
        REPO,
        f"openspec/changes/archive/2026-11-16-{item}-sample/tasks.md",
        NEW_HEAD,
        TICKED,
    )

    report = world.run(pull, mode="on")

    assert report.verdict is Verdict.MERGEABLE


def test_a_head_that_moves_after_the_read_writes_nothing(world: World) -> None:
    item = world.item()
    pull = world.pull(item, heads=(HEAD, NEW_HEAD))

    report = world.run(pull, mode="on", confirm=True)

    assert (report.result, report.written) == (ReviewResult.SKIPPED, False)
    assert (world.comments(), world.ready, world.labels(pull)) == ([], [], ())


def test_the_cap_of_rounds_leaves_the_pull_request_for_a_person_with_no_model_call(
    world: World,
) -> None:
    item = world.item()
    pull = world.pull(item)
    held = world.store.item(item)
    assert held is not None
    world.store.set_marks(held, {ReviewRecordKey.PULL: str(pull), ReviewRecordKey.ROUNDS: "3"})
    judge = FakeJudge(_reply(ReplyVerdict.MERGEABLE))

    report = world.run(pull, judge, mode="on", confirm=True)

    assert (report.result, judge.cases) == (ReviewResult.CAPPED, [])
    [comment] = world.comments()
    assert "A person decides" in comment


def test_rounds_of_another_pull_request_do_not_count(world: World) -> None:
    item = world.item(record={ReviewRecordKey.PULL: "999", ReviewRecordKey.ROUNDS: "3"})
    pull = world.pull(item)

    report = world.run(pull, mode="on")

    assert (report.result, report.rounds) == (ReviewResult.JUDGED, 0)


def test_a_failed_model_call_fails_the_attempt_and_writes_nothing(world: World) -> None:
    pull = world.pull(world.item())
    judge = FakeJudge(error=DevOpsCLIError("gateway down"))

    report = world.run(pull, judge, mode="on", confirm=True)

    assert report.result is ReviewResult.FAILED
    assert "gateway down" in report.reason
    assert world.comments() == []


def test_merged_work_since_the_base_on_the_change_folder_is_issue_changed(world: World) -> None:
    item = world.item()
    folder = f"openspec/changes/archive/2026-11-16-{item}-sample/tasks.md"
    pull = world.pull(item, history=[_commit("4" * 40, 77, folder)])

    report = world.run(pull, mode="on")

    assert report.verdict is Verdict.ISSUE_CHANGED
    assert report.evidence == (f"#77 changed `{folder}`",)


def test_the_grades_score_the_label_that_the_step_wrote(world: World) -> None:
    """`devops roadmap eval grades` reads the first verdict label of each bot pull request from
    its label events: the label that the step wrote scores as its verdict (#5968)."""
    item = world.item()
    pull = world.pull(item, runs=(("Static Analysis", "failure"),))
    world.run(pull, mode="on", confirm=True)
    title = "feat(roadmap): Add the sample"
    nodes = [
        {
            "number": pull,
            "title": title,
            "repository": {"nameWithOwner": REPO},
            "timelineItems": {"nodes": [{"label": {"name": name}} for name in world.labels(pull)]},
        }
    ]
    page = {
        "data": {
            "search": {
                "issueCount": 1,
                "pageInfo": {"hasNextPage": False, "endCursor": None},
                "nodes": nodes,
            }
        }
    }
    world.api.route("POST", "/graphql", github_json(page))

    [scored] = read_bot_pulls(get_github_session().client, "is:pr")
    grade = grade_verdicts(KIND_JOBS[scored.kind], [scored.verdict], partial_score=0.5)

    assert scored.verdict is Verdict.NEEDS_FIX
    assert grade.score == 0.5
