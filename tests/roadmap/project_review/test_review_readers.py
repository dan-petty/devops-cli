"""The readers of the project review catalog (#4692): the Actions runs split by created time under
the result cap, a newest-first listing that stops at the window start, the listing snapshot with
the changes after its watermark, and Prometheus and Loki read at the end of the window."""

from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx2
import pytest

from devops_cli.exceptions.roadmap import RoadmapReviewError
from devops_cli.github.session import get_github_session
from devops_cli.http.egress import EgressLevel
from devops_cli.roadmap.project_review.readers import (
    Reads,
    read_github,
    read_listing,
    read_loki,
    read_prometheus,
    read_runs,
)
from devops_cli.roadmap.stores.listing_snapshot import (
    LISTING_SCHEMA_KEY,
    FileSnapshotStore,
    ListingSnapshot,
)
from devops_cli.roadmap.stores.store import IssueRecord
from tests.support.fakes.clock import ClockFake
from tests.support.fakes.github import API, GitHubApiFake, github_json, next_page
from tests.support.fakes.http import WebFake

REPO = "example/project"
START = datetime(2026, 11, 4, 14, 51, 23, tzinfo=UTC)
END = datetime(2026, 11, 11, 14, 51, 23, tzinfo=UTC)
WATERMARK = datetime(2026, 11, 11, 14, 28, 4, tzinfo=UTC)
RUNS = f"/repos/{REPO}/actions/runs?branch=main&event=push"
# GitHub gives at most 1,000 results of a filtered list of runs; a later page holds none.
CAP = 1000
PER_PAGE = 100
_TIME = "%Y-%m-%dT%H:%M:%SZ"


def _utc(text: str) -> datetime:
    return datetime.strptime(text, _TIME).replace(tzinfo=UTC)


class RunsApi:
    """The Actions runs of the window as GitHub lists them: the runs of a `created` slice newest
    first, at most 1,000 of them in pages of 100, beside the real `total_count`."""

    def __init__(self, created: list[datetime]) -> None:
        self.runs = [
            {"id": number, "created_at": moment.strftime(_TIME), "conclusion": "success"}
            for number, moment in enumerate(created, start=1)
        ]
        self.pages: dict[str, list[int]] = defaultdict(list)
        self.totals: dict[str, int] = {}

    def __call__(self, request: httpx2.Request) -> httpx2.Response | None:
        if not request.url.path.endswith("/actions/runs"):
            return None
        created = request.url.params["created"]
        low, _, high = created.partition("..")
        found = [run for run in self.runs if _utc(low) <= _utc(run["created_at"]) <= _utc(high)][
            ::-1
        ]
        page = int(request.url.params.get("page", "1"))
        self.pages[created].append(page)
        self.totals[created] = len(found)
        shown = found[:CAP]
        rows = shown[(page - 1) * PER_PAGE : page * PER_PAGE]
        more = page * PER_PAGE < len(shown)
        link = next_page(str(request.url.copy_merge_params({"page": str(page + 1)})))
        return github_json(
            {"total_count": len(found), "workflow_runs": rows}, headers=link if more else None
        )


def test_two_thousand_runs_split_into_slices_under_the_cap_and_no_run_is_lost(
    github_api: GitHubApiFake,
) -> None:
    api = RunsApi([START + timedelta(seconds=302 * (n + 1)) for n in range(2000)])
    github_api.serve(api)
    reads = Reads()

    answer = read_runs(get_github_session(), RUNS, START, END, reads)

    ids = [run["id"] for run in answer["workflow_runs"]]
    read_to_end = [created for created, pages in api.pages.items() if pages != [1]]
    capped = [created for created, total in api.totals.items() if total >= CAP]
    assert (len(ids), set(ids) == set(range(1, 2001)), answer["total_count"]) == (2000, True, 2000)
    assert all(api.totals[created] < CAP for created in read_to_end)
    assert all(api.pages[created] == [1] for created in capped)
    assert reads.counts["github_runs"] == len(github_api.sent)


def test_a_slice_of_one_second_at_the_cap_raises(github_api: GitHubApiFake) -> None:
    moment = END
    github_api.serve(RunsApi([moment] * CAP))

    with pytest.raises(RoadmapReviewError, match="1,000"):
        read_runs(get_github_session(), RUNS, moment - timedelta(seconds=1), moment, Reads())


def test_a_newest_first_listing_stops_at_the_page_that_reaches_the_window_start(
    github_api: GitHubApiFake,
) -> None:
    first = f"/repos/{REPO}/releases?per_page=100"
    second = f"{first}&page=2"
    third = f"{first}&page=3"
    github_api.route(
        "GET",
        first,
        github_json([{"id": 3, "created_at": "2026-11-10T00:00:00Z"}], headers=next_page(second)),
    )
    github_api.route(
        "GET",
        second,
        github_json(
            [
                {"id": 2, "created_at": "2026-11-05T00:00:00Z"},
                {"id": 1, "created_at": "2026-11-01T00:00:00Z"},
            ],
            headers=next_page(third),
        ),
    )
    github_api.route("GET", third, github_json([{"id": 0, "created_at": "2026-10-01T00:00:00Z"}]))

    answer = read_github(
        get_github_session(), f"repos/{REPO}/releases", START, Reads(), newest_first="created_at"
    )

    assert ([item["id"] for item in answer], github_api.requested) == (
        [3, 2, 1],
        [f"GET {API}{first}", f"GET {API}{second}"],
    )


