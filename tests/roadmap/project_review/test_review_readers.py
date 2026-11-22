"""The readers of the project review catalog (#4692): the count of the Actions runs of each status,
a newest-first listing that stops at the window start, the review's own listing snapshot with the
changes after its watermark (#6603), the GitHub requests of a 7-day review, and Prometheus and Loki
read at the end of the window."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx2
import pytest

from devops_cli.config.settings import load_settings
from devops_cli.github.session import get_github_session
from devops_cli.http.egress import EgressLevel
from devops_cli.roadmap.project_review.catalog import Catalog, ReaderKind, load_catalog
from devops_cli.roadmap.project_review.data import ReviewWindow, WindowKind
from devops_cli.roadmap.project_review.dispatch import CatalogResult, ReadContext, read_catalog
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
# GitHub gives at most 1,000 results of a filtered list of runs, and 100 entries of a page.
CAP = 1000
PER_PAGE = 100
# The pages of the issue listing that a 7-day window reads in this repository (#6603).
LISTING_PAGES = 19
# The reader kinds that read GitHub, which the 45-request limit of #4692 bounds.
GITHUB_KINDS = (ReaderKind.LISTING, ReaderKind.GITHUB, ReaderKind.GITHUB_RUNS)
_TIME = "%Y-%m-%dT%H:%M:%SZ"


def _utc(text: str) -> datetime:
    return datetime.strptime(text, _TIME).replace(tzinfo=UTC)


def _push_runs(success: int, failure: int, cancelled: int, running: int) -> list[dict[str, Any]]:
    """The push runs of the window, oldest first, spread over its seconds: `success` of them that
    succeeded, `failure` that failed, `cancelled` that were cancelled and `running` that are in
    progress."""
    outcomes = (
        ("completed", "success"),
        ("completed", "failure"),
        ("completed", "cancelled"),
        ("in_progress", None),
    )
    counts = (success, failure, cancelled, running)
    runs = [
        {"status": status, "conclusion": conclusion}
        for (status, conclusion), count in zip(outcomes, counts, strict=True)
        for _ in range(count)
    ]
    step = (END - START) / (len(runs) + 1)
    return [
        {"id": number, "created_at": (START + step * number).strftime(_TIME), **run}
        for number, run in enumerate(runs, start=1)
    ]


class RunsApi:
    """The Actions runs of the window as GitHub answers them: the runs of a `created` range, newest
    first, at most the result cap of them in pages of `per_page`, beside the exact `total_count` of
    the range and of the status that the request filters on."""

    def __init__(self, runs: list[dict[str, Any]]) -> None:
        self.runs = runs

    def __call__(self, request: httpx2.Request) -> httpx2.Response | None:
        if not request.url.path.endswith("/actions/runs"):
            return None
        low, _, high = request.url.params["created"].partition("..")
        status = request.url.params.get("status")
        found = [
            run
            for run in reversed(self.runs)
            if _utc(low) <= _utc(run["created_at"]) <= _utc(high)
            and (status is None or status in (run["status"], run["conclusion"]))
        ]
        per_page = int(request.url.params.get("per_page", str(PER_PAGE)))
        page = int(request.url.params.get("page", "1"))
        rows = found[:CAP][(page - 1) * per_page : page * per_page]
        more = page * per_page < min(len(found), CAP)
        link = (
            next_page(str(request.url.copy_merge_params({"page": str(page + 1)}))) if more else None
        )
        return github_json({"total_count": len(found), "workflow_runs": rows}, headers=link)


def test_the_runs_reader_counts_each_status_with_one_request(github_api: GitHubApiFake) -> None:
    """A window of more runs than the result cap: one request for each status and one for the total,
    each of one entry, so five requests replace the pages of runs (#6603)."""
    github_api.serve(RunsApi(_push_runs(1800, 150, 30, 20)))
    reads = Reads()

    answer = read_runs(get_github_session(), RUNS, START, END, reads)

    assert answer["statuses"] == {
        "success": 1800,
        "failure": 150,
        "cancelled": 30,
        "in_progress": 20,
    }
    assert answer["total_count"] == 2000
    assert reads.counts["github_runs"] == len(github_api.sent) == 5
    assert [request.url.params["per_page"] for request in github_api.sent] == ["1"] * 5
    assert [request.url.params.get("status") for request in github_api.sent] == [
        "success",
        "failure",
        "cancelled",
        "in_progress",
        None,
    ]


def test_two_thousand_runs_split_into_slices_under_the_cap_and_no_run_is_lost(
    github_api: GitHubApiFake,
) -> None:
    """A window of 2,000 runs is above the result cap of 1,000, and one of them was skipped: the
    total of the window holds every run, and the four status counts hold the others, so no run of
    the window is lost (#6603). The case keeps the name that it had while the reader split a window
    into slices under the cap."""
    skipped = {
        "id": 2001,
        "created_at": (END - timedelta(minutes=1)).strftime(_TIME),
        "status": "completed",
        "conclusion": "skipped",
    }
    github_api.serve(RunsApi([*_push_runs(1500, 400, 70, 29), skipped]))
    reads = Reads()

    answer = read_runs(get_github_session(), RUNS, START, END, reads)

    assert answer["total_count"] == 2000
    assert sum(answer["statuses"].values()) == 1999
    assert "skipped" not in answer["statuses"]
    assert reads.counts["github_runs"] == len(github_api.sent) == 5


def test_a_slice_of_one_second_at_the_cap_raises(github_api: GitHubApiFake) -> None:
    """A window of one second holds 1,000 runs, the result cap. The reader reads the exact count of
    each status and of the total of that second, so it loses no run and raises nothing (#6603). The
    case keeps the name that it had while such a window raised."""
    moment = END.strftime(_TIME)
    runs = [
        {"id": number, "created_at": moment, "status": "completed", "conclusion": "success"}
        for number in range(1, CAP + 1)
    ]
    github_api.serve(RunsApi(runs))
    reads = Reads()

    answer = read_runs(get_github_session(), RUNS, END - timedelta(seconds=1), END, reads)

    assert answer["statuses"]["success"] == CAP
    assert answer["total_count"] == CAP
    assert reads.counts["github_runs"] == 5


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


def _stores(tmp_path: Path) -> tuple[FileSnapshotStore, FileSnapshotStore]:
    """The store that the review keeps, and the one of intake, each under `tmp_path`."""
    return FileSnapshotStore(tmp_path / "review-listing"), FileSnapshotStore(tmp_path / "listing")


def _held(
    store: FileSnapshotStore,
    *,
    full_at: datetime,
    watermark: datetime = WATERMARK,
    schema_key: str = LISTING_SCHEMA_KEY,
) -> bytes:
    """Keep a snapshot with one issue at `watermark`; give its bytes."""
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
            watermark=watermark,
            issues=(held,),
        )
    )
    return store.path(REPO).read_bytes()


