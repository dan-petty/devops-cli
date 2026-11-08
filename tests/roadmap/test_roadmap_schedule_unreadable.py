"""A `schedule.json` that exists and can't be read stops the round and names the file: it never
reads as empty, which would make every row due at once and spend model calls (#4042).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from devops_cli.exceptions import RoadmapRunError
from devops_cli.roadmap.run import build_stub_table
from tests.support.roadmap_run import REPO_DIR, make_candidates, poll_round, recorded

CORRUPT = {
    "not-json": "{not json",
    "not-an-object": json.dumps(["intake", "2026-10-04T11:00:00+00:00"]),
    "not-a-string": json.dumps({"intake": 1760000000}),
    "bad-timestamp": json.dumps({"intake": "yesterday"}),
}


@pytest.mark.parametrize("content", CORRUPT.values(), ids=CORRUPT.keys())
def test_an_unreadable_schedule_raises_an_error_that_names_the_file_and_runs_no_row(
    content: str, tmp_path: Path
) -> None:
    """A corrupt file, a file that is not an object, a value that is not a string and a bad
    timestamp each raise `RoadmapRunError` that names the file and its remedy. `run_due_jobs`
    runs no row, and the file stays as it was."""
    path = tmp_path / REPO_DIR / "schedule.json"
    path.parent.mkdir(parents=True)
    path.write_text(content, encoding="utf-8")
    store, _, _ = make_candidates(0)
    ran: list[str] = []
    table = build_stub_table(
        {"intake": recorded(ran, "intake"), "metrics": recorded(ran, "metrics")}
    )

    with pytest.raises(RoadmapRunError) as raised:
        poll_round(store, tmp_path, table=table)

    assert (
        str(path) in str(raised.value),
        "Repair it, or remove it" in str(raised.value),
        raised.value.details.get("path"),
        ran,
        path.read_text(encoding="utf-8"),
    ) == (True, True, str(path)[:256], [], content)


def test_a_missing_schedule_is_empty_and_every_row_with_a_first_run_is_due(
    tmp_path: Path,
) -> None:
    """A repository that never ran has no `schedule.json`: that is not an error."""
    store, _, _ = make_candidates(0)
    ran: list[str] = []
    table = build_stub_table({"metrics": recorded(ran, "metrics")})

    jobs = poll_round(store, tmp_path, table=table)

    assert ("metrics" in jobs, ran) == (True, ["metrics"])
