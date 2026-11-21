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
from collections.abc import Sequence
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

import pytest

from devops_cli.exceptions import GitOperationError, RoadmapImplementError
from devops_cli.exceptions.roadmap import PhaseOutputError
from devops_cli.github.client import PullStatus
from devops_cli.github.session import get_github_session
from devops_cli.roadmap.phases.files import RunFolders
from devops_cli.roadmap.phases.publish import Published, PublishTarget
from devops_cli.roadmap.steps.fix_checks import (
    Fixed,
    PullCheckout,
    Repair,
    check_scope,
    dry_run_fix_checks,
    run_fix_checks,
)
from devops_cli.roadmap.steps.fix_checks_cause import FileCause, ScopeVerdict
from devops_cli.roadmap.steps.fix_checks_phases import agent_phase, prepare_phase, publish_phase
from devops_cli.roadmap.stores.store import FixChecksRecordKey, FixChecksResult, ImplementRecordKey
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
OTHER = "tests/unrelated/test_other.py"
NOT_CAUSED = "the change of the branch does not cause its failure"
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
class FakeRepair:
    """The repair of a round, with each call recorded. Its publish calls the claim check and
    gives `pushed_head`: the new head, or None when the patch changes nothing."""

    path: Path
    tier1: Fixed = NO_LINT
    model: Fixed = DONE
    in_scope: bool = True
    caused: tuple[FileCause, ...] = ()
    pushed_head: str | None = NEW_HEAD
    pushed_paths: tuple[str, ...] = ()
    calls: list[str] = field(default_factory=list)
    pushes: int = 0
    extra: list[tuple[str, ...]] = field(default_factory=list)

    def build(self) -> Repair:
        def checkout(status: PullStatus, item: int, work: Path) -> PullCheckout:
            self.calls.append(f"checkout {status.head_ref} {item}")
            return PullCheckout(self.path, "https://github.com/example/project.git", self.path, "b")

        def tier1(path: Path, item: int, check: str, log: str) -> Fixed:
            self.calls.append("tier1")
            return self.tier1

        def model(reader: Any) -> Any:
            def fix(path: Path, item: int, check: str, log: str, extra: tuple[str, ...]) -> Fixed:
                self.calls.append("model")
                self.extra.append(extra)
                return self.model

            return fix

        def scope(path: Path, item: int, log: str, is_stage_plan: bool) -> ScopeVerdict:
            self.calls.append("scope")
            outside = () if self.in_scope else (FileCause(OTHER, NOT_CAUSED),)
            return ScopeVerdict(in_scope=self.in_scope, caused=self.caused, outside=outside)

        def patch(path: Path, base: str, out: Path) -> None:
            out.write_bytes(b"the patch")

        def publish(
            target: PublishTarget, patch: bytes, message: str, before_push: Any
        ) -> Published | None:
            before_push()
            self.pushes += 1
            if self.pushed_head is None:
                return None
            return Published(self.pushed_head, self.pushed_paths)

        return Repair(
            checkout=checkout,
            tier1=tier1,
            model=model,
            patch=patch,
            publish=publish,
            author=lambda: (BOT_USER, "1+bot@users.noreply.github.com"),
            scope=scope,
        )


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


def test_the_service_claim_does_not_stop_the_step(world: PullWorld) -> None:
    """The Service's own `owner/service` claims nothing against its jobs: only `owner/agent`,
    `owner/human` and the rest of the family stop the step (#5027, ADR 0021 section 8)."""
    pull = world.item("owner/service")
    world.pull(pull, labels=["owner/service"])

    report = world.run(pull)

    assert report.result == FixChecksResult.PLANNED


def test_the_named_check_is_the_check_of_the_round(world: PullWorld) -> None:
    """The fix-checks Job names the check of its unit, so the round works on that check and not
    on the first failed check (#5027)."""
    pull = world.item()
    world.pull(pull, runs=[_run(STATIC), _run("Tests & Coverage (shard 1)")])

    named = world.run(pull, check="Tests & Coverage (shard 1)")
    gone = world.run(pull, check="Type Check")

    assert (named.result, "`Tests & Coverage (shard 1)`" in named.reason) == (
        FixChecksResult.PLANNED,
        True,
    )
    assert (gone.result, gone.reason) == (
        FixChecksResult.SKIPPED,
        "Check `Type Check` does not fail on this head",
    )


