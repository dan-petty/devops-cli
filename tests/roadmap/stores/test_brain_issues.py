"""The brain entry of a cached issue in the shared cache tier (#6013, #7292).

The shared tier holds each issue of a public repository that a Service row reads, under a key of
the prefix `valkey:roadmap:v1:issue`, so rows share the issue and read GitHub only on a miss or
after one hour. The entry of a private repository reaches the shared tier only when the process
sends the `sweep` ACL user, and the entry of a repository whose visibility is not known does not
reach it. The counters are read on the OTLP fake.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from fakeredis import FakeServer, FakeValkey

from devops_cli.github.repo_ref import RepoRef
from devops_cli.roadmap.stores.brain_issues import (
    CachedIssue,
    cached_issue,
    remember_issue,
)
from devops_cli.roadmap.stores.store import IssueRecord
from tests.support.fakes.otlp import FakeCollector

if TYPE_CHECKING:
    from devops_cli.valkey.cache import ValkeyCacheTier

REPO = "dan-petty/devops-cli"
PRIVATE_REPO = "acme/private-repo"
NOW = datetime(2026, 11, 24, 12, 0, tzinfo=UTC)


def _entry(repo: str, number: int = 6013) -> CachedIssue:
    """The entry of issue `number` of `repo`, last checked at `NOW`."""
    record = IssueRecord(
        number=number,
        title="Cache GitHub issue and PR state in the brain",
        url=f"https://github.com/{repo}/issues/{number}",
        body="Issue body",
        labels=("type/feature", "priority/p1-high"),
        updated_at=NOW,
    )
    return CachedIssue(record=record, etag="W/'123'", checked_at=NOW)


def _keys(server: FakeServer) -> list[str]:
    return sorted(FakeValkey(server=server, decode_responses=True).keys("*"))


def _summed(otlp: FakeCollector, name: str) -> dict[tuple[str, str], float]:
    counted: dict[tuple[str, str], float] = {}
    for attributes, value in otlp.points(name):
        point = (attributes["store"], attributes["result"])
        counted[point] = counted.get(point, 0) + value
    return counted


def _reads(otlp: FakeCollector) -> dict[tuple[str, str], float]:
    from devops_cli.telemetry.instruments import BRAIN_READS_TOTAL

    return _summed(otlp, BRAIN_READS_TOTAL.name)


def _writes(otlp: FakeCollector) -> dict[tuple[str, str], float]:
    from devops_cli.telemetry.instruments import BRAIN_WRITES_TOTAL

    return _summed(otlp, BRAIN_WRITES_TOTAL.name)


def test_a_stored_issue_comes_back(
    shared_valkey: ValkeyCacheTier, valkey_server: FakeServer
) -> None:
    """A stored issue of a public repository comes back from the fake tier with no GitHub call."""
    entry = _entry(REPO)
    remember_issue(REPO, entry, private=False)

    assert cached_issue(REPO, 6013, private=False) == entry


def test_a_key_names_its_repository_and_number() -> None:
    """The key of a cached issue starts with the roadmap prefix of the shared tier, which the
    `sweep` user writes and the `brain` user reads, and holds the casefolded name of the
    repository and the number. The `:` after the name ends the repository part, so the keys of a
    repository are not keys of a repository whose name starts with the same text."""
    from devops_cli.roadmap.stores.brain_issues import issue_key

    key = issue_key(RepoRef("Dan-Petty/DevOps-CLI"), 6013)
    longer_name = issue_key("dan-petty/devops-cli-2", 6013)
    keys_of_the_repository = key.removesuffix("6013")

    assert (key, longer_name, longer_name.startswith(keys_of_the_repository)) == (
        "valkey:roadmap:v1:issue:dan-petty/devops-cli:6013",
        "valkey:roadmap:v1:issue:dan-petty/devops-cli-2:6013",
        False,
    )


def test_the_issue_key_has_a_ttl(shared_valkey: ValkeyCacheTier, valkey_server: FakeServer) -> None:
    """An issue entry written to the shared tier has a TTL above 0."""
    from devops_cli.roadmap.stores.brain_issues import issue_key

    remember_issue(REPO, _entry(REPO), private=False)

    client = FakeValkey(server=valkey_server)
    assert client.ttl(issue_key(REPO, 6013)) > 0


def test_an_entry_of_a_private_repository_reaches_the_shared_tier_only_under_the_sweep_user(
    shared_valkey: ValkeyCacheTier,
    valkey_server: FakeServer,
    otlp: FakeCollector,
    config: Callable[..., Path],
) -> None:
    """A write and a read of an entry of a private repository send no command while the process
    sends no ACL user, and each counts `private`. Under the `sweep` user the entry reaches the
    shared tier and comes back."""
    from devops_cli.roadmap.stores.visibility import SWEEP_USER

    entry = _entry(PRIVATE_REPO)
    remember_issue(PRIVATE_REPO, entry, private=True)
    with_no_user = (cached_issue(PRIVATE_REPO, 6013, private=True), _keys(valkey_server))

    config(valkey={"username": SWEEP_USER})
    remember_issue(PRIVATE_REPO, entry, private=True)
    under_sweep = (cached_issue(PRIVATE_REPO, 6013, private=True), _keys(valkey_server))

    assert (with_no_user, under_sweep, _reads(otlp), _writes(otlp)) == (
        (None, []),
        (entry, ["valkey:roadmap:v1:issue:acme/private-repo:6013"]),
        {("issue", "private"): 1.0, ("issue", "shared"): 1.0},
        {("issue", "private"): 1.0, ("issue", "shared"): 1.0},
    )


def test_a_caller_with_no_answer_and_no_read_uses_the_answer_that_the_process_holds(
    shared_valkey: ValkeyCacheTier, valkey_server: FakeServer, otlp: FakeCollector
) -> None:
    """A caller that gives no answer and no read of the visibility, such as a delivery that does
    not carry it, writes and reads nothing while the process holds no answer, and counts
    `unknown`. After a public answer of the visibility check, the same caller writes and reads the
    entry."""
    from devops_cli.roadmap.stores.visibility import visibility_of

    entry = _entry(REPO)
    remember_issue(REPO, entry)
    with_no_answer = (cached_issue(REPO, 6013), _keys(valkey_server))

    visibility_of(REPO, lambda: False)
    remember_issue(REPO, entry)
    with_a_public_answer = (cached_issue(REPO, 6013), _keys(valkey_server))

    assert (with_no_answer, with_a_public_answer, _reads(otlp), _writes(otlp)) == (
        (None, []),
        (entry, ["valkey:roadmap:v1:issue:dan-petty/devops-cli:6013"]),
        {("issue", "unknown"): 1.0, ("issue", "shared"): 1.0},
        {("issue", "unknown"): 1.0, ("issue", "shared"): 1.0},
    )


def test_no_visibility_read_while_the_shared_tier_does_not_answer(
    shared_valkey: ValkeyCacheTier, valkey_server: FakeServer, otlp: FakeCollector
) -> None:
    """While Valkey does not answer, a read and a write of an entry send no read of the
    visibility to GitHub: the read counts `fallback` and the write counts `skipped`."""
    visibility_reads: list[Any] = []

    def is_private() -> bool:
        visibility_reads.append(REPO)
        return False

    valkey_server.connected = False
    found = cached_issue(REPO, 6013, is_private=is_private)
    remember_issue(REPO, _entry(REPO), is_private=is_private)

    assert (found, visibility_reads, _reads(otlp), _writes(otlp)) == (
        None,
        [],
        {("issue", "fallback"): 1.0},
        {("issue", "skipped"): 1.0},
    )
