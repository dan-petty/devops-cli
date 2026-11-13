"""The status rows of the due table: each upstream status read is a row of its own, so a read that
fails fails its row and no other row, and the counter, the schedule and the ledger of failed
rounds see it (#4052).
"""

from __future__ import annotations

import json
from datetime import timedelta
from pathlib import Path
from typing import Any

import pytest

from devops_cli.config.constants import (
    CONST_SERVICE_FAILURES_FILENAME,
    CONST_SERVICE_LANE_STATUS,
    CONST_SERVICE_METRIC_JOB_SUSPENDED,
    CONST_SERVICE_METRIC_JOBS,
    CONST_URL_CLOUDFLARE_STATUS_SUMMARY,
    CONST_URL_GITHUB_STATUS_SUMMARY,
)
from devops_cli.config.defaults import DEFAULT_ROADMAP_METRICS_INTERVAL_MINUTES
from devops_cli.exceptions import RoadmapRunError
from devops_cli.roadmap.run import (
    DEFAULT_DUE_TABLE,
    STATUS_LANE_ROWS,
    FailureLedger,
    JobRow,
    run_due_jobs,
)
from devops_cli.telemetry.instruments import UPSTREAM_SERVICE_STATUS
from devops_cli.telemetry.metrics import GLOBAL_METRICS
from tests.support.fakes.git import GitFake
from tests.support.fakes.github_repository import GitHubFake
from tests.support.fakes.http import WebFake
from tests.support.fakes.otlp import FakeCollector
from tests.support.fakes.roadmap_store import InMemoryRoadmapStore
from tests.support.roadmap_run import (
    NOW,
    PLANNED,
    POLL_KEY,
    REPO,
    SimulatedGit,
    lane_table,
    read_schedule,
    run_metrics_adapter,
)

pytestmark = pytest.mark.usefixtures("keyring_store")

STATUS_PAGE = {
    "page": {"id": "page", "name": "Status", "url": "https://example.com"},
    "status": {"indicator": "none", "description": "All Systems Operational"},
}

STATUS_ROW_NAMES = (
    "metrics",
    "implement",
    "stage_ready",
    "stage",
    "release_comments",
    "github_status",
    "cloudflare_status",
    "pr_conflicts",
)
"""The status lane, in its order: the stage row submits the stage Jobs (#4559), and the two status
reads and the conflict row (#4027) come last, so a slow status page never delays `implement`."""

STATUS_READS = ("github_status", "cloudflare_status")


def _row(name: str) -> JobRow:
    """The row `name` of the status lane, or a failed assertion that names it."""
    for row in STATUS_LANE_ROWS:
        if row.name == name:
            return row
    raise AssertionError(f"The status lane has no row {name}.")


def _status_table() -> tuple[JobRow, ...]:
    """The status lane with the real runners of the two status reads and a stub for the others."""
    return lane_table(STATUS_LANE_ROWS, **{name: _row(name).runner for name in STATUS_READS})


def _jobs(row: str, result: str) -> float:
    """The value of the job counter of the status row `row` under `result`."""
    return GLOBAL_METRICS.get_counter(
        CONST_SERVICE_METRIC_JOBS,
        labels={"repo": REPO, "lane": CONST_SERVICE_LANE_STATUS, "row": row, "result": result},
    )


def test_row_names_of_the_status_lane_end_with_the_two_status_reads() -> None:
    """The status lane holds the five rows it held, the two status reads after them and the
    conflict row last, in this order, and the default table runs them before the other lanes
    (#4052, #4027)."""
    assert (
        tuple(row.name for row in STATUS_LANE_ROWS),
        tuple(row.name for row in DEFAULT_DUE_TABLE[: len(STATUS_ROW_NAMES)]),
    ) == (STATUS_ROW_NAMES, STATUS_ROW_NAMES)