def _changed_since(github_api: GitHubApiFake, since: str) -> str:
    """Answer the listing changed since `since` with one issue opened after the watermark."""
    path = f"/repos/{REPO}/issues?state=all&sort=updated&direction=desc&since={since}&per_page=100"
    github_api.route("GET", path, github_json([_opened(2)]))
    return f"GET {API}{path}"


def _opened(number: int) -> dict[str, Any]:
    """An issue as the issue listing gives it, changed at the end of the window."""
    return {
        "number": number,
        "title": f"Issue {number}",
        "html_url": f"https://github.com/{REPO}/issues/{number}",
        "state": "open",
        "created_at": "2026-11-11T14:40:00Z",
        "updated_at": "2026-11-11T14:40:00Z",
    }


def _changed_pages(github_api: GitHubApiFake, since: str, pages: list[list[int]]) -> None:
    """Answer the listing changed since `since` with one page for each list of issue numbers."""
    base = f"/repos/{REPO}/issues?state=all&sort=updated&direction=desc&since={since}&per_page=100"
    for index, numbers in enumerate(pages, start=1):
        path = base if index == 1 else f"{base}&page={index}"
        more = next_page(f"{base}&page={index + 1}") if index < len(pages) else None
        github_api.route(
            "GET", path, github_json([_opened(number) for number in numbers], headers=more)
        )


def _since(request: str) -> datetime:
    """The `since` of the request `request`, as the fake records it: its method and its URL."""
    return _utc(httpx2.URL(request.partition(" ")[2]).params["since"])


def test_the_listing_reads_the_issue_after_the_watermark_once_and_keeps_the_snapshot(
    github_api: GitHubApiFake, tmp_path: Path
) -> None:
    review, intake = _stores(tmp_path)
    before = _held(intake, full_at=WATERMARK - timedelta(hours=1))
    _changed_since(github_api, "2026-11-11T14:28:04Z")
    reads = Reads()

    records = read_listing(
        get_github_session(), REPO, intake, reads, start=START, review_snapshots=review, now=END
    )

    assert ([record["number"] for record in records], reads.counts["listing"]) == ([2, 1], 1)
    assert intake.path(REPO).read_bytes() == before
    kept = review.load(REPO)
    assert kept is not None
    assert (kept.schema_key, [issue.number for issue in kept.issues]) == (
        LISTING_SCHEMA_KEY,
        [2, 1],
    )


