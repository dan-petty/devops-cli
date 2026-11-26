"""The GitHub roadmap store takes an answer as the issue that it asked for only when the answer
names that issue (#7331).

A read of an issue by its number can answer with another issue: GitHub redirects the read of an
issue that was transferred to another repository, and the answer then holds the number and the
repository of the issue at its new place. The store compares the number and the repository of the
answer with the request. An answer that names another issue is no issue of the repository: a read
gives what a missing issue gives, a write is refused before any request, and the listing of the
store, the snapshot of the listing and the brain hold no record of that number.

GitHub is `RecordedGh` for one answer of a given shape, and `GitHubFake` for a repository that an
issue leaves.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest

from devops_cli.exceptions.git import GitHubOperationError
from devops_cli.roadmap.stores.brain_issues import CachedIssue, cached_issue, remember_issue
from devops_cli.roadmap.stores.github_store import GitHubRoadmapStore
from devops_cli.roadmap.stores.listing_snapshot import FileSnapshotStore, IncrementalListing
from devops_cli.roadmap.stores.store import CloseReason, IssueRecord, Item, ItemField
from tests.support.fakes.github import RunnerSession
from tests.support.fakes.github_repository import GitHubFake
from tests.support.roadmap_github_store import RecordedGh

if TYPE_CHECKING:
    from devops_cli.valkey.cache import ValkeyCacheTier

REPO = "acme/widgets"
OTHER = "acme/other"
ISSUE = f"repos/{REPO}/issues/7"
"""The request of issue #7 of the repository."""
TWELVE = f"repos/{REPO}/issues/12"
"""The request of issue #12 of the repository."""
PUBLIC = {"isPrivate": {"data": {"repository": {"isPrivate": False}}}}
ITEM_LABELS = ("priority/p2-medium", "status/ready")
STORE_LOG = "devops_cli.roadmap.stores.github_store"


def _answer(number: int, repo: str = REPO, *, without: tuple[str, ...] = (), **changes: Any) -> Any:
    """Issue `number` of `repo` as the REST API gives it, with no field of `without`."""
    payload = {
        "id": 1000 + number,
        "number": number,
        "title": f"Issue {number} of {repo}",
        "html_url": f"https://github.com/{repo}/issues/{number}",
        "url": f"https://api.github.com/repos/{repo}/issues/{number}",
        "repository_url": f"https://api.github.com/repos/{repo}",
        "body": f"The text of issue {number} of {repo}.",
        "state": "open",
        "labels": [{"name": label} for label in ITEM_LABELS],
        **changes,
    }
    return {name: value for name, value in payload.items() if name not in without}


def _store(replies: dict[str, Any]) -> tuple[GitHubRoadmapStore, RecordedGh]:
    runner = RecordedGh(replies)
    return GitHubRoadmapStore(REPO, runner=runner, session=RunnerSession(runner)), runner


def _item(store: GitHubRoadmapStore) -> Item:
    found = store.item(7)
    assert found is not None
    return found


ANOTHER_ISSUE = [
    pytest.param(_answer(12, OTHER), id="another-number-and-another-repository"),
    pytest.param(_answer(12), id="another-number"),
    pytest.param(_answer(7, OTHER), id="another-repository"),
    pytest.param(
        _answer(7, OTHER, without=("repository_url",)), id="another-repository-in-the-issue-url"
    ),
    pytest.param(
        _answer(7, OTHER, without=("repository_url", "url")),
        id="another-repository-in-the-page-url",
    ),
]

THE_ISSUE = [
    pytest.param(_answer(7), id="the-rest-answer"),
    pytest.param(_answer(7, "Acme/Widgets"), id="the-name-in-another-case"),
    pytest.param(_answer(7, without=("repository_url",)), id="no-repository-url"),
    pytest.param(_answer(7, without=("repository_url", "url")), id="the-page-url-only"),
    pytest.param(
        _answer(7, without=("repository_url", "url"), html_url="https://example.com/issues/7"),
        id="no-repository-in-any-field",
    ),
]


# ── Reads ─────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("answer", ANOTHER_ISSUE)
def test_an_answer_that_names_another_issue_reads_as_no_issue(answer: Any) -> None:
    store, _ = _store({ISSUE: answer})

    assert (store.issue(7), store.item(7), store.item(7, fresh=True)) == (None, None, None)


@pytest.mark.parametrize("answer", THE_ISSUE)
def test_an_answer_that_names_the_requested_issue_reads_as_before(answer: Any) -> None:
    store, _ = _store({ISSUE: answer})

    issue, item = store.issue(7), store.item(7)

    assert issue is not None
    assert item is not None
    assert (
        (issue.number, issue.title, issue.url, issue.labels),
        (item.number, item.status),
        store.read_issue_body(7),
        store.pull_title(7),
    ) == (
        (7, answer["title"], answer["html_url"], ITEM_LABELS),
        (7, "Ready"),
        answer["body"],
        None,
    )


