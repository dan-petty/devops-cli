"""The log line and the two gauges of the cadence of a row: the queue that its round gave, and the
interval that the next round uses (#5470).

The rounds run over `run_due_jobs` with a stage row whose runner gives a set queue. The collector is
the fake of the OTLP fixture, and a gauge point is read as (attributes, value).
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import pytest

from devops_cli.roadmap.run import JobOutcome, build_stub_table, run_due_jobs
from tests.support.paths import REPO_ROOT
from tests.support.roadmap_run import NOW, POLL_KEY, REPO

if TYPE_CHECKING:
    from pathlib import Path

    from tests.support.fakes.otlp import FakeCollector
    from tests.support.fakes.roadmap_store import InMemoryRoadmapStore

pytestmark = pytest.mark.usefixtures("keyring_store")

QUEUE_ITEMS = "devops_cli_roadmap_row_queue_items"
INTERVAL_SECONDS = "devops_cli_roadmap_row_interval_seconds"


def _stage_round(store: InMemoryRoadmapStore, tmp_path: Path, queue: int) -> None:
    """A first round in which the stage row gives `queue`."""
    table = build_stub_table({"stage": lambda **_: JobOutcome(queue=queue)})
    run_due_jobs(REPO, store, {POLL_KEY: 1}, table=table, data_dir=tmp_path, now=NOW)


def _lines(caplog: pytest.LogCaptureFixture) -> list[str]:
    return [record.getMessage() for record in caplog.records if "queue" in record.getMessage()]


def test_a_backlog_round_logs_and_sends_the_queue_and_the_backlog_interval(
    seeded_store: InMemoryRoadmapStore,
    tmp_path: Path,
    otlp: FakeCollector,
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A stage queue of 177 at a threshold of 50 logs the queue, 13 minutes and the threshold, and
    sends 177 items and 780 seconds under `repo` and `row`."""
    monkeypatch.setenv("DEVOPS_CLI_ROADMAP_STAGE_BACKLOG_INTERVAL_MINUTES", "13")
    monkeypatch.setenv("DEVOPS_CLI_ROADMAP_STAGE_BACKLOG_THRESHOLD", "50")
    caplog.set_level(logging.INFO, logger="devops_cli.roadmap.run")

    _stage_round(seeded_store, tmp_path, 177)

    lines = _lines(caplog)
    assert (
        len(lines),
        all(part in lines[0] for part in ("stage", REPO, "177", "13 minutes", "50")),
        otlp.points(QUEUE_ITEMS),
        otlp.points(INTERVAL_SECONDS),
    ) == (
        1,
        True,
        [({"repo": REPO, "row": "stage"}, 177)],
        [({"repo": REPO, "row": "stage"}, 780)],
    )


def test_a_round_below_the_threshold_logs_and_sends_the_interval(
    seeded_store: InMemoryRoadmapStore,
    tmp_path: Path,
    otlp: FakeCollector,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """With no backlog rule, a stage queue of 4 keeps 37 minutes, and the line names no
    threshold."""
    caplog.set_level(logging.INFO, logger="devops_cli.roadmap.run")

    _stage_round(seeded_store, tmp_path, 4)

    lines = _lines(caplog)
    assert (
        len(lines),
        all(part in lines[0] for part in ("stage", REPO, "4 items", "37 minutes")),
        "threshold" in lines[0],
        otlp.points(QUEUE_ITEMS),
        otlp.points(INTERVAL_SECONDS),
    ) == (
        1,
        True,
        False,
        [({"repo": REPO, "row": "stage"}, 4)],
        [({"repo": REPO, "row": "stage"}, 2220)],
    )


def test_the_gauges_are_declared_and_documented() -> None:
    """Both instruments are gauges, the queue in items and the interval in seconds, and
    docs/TELEMETRY.md lists both."""
    from devops_cli.telemetry.instruments import INSTRUMENTS, InstrumentKind

    declared = {instrument.name: instrument for instrument in INSTRUMENTS}
    documented = (REPO_ROOT / "docs" / "TELEMETRY.md").read_text(encoding="utf-8")

    assert [
        (
            name in declared and declared[name].kind == InstrumentKind.GAUGE,
            declared[name].unit if name in declared else None,
            name in documented,
        )
        for name in (QUEUE_ITEMS, INTERVAL_SECONDS)
    ] == [(True, "1", True), (True, "s", True)]
