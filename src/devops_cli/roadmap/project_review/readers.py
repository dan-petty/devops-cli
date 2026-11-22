"""The readers of the project review catalog (#4692), each a thin wrapper of an existing client.

- `listing`: the issue listing of the repository, read through the roadmap store. The review keeps
  its own snapshot of the listing (`review_listing`), and reads the issues and pull requests changed
  at or after the later of its watermark and the window start, or from the window start when the
  window starts before the first window that its snapshot covers. With no snapshot of its own it
  reads the snapshot of intake that way, and with neither it reads only the issues and pull requests
  changed at or after the window start, not the whole listing: a listing fact counts what was
  opened, closed, merged or written in the window, and each of these moves `updated_at`. It writes
  the review's snapshot and no snapshot of intake, so each snapshot file keeps one writer (#4854,
  #6603).
- `github`: a REST listing read through `GitHubSession.pages`. A newest-first listing stops after
  the first page that holds an item at or before the window start.
- `github_runs`: the Actions runs of a query, as a count for each status and a count of the window.
  GitHub gives the exact `total_count` of a filtered list, above its result cap of 1,000, so five
  requests of one entry replace the pages of runs (#6603).
- `prometheus` and `loki`: one instant query at the end of the window (`time`), through
  `PrometheusClient` and `query_loki_metrics`.

`Reads` counts the pages and queries that each reader kind asks for. A retry of a client is not
in the count.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Final, Protocol

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
    of intake as it is (#6603)."""

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
            full_at = min(held.full_at, self.start)
            listed = merged(held.issues, read_issues(changed_listing(gap)))
        self.review_snapshots.save(
            snapshot_of(
                repo, listed, schema_key=LISTING_SCHEMA_KEY, full_at=full_at, started=self.now
            )
        )
        return listed

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
) -> list[Any]:
    """The entries of the REST listing at `path`, page by page. With `newest_first`, the read
    stops after the first page that holds an entry whose `newest_first` time is at or before
    `start`. A page that is not an array is kept whole."""
    found: list[Any] = []
    for page in session.pages(_with_page_size(path)):
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


def _count_path(path: str, start: datetime, end: datetime, status: str | None) -> str:
    """The listing at `path` of the runs created in the window, of `status` when it is given, of
    the first entry only: its `total_count` is the count of them."""
    separator = "&" if "?" in path else "?"
    query = f"{path}{separator}created={utc_text(start)}..{utc_text(end)}&per_page=1"
    return query if status is None else f"{query}&status={status}"


def _run_count(
    session: PagedSession,
    path: str,
    start: datetime,
    end: datetime,
    reads: Reads,
    status: str | None,
) -> int:
    """The count of the Actions runs of `path` created in the window, of `status` when it is given,
    from one request of one entry."""
    reads.add(ReaderKind.GITHUB_RUNS)
    page = next(session.pages(_count_path(path, start, end, status)))
    return int(page.get("total_count", 0))


def read_runs(
    session: PagedSession, path: str, start: datetime, end: datetime, reads: Reads
) -> dict[str, Any]:
    """The Actions runs of the listing at `path` created in the window, as `{"statuses",
    "total_count"}`: the count of the runs of each status of `_RUN_STATUSES`, and the count of every
    run of the window, each from one request of one entry (#6603).

    GitHub gives the exact `total_count` of a filtered list above its result cap, so the five counts
    replace the pages of runs. A run of another status is in `total_count` and in no status count."""
    statuses = {
        status: _run_count(session, path, start, end, reads, status) for status in _RUN_STATUSES
    }
    total = _run_count(session, path, start, end, reads, None)
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