def test_an_old_snapshot_of_this_schema_gives_only_the_changes_after_its_watermark(
    github_api: GitHubApiFake, tmp_path: Path
) -> None:
    """The last full read of intake is 3 days old: the review reads the gap after the watermark,
    not the whole listing, because each listing fact counts issues that changed in the window."""
    review, intake = _stores(tmp_path)
    before = _held(intake, full_at=WATERMARK - timedelta(days=3))
    gap = _changed_since(github_api, "2026-11-11T14:28:04Z")

    records = read_listing(
        get_github_session(), REPO, intake, Reads(), start=START, review_snapshots=review, now=END
    )

    assert ([record["number"] for record in records], github_api.requested) == ([2, 1], [gap])
    assert intake.path(REPO).read_bytes() == before


@pytest.mark.parametrize("schema_key", [None, "0000000000000000"])
def test_with_no_snapshot_of_this_schema_the_listing_reads_the_changes_since_the_window_start(
    github_api: GitHubApiFake, tmp_path: Path, schema_key: str | None
) -> None:
    """No snapshot, or a snapshot of another record schema: the review reads the issues and pull
    requests changed at or after the window start, not the whole listing, and writes its own
    snapshot in place of none."""
    review, intake = _stores(tmp_path)
    before = None if schema_key is None else _held(intake, full_at=WATERMARK, schema_key=schema_key)
    since = _changed_since(github_api, "2026-11-04T14:51:23Z")

    records = read_listing(
        get_github_session(), REPO, intake, Reads(), start=START, review_snapshots=review, now=END
    )

    assert ([record["number"] for record in records], github_api.requested) == ([2], [since])
    path = intake.path(REPO)
    assert (path.read_bytes() if path.exists() else None) == before
    kept = review.load(REPO)
    assert kept is not None
    assert kept.schema_key == LISTING_SCHEMA_KEY


def test_a_second_review_over_a_new_window_reads_only_the_gap_pages(
    github_api: GitHubApiFake, tmp_path: Path
) -> None:
    """The review keeps its own snapshot, so a review whose window holds its watermark reads the
    gap after it: one page, where a review with no store reads three."""
    review, intake = _stores(tmp_path)
    _held(review, full_at=START)
    _changed_pages(github_api, "2026-11-11T14:28:04Z", [[2]])
    _changed_pages(github_api, "2026-11-04T14:51:23Z", [[7, 8], [9, 10], [11]])
    kept = Reads()
    empty = Reads()

    records = read_listing(
        get_github_session(), REPO, intake, kept, start=START, review_snapshots=review, now=END
    )
    read_listing(
        get_github_session(),
        REPO,
        intake,
        empty,
        start=START,
        review_snapshots=FileSnapshotStore(tmp_path / "empty"),
        now=END,
    )

    assert ([record["number"] for record in records], kept.counts["listing"]) == ([2, 1], 1)
    assert kept.counts["listing"] < empty.counts["listing"]
    assert (kept.counts["listing"], empty.counts["listing"]) == (1, 3)
    assert "since=2026-11-11T14:28:04Z" in github_api.requested[0]


def test_a_stale_review_snapshot_reads_from_the_window_start(
    github_api: GitHubApiFake, tmp_path: Path
) -> None:
    """A watermark 3 weeks before the window start reads no page more than a review with no
    snapshot: the gap starts at the window start, and each read names a `since` after it."""
    review, intake = _stores(tmp_path)
    stale = WATERMARK - timedelta(weeks=3)
    _held(review, full_at=stale - timedelta(days=1), watermark=stale)
    _changed_pages(github_api, "2026-11-04T14:51:23Z", [[7, 8], [9, 10], [11]])
    kept = Reads()
    empty = Reads()

    read_listing(
        get_github_session(), REPO, intake, kept, start=START, review_snapshots=review, now=END
    )
    sent = list(github_api.requested)
    read_listing(
        get_github_session(),
        REPO,
        intake,
        empty,
        start=START,
        review_snapshots=FileSnapshotStore(tmp_path / "empty"),
        now=END,
    )

    assert kept.counts["listing"] == empty.counts["listing"]
    assert len(sent) == kept.counts["listing"]
    assert all(_since(request) >= START for request in sent)


