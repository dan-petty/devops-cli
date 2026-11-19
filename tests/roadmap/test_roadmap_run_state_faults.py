"""Offline fault-injection suite for the Service state files (#3075).

The four cases run offline on paths under tmp_path:
1. A halt record that cannot be written: write a regular file at tmp_path / "blocker", give
   RoundPause the record tmp_path / "blocker" / "service-halt.json" and a refusal reader that
   answers True, then call after; the record does not exist at construction, the write raises
   NotADirectoryError, one state_unkept error line names the record and that class, halted() is
   True, the next round starts nothing, and no record file exists.
2. An unreadable schedule.json: the file holds invalid JSON, _read_schedule raises
   RoadmapRunError naming the file and the remedy, the file stays unchanged, and no row runs.
3. An unreadable failure ledger: FailureLedger(record=path) raises RoadmapRunError naming the
   file and the remedy.
4. An unreadable intake record: read_intake_record(path) raises RoadmapRunError naming the
   file and the remedy.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from pathlib import Path

import pytest

from devops_cli.config.constants import (
    CONST_SERVICE_HALT_FILENAME,
    CONST_SERVICE_METRIC_STATE_UNKEPT,
)
from devops_cli.exceptions import GitHubUnauthenticatedError, RoadmapRunError
from devops_cli.roadmap.run import (
    FailureLedger,
    build_stub_table,
    read_intake_record,
)
from devops_cli.server.service import RoundPause, StateRecord
from devops_cli.telemetry.metrics import GLOBAL_METRICS
from tests.support.roadmap_run import (
    REPO,
    REPO_DIR,
    make_candidates,
    poll_round,
    recorded,
)

pytestmark = pytest.mark.usefixtures("keyring_store")


def test_a_halt_record_that_cannot_be_written_stays_in_memory_and_reports_unkept(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """A halt record that cannot be written raises NotADirectoryError, sets the unkept metric,
    logs the error, keeps the Service halted in memory, and prevents subsequent rounds."""
    blocker = tmp_path / "blocker"
    blocker.write_text("a regular file blocking the directory\n", encoding="utf-8")
    record = blocker / CONST_SERVICE_HALT_FILENAME
    assert not record.exists()

    GLOBAL_METRICS.reset()
    pause = RoundPause(
        clock=lambda: datetime.now(UTC),
        refusal=lambda _exc: True,
        halt_record=record,
        identity="devops-roadmap[bot]",
    )
    assert not pause.halted()
    assert not pause.holds()

    with caplog.at_level(logging.ERROR):
        pause.after(GitHubUnauthenticatedError("bad token"), REPO)

    assert pause.halted()
    assert pause.holds()
    assert not record.exists()

    unkept = GLOBAL_METRICS.get_gauge_value(
        CONST_SERVICE_METRIC_STATE_UNKEPT, labels={"record": StateRecord.HALT}
    )
    assert unkept == 1.0

    errors = [
        rec.message
        for rec in caplog.records
        if rec.levelno >= logging.ERROR and str(record) in rec.message
    ]
    assert errors, f"Expected an error log naming record {record}"
    assert any("FileExistsError" in err or "NotADirectoryError" in err for err in errors)


def test_an_unreadable_schedule_raises_error_and_runs_no_row(tmp_path: Path) -> None:
    """An unreadable schedule.json raises RoadmapRunError naming the file and remedy (#4042)."""
    schedule_path = tmp_path / REPO_DIR / "schedule.json"
    schedule_path.parent.mkdir(parents=True, exist_ok=True)
    bad_content = "{not valid json\n"
    schedule_path.write_text(bad_content, encoding="utf-8")

    # In a poll_round, reading schedule.json raises RoadmapRunError, runs no row, and the file is kept
    store, _, _ = make_candidates(0)
    ran: list[str] = []
    table = build_stub_table({"metrics": recorded(ran, "metrics")})

    with pytest.raises(RoadmapRunError) as raised_poll:
        poll_round(store, tmp_path, table=table)

    err = str(raised_poll.value)
    assert str(schedule_path) in err
    assert "Repair" in err or "remove" in err
    assert raised_poll.value.details.get("path") == str(schedule_path)[:256]
    assert ran == []
    assert schedule_path.read_text(encoding="utf-8") == bad_content


def test_an_unreadable_failure_ledger_raises_error(tmp_path: Path) -> None:
    """An unreadable failure ledger raises RoadmapRunError naming the file and remedy."""
    ledger_path = tmp_path / "service-failures.json"
    bad_content = "not json content"
    ledger_path.write_text(bad_content, encoding="utf-8")

    with pytest.raises(RoadmapRunError) as raised:
        FailureLedger(record=ledger_path)

    err = str(raised.value)
    assert str(ledger_path) in err
    assert "Repair" in err or "remove" in err
    assert raised.value.details.get("path") == str(ledger_path)[:256]
    assert ledger_path.read_text(encoding="utf-8") == bad_content


def test_an_unreadable_intake_record_raises_error(tmp_path: Path) -> None:
    """An unreadable intake record raises RoadmapRunError naming the file and remedy."""
    intake_path = tmp_path / "intake.json"
    bad_content = "{corrupt intake json"
    intake_path.write_text(bad_content, encoding="utf-8")

    with pytest.raises(RoadmapRunError) as raised:
        read_intake_record(intake_path)

    err = str(raised.value)
    assert str(intake_path) in err
    assert "Repair" in err or "remove" in err
    assert raised.value.details.get("path") == str(intake_path)[:256]
    assert intake_path.read_text(encoding="utf-8") == bad_content
