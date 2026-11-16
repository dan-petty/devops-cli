"""Tests for the roadmap step `fix-checks` (#5023).

Verifies:
- Dry-run sees 0 requests
- A person pull request is refused/stopped
- An item or PR with an owner label is stopped
- A moved head returns skipped
- Soft and hard caps hold, and head count limit holds
- CI infrastructure failure posts a comment and waits
- Tier 1 fixes a lint failure with 0 model requests
- A log outside the plan scope stops with 0 model requests
- A log within plan scope runs a fix step
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from devops_cli.config.constants import CONST_GIT_MAIN_BRANCH
from devops_cli.github.check_verdict import CheckBucket, CheckVerdictSummary, PRCheckItem
from devops_cli.github.client import PullStatus
from devops_cli.roadmap.steps.fix_checks import (
    FixChecksResult,
    dry_run_fix_checks,
    run_fix_checks,
)
from devops_cli.roadmap.stores.store import FixChecksRecordKey
from tests.support.fakes.roadmap_store import InMemoryRoadmapStore

pytestmark = pytest.mark.usefixtures("keyring_store")

REPO = "example/project"
BOT_USER = "devops-cli-service[bot]"
BRANCH = "feat/42-sample"
HEAD_SHA = "1111111111111111111111111111111111111111"


class FakeGitHubClient:
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
        self.checks = checks or CheckVerdictSummary(
            items=[
                PRCheckItem(
                    name="Static Analysis",
                    bucket=CheckBucket.FAIL,
                    link="https://github.com/example/project/actions/runs/1/job/2",
                ),
            ],
        )
        self.log = log or "src/devops_cli/sample.py:10: error: undefined name 'foo'"
        self.comments: list[str] = []

    def get_pull_status(self, repo: str, pull: int) -> PullStatus:
        return self.status

    def comment_on_pull(self, repo: str, pull: int, body: str) -> None:
        self.comments.append(body)


class FakeGitHubSession:
    def __init__(self, client: FakeGitHubClient) -> None:
        self.client = client


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

    report = run_fix_checks(
        store, REPO, 42, head="2222222222222222222222222222222222222222", session=session
    )
    assert report.result == FixChecksResult.SKIPPED
    assert "moved" in report.reason.lower()


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


def test_ci_infra_failure_posts_comment_and_waits() -> None:
    store = InMemoryRoadmapStore(repo=REPO)
    pull = _seed_item(store)
    infra_checks = CheckVerdictSummary(
        items=[
            PRCheckItem(
                name="Test Job Duration",
                bucket=CheckBucket.FAIL,
                link="https://github.com/example/project/actions/runs/1/job/2",
            ),
        ],
    )
    client = FakeGitHubClient(
        status=_fake_status(pull),
        checks=infra_checks,
        log="Job duration exceeded runner limit",
    )
    session = FakeGitHubSession(client)

    report = run_fix_checks(store, REPO, pull, session=session)
    assert report.result == FixChecksResult.WAIT
    assert len(client.comments) == 1
    assert (
        "infrastructure" in client.comments[0].lower() or "ci_infra" in client.comments[0].lower()
    )
    updated = store.item(pull)
    assert updated is not None
    assert updated.job_record.get(FixChecksRecordKey.RESULT) == "wait"


def test_tier1_fixes_lint_with_zero_model_requests() -> None:
    store = InMemoryRoadmapStore(repo=REPO)
    pull = _seed_item(store)

    lint_checks = CheckVerdictSummary(
        items=[
            PRCheckItem(
                name="Static Analysis",
                bucket=CheckBucket.FAIL,
                link="https://github.com/example/project/actions/runs/1/job/2",
            ),
        ],
    )
    client = FakeGitHubClient(
        status=_fake_status(pull),
        checks=lint_checks,
        log="ruff check found 2 errors",
    )
    session = FakeGitHubSession(client)

    tier1_called = False

    def fake_tier1_runner(repo: str, pull: int, check_name: str, log: str) -> bool:
        nonlocal tier1_called
        tier1_called = True
        return True

    model_called = False

    def fake_model_runner(*args: Any, **kwargs: Any) -> Any:
        nonlocal model_called
        model_called = True
        raise AssertionError("Model should not be called for tier 1 fix")

    report = run_fix_checks(
        store,
        REPO,
        pull,
        session=session,
        tier1_fixer=fake_tier1_runner,
        model_fixer=fake_model_runner,
    )

    assert tier1_called is True
    assert model_called is False
    assert report.result == FixChecksResult.REPAIRED
    updated = store.item(pull)
    assert updated is not None
    assert updated.job_record.get(FixChecksRecordKey.RESULT) == "repaired"
    assert updated.job_record.get(FixChecksRecordKey.ROUNDS) == "1"


def test_outside_plan_scope_stops_with_zero_model_requests(tmp_path: Path) -> None:
    store = InMemoryRoadmapStore(repo=REPO)
    pull = _seed_item(store)

    # Log names file outside repair scope
    test_checks = CheckVerdictSummary(
        items=[
            PRCheckItem(
                name="Unit Tests",
                bucket=CheckBucket.FAIL,
                link="https://github.com/example/project/actions/runs/1/job/2",
            ),
        ],
    )
    client = FakeGitHubClient(
        status=_fake_status(pull),
        checks=test_checks,
        log="FAILED tests/unrelated/test_other.py::test_foo",
    )
    session = FakeGitHubSession(client)

    model_called = False

    def fake_model_runner(*args: Any, **kwargs: Any) -> Any:
        nonlocal model_called
        model_called = True
        raise AssertionError("Model should not be called when outside plan scope")

    report = run_fix_checks(
        store,
        REPO,
        pull,
        session=session,
        tier1_fixer=lambda repo, pull, check, log_text: False,
        model_fixer=fake_model_runner,
        scope_checker=lambda log, num: False,
    )

    assert model_called is False
    assert report.result == FixChecksResult.STOPPED
    assert "outside" in report.reason.lower()


def test_within_plan_scope_runs_model_fix() -> None:
    store = InMemoryRoadmapStore(repo=REPO)
    pull = _seed_item(store)

    test_checks = CheckVerdictSummary(
        items=[
            PRCheckItem(
                name="Unit Tests",
                bucket=CheckBucket.FAIL,
                link="https://github.com/example/project/actions/runs/1/job/2",
            ),
        ],
    )
    client = FakeGitHubClient(
        status=_fake_status(pull),
        checks=test_checks,
        log="FAILED tests/roadmap/test_sample.py::test_bar - AssertionError",
    )
    session = FakeGitHubSession(client)

    model_called = False

    def fake_model_runner(*args: Any, **kwargs: Any) -> bool:
        nonlocal model_called
        model_called = True
        return True

    report = run_fix_checks(
        store,
        REPO,
        pull,
        session=session,
        tier1_fixer=lambda repo, pull, check, log_text: False,
        model_fixer=fake_model_runner,
        scope_checker=lambda log, num: True,
    )

    assert model_called is True
    assert report.result == FixChecksResult.REPAIRED
    updated = store.item(pull)
    assert updated is not None
    assert updated.job_record.get(FixChecksRecordKey.RESULT) == "repaired"


def test_model_fix_failure() -> None:
    store = InMemoryRoadmapStore(repo=REPO)
    pull = _seed_item(store)

    test_checks = CheckVerdictSummary(
        items=[
            PRCheckItem(
                name="Unit Tests",
                bucket=CheckBucket.FAIL,
                link="https://github.com/example/project/actions/runs/1/job/2",
            ),
        ],
    )
    client = FakeGitHubClient(
        status=_fake_status(pull),
        checks=test_checks,
        log="FAILED tests/roadmap/test_sample.py::test_bar - AssertionError",
    )
    session = FakeGitHubSession(client)

    report = run_fix_checks(
        store,
        REPO,
        pull,
        session=session,
        tier1_fixer=lambda repo, pull, check, log_text: False,
        model_fixer=lambda *args: False,
        scope_checker=lambda log, num: True,
    )
    assert report.result == FixChecksResult.FAILED
    assert "model repair failed" in report.reason.lower()


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
    passing_checks = CheckVerdictSummary(
        items=[
            PRCheckItem(
                name="Static Analysis",
                bucket=CheckBucket.PASS,
                link="https://github.com/example/project/actions/runs/1/job/2",
            ),
        ],
    )
    client = FakeGitHubClient(status=_fake_status(pull), checks=passing_checks)
    session = FakeGitHubSession(client)
    report = run_fix_checks(store, REPO, pull, session=session)
    assert report.result == FixChecksResult.SKIPPED
    assert "no failed check" in report.reason.lower()


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
