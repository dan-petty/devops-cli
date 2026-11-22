"""The readers of the project review catalog (#4692): the count of the Actions runs of each status
by created slices under the count cap of GitHub, a newest-first listing that stops at the window
start, the review's own listing snapshot with the changes after its watermark (#6603), the GitHub
requests of a 7-day review, and Prometheus and Loki read at the end of the window."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx2
import pytest

import devops_cli.roadmap.stores.listing_snapshot as listing_snapshot
from devops_cli.config.settings import load_settings
from devops_cli.exceptions.roadmap import RoadmapReviewError
from devops_cli.github.session import get_github_session
from devops_cli.http.egress import EgressLevel
from devops_cli.roadmap.project_review.catalog import Catalog, ReaderKind, load_catalog
from devops_cli.roadmap.project_review.data import FactStatus, ReviewWindow, WindowKind
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
    snapshot_root,
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
# GitHub stops the `total_count` of a filtered list of Actions runs at 2,500: on 2026-11-22 a
# 30-day window of main push runs gave the total 2,500 and 2,500 successful runs (#6603).
CAP = 2500
# The entries of a page of the issue listing.
PER_PAGE = 100
# The `created` range of the window: after its start, in whole seconds, up to its end.
WINDOW_RANGE = "2026-11-04T14:51:24Z..2026-11-11T14:51:23Z"
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


def _run(number: int, moment: datetime, conclusion: str) -> dict[str, Any]:
    """A completed run with `conclusion`, created at `moment`."""
    return {
        "id": number,
        "created_at": moment.strftime(_TIME),
        "status": "completed",
        "conclusion": conclusion,
    }


class RunsApi:
    """The Actions runs of the window as GitHub counts them: the runs of a `created` range, both
    ends in and in whole seconds, of the status or the conclusion that the request filters on. As
    on GitHub, the `total_count` of such a filtered list stops at the cap of 2,500, and the page
    holds the first `per_page` runs, newest first."""

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
        return github_json({"total_count": min(len(found), CAP), "workflow_runs": found[:per_page]})


def _counts(total: int, each: int) -> Callable[[httpx2.Request], httpx2.Response | None]:
    """A runs listing that gives the `total_count` `total` with no status filter, and `each` for
    each status."""

    def answer(request: httpx2.Request) -> httpx2.Response | None:
        if not request.url.path.endswith("/actions/runs"):
            return None
        count = total if request.url.params.get("status") is None else each
        return github_json({"total_count": count, "workflow_runs": []})

    return answer


def test_a_window_under_the_cap_reads_its_total_then_one_count_for_each_status(
    github_api: GitHubApiFake,
) -> None:
    """A 7-day window of 2,000 runs is under the count cap: the reader reads the total of the
    window first, then one count for each status, each of one entry, so five requests replace the
    pages of runs (#6603)."""
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
    assert [request.url.params["created"] for request in github_api.sent] == [WINDOW_RANGE] * 5
    assert [request.url.params.get("status") for request in github_api.sent] == [
        None,
        "success",
        "failure",
        "cancelled",
        "in_progress",
    ]


def test_a_window_above_the_cap_splits_in_halves_whose_counts_add_up(
    github_api: GitHubApiFake,
) -> None:
    """A window of 4,500 runs gives the total 2,500, the cap, so the reader splits it in two halves
    by created time in whole seconds. Each half is under the cap, and the counts of the halves add
    up to the exact counts of the window (#6603)."""
    github_api.serve(RunsApi(_push_runs(4000, 300, 150, 50)))
    reads = Reads()

    answer = read_runs(get_github_session(), RUNS, START, END, reads)

    assert answer["statuses"] == {
        "success": 4000,
        "failure": 300,
        "cancelled": 150,
        "in_progress": 50,
    }
    assert answer["total_count"] == 4500
    assert reads.counts["github_runs"] == len(github_api.sent) == 11
    totals = [request for request in github_api.sent if "status" not in request.url.params]
    assert [request.url.params["created"] for request in totals] == [
        WINDOW_RANGE,
        "2026-11-04T14:51:24Z..2026-11-08T02:51:23Z",
        "2026-11-08T02:51:24Z..2026-11-11T14:51:23Z",
    ]


def test_a_slice_of_one_second_at_the_cap_raises(github_api: GitHubApiFake) -> None:
    """One second holds 2,500 runs, the count cap of GitHub. A slice of one second cannot split,
    so the reader cannot count each run, and it raises in place of a count that is too low."""
    github_api.serve(RunsApi([_run(number, END, "success") for number in range(1, CAP + 1)]))
    reads = Reads()

    with pytest.raises(RoadmapReviewError, match="2,500"):
        read_runs(get_github_session(), RUNS, END - timedelta(seconds=1), END, reads)

    assert reads.counts["github_runs"] == 1


def test_status_counts_above_the_total_of_a_slice_raise(github_api: GitHubApiFake) -> None:
    """The four status counts of a slice add up to 16, and its total is 10. GitHub cut or changed
    a count, so the reader raises in place of a wrong count."""
    github_api.serve(_counts(total=10, each=4))

    with pytest.raises(RoadmapReviewError, match="16"):
        read_runs(get_github_session(), RUNS, START, END, Reads())


def test_a_run_in_the_start_second_counts_in_the_window_before_and_not_in_this_one(
    github_api: GitHubApiFake,
) -> None:
    """GitHub reads both ends of a `created` range in whole seconds. The window holds the runs
    after its start up to its end, so a run in the start second counts in the window that ends
    there, and in no other window."""
    github_api.serve(RunsApi([_run(1, START, "success"), _run(2, END, "failure")]))
    session = get_github_session()

    this = read_runs(session, RUNS, START, END, Reads())
    before = read_runs(session, RUNS, START - timedelta(days=7), START, Reads())

    assert (this["total_count"], this["statuses"]["success"], this["statuses"]["failure"]) == (
        1,
        0,
        1,
    )
    assert (before["total_count"], before["statuses"]["success"]) == (1, 1)


def test_a_skipped_run_is_in_the_total_and_in_no_status_count(github_api: GitHubApiFake) -> None:
    """A window of 2,000 runs holds 3 skipped runs: the total of the window holds every run, and
    the four status counts hold the others, with no key for the skipped runs (#6603)."""
    skipped = [
        _run(2000 + minutes, END - timedelta(minutes=minutes), "skipped") for minutes in (1, 2, 3)
    ]
    github_api.serve(RunsApi([*_push_runs(1500, 400, 70, 27), *skipped]))
    reads = Reads()

    answer = read_runs(get_github_session(), RUNS, START, END, reads)

    assert answer["total_count"] == 2000
    assert sum(answer["statuses"].values()) == 1997
    assert "skipped" not in answer["statuses"]
    assert reads.counts["github_runs"] == len(github_api.sent) == 5


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
    """The first review reads its window and keeps its own snapshot. The second review is over a
    new window one day later, which holds the watermark of the first one, so it reads only the gap
    after that watermark: one page, where a review of the new window with no store reads three."""
    review, intake = _stores(tmp_path)
    day = timedelta(days=1)
    _changed_pages(github_api, "2026-11-04T14:51:23Z", [[7, 8], [9, 10], [11]])
    _changed_pages(github_api, "2026-11-05T14:51:23Z", [[7, 8], [9, 10], [11]])
    # The watermark of the first review: its newest change, 2026-11-11T14:40:00Z, less 60 s.
    _changed_pages(github_api, "2026-11-11T14:39:00Z", [[2]])
    first, second, empty = Reads(), Reads(), Reads()
    session = get_github_session()

    read_listing(session, REPO, intake, first, start=START, review_snapshots=review, now=END)
    sent = len(github_api.requested)
    records = read_listing(
        session, REPO, intake, second, start=START + day, review_snapshots=review, now=END + day
    )
    gap = github_api.requested[sent:]
    read_listing(
        session,
        REPO,
        intake,
        empty,
        start=START + day,
        review_snapshots=FileSnapshotStore(tmp_path / "empty"),
        now=END + day,
    )

    assert [record["number"] for record in records] == [11, 10, 9, 8, 7, 2]
    assert (first.counts["listing"], second.counts["listing"], empty.counts["listing"]) == (3, 1, 3)
    assert [_since(request) for request in gap] == [_utc("2026-11-11T14:39:00Z")]


def _issue(number: int, changed: str, *, closed: bool = False) -> dict[str, Any]:
    """An issue as the issue listing gives it, last changed at `changed`, closed then when
    `closed`."""
    return {
        "number": number,
        "title": f"Issue {number}",
        "html_url": f"https://github.com/{REPO}/issues/{number}",
        "state": "closed" if closed else "open",
        "created_at": "2026-08-01T00:00:00Z",
        "updated_at": changed,
        "closed_at": changed if closed else None,
    }


class ChangedApi:
    """The issue listing as GitHub answers a read of the changes: each issue whose `updated_at` is
    at or after `since`, newest change first, on one page. `change` gives an issue a new record."""

    def __init__(self, *issues: dict[str, Any]) -> None:
        self.issues = {issue["number"]: issue for issue in issues}

    def change(self, issue: dict[str, Any]) -> None:
        self.issues[issue["number"]] = issue

    def __call__(self, request: httpx2.Request) -> httpx2.Response | None:
        if not request.url.path.endswith("/issues"):
            return None
        since = _utc(request.url.params["since"])
        found = [issue for issue in self.issues.values() if _utc(issue["updated_at"]) >= since]
        found.sort(key=lambda issue: str(issue["updated_at"]), reverse=True)
        return github_json(found)


def test_a_wider_review_reads_a_change_between_the_watermark_and_a_later_window_start(
    github_api: GitHubApiFake, tmp_path: Path
) -> None:
    """Review A keeps a snapshot with the watermark 2026-09-14T23:59:00Z. Issue 2 closes on
    2026-10-06. Review B starts on 2026-10-14, after that watermark, so it reads the changes only
    from its start, and its snapshot covers only the time from there. Review C starts on
    2026-09-21, before the start of B, so it reads from its own start and gives the closed record
    of issue 2, not the open record that A kept."""
    review, intake = _stores(tmp_path)
    issues = ChangedApi(_issue(1, "2026-09-15T00:00:00Z"), _issue(2, "2026-09-10T00:00:00Z"))
    github_api.serve(issues)
    session = get_github_session()

    def run(start: str, now: str) -> list[dict[str, Any]]:
        return read_listing(
            session,
            REPO,
            intake,
            Reads(),
            start=_utc(start),
            review_snapshots=review,
            now=_utc(now),
        )

    run("2026-09-01T00:00:00Z", "2026-10-01T00:00:00Z")
    issues.change(_issue(2, "2026-10-06T00:00:00Z", closed=True))
    issues.change(_issue(3, "2026-10-18T00:00:00Z"))
    run("2026-10-14T00:00:00Z", "2026-10-21T00:00:00Z")
    records = run("2026-09-21T00:00:00Z", "2026-10-22T00:00:00Z")

    assert [(record["number"], record["state"]) for record in records] == [
        (3, "open"),
        (2, "closed"),
        (1, "open"),
    ]
    assert _since(github_api.requested[-1]) == _utc("2026-09-21T00:00:00Z")


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


def test_a_window_before_the_review_snapshot_reads_from_its_start(
    github_api: GitHubApiFake, tmp_path: Path
) -> None:
    """The review's own snapshot holds the records of the windows from its first start on. A window
    that starts before that first start holds no record of the snapshot, so the gap starts at the
    window start and not at the later watermark."""
    review, intake = _stores(tmp_path)
    _held(review, full_at=START + timedelta(days=2))
    since = _changed_since(github_api, "2026-11-04T14:51:23Z")

    records = read_listing(
        get_github_session(), REPO, intake, Reads(), start=START, review_snapshots=review, now=END
    )

    assert ([record["number"] for record in records], github_api.requested) == ([2, 1], [since])


def test_the_review_keeps_its_snapshot_apart_from_the_one_of_intake(
    tmp_path: Path, isolate_data_dir: Path
) -> None:
    """The review keeps `review-listing` in the state directory of the roadmap, and intake keeps
    `listing` there, so each snapshot file has one writer (#4854). Each store reads the state
    directory that a caller gives, and the state directory of the roadmap with none."""
    state = isolate_data_dir / "roadmap"
    owner, _, name = REPO.partition("/")
    kept = state / "review-listing" / owner / f"{name}.json"
    held = state / "listing"

    assert (listing_snapshot.review_listing().path(REPO), snapshot_root()) == (kept, held)
    assert (listing_snapshot.review_listing(tmp_path).path(REPO), snapshot_root(tmp_path)) == (
        tmp_path / "review-listing" / owner / f"{name}.json",
        tmp_path / "listing",
    )


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


def _context(tmp_path: Path) -> ReadContext:
    """The context of a 7-day review that ends at `END`, with an empty review store and an empty
    intake store under `tmp_path`."""
    review, intake = _stores(tmp_path)
    return ReadContext(
        checkout=tmp_path,
        repo=REPO,
        window=_window(),
        settings=load_settings(),
        now=END + timedelta(hours=1),
        snapshots=intake,
        review_snapshots=review,
    )


def _review(github_api: GitHubApiFake, tmp_path: Path) -> ReadContext:
    """Answer the GitHub reads of a 7-day review, and give its context: no snapshot of any kind, a
    window whose issue listing holds 19 pages, and 1,853 runs in it, the count of the main push
    runs of the week to 2026-11-22."""
    github_api.serve(ListingApi(LISTING_PAGES))
    github_api.serve(RunsApi(_push_runs(1743, 27, 77, 6)))
    _route_github_listings(github_api)
    return _context(tmp_path)


def test_the_main_push_runs_fact_gives_the_four_counts_and_the_total_of_the_window(
    github_api: GitHubApiFake, tmp_path: Path
) -> None:
    """The shipped fact `github_runs.main_push_runs` of a window of 2,072 runs, under the count cap:
    its value is the count of each of the four statuses, and its n is the total of the window."""
    shipped = load_catalog()
    catalog = Catalog(
        sections=shipped.sections,
        readers=shipped.readers,
        facts=tuple(fact for fact in shipped.facts if fact.id == "github_runs.main_push_runs"),
        disagreements=(),
    )
    github_api.serve(RunsApi(_push_runs(1927, 29, 104, 12)))

    result = read_catalog(catalog, _context(tmp_path))

    [fact] = result.facts
    assert (fact.status, fact.value, fact.n) == (
        FactStatus.OK,
        {"success": 1927, "failure": 29, "cancelled": 104, "in_progress": 12},
        2072,
    )
    assert result.collection.reads == {ReaderKind.GITHUB_RUNS: 5}


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
    first = read_catalog(_github_catalog(), context)
    sent = len(github_api.sent)

    second = read_catalog(_github_catalog(), context)

    reads = _github_requests(second)
    assert reads == len(github_api.sent) - sent
    assert reads < _github_requests(first)
    assert reads <= 45
    listing = ReaderKind.LISTING
    assert second.collection.reads[listing] < first.collection.reads[listing]


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