def test_row_names_of_the_status_reads_need_no_clone_and_use_the_metrics_interval() -> None:
    """A status read fetches a public page, so its row needs no clone. It uses the interval of the
    metrics row and is due on a first run. `metrics` keeps its clone (#4052)."""
    reads = [_row(name) for name in STATUS_READS]
    assert (
        [(row.needs_clone, row.first_run_due, row.interval) for row in reads],
        _row("metrics").needs_clone,
    ) == (
        [(False, True, timedelta(minutes=DEFAULT_ROADMAP_METRICS_INTERVAL_MINUTES))] * 2,
        True,
    )


def test_source_failed_github_status_read_counts_an_error_for_its_row_only(
    seeded_store: InMemoryRoadmapStore, tmp_path: Path, web: WebFake
) -> None:
    """GitHub status does not answer and Cloudflare status does. The round fails the row
    `github_status` and counts it under `error`. `metrics` and `cloudflare_status` count a
    success and write their stamp to `schedule.json`; `github_status` writes none (#4052)."""
    GLOBAL_METRICS.reset()
    web.refuse(CONST_URL_GITHUB_STATUS_SUMMARY)
    web.page(CONST_URL_CLOUDFLARE_STATUS_SUMMARY, json.dumps(STATUS_PAGE))

    with pytest.raises(RoadmapRunError) as raised:
        run_due_jobs(
            REPO,
            seeded_store,
            batch={POLL_KEY: 1},
            table=_status_table(),
            data_dir=tmp_path,
            now=NOW,
            lane=CONST_SERVICE_LANE_STATUS,
        )

    assert (
        list(raised.value.failed_jobs),
        {row: (_jobs(row, "success"), _jobs(row, "error")) for row in STATUS_ROW_NAMES},
        sorted(read_schedule(tmp_path)),
    ) == (
        ["github_status"],
        {
            "metrics": (1, 0),
            "implement": (1, 0),
            "stage_ready": (1, 0),
            "stage": (1, 0),
            "release_comments": (1, 0),
            "github_status": (0, 1),
            "cloudflare_status": (1, 0),
            "pr_conflicts": (1, 0),
        },
        sorted(name for name in STATUS_ROW_NAMES if name != "github_status"),
    )


def test_source_failed_status_page_error_is_the_error_of_the_read(
    seeded_store: InMemoryRoadmapStore,
    tmp_path: Path,
    web: WebFake,
) -> None:
    """A status page that answers with a payload the reader cannot parse ends the row with the
    `ServiceStatusError` of the reader. The row catches nothing (#4052)."""
    web.page(CONST_URL_GITHUB_STATUS_SUMMARY, json.dumps(STATUS_PAGE))
    web.page(CONST_URL_CLOUDFLARE_STATUS_SUMMARY, "not json")

    with pytest.raises(RoadmapRunError) as raised:
        run_due_jobs(
            REPO,
            seeded_store,
            batch={POLL_KEY: 1},
            table=_status_table(),
            data_dir=tmp_path,
            now=NOW,
            lane=CONST_SERVICE_LANE_STATUS,
        )

    cause = raised.value.__cause__
    assert isinstance(cause, ExceptionGroup)
    assert (
        list(raised.value.failed_jobs),
        [type(error).__name__ for error in cause.exceptions],
    ) == (
        ["cloudflare_status"],
        ["ServiceStatusError"],
    )


