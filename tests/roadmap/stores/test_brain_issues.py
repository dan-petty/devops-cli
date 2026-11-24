"""The brain entry of a cached issue in the shared cache tier (#6013).

The shared tier holds each issue that a Service row reads, under the key that `RepoRef.valkey_key`
builds, so rows share the issue and read GitHub only on a miss or after one hour.
"""

from __future__ import annotations

import fnmatch
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from fakeredis import FakeServer, FakeValkey

from devops_cli.github.repo_ref import RepoRef
from devops_cli.roadmap.stores.brain_issues import (
    CachedIssue,
    cached_issue,
    issue_cache,
    remember_issue,
)
from devops_cli.roadmap.stores.store import IssueRecord

if TYPE_CHECKING:
    from devops_cli.valkey.cache import ValkeyCacheTier


def test_a_stored_issue_comes_back(
    shared_valkey: ValkeyCacheTier, valkey_server: FakeServer
) -> None:
    """A stored issue comes back from the fake tier with no GitHub call."""
    repo = "dan-petty/devops-cli"
    now = datetime(2026, 11, 24, 12, 0, tzinfo=UTC)
    record = IssueRecord(
        number=6013,
        title="Cache GitHub issue and PR state in the brain",
        url="https://github.com/dan-petty/devops-cli/issues/6013",
        body="Issue body",
        labels=("type/feature", "priority/p1-high"),
        updated_at=now,
    )
    entry = CachedIssue(record=record, etag="W/'123'", checked_at=now)
    remember_issue(repo, entry)

    retrieved = cached_issue(repo, 6013)
    assert retrieved == entry
    assert retrieved is not None
    assert retrieved.record.title == "Cache GitHub issue and PR state in the brain"
    assert retrieved.record.number == 6013
    assert retrieved.etag == "W/'123'"
    assert retrieved.checked_at == now


def test_a_key_names_its_repository_and_object() -> None:
    """The cached issue key names its repository and number, matching RepoRef.valkey_key."""
    ref = RepoRef("dan-petty/devops-cli")
    cache = issue_cache(ref)
    expected_key = ref.valkey_key("brain-issue", "6013")
    assert cache.shared_key("6013") == expected_key
    assert expected_key == "roadmap:v1:brain-issue:dan-petty/devops-cli:6013"

    p1, p2 = ref.valkey_patterns
    assert fnmatch.fnmatch(expected_key, p1) or fnmatch.fnmatch(expected_key, p2)
    other_ref = RepoRef("dan-petty/other-repo")
    op1, op2 = other_ref.valkey_patterns
    assert not fnmatch.fnmatch(expected_key, op1)
    assert not fnmatch.fnmatch(expected_key, op2)


def test_the_issue_key_has_a_ttl(shared_valkey: ValkeyCacheTier, valkey_server: FakeServer) -> None:
    """An issue entry written to the shared tier has a TTL above 0."""
    repo = "dan-petty/devops-cli"
    cache = issue_cache(repo)
    now = datetime(2026, 11, 24, 12, 0, tzinfo=UTC)
    record = IssueRecord(
        number=6013,
        title="Test issue",
        url="https://github.com/dan-petty/devops-cli/issues/6013",
    )
    entry = CachedIssue(record=record, etag=None, checked_at=now)
    cache["6013"] = entry

    client = FakeValkey(server=valkey_server)
    ttl = client.ttl(cache.shared_key("6013"))
    assert ttl > 0
