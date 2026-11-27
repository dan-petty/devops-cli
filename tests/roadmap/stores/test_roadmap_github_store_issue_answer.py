"""The GitHub roadmap store takes an answer as the issue that it asked for only when the answer
names that issue (#7331).

A read of an issue by its number can answer with another issue: GitHub redirects the read of an
issue that was transferred to another repository, and the answer then holds the number and the
repository of the issue at its new place. The store compares the number and the repository of the
answer with the request. An answer that names another issue is no issue of the repository: a read
gives what a missing issue gives, a write is refused before any request, and the listing of the
store, the snapshot of the listing and the brain hold no record of that number.

A read can also say that the number left with no issue payload (#7337): GitHub answers 301 for a
transferred issue when `gh` does not follow the redirect, and 410 for a deleted one. A listing
below the number of an issue that left answers 404. The store reads the issue then, and a number
that is no issue of the repository raises the error of no issue and leaves the listing.

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

from devops_cli.config.constants import CONST_ROADMAP_REFINE_COMMENT_MARKER
from devops_cli.exceptions.git import GitHubNotFoundError, GitHubOperationError
from devops_cli.roadmap.stores.brain_issues import CachedIssue, cached_issue, remember_issue
from devops_cli.roadmap.stores.github_store import GitHubRoadmapStore
from devops_cli.roadmap.stores.listing_snapshot import FileSnapshotStore, IncrementalListing
from devops_cli.roadmap.stores.store import (
    CloseReason,
    Evidence,
    EvidenceKind,
    IssueRecord,
    Item,
    ItemField,
)
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
BELOW = f"{ISSUE}/"
"""Each request below the number of issue #7: its comments, its events and its blockers."""
NOT_FOUND = (1, "gh: Not Found (HTTP 404)")
GONE = (1, "gh: This issue was deleted (HTTP 410)")
REPOSITORY = f"repos/{REPO}"
"""The request of the repository, which gives the name that GitHub gives it now."""
RENAMED = "acme/gadgets"
NAME_LOG = "devops_cli.github.issue_answer"
NO_ISSUE = ("GitHubNotAnIssueError", "GITHUB_NOT_AN_ISSUE", f"#7 is not an issue of {REPO}.")
"""The class, the code and the message of the error of a number that is no issue."""


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
    """A store of `REPO` over the recorded `replies`. The repository answers with its own name,
    unless `replies` give another answer. That reply is the last one, because its key is a part
    of each other request of the repository."""
    runner = RecordedGh({**replies, REPOSITORY: replies.get(REPOSITORY, {"full_name": REPO})})
    return GitHubRoadmapStore(REPO, runner=runner, session=RunnerSession(runner)), runner


def _item(store: GitHubRoadmapStore) -> Item:
    found = store.item(7)
    assert found is not None
    return found


def _raised(error: GitHubOperationError) -> tuple[str, str, str]:
    """The class, the code and the message of `error`."""
    return type(error).__name__, error.error_code, str(error)


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

    assert (_raised(refused.value), refused.value.details) == (
        NO_ISSUE,
        {"operation": "roadmap.issue.read_body", "repo": REPO, "number": 7},
    )


def test_the_title_read_of_a_pull_request_takes_no_answer_that_names_another_one() -> None:
    pull = {"pull_request": {"url": f"https://api.github.com/repos/{OTHER}/pulls/12"}}
    own = {"pull_request": {"url": f"https://api.github.com/repos/{REPO}/pulls/7"}}
    moved, _ = _store({ISSUE: _answer(12, OTHER, **pull)})
    kept, _ = _store({ISSUE: _answer(7, **own)})

    assert (moved.pull_title(7), kept.pull_title(7)) == (None, f"Issue 7 of {REPO}")


def _logged(caplog: pytest.LogCaptureFixture) -> list[tuple[str, str]]:
    """The level and the text of each line that the store logged."""
    return [(log.levelname, log.getMessage()) for log in caplog.records if log.name == STORE_LOG]