def _held(
    store: FileSnapshotStore, *, full_at: datetime, schema_key: str = LISTING_SCHEMA_KEY
) -> bytes:
    """Keep a snapshot of intake with one issue at the watermark `WATERMARK`; give its bytes."""
    held = IssueRecord(
        number=1,
        title="Held",
        url=f"https://github.com/{REPO}/issues/1",
        created_at=datetime(2026, 11, 10, tzinfo=UTC),
        updated_at=datetime(2026, 11, 10, tzinfo=UTC),
    )
    store.save(
        ListingSnapshot(
            repo=REPO,
            schema_key=schema_key,
            full_at=full_at,
            watermark=WATERMARK,
            issues=(held,),
        )
    )
    return store.path(REPO).read_bytes()


def _changed_since(github_api: GitHubApiFake, since: str) -> str:
    """Answer the listing changed since `since` with one issue opened after the watermark."""
    opened = {
        "number": 2,
        "title": "After the watermark",
        "html_url": f"https://github.com/{REPO}/issues/2",
        "state": "open",
        "created_at": "2026-11-11T14:40:00Z",
        "updated_at": "2026-11-11T14:40:00Z",
    }
    path = f"/repos/{REPO}/issues?state=all&sort=updated&direction=desc&since={since}&per_page=100"
    github_api.route("GET", path, github_json([opened]))
    return f"GET {API}{path}"


def test_the_listing_reads_the_issue_after_the_watermark_once_and_keeps_the_snapshot(
    github_api: GitHubApiFake, tmp_path: Path
) -> None:
    store = FileSnapshotStore(tmp_path)
    before = _held(store, full_at=WATERMARK - timedelta(hours=1))
    _changed_since(github_api, "2026-11-11T14:28:04Z")
    reads = Reads()

    records = read_listing(get_github_session(), REPO, store, reads, start=START)

    assert ([record["number"] for record in records], reads.counts["listing"]) == ([2, 1], 1)
    assert store.path(REPO).read_bytes() == before


def test_an_old_snapshot_of_this_schema_gives_only_the_changes_after_its_watermark(
    github_api: GitHubApiFake, tmp_path: Path
) -> None:
    """The last full read of intake is 3 days old: the review reads the gap after the watermark,
    not the whole listing, because each listing fact counts issues that changed in the window."""
    store = FileSnapshotStore(tmp_path)
    before = _held(store, full_at=WATERMARK - timedelta(days=3))
    gap = _changed_since(github_api, "2026-11-11T14:28:04Z")

    records = read_listing(get_github_session(), REPO, store, Reads(), start=START)

    assert ([record["number"] for record in records], github_api.requested) == ([2, 1], [gap])
    assert store.path(REPO).read_bytes() == before


@pytest.mark.parametrize("schema_key", [None, "0000000000000000"])
def test_with_no_snapshot_of_this_schema_the_listing_reads_the_changes_since_the_window_start(
    github_api: GitHubApiFake, tmp_path: Path, schema_key: str | None
) -> None:
    """No snapshot, or a snapshot of another record schema: the review reads the issues and pull
    requests changed at or after the window start, not the whole listing, and writes no snapshot."""
    store = FileSnapshotStore(tmp_path / "listing")
    before = None if schema_key is None else _held(store, full_at=WATERMARK, schema_key=schema_key)
    since = _changed_since(github_api, "2026-11-04T14:51:23Z")

    records = read_listing(get_github_session(), REPO, store, Reads(), start=START)

    assert ([record["number"] for record in records], github_api.requested) == ([2], [since])
    path = store.path(REPO)
    assert (path.read_bytes() if path.exists() else None) == before


def _vector(request: httpx2.Request) -> httpx2.Response:
    return httpx2.Response(
        200,
        json={
            "status": "success",
            "data": {"resultType": "vector", "result": [{"metric": {}, "value": [1, "2"]}]},
        },
    )


def test_prometheus_and_loki_are_read_at_the_end_of_the_window(
    web: WebFake, clock: ClockFake
) -> None:
    web.serve(_vector)
    reads = Reads()

    read_prometheus("http://prometheus.example.com:9090", EgressLevel.PRIVATE, "up", END, reads)
    read_loki("http://loki.example.com:3100", 'count_over_time({app="x"}[1h])', END, reads)

    assert [(request.url.path, request.url.params["time"]) for request in web.sent] == [
        ("/api/v1/query", "2026-11-11T14:51:23Z"),
        ("/loki/api/v1/query", "2026-11-11T14:51:23Z"),
    ]
    assert (reads.counts["prometheus"], reads.counts["loki"]) == (1, 1)
