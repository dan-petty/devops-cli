"""Tests for `devops roadmap run` and due table execution (#981).

All tests run in-memory without network or cluster access, testing due evaluation,
schedule persistence, clone management, service wiring, and MCP integration. The clone cases run
real `git` against bare remotes in `tmp_path`, with the session's `gh api user` login answered
at the process edge (#1366). The last cases run the GitHub store over `GitHubFake`, a fake at
the `gh` process edge, to count a round's board reads (#1361).
"""

from __future__ import annotations

import json
import logging
import shutil
import subprocess
import time
from collections.abc import Callable, Iterator, Sequence
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from devops_cli.ai.mcp.server import roadmap_run
from devops_cli.commands.roadmap import app as roadmap_app
from devops_cli.commands.serve import app as serve_app
from devops_cli.config.constants import (
    CONST_GH_CLI,
    CONST_ROADMAP_CLOSURE_BATCH_KEYS,
    CONST_ROADMAP_INTAKE_BATCH_KEYS,
    CONST_URL_CLOUDFLARE_STATUS_SUMMARY,
    CONST_URL_GITHUB_STATUS_SUMMARY,
)
from devops_cli.config.defaults import DEFAULT_ROADMAP_METRICS_INTERVAL_MINUTES
from devops_cli.exceptions import GitOperationError, RoadmapRunError
from devops_cli.github.rate_limiter import get_github_rate_limiter
from devops_cli.roadmap.board_read import BOARD_BUDGET_OPERATION, BOARD_ITEMS_OPERATION
from devops_cli.roadmap.github_store import GitHubRoadmapStore
from devops_cli.roadmap.memory_store import InMemoryRoadmapStore
from devops_cli.roadmap.run import (
    DEFAULT_DUE_TABLE,
    JobOutcome,
    JobRow,
    _run_metrics_adapter,
    _run_refine_adapter,
    build_stub_table,
    ensure_checkout,
    run_due_jobs,
    service_job,
)
from devops_cli.roadmap.store import Change, ChangeKind, CloseReason, GitHubState, Release
from devops_cli.server.service import TriggerBatch
from devops_cli.telemetry.instruments import PROJECT_RELEASES_TOTAL
from devops_cli.telemetry.metrics import GLOBAL_METRICS
from tests.roadmap_board_fake import GitHubFake
from tests.web_fakes import StubWeb

REPO = "example/roadmap"
RELEASE = "v0.2.26"
RELEASE_BRANCH = f"release/{RELEASE}"
SESSION_LOGIN_ARGV = [CONST_GH_CLI, "api", "user", "--jq", ".login"]
COMMIT_IDENTITY = ("-c", "user.name=Test", "-c", "user.email=test@example.com")
NOW = datetime(2026, 10, 4, 12, 0, tzinfo=UTC)
runner = CliRunner()


@pytest.fixture
def seeded_store(roadmap_store: InMemoryRoadmapStore) -> InMemoryRoadmapStore:
    """Seeded roadmap store with current release and board configuration."""
    roadmap_store._roadmap.clock = lambda: NOW - timedelta(minutes=10)
    roadmap_store.seed_file(".github/roadmap.toml", "board = 1\n")
    person = roadmap_store.as_actor("alice")
    person.create_release("v0.2.25", state=GitHubState.CLOSED)
    person.create_release(RELEASE)
    person.create_release("v0.2.27")
    return roadmap_store


class StoreSpy:
    """Proxy tracking invocations on a roadmap store."""

    def __init__(self, inner: InMemoryRoadmapStore) -> None:
        self.inner = inner
        self.calls: list[str] = []

    def __getattr__(self, name: str) -> Any:
        attr = getattr(self.inner, name)
        if callable(attr):

            def wrapper(*args: Any, **kwargs: Any) -> Any:
                self.calls.append(name)
                return attr(*args, **kwargs)

            return wrapper
        return attr


