"""Tests for `devops roadmap run` and due table execution (#981).

All tests run in-memory without network or cluster access, testing due evaluation,
schedule persistence, clone management, service wiring, and MCP integration. The clone cases run
real `git` against bare remotes in `tmp_path`, with the session's `gh api user` login answered
at the process edge (#1366). The last cases run the GitHub store over `GitHubFake`, a fake at
the `gh` process edge, to count a round's reads and show that no round reads a project board
(#1361, ADR 0016). The table holds the status lane's
metrics and implement rows and the model lane's intake, refine, stage and alternatives rows;
every clone tracks origin's default branch.
"""

from __future__ import annotations

import ast
import asyncio
import json
import logging
import shutil
import subprocess
import threading
import time
from collections.abc import Callable, Iterator, Mapping, Sequence
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime, timedelta
from functools import partial
from pathlib import Path
from typing import Any, cast
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from devops_cli.ai.mcp.server import roadmap_run
from devops_cli.commands.roadmap import app as roadmap_app
from devops_cli.commands.serve import app as serve_app
from devops_cli.config.constants import (
    CONST_GH_CLI,
    CONST_ROADMAP_INTAKE_BATCH_KEYS,
    CONST_ROADMAP_RUN_CLONE_DIRNAME,
    CONST_ROADMAP_RUN_MODEL_CLONE_DIRNAME,
    CONST_ROADMAP_WEBHOOK_EVENTS,
    CONST_SERVICE_BUDGET_FILENAME,
    CONST_SERVICE_FAILURES_FILENAME,
    CONST_SERVICE_HALT_FILENAME,
    CONST_SERVICE_LANE_MODEL,
    CONST_SERVICE_LANE_STATUS,
    CONST_SERVICE_METRIC_JOB_SUSPENDED,
    CONST_URL_CLOUDFLARE_STATUS_SUMMARY,
    CONST_URL_GITHUB_STATUS_SUMMARY,
)
from devops_cli.config.defaults import DEFAULT_ROADMAP_METRICS_INTERVAL_MINUTES
from devops_cli.config.settings import ServiceConfig
from devops_cli.exceptions import (
    ConfigurationError,
    GitOperationError,
    RoadmapRefineError,
    RoadmapRunError,
)
from devops_cli.exceptions.git import GitHubOperationError, GitHubUnauthenticatedError
from devops_cli.github.rate_limiter import get_github_rate_limiter
from devops_cli.roadmap import store as roadmap_store_module
from devops_cli.roadmap.github_store import GitHubRoadmapStore
from devops_cli.roadmap.intake_model import (
    ModelEvidence,
    ModelProposal,
    ProposalRequest,
    UnusableProposalError,
)
from devops_cli.roadmap.memory_store import InMemoryRoadmapStore
from devops_cli.roadmap.run import (
    DEFAULT_DUE_TABLE,
    MODEL_LANE_ROWS,
    SCOPED_UPDATES,
    STATUS_LANE_ROWS,
    FailureLedger,
    JobOutcome,
    JobRow,
    WebhookDelivery,
    _run_intake_adapter,
    _run_metrics_adapter,
    _run_refine_adapter,
    build_stub_table,
    ensure_checkout,
    read_intake_record,
    run_due_jobs,
    run_scoped_update,
    service_job,
    service_jobs,
    service_state_dir,
)
from devops_cli.roadmap.store import (
    CloseReason,
    Evidence,
    EvidenceKind,
    GitHubState,
    ItemField,
    RoadmapStore,
)
from devops_cli.server.service import ServiceManager, TriggerBatch, no_round_pause
from devops_cli.telemetry.instruments import PROJECT_ITEMS, PROJECT_RELEASES
from devops_cli.telemetry.metrics import GLOBAL_METRICS
from tests.roadmap_faults import Fault, StoppingStore
from tests.roadmap_github_fake import GitHubFake
from tests.support.fakes.github import API, GitHubApiFake, RunnerSession, github_json
from tests.support.fakes.otlp import FakeCollector
from tests.support.paths import REPO_ROOT
from tests.support.waits import THREAD_HANDOFF_BOUND_SECONDS
from tests.web_fakes import StubWeb

pytestmark = pytest.mark.usefixtures("keyring_store")

REPO = "example/roadmap"
# An open planning bucket: a milestone with any title, which no job reads as a version.
PLANNED = "2026-11-05"
COMMIT_IDENTITY = ("-c", "user.name=Test", "-c", "user.email=test@example.com")
NOW = datetime(2026, 10, 4, 12, 0, tzinfo=UTC)
OPENED = CONST_ROADMAP_INTAKE_BATCH_KEYS[0]
POLL_KEY = ("poll", "", "")
# The Priority that makes an issue an Item, as a person sets it.
PLACED = {ItemField.PRIORITY: "P2-Medium"}
runner = CliRunner()


@pytest.mark.parametrize(
    ("module", "adapter_name"),
    [
        ("devops_cli.roadmap.refine", "_run_refine_adapter"),
        ("devops_cli.roadmap.stage", "_run_stage_adapter"),
    ],
)
def test_the_model_job_imports_are_at_module_level_not_lazy_in_the_adapter(
    parsed_source_trees: dict[Path, ast.Module], module: str, adapter_name: str
) -> None:
    """The refine and stage adapters import their modules at module level, so the Service's main
    thread imports pydantic_ai before its worker threads start, and two workers never import it
    for the first time at once and deadlock on the Python 3.14 import lock (#2535, #2659)."""
    tree = parsed_source_trees[REPO_ROOT / "src" / "devops_cli" / "roadmap" / "run.py"]

    module_level = [
        node
        for node in tree.body
        if isinstance(node, ast.ImportFrom) and (node.module or "") == module
    ]
    adapter = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == adapter_name
    )
    local = [
        node
        for node in ast.walk(adapter)
        if isinstance(node, ast.ImportFrom) and (node.module or "").startswith(module)
    ]

    assert (len(module_level), local) == (1, [])


@pytest.fixture
def seeded_store(roadmap_store: InMemoryRoadmapStore) -> InMemoryRoadmapStore:
    """The roadmap every command opens, with a closed and an open milestone."""
    roadmap_store._roadmap.clock = lambda: NOW - timedelta(minutes=10)
    roadmap_store.seed_milestone("Docs pass", state=GitHubState.CLOSED)
    roadmap_store.seed_milestone(PLANNED)
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


def _make_bare_remote(tmp_path: Path, *, other_branch: str | None = None) -> Path:
    """A bare remote whose HEAD names `main`, with one commit on `main` and, when asked, a later
    one on `other_branch`."""
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
    if other_branch is not None:
        _advance_bare_remote(bare, other_branch)
    return bare


def _clone_head(clone_path: Path) -> tuple[str, str]:
    """The clone's HEAD commit and the branch name HEAD points at (`HEAD` when detached)."""
    commit, branch = _git(clone_path, "rev-parse", "HEAD", "--abbrev-ref", "HEAD").splitlines()
    return commit, branch


@pytest.fixture
def main_remote(tmp_path: Path) -> Path:
    """A bare remote holding only `main`."""
    return _make_bare_remote(tmp_path)


@pytest.fixture
def dangling_head_remote(tmp_path: Path) -> Path:
    """A bare remote whose HEAD names `main`, which it lacks: it holds only a topic branch."""
    bare = _make_bare_remote(tmp_path, other_branch="feat/topic")
    _git(bare, "update-ref", "-d", "refs/heads/main")
    return bare


@pytest.fixture
def child_argvs(
    monkeypatch: pytest.MonkeyPatch, github_api: GitHubApiFake
) -> Iterator[list[list[str]]]:
    """Run git for real and answer the session's login lookup through the session fake.

    Every child's argv is recorded. `GET /user` returns `test-bot`, `GET /users/test-bot` its
    account ID, and any gh command fails the test instead of reaching GitHub.
    """
    github_api.route("GET", "/user", github_json({"login": "test-bot"}))
    github_api.route("GET", "/users/test-bot", github_json({"id": 4242, "login": "test-bot"}))
    get_github_rate_limiter().update_quota(
        "core", remaining=5000, limit=5000, reset_epoch=time.time() + 60.0
    )
    real_run = subprocess.run
    argvs: list[list[str]] = []

    def run(argv: Sequence[str], *args: Any, **kwargs: Any) -> subprocess.CompletedProcess[Any]:
        argvs.append(list(argv))
        if argv[0] != CONST_GH_CLI:
            return real_run(argv, *args, **kwargs)
        raise AssertionError(f"A clone test ran {argv}, which would reach GitHub")

    monkeypatch.setattr(subprocess, "run", run)
    yield argvs


REPO_DIR = Path("roadmap") / "example" / "roadmap"
HALF_HOUR_AGO = NOW - timedelta(minutes=30)


def _stamp(tmp_path: Path, **last_success: datetime) -> None:
    """Write each job's last success to the repository's `schedule.json`, and nothing else."""
    path = tmp_path / REPO_DIR / "schedule.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    stamps = {job: at.isoformat() for job, at in last_success.items()}
    path.write_text(json.dumps(stamps), encoding="utf-8")


def _recorded(
    ran: list[str], name: str, job: Callable[..., JobOutcome] | None = None
) -> Callable[..., JobOutcome]:
    """A job that adds `name` to `ran` and then runs `job`, or does nothing when `job` is None."""

    def run(**kwargs: Any) -> JobOutcome:
        ran.append(name)
        return job(**kwargs) if job else JobOutcome()

    return run


def _schedule(tmp_path: Path) -> dict[str, str]:
    """The repository's `schedule.json`."""
    return cast(
        dict[str, str],
        json.loads((tmp_path / REPO_DIR / "schedule.json").read_text(encoding="utf-8")),
    )


def _poll_round(
    store: RoadmapStore,
    tmp_path: Path,
    *,
    now: datetime = NOW,
    table: Sequence[JobRow] | None = None,
    batch: dict[tuple[str, str, str], int] | None = None,
) -> tuple[str, ...]:
    """The jobs one round runs at `now`, on the Service's poll unless `batch` says otherwise."""
    return run_due_jobs(
        REPO,
        store,
        batch={POLL_KEY: 1} if batch is None else batch,
        table=build_stub_table() if table is None else table,
        data_dir=tmp_path,
        now=now,
    )


# ── The due table ─────────────────────────────────────────────────────────────


