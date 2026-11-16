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

GitHub's REST API and `gh` are faked at their edges. The repair is given to the step as its
parameter: a checkout that records its push, and fixers that record their calls.
"""

from __future__ import annotations

import json
import subprocess
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest

from devops_cli.exceptions import RoadmapImplementError
from devops_cli.github.client import PullStatus
from devops_cli.roadmap.steps.fix_checks import (
    FixChecksResult,
    Fixed,
    Repair,
    check_scope,
    dry_run_fix_checks,
    run_fix_checks,
)
from devops_cli.roadmap.stores.store import FixChecksRecordKey, ImplementRecordKey
from tests.support.fakes.github import (
    GitHubApiFake,
    github_json,
    route_compare_files,
    route_file,
)
from tests.support.fakes.process import ProcessAnswer, ProcessCall, ProcessFake
from tests.support.fakes.roadmap_store import InMemoryRoadmapStore

pytestmark = pytest.mark.usefixtures("keyring_store")

REPO = "example/project"
BOT_USER = "devops-cli-service[bot]"
HEAD_SHA = "1111111111111111111111111111111111111111"
NEW_HEAD = "2222222222222222222222222222222222222222"
STATIC = "Static Analysis"
PLAN_LOG = "src/devops_cli/sample.py:10: error: undefined name 'foo'"
LINK = f"https://github.com/{REPO}/actions/runs/1/job/2"
NO_LINT = Fixed(done=False, reason="not a lint failure")
DONE = Fixed(done=True)
TICKED = "# Tasks\n\n## 1. Group\n\nChanges: `src/devops_cli/sample.py`.\n\n- [x] 1.1 Do it\n"
# What `uv sync --locked` (uv 0.13) says when `uv.lock` does not match `pyproject.toml`.
LOCK_LOG = (
    "error: The lockfile at `uv.lock` needs to be updated, but `--locked` was provided.\n\n"
    "hint: To update the lockfile, run `uv lock`.\n"
)


def _run(name: str, conclusion: str = "failure") -> dict[str, Any]:
    return {"name": name, "status": "completed", "conclusion": conclusion, "html_url": LINK}


@dataclass
class PullWorld:
    """Pull requests of `REPO` as GitHub and `gh` answer them, and the store of their items."""

    api: GitHubApiFake
    gh: ProcessFake
    store: InMemoryRoadmapStore = field(default_factory=lambda: InMemoryRoadmapStore(repo=REPO))

    def item(self, *labels: str, record: dict[Any, str | None] | None = None) -> int:
        """An item whose number is also the number of its pull request."""
        number = self.store.seed_issue("Sample feature", labels=["priority/p2-medium", *labels])
        if record:
            held = self.store.item(number)
            assert held is not None
            self.store.set_marks(held, record)
        return number

    def pull(
        self,
        number: int,
        *,
        author: str = BOT_USER,
        state: str = "open",
        labels: Sequence[str] = (),
        runs: Sequence[dict[str, Any]] = (),
        log: str = PLAN_LOG,
    ) -> None:
        """Pull request `number` on the branch of item `number`, with its check runs and the log
        of its failed run."""
        status = {
            "state": state,
            "draft": True,
            "head": {"ref": f"feat/{number}-sample", "sha": HEAD_SHA},
            "base": {"ref": "main"},
            "user": {"login": author},
            "labels": [{"name": name} for name in labels],
        }
        self.api.route("GET", f"/repos/{REPO}/pulls/{number}", github_json(status))
        checks = list(runs) or [_run(STATIC)]
        self.api.route(
            "GET",
            f"/repos/{REPO}/commits/{HEAD_SHA}/check-runs?per_page=100",
            github_json({"total_count": len(checks), "check_runs": checks}),
        )
        self.api.route(
            "POST",
            f"/repos/{REPO}/issues/{number}/comments",
            github_json({"id": 1}, status=201),
        )
        self.gh.answer(lambda call: call.argv[1:3] == ("run", "view"), ProcessAnswer(stdout=log))

    def comments(self) -> list[str]:
        return [
            json.loads(request.content)["body"]
            for request in self.api.sent
            if request.method == "POST" and request.url.path.endswith("/comments")
        ]

    def record(self, number: int) -> dict[str, str | None]:
        held = self.store.item(number)
        assert held is not None
        return {key: held.job_record.get(key) for key in FixChecksRecordKey}

    def run(self, number: int, **kwargs: Any) -> Any:
        return run_fix_checks(self.store, REPO, number, **kwargs)


@pytest.fixture
def world(github_api_and_gh: tuple[GitHubApiFake, ProcessFake]) -> PullWorld:
    api, gh = github_api_and_gh
    return PullWorld(api, gh)


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
    model: Fixed = DONE
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


def test_dry_run_sees_zero_requests() -> None:
    reads, writes = dry_run_fix_checks(REPO, 42)
    assert reads == ()
    assert writes == ()


def test_person_pull_request_is_stopped(world: PullWorld) -> None:
    world.pull(42, author="human-dev")

    report = world.run(42)

    assert report.result == FixChecksResult.STOPPED
    assert "bot" in report.reason.lower()


def test_owner_label_stops(world: PullWorld) -> None:
    world.pull(42, labels=["owner/human"])

    report = world.run(42)

    assert report.result == FixChecksResult.STOPPED
    assert "owner" in report.reason.lower()


def test_moved_head_returns_skipped(world: PullWorld) -> None:
    world.pull(42)

    report = world.run(42, head=NEW_HEAD)

    assert report.result == FixChecksResult.SKIPPED
    assert "moved" in report.reason.lower()


def test_the_hard_cap_stops(world: PullWorld) -> None:
    pull = world.item(record={FixChecksRecordKey.ROUNDS: "5"})
    world.pull(pull)

    report = world.run(pull)

    assert report.result == FixChecksResult.STOPPED
    assert "hard cap" in report.reason.lower()


def test_the_soft_cap_stops_without_error_reduction(world: PullWorld) -> None:
    pull = world.item(record={FixChecksRecordKey.ROUNDS: "3", FixChecksRecordKey.ERRORS: "1"})
    world.pull(pull, log="error: one\nerror: two")

    report = world.run(pull)

    assert report.result == FixChecksResult.STOPPED
    assert "soft cap" in report.reason.lower()


def test_the_head_cap_stops(world: PullWorld) -> None:
    pull = world.item(record={FixChecksRecordKey.HEADS: "h1,h2,h3"})
    world.pull(pull)

    report = world.run(pull)

    assert report.result == FixChecksResult.STOPPED
    assert "head" in report.reason.lower()


# ── The guards of #5983 ──────────────────────────────────────────────────────────────────

RUNNER = "devops-cli-runner-example-project-1"


def test_an_item_that_a_live_implement_job_holds_is_skipped(
    world: PullWorld, tmp_path: Path
) -> None:
    """The repair loop of the implement Job owns the failed check while the Job lives (#5983)."""
    pull = world.item(record={ImplementRecordKey.JOB: RUNNER})
    world.pull(pull)
    repair = FakeRepair(tmp_path)

    report = world.run(pull, confirm=True, repair=repair.build())

    assert (report.result, report.reason) == (
        FixChecksResult.SKIPPED,
        f"A runner Job works on it: `{RUNNER}`",
    )
    assert (repair.calls, world.comments()) == ([], [])
    assert set(world.record(pull).values()) == {None}


def test_an_item_whose_implement_job_ended_is_judged(world: PullWorld) -> None:
    """The record keeps `implement.job` after the Job ends; the state of the Job tells it ended."""
    pull = world.item(
        record={ImplementRecordKey.JOB: RUNNER, ImplementRecordKey.JOB_STATE: "failed"}
    )
    world.pull(pull)

    report = world.run(pull)

    assert report.result == FixChecksResult.PLANNED


@pytest.mark.parametrize(
    ("check", "log", "ended"),
    [
        (STATIC, PLAN_LOG, "failed"),
        (STATIC, PLAN_LOG, "stopped"),
        ("Test Job Duration", "Job duration exceeded runner limit", "wait"),
    ],
    ids=["failed", "stopped", "wait"],
)
def test_a_round_that_ended_on_the_same_head_and_check_is_not_repeated(
    world: PullWorld, tmp_path: Path, check: str, log: str, ended: str
) -> None:
    """A second call on the same head and check makes no model request, no checkout, no comment
    and no mark (#5983)."""
    record: dict[Any, str | None] = {
        FixChecksRecordKey.KEY: f"{HEAD_SHA}:{check}",
        FixChecksRecordKey.RESULT: ended,
        FixChecksRecordKey.HEADS: HEAD_SHA,
    }
    pull = world.item(record=record)
    world.pull(pull, runs=[_run(check)], log=log)
    repair = FakeRepair(tmp_path)

    report = world.run(pull, confirm=True, repair=repair.build())

    assert report.result == FixChecksResult.SKIPPED
    assert ended in report.reason
    assert (repair.calls, world.comments()) == ([], [])
    assert world.record(pull) == {**dict.fromkeys(FixChecksRecordKey), **record}


@pytest.mark.parametrize(
    "key", [f"{'0' * 40}:{STATIC}", f"{HEAD_SHA}:Tests & Coverage"], ids=["new-head", "new-check"]
)
def test_a_new_head_or_a_new_failed_check_starts_a_round(
    world: PullWorld, tmp_path: Path, key: str
) -> None:
    pull = world.item(record={FixChecksRecordKey.KEY: key, FixChecksRecordKey.RESULT: "failed"})
    world.pull(pull)
    repair = FakeRepair(tmp_path)

    report = world.run(pull, confirm=True, repair=repair.build())

    assert report.result == FixChecksResult.REPAIRED
    assert "model" in repair.calls
    assert world.record(pull)[FixChecksRecordKey.KEY] == f"{HEAD_SHA}:{STATIC}"


def test_a_lockfile_failure_in_a_check_of_the_class_ci_infra_goes_to_tier1(
    world: PullWorld, tmp_path: Path
) -> None:
    """A stale `uv.lock` fails `uv sync --locked` in every job, also in one whose name the class
    reads as infrastructure. Tier 1 has a fixer for it, so the round does not wait (#5983)."""
    pull = world.item()
    world.pull(pull, runs=[_run("Dependency Freshness")], log=LOCK_LOG)
    repair = FakeRepair(tmp_path, tier1=DONE)

    report = world.run(pull, confirm=True, repair=repair.build())

    assert (report.result, world.comments()) == (FixChecksResult.REPAIRED, [])
    assert repair.calls == [f"checkout feat/{pull}-sample {pull}", "tier1"]


# ── Without --confirm ────────────────────────────────────────────────────────────────────


def test_a_run_without_confirm_plans_the_repair_and_writes_nothing(
    world: PullWorld, tmp_path: Path
) -> None:
    """The case of #5971: a failed `Static Analysis` check whose log names a file of the plan."""
    pull = world.item()
    world.pull(pull)
    repair = FakeRepair(tmp_path)

    report = world.run(pull, repair=repair.build())

    assert (report.result, report.head) == (FixChecksResult.PLANNED, HEAD_SHA)
    assert STATIC in report.reason
    assert (repair.calls, world.comments()) == ([], [])
    assert set(world.record(pull).values()) == {None}


def test_a_ci_infra_failure_without_confirm_posts_no_comment(world: PullWorld) -> None:
    pull = world.item()
    world.pull(pull, runs=[_run("Test Job Duration")], log="Job duration exceeded runner limit")

    report = world.run(pull)

    assert report.result == FixChecksResult.PLANNED
    assert world.comments() == []
    assert set(world.record(pull).values()) == {None}


# ── With --confirm ───────────────────────────────────────────────────────────────────────


def test_ci_infra_failure_posts_comment_and_waits(world: PullWorld) -> None:
    pull = world.item()
    world.pull(pull, runs=[_run("Test Job Duration")], log="Job duration exceeded runner limit")

    report = world.run(pull, confirm=True)

    assert report.result == FixChecksResult.WAIT
    [comment] = world.comments()
    assert "infrastructure" in comment.lower()
    assert world.record(pull)[FixChecksRecordKey.RESULT] == "wait"


def test_a_confirmed_repair_needs_a_repair(world: PullWorld) -> None:
    pull = world.item()
    world.pull(pull)

    with pytest.raises(RoadmapImplementError, match="repair"):
        world.run(pull, confirm=True)


def test_tier1_fixes_lint_with_zero_model_requests(world: PullWorld, tmp_path: Path) -> None:
    pull = world.item()
    world.pull(pull, log="ruff check found 2 errors")
    repair = FakeRepair(tmp_path, tier1=DONE)

    report = world.run(pull, confirm=True, repair=repair.build())

    assert repair.calls == [f"checkout feat/{pull}-sample {pull}", "tier1"]
    assert (report.result, report.head) == (FixChecksResult.REPAIRED, NEW_HEAD)
    assert "0 model requests" in report.reason
    record = world.record(pull)
    assert (record[FixChecksRecordKey.RESULT], record[FixChecksRecordKey.ROUNDS]) == (
        "repaired",
        "1",
    )


def test_outside_plan_scope_stops_with_zero_model_requests(
    world: PullWorld, tmp_path: Path
) -> None:
    pull = world.item()
    world.pull(
        pull, runs=[_run("Unit Tests")], log="FAILED tests/unrelated/test_other.py::test_foo"
    )
    repair = FakeRepair(tmp_path, in_scope=False)

    report = world.run(pull, confirm=True, repair=repair.build())

    assert "model" not in repair.calls
    assert repair.checkout is not None
    assert repair.checkout.pushes == 0
    assert report.result == FixChecksResult.STOPPED
    assert "outside" in report.reason.lower()


def test_a_failed_check_whose_log_names_a_file_of_the_plan_ends_repaired(
    world: PullWorld, tmp_path: Path
) -> None:
    """The case of #5971 with the real scope check: the checkout holds the archived change of the
    item, and the log of the failed `Static Analysis` check names a file that the plan changes."""
    pull = world.item()
    world.pull(pull)
    archived = tmp_path / "openspec" / "changes" / "archive" / f"2026-11-16-{pull}-sample"
    archived.mkdir(parents=True)
    (archived / "tasks.md").write_text(TICKED, encoding="utf-8")
    repair = FakeRepair(tmp_path)
    built = repair.build()
    real_scope = Repair(
        checkout=built.checkout, tier1=built.tier1, model=built.model, scope=check_scope
    )

    report = world.run(pull, confirm=True, repair=real_scope)

    assert (report.result, report.head, report.rounds) == (FixChecksResult.REPAIRED, NEW_HEAD, 1)
    assert repair.calls == [f"checkout feat/{pull}-sample {pull}", "tier1", "model"]
    assert repair.checkout is not None
    assert repair.checkout.pushes == 1
    assert world.record(pull)[FixChecksRecordKey.KEY] == f"{HEAD_SHA}:{STATIC}"


def test_model_fix_failure_names_its_reason(world: PullWorld, tmp_path: Path) -> None:
    pull = world.item()
    world.pull(pull)
    repair = FakeRepair(tmp_path, model=Fixed(done=False, reason="limit reached"))

    report = world.run(pull, confirm=True, repair=repair.build())

    assert report.result == FixChecksResult.FAILED
    assert "model repair failed" in report.reason.lower()
    assert "limit reached" in report.reason
    assert repair.checkout is not None
    assert repair.checkout.pushes == 0
    assert world.record(pull)[FixChecksRecordKey.RESULT] == "failed"


def test_a_repair_that_leaves_the_judged_head_fails(world: PullWorld, tmp_path: Path) -> None:
    pull = world.item()
    world.pull(pull)
    repair = FakeRepair(tmp_path, pushed_head=None)

    report = world.run(pull, confirm=True, repair=repair.build())

    assert report.result == FixChecksResult.FAILED
    assert "no commit" in report.reason.lower()


def test_closed_pull_request_skipped(world: PullWorld) -> None:
    world.pull(42, state="closed")

    report = world.run(42)

    assert report.result == FixChecksResult.SKIPPED
    assert "closed" in report.reason.lower()


def test_passing_checks_skipped(world: PullWorld) -> None:
    pull = world.item()
    world.pull(pull, runs=[_run(STATIC, "success")])

    report = world.run(pull, confirm=True)

    assert report.result == FixChecksResult.SKIPPED
    assert "no failed check" in report.reason.lower()


# ── The ready mark after a repair ────────────────────────────────────────────────────────


def _repaired_draft(world: PullWorld, tasks: str, **record: str) -> int:
    """A draft that the step repaired: its checks pass, and its compare lists the archived change
    of the item, whose `tasks.md` is `tasks`. `record` holds more marks of the step."""
    marks = {FixChecksRecordKey(f"fix_checks.{key}"): value for key, value in record.items()}
    pull = world.item(record={FixChecksRecordKey.RESULT: "repaired", **marks})
    held = world.store.item(pull)
    assert held is not None
    world.store.set_marks(held, {ImplementRecordKey.PR: str(pull)})
    world.pull(pull, runs=[_run(STATIC, "success")])
    path = f"openspec/changes/archive/2026-11-16-{pull}-sample/tasks.md"
    route_compare_files(
        world.api,
        REPO,
        "main",
        HEAD_SHA,
        {"filename": path, "status": "added"},
        merge_base="c" * 40,
    )
    route_file(world.api, REPO, path, HEAD_SHA, tasks)
    return pull


def _ready_calls(world: PullWorld) -> list[tuple[str, ...]]:
    calls: list[tuple[str, ...]] = []

    def ready(call: ProcessCall) -> subprocess.CompletedProcess[str]:
        calls.append(call.argv[1:])
        return subprocess.CompletedProcess(call.argv, 0, stdout="")

    world.gh.answer(
        lambda call: call.argv[1:3] == ("pr", "ready"), ProcessAnswer(side_effect=ready)
    )
    return calls


def test_a_repaired_draft_whose_checks_pass_is_marked_ready(world: PullWorld) -> None:
    pull = _repaired_draft(world, TICKED)
    calls = _ready_calls(world)

    report = world.run(pull, confirm=True)

    assert report.result == FixChecksResult.READY
    assert calls == [("pr", "ready", str(pull), "--repo", REPO)]
    assert world.record(pull)[FixChecksRecordKey.RESULT] == "ready"


def test_a_draft_whose_checks_pass_after_the_third_repair_is_marked_ready(
    world: PullWorld,
) -> None:
    """The third repair pushes the fourth head. The cap of heads stops a repair, not the ready
    mark of a head whose checks pass (#5983)."""
    pull = _repaired_draft(world, TICKED, heads="h1,h2,h3", rounds="3")
    calls = _ready_calls(world)

    report = world.run(pull, confirm=True)

    assert report.result == FixChecksResult.READY
    assert calls == [("pr", "ready", str(pull), "--repo", REPO)]


def test_a_repaired_draft_that_the_readiness_rule_refuses_stays_a_draft(world: PullWorld) -> None:
    pull = _repaired_draft(world, TICKED.replace("- [x]", "- [ ]"))
    calls = _ready_calls(world)

    report = world.run(pull, confirm=True)

    assert report.result == FixChecksResult.SKIPPED
    assert report.reason.startswith("Draft is not ready")
    assert calls == []


def test_a_repaired_draft_without_confirm_is_not_marked_ready(world: PullWorld) -> None:
    pull = _repaired_draft(world, TICKED)
    calls = _ready_calls(world)

    report = world.run(pull)

    assert report.result == FixChecksResult.PLANNED
    assert calls == []
    assert world.record(pull)[FixChecksRecordKey.RESULT] == "repaired"


def test_a_draft_that_the_step_did_not_repair_is_left_to_the_watch_row(world: PullWorld) -> None:
    pull = world.item()
    world.pull(pull, runs=[_run(STATIC, "success")])
    calls = _ready_calls(world)

    report = world.run(pull, confirm=True)

    assert report.result == FixChecksResult.SKIPPED
    assert calls == []


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
