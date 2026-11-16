"""Tests for the roadmap step `fix-checks` (#5023, #5971).

Verifies:
- Dry-run sees 0 requests
- A person pull request is refused/stopped
- An item or PR with an owner label is stopped
- A moved head returns skipped
- Soft and hard caps hold, and head count limit holds
- A run without confirm plans and writes nothing
- CI infrastructure failure posts a comment and waits
- Tier 1 fixes a lint failure with 0 model requests
- A log outside the plan scope stops with 0 model requests
- A log within plan scope runs a fix step, and the step pushes its commit
- A repaired draft whose checks pass is marked ready by the readiness rule

The GitHub client is a fake. The checks and the failed log are answered at the two functions that
read them, and the checkout is a fake that records its push.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest

from devops_cli.config.constants import CONST_GIT_MAIN_BRANCH
from devops_cli.exceptions import RoadmapImplementError
from devops_cli.github.check_verdict import CheckBucket, CheckVerdictSummary, PRCheckItem
from devops_cli.github.client import PullStatus
from devops_cli.roadmap.implement.implement_pull import Answer, Draft, DraftKind, Readiness
from devops_cli.roadmap.steps import fix_checks
from devops_cli.roadmap.steps.fix_checks import (
    FixChecksResult,
    Fixed,
    Repair,
    dry_run_fix_checks,
    run_fix_checks,
)
from devops_cli.roadmap.stores.store import FixChecksRecordKey, ImplementRecordKey
from tests.support.fakes.roadmap_store import InMemoryRoadmapStore

pytestmark = pytest.mark.usefixtures("keyring_store")

REPO = "example/project"
BOT_USER = "devops-cli-service[bot]"
BRANCH = "feat/42-sample"
HEAD_SHA = "1111111111111111111111111111111111111111"
NEW_HEAD = "2222222222222222222222222222222222222222"
STATIC = "Static Analysis"
PLAN_LOG = "src/devops_cli/sample.py:10: error: undefined name 'foo'"
NO_LINT = Fixed(done=False, reason="not a lint failure")
COMMITTED = Fixed(done=True)
READY = Readiness(Answer.READY)


def _summary(name: str = STATIC, bucket: CheckBucket = CheckBucket.FAIL) -> CheckVerdictSummary:
    return CheckVerdictSummary(
        items=[
            PRCheckItem(
                name=name,
                bucket=bucket,
                link="https://github.com/example/project/actions/runs/1/job/2",
            ),
        ],
    )


class FakeGitHubClient:
    """The pull request, its checks and the log of its failed check, and the comments the step
    posts. The last client made answers the reads of the checks and of the log."""

    last: FakeGitHubClient | None = None

    def __init__(
        self,
        status: PullStatus | None = None,
        checks: CheckVerdictSummary | None = None,
        log: str = "",
    ) -> None:
        self.status = status or PullStatus.model_validate(
            {
                "state": "open",
                "draft": True,
                "head": {"ref": BRANCH, "sha": HEAD_SHA},
                "base": {"ref": CONST_GIT_MAIN_BRANCH},
                "user": {"login": BOT_USER},
                "labels": [],
            }
        )
        self.checks = checks or _summary()
        self.log = log or PLAN_LOG
        self.comments: list[str] = []
        type(self).last = self

    def get_pull_status(self, repo: str, pull: int) -> PullStatus:
        return self.status

    def comment_on_pull(self, repo: str, pull: int, body: str) -> None:
        self.comments.append(body)


class FakeGitHubSession:
    def __init__(self, client: FakeGitHubClient) -> None:
        self.client = client


@pytest.fixture(autouse=True)
def github_edges(monkeypatch: pytest.MonkeyPatch) -> None:
    """The step reads the check runs and the failed log through these two functions."""

    def checks(owner: str, name: str, sha: str) -> CheckVerdictSummary:
        assert FakeGitHubClient.last is not None
        return FakeGitHubClient.last.checks

    def log(repo: str, check: PRCheckItem) -> str:
        assert FakeGitHubClient.last is not None
        return FakeGitHubClient.last.log

    monkeypatch.setattr(fix_checks, "read_check_runs", checks)
    monkeypatch.setattr(fix_checks, "failed_log", log)


@dataclass
class FakeCheckout:
    """A checkout whose push returns `pushed_head`: the new head, or None when no fixer made a
    commit."""

    path: Path
    pushed_head: str | None = NEW_HEAD
    pushes: int = 0

    def push(self) -> str | None:
        self.pushes += 1
        return self.pushed_head


@dataclass
class FakeRepair:
    """The repair of a round, with each call recorded."""

    path: Path
    tier1: Fixed = NO_LINT
    model: Fixed = COMMITTED
    in_scope: bool = True
    pushed_head: str | None = NEW_HEAD
    calls: list[str] = field(default_factory=list)
    checkout: FakeCheckout | None = None

    def build(self) -> Repair:
        @contextmanager
        def checkout(status: PullStatus, item: int) -> Iterator[FakeCheckout]:
            self.calls.append(f"checkout {status.head_ref} {item}")
            self.checkout = FakeCheckout(self.path, self.pushed_head)
            yield self.checkout

        def tier1(path: Path, item: int, check: str, log: str) -> Fixed:
            self.calls.append("tier1")
            return self.tier1

        def model(path: Path, item: int, check: str, log: str) -> Fixed:
            self.calls.append("model")
            return self.model

        def scope(path: Path, item: int, log: str, is_stage_plan: bool) -> bool:
            self.calls.append("scope")
            return self.in_scope

        return Repair(checkout=checkout, tier1=tier1, model=model, scope=scope)


def _seed_item(
    store: InMemoryRoadmapStore,
    labels: list[str] | None = None,
    record: dict[Any, str | None] | None = None,
) -> int:
    all_labels = ["priority/p2-medium", *(labels or [])]
    num = store.seed_issue("Sample feature", labels=all_labels)
    if record:
        item = store.item(num)
        assert item is not None
        store.set_marks(item, record)
    return num


def _fake_status(pull: int = 42, **kwargs: Any) -> PullStatus:
    data: dict[str, Any] = {
        "state": "open",
        "draft": True,
        "head": {"ref": f"feat/{pull}-sample", "sha": HEAD_SHA},
        "base": {"ref": CONST_GIT_MAIN_BRANCH},
        "user": {"login": BOT_USER},
        "labels": [],
    }
    data.update(kwargs)
    return PullStatus.model_validate(data)


def _record(store: InMemoryRoadmapStore, pull: int) -> dict[str, str | None]:
    item = store.item(pull)
    assert item is not None
    return {key: item.job_record.get(key) for key in FixChecksRecordKey}


def test_dry_run_sees_zero_requests() -> None:
    reads, writes = dry_run_fix_checks(REPO, 42)
    assert reads == ()
    assert writes == ()


def test_person_pull_request_is_stopped() -> None:
    store = InMemoryRoadmapStore(repo=REPO)
    human_status = PullStatus.model_validate(
        {
            "state": "open",
            "draft": True,
            "head": {"ref": BRANCH, "sha": HEAD_SHA},
            "base": {"ref": CONST_GIT_MAIN_BRANCH},
            "user": {"login": "human-dev"},
            "labels": [],
        }
    )
    client = FakeGitHubClient(status=human_status)
    session = FakeGitHubSession(client)

    report = run_fix_checks(store, REPO, 42, session=session)
    assert report.result == FixChecksResult.STOPPED
    assert "bot" in report.reason.lower()


def test_owner_label_stops() -> None:
    store = InMemoryRoadmapStore(repo=REPO)
    status = PullStatus.model_validate(
        {
            "state": "open",
            "draft": True,
            "head": {"ref": BRANCH, "sha": HEAD_SHA},
            "base": {"ref": CONST_GIT_MAIN_BRANCH},
            "user": {"login": BOT_USER},
            "labels": ["owner/human"],
        }
    )
    client = FakeGitHubClient(status=status)
    session = FakeGitHubSession(client)

    report = run_fix_checks(store, REPO, 42, session=session)
    assert report.result == FixChecksResult.STOPPED
    assert "owner" in report.reason.lower()


def test_moved_head_returns_skipped() -> None:
    store = InMemoryRoadmapStore(repo=REPO)
    client = FakeGitHubClient()
    session = FakeGitHubSession(client)

    report = run_fix_checks(store, REPO, 42, head=NEW_HEAD, session=session)
    assert report.result == FixChecksResult.SKIPPED
    assert "moved" in report.reason.lower()


def test_caps_hold_soft_and_hard() -> None:
    store = InMemoryRoadmapStore(repo=REPO)
    pull = _seed_item(store, record={FixChecksRecordKey.ROUNDS: "5"})
    client = FakeGitHubClient(status=_fake_status(pull))
    session = FakeGitHubSession(client)

    # Hard cap reached (5 rounds)
    report = run_fix_checks(store, REPO, pull, session=session)
    assert report.result == FixChecksResult.STOPPED
    assert "hard cap" in report.reason.lower()

    # Soft cap reached without error reduction
    store = InMemoryRoadmapStore(repo=REPO)
    pull = _seed_item(
        store,
        record={
            FixChecksRecordKey.ROUNDS: "3",
            FixChecksRecordKey.ERRORS: "1",
        },
    )
    # Failed log has 2 errors (> 1)
    client_more_err = FakeGitHubClient(
        status=_fake_status(pull),
        log="error: one\nerror: two",
    )
    report = run_fix_checks(store, REPO, pull, session=FakeGitHubSession(client_more_err))
    assert report.result == FixChecksResult.STOPPED
    assert "soft cap" in report.reason.lower()

    # Head count limit (more than 3 heads)
    store = InMemoryRoadmapStore(repo=REPO)
    pull = _seed_item(
        store,
        record={
            FixChecksRecordKey.HEADS: "h1,h2,h3",
        },
    )
    client_heads = FakeGitHubClient(status=_fake_status(pull))
    report = run_fix_checks(store, REPO, pull, session=FakeGitHubSession(client_heads))
    assert report.result == FixChecksResult.STOPPED
    assert "head" in report.reason.lower()


# ── Without --confirm ────────────────────────────────────────────────────────────────────


def test_a_run_without_confirm_plans_the_repair_and_writes_nothing(tmp_path: Path) -> None:
    """The case of #5971: a failed `Static Analysis` check whose log names a file of the plan."""
    store = InMemoryRoadmapStore(repo=REPO)
    pull = _seed_item(store)
    client = FakeGitHubClient(status=_fake_status(pull))
    repair = FakeRepair(tmp_path)

    report = run_fix_checks(
        store, REPO, pull, session=FakeGitHubSession(client), repair=repair.build()
    )

    assert (report.result, report.head) == (FixChecksResult.PLANNED, HEAD_SHA)
    assert STATIC in report.reason
    assert (repair.calls, client.comments) == ([], [])
    assert set(_record(store, pull).values()) == {None}


