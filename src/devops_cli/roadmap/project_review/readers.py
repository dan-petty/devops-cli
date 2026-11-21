"""The readers of the project review catalog (#4692), each a thin wrapper of an existing client.

- `listing`: the issue listing that intake keeps as a snapshot, with the issues and pull requests
  changed at or after its watermark (`issues?since=<watermark>`), read through the roadmap store.
  The snapshot can be of any age when its records have the schema of this release. With no such
  snapshot, the reader reads only the issues and pull requests changed at or after the window
  start, not the whole listing: a listing fact counts what was opened, closed, merged or written
  in the window, and each of these moves `updated_at`. The review never writes a snapshot, so each
  snapshot file keeps one writer (#4854).
- `github`: a REST listing read through `GitHubSession.pages`. A newest-first listing stops after
  the first page that holds an item at or before the window start.
- `github_runs`: the Actions runs of a query. GitHub gives at most 1,000 results of a filtered list
  of runs, so a `created` slice whose `total_count` reaches the cap splits in two halves until
  each slice holds fewer runs. Each run is given once.
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

from devops_cli.config.defaults import (
    DEFAULT_GH_REST_PER_PAGE,
    DEFAULT_ROADMAP_REVIEW_RUN_RESULT_CAP,
)
from devops_cli.exceptions.roadmap import RoadmapReviewError
from devops_cli.http.egress import EgressLevel
from devops_cli.lang import MESSAGES
from devops_cli.models.prometheus import PrometheusQueryResult
from devops_cli.roadmap.project_review.catalog import ReaderKind, utc_text
from devops_cli.roadmap.stores.listing_snapshot import (
    LISTING_SCHEMA_KEY,
    SnapshotStore,
    changed_listing,
    merged,
)
from devops_cli.roadmap.stores.store import IssueRecord

_RUNS_KEY: Final = "workflow_runs"
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
    `snapshots` keeps, whatever the age of its last full read, and the changes after its watermark;
    or only the changes at or after `start` when no snapshot of this record schema is kept. It
    writes no snapshot."""

    snapshots: SnapshotStore
    start: datetime

    def read(
        self, repo: str, read_issues: Callable[[str], list[IssueRecord]]
    ) -> dict[int, IssueRecord]:
        held = self.snapshots.load(repo)
        if held is None or held.schema_key != LISTING_SCHEMA_KEY:
            return {issue.number: issue for issue in read_issues(changed_listing(self.start))}
        return merged(held.issues, read_issues(changed_listing(held.watermark)))


def read_listing(
    session: PagedSession,
    repo: str,
    snapshots: SnapshotStore,
    reads: Reads,
    *,
    start: datetime,
) -> list[dict[str, Any]]:
    """The issues and pull requests of `repo` as JSON, the highest number first: the snapshot that
    `snapshots` keeps and the changes after its watermark, or only the changes at or after `start`
    when no snapshot of this record schema is kept. The snapshot is not written, and the body of an
    issue is left out."""
    from devops_cli.roadmap.stores.github_store import GitHubRoadmapStore

    listing = _ReviewListing(snapshots, start)
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


def _slice_path(path: str, low: datetime, high: datetime) -> str:
    separator = "&" if "?" in path else "?"
    return _with_page_size(f"{path}{separator}created={utc_text(low)}..{utc_text(high)}")


def read_runs(
    session: PagedSession, path: str, start: datetime, end: datetime, reads: Reads
) -> dict[str, Any]:
    """The Actions runs of the listing at `path` created after `start` up to `end`, each once, as
    `{"total_count", "workflow_runs"}`, newest first.

    GitHub reads a `created` range in whole seconds, both ends in. A slice whose `total_count`
    reaches the result cap splits in two halves by created time, and only a slice under the cap
    is read to its last page. A slice of one second at the cap raises `RoadmapReviewError`, so
    no run is lost with no message."""
    cap = DEFAULT_ROADMAP_REVIEW_RUN_RESULT_CAP
    runs: dict[Any, Any] = {}
    slices = [(start.replace(microsecond=0) + _SECOND, end.replace(microsecond=0))]
    while slices:
        low, high = slices.pop()
        pages = session.pages(_slice_path(path, low, high))
        for number, page in enumerate(pages, start=1):
            reads.add(ReaderKind.GITHUB_RUNS)
            if number == 1 and int(page.get("total_count", 0)) >= cap:
                if high <= low:
                    raise RoadmapReviewError(
                        MESSAGES.roadmap.review_runs_at_cap.format(
                            cap=f"{cap:,}", slice=f"{utc_text(low)}..{utc_text(high)}"
                        )
                    )
                middle = low + timedelta(seconds=int((high - low).total_seconds()) // 2)
                slices.extend([(middle + _SECOND, high), (low, middle)])
                break
            for run in page.get(_RUNS_KEY, []):
                runs[run["id"]] = run
    ordered = sorted(runs.values(), key=lambda run: str(run.get("created_at", "")), reverse=True)
    return {"total_count": len(ordered), _RUNS_KEY: ordered}


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