def _refused_repair(tmp_path: Path) -> Repair:
    """A repair whose push the lease refuses."""

    def refused(target: PublishTarget, patch: bytes, message: str, before_push: Any) -> None:
        before_push()
        raise GitOperationError("git push refused: stale info", operation="roadmap.fix_checks")

    return replace(FakeRepair(tmp_path, tier1=DONE).build(), publish=refused)


def _status(pull: int, head: str) -> dict[str, Any]:
    return {
        "state": "open",
        "draft": True,
        "head": {"ref": f"feat/{pull}-sample", "sha": head},
        "base": {"ref": "main"},
        "user": {"login": BOT_USER},
    }


def test_a_push_that_the_lease_refuses_after_a_move_of_the_head_is_skipped(
    world: PullWorld, tmp_path: Path
) -> None:
    """Another writer moved the head after the judgment: the step records nothing, so no round
    counts as failed, and the new head is a new unit. A refusal on a head that did not move stays
    an error (#5027)."""
    pull = world.item()
    world.pull(pull)
    with pytest.raises(GitOperationError, match="stale info"):
        world.run(pull, confirm=True, repair=_refused_repair(tmp_path))
    world.api.route(
        "GET",
        f"/repos/{REPO}/pulls/{pull}",
        *[github_json(_status(pull, HEAD_SHA))] * 3,
        github_json(_status(pull, NEW_HEAD)),
    )

    report = world.run(pull, confirm=True, repair=_refused_repair(tmp_path))

    assert (report.result, report.reason) == (
        FixChecksResult.SKIPPED,
        "Head has moved: the lease refused the push",
    )
    assert world.record(pull) == dict.fromkeys(FixChecksRecordKey)


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
    assert repair.pushes == 0
    assert report.result == FixChecksResult.STOPPED
    assert report.reason == (f"Failed check log is outside plan scope: `{OTHER}`: {NOT_CAUSED}")
    assert world.comments() == []


def test_a_repair_of_a_file_that_the_change_causes_gives_it_to_the_model_and_names_it(
    world: PullWorld, tmp_path: Path
) -> None:
    """The case of #6114: the failed test is in a file that the plan does not list, and it calls a
    function that the plan changes. The model may change that file, and the comment of the step
    names it with the reason (#6116)."""
    pull = world.item()
    regression = "tests/git/test_review_worktree_regression.py"
    cause = "it uses the changed name `_run_pr_review_workflow`"
    world.pull(pull, runs=[_run("Tests & Coverage (shard 4 of 4)")], log=f"FAILED {regression}")
    repair = FakeRepair(tmp_path, caused=(FileCause(regression, cause),))

    report = world.run(pull, confirm=True, repair=repair.build())

    assert (report.result, report.head) == (FixChecksResult.REPAIRED, NEW_HEAD)
    assert repair.extra == [(regression,)]
    [comment] = world.comments()
    assert f"\n{regression}: {cause}\n" in comment
    assert "Tests & Coverage (shard 4 of 4)" in comment


def test_a_tier1_repair_names_the_files_that_it_wrote_again_in_a_comment(
    world: PullWorld, tmp_path: Path
) -> None:
    """The case of #6041: tier 1 writes the snapshot and the documents again with no model
    request, and the comment names each file (#6116)."""
    pull = world.item()
    written = (
        "docs/MCP_TOOLS.md",
        "tests/ai/mcp/__snapshots__/test_mcp_tool_listing/listing.json",
    )
    world.pull(pull, runs=[_run("Tests & Coverage (shard 3 of 4)")])
    repair = FakeRepair(tmp_path, tier1=Fixed(done=True, files=written), pushed_paths=written)

    report = world.run(pull, confirm=True, repair=repair.build())

    assert report.result == FixChecksResult.REPAIRED
    assert "model" not in repair.calls
    [comment] = world.comments()
    assert all(f"\n{name}\n" in comment for name in written)


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
    real_scope = replace(built, scope=check_scope)

    report = world.run(pull, confirm=True, repair=real_scope)

    assert (report.result, report.head, report.rounds) == (FixChecksResult.REPAIRED, NEW_HEAD, 1)
    assert repair.calls == [f"checkout feat/{pull}-sample {pull}", "tier1", "model"]
    assert repair.pushes == 1
    assert world.record(pull)[FixChecksRecordKey.KEY] == f"{HEAD_SHA}:{STATIC}"


