"""A suspended roadmap row runs one probe round after the wait of its failure class (#4065).

The ledger suspends a row after its limit of failed rounds in a row on one input. Before this
change only new input ended the suspension, so an outage that ends on its own left the row
`intake` suspended. Now the ledger keeps, for a suspended row, the time `retry_after`: the time of
the last failed round plus `RETRY_AFTER` of the failure class (#4060). A row past that time runs
one probe round. A failed probe round sets a new time, and a success clears the record. A new
input ends the suspension at once, as before.

Only the triage lane reads changes, so the wait changes the row `intake` only. The status lane and
the model lane put the hour into the input of a round (#2757), so their rows already run again each
hour. The rounds below run the row `intake` over `InMemoryRoadmapStore`, with a runner that fails
as the test says.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable, Mapping
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from devops_cli.ai.client.models import AIClientError, StructuredOutputValidationError
from devops_cli.config.constants import (
    CONST_SERVICE_FAILURES_FILENAME,
    CONST_SERVICE_METRIC_JOB_RETRY_AFTER_SECONDS,
    CONST_SERVICE_METRIC_JOB_SUSPENDED,
)
from devops_cli.config.defaults import DEFAULT_SERVICE_MAX_FAILED_ROUNDS
from devops_cli.exceptions import (
    GitHubOperationError,
    RoadmapItemChangedError,
    RoadmapRunError,
    RoadmapStageError,
)
from devops_cli.roadmap.failure import RETRY_AFTER, FailureClass
from devops_cli.roadmap.run import FailureLedger, JobOutcome, build_stub_table, run_due_jobs
from devops_cli.telemetry.metrics import GLOBAL_METRICS
from tests.support.fakes.roadmap_store import InMemoryRoadmapStore

pytestmark = pytest.mark.usefixtures("keyring_store")

REPO = "example-org/repo1"
START = datetime(2026, 11, 8, 12, tzinfo=UTC)
POLL = {("poll", "", ""): 1}
WEBHOOK = {("webhook", "issues", "labeled"): 1}
LIMIT = DEFAULT_SERVICE_MAX_FAILED_ROUNDS
STEP = timedelta(minutes=30)
HOUR = timedelta(hours=1)

# An error and the class that `CLASS_BY_EXCEPTION` gives it. A `ValueError` is no error of the
# project, so it reads as `ci_infra`, the class of an error that no entry names.
FAILURES: list[tuple[Callable[[], Exception], FailureClass]] = [
    (lambda: AIClientError("the provider is down"), FailureClass.PROVIDER),
    (lambda: StructuredOutputValidationError("no schema fits"), FailureClass.PARSER),
    (lambda: RoadmapStageError("a plan broke a rule"), FailureClass.PLAN_DEFECT),
    (lambda: GitHubOperationError("the write failed"), FailureClass.CI_INFRA),
    (lambda: ValueError("a runner raised a plain error"), FailureClass.CI_INFRA),
    (lambda: RoadmapItemChangedError("the item changed"), FailureClass.HEAD_MOVED),
]
FAILURE_IDS = ["provider", "parser", "plan_defect", "ci_infra", "plain_error", "head_moved"]


@pytest.fixture(autouse=True)
def _fresh_metrics() -> None:
    GLOBAL_METRICS.reset()


class _World:
    """Rounds of the row `intake` over one repository, one store and one ledger kept in a file.
    The runner raises `error()` until `healthy` is set, then succeeds."""

    def __init__(
        self,
        tmp_path: Path,
        error: Callable[[], Exception] = FAILURES[0][0],
        *,
        ledger: FailureLedger | None = None,
    ) -> None:
        self.now = START
        self.store = InMemoryRoadmapStore(clock=lambda: self.now)
        self.issue = self.store.seed_issue("An item")
        self.record = tmp_path / CONST_SERVICE_FAILURES_FILENAME
        self.ledger = ledger or FailureLedger(record=self.record)
        self.error = error
        self.healthy = False
        self.ran = 0
        self._data_dir = tmp_path
        self._table = build_stub_table({"intake": self._run})

    def _run(self, **_: Any) -> JobOutcome:
        self.ran += 1
        if self.healthy:
            return JobOutcome()
        raise self.error()

    def round(
        self, step: timedelta = STEP, batch: Mapping[tuple[str, str, str], int] = POLL
    ) -> bool:
        """One round `step` after the last, started by `batch`; whether the row ran in it."""
        self.now += step
        before = self.ran
        try:
            run_due_jobs(
                REPO,
                self.store,
                batch,
                table=self._table,
                data_dir=self._data_dir,
                now=self.now,
                failures=self.ledger,
            )
        except RoadmapRunError:
            pass
        return self.ran > before

    def suspend(self) -> None:
        """The rounds that make the row fail its limit, and the one that the suspension skips."""
        assert [self.round() for _ in range(LIMIT)] == [True] * LIMIT
        assert self.round() is False

    def minutes_until_run(self) -> int:
        """The minutes from now to the next round that runs the row, with a poll each `STEP`."""
        start = self.now
        for _ in range(int(timedelta(days=2) / STEP)):
            if self.round():
                return int((self.now - start) / timedelta(minutes=1))
        raise AssertionError("the row did not run in 2 days")

    def entries(self) -> list[list[Any]]:
        """The entries of the ledger file."""
        loaded: list[list[Any]] = json.loads(self.record.read_text(encoding="utf-8"))
        return loaded


def _gauge(name: str, row: str = "intake", **extra: str) -> float:
    return float(GLOBAL_METRICS.get_gauge_value(name, labels={"repo": REPO, "row": row, **extra}))


# ── The row runs after its time (retry_after) ─────────────────────────────────────────────


@pytest.mark.parametrize(("error", "klass"), FAILURES, ids=FAILURE_IDS)
def test_a_suspended_row_runs_after_its_retry_after_time_with_no_new_input(
    tmp_path: Path, error: Callable[[], Exception], klass: FailureClass
) -> None:
    """The wait is `RETRY_AFTER` of the class of the last failure, from the one table (#4060). A
    class that waits for no time runs at the next round. No comment and no webhook comes between."""
    world = _World(tmp_path, error)
    world.suspend()

    waited = world.minutes_until_run()

    assert waited == max(RETRY_AFTER[klass], STEP) // timedelta(minutes=1)


def test_a_row_runs_again_after_its_retry_after_time_when_the_fault_is_fixed(
    tmp_path: Path,
) -> None:
    world = _World(tmp_path)
    world.suspend()
    world.healthy = True

    assert (world.round(HOUR - STEP), world.round(STEP)) == (False, True)


def test_the_ledger_sets_retry_after_only_for_a_row_that_reached_its_limit(
    tmp_path: Path,
) -> None:
    """Rounds below the limit leave the field null; the round of the limit sets it from the time of
    that round and the wait of its class."""
    record = tmp_path / CONST_SERVICE_FAILURES_FILENAME
    ledger = FailureLedger(limit=3, record=record)
    kept: list[list[Any]] = []
    for step in range(3):
        ledger.failed(REPO, "intake", "input", FailureClass.PROVIDER.value, START + step * STEP)
        kept.append(json.loads(record.read_text(encoding="utf-8"))[0])

    assert [len(entry) for entry in kept] == [6, 6, 6]
    assert [entry[5] for entry in kept[:2]] == [None, None]
    assert datetime.fromisoformat(kept[2][5]) == START + 2 * STEP + HOUR


def test_the_ledger_is_suspended_before_retry_after_and_not_from_that_time_on() -> None:
    ledger = FailureLedger(limit=3)
    for step in range(3):
        ledger.failed(REPO, "intake", "input", FailureClass.PROVIDER.value, START + step * STEP)
    retry = START + 2 * STEP + HOUR

    assert [
        ledger.suspended(REPO, "intake", "input", retry - timedelta(seconds=1)),
        ledger.suspended(REPO, "intake", "input", retry),
        ledger.suspended(REPO, "intake", "other", START),
    ] == [True, False, False]


# ── A probe round (half_open) ─────────────────────────────────────────────────────────────


def test_a_failed_half_open_probe_round_sets_a_new_retry_after_time(tmp_path: Path) -> None:
    """The probe round at `retry_after` fails on the same input: the count grows and the new time is
    the time of that round plus the wait again. The row then waits for it."""
    world = _World(tmp_path)
    world.suspend()
    assert world.round(HOUR - STEP) is False
    probe_ran = world.round(STEP)
    kept = world.entries()[0]

    assert (
        probe_ran,
        kept[2],
        datetime.fromisoformat(kept[5]) == world.now + HOUR,
        world.round(),
        world.round(),
    ) == (True, LIMIT + 1, True, False, True)


def test_a_half_open_probe_round_that_succeeds_clears_the_record(tmp_path: Path) -> None:
    world = _World(tmp_path)
    world.suspend()
    world.healthy = True
    assert world.round(HOUR - STEP) is False
    probe_ran = world.round(STEP)

    assert (
        probe_ran,
        world.entries(),
        _gauge(CONST_SERVICE_METRIC_JOB_SUSPENDED, **{"class": "provider"}),
    ) == (True, [], 0.0)


def test_a_row_that_succeeded_after_a_probe_round_starts_its_count_again(tmp_path: Path) -> None:
    """After the success the next failures count from 1, so the row needs the limit of failed
    rounds again before it is suspended."""
    world = _World(tmp_path)
    world.suspend()
    world.healthy = True
    world.round(HOUR)
    world.healthy = False

    assert [world.round() for _ in range(LIMIT + 1)] == [True] * LIMIT + [False]


# ── New input (new_input) ─────────────────────────────────────────────────────────────────


def test_a_new_input_runs_a_suspended_row_at_once_before_its_retry_after_time(
    tmp_path: Path,
) -> None:
    """A webhook is new input: the time of the round is in the digest. The row runs at once, and a
    failure on the new input restarts the count at 1 with no retry time."""
    world = _World(tmp_path)
    world.suspend()

    ran = world.round(timedelta(minutes=5), WEBHOOK)
    kept = world.entries()[0]

    assert (ran, kept[2], kept[5]) == (True, 1, None)


def test_a_comment_of_a_person_is_new_input_before_the_retry_after_time(tmp_path: Path) -> None:
    world = _World(tmp_path)
    world.suspend()
    world.now += timedelta(minutes=5)
    world.store.seed_comment(
        world.issue, "An answer", author_login="alice", author_association="OWNER"
    )

    assert world.round(timedelta(minutes=5)) is True


def test_a_new_input_after_the_limit_restarts_the_row_on_the_ledger_alone() -> None:
    ledger = FailureLedger(limit=3)
    for step in range(3):
        ledger.failed(REPO, "intake", "input", FailureClass.PARSER.value, START + step * STEP)

    assert ledger.suspended(REPO, "intake", "new input", START + STEP) is False


# ── A record from before this change (old_record) ─────────────────────────────────────────


def test_an_old_record_of_five_fields_loads_and_keeps_the_digest_rule(tmp_path: Path) -> None:
    """The entry has no `retry_after`. The row is suspended at any later time on the same input,
    runs on a new input, and the ledger does not raise."""
    record = tmp_path / CONST_SERVICE_FAILURES_FILENAME
    old = [[REPO, "intake", 3, "input", ["GitHubOperationError"] * 3]]
    record.write_text(json.dumps(old), encoding="utf-8")

    ledger = FailureLedger(record=record)

    assert [
        ledger.suspended(REPO, "intake", "input", START),
        ledger.suspended(REPO, "intake", "input", START + timedelta(days=30)),
        ledger.suspended(REPO, "intake", "other", START),
        ledger.causes(REPO, "intake"),
    ] == [True, True, False, ("GitHubOperationError",) * 3]


def test_an_old_record_of_four_fields_loads_and_keeps_the_digest_rule(tmp_path: Path) -> None:
    record = tmp_path / CONST_SERVICE_FAILURES_FILENAME
    record.write_text(json.dumps([[REPO, "intake", 3, "input"]]), encoding="utf-8")

    ledger = FailureLedger(record=record)

    assert [
        ledger.suspended(REPO, "intake", "input", START + timedelta(days=30)),
        ledger.causes(REPO, "intake"),
    ] == [True, ("unknown",) * 3]


def test_an_old_record_shows_the_unknown_class_and_no_seconds_on_the_gauges(
    tmp_path: Path,
) -> None:
    """An exception name is no class, so the label reads `unknown`, and a row with no retry time has
    no seconds left."""
    record = tmp_path / CONST_SERVICE_FAILURES_FILENAME
    record.write_text(
        json.dumps([[REPO, "intake", 3, "input", ["GitHubOperationError"] * 3]]), encoding="utf-8"
    )

    ledger = FailureLedger(record=record)
    ledger.suspended(REPO, "intake", "input", START)

    unknown = {"class": "unknown"}
    assert (
        _gauge(CONST_SERVICE_METRIC_JOB_SUSPENDED, **unknown),
        _gauge(CONST_SERVICE_METRIC_JOB_RETRY_AFTER_SECONDS, **unknown),
    ) == (1.0, 0.0)


def test_an_old_record_keeps_the_row_suspended_in_a_round_for_30_days_of_one_input(
    tmp_path: Path,
) -> None:
    """The record that the new ledger wrote is cut back to the form of the older image: 5 fields,
    the exception name as the cause. A restart loads it, and polls with no new input run no row."""
    first = _World(tmp_path)
    first.suspend()
    (repo, row, rounds, digest, *_) = first.entries()[0]
    first.record.write_text(
        json.dumps([[repo, row, rounds, digest, ["GitHubOperationError"] * rounds]]),
        encoding="utf-8",
    )
    restarted = _World(tmp_path, ledger=FailureLedger(record=first.record))
    restarted.now = first.now

    polls = [restarted.round(timedelta(days=1)) for _ in range(30)]

    assert (polls, restarted.ran) == ([False] * 30, 0)


def test_an_old_record_is_written_in_the_new_form_by_its_next_change(tmp_path: Path) -> None:
    record = tmp_path / CONST_SERVICE_FAILURES_FILENAME
    record.write_text(json.dumps([[REPO, "intake", 3, "input", ["x"] * 3]]), encoding="utf-8")
    ledger = FailureLedger(record=record)

    ledger.failed(REPO, "intake", "other", FailureClass.PROVIDER.value, START)

    assert json.loads(record.read_text(encoding="utf-8")) == [
        [REPO, "intake", 1, "other", ["provider"], None]
    ]


@pytest.mark.parametrize(
    "content",
    [
        pytest.param('{"not": "a list"}', id="not_a_list"),
        pytest.param(json.dumps([[REPO, "intake", 3, "input", [], "soon"]]), id="retry_not_a_time"),
        pytest.param("[[", id="not_json"),
    ],
)
def test_an_unreadable_record_still_raises(tmp_path: Path, content: str) -> None:
    record = tmp_path / CONST_SERVICE_FAILURES_FILENAME
    record.write_text(content, encoding="utf-8")

    with pytest.raises(RoadmapRunError) as raised:
        FailureLedger(record=record)

    assert raised.value.details == {"path": str(record)}


# ── The class as the cause (class_cause) ──────────────────────────────────────────────────


@pytest.mark.parametrize(("error", "klass"), FAILURES, ids=FAILURE_IDS)
def test_the_ledger_file_holds_the_class_value_and_the_gauge_has_the_class_label(
    tmp_path: Path, error: Callable[[], Exception], klass: FailureClass
) -> None:
    """The cause of each failed round is the class value, not the exception name. An error that is
    no `DevOpsCLIError` is `ci_infra`, as an unknown record is for `retry_after()`."""
    world = _World(tmp_path, error)
    world.suspend()
    kept = world.entries()[0]

    assert (
        kept[4],
        _gauge(CONST_SERVICE_METRIC_JOB_SUSPENDED, **{"class": klass.value}),
    ) == ([klass.value] * LIMIT, 1.0)


def test_a_class_that_changes_moves_the_suspended_gauge_to_the_new_class_and_its_wait() -> None:
    """Two provider failures and then a parser failure on one input: the last class decides the
    wait, the gauge of the old class is 0 and a series of no class is left at 1."""
    ledger = FailureLedger(limit=3)
    ledger.failed(REPO, "intake", "input", FailureClass.PROVIDER.value, START)
    ledger.failed(REPO, "intake", "input", FailureClass.PROVIDER.value, START)
    ledger.failed(REPO, "intake", "input", FailureClass.PARSER.value, START)
    retry = START + RETRY_AFTER[FailureClass.PARSER]

    assert [
        _gauge(CONST_SERVICE_METRIC_JOB_SUSPENDED, **{"class": "provider"}),
        _gauge(CONST_SERVICE_METRIC_JOB_SUSPENDED, **{"class": "parser"}),
        ledger.suspended(REPO, "intake", "input", retry - timedelta(seconds=1)),
        ledger.suspended(REPO, "intake", "input", retry),
    ] == [0.0, 1.0, True, False]


def test_a_cleared_row_sets_the_gauge_of_its_last_class_to_zero() -> None:
    ledger = FailureLedger(limit=3)
    for _ in range(3):
        ledger.failed(REPO, "intake", "input", FailureClass.CI_INFRA.value, START)

    ledger.succeeded(REPO, "intake")

    assert [
        _gauge(CONST_SERVICE_METRIC_JOB_SUSPENDED, **{"class": "ci_infra"}),
        _gauge(CONST_SERVICE_METRIC_JOB_RETRY_AFTER_SECONDS, **{"class": "ci_infra"}),
    ] == [0.0, 0.0]


def test_the_seconds_gauge_holds_the_seconds_left_as_of_the_last_check() -> None:
    ledger = FailureLedger(limit=3)
    for _ in range(3):
        ledger.failed(REPO, "intake", "input", FailureClass.PROVIDER.value, START)
    seconds = {"class": "provider"}
    after_failure = _gauge(CONST_SERVICE_METRIC_JOB_RETRY_AFTER_SECONDS, **seconds)
    ledger.suspended(REPO, "intake", "input", START + timedelta(minutes=10))
    after_check = _gauge(CONST_SERVICE_METRIC_JOB_RETRY_AFTER_SECONDS, **seconds)
    ledger.suspended(REPO, "intake", "input", START + HOUR)
    after_time = _gauge(CONST_SERVICE_METRIC_JOB_RETRY_AFTER_SECONDS, **seconds)

    assert (after_failure, after_check, after_time) == (3600.0, 3000.0, 0.0)


def test_the_suspension_log_line_names_the_class_and_the_retry_time(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    world = _World(tmp_path)
    with caplog.at_level(logging.WARNING):
        world.suspend()
    (line,) = [r.getMessage() for r in caplog.records if "failed" in r.getMessage()]

    assert (
        "provider" in line,
        (START + (LIMIT - 1) * STEP + HOUR).isoformat() in line,
        "until its input changes" in line,
    ) == (True, True, False)