def test_a_ci_infra_failure_without_confirm_posts_no_comment() -> None:
    store = InMemoryRoadmapStore(repo=REPO)
    pull = _seed_item(store)
    client = FakeGitHubClient(
        status=_fake_status(pull),
        checks=_summary("Test Job Duration"),
        log="Job duration exceeded runner limit",
    )

    report = run_fix_checks(store, REPO, pull, session=FakeGitHubSession(client))

    assert report.result == FixChecksResult.PLANNED
    assert client.comments == []
    assert set(_record(store, pull).values()) == {None}


# ── With --confirm ───────────────────────────────────────────────────────────────────────


def test_ci_infra_failure_posts_comment_and_waits() -> None:
    store = InMemoryRoadmapStore(repo=REPO)
    pull = _seed_item(store)
    client = FakeGitHubClient(
        status=_fake_status(pull),
        checks=_summary("Test Job Duration"),
        log="Job duration exceeded runner limit",
    )
    session = FakeGitHubSession(client)

    report = run_fix_checks(store, REPO, pull, session=session, confirm=True)
    assert report.result == FixChecksResult.WAIT
    assert len(client.comments) == 1
    assert (
        "infrastructure" in client.comments[0].lower() or "ci_infra" in client.comments[0].lower()
    )
    assert _record(store, pull)[FixChecksRecordKey.RESULT] == "wait"