def test_model_fix_failure_names_its_reason(world: PullWorld, tmp_path: Path) -> None:
    pull = world.item()
    world.pull(pull)
    repair = FakeRepair(tmp_path, model=Fixed(done=False, reason="limit reached"))

    report = world.run(pull, confirm=True, repair=repair.build())

    assert report.result == FixChecksResult.FAILED
    assert "model repair failed" in report.reason.lower()
    assert "limit reached" in report.reason
    assert repair.pushes == 0
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


@pytest.mark.parametrize("check", [STATIC, "Test Job Duration"])
def test_the_ready_path_skips_a_check_that_failed_after_the_read_of_the_watch_row(
    world: PullWorld, check: str
) -> None:
    """The watch row read passing checks, and the step reads a failed check: the ready path gives
    `skipped` with no repair, no comment and no ready mark, and the next round judges the head
    (#6018)."""
    pull = world.item(record={FixChecksRecordKey.RESULT: "repaired"})
    world.pull(pull, runs=[_run(check)], log="Job duration exceeded runner limit")
    calls = _ready_calls(world)

    report = world.run(pull, head=HEAD_SHA, confirm=True, ready_only=True)

    assert (report.result, world.comments(), calls) == (FixChecksResult.SKIPPED, [], [])
    assert world.record(pull)[FixChecksRecordKey.RESULT] == "repaired"


def test_an_implement_draft_that_its_job_left_at_the_draft_is_marked_ready(
    world: PullWorld,
) -> None:
    """The implement Job ends at the draft, so the ready path marks a green implement draft ready
    with no repair before it (#6559)."""
    pull = _repaired_draft(world, TICKED)
    held = world.store.item(pull)
    assert held is not None
    world.store.set_marks(
        held, {FixChecksRecordKey.RESULT: None, ImplementRecordKey.RESULT: "drafted"}
    )
    calls = _ready_calls(world)

    report = world.run(pull, head=HEAD_SHA, confirm=True, ready_only=True)

    assert (report.result, calls) == (
        FixChecksResult.READY,
        [("pr", "ready", str(pull), "--repo", REPO)],
    )


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
    assert check_scope(
        tmp_path, 98, "error at openspec/changes/98-test-plan/tasks.md", is_stage_plan=True
    ).in_scope
    assert check_scope(tmp_path, 98, "error at src/other.py", is_stage_plan=True).in_scope is False

    # Archived change with tasks.md
    archive_dir = tmp_path / "openspec" / "changes" / "archive" / "2026-11-16-99-test-plan"
    archive_dir.mkdir(parents=True)
    (archive_dir / "tasks.md").write_text(
        "# Tasks\n\n## 1. Group\nReads: `src/read.py`.\nChanges: `src/mod.py`.\n- [ ] 1.1 Do it\n",
        encoding="utf-8",
    )
    assert (
        check_scope(tmp_path, 99, "FAILED src/mod.py::test", is_stage_plan=False).in_scope is True
    )
    assert check_scope(tmp_path, 99, "FAILED src/other.py", is_stage_plan=False).in_scope is False
    # Missing tasks.md or non-existent change
    assert check_scope(tmp_path, 888, "FAILED src/mod.py", is_stage_plan=False).in_scope is False


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


# ── The phases ────────────────────────────────────────────────────────────────────────────


def _phases(world: PullWorld, pull: int, repair: Repair, folders: RunFolders) -> Any:
    """`prepare`, `agent` and `publish` on the run folder `folders`, one after the other, as
    three containers run them (#6601): the report of `publish`, and the requests of the agent."""
    client = get_github_session().client
    prepare_phase(
        world.store, client, REPO, pull, head=HEAD_SHA, check=None, repair=repair, folders=folders
    )
    before = len(world.api.sent)
    agent_phase(folders, repair)
    agent_requests = len(world.api.sent) - before
    return publish_phase(world.store, client, folders, repair), agent_requests