class ListingApi:
    """The issue listing of a window as GitHub pages it: `pages` pages of 100 issues each for a read
    from before `WATERMARK`, one page for a read at or after it, and no page after the last."""

    def __init__(self, pages: int) -> None:
        self.pages = pages

    def __call__(self, request: httpx2.Request) -> httpx2.Response | None:
        if not request.url.path.endswith("/issues"):
            return None
        last = 1 if _utc(request.url.params["since"]) >= WATERMARK else self.pages
        page = int(request.url.params.get("page", "1"))
        numbers = range((page - 1) * PER_PAGE + 1, page * PER_PAGE + 1)
        link = (
            next_page(str(request.url.copy_merge_params({"page": str(page + 1)})))
            if page < last
            else None
        )
        return github_json([_opened(number) for number in numbers], headers=link)


def _window() -> ReviewWindow:
    """The 7-day window of a review that ends at `END`."""
    return ReviewWindow(
        kind=WindowKind.PERIOD,
        id="2026-W45",
        base_sha="a" * 40,
        head_sha="b" * 40,
        start=START,
        end=END,
        previous_id=None,
    )


def _github_catalog() -> Catalog:
    """The facts of the shipped catalog that read GitHub, and no other: the GitHub requests of a
    review, without the reads of the cluster and the programs of the openspec reader."""
    shipped = load_catalog()
    return Catalog(
        sections=shipped.sections,
        readers=shipped.readers,
        facts=tuple(fact for fact in shipped.facts if fact.reader in GITHUB_KINDS),
        disagreements=(),
    )


def _route_github_listings(github_api: GitHubApiFake) -> None:
    """Answer each other GitHub listing of the catalog with one page whose newest entry is before
    the window start, so the read stops at that page."""
    old = {"created_at": "2026-11-01T00:00:00Z", "updated_at": "2026-11-01T00:00:00Z"}
    github_api.route(
        "GET",
        f"/repos/{REPO}/releases?per_page=100",
        github_json([{"id": 1, "draft": False, **old}]),
    )
    for query in ("sort=created&direction=desc", "state=fixed&sort=updated&direction=desc"):
        github_api.route(
            "GET",
            f"/repos/{REPO}/code-scanning/alerts?{query}&per_page=100",
            github_json([{"number": 1, "state": "open", "fixed_at": None, **old}]),
        )


def _review(github_api: GitHubApiFake, tmp_path: Path) -> ReadContext:
    """Answer the GitHub reads of a 7-day review, and give its context: no snapshot of any kind, a
    window whose issue listing holds 19 pages, and 3,000 runs in it."""
    review, intake = _stores(tmp_path)
    github_api.serve(ListingApi(LISTING_PAGES))
    github_api.serve(RunsApi(_push_runs(2700, 200, 70, 30)))
    _route_github_listings(github_api)
    return ReadContext(
        checkout=tmp_path,
        repo=REPO,
        window=_window(),
        settings=load_settings(),
        now=END + timedelta(hours=1),
        snapshots=intake,
        review_snapshots=review,
    )


def _github_requests(result: CatalogResult) -> int:
    """The GitHub requests that a review sent, as its reads count them."""
    return sum(result.collection.reads.get(kind, 0) for kind in GITHUB_KINDS)


def test_a_first_seven_day_review_sends_at_most_45_requests(
    github_api: GitHubApiFake, tmp_path: Path
) -> None:
    """A 7-day review with no snapshot of any kind reads 19 pages of the issue listing, a page of
    each other GitHub listing and the five counts of the runs: 45 requests at most (#4692, #6603)."""
    context = _review(github_api, tmp_path)

    result = read_catalog(_github_catalog(), context)

    sent = _github_requests(result)
    assert sent == len(github_api.sent)
    assert sent <= 45


def test_a_second_seven_day_review_sends_at_most_45_requests(
    github_api: GitHubApiFake, tmp_path: Path
) -> None:
    """The second review reads the gap after the watermark that the first one kept, so it sends
    fewer requests than the first and 45 at most (#4692, #6603)."""
    context = _review(github_api, tmp_path)
    first = _github_requests(read_catalog(_github_catalog(), context))
    sent = len(github_api.sent)

    second = read_catalog(_github_catalog(), context)

    reads = _github_requests(second)
    assert reads == len(github_api.sent) - sent
    assert reads < first
    assert reads <= 45


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
