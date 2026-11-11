"""The seconds of each roadmap row: one histogram sample for each row that ran, under its
repository, row and result (#4058).

The rounds run over `run_due_jobs` with rows whose runners move the fake clock by a set number
of seconds, so a sample holds a value the test knows. The collector is the fake of the OTLP
fixture, and a histogram point is read as (attributes, count, sum).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

from devops_cli.exceptions import RoadmapRunError, ServiceStoppingError
from devops_cli.roadmap.run import (
    DEFAULT_DUE_TABLE,
    FailureLedger,
    JobOutcome,
    JobRow,
    run_due_jobs,
)
from tests.support.paths import REPO_ROOT
from tests.support.roadmap_run import NOW, OPENED, POLL_KEY, REPO, SimulatedGit

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from tests.support.fakes.clock import ClockFake
    from tests.support.fakes.otlp import FakeCollector
    from tests.support.fakes.roadmap_store import InMemoryRoadmapStore

pytestmark = pytest.mark.usefixtures("keyring_store")

ROW_SECONDS = "devops_cli_roadmap_row_seconds"


def _row(
    name: str, runner: Callable[..., JobOutcome], *, on: tuple[str, str, str] = POLL_KEY
) -> JobRow:
    """A row that a trigger of the key `on` makes due."""
    return JobRow(name=name, batch_keys=(on,), runner=runner)


def _takes(clock: ClockFake, seconds: float) -> Callable[..., JobOutcome]:
    """A runner that takes `seconds` on the fake clock and succeeds."""

    def run(**_: Any) -> JobOutcome:
        clock.shift(seconds)
        return JobOutcome()

    return run


def _fails_after(clock: ClockFake, seconds: float, error: Exception) -> Callable[..., JobOutcome]:
    """A runner that takes `seconds` on the fake clock and then raises `error`."""

    def run(**_: Any) -> JobOutcome:
        clock.shift(seconds)
        raise error

    return run


def _samples(otlp: FakeCollector) -> list[tuple[dict[str, Any], int, float]]:
    """Each point of the row seconds histogram, as (attributes, count, sum), in a stable order."""
    found = []
    for metric in otlp.metrics:
        if metric["name"] != ROW_SECONDS:
            continue
        for point in metric["exponentialHistogram"]["dataPoints"]:
            attrs = {a["key"]: next(iter(a["value"].values())) for a in point["attributes"]}
            found.append((attrs, int(point["count"]), point["sum"]))
    return sorted(found, key=lambda sample: sorted(sample[0].items()))


def _round(
    store: InMemoryRoadmapStore,
    tmp_path: Path,
    table: tuple[JobRow, ...],
    *,
    failures: FailureLedger | None = None,
    batch: dict[tuple[str, str, str], int] | None = None,
) -> None:
    """One round of `table` for the repository, in the status lane. A round with a failed row
    raises, and the test reads the samples."""
    try:
        run_due_jobs(
            REPO,
            store,
            batch or {POLL_KEY: 1},
            table=table,
            data_dir=tmp_path,
            now=NOW,
            failures=failures,
            lane="status",
        )
    except RoadmapRunError:
        pass


def test_a_round_emits_one_row_seconds_sample_for_each_row_that_ran(
    seeded_store: InMemoryRoadmapStore, tmp_path: Path, clock: ClockFake, otlp: FakeCollector
) -> None:
    """Each row that ran adds one sample of its own seconds under `repo`, `row` and `result`, and
    no other label: the collector sets `job` from the resource and would lose a label of that
    name."""
    table = (_row("metrics", _takes(clock, 2.5)), _row("implement", _takes(clock, 7.0)))

    _round(seeded_store, tmp_path, table)

    assert _samples(otlp) == [
        ({"repo": REPO, "row": "implement", "result": "success"}, 1, 7.0),
        ({"repo": REPO, "row": "metrics", "result": "success"}, 1, 2.5),
    ]


def test_a_row_that_runs_in_two_rounds_adds_a_sample_for_each_round(
    seeded_store: InMemoryRoadmapStore, tmp_path: Path, clock: ClockFake, otlp: FakeCollector
) -> None:
    """The series of a row holds the count and the sum of its rounds, so the mean is their ratio."""
    table = (_row("metrics", _takes(clock, 1.5)),)

    _round(seeded_store, tmp_path, table)
    _round(seeded_store, tmp_path, table)

    assert _samples(otlp) == [({"repo": REPO, "row": "metrics", "result": "success"}, 2, 3.0)]


def test_not_run_a_row_that_is_not_due_adds_no_row_seconds_sample(
    seeded_store: InMemoryRoadmapStore, tmp_path: Path, clock: ClockFake, otlp: FakeCollector
) -> None:
    """A row that no trigger of the batch makes due is not run and not timed."""
    table = (
        _row("metrics", _takes(clock, 2.5)),
        _row("refine", _takes(clock, 9.0), on=OPENED),
    )

    _round(seeded_store, tmp_path, table)

    assert [(attrs["row"], total) for attrs, _, total in _samples(otlp)] == [("metrics", 2.5)]


def test_not_run_a_row_that_the_ledger_suspends_adds_no_row_seconds_sample(
    seeded_store: InMemoryRoadmapStore, tmp_path: Path, clock: ClockFake, otlp: FakeCollector
) -> None:
    """A row that failed its limit of rounds on the same input does not run, so the round that
    skips it adds no sample for it. The two rounds that failed added their samples."""
    ledger = FailureLedger(limit=2)
    table = (
        _row("implement", _fails_after(clock, 4.0, RuntimeError("the row failed"))),
        _row("metrics", _takes(clock, 1.0)),
    )

    for _ in range(3):
        _round(seeded_store, tmp_path, table, failures=ledger)

    assert _samples(otlp) == [
        ({"repo": REPO, "row": "implement", "result": "error"}, 2, 8.0),
        ({"repo": REPO, "row": "metrics", "result": "success"}, 3, 3.0),
    ]


def test_not_run_a_row_that_a_clone_failure_keeps_from_running_adds_no_row_seconds_sample(
    seeded_store: InMemoryRoadmapStore,
    tmp_path: Path,
    clock: ClockFake,
    otlp: FakeCollector,
    git_sim: SimulatedGit,
) -> None:
    """A row that needs a clone the Service could not make never reaches its runner, so no time
    passed in the row and no sample is added."""
    ran: list[str] = []

    def runner(**_: Any) -> JobOutcome:
        ran.append("ran")
        clock.shift(3.0)
        return JobOutcome()

    table = tuple(
        JobRow(name=name, batch_keys=(POLL_KEY,), runner=runner, needs_clone=True)
        for name in ("metrics", "refine")
    )

    with pytest.raises(RoadmapRunError) as raised:
        run_due_jobs(
            REPO,
            seeded_store,
            {POLL_KEY: 1},
            table=table,
            data_dir=tmp_path,
            remote_url=str(tmp_path / "missing_remote"),
            now=NOW,
            lane="status",
        )

    assert (ran, _samples(otlp), list(raised.value.failed_jobs)) == ([], [], ["metrics", "refine"])


@pytest.mark.parametrize(
    ("error", "result"),
    [
        (RuntimeError("the row failed"), "error"),
        (ServiceStoppingError("the Service is stopping"), "stopped"),
    ],
    ids=["error_result", "stopped_result"],
)
def test_a_row_that_raises_adds_a_row_seconds_sample_with_the_result_of_its_error(
    error: Exception,
    result: str,
    seeded_store: InMemoryRoadmapStore,
    tmp_path: Path,
    clock: ClockFake,
    otlp: FakeCollector,
) -> None:
    """A failure adds the seconds up to the error under `error`, and a stop of the Service adds
    them under `stopped`: the same two values as the job counter."""
    table = (_row("implement", _fails_after(clock, 4.0, error)),)

    _round(seeded_store, tmp_path, table)

    assert _samples(otlp) == [({"repo": REPO, "row": "implement", "result": result}, 1, 4.0)]


def test_a_run_with_no_lane_adds_the_row_seconds_sample_too(
    seeded_store: InMemoryRoadmapStore, tmp_path: Path, clock: ClockFake, otlp: FakeCollector
) -> None:
    """The seconds of a row do not depend on the lane, so a run of the command line, which has no
    lane and counts no job, adds the sample."""
    table = (_row("metrics", _takes(clock, 2.0)),)

    run_due_jobs(
        REPO, seeded_store, {POLL_KEY: 1}, table=table, data_dir=tmp_path, now=NOW, lane=None
    )

    assert _samples(otlp) == [({"repo": REPO, "row": "metrics", "result": "success"}, 1, 2.0)]


def test_the_row_seconds_series_of_a_repository_are_bounded_by_the_rows_and_results() -> None:
    """The label `row` holds one of the 12 rows of the due table and `result` one of 3 values, so
    one repository adds at most 36 series. The histogram is exponential, which Prometheus 3 stores
    as one native histogram per series, so the buckets add none."""
    from devops_cli.config.constants import (
        CONST_SERVICE_JOB_RESULT_ERROR,
        CONST_SERVICE_JOB_RESULT_STOPPED,
        CONST_SERVICE_JOB_RESULT_SUCCESS,
    )

    results = {
        CONST_SERVICE_JOB_RESULT_SUCCESS,
        CONST_SERVICE_JOB_RESULT_ERROR,
        CONST_SERVICE_JOB_RESULT_STOPPED,
    }

    assert (len({row.name for row in DEFAULT_DUE_TABLE}), len(results)) == (12, 3)


def test_the_row_seconds_instrument_is_declared_and_documented() -> None:
    """The instrument is a histogram of seconds with the labels `repo`, `row` and `result`, and
    docs/TELEMETRY.md lists it, with its series count."""
    from devops_cli.telemetry.instruments import INSTRUMENTS, InstrumentKind

    declared = {instrument.name: instrument for instrument in INSTRUMENTS}
    documented = (REPO_ROOT / "docs" / "TELEMETRY.md").read_text(encoding="utf-8")

    assert (
        ROW_SECONDS in declared
        and declared[ROW_SECONDS].kind == InstrumentKind.HISTOGRAM
        and declared[ROW_SECONDS].unit == "s",
        ROW_SECONDS in documented,
    ) == (True, True)
