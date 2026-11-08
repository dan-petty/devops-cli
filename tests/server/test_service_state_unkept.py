"""A state record that the roadmap Service could not write shows on its /metrics (#4048).

The Service keeps three records on its volume: the request budget, the halt and the failure
ledger. A write error stays one error log line, and the Service goes on with memory only (#2474).
The gauge `devops_cli_service_state_unkept` also shows it, by `record`: 1 after a write error, 0
after the next write that works. The budget, the pause and the ledger are real; the fault is a
record whose parent directory is a regular file, which the operating system refuses.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from pathlib import Path

import pytest

from devops_cli.config.constants import (
    CONST_SERVICE_BUDGET_FILENAME,
    CONST_SERVICE_FAILURES_FILENAME,
    CONST_SERVICE_HALT_FILENAME,
    CONST_SERVICE_METRIC_STATE_UNKEPT,
)
from devops_cli.exceptions import RoadmapRunError
from devops_cli.roadmap.run import FailureLedger
from devops_cli.server.service import RequestBudget, RoundPause
from devops_cli.telemetry.metrics import GLOBAL_METRICS
from devops_cli.telemetry.tracer import reset_tracer

REPO = "example-org/repo1"
NOW = datetime(2026, 11, 8, 12, tzinfo=UTC)
RECORDS = ("budget", "halt", "ledger")


@pytest.fixture(autouse=True)
def _reset_metrics() -> None:
    GLOBAL_METRICS.reset()
    reset_tracer()


def _clock() -> datetime:
    return NOW


def _refused(_: Exception) -> bool:
    return True


def _series() -> dict[str, float]:
    """The series of the gauge that exist, by `record`: a record never written has none."""
    found = {
        record: GLOBAL_METRICS.registry.get_sample_value(
            CONST_SERVICE_METRIC_STATE_UNKEPT, {"record": record}
        )
        for record in RECORDS
    }
    return {record: value for record, value in found.items() if value is not None}


def _blocked(tmp_path: Path, name: str) -> Path:
    """A record that cannot be written: its parent directory is a regular file."""
    (tmp_path / "volume").write_text("not a directory", encoding="utf-8")
    return tmp_path / "volume" / name


def _repair(tmp_path: Path) -> None:
    """Make the parent of the blocked record a directory, so the next write works."""
    (tmp_path / "volume").unlink()
    (tmp_path / "volume").mkdir()


def _write_budget(record: Path) -> None:
    RequestBudget(_clock, 100, record=record).admit()


def _write_halt(record: Path) -> None:
    RoundPause(_clock, refusal=_refused, halt_record=record).after(RuntimeError("refused"), REPO)


def _write_ledger(record: Path) -> None:
    FailureLedger(record=record).failed(REPO, "stage", "input", "AIClientError")


WRITERS = {
    "budget": (CONST_SERVICE_BUDGET_FILENAME, _write_budget),
    "halt": (CONST_SERVICE_HALT_FILENAME, _write_halt),
    "ledger": (CONST_SERVICE_FAILURES_FILENAME, _write_ledger),
}


def test_a_budget_write_error_logs_sets_the_gauge_and_raises_nothing_in_admit(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """The first request cannot be kept: `admit` still gives it its place, and the gauge for the
    budget is 1 while the other records stay unset. After the volume is repaired, the next request
    is kept and the gauge is 0."""
    record = _blocked(tmp_path, CONST_SERVICE_BUDGET_FILENAME)
    budget = RequestBudget(_clock, 100, record=record)

    with caplog.at_level(logging.ERROR):
        budget.admit()
    failed = (budget.spent(), _series(), [r.getMessage() for r in caplog.records])
    _repair(tmp_path)
    budget.admit()

    assert (failed[0], failed[1], len(failed[2]), "Could not write" in failed[2][0]) == (
        1,
        {"budget": 1.0},
        1,
        True,
    )
    assert (budget.spent(), record.exists(), _series()) == (
        2,
        True,
        {"budget": 0.0},
    )


def test_a_halt_write_error_sets_the_gauge_for_the_halt_record(tmp_path: Path) -> None:
    """A refused identity halts the rounds in memory when the halt file cannot be written."""
    pause = RoundPause(
        _clock,
        refusal=_refused,
        halt_record=_blocked(tmp_path, CONST_SERVICE_HALT_FILENAME),
    )

    pause.after(RuntimeError("refused"), REPO)

    assert (pause.halted(), _series()) == (True, {"halt": 1.0})


def test_a_ledger_write_error_sets_the_gauge_for_the_ledger_record(tmp_path: Path) -> None:
    """A failed round is counted in memory when the ledger file cannot be written, and the next
    write that works, a round that succeeds, clears the gauge."""
    record = _blocked(tmp_path, CONST_SERVICE_FAILURES_FILENAME)
    ledger = FailureLedger(record=record)

    rounds = ledger.failed(REPO, "stage", "input", "AIClientError")
    failed = _series()
    _repair(tmp_path)
    ledger.succeeded(REPO, "stage")

    assert (rounds, failed, _series()) == (
        1,
        {"ledger": 1.0},
        {"ledger": 0.0},
    )


@pytest.mark.parametrize("record", RECORDS)
def test_each_record_has_its_own_series_that_a_good_write_sets_to_0(
    record: str, tmp_path: Path
) -> None:
    """The gauge has one series for each record. A write that works creates only its own series, at
    0, so the three series exist once the three records have been written."""
    name, write = WRITERS[record]

    write(tmp_path / name)

    assert (_series(), (tmp_path / name).exists()) == ({record: 0.0}, True)


@pytest.mark.parametrize("record", RECORDS)
def test_a_good_write_after_a_write_error_sets_only_its_own_series_to_0(
    record: str, tmp_path: Path
) -> None:
    """The write error of one record sets only its own series, and the next good write of that
    record clears it."""
    name, write = WRITERS[record]
    blocked = _blocked(tmp_path, name)

    write(blocked)
    failed = _series()
    _repair(tmp_path)
    write(blocked)

    assert (failed, _series()) == ({record: 1.0}, {record: 0.0})


def test_a_record_that_cannot_be_read_still_raises_and_sets_no_gauge(tmp_path: Path) -> None:
    """The gauge shows a write that failed. A record that cannot be read at the start is an error
    that stops the start (#2474), and it leaves the gauge alone."""
    record = tmp_path / CONST_SERVICE_FAILURES_FILENAME
    record.write_text("{not json", encoding="utf-8")

    with pytest.raises(RoadmapRunError) as raised:
        FailureLedger(record=record)

    assert (raised.value.details, _series()) == ({"path": str(record)}, {})
