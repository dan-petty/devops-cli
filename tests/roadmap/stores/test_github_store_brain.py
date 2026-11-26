"""The project-brain cache of GitHub issues in the store (#6013, #7292).

Rows read the cached issue first from the shared tier, revalidating after one hour with
`If-None-Match`, and store writes update the entry. The store reads the visibility of its
repository once in each lifetime of the answer, after the shared tier answered. The shared tier
holds the issues of a public repository, and of a private one only under the `sweep` ACL user.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest
from fakeredis import FakeServer, FakeValkey

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
from devops_cli.telemetry.instruments import (
    BRAIN_CACHE_TOTAL,
    BRAIN_READS_TOTAL,
    BRAIN_WRITES_TOTAL,
)
from tests.support.fakes.otlp import FakeCollector
from tests.support.roadmap_github_store import REPO, RecordedGh, issue_payload

if TYPE_CHECKING:
    from devops_cli.valkey.cache import ValkeyCacheTier


PRIVATE_REPO = "acme/private-repo"
PUBLIC = {"isPrivate": {"data": {"repository": {"isPrivate": False}}}}
PRIVATE = {"isPrivate": {"data": {"repository": {"isPrivate": True}}}}


def _store(runner: RecordedGh, repo: str = REPO) -> GitHubRoadmapStore:
    return GitHubRoadmapStore(repo, runner=runner, session=get_github_session())


def _github(replies: dict[str, Any]) -> RecordedGh:
    """GitHub with a public repository: it answers the visibility read and `replies`."""
    return RecordedGh({**PUBLIC, **replies})


def _issue_of(repo: str, number: int, title: str) -> Any:
    """Issue `number` of `repo` as GitHub gives it: each URL of the answer names the repository
    of the store that reads it."""
    return issue_payload(
        number,
        title=title,
        url=f"https://api.github.com/repos/{repo}/issues/{number}",
        html_url=f"https://github.com/{repo}/issues/{number}",
    )


def _requests(runner: RecordedGh) -> list[str]:
    """Each request that GitHub got, in order: a read of the visibility or a request of an
    issue."""
    return ["visibility" if "isPrivate" in " ".join(args) else "issue" for args, _ in runner.calls]


def _seed(entry: CachedIssue) -> None:
    """Write `entry` of the public repository to the shared tier, as another process did."""
    remember_issue(REPO, entry, private=False)


def _held(number: int) -> CachedIssue | None:
    """The entry of issue `number` of the public repository that the shared tier holds."""
    return cached_issue(REPO, number, private=False)


def _keys(server: FakeServer) -> list[str]:
    return sorted(FakeValkey(server=server, decode_responses=True).keys("*"))


def _summed(otlp: FakeCollector, name: str) -> dict[tuple[str, str], float]:
    counted: dict[tuple[str, str], float] = {}
    for attributes, value in otlp.points(name):
        point = (attributes["store"], attributes["result"])
        counted[point] = counted.get(point, 0) + value
    return counted


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
    _seed(CachedIssue(record=record, etag="W/'1'", checked_at=now))

    runner = _github({})
    store = _store(runner)
    with request_scope(row="refine"):
        found = store.issue(6013)

    assert found == record
    assert _requests(runner) == ["visibility"]
    assert _summed_cache(otlp).get(("refine", "hit")) == 1.0


def test_a_miss_reads_github_once_and_fills_the_entry(
    shared_valkey: ValkeyCacheTier, valkey_server: FakeServer, otlp: FakeCollector
) -> None:
    """A missing issue reads GitHub once, writes the tier, and counts a miss."""
    payload = issue_payload(6013, title="Fetched issue")
    runner = _github({"issues/6013": payload})
    store = _store(runner)

    with request_scope(row="stage"):
        found = store.issue(6013)

    assert found is not None
    assert found.title == "Fetched issue"
    assert _requests(runner) == ["visibility", "issue"]
    assert _summed_cache(otlp).get(("stage", "miss")) == 1.0

    cached = _held(6013)
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
    _seed(CachedIssue(record=record, etag=None, checked_at=now))

    runner = _github({"labels": ""})
    store = _store(runner)
    store.label_issue(6013, "status/ready")

    cached = _held(6013)
    assert cached is not None
    assert "status/ready" in cached.record.labels
    assert "type/feature" in cached.record.labels


def test_the_tier_refuses_a_connection(
    shared_valkey: ValkeyCacheTier, valkey_server: FakeServer
) -> None:
    """When Valkey is down, the read falls back to GitHub with no error, and the store sends no
    read of the visibility."""
    payload = issue_payload(6013, title="Fallback issue")
    runner = _github({"issues/6013": payload})
    store = _store(runner)

    valkey_server.connected = False
    with request_scope(row="implement"):
        found = store.issue(6013)

    assert found is not None
    assert found.title == "Fallback issue"
    assert _requests(runner) == ["issue"]


def test_a_second_read_in_the_same_hour_sends_no_request(
    shared_valkey: ValkeyCacheTier, valkey_server: FakeServer
) -> None:
    """Two reads within the hour send only one GitHub request."""
    payload = issue_payload(6013, title="Hour read")
    runner = _github({"issues/6013": payload})
    store = _store(runner)

    first = store.issue(6013)
    second = store.issue(6013)

    assert first == second
    assert _requests(runner) == ["visibility", "issue"]


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
    _seed(CachedIssue(record=record, etag="etag-123", checked_at=old_time))

    def reply_304(args: list[str]) -> tuple[int, str]:
        assert any("If-None-Match: etag-123" in a for a in args)
        return (0, "HTTP/2 304 Not Modified\r\nETag: etag-123\r\n\r\n")

    runner = _github({"issues/6013": reply_304})
    store = _store(runner)

    with request_scope(row="refine"):
        found = store.issue(6013)

    assert found is not None
    assert found.title == "Unchanged issue"
    assert _requests(runner) == ["visibility", "issue"]
    assert _summed_cache(otlp).get(("refine", "miss")) == 1.0

    cached = _held(6013)
    assert cached is not None
    assert cached.checked_at != old_time
    assert cached.etag == "etag-123"


def test_one_hour_of_a_quiet_repository_costs_fewer_than_20_requests(
    shared_valkey: ValkeyCacheTier, valkey_server: FakeServer
) -> None:
    """12 rounds of 5 minutes reading 6 issues send only 6 requests in total."""
    issues = [issue_payload(n, title=f"Issue {n}") for n in range(101, 107)]
    runner = _github({f"issues/{item['number']}": item for item in issues})
    store = _store(runner)

    for _round_num in range(12):
        for n in range(101, 107):
            store.issue(n)

    assert _requests(runner) == ["visibility", *["issue"] * 6]


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
    _seed(CachedIssue(record=record, etag="etag-old", checked_at=old_time))

    updated_body = json.dumps(issue_payload(6013, title="Updated issue"))
    response = f'HTTP/2 200 OK\r\nETag: W/"etag-new"\r\n\r\n{updated_body}'
    runner = _github({"issues/6013": (0, response)})
    store = _store(runner)
    store._all = {}

    found = store.issue(6013)

    assert found is not None
    assert found.title == "Updated issue"
    assert store._all[6013].title == "Updated issue"

    cached = _held(6013)
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
    _seed(CachedIssue(record=record, etag="etag-del", checked_at=old_time))

    runner = _github({"issues/6013": (1, "HTTP 404: Not Found\r\n")})
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
    _seed(CachedIssue(record=record, etag="etag-pr", checked_at=old_time))

    pr_body = json.dumps({**issue_payload(6013), "pull_request": {"url": "https://example.com"}})
    response = f'HTTP/2 200 OK\r\nETag: W/"etag-pr"\r\n\r\n{pr_body}'
    runner = _github({"issues/6013": (0, response)})
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
    _seed(CachedIssue(record=record, etag="etag-err", checked_at=old_time))

    runner = _github({"issues/6013": (1, "HTTP 500: Server Error\r\n")})
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
    _seed(CachedIssue(record=record, etag=None, checked_at=now))

    runner = _github({"labels": ""})
    store = _store(runner)
    store._all = {6013: record}

    store.unlabel_issue(6013, "status/ready")

    cached = _held(6013)
    assert cached is not None
    assert cached.record.labels == ("type/feature",)
    assert store._all[6013].labels == ("type/feature",)


def test_fresh_issue_read_revalidates_cached_entry_with_etag(
    shared_valkey: ValkeyCacheTier, valkey_server: FakeServer, otlp: FakeCollector
) -> None:
    """`fresh=True` bypasses the 1-hour cache hit window and revalidates stored ETags (#7063)."""
    now = datetime.now(UTC)
    record = IssueRecord(
        number=6013,
        title="Stale title",
        url=f"https://github.com/{REPO}/issues/6013",
        labels=("priority/p1-high", "status/in-progress"),
        updated_at=now,
    )
    _seed(CachedIssue(record=record, etag="etag-old", checked_at=now))

    live_body = json.dumps(
        issue_payload(
            6013,
            title="Live title",
            labels=[{"name": "priority/p1-high"}, {"name": "status/in-review"}],
        )
    )
    response = f'HTTP/2 200 OK\r\nETag: W/"etag-live"\r\n\r\n{live_body}'

    def reply_live(args: list[str]) -> tuple[int, str]:
        assert any("If-None-Match: etag-old" in a for a in args)
        return (0, response)

    runner = _github({"issues/6013": reply_live})
    store = _store(runner)
    store._all = {6013: record}

    with request_scope(row="implement"):
        found = store.issue(6013, fresh=True)

    assert found is not None
    assert found.title == "Live title"
    assert found.labels == ("priority/p1-high", "status/in-review")
    assert _requests(runner) == ["visibility", "issue"]
    assert _summed_cache(otlp).get(("implement", "miss")) == 1.0
    assert store._all[6013].title == "Live title"

    cached = _held(6013)
    assert cached is not None
    assert cached.record.title == "Live title"
    assert cached.etag == 'W/"etag-live"'


def test_fresh_item_read_bypasses_fresh_cache_without_etag(
    shared_valkey: ValkeyCacheTier, valkey_server: FakeServer
) -> None:
    """`item(n, fresh=True)` reads live GitHub even when a webhook wrote an entry with no ETag (#7063)."""
    now = datetime.now(UTC)
    stale = IssueRecord(
        number=6013,
        title="Queued item",
        url=f"https://github.com/{REPO}/issues/6013",
        labels=("priority/p1-high", "status/in-progress", "owner/service"),
        updated_at=now,
    )
    _seed(CachedIssue(record=stale, etag=None, checked_at=now))

    payload = issue_payload(
        6013,
        title="Queued item",
        labels=[{"name": "priority/p1-high"}, {"name": "status/in-review"}],
    )
    runner = _github({"issues/6013": payload})
    store = _store(runner)
    store._all = {6013: stale}

    item = store.item(6013, fresh=True)

    assert item is not None
    assert item.status == "In Review"
    assert _requests(runner) == ["visibility", "issue"]
    assert store._all[6013].labels == ("priority/p1-high", "status/in-review")

    cached = _held(6013)
    assert cached is not None
    assert cached.record.labels == ("priority/p1-high", "status/in-review")


def _reads(otlp: FakeCollector) -> dict[tuple[str, str], float]:
    return _summed(otlp, BRAIN_READS_TOTAL.name)


def _writes(otlp: FakeCollector) -> dict[tuple[str, str], float]:
    return _summed(otlp, BRAIN_WRITES_TOTAL.name)


def _new_process() -> None:
    """Drop the visibility answers of the process, as a new process starts."""
    from devops_cli.roadmap.stores.visibility import reset_visibility

    reset_visibility()


def test_a_private_repository_reads_github_each_time_and_writes_no_key(
    shared_valkey: ValkeyCacheTier, valkey_server: FakeServer, otlp: FakeCollector
) -> None:
    """Each read of an issue of a private repository answers from GitHub, and the shared tier
    gets no key, while the process sends no ACL user. The private answer is kept, so GitHub gets
    one read of the visibility, and each read and each write counts `private` (#7292)."""
    runner = RecordedGh({**PRIVATE, "issues/6013": _issue_of(PRIVATE_REPO, 6013, "Private issue")})
    store = _store(runner, PRIVATE_REPO)

    titles = [found.title for found in (store.issue(6013), store.issue(6013)) if found is not None]

    assert (titles, _requests(runner), _keys(valkey_server), _reads(otlp), _writes(otlp)) == (
        ["Private issue", "Private issue"],
        ["visibility", "issue", "issue"],
        [],
        {("issue", "private"): 2.0},
        {("issue", "private"): 2.0},
    )


def test_an_issue_that_the_service_opens_in_a_private_repository_writes_no_key(
    shared_valkey: ValkeyCacheTier, valkey_server: FakeServer, otlp: FakeCollector
) -> None:
    """A write of the Service comes with no read of the entry before it. The store reads the
    visibility after its write to GitHub, and the issue that it opened in a private repository
    leaves the shared tier with no key, while the process sends no ACL user."""
    opened_issue = issue_payload(7, title="Opened issue")
    runner = RecordedGh({**PRIVATE, f"repos/{PRIVATE_REPO}/issues": opened_issue})

    opened = _store(runner, PRIVATE_REPO).create_issue("Opened issue", "Text")

    assert (opened.title, _requests(runner), _keys(valkey_server), _writes(otlp)) == (
        "Opened issue",
        ["issue", "visibility"],
        [],
        {("issue", "private"): 1.0},
    )


def test_a_private_repository_is_shared_under_the_sweep_user(
    shared_valkey: ValkeyCacheTier, valkey_server: FakeServer, config: Callable[..., Path]
) -> None:
    """While the process sends the `sweep` ACL user, the issue of a private repository reaches
    the shared tier, and the second read sends no request."""
    from devops_cli.roadmap.stores.visibility import SWEEP_USER

    config(valkey={"username": SWEEP_USER})
    runner = RecordedGh({**PRIVATE, "issues/6013": _issue_of(PRIVATE_REPO, 6013, "Private issue")})
    store = _store(runner, PRIVATE_REPO)

    first = store.issue(6013)
    second = store.issue(6013)

    assert (first == second, _requests(runner), _keys(valkey_server)) == (
        True,
        ["visibility", "issue"],
        ["valkey:roadmap:v1:issue:acme/private-repo:6013"],
    )


def test_a_public_repository_keeps_the_shared_read_and_write(
    shared_valkey: ValkeyCacheTier, valkey_server: FakeServer, otlp: FakeCollector
) -> None:
    """A read of an issue of a public repository fills the shared tier under the roadmap prefix,
    and a new process reads the entry with no request of the issue. Each process reads the
    visibility one time."""
    runner = _github({"issues/6013": issue_payload(6013, title="Public issue")})

    first = _store(runner).issue(6013)
    _new_process()
    second = _store(runner).issue(6013)

    assert (first == second, _requests(runner), _keys(valkey_server)) == (
        True,
        ["visibility", "issue", "visibility"],
        [f"valkey:roadmap:v1:issue:{REPO}:6013"],
    )
    assert (_reads(otlp), _writes(otlp)) == (
        {("issue", "source"): 1.0, ("issue", "shared"): 1.0},
        {("issue", "shared"): 1.0},
    )


def test_a_failed_visibility_read_reads_github_and_writes_no_key(
    shared_valkey: ValkeyCacheTier, valkey_server: FakeServer, otlp: FakeCollector
) -> None:
    """A failed read of the visibility gives an unknown answer: each read of an issue answers
    from GitHub, the shared tier gets no key, and each read and each write counts `unknown`. The
    unknown answer is kept, so GitHub gets one read of the visibility."""
    runner = RecordedGh(
        {
            "isPrivate": (1, "API rate limit exceeded"),
            "issues/6013": _issue_of(PRIVATE_REPO, 6013, "Issue of an unknown repository"),
        }
    )
    store = _store(runner, PRIVATE_REPO)

    titles = [found.title for found in (store.issue(6013), store.issue(6013)) if found is not None]

    assert (titles, _requests(runner), _keys(valkey_server), _reads(otlp), _writes(otlp)) == (
        ["Issue of an unknown repository", "Issue of an unknown repository"],
        ["visibility", "issue", "issue"],
        [],
        {("issue", "unknown"): 2.0},
        {("issue", "unknown"): 2.0},
    )