def test_the_table_runs_the_lanes_in_order_and_names_no_release_job() -> None:
    """The status lane's metrics and implement rows run first, then the model lane's intake,
    refine, stage and alternatives; no row closes items, cuts or starts a release (#1360, #2652,
    #2659, #2667, #2757)."""
    assert (
        [row.name for row in DEFAULT_DUE_TABLE],
        DEFAULT_DUE_TABLE == (*STATUS_LANE_ROWS, *MODEL_LANE_ROWS),
        sorted(CONST_ROADMAP_WEBHOOK_EVENTS),
    ) == (
        ["metrics", "implement", "intake", "refine", "stage", "alternatives"],
        True,
        ["issues"],
    )


def test_due_table_scenarios(seeded_store: InMemoryRoadmapStore, tmp_path: Path) -> None:
    """Intake is due by its hour, a first run, an opened issue's webhook and a reopen a poll
    reads; a close, a label and the store's own write make nothing due. Intake placing a
    critical fix or a P0 item makes refine due in the same round."""
    person = seeded_store.as_actor("alice")
    planned_item = person.seed_issue("Planned bug", milestone=PLANNED, fields=PLACED)
    other_item = person.seed_issue("Backlog item", fields=PLACED)
    t59, t61 = NOW - timedelta(minutes=59), NOW - timedelta(minutes=61)

    def due(
        batch: dict[tuple[str, str, str], int] | None = None,
        *,
        stamps: dict[str, datetime] | None = None,
        table: Sequence[JobRow] | None = None,
    ) -> tuple[str, ...]:
        _stamp(tmp_path, **({"intake": t59} if stamps is None else stamps))
        return _poll_round(seeded_store, tmp_path, table=table, batch=batch or {})

    hour = (due(), due(stamps={"intake": t61}), due(stamps={}))
    opened = due({OPENED: 1})
    person.close_by_hand(other_item, CloseReason.COMPLETED)
    person.reopen_issue(other_item)
    reopened = due({POLL_KEY: 1})
    seeded_store._roadmap.changes.clear()
    person.close_by_hand(planned_item, CloseReason.COMPLETED)
    closed = due({POLL_KEY: 1})
    seeded_store._roadmap.changes.clear()
    person.add_label(other_item, "enhancement")
    labeled = due({POLL_KEY: 1})
    seeded_store._roadmap.changes.clear()
    seeded_store.close_by_hand(other_item, CloseReason.COMPLETED)
    own = due({POLL_KEY: 1})
    critical = build_stub_table(
        {
            "intake": lambda **_: JobOutcome(placed_critical_or_p0=True),
            "refine": lambda **_: JobOutcome(),
        }
    )
    quiet = build_stub_table(
        {"intake": lambda **_: JobOutcome(), "refine": lambda **_: JobOutcome()}
    )
    every = {"intake": t59, "refine": t59}
    cascade = (
        due({OPENED: 1}, stamps=every, table=critical),
        due({OPENED: 1}, stamps=every, table=quiet),
        due(stamps=every, table=quiet),
    )
    assert (hour, opened, reopened, closed, labeled, own, cascade) == (
        ((), ("intake",), ("intake",)),
        ("intake",),
        ("intake",),
        (),
        (),
        (),
        (("intake", "refine"), ("intake",), ()),
    )


def test_webhook_or_poll_identical_and_oldest_cutoff(
    seeded_store: InMemoryRoadmapStore, tmp_path: Path
) -> None:
    """Webhook and poll batches identify same REOPENED trigger with 1 changes_since call."""
    person = seeded_store.as_actor("alice")
    num = person.seed_issue("Item 1", fields=PLACED, state=GitHubState.CLOSED)
    person.reopen_issue(num)
    sched = {"intake": NOW - timedelta(minutes=30)}

    _stamp(tmp_path, **sched)
    spy_wh = StoreSpy(seeded_store)
    res_wh = _poll_round(spy_wh, tmp_path, batch={("webhook", "issues", "reopened"): 1})
    calls_wh = spy_wh.calls.count("changes_since")

    _stamp(tmp_path, **sched)
    spy_poll = StoreSpy(seeded_store)
    res_poll = _poll_round(spy_poll, tmp_path)
    calls_poll = spy_poll.calls.count("changes_since")

    assert (res_wh, calls_wh, res_poll, calls_poll) == (("intake",), 1, ("intake",), 1)


def test_order_and_cross_job_triggers(seeded_store: InMemoryRoadmapStore, tmp_path: Path) -> None:
    """A first round runs metrics, then intake, then refine; with every row run within the hour,
    intake that places a critical fix brings refine in, and a round whose only change is the
    store's own runs nothing (#1360)."""
    calls: list[str] = []

    def make_runner(name: str, outcome: JobOutcome) -> Callable[..., JobOutcome]:
        def run(**_: Any) -> JobOutcome:
            calls.append(name)
            return outcome

        return run

    stubs = {name: make_runner(name, JobOutcome()) for name in ("metrics", "intake", "refine")}
    first = _poll_round(seeded_store, tmp_path, table=build_stub_table(stubs), batch={OPENED: 1})
    t59 = NOW - timedelta(minutes=59)
    _stamp(tmp_path, metrics=NOW - timedelta(minutes=5), intake=t59, refine=t59)
    critical = build_stub_table(
        {"intake": make_runner("intake", JobOutcome(placed_critical_or_p0=True))},
        include_refine=True,
    )
    cascaded = _poll_round(seeded_store, tmp_path, table=critical, batch={OPENED: 1})
    _stamp(tmp_path, metrics=NOW - timedelta(minutes=5), intake=t59, refine=t59)
    seeded_store.close_by_hand(
        seeded_store.seed_issue("Closed by the job", fields=PLACED), CloseReason.COMPLETED
    )
    own = _poll_round(seeded_store, tmp_path, table=build_stub_table(stubs))
    assert (first, calls[:3], cascaded, own) == (
        ("metrics", "intake", "refine"),
        ["metrics", "intake", "refine"],
        ("intake", "refine"),
        (),
    )