def test_the_body_read_refuses_an_answer_that_names_another_issue() -> None:
    store, _ = _store({ISSUE: _answer(12, OTHER)})

    with pytest.raises(GitHubOperationError) as refused:
        store.read_issue_body(7)

    assert (str(refused.value), refused.value.error_code, refused.value.details) == (
        f"#7 is not an issue of {REPO}.",
        "GITHUB_OPERATION_FAILED",
        {"operation": "roadmap.issue.read_body", "repo": REPO, "number": 7},
    )


def test_the_title_read_of_a_pull_request_takes_no_answer_that_names_another_one() -> None:
    pull = {"pull_request": {"url": f"https://api.github.com/repos/{OTHER}/pulls/12"}}
    own = {"pull_request": {"url": f"https://api.github.com/repos/{REPO}/pulls/7"}}
    moved, _ = _store({ISSUE: _answer(12, OTHER, **pull)})
    kept, _ = _store({ISSUE: _answer(7, **own)})

    assert (moved.pull_title(7), kept.pull_title(7)) == (None, f"Issue 7 of {REPO}")


def test_the_refusal_logs_a_warning_that_names_the_requested_number_only(
    caplog: pytest.LogCaptureFixture,
) -> None:
    store, _ = _store({ISSUE: _answer(12, OTHER)})

    with caplog.at_level(logging.WARNING, logger=STORE_LOG):
        store.issue(7)

    logged = [(log.levelname, log.getMessage()) for log in caplog.records if log.name == STORE_LOG]
    assert logged == [
        (
            "WARNING",
            f"GitHub answered the request of issue #7 of {REPO} with another issue, so #7 is no "
            "issue of the repository.",
        )
    ]


# ── Writes ────────────────────────────────────────────────────────────────────

WRITES: list[Any] = [
    pytest.param(
        lambda store, item: store.set_field(item, ItemField.STATUS, "Planned"), id="set_field"
    ),
    pytest.param(
        lambda store, item: store.set_fields(item, {ItemField.STATUS: "Planned"}), id="set_fields"
    ),
    pytest.param(
        lambda store, item: store.set_marks(item, {"alternatives.verdict": "none"}), id="set_marks"
    ),
    pytest.param(lambda store, item: store.write_issue_body(7, "New text."), id="write_issue_body"),
    pytest.param(lambda store, item: store.set_title(7, "A new title"), id="set_title"),
    pytest.param(lambda store, item: store.close(7, CloseReason.COMPLETED), id="close"),
    pytest.param(lambda store, item: store.add_sub_issue(7, 12), id="add_sub_issue"),
    pytest.param(lambda store, item: store.add_blocked_by(7, 12), id="add_blocked_by"),
]


@pytest.mark.parametrize("write", WRITES)
def test_a_write_sends_no_request_when_the_read_answers_with_another_issue(
    write: Callable[[GitHubRoadmapStore, Item], None],
) -> None:
    """The store read the item when #7 was an issue of the repository, which also holds an
    issue #12. Each write reads the issue of the item first."""
    store, runner = _store({ISSUE: _answer(7), TWELVE: _answer(12)})
    item = _item(store)
    runner.replies[ISSUE] = _answer(12, OTHER)

    with pytest.raises(GitHubOperationError) as refused:
        write(store, item)

    assert (str(refused.value), runner.writes) == (f"#7 is not an issue of {REPO}.", [])


def test_a_write_whose_answer_names_another_issue_is_refused_and_not_kept(
    shared_valkey: ValkeyCacheTier,
) -> None:
    """The answer of the `PATCH` of an issue is the issue too. An answer that names another issue
    fails the write, and the brain keeps no entry of it."""
    store, _ = _store({**PUBLIC, "-X PATCH": _answer(12, OTHER), ISSUE: _answer(7)})

    with pytest.raises(GitHubOperationError) as refused:
        store.set_title(7, "A new title")

    assert (
        str(refused.value),
        cached_issue(REPO, 12, private=False),
        cached_issue(REPO, 7, private=False),
    ) == (f"#7 is not an issue of {REPO}.", None, None)


# ── The brain ─────────────────────────────────────────────────────────────────


def _entry(number: int, repo: str = REPO, *, at: datetime, etag: str | None = None) -> CachedIssue:
    record = IssueRecord(
        number=number,
        title=f"Issue {number} of {repo}",
        url=f"https://github.com/{repo}/issues/{number}",
        updated_at=at,
    )
    return CachedIssue(record=record, etag=etag, checked_at=at)


def test_a_conditional_read_that_answers_with_another_issue_gives_no_issue_and_drops_the_entry(
    shared_valkey: ValkeyCacheTier,
) -> None:
    """The entry of #7 is older than one hour, so the store sends a conditional read. GitHub
    answers 200 with another issue."""
    remember_issue(
        REPO, _entry(7, at=datetime(2026, 1, 1, tzinfo=UTC), etag="etag-7"), private=False
    )
    answer = f'HTTP/2 200 OK\r\nETag: W/"etag-12"\r\n\r\n{json.dumps(_answer(12, OTHER))}'
    store, runner = _store({**PUBLIC, ISSUE: (0, answer)})

    found = store.issue(7)

    sent = [args for args, _ in runner.calls if ISSUE in args]
    assert (
        found,
        sent,
        cached_issue(REPO, 7, private=False),
        cached_issue(REPO, 12, private=False),
    ) == (None, [["api", ISSUE, "--include", "-H", "If-None-Match: etag-7"]], None, None)


