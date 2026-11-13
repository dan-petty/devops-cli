"""`devops roadmap run` picks the rows of the due table that are due: the order of the lanes, the
interval of each row, the hints of a webhook or a poll, and the record of each success (#981).
"""

from __future__ import annotations

import json
from collections.abc import Callable, Sequence
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from devops_cli.config.constants import (
    CONST_ROADMAP_STAGE_DUE_STAMP,
    CONST_ROADMAP_WEBHOOK_EVENTS,
)
from devops_cli.exceptions import (
    RoadmapRefineError,
    RoadmapRunError,
)
from devops_cli.roadmap.run import (
    DEFAULT_DUE_TABLE,
    MODEL_LANE_ROWS,
    STATUS_LANE_ROWS,
    TRIAGE_LANE_ROWS,
    JobOutcome,
    JobRow,
    build_stub_table,
    read_intake_record,
    run_due_jobs,
)
from devops_cli.roadmap.stores.store import (
    CloseReason,
    GitHubState,
)
from tests.support.fakes.roadmap_store import InMemoryRoadmapStore
from tests.support.roadmap_run import (
    NOW,
    OPENED,
    PLACED,
    PLANNED,
    POLL_KEY,
    REPO,
    REPO_DIR,
    TWENTY_MINUTES_AGO,
    poll_round,
    read_schedule,
    recorded,
    stamp_successes,
)

pytestmark = pytest.mark.usefixtures("keyring_store")


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


# Just under the shortest interval of the hourly rows (refine, 17 minutes), and over all of them.
UNDER_MINUTES = 16


OVER_AGO = NOW - timedelta(minutes=61)


def _stamp_the_default_table(
    tmp_path: Path, *, except_for: tuple[str, ...], **ages: timedelta
) -> None:
    """Stamp each row of the default due table as run a minute ago, so no row is due, except the
    rows in `except_for`, which hold no stamp unless `ages` gives one as the time since its last
    success."""
    now = datetime.now(UTC)
    stamps = {row.name: now - timedelta(minutes=1) for row in DEFAULT_DUE_TABLE}
    for name in except_for:
        del stamps[name]
    stamp_successes(tmp_path, **stamps, **{name: now - age for name, age in ages.items()})


# ── The due table ─────────────────────────────────────────────────────────────


def test_the_table_runs_the_lanes_in_order_and_names_no_release_job() -> None:
    """The status lane's metrics, implement, stage_ready, stage, release_comments, github_status,
    cloudflare_status and pr_conflicts rows run first, then
    the triage lane's intake row, then the model lane's retitle, fix_plan, refine and
    alternatives rows; no row closes items, cuts or starts a release
    (#1360, #1534, #2652, #2659, #2667, #2757, #2865, #3535, #4559, #5061)."""
    assert (
        [row.name for row in DEFAULT_DUE_TABLE],
        DEFAULT_DUE_TABLE == (*STATUS_LANE_ROWS, *TRIAGE_LANE_ROWS, *MODEL_LANE_ROWS),
        sorted(CONST_ROADMAP_WEBHOOK_EVENTS),
    ) == (
        [
            "metrics",
            "implement",
            "stage_ready",
            "stage",
            "release_comments",
            "github_status",
            "cloudflare_status",
            "pr_conflicts",
            "intake",
            "retitle",
            "fix_plan",
            "refine",
            "alternatives",
        ],
        True,
        ["issues"],
    )


def test_due_table_scenarios(seeded_store: InMemoryRoadmapStore, tmp_path: Path) -> None:
    """Intake is due by its interval, a first run, an opened issue's webhook and a reopen a poll
    reads; a close, a label and the store's own write make nothing due. Intake placing a
    critical fix or a P0 item makes refine due in the same round."""
    person = seeded_store.as_actor("alice")
    planned_item = person.seed_issue("Planned bug", milestone=PLANNED, fields=PLACED)
    other_item = person.seed_issue("Backlog item", fields=PLACED)
    under, over = NOW - timedelta(minutes=UNDER_MINUTES), OVER_AGO

    def due(
        batch: dict[tuple[str, str, str], int] | None = None,
        *,
        stamps: dict[str, datetime] | None = None,
        table: Sequence[JobRow] | None = None,
    ) -> tuple[str, ...]:
        stamp_successes(tmp_path, **({"intake": under} if stamps is None else stamps))
        return poll_round(seeded_store, tmp_path, table=table, batch=batch or {})

    hour = (due(), due(stamps={"intake": over}), due(stamps={}))
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
    every = {"intake": under, "refine": under}
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
    sched = {"intake": TWENTY_MINUTES_AGO}

    stamp_successes(tmp_path, **sched)
    spy_wh = StoreSpy(seeded_store)
    res_wh = poll_round(spy_wh, tmp_path, batch={("webhook", "issues", "reopened"): 1})
    calls_wh = spy_wh.calls.count("changes_since")

    stamp_successes(tmp_path, **sched)
    spy_poll = StoreSpy(seeded_store)
    res_poll = poll_round(spy_poll, tmp_path)
    calls_poll = spy_poll.calls.count("changes_since")

    assert (res_wh, calls_wh, res_poll, calls_poll) == (("intake",), 1, ("intake",), 1)