def test_a_confirmed_repair_needs_a_repair() -> None:
    store = InMemoryRoadmapStore(repo=REPO)
    pull = _seed_item(store)
    client = FakeGitHubClient(status=_fake_status(pull))

    with pytest.raises(RoadmapImplementError, match="repair"):
        run_fix_checks(store, REPO, pull, session=FakeGitHubSession(client), confirm=True)


def test_tier1_fixes_lint_with_zero_model_requests(tmp_path: Path) -> None:
    store = InMemoryRoadmapStore(repo=REPO)
    pull = _seed_item(store)
    client = FakeGitHubClient(status=_fake_status(pull), log="ruff check found 2 errors")
    repair = FakeRepair(tmp_path, tier1=Fixed(done=True))

    report = run_fix_checks(
        store, REPO, pull, session=FakeGitHubSession(client), confirm=True, repair=repair.build()
    )

    assert repair.calls == [f"checkout feat/{pull}-sample {pull}", "tier1"]
    assert (report.result, report.head) == (FixChecksResult.REPAIRED, NEW_HEAD)
    assert "0 model requests" in report.reason
    record = _record(store, pull)
    assert (record[FixChecksRecordKey.RESULT], record[FixChecksRecordKey.ROUNDS]) == (
        "repaired",
        "1",
    )