def test_ledger_per_row_three_failed_cloudflare_reads_suspend_only_that_row(
    seeded_store: InMemoryRoadmapStore, tmp_path: Path, web: WebFake
) -> None:
    """Cloudflare status does not answer for the limit of rounds in a row. The record of failed
    rounds holds one entry, for `cloudflare_status`, and the gauge
    `devops_cli_service_job_suspended` is 1 for that row and 0 for the others (#4052)."""
    record = tmp_path / CONST_SERVICE_FAILURES_FILENAME
    failures = FailureLedger(record=record)
    web.page(CONST_URL_GITHUB_STATUS_SUMMARY, json.dumps(STATUS_PAGE))
    web.refuse(CONST_URL_CLOUDFLARE_STATUS_SUMMARY)

    def round_of(step: int) -> tuple[str, ...]:
        return run_due_jobs(
            REPO,
            seeded_store,
            batch={POLL_KEY: 1},
            table=_status_table(),
            data_dir=tmp_path,
            now=NOW + timedelta(minutes=step),
            failures=failures,
            lane=CONST_SERVICE_LANE_STATUS,
        )

    failed: list[list[str]] = []
    for step in range(failures.limit):
        with pytest.raises(RoadmapRunError) as raised:
            round_of(step)
        failed.append(list(raised.value.failed_jobs))
    GLOBAL_METRICS.reset()
    reloaded = FailureLedger(record=record)
    suspended: dict[str, Any] = {
        row: GLOBAL_METRICS.get_gauge_value(
            CONST_SERVICE_METRIC_JOB_SUSPENDED,
            labels={"repo": REPO, "row": row, "class": "ci_infra"},
        )
        for row in STATUS_ROW_NAMES
    }

    assert (
        failed,
        [entry[:3] for entry in json.loads(record.read_text(encoding="utf-8"))],
        suspended,
        reloaded.limit,
    ) == (
        [["cloudflare_status"]] * failures.limit,
        [[REPO, "cloudflare_status", failures.limit]],
        {row: 1.0 if row == "cloudflare_status" else 0.0 for row in STATUS_ROW_NAMES},
        failures.limit,
    )


def test_a_status_row_sends_the_status_of_its_source_and_reads_no_other_page(
    seeded_store: InMemoryRoadmapStore,
    tmp_path: Path,
    web: WebFake,
    otlp: FakeCollector,
) -> None:
    """The row `github_status` reads the GitHub page and sends its gauge, and reads no Cloudflare
    page. The row `cloudflare_status` does the same for its own page (#4052)."""
    web.page(CONST_URL_GITHUB_STATUS_SUMMARY, json.dumps(STATUS_PAGE))
    web.page(CONST_URL_CLOUDFLARE_STATUS_SUMMARY, json.dumps(STATUS_PAGE))

    _row("github_status").runner(store=seeded_store, repo=REPO, clone_path=None)
    after_github = (list(web.requested), _services(otlp))
    _row("cloudflare_status").runner(store=seeded_store, repo=REPO, clone_path=None)

    assert (after_github, _services(otlp), web.requested) == (
        ([CONST_URL_GITHUB_STATUS_SUMMARY], ["github"]),
        ["cloudflare", "github"],
        [CONST_URL_GITHUB_STATUS_SUMMARY, CONST_URL_CLOUDFLARE_STATUS_SUMMARY],
    )


def test_the_metrics_row_reads_no_status_page_and_raises_when_its_collection_fails(
    seeded_store: InMemoryRoadmapStore,
    tmp_path: Path,
    web: WebFake,
    git_fake: GitFake,
    git_sim: SimulatedGit,
) -> None:
    """The row `metrics` reads the project metrics only. A collection that fails raises out of
    the row, so the counter, the schedule and the ledger see it, and no status page is read
    (#4052)."""
    clone = tmp_path / "clone"
    clone.mkdir()
    (clone / ".git").mkdir()
    milestone = {"number": 26, "title": PLANNED, "state": "open", "open_issues": None}
    GitHubFake(REPO, milestones=[milestone]).install(git_fake)

    with pytest.raises(TypeError, match="NoneType"):
        run_metrics_adapter(store=seeded_store, repo=REPO, clone_path=clone)

    assert {CONST_URL_GITHUB_STATUS_SUMMARY, CONST_URL_CLOUDFLARE_STATUS_SUMMARY}.isdisjoint(
        web.requested
    )


def _services(otlp: FakeCollector) -> list[str]:
    """The services whose status gauge reached the collector, sorted."""
    return sorted(attrs["service"] for attrs, _ in otlp.points(UPSTREAM_SERVICE_STATUS.name))
