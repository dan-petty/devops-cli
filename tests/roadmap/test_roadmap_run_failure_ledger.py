"""The ledger of failed rounds: what a record holds, how a restart loads it and when a suspended
row runs again (#981).
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from devops_cli.config.constants import (
    CONST_SERVICE_FAILURES_FILENAME,
    CONST_SERVICE_METRIC_JOB_SUSPENDED,
)
from devops_cli.exceptions import (
    GitOperationError,
    RoadmapRunError,
)
from devops_cli.roadmap.run import (
    STATUS_LANE_ROWS,
    FailureLedger,
    JobOutcome,
    run_due_jobs,
)
from devops_cli.telemetry.metrics import GLOBAL_METRICS
from tests.support.fakes.roadmap_store import InMemoryRoadmapStore
from tests.support.roadmap_run import NOW, POLL_KEY, REPO, lane_table

pytestmark = pytest.mark.usefixtures("keyring_store")


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
            table=lane_table(STATUS_LANE_ROWS, implement=failing),
            data_dir=tmp_path,
            now=at,
            failures=FailureLedger(record=record),
        )

    for step in range(FailureLedger().limit):
        with pytest.raises(RoadmapRunError) as raised:
            round_of(NOW + timedelta(minutes=step))
        assert raised.value.error_code == "DEVOPS_CLI_ERROR"
    kept = json.loads(record.read_text(encoding="utf-8"))
    GLOBAL_METRICS.reset()
    suspended_labels = {"repo": REPO, "row": "implement", "class": "ci_infra"}

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


def test_the_ledger_record_holds_the_causes_and_a_restart_loads_them(tmp_path: Path) -> None:
    """The causes of the failed rounds survive a restart of the Service (#3493)."""
    record = tmp_path / CONST_SERVICE_FAILURES_FILENAME
    ledger = FailureLedger(record=record)
    ledger.failed(REPO, "stage", "input", "provider", NOW)
    ledger.failed(REPO, "stage", "input", "plan_defect", NOW)

    reloaded = FailureLedger(record=record)

    assert (
        json.loads(record.read_text(encoding="utf-8")),
        reloaded.causes(REPO, "stage"),
    ) == (
        [[REPO, "stage", 2, "input", ["provider", "plan_defect"], None]],
        ("provider", "plan_defect"),
    )


def test_a_ledger_record_in_the_old_format_loads_with_unknown_causes(tmp_path: Path) -> None:
    """A record that an earlier version wrote has no causes: each failed round reads `unknown`
    (#3493)."""
    record = tmp_path / CONST_SERVICE_FAILURES_FILENAME
    record.write_text(json.dumps([[REPO, "stage", 3, "input"]]), encoding="utf-8")

    ledger = FailureLedger(record=record)

    assert (ledger.suspended(REPO, "stage", "input", NOW), ledger.causes(REPO, "stage")) == (
        True,
        ("unknown",) * 3,
    )
    ledger.failed(REPO, "stage", "other", "provider", NOW)
    assert FailureLedger(record=record).causes(REPO, "stage") == ("provider",)


def test_a_suspended_implement_row_runs_again_on_a_later_poll_round_when_the_fault_is_fixed(
    seeded_store: InMemoryRoadmapStore, tmp_path: Path
) -> None:
    """The status lane reads no issue change, so a poll round brings no new input by itself. The
    input of such a round holds the hour of the round: a row suspended by a fault that is fixed
    runs again in a later hour, with no webhook (#2757)."""
    calls: list[str] = []
    fixed = {"yes": False}

    def implement(**_: Any) -> JobOutcome:
        calls.append("implement")
        if not fixed["yes"]:
            raise GitOperationError("The Kubernetes API refused the call.")
        return JobOutcome()

    failures = FailureLedger()

    def round_of(at: datetime) -> tuple[str, ...]:
        return run_due_jobs(
            REPO,
            seeded_store,
            batch={POLL_KEY: 1},
            table=lane_table(STATUS_LANE_ROWS, implement=implement),
            data_dir=tmp_path,
            now=at,
            failures=failures,
        )

    for step in range(failures.limit):
        with pytest.raises(RoadmapRunError) as raised:
            round_of(NOW + timedelta(minutes=step))
        assert raised.value.error_code == "DEVOPS_CLI_ERROR"
    same_hour = round_of(NOW + timedelta(minutes=10))
    fixed["yes"] = True
    later = round_of(NOW + timedelta(hours=1, minutes=10))

    assert (same_hour, later, len(calls)) == (
        ("stage_ready",),
        (
            "metrics",
            "implement",
            "stage_ready",
            "release_comments",
            "github_status",
            "cloudflare_status",
            "pr_conflicts",
        ),
        4,
    )