def _git(cwd: Path, *args: str) -> str:
    """Run git in `cwd` and return its output; an error fails the test."""
    return subprocess.run(
        ["git", "-C", str(cwd), *args],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _advance_bare_remote(bare: Path, branch: str, *, onto: str = "main") -> str:
    """Commit on top of `onto` in the bare remote, point `branch` at that commit, and return its
    hash."""
    commit = _git(
        bare, *COMMIT_IDENTITY, "commit-tree", f"{onto}^{{tree}}", "-p", onto, "-m", branch
    )
    _git(bare, "update-ref", f"refs/heads/{branch}", commit)
    return commit


def _make_bare_remote(tmp_path: Path, *, with_release_branch: bool = True) -> Path:
    """A bare remote whose HEAD names `main`, with one commit on `main` and, unless told otherwise,
    a later one on release/v0.2.26."""
    bare = tmp_path / "remote.git"
    _git(tmp_path, "init", "--bare", "--initial-branch=main", str(bare))
    empty_tree = subprocess.run(
        ["git", "-C", str(bare), "mktree"], input="", capture_output=True, text=True, check=True
    ).stdout.strip()
    _git(
        bare,
        "update-ref",
        "refs/heads/main",
        _git(bare, *COMMIT_IDENTITY, "commit-tree", empty_tree, "-m", "init"),
    )
    if with_release_branch:
        _advance_bare_remote(bare, RELEASE_BRANCH)
    return bare


def _clone_head(clone_path: Path) -> tuple[str, str]:
    """The clone's HEAD commit and the branch name HEAD points at (`HEAD` when detached)."""
    commit, branch = _git(clone_path, "rev-parse", "HEAD", "--abbrev-ref", "HEAD").splitlines()
    return commit, branch


@pytest.fixture
def release_remote(tmp_path: Path) -> Path:
    """A bare remote holding `main` and a later commit on the current release's branch."""
    return _make_bare_remote(tmp_path)


@pytest.fixture
def main_only_remote(tmp_path: Path) -> Path:
    """A bare remote holding only `main`, as between a ship and the next release's start."""
    return _make_bare_remote(tmp_path, with_release_branch=False)


@pytest.fixture
def dangling_head_remote(release_remote: Path) -> Path:
    """A bare remote whose HEAD names `main`, which it lacks: it holds only the release branch."""
    _git(release_remote, "update-ref", "-d", "refs/heads/main")
    return release_remote


@pytest.fixture
def child_argvs(monkeypatch: pytest.MonkeyPatch) -> Iterator[list[list[str]]]:
    """Run git for real and answer the session's login lookup at the process edge.

    Every child's argv is recorded. `gh api user --jq .login` prints `test-bot`, and any other gh
    command fails the test instead of reaching GitHub. The core quota is seeded, so the lookup sends
    no `gh api rate_limit` first, and a lookup that failed would show as the `devops-cli` fallback.
    """
    get_github_rate_limiter().update_quota(
        "core", remaining=5000, limit=5000, reset_epoch=time.time() + 60.0
    )
    real_run = subprocess.run
    argvs: list[list[str]] = []

    def run(argv: Sequence[str], *args: Any, **kwargs: Any) -> subprocess.CompletedProcess[Any]:
        argvs.append(list(argv))
        if argv[0] != CONST_GH_CLI:
            return real_run(argv, *args, **kwargs)
        if list(argv) != SESSION_LOGIN_ARGV:
            raise AssertionError(f"A clone test ran {argv}, which would reach GitHub")
        return subprocess.CompletedProcess(argv, 0, stdout="test-bot\n", stderr="")

    monkeypatch.setattr(subprocess, "run", run)
    yield argvs


def test_due_table_scenarios(seeded_store: InMemoryRoadmapStore, tmp_path: Path) -> None:
    """Assert ordered tuple of jobs that run across due table conditions."""
    person = seeded_store.as_actor("alice")
    curr_item = person.seed_issue("Current release bug", release=RELEASE, on_board=True)
    other_item = person.seed_issue("Backlog item", release=None, on_board=True)

    def _eval(
        batch: dict[tuple[str, str, str], int] | None = None,
        schedule_init: dict[str, str] | None = None,
        table: Sequence[JobRow] | None = None,
    ) -> tuple[str, ...]:
        sched_file = tmp_path / "roadmap" / "example" / "roadmap" / "schedule.json"
        if schedule_init is not None:
            sched_file.parent.mkdir(parents=True, exist_ok=True)
            sched_file.write_text(json.dumps(schedule_init), encoding="utf-8")
        elif sched_file.exists():
            sched_file.unlink()
        tbl = table if table is not None else build_stub_table()
        return run_due_jobs(
            REPO,
            seeded_store,
            batch=batch,
            table=tbl,
            data_dir=tmp_path,
            now=NOW,
        )

    t59 = (NOW - timedelta(minutes=59)).isoformat()
    t61 = (NOW - timedelta(minutes=61)).isoformat()

    c_59 = _eval(schedule_init={"intake": t59, "close": t59})
    c_61 = _eval(schedule_init={"intake": t61, "close": t59})
    c_no_run = _eval(schedule_init={})

    c_webhook_opened = _eval(
        batch={CONST_ROADMAP_INTAKE_BATCH_KEYS[0]: 1},
        schedule_init={"intake": t59, "close": t59},
    )

    person.close_by_hand(other_item, CloseReason.COMPLETED)
    person.reopen_issue(other_item)
    c_reopened = _eval(
        batch={("poll", "", ""): 1},
        schedule_init={"intake": t59, "close": t59},
    )

    seeded_store._roadmap.changes.clear()
    person.close_issue(curr_item, CloseReason.COMPLETED, "Done")
    c_closed_curr = _eval(
        batch={("poll", "", ""): 1},
        schedule_init={"intake": t59, "close": t59},
    )

    seeded_store._roadmap.changes.clear()
    person.add_label(other_item, "enhancement")
    c_labeled_outside = _eval(
        batch={("poll", "", ""): 1},
        schedule_init={"intake": t59, "close": t59},
    )

    seeded_store._roadmap.changes.clear()
    seeded_store.close_issue(curr_item, CloseReason.COMPLETED, "Done")
    c_store_actor = _eval(
        batch={("poll", "", ""): 1},
        schedule_init={"intake": t59, "close": t59},
    )

    tbl_close_hit = build_stub_table({"close": lambda **_: JobOutcome(closed_items=(curr_item,))})
    tbl_close_miss = build_stub_table({"close": lambda **_: JobOutcome(closed_items=())})
    c_close_hit = _eval(
        batch={CONST_ROADMAP_CLOSURE_BATCH_KEYS[0]: 1},
        schedule_init={"intake": t59, "close": t59},
        table=tbl_close_hit,
    )
    c_close_miss = _eval(
        batch={CONST_ROADMAP_CLOSURE_BATCH_KEYS[0]: 1},
        schedule_init={"intake": t59, "close": t59},
        table=tbl_close_miss,
    )

    tbl_crit = build_stub_table(
        {
            "intake": lambda **_: JobOutcome(placed_critical_or_p0=True),
            "close": lambda **_: JobOutcome(),
            "reprioritize": lambda **_: JobOutcome(),
            "refine": lambda **_: JobOutcome(),
        }
    )
    c_refine_intake = _eval(
        batch={CONST_ROADMAP_INTAKE_BATCH_KEYS[0]: 1},
        schedule_init={"intake": t59, "close": t59},
        table=tbl_crit,
    )

    tbl_reprio = build_stub_table(
        {
            "intake": lambda **_: JobOutcome(),
            "close": lambda **_: JobOutcome(closed_items=(curr_item,)),
            "reprioritize": lambda **_: JobOutcome(),
            "refine": lambda **_: JobOutcome(),
        }
    )
    c_refine_reprio = _eval(
        batch={CONST_ROADMAP_CLOSURE_BATCH_KEYS[0]: 1},
        schedule_init={"intake": t59, "close": t59},
        table=tbl_reprio,
    )

    assert (
        c_59,
        c_61,
        c_no_run,
        c_webhook_opened,
        c_reopened,
        c_closed_curr,
        c_labeled_outside,
        c_store_actor,
        c_close_hit,
        c_close_miss,
        c_refine_intake,
        c_refine_reprio,
    ) == (
        (),
        ("intake",),
        ("intake",),
        ("intake",),
        ("intake",),
        ("reprioritize",),
        (),
        (),
        ("close", "reprioritize"),
        ("close",),
        ("intake", "refine"),
        ("close", "reprioritize", "refine"),
    )


def test_webhook_or_poll_identical_and_oldest_cutoff(
    seeded_store: InMemoryRoadmapStore, tmp_path: Path
) -> None:
    """Webhook and poll batches identify same REOPENED trigger with 1 changes_since call."""
    person = seeded_store.as_actor("alice")
    num = person.seed_issue("Item 1", release=None, on_board=True, state=GitHubState.CLOSED)
    person.reopen_issue(num)

    t30 = (NOW - timedelta(minutes=30)).isoformat()
    t40 = (NOW - timedelta(minutes=40)).isoformat()
    sched = {"intake": t30, "close": t40}

    sched_file = tmp_path / "roadmap" / "example" / "roadmap" / "schedule.json"
    sched_file.parent.mkdir(parents=True, exist_ok=True)
    sched_file.write_text(json.dumps(sched), encoding="utf-8")

    spy_wh = StoreSpy(seeded_store)
    res_wh = run_due_jobs(
        REPO,
        spy_wh,  # type: ignore[arg-type]
        batch={("webhook", "issues", "reopened"): 1},
        table=build_stub_table(),
        data_dir=tmp_path,
        now=NOW,
    )
    calls_wh = spy_wh.calls.count("changes_since")

    sched_file.write_text(json.dumps(sched), encoding="utf-8")
    spy_poll = StoreSpy(seeded_store)
    res_poll = run_due_jobs(
        REPO,
        spy_poll,  # type: ignore[arg-type]
        batch={("poll", "", ""): 1},
        table=build_stub_table(),
        data_dir=tmp_path,
        now=NOW,
    )
    calls_poll = spy_poll.calls.count("changes_since")

    assert (res_wh, calls_wh, res_poll, calls_poll) == (
        ("intake",),
        1,
        ("intake",),
        1,
    )


def test_order_and_cross_job_triggers(seeded_store: InMemoryRoadmapStore, tmp_path: Path) -> None:
    """With 4-job stub table, cross-job outcomes cascade and avoid self-triggering."""
    person = seeded_store.as_actor("alice")
    curr_item = person.seed_issue("Bug", release=RELEASE, on_board=True)

    calls: list[str] = []

    def make_runner(name: str, outcome: JobOutcome) -> Callable[..., JobOutcome]:
        def r(**_: Any) -> JobOutcome:
            calls.append(name)
            return outcome

        return r

    all_stubs = {
        "intake": make_runner("intake", JobOutcome()),
        "close": make_runner("close", JobOutcome()),
        "reprioritize": make_runner("reprioritize", JobOutcome()),
        "refine": make_runner("refine", JobOutcome()),
    }
    table_all = build_stub_table(all_stubs)
    res_all = run_due_jobs(
        REPO,
        seeded_store,
        batch={
            CONST_ROADMAP_INTAKE_BATCH_KEYS[0]: 1,
            CONST_ROADMAP_CLOSURE_BATCH_KEYS[0]: 1,
            ("webhook", "milestones", "opened"): 1,
        },
        table=table_all,
        data_dir=tmp_path,
        now=NOW,
    )

    t59 = (NOW - timedelta(minutes=59)).isoformat()
    sched = {"intake": t59, "close": t59}
    sched_file = tmp_path / "roadmap" / "example" / "roadmap" / "schedule.json"
    sched_file.write_text(json.dumps(sched), encoding="utf-8")

    close_hit_table = build_stub_table(
        {"close": make_runner("close", JobOutcome(closed_items=(curr_item,)))}
    )
    res_close_hit = run_due_jobs(
        REPO,
        seeded_store,
        batch={CONST_ROADMAP_CLOSURE_BATCH_KEYS[0]: 1},
        table=close_hit_table,
        data_dir=tmp_path,
        now=NOW,
    )

    intake_crit_table = build_stub_table(
        {"intake": make_runner("intake", JobOutcome(placed_critical_or_p0=True))},
        include_refine=True,
    )
    res_intake_crit = run_due_jobs(
        REPO,
        seeded_store,
        batch={CONST_ROADMAP_INTAKE_BATCH_KEYS[0]: 1},
        table=intake_crit_table,
        data_dir=tmp_path,
        now=NOW,
    )

    reprio_write_table = build_stub_table(
        {
            "reprioritize": make_runner(
                "reprioritize",
                JobOutcome(
                    changes=(
                        Change(
                            kind=ChangeKind.CLOSED,
                            number=curr_item,
                            actor=seeded_store._actor,
                            at=NOW,
                        ),
                    )
                ),
            )
        }
    )
    sched_file.write_text(json.dumps(sched), encoding="utf-8")
    person.close_issue(curr_item, CloseReason.COMPLETED, "Done")
    run_due_jobs(
        REPO,
        seeded_store,
        batch={("poll", "", ""): 1},
        table=reprio_write_table,
        data_dir=tmp_path,
        now=NOW,
    )
    seeded_store._roadmap.changes = [
        Change(
            kind=ChangeKind.CLOSED,
            number=curr_item,
            actor=seeded_store._actor,
            at=NOW,
            release=RELEASE,
        )
    ]
    res_second_call = run_due_jobs(
        REPO,
        seeded_store,
        batch={("poll", "", ""): 1},
        table=reprio_write_table,
        data_dir=tmp_path,
        now=NOW,
    )

    assert (
        res_all,
        res_close_hit,
        res_intake_crit,
        res_second_call,
    ) == (
        ("intake", "close", "reprioritize", "refine"),
        ("close", "reprioritize"),
        ("intake", "refine"),
        (),
    )


def test_failure_isolation_and_cli_exit(
    seeded_store: InMemoryRoadmapStore, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Failed stub allows subsequent jobs to run, preserves schedule cutoff, and CLI exits 1."""
    monkeypatch.setenv("DEVOPS_CLI_DATA_DIR", str(tmp_path))
    person = seeded_store.as_actor("alice")
    person.seed_issue("Item 1", release=RELEASE, on_board=True)

    ran_jobs: list[str] = []

    def failing_intake(**_: Any) -> JobOutcome:
        ran_jobs.append("intake")
        raise RuntimeError("Intake failed")

    def ok_reprio(**_: Any) -> JobOutcome:
        ran_jobs.append("reprioritize")
        return JobOutcome()

    table = build_stub_table({"intake": failing_intake, "reprioritize": ok_reprio})

    with pytest.raises(RoadmapRunError) as exc_info:
        run_due_jobs(
            REPO,
            seeded_store,
            batch={
                CONST_ROADMAP_INTAKE_BATCH_KEYS[0]: 1,
                ("webhook", "milestones", "opened"): 1,
            },
            table=table,
            data_dir=tmp_path,
            now=NOW,
        )

    sched_file = tmp_path / "roadmap" / "example" / "roadmap" / "schedule.json"
    sched_data = json.loads(sched_file.read_text(encoding="utf-8"))

    with pytest.raises(RoadmapRunError):
        run_due_jobs(
            REPO,
            seeded_store,
            batch={
                CONST_ROADMAP_INTAKE_BATCH_KEYS[0]: 1,
                ("webhook", "milestones", "opened"): 1,
            },
            table=table,
            data_dir=tmp_path,
            now=NOW,
        )

    def failing_adapter(*_: Any, **__: Any) -> JobOutcome:
        raise RoadmapRunError("Crash", failed_jobs=("intake",))

    with patch("devops_cli.roadmap.run.run_due_jobs", side_effect=failing_adapter):
        res = runner.invoke(roadmap_app, ["run", "--confirm", "-R", REPO])

    assert (
        exc_info.value.failed_jobs,
        tuple(ran_jobs[:2]),
        "intake" not in sched_data,
        "reprioritize" in sched_data,
        res.exit_code,
        "intake" in res.output,
    ) == (
        ("intake",),
        ("intake", "reprioritize"),
        True,
        True,
        1,
        True,
    )


def test_state_file_persistence(seeded_store: InMemoryRoadmapStore, tmp_path: Path) -> None:
    """Schedule records success time; subsequent run 30m later sees intake not due."""
    tbl = build_stub_table({"intake": lambda **_: JobOutcome()})
    run_due_jobs(
        REPO,
        seeded_store,
        batch={CONST_ROADMAP_INTAKE_BATCH_KEYS[0]: 1},
        table=tbl,
        data_dir=tmp_path,
        now=NOW,
    )

    sched_file = tmp_path / "roadmap" / "example" / "roadmap" / "schedule.json"
    data = json.loads(sched_file.read_text(encoding="utf-8"))

    t30 = NOW + timedelta(minutes=30)
    second_due = run_due_jobs(
        REPO,
        seeded_store,
        batch={},
        table=tbl,
        data_dir=tmp_path,
        now=t30,
    )

    assert ("intake" in data, second_due) == (True, ())


def test_release_read_failure_propagates_closed(
    seeded_store: InMemoryRoadmapStore, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A failure reading releases from the store propagates rather than being swallowed as None."""

    def broken_releases() -> tuple[Any, ...]:
        raise RuntimeError("GitHub API timeout during releases read")

    monkeypatch.setattr(seeded_store, "releases", broken_releases)
    tbl = build_stub_table({"intake": lambda **_: JobOutcome()})
    with pytest.raises(RuntimeError, match="GitHub API timeout during releases read"):
        run_due_jobs(
            REPO,
            seeded_store,
            batch={("webhook", "issues", "opened"): 1},
            table=tbl,
            data_dir=tmp_path,
            now=NOW,
        )


def _current_release(store: InMemoryRoadmapStore) -> Release:
    """The seeded store's current release, v0.2.26."""
    return next(r for r in store.releases() if r.title == RELEASE)


def test_checkouts_git_management(
    seeded_store: InMemoryRoadmapStore,
    tmp_path: Path,
    release_remote: Path,
    child_argvs: list[list[str]],
) -> None:
    """Clones to expected path, tracks remote tip, sets identity, fails clone-dependent jobs:
    close, refine and metrics, which walks the clone's release tags (#1358)."""
    bare = release_remote
    data_dir = tmp_path / "data"

    cur = _current_release(seeded_store)
    clone_path = ensure_checkout(REPO, data_dir, remote_url=str(bare), current_rel=cur)

    expected_clone = data_dir / "roadmap" / "example" / "roadmap" / "clone"
    user_name = _git(clone_path, "config", "user.name")
    user_email = _git(clone_path, "config", "user.email")

    new_rev = _advance_bare_remote(bare, RELEASE_BRANCH, onto=RELEASE_BRANCH)
    ensure_checkout(REPO, data_dir, remote_url=str(bare), current_rel=cur)
    head = _clone_head(clone_path)

    shutil.rmtree(bare)
    shutil.rmtree(clone_path)

    ran_intake = False
    ran_reprio = False
    called_close = False
    called_refine = False
    called_metrics = False

    def stub_intake(**_: Any) -> JobOutcome:
        nonlocal ran_intake
        ran_intake = True
        return JobOutcome()

    def stub_reprio(**_: Any) -> JobOutcome:
        nonlocal ran_reprio
        ran_reprio = True
        return JobOutcome()

    def stub_close(**_: Any) -> JobOutcome:
        nonlocal called_close
        called_close = True
        return JobOutcome()

    def stub_refine(**_: Any) -> JobOutcome:
        nonlocal called_refine
        called_refine = True
        return JobOutcome()

    def stub_metrics(**_: Any) -> JobOutcome:
        nonlocal called_metrics
        called_metrics = True
        return JobOutcome()

    fail_table = build_stub_table(
        {
            "intake": stub_intake,
            "close": stub_close,
            "reprioritize": stub_reprio,
            "refine": stub_refine,
            "metrics": stub_metrics,
        },
        needs_clone=True,
    )

    with pytest.raises(RoadmapRunError) as exc_info:
        run_due_jobs(
            REPO,
            seeded_store,
            batch={
                CONST_ROADMAP_INTAKE_BATCH_KEYS[0]: 1,
                CONST_ROADMAP_CLOSURE_BATCH_KEYS[0]: 1,
                ("webhook", "milestones", "opened"): 1,
            },
            table=fail_table,
            data_dir=data_dir,
            remote_url=str(bare),
            now=NOW,
        )

    assert (
        clone_path == expected_clone,
        user_name,
        user_email,
        head,
        ran_intake,
        ran_reprio,
        called_close,
        called_refine,
        called_metrics,
        exc_info.value.failed_jobs,
    ) == (
        True,
        "test-bot",
        "test-bot@users.noreply.github.com",
        (new_rev, RELEASE_BRANCH),
        True,
        True,
        False,
        False,
        False,
        ("close", "refine", "metrics"),
    )


def _checkout_info_lines(caplog: pytest.LogCaptureFixture) -> list[str]:
    """The INFO lines the checkout logged."""
    return [
        record.getMessage()
        for record in caplog.records
        if record.name == "devops_cli.roadmap.run" and record.levelno == logging.INFO
    ]


def test_checkout_tracks_the_default_branch_until_the_release_branch_exists(
    seeded_store: InMemoryRoadmapStore,
    tmp_path: Path,
    main_only_remote: Path,
    child_argvs: list[list[str]],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A current release with no branch on origin gets `main` and one INFO line; once origin has
    the release branch, the next checkout tracks it (#1366)."""
    data_dir = tmp_path / "data"
    cur = _current_release(seeded_store)
    main_tip = _git(main_only_remote, "rev-parse", "main")

    with caplog.at_level(logging.INFO, logger="devops_cli.roadmap.run"):
        clone_path = ensure_checkout(
            REPO, data_dir, remote_url=str(main_only_remote), current_rel=cur
        )
        before_branch = _clone_head(clone_path)
        release_tip = _advance_bare_remote(main_only_remote, RELEASE_BRANCH)
        ensure_checkout(REPO, data_dir, remote_url=str(main_only_remote), current_rel=cur)

    names_release_and_default = [
        all(name in line for name in (REPO, RELEASE, "main"))
        for line in _checkout_info_lines(caplog)
    ]
    assert (
        before_branch,
        _clone_head(clone_path),
        names_release_and_default,
        _git(clone_path, "config", "user.name"),
    ) == ((main_tip, "main"), (release_tip, RELEASE_BRANCH), [True], "test-bot")


def test_checkout_returns_to_the_default_branch_when_origin_deletes_the_release_branch(
    seeded_store: InMemoryRoadmapStore,
    tmp_path: Path,
    release_remote: Path,
    child_argvs: list[list[str]],
) -> None:
    """A ship deletes the release branch while its release is still current: the pruning fetch
    drops the stale remote-tracking ref and the clone tracks `main` (#1366)."""
    data_dir = tmp_path / "data"
    cur = _current_release(seeded_store)
    main_tip, release_tip = _git(release_remote, "rev-parse", "main", RELEASE_BRANCH).splitlines()

    clone_path = ensure_checkout(REPO, data_dir, remote_url=str(release_remote), current_rel=cur)
    on_release = _clone_head(clone_path)
    _git(release_remote, "update-ref", "-d", f"refs/heads/{RELEASE_BRANCH}")
    ensure_checkout(REPO, data_dir, remote_url=str(release_remote), current_rel=cur)
    stale_ref = subprocess.run(
        ["git", "rev-parse", "--verify", "--quiet", f"refs/remotes/origin/{RELEASE_BRANCH}"],
        cwd=clone_path,
        capture_output=True,
        check=False,
    )

    assert (on_release, _clone_head(clone_path), stale_ref.returncode) == (
        (release_tip, RELEASE_BRANCH),
        (main_tip, "main"),
        1,
    )


def test_checkout_follows_the_default_branch_while_no_release_is_open(
    tmp_path: Path,
    main_only_remote: Path,
    child_argvs: list[list[str]],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """With no open release the clone tracks `main` as it moves, and logs nothing (#1366)."""
    data_dir = tmp_path / "data"
    first_tip = _git(main_only_remote, "rev-parse", "main")

    with caplog.at_level(logging.INFO, logger="devops_cli.roadmap.run"):
        clone_path = ensure_checkout(REPO, data_dir, remote_url=str(main_only_remote))
        first = _clone_head(clone_path)
        new_tip = _advance_bare_remote(main_only_remote, "main")
        ensure_checkout(REPO, data_dir, remote_url=str(main_only_remote))

    assert (first, _clone_head(clone_path), _checkout_info_lines(caplog)) == (
        (first_tip, "main"),
        (new_tip, "main"),
        [],
    )


def test_checkout_raises_when_the_fetch_fails_and_keeps_the_branch_it_had(
    seeded_store: InMemoryRoadmapStore,
    tmp_path: Path,
    release_remote: Path,
    child_argvs: list[list[str]],
) -> None:
    """An unreachable origin raises GitOperationError with git's reason; the clone does not fall
    back to the default branch (#1366)."""
    data_dir = tmp_path / "data"
    cur = _current_release(seeded_store)
    clone_path = ensure_checkout(REPO, data_dir, remote_url=str(release_remote), current_rel=cur)
    on_release = _clone_head(clone_path)
    shutil.rmtree(release_remote)

    with pytest.raises(GitOperationError) as raised:
        ensure_checkout(REPO, data_dir, remote_url=str(release_remote), current_rel=cur)

    message = str(raised.value)
    assert (
        "git fetch --prune origin failed" in message,
        "does not appear to be a git repository" in message,
        _clone_head(clone_path),
    ) == (True, True, on_release)


def _commit_file(bare: Path, branch: str, content: str, *, parent: str | None = None) -> str:
    """Point `branch` in the bare remote at a commit whose tree holds one file, `f.txt`, with
    `content`, and return the commit's hash."""
    blob = subprocess.run(
        ["git", "-C", str(bare), "hash-object", "-w", "--stdin"],
        input=content,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    tree = subprocess.run(
        ["git", "-C", str(bare), "mktree"],
        input=f"100644 blob {blob}\tf.txt\n",
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    parents = ("-p", parent) if parent else ()
    commit = _git(bare, *COMMIT_IDENTITY, "commit-tree", tree, *parents, "-m", branch)
    _git(bare, "update-ref", f"refs/heads/{branch}", commit)
    return commit


def test_checkout_discards_a_tracked_change_a_failed_job_left_in_the_clone(
    seeded_store: InMemoryRoadmapStore,
    tmp_path: Path,
    child_argvs: list[list[str]],
) -> None:
    """A cut that fails after writing its files leaves a tracked change in the clone. The next
    checkout still moves to origin's tip and drops the change, instead of failing every later
    round until a person cleans the clone (#1366)."""
    bare = tmp_path / "remote.git"
    _git(tmp_path, "init", "--bare", "--initial-branch=main", str(bare))
    main_tip = _commit_file(bare, "main", "main\n")
    _commit_file(bare, RELEASE_BRANCH, "release\n", parent=main_tip)
    data_dir = tmp_path / "data"
    cur = _current_release(seeded_store)
    clone_path = ensure_checkout(REPO, data_dir, remote_url=str(bare), current_rel=cur)
    (clone_path / "f.txt").write_text("left by a failed cut\n")
    _git(bare, "update-ref", "-d", f"refs/heads/{RELEASE_BRANCH}")

    ensure_checkout(REPO, data_dir, remote_url=str(bare), current_rel=cur)

    assert (
        _clone_head(clone_path),
        (clone_path / "f.txt").read_text(),
        _git(clone_path, "status", "--porcelain"),
    ) == ((main_tip, "main"), "main\n", "")


def test_checkout_raises_when_origin_head_names_no_branch(
    seeded_store: InMemoryRoadmapStore,
    tmp_path: Path,
    dangling_head_remote: Path,
    child_argvs: list[list[str]],
) -> None:
    """A remote whose HEAD names a branch it lacks has no default branch to fall back to, so the
    checkout raises GitOperationError with git's reason instead of guessing one (#1366)."""
    with pytest.raises(GitOperationError) as raised:
        ensure_checkout(
            REPO,
            tmp_path / "data",
            remote_url=str(dangling_head_remote),
            current_rel=_current_release(seeded_store),
        )

    message = str(raised.value)
    assert (
        "git remote set-head origin --auto failed" in message,
        "Cannot determine remote HEAD" in message,
    ) == (True, True)


def test_a_round_after_a_ship_runs_its_clone_jobs_on_the_default_branch(
    seeded_store: InMemoryRoadmapStore,
    tmp_path: Path,
    main_only_remote: Path,
    child_argvs: list[list[str]],
) -> None:
    """The round that sees a ship runs close before reprioritize starts the release, so the
    release has no branch yet: close and refine share one clone on `main`, and nothing fails.
    The dry run of the same round starts no git command (#1366)."""
    data_dir = tmp_path / "data"
    main_tip = _git(main_only_remote, "rev-parse", "main")
    seen: dict[str, tuple[Path | None, tuple[str, str]]] = {}

    def record(job: str) -> Callable[..., JobOutcome]:
        def run_job(*, clone_path: Path | None = None, **_: Any) -> JobOutcome:
            assert clone_path is not None
            seen[job] = (clone_path, _clone_head(clone_path))
            return JobOutcome()

        return run_job

    def start_release(**_: Any) -> JobOutcome:
        _git(main_only_remote, "update-ref", f"refs/heads/{RELEASE_BRANCH}", "main")
        return JobOutcome()

    table = build_stub_table(
        {"close": record("close"), "reprioritize": start_release, "refine": record("refine")},
        needs_clone=True,
    )
    ship_batch = {("webhook", "pull_request", "closed"): 1, ("webhook", "milestone", "closed"): 1}

    def run_round(*, dry_run: bool) -> tuple[str, ...]:
        return run_due_jobs(
            REPO,
            seeded_store,
            batch=ship_batch,
            table=table,
            data_dir=data_dir,
            remote_url=str(main_only_remote),
            dry_run=dry_run,
            now=NOW,
        )

    before_dry_run = len(child_argvs)
    planned = run_round(dry_run=True)
    dry_run_git = [argv for argv in child_argvs[before_dry_run:] if argv[0] == "git"]
    ran = run_round(dry_run=False)

    clone = data_dir / "roadmap" / "example" / "roadmap" / "clone"
    assert (planned, dry_run_git, ran, seen) == (
        ("intake", "close", "reprioritize", "refine"),
        [],
        ("intake", "close", "reprioritize", "refine"),
        {"close": (clone, (main_tip, "main")), "refine": (clone, (main_tip, "main"))},
    )


def test_idle_records_zero_or_one_store_calls(
    seeded_store: InMemoryRoadmapStore, tmp_path: Path
) -> None:
    """Empty batch records 0 store calls; empty poll records exactly 1 changes_since call."""
    t30 = (NOW - timedelta(minutes=30)).isoformat()
    t5 = (NOW - timedelta(minutes=5)).isoformat()
    sched = {"intake": t30, "close": t30, "metrics": t5}
    sched_file = tmp_path / "roadmap" / "example" / "roadmap" / "schedule.json"
    sched_file.parent.mkdir(parents=True, exist_ok=True)
    sched_file.write_text(json.dumps(sched), encoding="utf-8")

    spy_idle = StoreSpy(seeded_store)
    res_idle = run_due_jobs(REPO, spy_idle, batch={}, data_dir=tmp_path, now=NOW)  # type: ignore[arg-type]

    spy_poll = StoreSpy(seeded_store)
    res_poll = run_due_jobs(
        REPO,
        spy_poll,  # type: ignore[arg-type]
        batch={("poll", "", ""): 1},
        data_dir=tmp_path,
        now=NOW,
    )

    assert (res_idle, len(spy_idle.calls), res_poll, spy_poll.calls) == (
        (),
        0,
        (),
        ["changes_since"],
    )


def test_no_prompt_and_cli_modes(
    seeded_store: InMemoryRoadmapStore, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Stub called with no confirm argument; CLI without confirm or with dry-run runs none."""
    monkeypatch.setenv("DEVOPS_CLI_DATA_DIR", str(tmp_path))
    received_args: list[dict[str, Any]] = []

    def stub_runner(**kwargs: Any) -> JobOutcome:
        received_args.append(kwargs)
        return JobOutcome()

    tbl = build_stub_table({"intake": stub_runner})
    run_due_jobs(
        REPO,
        seeded_store,
        batch={CONST_ROADMAP_INTAKE_BATCH_KEYS[0]: 1},
        table=tbl,
        data_dir=tmp_path,
        now=NOW,
    )
    had_confirm = "confirm" in received_args[0] if received_args else True

    with patch("devops_cli.roadmap.run.DEFAULT_DUE_TABLE", tbl):
        res_plain = runner.invoke(roadmap_app, ["run", "-R", REPO])
        res_dry = runner.invoke(roadmap_app, ["run", "--dry-run", "--confirm", "-R", REPO])
        received_args.clear()
        res_confirm = runner.invoke(roadmap_app, ["run", "--confirm", "-R", REPO])
        confirm_called = len(received_args) > 0

    assert (
        had_confirm,
        res_plain.exit_code,
        "Due:" in res_plain.output,
        res_dry.exit_code,
        "Due:" in res_dry.output,
        res_confirm.exit_code,
        confirm_called,
    ) == (
        False,
        0,
        True,
        0,
        True,
        0,
        True,
    )


def test_service_wiring(
    seeded_store: InMemoryRoadmapStore,
    roadmap_store_repos: list[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`devops serve --service` passes service_job to create_service_app and opens store."""
    monkeypatch.setenv("DEVOPS_CLI_SERVICE_REPOS", f'["{REPO}"]')
    monkeypatch.setenv("DEVOPS_CLI_SERVICE_MACHINE_ACCOUNT", "devops-cli")
    monkeypatch.setenv("DEVOPS_CLI_SERVICE_WEBHOOK_SECRETS", f'{{"{REPO}":"secret-1"}}')

    with patch("uvicorn.run") as mock_uvicorn:
        res = runner.invoke(serve_app, ["--service"])
        fastapi_app = mock_uvicorn.call_args[0][0]

    batch = TriggerBatch(
        repo=REPO,
        counts={CONST_ROADMAP_INTAKE_BATCH_KEYS[0]: 1},
        first_at=NOW,
        last_at=NOW,
    )
    with patch("devops_cli.roadmap.run.run_due_jobs") as mock_run:
        service_job(REPO, batch)

    assert (
        res.exit_code,
        fastapi_app.state.job is service_job,
        REPO in roadmap_store_repos,
        mock_run.called,
    ) == (
        0,
        True,
        True,
        True,
    )


def test_mcp_mirror_roadmap_run(seeded_store: InMemoryRoadmapStore) -> None:
    """FastMCP roadmap_run returns due tuple, mutates nothing, and calls no stub."""
    from devops_cli.ai.mcp import server as mcp_server

    items_before = [it.model_dump() for it in seeded_store.items()]
    cards_before = [c.model_dump() for c in seeded_store.cards()]
    comments_before = {
        it.number: list(seeded_store.comments_on(it.number)) for it in seeded_store.items()
    }

    def in_process(cmd: list[str], **_: object) -> str:
        return runner.invoke(roadmap_app, cmd[4:]).output

    with patch.object(mcp_server, "_run_mcp_cmd", side_effect=in_process):
        due = roadmap_run(repo=REPO)

    items_after = [it.model_dump() for it in seeded_store.items()]
    cards_after = [c.model_dump() for c in seeded_store.cards()]
    comments_after = {
        it.number: list(seeded_store.comments_on(it.number)) for it in seeded_store.items()
    }

    assert (
        isinstance(due, tuple),
        items_before == items_after,
        cards_before == cards_after,
        comments_before == comments_after,
    ) == (
        True,
        True,
        True,
        True,
    )


def test_ensure_checkout_rejects_path_escape_and_malformed_repo_slugs(tmp_path: Path) -> None:
    """Test that ensure_checkout strictly validates repo slugs and prevents path traversal escapes."""
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    escapes = [
        "owner//tmp",
        "/tmp/repo",
        "owner/../etc",
        "owner/name/extra",
        "single_slug",
        "owner/",
        "/name",
    ]
    results: list[bool] = []
    for malformed in escapes:
        with pytest.raises(GitOperationError):
            ensure_checkout(malformed, data_dir)
        results.append(True)

    assert (len(results), all(results)) == (len(escapes), True)


STATUS_PAGE = {
    "page": {"id": "page", "name": "Status", "url": "https://example.com"},
    "status": {"indicator": "none", "description": "All Systems Operational"},
}


def test_the_metrics_job_walks_the_release_tags_of_its_own_clone(
    seeded_store: InMemoryRoadmapStore,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    stub_web: StubWeb,
    git: Callable[..., None],
) -> None:
    """The default table's metrics row clones the repository and walks its release tags there,
    not in the working directory, which in the Service is no git repository (#1358). The gauge
    reads the remote's two tags, and the job logs no warning, so every GitHub and status read it
    made was answered."""
    row = next(row for row in DEFAULT_DUE_TABLE if row.name == "metrics")
    remote = _make_bare_remote(tmp_path)
    for tag in ("v0.1.0", "v0.2.0"):
        git(remote, "tag", tag, f"release/{RELEASE}")
    github = GitHubFake(REPO, milestones=[{"number": 26, "title": RELEASE, "state": "open"}])
    monkeypatch.setattr(subprocess, "run", github.process(subprocess.run))
    for url in (CONST_URL_GITHUB_STATUS_SUMMARY, CONST_URL_CLOUDFLARE_STATUS_SUMMARY):
        stub_web.page(url, json.dumps(STATUS_PAGE))
    GLOBAL_METRICS.clear_metric(PROJECT_RELEASES_TOTAL.name)
    data_dir = tmp_path / "data"
    with caplog.at_level(logging.WARNING):
        ran = run_due_jobs(
            REPO, seeded_store, table=(row,), data_dir=data_dir, remote_url=str(remote), now=NOW
        )
    clone = data_dir / "roadmap" / "example" / "roadmap" / "clone"
    assert (
        (row.needs_clone, row.first_run_due, row.interval),
        ran,
        (clone / ".git").is_dir(),
        GLOBAL_METRICS.get_gauge(PROJECT_RELEASES_TOTAL.name),
        [record.getMessage() for record in caplog.records if record.levelno >= logging.WARNING],
    ) == (
        (True, True, timedelta(minutes=DEFAULT_ROADMAP_METRICS_INTERVAL_MINUTES)),
        ("metrics",),
        True,
        2.0,
        [],
    )


def test_a_failed_metrics_collection_or_status_read_is_logged_and_the_job_goes_on(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    stub_web: StubWeb,
    git: Callable[..., None],
) -> None:
    """GitHub answers a milestone the report can't count, and neither status page answers:
    each failure is a WARNING from the job, which still returns its outcome."""
    clone = tmp_path / "clone"
    clone.mkdir()
    git(clone, "init", "--quiet")
    milestone = {"number": 26, "title": RELEASE, "state": "open", "open_issues": None}
    monkeypatch.setattr(
        subprocess, "run", GitHubFake(REPO, milestones=[milestone]).process(subprocess.run)
    )
    with caplog.at_level(logging.WARNING):
        outcome = _run_metrics_adapter(repo=REPO, clone_path=clone)
    job = [r.getMessage() for r in caplog.records if r.name == "devops_cli.roadmap.run"]
    status_pages = {CONST_URL_GITHUB_STATUS_SUMMARY, CONST_URL_CLOUDFLARE_STATUS_SUMMARY}
    assert (
        outcome,
        [message.partition(":")[0] for message in job],
        status_pages <= set(stub_web.requested),
    ) == (
        JobOutcome(),
        [
            f"Project metrics collection failed for {REPO}",
            "GitHub service status collection failed",
            "Cloudflare service status collection failed",
        ],
        True,
    )


@pytest.mark.parametrize(
    ("job", "runner"), [("metrics", _run_metrics_adapter), ("refine", _run_refine_adapter)]
)
def test_a_job_that_reads_the_clone_fails_without_one_rather_than_reading_the_cwd(
    seeded_store: InMemoryRoadmapStore, job: str, runner: Callable[..., JobOutcome]
) -> None:
    """A row that runs metrics or refine without `needs_clone` is a table error, not a run
    over the working directory, which in the Service is no git repository (#1358)."""
    with pytest.raises(GitOperationError) as raised:
        runner(store=seeded_store, repo=REPO, clone_path=None)
    assert (f"roadmap {job} job" in str(raised.value), "needs_clone" in str(raised.value)) == (
        True,
        True,
    )


# ── On the GitHub store, at the `gh` process edge (#1361) ─────────────────────


def _labeled(count: int, actor: str) -> list[dict[str, Any]]:
    """`count` label events by `actor` on issues #1.., newest first, in no milestone."""
    return [
        {
            "event": "labeled",
            "created_at": (NOW - timedelta(seconds=10 + n)).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "actor": {"login": actor},
            "issue": {"number": n + 1, "milestone": None},
            "label": {"name": "scope/cli"},
        }
        for n in range(count)
    ]


def _github_round(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, events: list[dict[str, Any]]
) -> tuple[GitHubFake, GitHubRoadmapStore]:
    """A repository with 60 cards and a current release, its jobs all run five minutes ago, the
    Service logged in as `roadmap-bot`, and the store a round opens over it."""
    github = GitHubFake(
        REPO,
        milestones=[
            {"number": 25, "title": "v0.2.25", "state": "closed"},
            {"number": 26, "title": RELEASE, "state": "open"},
        ],
        events=events,
    )
    for number in range(1, 61):
        github.seed_issue(number, card={"status": "Ready"})
    t5 = (NOW - timedelta(minutes=5)).isoformat()
    sched_file = tmp_path / "roadmap" / "example" / "roadmap" / "schedule.json"
    sched_file.parent.mkdir(parents=True, exist_ok=True)
    sched_file.write_text(
        json.dumps({"intake": t5, "close": t5, "reprioritize": t5}), encoding="utf-8"
    )
    monkeypatch.setattr("devops_cli.roadmap.run._get_session_login", lambda: "roadmap-bot")
    store = GitHubRoadmapStore(REPO, board_owner="example", board_number=1, runner=github)
    return github, store


def test_a_round_judging_50_foreign_label_changes_reads_the_board_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """None of the changes is in the current release, so reprioritize's trigger looks up every
    one of the 50 Items: all of them, and the job records the changes carry, come from the one
    listing the round's store reads."""
    github, store = _github_round(tmp_path, monkeypatch, _labeled(50, "alice"))
    ran = run_due_jobs(
        REPO,
        store,
        batch={("poll", "", ""): 1},
        table=build_stub_table(),
        data_dir=tmp_path,
        now=NOW,
    )
    sent = [" ".join(args) for args in github.graphql_calls()]
    assert (
        ran,
        sum(BOARD_BUDGET_OPERATION in args for args in sent),
        sum(BOARD_ITEMS_OPERATION in args for args in sent),
        sum(
            "issues/" in " ".join(args) and "events" not in " ".join(args) for args in github.calls
        ),
    ) == ((), 1, 1, 50)


def test_a_poll_whose_changes_are_all_the_services_own_sends_no_graphql_request(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The Service's own events are dropped before any job record is read, so a poll with no
    interval due and nothing else since the cutoff reads only the issue events."""
    github, store = _github_round(tmp_path, monkeypatch, _labeled(12, "roadmap-bot"))
    ran = run_due_jobs(
        REPO,
        store,
        batch={("poll", "", ""): 1},
        table=build_stub_table(),
        data_dir=tmp_path,
        now=NOW,
    )
    assert (ran, github.graphql_calls(), [args[1][:24] for args in github.calls]) == (
        (),
        [],
        ["repos/example/roadmap/is"],
    )