def test_a_304_answer_gives_the_entry_of_the_requested_issue(
    shared_valkey: ValkeyCacheTier,
) -> None:
    held = _entry(7, at=datetime(2026, 1, 1, tzinfo=UTC), etag="etag-7")
    remember_issue(REPO, held, private=False)
    store, _ = _store({**PUBLIC, ISSUE: (0, "HTTP/2 304 Not Modified\r\nETag: etag-7\r\n\r\n")})

    assert store.issue(7) == held.record


def test_an_entry_that_names_another_issue_is_not_used_and_is_removed(
    shared_valkey: ValkeyCacheTier,
) -> None:
    """An entry is the issue only when its record names the requested number and the repository
    of the store. For any other entry, the store reads the issue from GitHub."""
    remember_issue(REPO, _entry(12, OTHER, at=datetime.now(UTC)), private=False)
    store, runner = _store({**PUBLIC, TWELVE: _answer(12)})

    found = store.issue(12)
    kept = cached_issue(REPO, 12, private=False)

    assert found is not None
    assert kept is not None
    assert (
        found.title,
        kept.record.url,
        [args for args, _ in runner.calls if TWELVE in args],
    ) == (f"Issue 12 of {REPO}", f"https://github.com/{REPO}/issues/12", [["api", TWELVE]])


# ── The listing ───────────────────────────────────────────────────────────────


def _round(github: GitHubFake, listing: IncrementalListing) -> GitHubRoadmapStore:
    """The store of one round of a lane, which reads every issue through `listing`."""
    return GitHubRoadmapStore(REPO, runner=github, session=RunnerSession(github), listing=listing)


def _numbers(store: GitHubRoadmapStore) -> list[int]:
    """The numbers of the items that the store lists, in order of number."""
    return sorted(item.number for item in store.items())


def _repository() -> GitHubFake:
    github = GitHubFake(REPO)
    github.seed_issue(7, labels=ITEM_LABELS, body="Text of 7")
    github.seed_issue(8, labels=ITEM_LABELS, body="Text of 8")
    return github


def test_a_round_drops_the_record_of_an_issue_whose_read_answers_with_another_issue(
    tmp_path: Path,
) -> None:
    """The snapshot of the lane holds #7 as an open item. The issue leaves the repository, which
    the read of the changes does not show. The first read of #7 by its number takes the record
    out of the listing of the round, and no later round of the lane lists it."""
    github = _repository()
    snapshots = FileSnapshotStore(tmp_path)
    listing = IncrementalListing(snapshots)
    listed_first = _numbers(_round(github, listing))
    github.move_issue(7, to=OTHER, as_number=12)

    second = _round(github, listing)
    listed_before = _numbers(second)
    read = second.item(7)
    listed_after = _numbers(second)
    listed_later = _numbers(_round(github, listing))

    kept = snapshots.load(REPO)
    assert kept is not None
    assert (listed_first, listed_before, read, listed_after, listed_later) == (
        [7, 8],
        [7, 8],
        None,
        [8],
        [8],
    )
    assert [issue.number for issue in kept.issues] == [8]


def test_a_dropped_record_stays_out_when_another_copy_of_the_snapshot_holds_it(
    tmp_path: Path,
) -> None:
    """Another lane writes its copy of the snapshot, which still holds #7, over the shared one.
    The lane that read #7 by its number keeps the record out until GitHub lists the number
    again."""
    github = _repository()
    snapshots = FileSnapshotStore(tmp_path)
    listing = IncrementalListing(snapshots)
    _numbers(_round(github, listing))
    with_seven = snapshots.load(REPO)
    assert with_seven is not None
    github.move_issue(7, to=OTHER, as_number=12)
    discovering = _round(github, listing)
    _numbers(discovering)
    discovering.item(7)

    snapshots.save(with_seven)
    listed_from_the_other_copy = _numbers(_round(github, listing))
    github.seed_issue(
        7, labels=ITEM_LABELS, body="Text of 7", updated_at=datetime.now(UTC).replace(microsecond=0)
    )
    listed_after_github_lists_it = _numbers(_round(github, listing))

    assert (listed_from_the_other_copy, listed_after_github_lists_it) == ([8], [7, 8])


def test_a_missing_issue_that_the_listing_holds_leaves_the_listing(tmp_path: Path) -> None:
    """GitHub answers 404 for a number that the snapshot holds and that is no issue of the
    repository now. The record leaves the listing as the record of a redirected read does."""
    github = _repository()
    listing = IncrementalListing(FileSnapshotStore(tmp_path))
    _numbers(_round(github, listing))
    del github.issues[7]

    second = _round(github, listing)
    listed_before = _numbers(second)
    read = second.issue(7)

    assert (listed_before, read, _numbers(second), _numbers(_round(github, listing))) == (
        [7, 8],
        None,
        [8],
        [8],
    )
