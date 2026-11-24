"""The project-brain cache of GitHub issues in the store (#6013).

Rows read the cached issue first from the shared tier, revalidating after one hour with
`If-None-Match`, and store writes update the entry.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pytest
from fakeredis import FakeServer

from devops_cli.exceptions.git import GitHubOperationError
from devops_cli.github.request_scope import request_scope
from devops_cli.github.session import get_github_session
from devops_cli.roadmap.stores.brain_issues import (
    CachedIssue,
    cached_issue,
    remember_issue,
)
from devops_cli.roadmap.stores.github_store import GitHubRoadmapStore
from devops_cli.roadmap.stores.store import IssueRecord
from devops_cli.telemetry.instruments import BRAIN_CACHE_TOTAL
from tests.support.fakes.otlp import FakeCollector
from tests.support.roadmap_github_store import REPO, RecordedGh, issue_payload

if TYPE_CHECKING:
    from devops_cli.valkey.cache import ValkeyCacheTier


def _store(runner: RecordedGh) -> GitHubRoadmapStore:
    return GitHubRoadmapStore(REPO, runner=runner, session=get_github_session())


def _summed_cache(otlp: FakeCollector) -> dict[tuple[str, str], float]:
    counted: dict[tuple[str, str], float] = {}
    for attrs, value in otlp.points(BRAIN_CACHE_TOTAL.name):
        counted[(attrs.get("row", ""), attrs.get("result", ""))] = (
            counted.get((attrs.get("row", ""), attrs.get("result", "")), 0.0) + value
        )
    return counted


def test_a_fresh_entry_sends_no_request(
    shared_valkey: ValkeyCacheTier, valkey_server: FakeServer, otlp: FakeCollector
) -> None:
    """A fresh entry in the tier returns the issue with no GitHub request and counts a hit."""
    now = datetime.now(UTC)
    record = IssueRecord(
        number=6013,
        title="Cache issue state",
        url=f"https://github.com/{REPO}/issues/6013",
        labels=("type/feature",),
        updated_at=now,
    )
    remember_issue(REPO, CachedIssue(record=record, etag="W/'1'", checked_at=now))

    runner = RecordedGh({})
    store = _store(runner)
    with request_scope(row="refine"):
        found = store.issue(6013)

    assert found == record
    assert len(runner.calls) == 0
    assert _summed_cache(otlp).get(("refine", "hit")) == 1.0


def test_a_miss_reads_github_once_and_fills_the_entry(
    shared_valkey: ValkeyCacheTier, valkey_server: FakeServer, otlp: FakeCollector
) -> None:
    """A missing issue reads GitHub once, writes the tier, and counts a miss."""
    payload = issue_payload(6013, title="Fetched issue")
    runner = RecordedGh({"issues/6013": payload})
    store = _store(runner)

    with request_scope(row="stage"):
        found = store.issue(6013)

    assert found is not None
    assert found.title == "Fetched issue"
    assert len(runner.calls) == 1
    assert _summed_cache(otlp).get(("stage", "miss")) == 1.0

    cached = cached_issue(REPO, 6013)
    assert cached is not None
    assert cached.record.title == "Fetched issue"


def test_a_label_write_fills_the_entry(
    shared_valkey: ValkeyCacheTier, valkey_server: FakeServer
) -> None:
    """A label write updates the tier with the new label set."""
    now = datetime.now(UTC)
    record = IssueRecord(
        number=6013,
        title="Labeled issue",
        url=f"https://github.com/{REPO}/issues/6013",
        labels=("type/feature",),
        updated_at=now,
    )
    remember_issue(REPO, CachedIssue(record=record, etag=None, checked_at=now))

    runner = RecordedGh({"labels": ""})
    store = _store(runner)
    store.label_issue(6013, "status/ready")

    cached = cached_issue(REPO, 6013)
    assert cached is not None
    assert "status/ready" in cached.record.labels
    assert "type/feature" in cached.record.labels


def test_the_tier_refuses_a_connection(
    shared_valkey: ValkeyCacheTier, valkey_server: FakeServer
) -> None:
    """When Valkey is down, the read falls back to GitHub with no error."""
    payload = issue_payload(6013, title="Fallback issue")
    runner = RecordedGh({"issues/6013": payload})
    store = _store(runner)

    valkey_server.connected = False
    with request_scope(row="implement"):
        found = store.issue(6013)

    assert found is not None
    assert found.title == "Fallback issue"
    assert len(runner.calls) == 1


def test_a_second_read_in_the_same_hour_sends_no_request(
    shared_valkey: ValkeyCacheTier, valkey_server: FakeServer
) -> None:
    """Two reads within the hour send only one GitHub request."""
    payload = issue_payload(6013, title="Hour read")
    runner = RecordedGh({"issues/6013": payload})
    store = _store(runner)

    first = store.issue(6013)
    second = store.issue(6013)

    assert first == second
    assert len(runner.calls) == 1


def test_a_304_answer_keeps_the_stored_issue(
    shared_valkey: ValkeyCacheTier, valkey_server: FakeServer, otlp: FakeCollector
) -> None:
    """A 304 response leaves the cached record unchanged and updates checked_at."""
    old_time = datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC)
    record = IssueRecord(
        number=6013,
        title="Unchanged issue",
        url=f"https://github.com/{REPO}/issues/6013",
        labels=("type/feature",),
        updated_at=old_time,
    )
    remember_issue(REPO, CachedIssue(record=record, etag="etag-123", checked_at=old_time))

    def reply_304(args: list[str]) -> tuple[int, str]:
        assert any("If-None-Match: etag-123" in a for a in args)
        return (0, "HTTP/2 304 Not Modified\r\nETag: etag-123\r\n\r\n")

    runner = RecordedGh({"issues/6013": reply_304})
    store = _store(runner)

    with request_scope(row="refine"):
        found = store.issue(6013)

    assert found is not None
    assert found.title == "Unchanged issue"
    assert len(runner.calls) == 1
    assert _summed_cache(otlp).get(("refine", "miss")) == 1.0

    cached = cached_issue(REPO, 6013)
    assert cached is not None
    assert cached.checked_at != old_time
    assert cached.etag == "etag-123"


def test_one_hour_of_a_quiet_repository_costs_fewer_than_20_requests(
    shared_valkey: ValkeyCacheTier, valkey_server: FakeServer
) -> None:
    """12 rounds of 5 minutes reading 6 issues send only 6 requests in total."""
    issues = [issue_payload(n, title=f"Issue {n}") for n in range(101, 107)]
    runner = RecordedGh({f"issues/{item['number']}": item for item in issues})
    store = _store(runner)

    for _round_num in range(12):
        for n in range(101, 107):
            store.issue(n)

    assert len(runner.calls) == 6


def test_revalidation_updates_modified_issue(
    shared_valkey: ValkeyCacheTier, valkey_server: FakeServer
) -> None:
    """A 200 response during revalidation updates the cached record and store collection."""
    old_time = datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC)
    record = IssueRecord(
        number=6013,
        title="Old issue",
        url=f"https://github.com/{REPO}/issues/6013",
        labels=("type/feature",),
        updated_at=old_time,
    )
    remember_issue(REPO, CachedIssue(record=record, etag="etag-old", checked_at=old_time))

    updated_body = json.dumps(issue_payload(6013, title="Updated issue"))
    response = f'HTTP/2 200 OK\r\nETag: W/"etag-new"\r\n\r\n{updated_body}'
    runner = RecordedGh({"issues/6013": (0, response)})
    store = _store(runner)
    store._all = {}

    found = store.issue(6013)

    assert found is not None
    assert found.title == "Updated issue"
    assert store._all[6013].title == "Updated issue"

    cached = cached_issue(REPO, 6013)
    assert cached is not None
    assert cached.record.title == "Updated issue"
    assert cached.etag == 'W/"etag-new"'
    assert cached.checked_at != old_time


def test_revalidation_returns_none_for_not_found(
    shared_valkey: ValkeyCacheTier, valkey_server: FakeServer
) -> None:
    """A 404 response during revalidation returns None."""
    old_time = datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC)
    record = IssueRecord(
        number=6013,
        title="Deleted issue",
        url=f"https://github.com/{REPO}/issues/6013",
        labels=(),
        updated_at=old_time,
    )
    remember_issue(REPO, CachedIssue(record=record, etag="etag-del", checked_at=old_time))

    runner = RecordedGh({"issues/6013": (1, "HTTP 404: Not Found\r\n")})
    store = _store(runner)

    assert store.issue(6013) is None


def test_revalidation_returns_none_for_pull_request(
    shared_valkey: ValkeyCacheTier, valkey_server: FakeServer
) -> None:
    """A pull request payload during revalidation returns None."""
    old_time = datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC)
    record = IssueRecord(
        number=6013,
        title="Converted issue",
        url=f"https://github.com/{REPO}/issues/6013",
        labels=(),
        updated_at=old_time,
    )
    remember_issue(REPO, CachedIssue(record=record, etag="etag-pr", checked_at=old_time))

    pr_body = json.dumps({**issue_payload(6013), "pull_request": {"url": "https://example.com"}})
    response = f'HTTP/2 200 OK\r\nETag: W/"etag-pr"\r\n\r\n{pr_body}'
    runner = RecordedGh({"issues/6013": (0, response)})
    store = _store(runner)

    assert store.issue(6013) is None


def test_revalidation_raises_error_on_server_failure(
    shared_valkey: ValkeyCacheTier, valkey_server: FakeServer
) -> None:
    """A server error during revalidation raises a GitHubOperationError."""
    old_time = datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC)
    record = IssueRecord(
        number=6013,
        title="Failing issue",
        url=f"https://github.com/{REPO}/issues/6013",
        labels=(),
        updated_at=old_time,
    )
    remember_issue(REPO, CachedIssue(record=record, etag="etag-err", checked_at=old_time))

    runner = RecordedGh({"issues/6013": (1, "HTTP 500: Server Error\r\n")})
    store = _store(runner)

    with pytest.raises(GitHubOperationError, match="Could not revalidate issue #6013"):
        store.issue(6013)


def test_unlabel_issue_updates_cached_entry(
    shared_valkey: ValkeyCacheTier, valkey_server: FakeServer
) -> None:
    """Unlabeling an issue removes the label from both the cache and kept items."""
    now = datetime.now(UTC)
    record = IssueRecord(
        number=6013,
        title="Labeled issue",
        url=f"https://github.com/{REPO}/issues/6013",
        labels=("status/ready", "type/feature"),
        updated_at=now,
    )
    remember_issue(REPO, CachedIssue(record=record, etag=None, checked_at=now))

    runner = RecordedGh({"labels": ""})
    store = _store(runner)
    store._all = {6013: record}

    store.unlabel_issue(6013, "status/ready")

    cached = cached_issue(REPO, 6013)
    assert cached is not None
    assert cached.record.labels == ("type/feature",)
    assert store._all[6013].labels == ("type/feature",)