def test_outside_plan_scope_stops_with_zero_model_requests(tmp_path: Path) -> None:
    store = InMemoryRoadmapStore(repo=REPO)
    pull = _seed_item(store)
    client = FakeGitHubClient(
        status=_fake_status(pull),
        checks=_summary("Unit Tests"),
        log="FAILED tests/unrelated/test_other.py::test_foo",
    )
    repair = FakeRepair(tmp_path, in_scope=False)

    report = run_fix_checks(
        store, REPO, pull, session=FakeGitHubSession(client), confirm=True, repair=repair.build()
    )

    assert "model" not in repair.calls
    assert repair.checkout is not None
    assert repair.checkout.pushes == 0
    assert report.result == FixChecksResult.STOPPED
    assert "outside" in report.reason.lower()


def test_a_failed_check_whose_log_names_a_file_of_the_plan_ends_repaired(tmp_path: Path) -> None:
    """The case of #5971 with the real scope check: the checkout holds the archived change of the
    item, and the log of the failed `Static Analysis` check names a file that the plan changes."""
    store = InMemoryRoadmapStore(repo=REPO)
    pull = _seed_item(store)
    archived = tmp_path / "openspec" / "changes" / "archive" / f"2026-11-16-{pull}-sample"
    archived.mkdir(parents=True)
    (archived / "tasks.md").write_text(
        "# Tasks\n\n## 1. Group\n\nChanges: `src/devops_cli/sample.py`.\n\n- [x] 1.1 Do it\n",
        encoding="utf-8",
    )
    client = FakeGitHubClient(status=_fake_status(pull))
    repair = FakeRepair(tmp_path)
    built = repair.build()
    real_scope = Repair(
        checkout=built.checkout, tier1=built.tier1, model=built.model, scope=fix_checks.check_scope
    )

    report = run_fix_checks(
        store, REPO, pull, session=FakeGitHubSession(client), confirm=True, repair=real_scope
    )

    assert (report.result, report.head, report.rounds) == (FixChecksResult.REPAIRED, NEW_HEAD, 1)
    assert repair.calls == [f"checkout feat/{pull}-sample {pull}", "tier1", "model"]
    assert repair.checkout is not None
    assert repair.checkout.pushes == 1
    assert _record(store, pull)[FixChecksRecordKey.KEY] == f"{HEAD_SHA}:{STATIC}"


def test_model_fix_failure_names_its_reason(tmp_path: Path) -> None:
    store = InMemoryRoadmapStore(repo=REPO)
    pull = _seed_item(store)
    client = FakeGitHubClient(status=_fake_status(pull))
    repair = FakeRepair(tmp_path, model=Fixed(done=False, reason="limit reached"))

    report = run_fix_checks(
        store, REPO, pull, session=FakeGitHubSession(client), confirm=True, repair=repair.build()
    )

    assert report.result == FixChecksResult.FAILED
    assert "model repair failed" in report.reason.lower()
    assert "limit reached" in report.reason
    assert repair.checkout is not None
    assert repair.checkout.pushes == 0
    assert _record(store, pull)[FixChecksRecordKey.RESULT] == "failed"


