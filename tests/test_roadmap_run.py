"""Tests for `devops roadmap run` and due table execution (#981).

All tests run in-memory without network or cluster access, testing due evaluation,
schedule persistence, clone management, service wiring, and MCP integration.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from collections.abc import Callable, Sequence
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
    CONST_ROADMAP_CLOSURE_BATCH_KEYS,
    CONST_ROADMAP_INTAKE_BATCH_KEYS,
)
from devops_cli.exceptions import GitOperationError, RoadmapRunError
from devops_cli.roadmap.memory_store import InMemoryRoadmapStore
from devops_cli.roadmap.run import (
    JobOutcome,
    JobRow,
    build_stub_table,
    ensure_checkout,
    run_due_jobs,
    service_job,
)
from devops_cli.roadmap.store import Change, ChangeKind, CloseReason, GitHubState
from devops_cli.server.service import TriggerBatch

REPO = "example/roadmap"
RELEASE = "v0.2.26"
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


def _make_bare_remote(tmp_path: Path) -> Path:
    """Create a temporary bare git repo with a commit on release/v0.2.26."""
    bare = tmp_path / "remote.git"
    work = tmp_path / "work"
    subprocess.run(["git", "init", "--bare", str(bare)], check=True, capture_output=True)
    subprocess.run(["git", "clone", str(bare), str(work)], check=True, capture_output=True)
    subprocess.run(
        ["git", "checkout", "-b", f"release/{RELEASE}"],
        cwd=str(work),
        check=True,
        capture_output=True,
    )
    (work / "file.txt").write_text("initial", encoding="utf-8")
    subprocess.run(["git", "config", "user.name", "Test"], cwd=str(work), check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=str(work), check=True)
    subprocess.run(["git", "add", "."], cwd=str(work), check=True)
    subprocess.run(
        ["git", "commit", "-m", "init"],
        cwd=str(work),
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "push", "origin", f"release/{RELEASE}"],
        cwd=str(work),
        check=True,
        capture_output=True,
    )
    return bare


def _advance_bare_remote(tmp_path: Path) -> str:
    """Add another commit to the bare remote and return its commit hash."""
    work = tmp_path / "work"
    (work / "file.txt").write_text("updated", encoding="utf-8")
    subprocess.run(
        ["git", "commit", "-am", "second"],
        cwd=str(work),
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "push", "origin", f"release/{RELEASE}"],
        cwd=str(work),
        check=True,
        capture_output=True,
    )
    rev = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=str(work),
        capture_output=True,
        text=True,
        check=True,
    )
    return rev.stdout.strip()


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


def test_checkouts_git_management(
    seeded_store: InMemoryRoadmapStore, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Clones to expected path, tracks remote tip, sets identity, fails clone-dependent jobs."""
    bare = _make_bare_remote(tmp_path)
    data_dir = tmp_path / "data"

    fake_session = type("FakeSession", (), {"login": "test-bot"})()
    monkeypatch.setattr("devops_cli.github.session.get_github_session", lambda: fake_session)

    cur = next(r for r in seeded_store.releases() if r.title == RELEASE)
    clone_path = ensure_checkout(REPO, data_dir, remote_url=str(bare), current_rel=cur)

    expected_clone = data_dir / "roadmap" / "example" / "roadmap" / "clone"
    user_name = subprocess.run(
        ["git", "config", "user.name"],
        cwd=str(clone_path),
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    user_email = subprocess.run(
        ["git", "config", "user.email"],
        cwd=str(clone_path),
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()

    new_rev = _advance_bare_remote(tmp_path)
    ensure_checkout(REPO, data_dir, remote_url=str(bare), current_rel=cur)
    head_rev = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=str(clone_path),
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()

    shutil.rmtree(bare)
    shutil.rmtree(clone_path)

    ran_intake = False
    ran_reprio = False
    called_close = False
    called_refine = False

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

    fail_table = build_stub_table(
        {
            "intake": stub_intake,
            "close": stub_close,
            "reprioritize": stub_reprio,
            "refine": stub_refine,
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
        head_rev == new_rev,
        ran_intake,
        ran_reprio,
        called_close,
        called_refine,
        exc_info.value.failed_jobs,
    ) == (
        True,
        "test-bot",
        "test-bot@users.noreply.github.com",
        True,
        True,
        True,
        False,
        False,
        ("close", "refine"),
    )


def test_idle_records_zero_or_one_store_calls(
    seeded_store: InMemoryRoadmapStore, tmp_path: Path
) -> None:
    """Empty batch records 0 store calls; empty poll records exactly 1 changes_since call."""
    t30 = (NOW - timedelta(minutes=30)).isoformat()
    sched = {"intake": t30, "close": t30}
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
