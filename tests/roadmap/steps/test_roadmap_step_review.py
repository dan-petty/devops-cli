"""Tests for the roadmap step `review` (#5969).

The rules are pure functions of `ReviewFacts`, so most cases need no fake. The calls of
`run_review` fake GitHub's REST and GraphQL API at the HTTP edge, `gh pr ready` at the process
edge, and the roadmap store in memory. The model judge and the delete of a branch are given to the
step as parameters.
"""

from __future__ import annotations

import json
import subprocess
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

import pytest

from devops_cli.config.settings import Settings
from devops_cli.exceptions import DevOpsCLIError
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
    ReviewResult,
    Waiting,
    model_judgement,
    rule_judgement,
    run_review,
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

    assert isinstance(rule_judgement(_facts(checks=checks)), Waiting)


@pytest.mark.parametrize(
    "checks",
    [
        _checks(_check("Tests", CheckBucket.PENDING)),
        CheckVerdictSummary(
            items=[
                PRCheckItem(name="no checks reported", state="pending", bucket=CheckBucket.PENDING)
            ]
        ),
        CheckVerdictSummary(unread_reason="GitHub answered 502"),
    ],
)
def test_a_check_that_runs_or_cannot_be_read_waits(checks: CheckVerdictSummary) -> None:
    assert isinstance(rule_judgement(_facts(checks=checks)), Waiting)


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
    ) -> int:
        """The pull request of `item` on its branch, with its check runs, its diff, its threads,
        the history of the base branch, and the change folder of the item."""
        branch = f"{'docs' if kind is PullKind.PLAN else 'feat'}/{item}-sample"
        number = self.store.seed_pull(
            title, head_ref=branch, head_sha=HEAD, draft=draft, labels=labels
        )
        key = StageRecordKey.PR if kind is PullKind.PLAN else ImplementRecordKey.PR
        held = self.store.item(item)
        assert held is not None
        self.store.set_marks(held, {key: str(number)})
        self.api.route(
            "GET",
            f"/repos/{REPO}/pulls/{number}",
            *(
                github_json(
                    {
                        "state": "open",
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
                    "pullRequest": {"reviewThreads": {"nodes": list(threads)}},
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

    def withdraw(self, branch: str, lease: str) -> None:
        self.withdrawn.append((branch, lease))

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


def test_a_discarded_delivery_is_closed_withdrawn_and_returned_for_a_new_implementation(
    world: World,
) -> None:
    item = world.item(record={ImplementRecordKey.BRANCH: "feat/1-sample"})
    pull = world.pull(item)
    judge = FakeJudge(_reply(ReplyVerdict.DISCARD, CODE))

    report = world.run(pull, judge, mode="on", confirm=True)

    assert (report.verdict, report.label) == (
        Verdict.DISCARD_IMPLEMENTATION,
        "verdict/discard-implementation",
    )
    assert world.closed() == [pull]
    assert world.withdrawn == [(f"feat/{item}-sample", HEAD)]
    held = world.store.item(item)
    assert held is not None
    assert held.status == "New"
    assert held.job_record.get(ImplementRecordKey.PR) is None
    assert held.job_record.get(ImplementRecordKey.BRANCH) is None
    assert set(world.record(item).values()) == {None}


def test_a_discarded_plan_clears_the_keys_of_the_plan(world: World) -> None:
    item = world.item()
    pull = world.pull(item, title="docs(openspec): plan #1 Add the sample", kind=PullKind.PLAN)
    judge = FakeJudge(_reply(ReplyVerdict.DISCARD, f"openspec/changes/{item}-sample/tasks.md"))

    report = world.run(pull, judge, mode="on", confirm=True)

    assert (report.verdict, report.label) == (Verdict.DISCARD_PLAN, "verdict/discard-plan")
    assert world.withdrawn == [(f"docs/{item}-sample", HEAD)]
    held = world.store.item(item)
    assert held is not None
    assert (held.status, held.job_record.get(StageRecordKey.PR)) == ("New", None)


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