def test_refine_is_due_an_hour_after_its_last_success_and_on_a_first_run(
    seeded_store: InMemoryRoadmapStore, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Refine is due 60 min after its last success, not at 59, and on a first run; the CLI's dry
    run lists it (#1515)."""
    table = build_stub_table(include_refine=True)

    def schedule(refine_age: timedelta | None, now: datetime) -> None:
        ages = {"intake": now - timedelta(minutes=59)}
        _stamp(tmp_path, **ages, **({} if refine_age is None else {"refine": now - refine_age}))

    def due(refine_age: timedelta | None) -> tuple[str, ...]:
        schedule(refine_age, NOW)
        return run_due_jobs(
            REPO, seeded_store, table=table, data_dir=tmp_path, dry_run=True, now=NOW
        )

    at_60, at_59, first = due(timedelta(minutes=60)), due(timedelta(minutes=59)), due(None)
    monkeypatch.setenv("DEVOPS_CLI_DATA_DIR", str(tmp_path))
    schedule(timedelta(minutes=61), datetime.now(UTC))
    with patch("devops_cli.roadmap.run.DEFAULT_DUE_TABLE", table):
        cli = runner.invoke(roadmap_app, ["run", "--dry-run", "-R", REPO])

    assert (at_60, at_59, first, cli.exit_code, "Due: refine\n" in cli.output) == (
        ("refine",),
        (),
        ("refine",),
        0,
        True,
    )


def test_stage_is_due_an_hour_after_its_last_success_on_a_first_run_and_the_dry_run_lists_it(
    seeded_store: InMemoryRoadmapStore, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The stage row is due 60 min after its last success, not at 59, and on a first run; the
    CLI's dry run lists it after refine (#2659)."""
    table = build_stub_table(include_refine=True, include_stage=True)

    def due(stage_age: timedelta | None) -> tuple[str, ...]:
        ages = {"intake": NOW - timedelta(minutes=59), "refine": NOW - timedelta(minutes=59)}
        _stamp(tmp_path, **ages, **({} if stage_age is None else {"stage": NOW - stage_age}))
        return run_due_jobs(
            REPO, seeded_store, table=table, data_dir=tmp_path, dry_run=True, now=NOW
        )

    at_60, at_59, first = due(timedelta(minutes=60)), due(timedelta(minutes=59)), due(None)
    monkeypatch.setenv("DEVOPS_CLI_DATA_DIR", str(tmp_path))
    with patch("devops_cli.roadmap.run.DEFAULT_DUE_TABLE", table):
        cli = runner.invoke(roadmap_app, ["run", "--dry-run", "-R", REPO])

    assert (at_60, at_59, first, cli.exit_code, "Due: intake, refine, stage\n" in cli.output) == (
        ("stage",),
        (),
        ("stage",),
        0,
        True,
    )


def test_stage_is_due_in_a_round_where_refine_set_an_item_ready(
    seeded_store: InMemoryRoadmapStore, tmp_path: Path
) -> None:
    """Five minutes after its last success the stage row is due in the round where refine set an
    item Ready, and not in a round where refine set none (#2659)."""
    t61 = NOW - timedelta(minutes=61)

    def round_with(refine: JobOutcome) -> tuple[str, ...]:
        _stamp(
            tmp_path,
            intake=NOW - timedelta(minutes=5),
            refine=t61,
            stage=NOW - timedelta(minutes=5),
        )
        table = build_stub_table({"refine": lambda **_: refine}, include_stage=True)
        return _poll_round(seeded_store, tmp_path, table=table)

    assert (round_with(JobOutcome(set_ready=True)), round_with(JobOutcome())) == (
        ("refine", "stage"),
        ("refine",),
    )


def test_stage_is_due_in_a_round_where_refine_set_an_item_ready_and_failed_another(
    seeded_store: InMemoryRoadmapStore, tmp_path: Path
) -> None:
    """A refine round that fails an item after it set another Ready still makes the stage row
    due in that round, and the round still fails for refine (#2659)."""
    _stamp(
        tmp_path,
        intake=NOW - timedelta(minutes=5),
        refine=NOW - timedelta(minutes=61),
        stage=NOW - timedelta(minutes=5),
    )
    ran: list[str] = []

    def failing_refine(**_: Any) -> JobOutcome:
        raise RoadmapRefineError("refine failed", failed_items=[7], readied_count=1)

    def stage(**_: Any) -> JobOutcome:
        ran.append("stage")
        return JobOutcome()

    table = build_stub_table({"refine": failing_refine, "stage": stage}, include_stage=True)

    with pytest.raises(RoadmapRunError) as raised:
        _poll_round(seeded_store, tmp_path, table=table)

    assert (raised.value.failed_jobs, ran) == (("refine",), ["stage"])


def test_failure_isolation_and_cli_exit(
    seeded_store: InMemoryRoadmapStore, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A failed stub lets the next job run, keeps its own schedule stamp unwritten, and the CLI
    exits 1 naming it."""
    monkeypatch.setenv("DEVOPS_CLI_DATA_DIR", str(tmp_path))
    ran_jobs: list[str] = []

    def failing_intake(**_: Any) -> JobOutcome:
        ran_jobs.append("intake")
        raise RuntimeError("Intake failed")

    def ok_refine(**_: Any) -> JobOutcome:
        ran_jobs.append("refine")
        return JobOutcome()

    table = build_stub_table({"intake": failing_intake, "refine": ok_refine})
    with pytest.raises(RoadmapRunError) as exc_info:
        _poll_round(seeded_store, tmp_path, table=table, batch={OPENED: 1})
    sched_data = _schedule(tmp_path)

    def failing_adapter(*_: Any, **__: Any) -> JobOutcome:
        raise RoadmapRunError("Crash [bold red]markup[/bold red]", failed_jobs=("intake",))

    with patch("devops_cli.roadmap.run.run_due_jobs", side_effect=failing_adapter):
        res = runner.invoke(roadmap_app, ["run", "--confirm", "-R", REPO])

    assert (
        exc_info.value.failed_jobs,
        tuple(ran_jobs),
        "intake" not in sched_data,
        "refine" in sched_data,
        res.exit_code,
        "[bold red]markup[/bold red]" in res.output,
    ) == (("intake",), ("intake", "refine"), True, True, 1, True)


def test_state_file_persistence(seeded_store: InMemoryRoadmapStore, tmp_path: Path) -> None:
    """Schedule records success time; subsequent run 30m later sees intake not due."""
    tbl = build_stub_table({"intake": lambda **_: JobOutcome()})
    _poll_round(seeded_store, tmp_path, table=tbl, batch={OPENED: 1})
    data = _schedule(tmp_path)
    second_due = _poll_round(
        seeded_store, tmp_path, table=tbl, batch={}, now=NOW + timedelta(minutes=30)
    )
    assert ("intake" in data, second_due) == (True, ())


def test_a_failed_read_of_the_changes_propagates_closed(
    seeded_store: InMemoryRoadmapStore, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A failure reading the changes a poll judges propagates rather than being taken as no
    change."""

    def broken_changes(*_: Any, **__: Any) -> list[Any]:
        raise RuntimeError("GitHub API timeout during the events read")

    monkeypatch.setattr(seeded_store, "changes_since", broken_changes)
    with pytest.raises(RuntimeError, match="GitHub API timeout during the events read"):
        _poll_round(seeded_store, tmp_path, table=build_stub_table())


def test_intake_left_with_fresh_candidates_runs_at_the_next_poll_and_its_record_fails_closed(
    seeded_store: InMemoryRoadmapStore, tmp_path: Path
) -> None:
    """The record's pending flag makes intake due with nothing else due, even with no trigger
    at all; a record that cannot be read makes it due too, and reading it raises, naming it."""
    _stamp(tmp_path, intake=HALF_HOUR_AGO)
    record = tmp_path / REPO_DIR / "intake.json"
    record.write_text(json.dumps({"pending": False}), encoding="utf-8")
    settled = _poll_round(seeded_store, tmp_path)
    record.write_text(json.dumps({"pending": True}), encoding="utf-8")
    pending = (_poll_round(seeded_store, tmp_path, batch={}), _poll_round(seeded_store, tmp_path))
    record.write_text("{not json", encoding="utf-8")
    unreadable = _poll_round(seeded_store, tmp_path)
    with pytest.raises(RoadmapRunError, match=r"intake\.json .* Repair it, or remove it"):
        read_intake_record(record)
    assert (settled, pending, unreadable) == ((), (("intake",), ("intake",)), ("intake",))


def test_idle_records_zero_or_one_store_calls(
    seeded_store: InMemoryRoadmapStore, tmp_path: Path
) -> None:
    """Empty batch records 0 store calls; empty poll records exactly 1 changes_since call."""
    recent = NOW - timedelta(minutes=5)
    _stamp(
        tmp_path,
        intake=HALF_HOUR_AGO,
        refine=HALF_HOUR_AGO,
        stage=HALF_HOUR_AGO,
        implement=recent,
        metrics=recent,
        alternatives=recent,
    )
    spy_idle = StoreSpy(seeded_store)
    res_idle = run_due_jobs(REPO, spy_idle, batch={}, data_dir=tmp_path, now=NOW)
    spy_poll = StoreSpy(seeded_store)
    res_poll = run_due_jobs(REPO, spy_poll, batch={POLL_KEY: 1}, data_dir=tmp_path, now=NOW)
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
    _poll_round(seeded_store, tmp_path, table=tbl, batch={OPENED: 1})
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
    ) == (False, 0, True, 0, True, 0, True)


@pytest.fixture
def service_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    """The settings `devops serve --service` needs to manage REPO as a GitHub App."""
    monkeypatch.setenv("DEVOPS_CLI_SERVICE_REPOS", f'["{REPO}"]')
    monkeypatch.setenv("DEVOPS_CLI_SERVICE_GITHUB_APP_APP_ID", "1001")
    monkeypatch.setenv("DEVOPS_CLI_SERVICE_GITHUB_APP_INSTALLATION_ID", "42")
    monkeypatch.setenv("DEVOPS_CLI_SERVICE_GITHUB_APP_SLUG", "devops-roadmap")
    monkeypatch.setenv("DEVOPS_CLI_SERVICE_GITHUB_APP_PRIVATE_KEY", "test-app-private-key")
    monkeypatch.setenv("DEVOPS_CLI_SERVICE_WEBHOOK_SECRETS", f'{{"{REPO}":"secret-1"}}')


@pytest.mark.usefixtures("service_settings")
def test_service_wiring(
    seeded_store: InMemoryRoadmapStore,
    roadmap_store_repos: list[str],
) -> None:
    """`devops serve --service` passes the two lanes' jobs to create_service_app, with no
    reader of a round pause: no roadmap read has a budget refusal that names one (ADR 0016).
    Each lane's job opens the store and runs its own rows in its own clone (#1532)."""
    with patch("uvicorn.run") as mock_uvicorn:
        res = runner.invoke(serve_app, ["--service"])
        fastapi_app = mock_uvicorn.call_args[0][0]()

    batch = TriggerBatch(repo=REPO, counts={OPENED: 1}, first_at=NOW, last_at=NOW)
    with patch("devops_cli.roadmap.run.run_due_jobs") as mock_run:
        for lane_job in fastapi_app.state.jobs.values():
            lane_job(batch)

    lanes = [
        (call.args[0], call.kwargs["table"], call.kwargs["clone_dirname"])
        for call in mock_run.call_args_list
    ]
    assert (
        res.exit_code,
        list(fastapi_app.state.jobs),
        fastapi_app.state.pause_until is no_round_pause,
        REPO in roadmap_store_repos,
        lanes,
        [[row.name for row in rows] for rows in (STATUS_LANE_ROWS, MODEL_LANE_ROWS)],
    ) == (
        0,
        [CONST_SERVICE_LANE_STATUS, CONST_SERVICE_LANE_MODEL],
        True,
        True,
        [
            (REPO, STATUS_LANE_ROWS, CONST_ROADMAP_RUN_CLONE_DIRNAME),
            (REPO, MODEL_LANE_ROWS, CONST_ROADMAP_RUN_MODEL_CLONE_DIRNAME),
        ],
        [["metrics", "implement"], ["intake", "refine", "stage", "alternatives"]],
    )


@pytest.mark.usefixtures("service_settings")
def test_the_service_that_serve_starts_reads_its_halt_and_budget_from_the_volume() -> None:
    """`devops serve --service` gives the Service the state directory on its volume. A Service
    that starts there after a halt and after 60 requests in the budget window is still halted,
    and its budget still counts the 60 requests (#2474, #2523)."""
    volume = service_state_dir()
    volume.mkdir(parents=True)
    halt = {"identity": "devops-roadmap[bot]", "repo": REPO, "kind": "GitHubUnauthenticatedError"}
    (volume / CONST_SERVICE_HALT_FILENAME).write_text(json.dumps(halt), encoding="utf-8")
    window = [[(datetime.now(UTC) - timedelta(minutes=5)).isoformat(), 60]]
    (volume / CONST_SERVICE_BUDGET_FILENAME).write_text(json.dumps(window), encoding="utf-8")

    with patch("uvicorn.run") as mock_uvicorn:
        res = runner.invoke(serve_app, ["--service"])
        manager = mock_uvicorn.call_args[0][0]().state.service_manager

    assert (res.exit_code, manager.pause.halted(), manager.budget.spent()) == (0, True, 60)


def test_mcp_mirror_roadmap_run(seeded_store: InMemoryRoadmapStore) -> None:
    """FastMCP roadmap_run returns due tuple, mutates nothing, and calls no stub."""
    from devops_cli.ai.mcp import server as mcp_server

    seeded_store.seed_issue("An item", fields=PLACED)
    items_before = [it.model_dump() for it in seeded_store.items()]
    writes_before = seeded_store.job_writes()

    def in_process(cmd: list[str], **_: object) -> str:
        return runner.invoke(roadmap_app, cmd[4:]).output

    with patch.object(mcp_server, "_run_mcp_cmd", side_effect=in_process):
        due = roadmap_run(repo=REPO)

    assert isinstance(due, str)
    assert [it.model_dump() for it in seeded_store.items()] == items_before
    assert seeded_store.job_writes() == writes_before


# ── The clone ─────────────────────────────────────────────────────────────────


def test_checkouts_git_management(
    seeded_store: InMemoryRoadmapStore,
    tmp_path: Path,
    main_remote: Path,
    child_argvs: list[list[str]],
) -> None:
    """Clones to the expected path, tracks origin's default branch as it moves, sets the
    identity, and fails the clone-dependent jobs, metrics and refine, when origin is gone; intake
    needs no clone and still runs (#1358)."""
    data_dir = tmp_path / "data"
    clone_path = ensure_checkout(REPO, data_dir, remote_url=str(main_remote))
    expected_clone = data_dir / "roadmap" / "example" / "roadmap" / "clone"
    user_name = _git(clone_path, "config", "user.name")
    user_email = _git(clone_path, "config", "user.email")
    new_rev = _advance_bare_remote(main_remote, "main")
    ensure_checkout(REPO, data_dir, remote_url=str(main_remote))
    head = _clone_head(clone_path)
    shutil.rmtree(main_remote)
    shutil.rmtree(clone_path)

    ran: list[str] = []

    def stub(name: str) -> Callable[..., JobOutcome]:
        return _recorded(ran, name)

    fail_table = build_stub_table(
        {name: stub(name) for name in ("metrics", "intake", "refine")}, needs_clone=True
    )
    with pytest.raises(RoadmapRunError) as exc_info:
        run_due_jobs(
            REPO,
            seeded_store,
            batch={OPENED: 1},
            table=fail_table,
            data_dir=data_dir,
            remote_url=str(main_remote),
            now=NOW,
        )
    assert (
        clone_path == expected_clone,
        user_name,
        user_email,
        head,
        ran,
        exc_info.value.failed_jobs,
    ) == (
        True,
        "test-bot",
        "4242+test-bot@users.noreply.github.com",
        (new_rev, "main"),
        ["intake"],
        ("metrics", "refine"),
    )


def test_checkout_tracks_the_default_branch_whatever_other_branches_origin_holds(
    tmp_path: Path, child_argvs: list[list[str]], caplog: pytest.LogCaptureFixture
) -> None:
    """Another branch on origin is never tracked: the clone follows origin's default branch as
    it moves, and logs nothing about a branch choice."""
    remote = _make_bare_remote(tmp_path, other_branch="feat/1-other")
    data_dir = tmp_path / "data"
    first_tip = _git(remote, "rev-parse", "main")
    with caplog.at_level(logging.INFO, logger="devops_cli.roadmap.run"):
        clone_path = ensure_checkout(REPO, data_dir, remote_url=str(remote))
        first = _clone_head(clone_path)
        new_tip = _advance_bare_remote(remote, "main")
        ensure_checkout(REPO, data_dir, remote_url=str(remote))
    infos = [
        record.getMessage()
        for record in caplog.records
        if record.name == "devops_cli.roadmap.run" and record.levelno == logging.INFO
    ]
    assert (first, _clone_head(clone_path), infos) == (
        (first_tip, "main"),
        (new_tip, "main"),
        [],
    )


def test_checkout_raises_when_the_fetch_fails_and_keeps_the_branch_it_had(
    tmp_path: Path, main_remote: Path, child_argvs: list[list[str]]
) -> None:
    """An unreachable origin raises GitOperationError with git's reason; the clone keeps the
    commit it had (#1366)."""
    data_dir = tmp_path / "data"
    clone_path = ensure_checkout(REPO, data_dir, remote_url=str(main_remote))
    before = _clone_head(clone_path)
    shutil.rmtree(main_remote)

    with pytest.raises(GitOperationError) as raised:
        ensure_checkout(REPO, data_dir, remote_url=str(main_remote))

    message = str(raised.value)
    assert (
        "git fetch --prune origin failed" in message,
        "does not appear to be a git repository" in message,
        _clone_head(clone_path),
    ) == (True, True, before)


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
    tmp_path: Path, child_argvs: list[list[str]]
) -> None:
    """A job that fails after writing a file leaves a tracked change in the clone. The next
    checkout still moves to origin's tip and drops the change, instead of failing every later
    round until a person cleans the clone (#1366)."""
    bare = tmp_path / "remote.git"
    _git(tmp_path, "init", "--bare", "--initial-branch=main", str(bare))
    first = _commit_file(bare, "main", "main\n")
    data_dir = tmp_path / "data"
    clone_path = ensure_checkout(REPO, data_dir, remote_url=str(bare))
    (clone_path / "f.txt").write_text("left by a failed job\n")
    tip = _commit_file(bare, "main", "next\n", parent=first)

    ensure_checkout(REPO, data_dir, remote_url=str(bare))

    assert (
        _clone_head(clone_path),
        (clone_path / "f.txt").read_text(),
        _git(clone_path, "status", "--porcelain"),
    ) == ((tip, "main"), "next\n", "")


def test_checkout_raises_when_origin_head_names_no_branch(
    tmp_path: Path, dangling_head_remote: Path, child_argvs: list[list[str]]
) -> None:
    """A remote whose HEAD names a branch it lacks has no default branch, so the checkout raises
    GitOperationError with git's reason instead of guessing one (#1366)."""
    with pytest.raises(GitOperationError) as raised:
        ensure_checkout(REPO, tmp_path / "data", remote_url=str(dangling_head_remote))

    message = str(raised.value)
    assert (
        "git remote set-head origin --auto failed" in message,
        "Cannot determine remote HEAD" in message,
    ) == (True, True)


def test_clone_and_change_filter_fail_closed_when_login_lookup_fails(
    seeded_store: InMemoryRoadmapStore,
    tmp_path: Path,
    main_remote: Path,
    github_api: GitHubApiFake,
) -> None:
    """When `GET /user` fails, the clone rows and the change filter fail closed without fallback.

    `ensure_checkout` fails before configuring `user.name`, so no `devops-cli` identity is
    written. The clone row fails in `run_due_jobs`, and a store with no actor fails the round
    during change filtering rather than filtering with `devops-cli` (#1409).
    """
    github_api.route("GET", "/user", github_json({"message": "Bad credentials"}, status=401))
    data_dir = tmp_path / "data"

    with pytest.raises(GitHubUnauthenticatedError):
        ensure_checkout(REPO, data_dir, remote_url=str(main_remote))

    clone_dir = data_dir / "roadmap" / REPO / CONST_ROADMAP_RUN_CLONE_DIRNAME
    if (clone_dir / ".git").exists():
        proc = subprocess.run(
            ["git", "-C", str(clone_dir), "config", "user.name"],
            capture_output=True,
            text=True,
            check=False,
        )
        assert proc.stdout.strip() != "devops-cli"

    table = build_stub_table({"refine": lambda **_: JobOutcome()}, needs_clone=True)
    with pytest.raises(RoadmapRunError) as exc_info:
        run_due_jobs(
            REPO,
            seeded_store,
            table=table,
            data_dir=data_dir,
            remote_url=str(main_remote),
            batch={OPENED: 1},
        )
    assert "refine" in exc_info.value.failed_jobs

    store_without_actor = seeded_store.as_actor("")
    store_without_actor._actor = None  # type: ignore[assignment]
    with pytest.raises(GitHubUnauthenticatedError):
        run_due_jobs(
            REPO,
            store_without_actor,
            table=table,
            data_dir=data_dir,
            remote_url=str(main_remote),
            batch={POLL_KEY: 1},
        )


def test_a_rounds_clone_jobs_share_one_clone_on_the_default_branch(
    seeded_store: InMemoryRoadmapStore,
    tmp_path: Path,
    main_remote: Path,
    child_argvs: list[list[str]],
) -> None:
    """Metrics and refine share one clone on `main`, and nothing fails. The dry run of the same
    round starts no git command (#1366)."""
    data_dir = tmp_path / "data"
    main_tip = _git(main_remote, "rev-parse", "main")
    seen: dict[str, tuple[Path | None, tuple[str, str]]] = {}

    def record(job: str) -> Callable[..., JobOutcome]:
        def run_job(*, clone_path: Path | None = None, **_: Any) -> JobOutcome:
            assert clone_path is not None
            seen[job] = (clone_path, _clone_head(clone_path))
            return JobOutcome()

        return run_job

    table = build_stub_table(
        {"metrics": record("metrics"), "refine": record("refine")}, needs_clone=True
    )

    def run_round(*, dry_run: bool) -> tuple[str, ...]:
        return run_due_jobs(
            REPO,
            seeded_store,
            batch={OPENED: 1},
            table=table,
            data_dir=data_dir,
            remote_url=str(main_remote),
            dry_run=dry_run,
            now=NOW,
        )

    before_dry_run = len(child_argvs)
    planned = run_round(dry_run=True)
    dry_run_git = [argv for argv in child_argvs[before_dry_run:] if argv[0] == "git"]
    ran = run_round(dry_run=False)

    clone = data_dir / "roadmap" / "example" / "roadmap" / "clone"
    assert (planned, dry_run_git, ran, seen) == (
        ("metrics", "intake", "refine"),
        [],
        ("metrics", "intake", "refine"),
        {"metrics": (clone, (main_tip, "main")), "refine": (clone, (main_tip, "main"))},
    )


def test_ensure_checkout_rejects_path_escape_and_malformed_repo_slugs(tmp_path: Path) -> None:
    """Test that ensure_checkout strictly validates repo slugs and prevents path traversal escapes."""
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    escapes = [
        "owner//tmp",
        str(tmp_path / "repo"),
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


# ── The metrics job ───────────────────────────────────────────────────────────

STATUS_PAGE = {
    "page": {"id": "page", "name": "Status", "url": "https://example.com"},
    "status": {"indicator": "none", "description": "All Systems Operational"},
}


def test_the_metrics_job_walks_the_version_tags_of_its_own_clone(
    seeded_store: InMemoryRoadmapStore,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    stub_web: StubWeb,
    git: Callable[..., None],
    otlp: FakeCollector,
) -> None:
    """The default table's metrics row clones the repository and walks its version tags there,
    not in the working directory, which in the Service is no git repository (#1358). The gauge
    reads the remote's two past tags, and the job counts the open item of the store it was given
    (#2263). It logs no warning, so every GitHub and status read it made was answered."""
    row = next(row for row in DEFAULT_DUE_TABLE if row.name == "metrics")
    remote = _make_bare_remote(tmp_path)
    for tag in ("v0.1.0", "v0.2.0"):
        git(remote, "tag", tag, "main")
    github = GitHubFake(REPO, milestones=[{"number": 26, "title": PLANNED, "state": "open"}])
    monkeypatch.setattr(subprocess, "run", github.process(subprocess.run))
    for url in (CONST_URL_GITHUB_STATUS_SUMMARY, CONST_URL_CLOUDFLARE_STATUS_SUMMARY):
        stub_web.page(url, json.dumps(STATUS_PAGE))
    stub_web.page(
        f"{API}/user",
        json.dumps({"login": "test-bot"}),
        headers={"content-type": "application/json"},
    )
    stub_web.page(
        f"{API}/users/test-bot",
        json.dumps({"id": 4242, "login": "test-bot"}),
        headers={"content-type": "application/json"},
    )
    seeded_store.seed_issue("feat: export", labels=("type/feature",), fields=PLACED)
    seeded_store.seed_issue("A candidate", labels=("type/feature",))
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
        otlp.points(PROJECT_RELEASES.name),
        otlp.points(PROJECT_ITEMS.name),
        [record.getMessage() for record in caplog.records if record.levelno >= logging.WARNING],
    ) == (
        (True, True, timedelta(minutes=DEFAULT_ROADMAP_METRICS_INTERVAL_MINUTES)),
        ("metrics",),
        True,
        [({}, 2.0)],
        [({"release": "", "state": "open", "type": "feature", "priority": "P2-Medium"}, 1.0)],
        [],
    )


def test_a_failed_metrics_collection_or_status_read_is_logged_and_the_job_goes_on(
    seeded_store: InMemoryRoadmapStore,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    stub_web: StubWeb,
    git: Callable[..., None],
) -> None:
    """GitHub answers a milestone the report cannot count, and neither status page answers:
    each failure is a WARNING from the job, which still returns its outcome."""
    clone = tmp_path / "clone"
    clone.mkdir()
    git(clone, "init", "--quiet")
    milestone = {"number": 26, "title": PLANNED, "state": "open", "open_issues": None}
    monkeypatch.setattr(
        subprocess, "run", GitHubFake(REPO, milestones=[milestone]).process(subprocess.run)
    )
    with caplog.at_level(logging.WARNING):
        outcome = _run_metrics_adapter(store=seeded_store, repo=REPO, clone_path=clone)
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


# ── Intake's limit (#1360) ────────────────────────────────────────────────────


@dataclass
class _IntakeModel:
    """Embeds every text alike and proposes a P2 feature for every candidate but those titled
    in `unusable`, for which it has no usable proposal; `asked` holds each title it judged."""

    unusable: frozenset[str] = frozenset()
    asked: list[str] = field(default_factory=list)
    proposals: Mapping[str, ModelProposal] = field(default_factory=dict)

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        return [[1.0] for _ in texts]

    def propose(self, request: ProposalRequest) -> ModelProposal:
        self.asked.append(request.title)
        if request.title in self.unusable:
            raise UnusableProposalError("no proposal fits")
        if request.title in self.proposals:
            return self.proposals[request.title]
        return ModelProposal(
            type="type/feature",
            type_reason="it adds a capability.",
            priority="P2-Medium",
            priority_reason="useful, not urgent.",
            value="Medium",
            value_reason="it helps maintainers.",
            effort="Low",
            effort_reason="one module.",
        )


@dataclass
class _Clock:
    now: datetime = NOW - timedelta(minutes=10)

    def __call__(self) -> datetime:
        return self.now


def _candidates(count: int) -> tuple[InMemoryRoadmapStore, _Clock, list[str]]:
    """A roadmap with an open milestone and `count` open issues with no Priority, titled
    `candidate 1` up: each one intake's candidate."""
    clock = _Clock()
    store = InMemoryRoadmapStore(clock=clock)
    store.seed_file(".github/labels.yml", Path(".github/labels.yml").read_text(encoding="utf-8"))
    store.seed_milestone(PLANNED)
    titles = [f"candidate {n}" for n in range(1, count + 1)]
    for title in titles:
        store.seed_issue(title)
    return store, clock, titles


def _intake_table(model: _IntakeModel, ran: list[str]) -> tuple[JobRow, ...]:
    """The due table with the Service's own intake over `model`, each run's name added to
    `ran`."""
    intake = partial(_run_intake_adapter, model=model)
    return build_stub_table({"intake": _recorded(ran, "intake", intake)})


def test_a_capped_intake_decides_every_candidate_over_successive_polls_fresh_ones_first(
    tmp_path: Path,
) -> None:
    """Twelve candidates and a limit of five, the five oldest unusable: three polls decide all
    twelve, and the fourth runs no intake. A person's edit to a skipped candidate puts it first
    at intake's next run."""
    store, clock, titles = _candidates(12)
    model = _IntakeModel(unusable=frozenset(titles[:5]))
    ran: list[str] = []
    table = _intake_table(model, ran)

    def poll(minutes: int) -> tuple[tuple[str, ...], tuple[str, ...]]:
        ran.clear()
        asked = len(model.asked)
        _poll_round(store, tmp_path, now=NOW + timedelta(minutes=minutes), table=table)
        return tuple(ran), tuple(model.asked[asked:])

    polls = [poll(minutes) for minutes in (0, 5, 10, 15)]
    clock.now = NOW + timedelta(minutes=20)
    store.as_actor("alice").write_issue_body(4, "Steps to reproduce: run it twice.")
    edited_first = poll(75)[1][:1]
    assert (polls, edited_first) == (
        [
            (("intake",), tuple(titles[:5])),
            (("intake",), tuple(titles[5:10])),
            (("intake",), (*titles[10:], *titles[:3])),
            ((), ()),
        ],
        ("candidate 4",),
    )


def test_a_failed_placement_is_decided_again_after_the_fresh_candidates_and_its_round_goes_on(
    tmp_path: Path,
) -> None:
    """A round whose first placement fails at its first gh write still places the other four
    and fails the job (#1443). The record is written before any placement, so the next round
    decides the fresh candidates first, then the failed one, and none of the four again (#1360)."""
    store, _, titles = _candidates(7)
    model = _IntakeModel()
    table = _intake_table(model, [])
    stopping = StoppingStore(store, Fault(at=1, write="label_issue"))
    with pytest.raises(RoadmapRunError):
        _poll_round(stopping.as_store(), tmp_path, table=table)
    placed = tuple(store.item(number) is not None for number in range(1, 6))
    asked = len(model.asked)
    _poll_round(store, tmp_path, now=NOW + timedelta(minutes=5), table=table)
    assert (stopping.writes[:1], placed, tuple(model.asked[asked:])) == (
        ["label_issue"],
        (False, True, True, True, True),
        (*titles[5:], titles[0]),
    )


def test_intake_placing_p0_item_makes_no_refine_call_and_refine_is_due_through_cross_job_rule(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """An intake run that places a P0 item makes no refine call directly; the same round's refine
    row is due through the cross-job rule (#1540)."""
    clock = _Clock()
    store = InMemoryRoadmapStore(clock=clock)
    store.seed_file(".github/labels.yml", Path(".github/labels.yml").read_text(encoding="utf-8"))
    store.seed_milestone(PLANNED)
    store.seed_evidence(Evidence(kind=EvidenceKind.FAILED_RUN, value="4242"))
    num = store.seed_issue(
        "P0 critical candidate",
        body="Failed run 4242.",
        labels=["type/bug"],
        author_association="COLLABORATOR",
    )
    proposal = ModelProposal(
        type="type/bug",
        type_reason="defect.",
        priority="P0-Critical",
        priority_reason="critical.",
        value="High",
        value_reason="high.",
        effort="Low",
        effort_reason="low.",
        evidence=ModelEvidence(kind="failed_run", value="4242"),
    )
    model = _IntakeModel(proposals={"P0 critical candidate": proposal})
    ran: list[str] = []
    intake = partial(_run_intake_adapter, model=model)
    table = build_stub_table(
        {
            "intake": _recorded(ran, "intake", intake),
            "refine": _recorded(ran, "refine"),
        }
    )
    _stamp(
        tmp_path,
        metrics=NOW,
        intake=NOW - timedelta(minutes=61),
        refine=NOW - timedelta(minutes=5),
    )
    with caplog.at_level(logging.WARNING, logger="devops_cli.roadmap.intake"):
        jobs = _poll_round(store, tmp_path, table=table)

    intake_warnings = [
        r.getMessage() for r in caplog.records if r.name == "devops_cli.roadmap.intake"
    ]
    item = store.item(num)
    assert (
        jobs,
        ran,
        any("refine" in w.lower() for w in intake_warnings),
        item is not None and item.priority,
    ) == (("intake", "refine"), ["intake", "refine"], False, "P0-Critical")


def test_intake_placing_p0_critical_issue_already_labelled_type_bug_makes_refine_due(
    tmp_path: Path,
) -> None:
    """An intake that places a P0-Critical issue already labelled type/bug, so intake adds no
    type label, makes refine due in the same round (#1540)."""
    clock = _Clock()
    store = InMemoryRoadmapStore(clock=clock)
    store.seed_file(".github/labels.yml", Path(".github/labels.yml").read_text(encoding="utf-8"))
    store.seed_milestone(PLANNED)
    store.seed_evidence(Evidence(kind=EvidenceKind.FAILED_RUN, value="4242"))
    num = store.seed_issue(
        "Pre-labelled P0 bug",
        body="Failed run 4242.",
        labels=["type/bug"],
        author_association="COLLABORATOR",
    )
    proposal = ModelProposal(
        type="type/bug",
        type_reason="defect.",
        priority="P0-Critical",
        priority_reason="critical.",
        value="High",
        value_reason="high.",
        effort="Low",
        effort_reason="low.",
        evidence=ModelEvidence(kind="failed_run", value="4242"),
    )
    model = _IntakeModel(proposals={"Pre-labelled P0 bug": proposal})
    ran: list[str] = []
    intake = partial(_run_intake_adapter, model=model)
    table = build_stub_table(
        {
            "intake": _recorded(ran, "intake", intake),
            "refine": _recorded(ran, "refine"),
        }
    )
    _stamp(
        tmp_path,
        metrics=NOW,
        intake=NOW - timedelta(minutes=61),
        refine=NOW - timedelta(minutes=5),
    )
    jobs = _poll_round(store, tmp_path, table=table)
    item = store.item(num)
    assert (
        jobs,
        ran,
        item is not None and item.priority,
    ) == (("intake", "refine"), ["intake", "refine"], "P0-Critical")


def test_intake_placing_p2_medium_issue_labelled_type_bug_does_not_make_refine_due(
    tmp_path: Path,
) -> None:
    """An intake that places a P2-Medium issue labelled type/bug does not make refine due in
    the same round, whether it goes to the backlog or keeps a milestone a person set (#1540)."""
    clock = _Clock()
    store = InMemoryRoadmapStore(clock=clock)
    store.seed_file(".github/labels.yml", Path(".github/labels.yml").read_text(encoding="utf-8"))
    store.seed_milestone(PLANNED)
    # 1. Backlog placement
    num_backlog = store.seed_issue("Backlog P2 bug")
    proposal_backlog = ModelProposal(
        type="type/bug",
        type_reason="defect.",
        priority="P2-Medium",
        priority_reason="medium.",
        value="Medium",
        value_reason="medium.",
        effort="Low",
        effort_reason="low.",
    )
    model_backlog = _IntakeModel(proposals={"Backlog P2 bug": proposal_backlog})
    ran_backlog: list[str] = []
    table_backlog = build_stub_table(
        {
            "intake": _recorded(
                ran_backlog, "intake", partial(_run_intake_adapter, model=model_backlog)
            ),
            "refine": _recorded(ran_backlog, "refine"),
        }
    )
    _stamp(
        tmp_path,
        metrics=NOW,
        intake=NOW - timedelta(minutes=61),
        refine=NOW - timedelta(minutes=5),
    )
    jobs_backlog = _poll_round(store, tmp_path, table=table_backlog)
    item_backlog = store.item(num_backlog)
    assert (
        jobs_backlog,
        ran_backlog,
        item_backlog is not None and item_backlog.priority,
    ) == (("intake",), ["intake"], "P2-Medium")

    # 2. Keeps a milestone a person set
    num_milestone = store.seed_issue("Milestone P2 bug", milestone=PLANNED)
    proposal_milestone = ModelProposal(
        type="type/bug",
        type_reason="defect.",
        priority="P2-Medium",
        priority_reason="medium.",
        value="Medium",
        value_reason="medium.",
        effort="Low",
        effort_reason="low.",
    )
    model_milestone = _IntakeModel(proposals={"Milestone P2 bug": proposal_milestone})
    ran_milestone: list[str] = []
    table_milestone = build_stub_table(
        {
            "intake": _recorded(
                ran_milestone, "intake", partial(_run_intake_adapter, model=model_milestone)
            ),
            "refine": _recorded(ran_milestone, "refine"),
        }
    )
    _stamp(
        tmp_path,
        metrics=NOW,
        intake=NOW - timedelta(minutes=61),
        refine=NOW - timedelta(minutes=5),
    )
    jobs_milestone = _poll_round(store, tmp_path, table=table_milestone)
    item_milestone = store.item(num_milestone)
    assert (
        jobs_milestone,
        ran_milestone,
        item_milestone is not None and (item_milestone.priority, item_milestone.milestone),
    ) == (("intake",), ["intake"], ("P2-Medium", PLANNED))


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
    """A repository with 60 Items and an open milestone, its intake run five minutes ago, the
    Service logged in as `roadmap-bot`, and the store a round opens over it."""
    github = GitHubFake(
        REPO, milestones=[{"number": 26, "title": PLANNED, "state": "open"}], events=events
    )
    for number in range(1, 61):
        github.seed_issue(number, labels=("priority/p2-medium", "status/ready"))
    _stamp(tmp_path, intake=NOW - timedelta(minutes=5))
    monkeypatch.setattr("devops_cli.roadmap.run._get_session_login", lambda: "roadmap-bot")
    store = GitHubRoadmapStore(REPO, runner=github, session=RunnerSession(github))
    return github, store


def test_a_round_judging_50_foreign_label_changes_reads_only_the_issue_events(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A label change makes no job due, and no rule reads an Item or an issue for it, so the
    round reads the issue events and nothing else (#1360)."""
    github, store = _github_round(tmp_path, monkeypatch, _labeled(50, "alice"))
    ran = _poll_round(store, tmp_path)
    assert (ran, [args[-1].split("?")[0] for args in github.calls]) == (
        (),
        [f"{API}/repos/{REPO}/issues/events"],
    )


def test_a_poll_whose_changes_are_all_the_services_own_sends_no_graphql_request(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The Service's own events are dropped, so a poll with no interval due and nothing else
    since the cutoff reads only the issue events (#1360)."""
    github, store = _github_round(tmp_path, monkeypatch, _labeled(12, "roadmap-bot"))
    ran = _poll_round(store, tmp_path)
    assert (ran, [args[-1].split("?")[0] for args in github.calls]) == (
        (),
        [f"{API}/repos/{REPO}/issues/events"],
    )


DEFAULT_JOB_NAMES = ("metrics", "implement", "intake", "refine")
POLL = TriggerBatch(repo=REPO, counts={POLL_KEY: 1}, first_at=NOW, last_at=NOW)


def _service_github(events: list[dict[str, Any]]) -> GitHubFake:
    """The repository `service_job` opens, with three Items, the labels file intake reads, and
    `events` dated now."""
    now = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    github = GitHubFake(
        REPO,
        milestones=[{"number": 26, "title": PLANNED, "state": "open"}],
        files={".github/labels.yml": Path(".github/labels.yml").read_text(encoding="utf-8")},
        events=[event | {"created_at": now} for event in events],
    )
    for number in range(1, 4):
        github.seed_issue(number, labels=("priority/p2-medium", "status/ready"))
    return github


def _serve_over(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, gh: Callable[..., Any]) -> None:
    """`service_job` opens its stores over `gh`, logged in as `roadmap-bot`, with every job of
    the default table run a minute ago, so a poll runs only what changes since then make due."""
    minute_ago = datetime.now(UTC) - timedelta(minutes=1)
    _stamp(tmp_path, **dict.fromkeys(DEFAULT_JOB_NAMES, minute_ago))
    monkeypatch.setenv("DEVOPS_CLI_DATA_DIR", str(tmp_path))
    monkeypatch.setattr("devops_cli.roadmap.run._get_session_login", lambda: "roadmap-bot")
    monkeypatch.setattr(
        roadmap_store_module,
        "get_roadmap_store",
        lambda repo, runner=None: GitHubRoadmapStore(repo, runner=gh, session=RunnerSession(gh)),
    )


def test_a_service_round_that_places_a_candidate_sends_no_projects_request(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A reopened issue makes intake due in a model-lane round. The round places the candidate
    with labels alone: it sends no request to a project board and reads no
    `.github/roadmap.toml` (ADR 0016)."""
    reopened = {"event": "reopened", "actor": {"login": "alice"}, "issue": {"number": 4}}
    github = _service_github([reopened])
    github.seed_issue(4, "A candidate", body="Export the report as CSV.")
    _serve_over(tmp_path, monkeypatch, github)
    monkeypatch.setattr(subprocess, "run", github.process(subprocess.run))
    model, ran = _IntakeModel(), []
    lane = partial(
        service_job,
        table=_intake_table(model, ran),
        clone_dirname=CONST_ROADMAP_RUN_MODEL_CLONE_DIRNAME,
    )
    lane(POLL)
    assert (ran, github.project_calls(), sorted(github.labels(4))) == (
        ["intake"],
        [],
        ["effort/low", "priority/p2-medium", "status/new", "type/feature", "value/medium"],
    )


# ── The Service's status and model lanes (#1532) ──────────────────────────────


def _lane(
    rows: Sequence[JobRow], *, needs_clone: bool = False, **runners: Callable[..., JobOutcome]
) -> tuple[JobRow, ...]:
    """A lane's rows, in its order, each running its stub from `runners` or doing nothing, with a
    clone only when `needs_clone`."""
    return tuple(
        replace(
            row,
            runner=runners.get(row.name, lambda **_: JobOutcome()),
            needs_clone=needs_clone and row.needs_clone,
        )
        for row in rows
    )


def test_a_status_lane_poll_reads_no_change_and_sends_no_request(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """No status-lane row has a due rule, so its poll reads no change: with nothing due by its
    interval, the round sends no request, and reads no roadmap file as it opens the store."""
    github = _service_github(_labeled(2, "alice"))
    _serve_over(tmp_path, monkeypatch, github)
    service_jobs(tmp_path)[CONST_SERVICE_LANE_STATUS](POLL)
    assert [args for args in github.calls if "rate_limit" not in " ".join(args)] == []


def test_a_blocked_model_lane_holds_back_none_of_the_status_lanes_rounds(
    seeded_store: InMemoryRoadmapStore, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A refine round blocks on a slow model. In the same repository the status lane still runs
    the metrics row and the implement row a poll makes due, while the refine round is still
    running (#2757)."""
    monkeypatch.setenv("DEVOPS_CLI_DATA_DIR", str(tmp_path))
    refining, model_answers = threading.Event(), threading.Event()
    refine_released: list[bool] = []
    measured: list[str] = []
    during_refine: list[bool] = []

    def implement(**_: Any) -> JobOutcome:
        # Records whether the model had not yet answered when the row ran.
        during_refine.append(not model_answers.is_set())
        return JobOutcome()

    def refine(**_: Any) -> JobOutcome:
        refining.set()
        # Records that the test, not the bound, ended each wait on the slow model.
        refine_released.append(model_answers.wait(timeout=THREAD_HANDOFF_BOUND_SECONDS))
        return JobOutcome()

    lanes = {
        CONST_SERVICE_LANE_STATUS: partial(
            service_job,
            table=_lane(
                STATUS_LANE_ROWS,
                metrics=_recorded(measured, "metrics"),
                implement=_recorded(measured, "implement", implement),
            ),
            clone_dirname=CONST_ROADMAP_RUN_CLONE_DIRNAME,
        ),
        CONST_SERVICE_LANE_MODEL: partial(
            service_job,
            table=_lane(MODEL_LANE_ROWS, refine=refine),
            clone_dirname=CONST_ROADMAP_RUN_MODEL_CLONE_DIRNAME,
        ),
    }
    manager = ServiceManager(
        ServiceConfig(repos=[REPO]), {}, lanes, lambda: datetime.now(UTC), asyncio.sleep
    )
    status_lane, model_lane = (manager.workers[(REPO, lane)] for lane in lanes)
    for worker in manager.workers.values():
        worker.start()
    manager.enqueue_trigger(REPO, "poll", "", "")
    assert refining.wait(timeout=THREAD_HANDOFF_BOUND_SECONDS)
    measured_while_refining = status_lane.wait_active(THREAD_HANDOFF_BOUND_SECONDS)
    refine_still_running = model_lane.is_active()
    model_answers.set()
    asyncio.run(manager.drain_and_stop())
    assert (
        measured_while_refining,
        measured,
        during_refine,
        refine_still_running,
        bool(refine_released) and all(refine_released),
    ) == (True, ["metrics", "implement"], [True], True, True)


def test_the_implement_row_is_due_on_the_status_lane_by_its_interval_and_by_no_hint(
    seeded_store: InMemoryRoadmapStore, tmp_path: Path
) -> None:
    """A poll makes the row due on the status lane ten minutes after its last success and not
    before. A webhook batch reaches the lane too, and makes the row due no sooner, since the row
    has no batch key (#2757)."""

    def ran(batch: dict[tuple[str, str, str], int], **stamps: datetime) -> tuple[str, ...]:
        _stamp(tmp_path, **stamps)
        return _poll_round(seeded_store, tmp_path, table=_lane(STATUS_LANE_ROWS), batch=batch)

    fresh = {"metrics": NOW - timedelta(minutes=1)}
    first = ran({POLL_KEY: 1})
    too_soon = ran({POLL_KEY: 1}, **fresh, implement=NOW - timedelta(minutes=9, seconds=59))
    ten_minutes = ran({POLL_KEY: 1}, **fresh, implement=NOW - timedelta(minutes=10))
    hinted = ran({OPENED: 1}, **fresh, implement=NOW - timedelta(minutes=2))

    assert (first, too_soon, ten_minutes, hinted) == (
        ("metrics", "implement"),
        (),
        ("implement",),
        (),
    )


def test_a_ledger_record_with_an_implement_entry_loads_and_keeps_the_row_suspended_on_its_lane(
    seeded_store: InMemoryRoadmapStore, tmp_path: Path
) -> None:
    """The ledger keys an entry by the repository and the job, so a record has no lane to move.
    A record whose `implement` entry reached the limit loads, shows the row suspended, and keeps
    the row from running in a status-lane round of the same input (#2757)."""
    record = tmp_path / CONST_SERVICE_FAILURES_FILENAME
    calls: list[str] = []

    def failing(**_: Any) -> JobOutcome:
        calls.append("implement")
        raise GitOperationError("The Kubernetes API refused the call.")

    def round_of(at: datetime) -> tuple[str, ...]:
        return run_due_jobs(
            REPO,
            seeded_store,
            batch={POLL_KEY: 1},
            table=_lane(STATUS_LANE_ROWS, implement=failing),
            data_dir=tmp_path,
            now=at,
            failures=FailureLedger(record=record),
        )

    for step in range(FailureLedger().limit):
        with pytest.raises(RoadmapRunError):
            round_of(NOW + timedelta(minutes=step))
    kept = json.loads(record.read_text(encoding="utf-8"))
    GLOBAL_METRICS.reset()
    suspended_labels = {"repo": REPO, "row": "implement"}

    # A restart: a new ledger reads the record, and the round of the same input runs no row.
    round_of(NOW + timedelta(minutes=10))
    loaded = GLOBAL_METRICS.get_gauge_value(
        CONST_SERVICE_METRIC_JOB_SUSPENDED, labels=suspended_labels
    )

    assert (
        [entry[:3] for entry in kept],
        calls,
        loaded,
    ) == ([[REPO, "implement", FailureLedger().limit]], ["implement"] * 3, 1.0)


def test_each_lanes_success_stays_in_schedule_json_when_their_rounds_interleave(
    seeded_store: InMemoryRoadmapStore, tmp_path: Path
) -> None:
    """A model-lane round records intake, refine, stage and alternatives while a status-lane round
    is running metrics, which had read `schedule.json` before them: the success of metrics and the
    one of implement, which follows it, keep theirs."""
    later = NOW + timedelta(seconds=1)

    def metrics(**_: Any) -> JobOutcome:
        model_round = run_due_jobs(
            REPO,
            seeded_store,
            batch={POLL_KEY: 1},
            table=_lane(MODEL_LANE_ROWS),
            data_dir=tmp_path,
            now=later,
        )
        assert model_round == ("intake", "refine", "stage", "alternatives")
        return JobOutcome()

    ran = run_due_jobs(
        REPO,
        seeded_store,
        batch={POLL_KEY: 1},
        table=_lane(STATUS_LANE_ROWS, metrics=metrics),
        data_dir=tmp_path,
        now=NOW,
    )
    assert (ran, _schedule(tmp_path)) == (
        ("metrics", "implement"),
        {
            "intake": later.isoformat(),
            "refine": later.isoformat(),
            "stage": later.isoformat(),
            "alternatives": later.isoformat(),
            "metrics": NOW.isoformat(),
            "implement": NOW.isoformat(),
        },
    )


def test_each_lane_updates_only_its_own_clone(
    seeded_store: InMemoryRoadmapStore, tmp_path: Path, child_argvs: list[list[str]]
) -> None:
    """The status lane's metrics works in `clone` and the model lane's refine in `model-clone`,
    each at origin's tip of the default branch. A model-lane round leaves a change in `clone`
    alone, where a checkout of that clone would discard it."""
    bare = tmp_path / "remote.git"
    _git(tmp_path, "init", "--bare", "--initial-branch=main", str(bare))
    main_tip = _commit_file(bare, "main", "main\n")
    data_dir = tmp_path / "data"
    seen: dict[str, tuple[Path, tuple[str, str]]] = {}

    def record(job: str) -> Callable[..., JobOutcome]:
        def run_job(*, clone_path: Path | None = None, **_: Any) -> JobOutcome:
            assert clone_path is not None
            seen[job] = (clone_path, _clone_head(clone_path))
            return JobOutcome()

        return run_job

    def lane_round(table: Sequence[JobRow], clone_dirname: str) -> tuple[str, ...]:
        return run_due_jobs(
            REPO,
            seeded_store,
            batch={OPENED: 1},
            table=table,
            data_dir=data_dir,
            remote_url=str(bare),
            now=NOW,
            clone_dirname=clone_dirname,
        )

    lane_round(
        _lane(STATUS_LANE_ROWS, needs_clone=True, metrics=record("metrics")),
        CONST_ROADMAP_RUN_CLONE_DIRNAME,
    )
    in_progress = seen["metrics"][0] / "f.txt"
    in_progress.write_text("work in progress\n")
    lane_round(
        _lane(MODEL_LANE_ROWS, needs_clone=True, refine=record("refine")),
        CONST_ROADMAP_RUN_MODEL_CLONE_DIRNAME,
    )
    repo_dir = data_dir / REPO_DIR
    assert (seen, in_progress.read_text()) == (
        {
            "metrics": (repo_dir / "clone", (main_tip, "main")),
            "refine": (repo_dir / "model-clone", (main_tip, "main")),
        },
        "work in progress\n",
    )


def test_roadmap_run_error_is_configuration_only() -> None:
    """RoadmapRunError.is_configuration_only checks if all cause group exceptions are ConfigurationError (#1365)."""
    cfg1 = ConfigurationError("bad labels 1", key="service.repos")
    cfg2 = ConfigurationError("bad labels 2", key="labels")
    unexpected = RuntimeError("unexpected crash")

    # Group of configuration errors only
    group_cfg = ExceptionGroup("jobs", [cfg1, cfg2])
    err1 = RoadmapRunError("failed", failed_jobs=("intake", "metrics"))
    err1.__cause__ = group_cfg
    assert err1.is_configuration_only is True

    # Group of mixed errors
    group_mixed = ExceptionGroup("jobs", [cfg1, unexpected])
    err2 = RoadmapRunError("failed", failed_jobs=("intake", "metrics"))
    err2.__cause__ = group_mixed
    assert err2.is_configuration_only is False

    # Group of unexpected errors only
    group_unexpected = ExceptionGroup("jobs", [unexpected])
    err3 = RoadmapRunError("failed", failed_jobs=("metrics",))
    err3.__cause__ = group_unexpected
    assert err3.is_configuration_only is False

    # Single ConfigurationError cause
    err4 = RoadmapRunError("failed", failed_jobs=("intake",))
    err4.__cause__ = cfg1
    assert err4.is_configuration_only is True

    # No cause or non-config single cause
    err5 = RoadmapRunError("failed", failed_jobs=("intake",))
    err5.__cause__ = unexpected
    assert err5.is_configuration_only is False

    err6 = RoadmapRunError("failed", failed_jobs=())
    assert err6.is_configuration_only is False


def test_failed_run_keeps_every_job_error_and_clone_error(
    seeded_store: InMemoryRoadmapStore, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """A failed run keeps every job's error, names intake and metrics, refine with clone failure,
    carries ExceptionGroup cause with PEP 678 notes, is not config-only, and emits no ERROR log (#1365)."""
    data_dir = tmp_path / "data"
    missing_remote = tmp_path / "missing_remote"
    ran: list[str] = []

    def fail_intake(**_: Any) -> JobOutcome:
        raise ConfigurationError("invalid labels.yml", key="labels")

    def stub(name: str) -> Callable[..., JobOutcome]:
        return _recorded(ran, name)

    table = build_stub_table(
        {"intake": fail_intake, "metrics": stub("metrics"), "refine": stub("refine")},
        needs_clone=True,
    )

    with caplog.at_level(logging.ERROR, logger="devops_cli.roadmap.run"):
        with pytest.raises(RoadmapRunError) as exc_info:
            run_due_jobs(
                REPO,
                seeded_store,
                batch={OPENED: 1},
                table=table,
                data_dir=data_dir,
                remote_url=str(missing_remote),
                now=NOW,
            )

    err = exc_info.value
    assert err.failed_jobs == ("metrics", "intake", "refine")
    assert "intake: invalid labels.yml" in str(err)
    assert "metrics, refine: git clone " in str(err)
    assert err.is_configuration_only is False

    cause = err.__cause__
    assert isinstance(cause, ExceptionGroup)
    assert len(cause.exceptions) == 2
    notes = {exc.__notes__[0]: exc for exc in cause.exceptions}
    assert "intake" in notes
    assert isinstance(notes["intake"], ConfigurationError)
    assert "metrics, refine" in notes
    assert isinstance(notes["metrics, refine"], GitOperationError)

    # No ERROR records emitted by devops_cli.roadmap.run
    error_records = [
        r
        for r in caplog.records
        if r.name == "devops_cli.roadmap.run" and r.levelno >= logging.ERROR
    ]
    assert error_records == []


def test_failed_run_configuration_only(seeded_store: InMemoryRoadmapStore, tmp_path: Path) -> None:
    """A run failing only with ConfigurationError is marked is_configuration_only (#1365)."""
    data_dir = tmp_path / "data"

    def fail_intake(**_: Any) -> JobOutcome:
        raise ConfigurationError("missing labels", key="labels")

    table = build_stub_table({"intake": fail_intake})

    with pytest.raises(RoadmapRunError) as exc_info:
        run_due_jobs(
            REPO,
            seeded_store,
            batch={OPENED: 1},
            table=table,
            data_dir=data_dir,
            now=NOW,
        )

    err = exc_info.value
    assert err.failed_jobs == ("intake",)
    assert "intake: missing labels" in str(err)
    assert err.is_configuration_only is True
    assert isinstance(err.__cause__, ExceptionGroup)
    assert len(err.__cause__.exceptions) == 1
    assert err.__cause__.exceptions[0].__notes__ == ["intake"]


def test_clone_fails_with_missing_git_binary(
    seeded_store: InMemoryRoadmapStore, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When git binary is missing, clone rows fail with FileNotFoundError as group member (#1365)."""
    data_dir = tmp_path / "data"
    empty_bin = tmp_path / "empty_bin"
    empty_bin.mkdir()
    monkeypatch.setenv("PATH", str(empty_bin))

    missing_remote = tmp_path / "missing_remote"
    ran: list[str] = []

    def stub(name: str) -> Callable[..., JobOutcome]:
        return _recorded(ran, name)

    table = build_stub_table(
        {"metrics": stub("metrics"), "refine": stub("refine")},
        needs_clone=True,
    )

    with pytest.raises(RoadmapRunError) as exc_info:
        run_due_jobs(
            REPO,
            seeded_store,
            batch={OPENED: 1},
            table=table,
            data_dir=data_dir,
            remote_url=str(missing_remote),
            now=NOW,
        )

    err = exc_info.value
    assert err.failed_jobs == ("metrics", "refine")
    cause = err.__cause__
    assert isinstance(cause, ExceptionGroup)
    assert len(cause.exceptions) == 1
    assert isinstance(cause.exceptions[0], FileNotFoundError)
    assert cause.exceptions[0].__notes__ == ["metrics, refine"]
    assert str(cause.exceptions[0]).splitlines()[0] in str(err)


def test_a_service_round_needs_no_roadmap_file(
    roadmap_store: InMemoryRoadmapStore,
    roadmap_store_repos: list[str],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A repository with no roadmap file runs its round: service_job opens the store of the
    batch's repository and reads no file (ADR 0016)."""
    monkeypatch.setenv("DEVOPS_CLI_DATA_DIR", str(tmp_path))
    batch = TriggerBatch(repo="example/repo", counts={OPENED: 1}, first_at=NOW, last_at=NOW)
    ran: list[str] = []
    service_job(
        batch,
        table=_lane(STATUS_LANE_ROWS, metrics=_recorded(ran, "metrics")),
        clone_dirname=CONST_ROADMAP_RUN_CLONE_DIRNAME,
    )
    assert (ran, roadmap_store_repos) == (["metrics"], ["example/repo"])


def test_service_job_unreadable_github_roadmap_propagates_unchanged(
    unreadable_github_roadmap: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A model-lane round whose read of the changes GitHub cannot answer (HTTP 503) raises
    GitHubOperationError unchanged (#1365)."""
    monkeypatch.setenv("DEVOPS_CLI_DATA_DIR", str(tmp_path))
    monkeypatch.setattr("devops_cli.roadmap.run._get_session_login", lambda: "roadmap-bot")
    batch = TriggerBatch(repo="example/repo", counts={OPENED: 1}, first_at=NOW, last_at=NOW)

    with pytest.raises(GitHubOperationError) as exc_info:
        service_job(batch, table=MODEL_LANE_ROWS, clone_dirname=CONST_ROADMAP_RUN_CLONE_DIRNAME)

    assert not isinstance(exc_info.value, ConfigurationError)


# ── Scoped updates (ADR 0017) ─────────────────────────────────────────────────


def _delivery(action: str, number: int, *, event: str = "issues") -> WebhookDelivery:
    """What a webhook delivery of `event` with `action` about issue `number` carries."""
    return WebhookDelivery(repo=REPO, event=event, action=action, number=number)


def test_the_issues_actions_run_a_scoped_intake_on_the_model_lane() -> None:
    """`issues` opened, edited and reopened each run intake of one issue on the model lane, and
    no other event has a scoped update."""
    assert {key: (update.job, update.lane) for key, update in SCOPED_UPDATES.items()} == {
        ("issues", "opened"): ("intake", CONST_SERVICE_LANE_MODEL),
        ("issues", "edited"): ("intake", CONST_SERVICE_LANE_MODEL),
        ("issues", "reopened"): ("intake", CONST_SERVICE_LANE_MODEL),
    }


@pytest.mark.parametrize("action", ["opened", "edited", "reopened"])
def test_an_issues_delivery_intakes_only_its_issue_and_writes_no_last_success(
    action: str, tmp_path: Path
) -> None:
    """The scoped update of an `issues` delivery decides and places only the issue it names: the
    model judges it alone, only it gets labels and a reason comment, and `schedule.json` keeps
    each job's last success as it was."""
    store, _, _ = _candidates(3)
    _stamp(tmp_path, intake=HALF_HOUR_AGO)
    model = _IntakeModel()

    outcome = run_scoped_update(
        _delivery(action, 2), store, data_dir=tmp_path, now=NOW, model=model
    )

    assert (
        outcome,
        model.asked,
        sorted({write.number for write in store.job_writes()}),
        [store.item(number) is not None for number in (1, 2, 3)],
        [len(store.comments_on(number)) for number in (1, 2, 3)],
        _schedule(tmp_path),
    ) == (
        JobOutcome(),
        ["candidate 2"],
        [2],
        [False, True, False],
        [0, 1, 0],
        {"intake": HALF_HOUR_AGO.isoformat()},
    )


def test_an_edit_of_an_item_and_an_event_with_no_scoped_update_change_nothing(
    tmp_path: Path,
) -> None:
    """An edit of an issue that is already an Item decides nothing and writes no record. An
    `issues` action or an event with no scoped update returns None, so its delivery stays a hint
    for a whole round."""
    store, _, _ = _candidates(0)
    placed = store.seed_issue("placed", fields={ItemField.PRIORITY: "P2-Medium"})
    model = _IntakeModel()

    def run(delivery: WebhookDelivery) -> JobOutcome | None:
        return run_scoped_update(delivery, store, data_dir=tmp_path, now=NOW, model=model)

    edited = run(_delivery("edited", placed))
    closed = run(_delivery("closed", placed))
    pull = run(_delivery("opened", placed, event="pull_request"))

    assert (
        edited,
        closed,
        pull,
        model.asked,
        store.job_writes(),
        (tmp_path / REPO_DIR / "intake.json").exists(),
    ) == (JobOutcome(), None, None, [], [], False)


@pytest.mark.parametrize("lost", ["opened", "reopened"])
def test_a_poll_after_a_scoped_update_decides_the_lost_delivery_and_not_the_handled_one(
    lost: str, tmp_path: Path
) -> None:
    """Test first for #2009: the delivery of issue 2 runs its scoped update, and the delivery of
    issue 1 is lost. The next poll comes before intake's hourly interval. It runs intake, which
    decides issue 1 and does not decide issue 2 again."""
    store, clock, _ = _candidates(1)
    if lost == "reopened":
        store.close_by_hand(1, CloseReason.NOT_PLANNED)
        clock.now = NOW - timedelta(minutes=5)
        store.reopen_issue(1)
    delivered = store.seed_issue("candidate 2")
    _stamp(tmp_path, intake=HALF_HOUR_AGO)
    model = _IntakeModel()
    ran: list[str] = []

    run_scoped_update(
        _delivery("opened", delivered), store, data_dir=tmp_path, now=NOW, model=model
    )
    after_update = _schedule(tmp_path)
    jobs = _poll_round(
        store, tmp_path, now=NOW + timedelta(minutes=5), table=_intake_table(model, ran)
    )

    assert (
        after_update,
        jobs,
        model.asked,
        store.item(1) is not None,
        store.item(delivered) is not None,
    ) == (
        {"intake": HALF_HOUR_AGO.isoformat()},
        ("intake",),
        ["candidate 2", "candidate 1"],
        True,
        True,
    )


def test_a_scoped_update_keeps_the_entries_and_the_pending_flag_a_capped_round_left(
    tmp_path: Path,
) -> None:
    """A capped round decides five of seven candidates and leaves a fresh one. A scoped update of
    candidate 6 adds its entry, keeps the five others and keeps intake due. The next poll decides
    candidate 7 alone."""
    store, _, titles = _candidates(7)
    model = _IntakeModel()
    table = _intake_table(model, [])
    _poll_round(store, tmp_path, table=table)

    run_scoped_update(
        _delivery("opened", 6),
        store,
        data_dir=tmp_path,
        now=NOW + timedelta(minutes=1),
        model=model,
    )
    record = read_intake_record(tmp_path / REPO_DIR / "intake.json")
    asked = len(model.asked)
    _poll_round(store, tmp_path, now=NOW + timedelta(minutes=5), table=table)

    assert (record.pending, sorted(record.waiting), model.asked[asked:]) == (
        True,
        [1, 2, 3, 4, 5, 6],
        [titles[6]],
    )


def test_the_alternatives_row_follows_refine_and_is_due_once_a_day_and_by_no_hint(
    seeded_store: InMemoryRoadmapStore, tmp_path: Path
) -> None:
    """The row is due on a first run, 24 hours after its last success and not before, and a
    webhook hint that makes intake due makes it due no sooner (#2652)."""
    five_minutes_ago = NOW - timedelta(minutes=5)
    recent = {
        "intake": five_minutes_ago,
        "refine": five_minutes_ago,
        "stage": five_minutes_ago,
    }

    def ran(batch: dict[tuple[str, str, str], int], **stamps: datetime) -> tuple[str, ...]:
        _stamp(tmp_path, **stamps)
        return _poll_round(seeded_store, tmp_path, table=_lane(MODEL_LANE_ROWS), batch=batch)

    first = ran({POLL_KEY: 1})
    too_soon = ran({POLL_KEY: 1}, **recent, alternatives=NOW - timedelta(hours=23, minutes=59))
    a_day = ran({POLL_KEY: 1}, **recent, alternatives=NOW - timedelta(hours=24))
    hinted = ran({OPENED: 1}, **recent, alternatives=NOW - timedelta(hours=2))

    assert (first, too_soon, a_day, hinted) == (
        ("intake", "refine", "stage", "alternatives"),
        (),
        ("alternatives",),
        ("intake",),
    )


def test_the_dry_run_of_the_cli_lists_the_alternatives_row(
    seeded_store: InMemoryRoadmapStore, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """On a first run every row is due, and the CLI's dry run lists the alternatives row last
    (#2652)."""
    monkeypatch.setenv("DEVOPS_CLI_DATA_DIR", str(tmp_path))

    cli = runner.invoke(roadmap_app, ["run", "--dry-run", "-R", REPO])

    assert (
        cli.exit_code,
        "Due: metrics, implement, intake, refine, stage, alternatives\n" in cli.output,
    ) == (0, True)


def test_the_alternatives_adapter_imports_the_job_at_module_level_not_lazily(
    parsed_source_trees: dict[Path, ast.Module],
) -> None:
    """The job imports pydantic_ai, so the Service's main thread imports it before its worker
    threads start, as it does for refine (#2535)."""
    tree = parsed_source_trees[REPO_ROOT / "src" / "devops_cli" / "roadmap" / "run.py"]
    wanted = "devops_cli.roadmap.alternatives"

    module_level = [
        node
        for node in tree.body
        if isinstance(node, ast.ImportFrom) and (node.module or "") == wanted
    ]
    local = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
        and (node.module or "") == wanted
        and node not in module_level
    ]

    assert (len(module_level), local) == (1, [])
