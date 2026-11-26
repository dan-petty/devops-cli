"""The readers of the project review catalog (#4692), each a thin wrapper of an existing client.

- `listing`: the issue listing of the repository, read through the roadmap store. The review keeps
  its own snapshot of the listing (`review_listing`), and reads the issues and pull requests changed
  at or after the later of its watermark and the window start, or from the window start when the
  window starts before the first window that its snapshot covers. With no snapshot of its own it
  reads the snapshot of intake that way, and with neither it reads only the issues and pull requests
  changed at or after the window start, not the whole listing: a listing fact counts what was
  opened, closed, merged or written in the window, and each of these moves `updated_at`. A read
  that starts after the watermark leaves the changes before its start unread, so the kept snapshot
  then covers only the time from that start. It writes the review's snapshot and no snapshot of
  intake, so each snapshot file keeps one writer (#4854, #6603).
- `github`: a REST listing read through `GitHubSession.pages`. A newest-first listing stops after
  the first page that holds an item at or before the window start.
- `github_runs`: the Actions runs of a query, as a count for each status and a count of the window,
  each the `total_count` of a request of one entry. GitHub stops that count at 2,500, so a `created`
  slice whose total reaches the cap splits in two halves until each slice is under it (#6603).
- `prometheus` and `loki`: one instant query at the end of the window (`time`), through
  `PrometheusClient` and `query_loki_metrics`.

`Reads` counts the pages and queries that each reader kind asks for. A retry of a client is not
in the count.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any, Final, Protocol

from devops_cli.config.constants import CONST_ROADMAP_REVIEW_RUN_COUNT_CAP
from devops_cli.config.defaults import DEFAULT_GH_REST_PER_PAGE
from devops_cli.exceptions.roadmap import RoadmapReviewError
from devops_cli.http.egress import EgressLevel
from devops_cli.lang import MESSAGES
from devops_cli.models.prometheus import PrometheusQueryResult
from devops_cli.roadmap.project_review.catalog import ReaderKind, utc_text
from devops_cli.roadmap.stores.listing_snapshot import (
    LISTING_SCHEMA_KEY,
    ListingSnapshot,
    SnapshotStore,
    changed_listing,
    merged,
    snapshot_of,
)
from devops_cli.roadmap.stores.store import IssueRecord

# The statuses of a run whose count the review reads, each with one request: GitHub answers the
# `status` of a request with the runs of that status or of that conclusion.
_RUN_STATUSES: Final = ("success", "failure", "cancelled", "in_progress")
_SECOND: Final = timedelta(seconds=1)


class PagedSession(Protocol):
    """Reads a REST listing one page at a time, as `GitHubSession.pages` does."""

    def pages(self, path: str, *, max_pages: int | None = ...) -> Iterator[Any]: ...


@dataclass
class Reads:
    """The pages and queries that each reader kind asked for."""

    counts: Counter[str] = field(default_factory=Counter)

    def add(self, kind: ReaderKind, number: int = 1) -> None:
        self.counts[kind] += number


def _with_page_size(path: str) -> str:
    """`path` from the API root with a full page of entries."""
    separator = "&" if "?" in path else "?"
    return f"/{path.lstrip('/')}{separator}per_page={DEFAULT_GH_REST_PER_PAGE}"


def _time(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    return datetime.fromisoformat(value).astimezone(UTC)


@dataclass(frozen=True)
class _CountedPages:
    """A listing session for the roadmap store that reads each page through `session` and counts
    it as a `listing` read."""

    session: PagedSession
    reads: Reads

    def paginate(self, path: str, *, iterable_key: str | None = None) -> Iterator[Any]:
        for page in self.session.pages(path):
            self.reads.add(ReaderKind.LISTING)
            items = page.get(iterable_key) if iterable_key and isinstance(page, dict) else page
            if not isinstance(items, list):
                raise RoadmapReviewError(MESSAGES.roadmap.review_page_not_a_list.format(path=path))
            yield from items


@dataclass(frozen=True)
class _ReviewListing:
    """How the review reads every issue and pull request of a repository: the snapshot that
    `review_snapshots` keeps, else the one of intake, and the changes after the later of its
    watermark and `start`; or only the changes at or after `start` when neither snapshot has this
    record schema. Each read keeps the merged records in `review_snapshots`, and leaves the snapshot
    of intake as it is (#6603). The `full_at` of the kept snapshot is the first time from which it
    holds each change: the gap start when the gap starts after the watermark, as no change between
    the two was read."""

    review_snapshots: SnapshotStore
    snapshots: SnapshotStore
    start: datetime
    now: datetime

    def read(
        self, repo: str, read_issues: Callable[[str], list[IssueRecord]]
    ) -> dict[int, IssueRecord]:
        held, own = self._held(repo)
        if held is None:
            gap = full_at = self.start
            listed = {issue.number: issue for issue in read_issues(changed_listing(gap))}
        else:
            gap = self._gap(held, own=own)
            full_at = gap if gap > held.watermark else min(held.full_at, self.start)
            listed = merged(held.issues, read_issues(changed_listing(gap)))
        self.review_snapshots.save(
            snapshot_of(
                repo, listed, schema_key=LISTING_SCHEMA_KEY, full_at=full_at, started=self.now
            )
        )
        return listed

    def drop(self, repo: str, number: int) -> None:
        """Nothing: the review reads no issue by its number, so its store names no number that
        left the repository (#7331)."""

    def _gap(self, held: ListingSnapshot, *, own: bool) -> datetime:
        """Where the changes are read from: the later of the watermark of `held` and `start`, or
        `start` when it is before the first window that the review's own snapshot covers, which
        holds no record from before it."""
        if own and self.start < held.full_at:
            return self.start
        return max(held.watermark, self.start)

    def _held(self, repo: str) -> tuple[ListingSnapshot | None, bool]:
        """The snapshot the changes are read from, and whether it is the review's own: the review's
        own first, then the one of intake, each when its records have this schema."""
        own = self._fit(self.review_snapshots.load(repo))
        if own is not None:
            return own, True
        return self._fit(self.snapshots.load(repo)), False

    @staticmethod
    def _fit(held: ListingSnapshot | None) -> ListingSnapshot | None:
        """`held` when its records have the schema of this release."""
        return held if held is not None and held.schema_key == LISTING_SCHEMA_KEY else None


def read_listing(
    session: PagedSession,
    repo: str,
    snapshots: SnapshotStore,
    reads: Reads,
    *,
    start: datetime,
    review_snapshots: SnapshotStore,
    now: datetime,
) -> list[dict[str, Any]]:
    """The issues and pull requests of `repo` as JSON, the highest number first: the snapshot that
    the review keeps, else the one of intake, and the changes after the later of its watermark and
    `start`, or only the changes at or after `start` when neither snapshot has this record schema.
    The review keeps the merged records in `review_snapshots` and writes no snapshot of intake. The
    body of an issue is left out."""
    from devops_cli.roadmap.stores.github_store import GitHubRoadmapStore

    listing = _ReviewListing(review_snapshots, snapshots, start, now)
    store = GitHubRoadmapStore(repo, session=_CountedPages(session, reads), listing=listing)
    records = sorted(store.listing(), key=lambda record: record.number, reverse=True)
    return [record.model_dump(mode="json", exclude={"body"}) for record in records]


def read_github(
    session: PagedSession,
    path: str,
    start: datetime,
    reads: Reads,
    *,
    newest_first: str | None = None,
    paginate: bool = True,
) -> list[Any]:
    """The entries of the REST listing at `path`, page by page. With `newest_first`, the read
    stops after the first page that holds an entry whose `newest_first` time is at or before
    `start`. A page that is not an array is kept whole. Set `paginate=False` for single resources
    such as `/repos/<owner>/<name>/contents/<path>`."""
    found: list[Any] = []
    target = _with_page_size(path) if paginate else f"/{path.lstrip('/')}"
    for page in session.pages(target):
        reads.add(ReaderKind.GITHUB)
        if not isinstance(page, list):
            found.append(page)
            continue
        found.extend(page)
        if newest_first is not None and any(
            (moment := _time(entry.get(newest_first))) is not None and moment <= start
            for entry in page
            if isinstance(entry, dict)
        ):
            break
    return found


def _created(low: datetime, high: datetime) -> str:
    """The `created` range of GitHub from `low` to `high`, both in whole seconds."""
    return f"{utc_text(low)}..{utc_text(high)}"


def _count_path(path: str, low: datetime, high: datetime, status: str | None) -> str:
    """The listing at `path` of the runs created from `low` to `high`, both in whole seconds, of
    `status` when it is given, of the first entry only: its `total_count` is the count of them."""
    separator = "&" if "?" in path else "?"
    query = f"{path}{separator}created={_created(low, high)}&per_page=1"
    return query if status is None else f"{query}&status={status}"


def _run_count(
    session: PagedSession,
    path: str,
    low: datetime,
    high: datetime,
    reads: Reads,
    status: str | None,
) -> int:
    """The count of the Actions runs of `path` created from `low` to `high`, of `status` when it is
    given, from one request of one entry. A page with no `total_count` that is a whole number at or
    above 0 raises `RoadmapReviewError`, so a missing count is never 0."""
    reads.add(ReaderKind.GITHUB_RUNS)
    page = next(session.pages(_count_path(path, low, high, status)))
    count = page.get("total_count") if isinstance(page, dict) else None
    if isinstance(count, bool) or not isinstance(count, int) or count < 0:
        raise RoadmapReviewError(
            MESSAGES.roadmap.review_runs_no_count.format(slice=_created(low, high))
        )
    return count


def read_runs(
    session: PagedSession, path: str, start: datetime, end: datetime, reads: Reads
) -> dict[str, Any]:
    """The Actions runs of the listing at `path` created after `start` up to `end`, as
    `{"statuses", "total_count"}`: the count of the runs of each status of `_RUN_STATUSES`, and the
    count of every run of the window (#6603).

    GitHub reads a `created` range in whole seconds, both ends in, and stops the `total_count` of a
    filtered list at `CONST_ROADMAP_REVIEW_RUN_COUNT_CAP`. The reader reads the total of a slice
    first. A slice at the cap splits in two halves by created time, and a slice under it gets one
    count for each status, so a window under the cap costs five requests. A page with no count, a
    slice of one second at the cap, or status counts above the total of a slice raise
    `RoadmapReviewError`, so no count is wrong with no message. A run of another status is in
    `total_count` and in no status count."""
    cap = CONST_ROADMAP_REVIEW_RUN_COUNT_CAP
    statuses = dict.fromkeys(_RUN_STATUSES, 0)
    total = 0
    slices = [(start.replace(microsecond=0) + _SECOND, end.replace(microsecond=0))]
    while slices:
        low, high = slices.pop()
        named = _created(low, high)
        count = _run_count(session, path, low, high, reads, None)
        if count >= cap:
            if high <= low:
                raise RoadmapReviewError(
                    MESSAGES.roadmap.review_runs_at_cap.format(cap=f"{cap:,}", slice=named)
                )
            middle = low + timedelta(seconds=int((high - low).total_seconds()) // 2)
            slices.extend([(middle + _SECOND, high), (low, middle)])
            continue
        counts = {
            status: _run_count(session, path, low, high, reads, status) for status in statuses
        }
        if (counted := sum(counts.values())) > count:
            raise RoadmapReviewError(
                MESSAGES.roadmap.review_runs_above_total.format(
                    slice=named, counted=f"{counted:,}", total=f"{count:,}"
                )
            )
        total += count
        for status, number in counts.items():
            statuses[status] += number
    return {"statuses": statuses, "total_count": total}


def read_prometheus(
    base_url: str, level: EgressLevel, query: str, at: datetime, reads: Reads
) -> PrometheusQueryResult:
    """The vector of the instant query `query` at the time `at`."""
    from devops_cli.prometheus.client import PrometheusClient

    reads.add(ReaderKind.PROMETHEUS)
    with PrometheusClient(base_url, level) as client:
        return PrometheusQueryResult.from_instant_response(client.query(query, at=utc_text(at)))


def read_loki(loki_url: str, query: str, at: datetime, reads: Reads) -> PrometheusQueryResult:
    """The vector of the LogQL metric query `query` at the time `at`."""
    from devops_cli.k8s.logql import query_loki_metrics

    reads.add(ReaderKind.LOKI)
    [result] = query_loki_metrics([query], loki_url, at=utc_text(at))
    return result