def test_a_repair_that_leaves_the_judged_head_fails(tmp_path: Path) -> None:
    store = InMemoryRoadmapStore(repo=REPO)
    pull = _seed_item(store)
    client = FakeGitHubClient(status=_fake_status(pull))
    repair = FakeRepair(tmp_path, pushed_head=None)

    report = run_fix_checks(
        store, REPO, pull, session=FakeGitHubSession(client), confirm=True, repair=repair.build()
    )

    assert report.result == FixChecksResult.FAILED
    assert "no commit" in report.reason.lower()


def test_closed_pull_request_skipped() -> None:
    store = InMemoryRoadmapStore(repo=REPO)
    status = _fake_status(42, state="closed")
    client = FakeGitHubClient(status=status)
    session = FakeGitHubSession(client)
    report = run_fix_checks(store, REPO, 42, session=session)
    assert report.result == FixChecksResult.SKIPPED
    assert "closed" in report.reason.lower()


def test_passing_checks_skipped() -> None:
    store = InMemoryRoadmapStore(repo=REPO)
    pull = _seed_item(store)
    client = FakeGitHubClient(status=_fake_status(pull), checks=_summary(bucket=CheckBucket.PASS))
    session = FakeGitHubSession(client)
    report = run_fix_checks(store, REPO, pull, session=session, confirm=True)
    assert report.result == FixChecksResult.SKIPPED
    assert "no failed check" in report.reason.lower()


# ── The ready mark after a repair ────────────────────────────────────────────────────────


@dataclass
class ReadyEdge:
    """The answer of the readiness rule, and the ready marks the step sends."""

    answer: Readiness = READY
    drafts: list[Draft] = field(default_factory=list)
    marked: list[tuple[str, int, str | None]] = field(default_factory=list)


@pytest.fixture
def ready_edge(monkeypatch: pytest.MonkeyPatch) -> ReadyEdge:
    edge = ReadyEdge()

    def read(repo: str, number: int, **kwargs: Any) -> Draft:
        return Draft(DraftKind.IMPLEMENT, kwargs["pull"], checks=kwargs["checks"])

    def judge(draft: Draft) -> Readiness:
        edge.drafts.append(draft)
        return edge.answer

    def mark(repo: str, pull: int, expected_head: str | None = None) -> None:
        edge.marked.append((repo, pull, expected_head))

    monkeypatch.setattr(fix_checks, "read_draft", read)
    monkeypatch.setattr(fix_checks, "draft_readiness", judge)
    monkeypatch.setattr(fix_checks, "mark_ready", mark)
    return edge


def _repaired_item(store: InMemoryRoadmapStore) -> int:
    pull = _seed_item(store, record={FixChecksRecordKey.RESULT: "repaired"})
    item = store.item(pull)
    assert item is not None
    store.set_marks(item, {ImplementRecordKey.PR: str(pull)})
    return pull


def test_a_repaired_draft_whose_checks_pass_is_marked_ready(ready_edge: ReadyEdge) -> None:
    store = InMemoryRoadmapStore(repo=REPO)
    pull = _repaired_item(store)
    client = FakeGitHubClient(status=_fake_status(pull), checks=_summary(bucket=CheckBucket.PASS))

    report = run_fix_checks(store, REPO, pull, session=FakeGitHubSession(client), confirm=True)

    assert report.result == FixChecksResult.READY
    assert ready_edge.marked == [(REPO, pull, HEAD_SHA)]
    assert _record(store, pull)[FixChecksRecordKey.RESULT] == "ready"


def test_a_repaired_draft_that_the_readiness_rule_holds_stays_a_draft(
    ready_edge: ReadyEdge,
) -> None:
    ready_edge.answer = Readiness(Answer.WAIT, "A task of the change is not ticked")
    store = InMemoryRoadmapStore(repo=REPO)
    pull = _repaired_item(store)
    client = FakeGitHubClient(status=_fake_status(pull), checks=_summary(bucket=CheckBucket.PASS))

    report = run_fix_checks(store, REPO, pull, session=FakeGitHubSession(client), confirm=True)

    assert report.result == FixChecksResult.SKIPPED
    assert "not ticked" in report.reason
    assert ready_edge.marked == []