def test_order_and_cross_job_triggers(seeded_store: InMemoryRoadmapStore, tmp_path: Path) -> None:
    """A first round runs metrics, then intake, then refine; with every row run within its interval,
    intake that places a critical fix brings refine in, and a round whose only change is the
    store's own runs nothing (#1360)."""
    calls: list[str] = []

    def make_runner(name: str, outcome: JobOutcome) -> Callable[..., JobOutcome]:
        def run(**_: Any) -> JobOutcome:
            calls.append(name)
            return outcome

        return run

    stubs = {name: make_runner(name, JobOutcome()) for name in ("metrics", "intake", "refine")}
    first = poll_round(seeded_store, tmp_path, table=build_stub_table(stubs), batch={OPENED: 1})
    under = NOW - timedelta(minutes=UNDER_MINUTES)
    stamp_successes(tmp_path, metrics=NOW - timedelta(minutes=5), intake=under, refine=under)
    critical = build_stub_table(
        {"intake": make_runner("intake", JobOutcome(placed_critical_or_p0=True))},
        include_refine=True,
    )
    cascaded = poll_round(seeded_store, tmp_path, table=critical, batch={OPENED: 1})
    stamp_successes(tmp_path, metrics=NOW - timedelta(minutes=5), intake=under, refine=under)
    seeded_store.close_by_hand(
        seeded_store.seed_issue("Closed by the job", fields=PLACED), CloseReason.COMPLETED
    )
    own = poll_round(seeded_store, tmp_path, table=build_stub_table(stubs))
    assert (first, calls[:3], cascaded, own) == (
        ("metrics", "intake", "refine"),
        ["metrics", "intake", "refine"],
        ("intake", "refine"),
        (),
    )


def test_refine_is_due_at_its_interval_after_its_last_success_and_on_a_first_run(
    seeded_store: InMemoryRoadmapStore,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    cli: Callable[..., Any],
) -> None:
    """Refine is due 17 min after its last success, not at 16, and on a first run; the CLI's dry
    run lists it (#1515)."""
    table = build_stub_table(include_refine=True)

    def schedule(refine_age: timedelta | None, now: datetime) -> None:
        ages = {"intake": now - timedelta(minutes=UNDER_MINUTES)}
        stamp_successes(
            tmp_path, **ages, **({} if refine_age is None else {"refine": now - refine_age})
        )

    def due(refine_age: timedelta | None) -> tuple[str, ...]:
        schedule(refine_age, NOW)
        return run_due_jobs(
            REPO, seeded_store, table=table, data_dir=tmp_path, dry_run=True, now=NOW
        )

    at_17, at_16, first = due(timedelta(minutes=17)), due(timedelta(minutes=16)), due(None)
    monkeypatch.setenv("DEVOPS_CLI_DATA_DIR", str(tmp_path))
    _stamp_the_default_table(tmp_path, except_for=("refine",), refine=timedelta(minutes=61))
    result = cli(["roadmap", "run", "--dry-run", "-R", REPO])

    assert (at_17, at_16, first, result.exit_code, "Due: refine\n" in result.output) == (
        ("refine",),
        (),
        ("refine",),
        0,
        True,
    )