def test_the_three_phases_on_a_run_folder_repair_as_one_round_does(
    world: PullWorld, tmp_path: Path
) -> None:
    """The phases hand the round on through the run folder: the agent phase makes no GitHub call,
    and `publish` pushes and records the repair as the round of one process does (#6601)."""
    pull = world.item()
    world.pull(pull)
    repair = FakeRepair(tmp_path / "checkout")
    folders = RunFolders(tmp_path / "run")

    report, agent_requests = _phases(world, pull, repair.build(), folders)

    assert (report.result, report.head, agent_requests, repair.pushes) == (
        FixChecksResult.REPAIRED,
        NEW_HEAD,
        0,
        1,
    )
    assert world.record(pull)[FixChecksRecordKey.RESULT] == "repaired"
    state = json.loads((folders.state / "state.json").read_text(encoding="utf-8"))
    assert (state["target"]["lease"], state["target"]["workflow_paths"]) == (HEAD_SHA, [])
    assert not (folders.work / "state.json").exists()


def test_a_round_that_prepare_ends_reaches_publish_as_its_report(
    world: PullWorld, tmp_path: Path
) -> None:
    """A round that ends in `prepare`, here on an owner label, writes no inputs: the agent phase
    does nothing, and `publish` gives the report of `prepare`."""
    pull = world.item("owner/human")
    world.pull(pull)
    repair = FakeRepair(tmp_path / "checkout")
    folders = RunFolders(tmp_path / "run")

    report, _ = _phases(world, pull, repair.build(), folders)

    assert (report.result, report.reason, repair.calls, repair.pushes) == (
        FixChecksResult.STOPPED,
        "Item holds an owner label",
        [],
        0,
    )
    assert list(folders.out.iterdir()) == []


@pytest.mark.parametrize("when", ["publish", "push"])
def test_a_claim_after_the_agent_phase_stops_publish_with_no_push(
    world: PullWorld, tmp_path: Path, when: str
) -> None:
    """The claim check runs in `prepare`, in `publish` and again right before the push: a person
    who claims the item while the agent works, or while `publish` builds the commit, gets no push
    and no record (#3702)."""
    pull = world.item()
    world.pull(pull)
    claimed = {**_status(pull, HEAD_SHA), "labels": [{"name": "owner/human"}]}
    reads = 3 if when == "publish" else 4
    world.api.route(
        "GET",
        f"/repos/{REPO}/pulls/{pull}",
        *[github_json(_status(pull, HEAD_SHA))] * (reads - 2),
        github_json(claimed),
    )
    repair = FakeRepair(tmp_path / "checkout")
    folders = RunFolders(tmp_path / "run")

    report, _ = _phases(world, pull, repair.build(), folders)

    assert (report.result, report.reason, repair.pushes) == (
        FixChecksResult.STOPPED,
        "Item holds an owner label",
        0,
    )
    assert world.record(pull)[FixChecksRecordKey.RESULT] is None


@pytest.mark.parametrize(
    ("outcome", "reason"),
    [
        ('{"kind": "done", "result": "ready", "detail": "tier1"}', "names no result"),
        ('{"kind": "done", "result": "repaired"}', "names no result"),
        (
            '{"kind": "done", "result": "repaired", "detail": "tier1", "author": "mallory"}',
            "not of its model",
        ),
    ],
    ids=["other-result", "no-tier", "other-key"],
)
def test_publish_refuses_an_outcome_outside_the_enums_of_the_step(
    world: PullWorld, tmp_path: Path, outcome: str, reason: str
) -> None:
    """`publish` takes the result and the tier of the outcome from the enums of the step only,
    and no key outside its model (#3702)."""
    pull = world.item()
    world.pull(pull)
    repair = FakeRepair(tmp_path / "checkout")
    folders = RunFolders(tmp_path / "run")
    client = get_github_session().client
    built = repair.build()
    prepare_phase(
        world.store, client, REPO, pull, head=HEAD_SHA, check=None, repair=built, folders=folders
    )
    (folders.out / "outcome.json").write_text(outcome, encoding="utf-8")

    with pytest.raises(PhaseOutputError, match=reason):
        publish_phase(world.store, client, folders, built)

    assert repair.pushes == 0