def test_a_repaired_draft_without_confirm_is_not_marked_ready(ready_edge: ReadyEdge) -> None:
    store = InMemoryRoadmapStore(repo=REPO)
    pull = _repaired_item(store)
    client = FakeGitHubClient(status=_fake_status(pull), checks=_summary(bucket=CheckBucket.PASS))

    report = run_fix_checks(store, REPO, pull, session=FakeGitHubSession(client))

    assert report.result == FixChecksResult.PLANNED
    assert ready_edge.marked == []
    assert _record(store, pull)[FixChecksRecordKey.RESULT] == "repaired"


def test_a_draft_that_the_step_did_not_repair_is_left_to_the_watch_row(
    ready_edge: ReadyEdge,
) -> None:
    store = InMemoryRoadmapStore(repo=REPO)
    pull = _seed_item(store)
    client = FakeGitHubClient(status=_fake_status(pull), checks=_summary(bucket=CheckBucket.PASS))

    report = run_fix_checks(store, REPO, pull, session=FakeGitHubSession(client), confirm=True)

    assert report.result == FixChecksResult.SKIPPED
    assert (ready_edge.drafts, ready_edge.marked) == ([], [])


# ── Helpers ─────────────────────────────────────────────────────────────────────────────


def test_count_errors_patterns() -> None:
    from devops_cli.roadmap.steps.fix_checks import count_errors

    assert count_errors("") == 0
    assert count_errors("3 failed, 10 passed") == 3
    assert count_errors("Found 4 errors in project") == 4
    assert count_errors("1 error found") == 1
    assert count_errors("something bad\nERROR: bad\nFAIL: test\nfooter") == 2
    assert count_errors("generic line without markers") == 1


def test_is_bot_author_patterns() -> None:
    from devops_cli.config.constants import CONST_ROADMAP_OWNER_SERVICE
    from devops_cli.roadmap.steps.fix_checks import is_bot_author

    assert is_bot_author("") is False
    assert is_bot_author("custom-bot") is True
    assert is_bot_author("github-actions[bot]") is True
    assert is_bot_author(CONST_ROADMAP_OWNER_SERVICE) is True


def test_check_scope_helper(tmp_path: Path) -> None:
    from devops_cli.roadmap.steps.fix_checks import check_scope

    # Stage plan
    plan_dir = tmp_path / "openspec" / "changes" / "98-test-plan"
    plan_dir.mkdir(parents=True)
    assert (
        check_scope(
            tmp_path, 98, "error at openspec/changes/98-test-plan/tasks.md", is_stage_plan=True
        )
        is True
    )
    assert check_scope(tmp_path, 98, "error at src/other.py", is_stage_plan=True) is False

    # Archived change with tasks.md
    archive_dir = tmp_path / "openspec" / "changes" / "archive" / "2026-11-16-99-test-plan"
    archive_dir.mkdir(parents=True)
    (archive_dir / "tasks.md").write_text(
        "# Tasks\n\n## 1. Group\nReads: `src/read.py`.\nChanges: `src/mod.py`.\n- [ ] 1.1 Do it\n",
        encoding="utf-8",
    )
    assert check_scope(tmp_path, 99, "FAILED src/mod.py::test", is_stage_plan=False) is True
    assert check_scope(tmp_path, 99, "FAILED src/other.py", is_stage_plan=False) is False
    # Missing tasks.md or non-existent change
    assert check_scope(tmp_path, 888, "FAILED src/mod.py", is_stage_plan=False) is False


def test_report_to_json() -> None:
    from devops_cli.roadmap.steps.fix_checks import FixChecksReport

    report = FixChecksReport(
        repo=REPO,
        pull=42,
        result=FixChecksResult.REPAIRED,
        head="sha123",
        rounds=2,
        errors=3,
        reason="tier 2 repaired",
    )
    data = json.loads(report.to_json())
    assert data["job"] == "fix_checks"
    assert data["head"] == "sha123"
    assert data["rounds"] == 2
    assert data["errors"] == 3
    assert data["reason"] == "tier 2 repaired"