def test_stage_is_due_at_its_interval_after_its_last_success_on_a_first_run_and_the_dry_run_lists_it(
    seeded_store: InMemoryRoadmapStore,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    cli: Callable[..., Any],
) -> None:
    """The stage row is due 37 min after its last success, not at 36, and on a first run; the
    CLI's dry run lists it with the status lane, before intake and refine (#2659, #4559)."""
    table = build_stub_table(include_refine=True, include_stage=True)

    def due(stage_age: timedelta | None) -> tuple[str, ...]:
        ages = {
            "intake": NOW - timedelta(minutes=UNDER_MINUTES),
            "refine": NOW - timedelta(minutes=UNDER_MINUTES),
        }
        stamp_successes(
            tmp_path, **ages, **({} if stage_age is None else {"stage": NOW - stage_age})
        )
        return run_due_jobs(
            REPO, seeded_store, table=table, data_dir=tmp_path, dry_run=True, now=NOW
        )

    at_37, at_36, first = due(timedelta(minutes=37)), due(timedelta(minutes=36)), due(None)
    monkeypatch.setenv("DEVOPS_CLI_DATA_DIR", str(tmp_path))
    _stamp_the_default_table(tmp_path, except_for=("intake", "refine", "stage"))
    result = cli(["roadmap", "run", "--dry-run", "-R", REPO])

    assert (
        at_37,
        at_36,
        first,
        result.exit_code,
        "Due: stage, intake, refine\n" in result.output,
    ) == (
        ("stage",),
        (),
        ("stage",),
        0,
        True,
    )


def test_stage_runs_before_refine_and_is_due_in_the_round_after_refine_set_an_item_ready(
    seeded_store: InMemoryRoadmapStore, tmp_path: Path
) -> None:
    """With both rows due, the round runs stage before refine. A refine that set an item Ready
    stamps `stage_due`, so a round five minutes later runs stage again; a refine that set none
    leaves stage not due (#2659, #4796)."""
    ran: list[str] = []

    def rounds(set_ready: bool) -> tuple[tuple[str, ...], tuple[str, ...]]:
        stamp_successes(
            tmp_path, intake=NOW - timedelta(minutes=5), refine=OVER_AGO, stage=OVER_AGO
        )
        table = build_stub_table(
            {
                "refine": recorded(ran, "refine", lambda **_: JobOutcome(set_ready=set_ready)),
                "stage": recorded(ran, "stage"),
            }
        )
        first = poll_round(seeded_store, tmp_path, table=table)
        return first, poll_round(
            seeded_store, tmp_path, table=table, now=NOW + timedelta(minutes=5)
        )

    assert (rounds(True), rounds(False), ran[:2]) == (
        (("stage", "refine"), ("stage",)),
        (("stage", "refine"), ()),
        ["stage", "refine"],
    )


def test_a_refine_round_that_set_an_item_ready_and_failed_another_makes_stage_due(
    seeded_store: InMemoryRoadmapStore, tmp_path: Path
) -> None:
    """A refine round that fails an item after it set another Ready still stamps `stage_due`, and
    the round still fails for refine (#2659, #4796)."""
    stamp_successes(
        tmp_path,
        intake=NOW - timedelta(minutes=5),
        refine=OVER_AGO,
        stage=NOW - timedelta(minutes=5),
    )

    def failing_refine(**_: Any) -> JobOutcome:
        raise RoadmapRefineError("refine failed", failed_items=[7], readied_count=1)

    table = build_stub_table({"refine": failing_refine}, include_stage=True)

    with pytest.raises(RoadmapRunError) as raised:
        poll_round(seeded_store, tmp_path, table=table)
    later = run_due_jobs(
        REPO,
        seeded_store,
        table=table,
        data_dir=tmp_path,
        dry_run=True,
        now=NOW + timedelta(minutes=5),
    )

    assert (
        raised.value.failed_jobs,
        read_schedule(tmp_path).get(CONST_ROADMAP_STAGE_DUE_STAMP),
        later,
    ) == (("refine",), NOW.isoformat(), ("stage", "refine"))


