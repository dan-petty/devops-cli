"""The job counter of each row of a lane: a success, an error and a stop count under their own row
(#3495).
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

import pytest

from devops_cli.config.constants import (
    CONST_SERVICE_LANE_STATUS,
    CONST_SERVICE_LANE_TRIAGE,
    CONST_SERVICE_METRIC_JOBS,
)
from devops_cli.exceptions import (
    RoadmapRunError,
    ServiceStoppingError,
)
from devops_cli.roadmap.run import (
    JobOutcome,
    build_stub_table,
    run_scoped_update,
    service_jobs,
)
from devops_cli.telemetry.metrics import GLOBAL_METRICS
from tests.support.roadmap_run import (
    NOW,
    POLL,
    REPO,
    IntakeModel,
    labeled_changes,
    make_candidates,
    serve_over,
    service_github,
    webhook_delivery,
)

pytestmark = pytest.mark.usefixtures("keyring_store")


def _job_count(lane: str, row: str, result: str) -> float:
    """The value of the job counter of the row `row` of `lane` under `result`."""
    return GLOBAL_METRICS.get_counter(
        CONST_SERVICE_METRIC_JOBS,
        labels={"repo": REPO, "lane": lane, "row": row, "result": result},
    )


@pytest.mark.usefixtures("roadmap_bot")
def test_each_row_of_a_lane_counts_its_own_job(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A row that ends counts one job of the job counter under its own row and result, so a lane
    with one row that fails counts that row as an error and the other row as a success (#3495)."""
    GLOBAL_METRICS.reset()
    github = service_github(labeled_changes(2, "alice"))
    serve_over(tmp_path, monkeypatch, github, stamped=False)

    def fails(**_: object) -> JobOutcome:
        raise RuntimeError("the implement job failed")

    table = build_stub_table({"metrics": lambda **_: JobOutcome(), "implement": fails})
    with pytest.raises(RoadmapRunError) as raised:
        service_jobs(tmp_path)[CONST_SERVICE_LANE_STATUS](POLL, table=table)
    assert list(raised.value.failed_jobs) == ["implement"]

    assert (
        _job_count(CONST_SERVICE_LANE_STATUS, "metrics", "success"),
        _job_count(CONST_SERVICE_LANE_STATUS, "implement", "error"),
    ) == (1, 1)


@pytest.mark.usefixtures("roadmap_bot")
def test_a_row_that_the_stop_of_the_service_ends_counts_as_stopped(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A stop is no failure of the row (#2753), so the row counts under `stopped` and the job
    failure alert does not read it (#3495)."""
    GLOBAL_METRICS.reset()
    github = service_github(labeled_changes(2, "alice"))
    serve_over(tmp_path, monkeypatch, github, stamped=False)

    def stops(**_: object) -> JobOutcome:
        raise ServiceStoppingError("the Service is stopping")

    table = build_stub_table({"metrics": lambda **_: JobOutcome(), "implement": stops})
    with pytest.raises(RoadmapRunError) as ended:
        service_jobs(tmp_path)[CONST_SERVICE_LANE_STATUS](POLL, table=table)

    assert (
        list(ended.value.failed_jobs),
        _job_count(CONST_SERVICE_LANE_STATUS, "implement", "stopped"),
        _job_count(CONST_SERVICE_LANE_STATUS, "implement", "error"),
    ) == (["implement"], 1, 0)


@pytest.mark.parametrize(
    ("raised", "result"),
    [
        (RuntimeError("the store failed"), "error"),
        (ServiceStoppingError("the Service is stopping"), "stopped"),
    ],
)
def test_a_scoped_update_that_raises_counts_under_the_result_of_its_error(
    raised: Exception, result: str, tmp_path: Path
) -> None:
    """A scoped update counts as a row does: a stop under `stopped`, a failure under `error`."""
    GLOBAL_METRICS.reset()

    class RaisingModel(IntakeModel):
        def embed(self, texts: Sequence[str]) -> list[list[float]]:
            raise raised

    store, _, _ = make_candidates(1)
    with pytest.raises(type(raised)) as ended:
        run_scoped_update(
            webhook_delivery("opened", 1), store, data_dir=tmp_path, now=NOW, model=RaisingModel()
        )

    assert (ended.value, _job_count(CONST_SERVICE_LANE_TRIAGE, "intake", result)) == (raised, 1)