def test_the_refusal_logs_one_line_with_the_place_that_the_answer_names(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The store reads the number three times. It logs the number one time, with the repository
    and the number of the answer and no other field of it."""
    store, _ = _store({ISSUE: _answer(12, OTHER, title="A title that is no part of a log line")})

    with caplog.at_level(logging.WARNING, logger=STORE_LOG):
        store.issue(7)
        store.item(7, fresh=True)
        store.pull_title(7)

    assert _logged(caplog) == [
        (
            "WARNING",
            f"#7 is no issue of {REPO} now: GitHub answers with {OTHER}#12. The store leaves "
            "it out.",
        )
    ]


# ── A read that says only that the number left ────────────────────────────────

LEFT = [
    pytest.param("gh: HTTP 301", id="redirect-not-followed"),
    pytest.param("gh: This issue was deleted (HTTP 410)", id="deleted"),
    pytest.param("gh: Not Found (HTTP 404)", id="missing"),
]


@pytest.mark.parametrize("said", LEFT)
def test_a_plain_read_that_says_that_the_number_left_reads_as_no_issue(said: str) -> None:
    store, runner = _store({ISSUE: (1, said)})

    with pytest.raises(GitHubOperationError) as refused:
        store.read_issue_body(7)

    assert (store.issue(7), store.item(7), store.pull_title(7), _raised(refused.value)) == (
        None,
        None,
        None,
        NO_ISSUE,
    )
    assert {tuple(args) for args, _ in runner.calls} == {("api", ISSUE)}


@pytest.mark.parametrize("said", LEFT)
def test_a_conditional_read_that_says_that_the_number_left_gives_no_issue_and_drops_the_entry(
    shared_valkey: ValkeyCacheTier, said: str
) -> None:
    """The entry of #7 is older than one hour, so the store sends a conditional read."""
    remember_issue(
        REPO, _entry(7, at=datetime(2026, 1, 1, tzinfo=UTC), etag="etag-7"), private=False
    )
    store, runner = _store({**PUBLIC, ISSUE: (1, said)})

    found = store.issue(7)

    sent = [args for args, _ in runner.calls if ISSUE in args]
    assert (found, sent, cached_issue(REPO, 7, private=False)) == (
        None,
        [["api", ISSUE, "--include", "-H", "If-None-Match: etag-7"]],
        None,
    )


def test_a_conditional_read_whose_headers_hold_the_status_301_gives_no_issue(
    shared_valkey: ValkeyCacheTier,
) -> None:
    """`gh api --include` can also end with exit status 0 and the status line of the redirect."""
    remember_issue(
        REPO, _entry(7, at=datetime(2026, 1, 1, tzinfo=UTC), etag="etag-7"), private=False
    )
    answer = "HTTP/2 301 Moved Permanently\r\nLocation: https://example.com/\r\n\r\n"
    store, _ = _store({**PUBLIC, ISSUE: (0, answer)})

    assert (store.issue(7), cached_issue(REPO, 7, private=False)) == (None, None)


def test_a_redirect_of_a_route_that_is_no_issue_number_stays_an_error() -> None:
    """Only a read of one issue by its number takes 301 as no issue. The listing of the issues
    and the read of a commit raise for it."""
    store, _ = _store({"/issues?": (1, "gh: HTTP 301"), "/commits/": (1, "gh: HTTP 301")})

    with pytest.raises(GitHubOperationError) as listing:
        store.items()
    with pytest.raises(GitHubOperationError) as commit:
        store.evidence_holds(Evidence(kind=EvidenceKind.REGRESSION_COMMIT, value="0" * 40))

    assert ("HTTP 301" in str(listing.value), "HTTP 301" in str(commit.value)) == (True, True)


@pytest.mark.parametrize("said", LEFT)
def test_a_store_that_read_no_listing_logs_a_number_that_left_one_time(
    said: str, caplog: pytest.LogCaptureFixture
) -> None:
    """A Job reads one number and no listing. The store cannot tell whether a lane lists the
    number, so it logs the number that it leaves out."""
    store, _ = _store({ISSUE: (1, said)})

    with caplog.at_level(logging.WARNING, logger=STORE_LOG):
        store.issue(7)
        store.item(7, fresh=True)

    assert _logged(caplog) == [
        ("WARNING", f"#7 is no issue of {REPO} now. The store leaves it out.")
    ]


def test_a_store_that_read_its_listing_logs_a_number_that_was_an_issue_and_no_other(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """The listing of a Job is new, so it does not hold #9, which was transferred. The status
    301 says that #9 was an issue, and the store logs it. The status 404 of #99 says nothing of
    the kind: no lane lists that number, and the store logs none."""
    github = _repository()
    github.seed_issue(9, labels=ITEM_LABELS, body="Text of 9")
    github.move_issue(9, to=OTHER, as_number=12, followed=False)
    store = _round(github, IncrementalListing(FileSnapshotStore(tmp_path)))
    listed = _numbers(store)

    with caplog.at_level(logging.WARNING, logger=STORE_LOG):
        read = (store.issue(99), store.issue(9), store.issue(9))

    assert (listed, read, _logged(caplog)) == (
        [7, 8],
        (None, None, None),
        [("WARNING", f"#9 is no issue of {REPO} now. The store leaves it out.")],
    )


# ── A renamed repository ──────────────────────────────────────────────────────


def _name_reads(runner: RecordedGh) -> list[list[str]]:
    """Each read of the repository itself that the store sent."""
    return [args for args, _ in runner.calls if args == ["api", REPOSITORY]]


def test_an_answer_under_the_old_name_of_a_renamed_repository_is_the_requested_issue(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """GitHub redirects each route of a renamed repository, so each issue answer holds the
    requested number and the new name. The store reads the name of its repository one time for
    many such answers, takes them, and says one time that its name is old."""
    store, runner = _store(
        {
            ISSUE: _answer(7, RENAMED),
            TWELVE: _answer(12, RENAMED),
            REPOSITORY: {"full_name": RENAMED},
        }
    )

    with caplog.at_level(logging.WARNING):
        seven, twelve, again = store.issue(7), store.issue(12), store.item(7, fresh=True)
        body = store.read_issue_body(7)

    assert seven is not None
    assert twelve is not None
    assert again is not None
    assert (seven.number, twelve.number, again.number, body, _name_reads(runner)) == (
        7,
        12,
        7,
        f"The text of issue 7 of {RENAMED}.",
        [["api", REPOSITORY]],
    )
    assert [log.getMessage() for log in caplog.records if log.name in (NAME_LOG, STORE_LOG)] == [
        f"GitHub names the repository {REPO} as {RENAMED} now. The configured name is old: give "
        "the new name."
    ]


NOT_THIS_REPOSITORY: list[Any] = [
    pytest.param({"full_name": REPO}, id="the-repository-keeps-its-name"),
    pytest.param({"full_name": RENAMED}, id="the-repository-has-a-third-name"),
    pytest.param(NOT_FOUND, id="no-repository"),
    pytest.param((1, "gh: HTTP 301"), id="redirect-not-followed"),
]


@pytest.mark.parametrize("repository", NOT_THIS_REPOSITORY)
def test_a_transferred_issue_that_kept_its_number_is_refused(repository: Any) -> None:
    """The answer holds the requested number and the name of another repository. GitHub does not
    give the repository of the store that name, so the answer is the issue at another place. The
    store reads the name one time for many answers."""
    store, runner = _store(
        {ISSUE: _answer(7, OTHER), TWELVE: _answer(12, OTHER), REPOSITORY: repository}
    )

    read = (store.issue(7), store.issue(12), store.item(7, fresh=True))

    assert (read, _name_reads(runner)) == ((None, None, None), [["api", REPOSITORY]])


def test_a_renamed_repository_drops_no_record(tmp_path: Path) -> None:
    """The rename of a repository must not read as "each item left": a round after the rename
    reads each item again and keeps each record of its listing."""
    github = _repository()
    listing = IncrementalListing(FileSnapshotStore(tmp_path))
    _numbers(_round(github, listing))
    github.rename_repository(RENAMED)

    second = _round(github, listing)
    read = [second.item(7, fresh=True), second.item(8, fresh=True)]

    assert [None if item is None else item.number for item in read] == [7, 8]
    assert (_numbers(second), _numbers(_round(github, listing))) == ([7, 8], [7, 8])


# ── The listings below a number ───────────────────────────────────────────────

LISTINGS: list[Any] = [
    pytest.param(lambda store: store.comments_on(7), id="comments_on"),
    pytest.param(lambda store: store.label_changes(7), id="label_changes"),
    pytest.param(lambda store: store.blocked_by(7), id="blocked_by"),
]
NO_ISSUE_ANSWERS: list[Any] = [
    pytest.param(_answer(12, OTHER), id="another-issue"),
    pytest.param((1, "gh: HTTP 301"), id="redirect-not-followed"),
    pytest.param(NOT_FOUND, id="missing"),
]


@pytest.mark.parametrize("read", LISTINGS)
@pytest.mark.parametrize("answer", NO_ISSUE_ANSWERS)
def test_a_404_below_the_number_of_no_issue_raises_the_error_of_no_issue(
    read: Callable[[GitHubRoadmapStore], Any], answer: Any
) -> None:
    """A 404 of a listing below a number does not say why. The store reads the issue, and the
    answer says that the number is no issue of the repository."""
    store, _ = _store({BELOW: NOT_FOUND, ISSUE: answer})

    with pytest.raises(GitHubOperationError) as refused:
        read(store)

    assert _raised(refused.value) == NO_ISSUE


@pytest.mark.parametrize("read", LISTINGS)
def test_a_404_below_the_number_of_an_issue_of_the_repository_stays_the_error_of_the_listing(
    read: Callable[[GitHubRoadmapStore], Any],
) -> None:
    store, _ = _store({BELOW: NOT_FOUND, ISSUE: _answer(7)})

    with pytest.raises(GitHubNotFoundError) as missing:
        read(store)

    assert (type(missing.value).__name__, missing.value.error_code) == (
        "GitHubNotFoundError",
        "GITHUB_NOT_FOUND",
    )


NO_LISTING: list[Any] = [
    pytest.param(GONE, id="deleted"),
    pytest.param((1, "gh: HTTP 301"), id="redirect-not-followed"),
]


@pytest.mark.parametrize("read", LISTINGS)
@pytest.mark.parametrize("below", NO_LISTING)
def test_a_410_or_a_301_below_the_number_of_no_issue_raises_the_error_of_no_issue(
    read: Callable[[GitHubRoadmapStore], Any], below: Any
) -> None:
    """GitHub answers 410 for the comments, the events and the blockers of a deleted issue, and a
    redirect that is not followed ends with 301. The store reads the issue for each of them."""
    store, _ = _store({BELOW: below, ISSUE: GONE})

    with pytest.raises(GitHubOperationError) as refused:
        read(store)

    assert _raised(refused.value) == NO_ISSUE


def test_a_410_below_the_number_of_an_issue_of_the_repository_stays_the_error_of_the_listing() -> (
    None
):
    store, _ = _store({BELOW: GONE, ISSUE: _answer(7)})

    with pytest.raises(GitHubOperationError) as refused:
        store.comments_on(7)

    assert (type(refused.value).__name__, refused.value.details.get("status")) == (
        "GitHubOperationError",
        410,
    )


def test_a_job_comment_on_no_issue_is_refused_before_the_write() -> None:
    """The store reads the comments of the number before it posts a comment with a job marker."""
    store, runner = _store({BELOW: NOT_FOUND, ISSUE: _answer(12, OTHER)})

    with pytest.raises(GitHubOperationError) as refused:
        store.comment(7, f"{CONST_ROADMAP_REFINE_COMMENT_MARKER}\n\nA comment of a job.")

    assert (_raised(refused.value), runner.writes) == (NO_ISSUE, [])


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


@pytest.mark.parametrize("read", LISTINGS[:2])
def test_a_404_below_the_number_of_an_issue_that_left_drops_its_record(
    read: Callable[[GitHubRoadmapStore], Any], tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """The first read of a round for #7 is a listing below its number, which answers 404. The
    record leaves the listing of the round, no later round of the lane lists it, and the store
    logs the number one time with its new place."""
    github = _repository()
    listing = IncrementalListing(FileSnapshotStore(tmp_path))
    _numbers(_round(github, listing))
    github.move_issue(7, to=OTHER, as_number=12)

    second = _round(github, listing)
    listed_before = _numbers(second)
    with caplog.at_level(logging.WARNING, logger=STORE_LOG):
        with pytest.raises(GitHubOperationError) as refused:
            read(second)
        with pytest.raises(GitHubOperationError) as again:
            read(second)

    assert (
        listed_before,
        _raised(refused.value),
        _raised(again.value),
        _numbers(second),
        _numbers(_round(github, listing)),
        _logged(caplog),
    ) == (
        [7, 8],
        NO_ISSUE,
        NO_ISSUE,
        [8],
        [8],
        [
            (
                "WARNING",
                f"#7 is no issue of {REPO} now: GitHub answers with {OTHER}#12. The store "
                "leaves it out.",
            )
        ],
    )


def test_a_redirect_that_gh_does_not_follow_drops_the_record_and_logs_it(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    github = _repository()
    listing = IncrementalListing(FileSnapshotStore(tmp_path))
    _numbers(_round(github, listing))
    github.move_issue(7, to=OTHER, as_number=12, followed=False)

    second = _round(github, listing)
    listed_before = _numbers(second)
    with caplog.at_level(logging.WARNING, logger=STORE_LOG):
        read = second.item(7, fresh=True)

    assert (listed_before, read, _numbers(second), _numbers(_round(github, listing))) == (
        [7, 8],
        None,
        [8],
        [8],
    )
    assert _logged(caplog) == [
        ("WARNING", f"#7 is no issue of {REPO} now. The store leaves it out.")
    ]


def test_a_410_of_the_comments_of_a_deleted_issue_drops_its_record(tmp_path: Path) -> None:
    """A person deleted #7, and the lane got no delivery for it. The comments of #7 answer 410,
    and so does the issue. The record leaves the listing at the read of the comments, so no later
    round of the lane lists it."""
    github = _repository()
    listing = IncrementalListing(FileSnapshotStore(tmp_path))
    _numbers(_round(github, listing))
    github.delete_issue(7)

    second = _round(github, listing)
    listed_before = _numbers(second)
    with pytest.raises(GitHubOperationError) as refused:
        second.comments_on(7)

    assert (
        listed_before,
        _raised(refused.value),
        _numbers(second),
        _numbers(_round(github, listing)),
    ) == ([7, 8], NO_ISSUE, [8], [8])