def test_failure_isolation_and_cli_exit(
    seeded_store: InMemoryRoadmapStore,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    cli: Callable[..., Any],
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
        poll_round(seeded_store, tmp_path, table=table, batch={OPENED: 1})
    sched_data = read_schedule(tmp_path)

    def failing_adapter(*_: Any, **__: Any) -> JobOutcome:
        raise RoadmapRunError("Crash [bold red]markup[/bold red]", failed_jobs=("intake",))

    with patch("devops_cli.roadmap.run.run_due_jobs", side_effect=failing_adapter):
        res = cli(["roadmap", "run", "--confirm", "-R", REPO])

    assert (
        exc_info.value.failed_jobs,
        tuple(ran_jobs),
        "intake" not in sched_data,
        "refine" in sched_data,
        res.exit_code,
        "[bold red]markup[/bold red]" in res.output,
    ) == (("intake",), ("intake", "refine"), True, True, 1, True)


def test_state_file_persistence(seeded_store: InMemoryRoadmapStore, tmp_path: Path) -> None:
    """Schedule records success time; subsequent run 20m later sees intake not due."""
    tbl = build_stub_table({"intake": lambda **_: JobOutcome()})
    poll_round(seeded_store, tmp_path, table=tbl, batch={OPENED: 1})
    data = read_schedule(tmp_path)
    second_due = poll_round(
        seeded_store, tmp_path, table=tbl, batch={}, now=NOW + timedelta(minutes=20)
    )
    assert ("intake" in data, second_due) == (True, ())


def test_a_failed_read_of_the_changes_propagates_closed(
    seeded_store: InMemoryRoadmapStore, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A failure reading the changes a poll judges propagates rather than being taken as no
    change."""

    seeded_store.fail_read(
        "changes_since", RuntimeError("GitHub API timeout during the events read")
    )
    with pytest.raises(RuntimeError, match="GitHub API timeout during the events read"):
        poll_round(seeded_store, tmp_path, table=build_stub_table())


def test_intake_left_with_fresh_candidates_runs_at_the_next_poll_and_its_record_fails_closed(
    seeded_store: InMemoryRoadmapStore, tmp_path: Path
) -> None:
    """The record's pending flag makes intake due with nothing else due, even with no trigger
    at all; a record that cannot be read makes it due too, and reading it raises, naming it."""
    stamp_successes(tmp_path, intake=TWENTY_MINUTES_AGO)
    record = tmp_path / REPO_DIR / "intake.json"
    record.write_text(json.dumps({"pending": False}), encoding="utf-8")
    settled = poll_round(seeded_store, tmp_path)
    record.write_text(json.dumps({"pending": True}), encoding="utf-8")
    pending = (poll_round(seeded_store, tmp_path, batch={}), poll_round(seeded_store, tmp_path))
    record.write_text("{not json", encoding="utf-8")
    unreadable = poll_round(seeded_store, tmp_path)
    with pytest.raises(RoadmapRunError, match=r"intake\.json .* Repair it, or remove it"):
        read_intake_record(record)
    assert (settled, pending, unreadable) == ((), (("intake",), ("intake",)), ("intake",))


def test_idle_records_zero_or_one_store_calls(
    seeded_store: InMemoryRoadmapStore, tmp_path: Path
) -> None:
    """Empty batch records 0 store calls; empty poll records exactly 1 changes_since call."""
    recent = NOW - timedelta(minutes=2)
    stamp_successes(
        tmp_path,
        intake=TWENTY_MINUTES_AGO,
        refine=recent,
        retitle=TWENTY_MINUTES_AGO,
        stage=TWENTY_MINUTES_AGO,
        implement=recent,
        stage_ready=recent,
        release_comments=recent,
        github_status=recent,
        cloudflare_status=recent,
        pr_conflicts=recent,
        metrics=recent,
        alternatives=recent,
        fix_plan=recent,
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
    seeded_store: InMemoryRoadmapStore,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    cli: Callable[..., Any],
) -> None:
    """Stub called with no confirm argument; CLI without confirm or with dry-run runs none."""
    received_args: list[dict[str, Any]] = []

    def stub_runner(**kwargs: Any) -> JobOutcome:
        received_args.append(kwargs)
        return JobOutcome()

    tbl = build_stub_table({"intake": stub_runner})
    poll_round(seeded_store, tmp_path, table=tbl, batch={OPENED: 1})
    had_confirm = "confirm" in received_args[0] if received_args else True

    monkeypatch.setenv("DEVOPS_CLI_DATA_DIR", str(tmp_path))
    _stamp_the_default_table(tmp_path, except_for=("stage_ready",), stage_ready=timedelta(days=1))
    res_plain = cli(["roadmap", "run", "-R", REPO])
    res_dry = cli(["roadmap", "run", "--dry-run", "--confirm", "-R", REPO])
    stamped_before = read_schedule(tmp_path)["stage_ready"]
    res_confirm = cli(["roadmap", "run", "--confirm", "-R", REPO])

    assert (
        had_confirm,
        res_plain.exit_code,
        "Due: stage_ready" in res_plain.output,
        res_dry.exit_code,
        "Due: stage_ready" in res_dry.output,
        res_confirm.exit_code,
        read_schedule(tmp_path)["stage_ready"] != stamped_before,
    ) == (False, 0, True, 0, True, 0, True)
