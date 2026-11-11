"""The label and state changes that the GitHub roadmap store reads from the issue events since a
time (#1335), and the newest issue that it reads from the issue listing (#4540).
"""

from __future__ import annotations

import itertools
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from devops_cli.config.defaults import DEFAULT_GH_MAX_PAGINATED_PAGES
from devops_cli.exceptions.git import (
    GitHubOperationError,
    GitHubUnreadError,
)
from devops_cli.roadmap.stores.store import (
    ChangeKind,
)
from tests.support.fakes.github import (
    API,
    GitHubApiFake,
    github_json,
    next_page,
)
from tests.support.roadmap_github_store import (
    EVENTS,
    REPO,
    issue_payload,
    over_github,
    recorded_store,
)

# ── Changes ───────────────────────────────────────────────────────────────────


def event_at(template: dict[str, Any], moment: datetime) -> dict[str, Any]:
    return {**template, "created_at": moment.strftime("%Y-%m-%dT%H:%M:%SZ")}


EVENTS_LISTING = f"/repos/{REPO}/issues/events?per_page=100"


def test_changes_since_follows_newest_first_pages_and_stops_at_the_first_older_event(
    github_api: GitHubApiFake,
) -> None:
    """The issue events are read newest first through the session, following GitHub's links,
    and the read stops at the first event older than the cutoff: the third page is never
    requested."""
    referenced = next(event for event in EVENTS if event["event"] == "referenced")
    start = datetime(2026, 10, 3, tzinfo=UTC)
    newer_page = [event_at(referenced, start - timedelta(minutes=n)) for n in range(100)]
    oldest_recorded = datetime.fromisoformat(EVENTS[-1]["created_at"])
    older_padding = [
        event_at(referenced, oldest_recorded - timedelta(minutes=n + 1)) for n in range(90)
    ]
    second, third = f"{EVENTS_LISTING}&page=2", f"{EVENTS_LISTING}&page=3"
    github_api.route("GET", EVENTS_LISTING, github_json(newer_page, headers=next_page(second)))
    github_api.route("GET", second, github_json(EVENTS + older_padding, headers=next_page(third)))
    github_api.route("GET", third, github_json({"message": "page 3 must not be read"}, status=500))
    store, _ = over_github()
    changes = store.changes_since(datetime(2026, 10, 1, 22, 0, tzinfo=UTC))
    assert (
        [url for url in github_api.requested if "issues/events" in url],
        [(change.kind, change.number, change.at.isoformat()) for change in changes],
    ) == (
        [f"GET {API}{EVENTS_LISTING}", f"GET {API}{second}"],
        [
            (ChangeKind.CLOSED, 299, "2026-10-01T22:39:06+00:00"),
            (ChangeKind.LABELED, 917, "2026-10-01T22:39:11+00:00"),
        ],
    )


def test_changes_since_whose_second_event_is_older_than_the_cutoff_sends_one_request(
    github_api: GitHubApiFake,
) -> None:
    """The events' second entry is older than the cutoff, and GitHub links a next page: the
    read stops there, so the events cost one request and the linked page is never asked for."""
    referenced = next(event for event in EVENTS if event["event"] == "referenced")
    cutoff = datetime(2026, 10, 2, tzinfo=UTC)
    page = [
        event_at(referenced, cutoff + timedelta(minutes=5)),
        event_at(referenced, cutoff - timedelta(minutes=5)),
    ]
    second = f"{EVENTS_LISTING}&page=2"
    github_api.route("GET", EVENTS_LISTING, github_json(page, headers=next_page(second)))
    github_api.route("GET", second, github_json({"message": "must not be read"}, status=500))
    store, _ = over_github()
    store.changes_since(cutoff)
    assert [url for url in github_api.requested if "issues/events" in url] == [
        f"GET {API}{EVENTS_LISTING}"
    ]


def test_changes_since_keeps_label_and_state_events_only() -> None:
    """A milestone event is a person's planning and no job reads it, so the poll reports none.
    A field change is a label event of its family (ADR 0003)."""
    closed = next(e for e in EVENTS if e["event"] == "closed" and "pull_request" not in e["issue"])
    reopened = {**closed, "event": "reopened", "created_at": "2026-10-02T01:00:00Z"}
    store, _ = recorded_store({"issues/events": [reopened, *EVENTS]})
    changes = store.changes_since(datetime(2026, 10, 1))
    assert [(change.kind, change.number, change.actor, change.label) for change in changes] == [
        (ChangeKind.UNLABELED, 829, "dan-petty", "scope/github"),
        (ChangeKind.CLOSED, 299, "dan-petty", None),
        (ChangeKind.LABELED, 917, "dan-petty", "type/bug"),
        (ChangeKind.REOPENED, 299, "dan-petty", None),
    ]


def test_changes_since_drops_an_actors_own_changes() -> None:
    """A run's own events are left out, and the others' changes stay (#1361)."""
    closed = next(e for e in EVENTS if e["event"] == "closed" and "pull_request" not in e["issue"])
    own = {**closed, "actor": {"login": "roadmap-bot"}, "created_at": "2026-10-02T01:00:00Z"}
    store, runner = recorded_store({"issues/events": [own]})
    alone = store.changes_since(datetime(2026, 10, 1, tzinfo=UTC), except_actor="roadmap-bot")
    runner.replies["issues/events"] = [own, *EVENTS]
    mixed = store.changes_since(datetime(2026, 10, 1, tzinfo=UTC), except_actor="roadmap-bot")
    assert (alone, {change.actor for change in mixed}, len(mixed)) == ([], {"dan-petty"}, 3)


def test_changes_since_with_an_empty_actor_leaves_out_nothing() -> None:
    """An empty session login names no actor, so no change is left out, not even one GitHub
    reports with an empty login."""
    closed = next(e for e in EVENTS if e["event"] == "closed" and "pull_request" not in e["issue"])
    nameless = {**closed, "actor": {"login": ""}, "created_at": "2026-10-02T01:00:00Z"}
    store, _ = recorded_store({"issues/events": [nameless]})
    changes = store.changes_since(datetime(2026, 10, 1, tzinfo=UTC), except_actor="")
    assert [(change.number, change.actor) for change in changes] == [
        (closed["issue"]["number"], "")
    ]


ISSUE_950_EVENTS = f"/repos/{REPO}/issues/950/events?per_page=100"


def issue_event(event: str, moment: str, **fields: Any) -> dict[str, Any]:
    """An event of an issue's own listing: it has no `issue` key, as GitHub omits it there."""
    return {"event": event, "created_at": moment, "actor": {"login": "dan-petty"}, **fields}


def test_label_changes_keeps_the_label_events_of_an_issue_oldest_first_across_pages(
    github_api: GitHubApiFake,
) -> None:
    """An issue's events are read from its own listing, following GitHub's links. The labeled
    and unlabeled events are kept in the order GitHub lists them, and the others are left out
    (#2919)."""
    second = f"{ISSUE_950_EVENTS}&page=2"
    first_page = [
        issue_event("labeled", "2026-10-02T12:00:00Z", label={"name": "status/ready"}),
        issue_event("commented", "2026-10-02T12:01:00Z"),
        issue_event("unlabeled", "2026-10-02T12:02:00Z", label={"name": "status/new"}),
    ]
    second_page = [
        issue_event("labeled", "2026-10-02T13:00:00Z", label={"name": "owner/agent"}),
    ]
    github_api.route("GET", ISSUE_950_EVENTS, github_json(first_page, headers=next_page(second)))
    github_api.route("GET", second, github_json(second_page))
    store, _ = over_github()
    changes = store.label_changes(950)
    assert (
        [(c.kind, c.number, c.actor, c.label, c.at.isoformat()) for c in changes],
        [url for url in github_api.requested if "/events" in url],
    ) == (
        [
            (ChangeKind.LABELED, 950, "dan-petty", "status/ready", "2026-10-02T12:00:00+00:00"),
            (ChangeKind.UNLABELED, 950, "dan-petty", "status/new", "2026-10-02T12:02:00+00:00"),
            (ChangeKind.LABELED, 950, "dan-petty", "owner/agent", "2026-10-02T13:00:00+00:00"),
        ],
        [f"GET {API}{ISSUE_950_EVENTS}", f"GET {API}{second}"],
    )


def test_label_changes_raises_when_a_later_page_of_the_events_fails(
    github_api: GitHubApiFake,
) -> None:
    """A failed page of an issue's events raises rather than taking the listing as whole (#2919)."""
    second = f"{ISSUE_950_EVENTS}&page=2"
    first_page = [issue_event("labeled", "2026-10-02T12:00:00Z", label={"name": "status/ready"})]
    github_api.route("GET", ISSUE_950_EVENTS, github_json(first_page, headers=next_page(second)))
    github_api.route("GET", second, github_json({"message": "server error"}, status=500))
    store, _ = over_github()
    with pytest.raises(GitHubOperationError) as raised:
        store.label_changes(950)
    assert "issues/950/events" in str(raised.value)


def test_changes_since_raises_when_the_events_outrun_the_page_cap(
    github_api: GitHubApiFake,
) -> None:
    """A chain of linked pages that never reaches back past the cutoff stops at the session's
    page cap, raising rather than taking the listing as whole."""
    referenced = next(event for event in EVENTS if event["event"] == "referenced")
    start = datetime(2026, 10, 3, tzinfo=UTC)
    full_page = [event_at(referenced, start - timedelta(minutes=n)) for n in range(100)]
    cap = DEFAULT_GH_MAX_PAGINATED_PAGES
    pages = [EVENTS_LISTING, *(f"{EVENTS_LISTING}&page={n}" for n in range(2, cap + 2))]
    for page, following in itertools.pairwise(pages):
        github_api.route("GET", page, github_json(full_page, headers=next_page(following)))
    store, _ = over_github()
    with pytest.raises(GitHubUnreadError, match=f"runs past {cap} pages"):
        store.changes_since(datetime(2026, 10, 1, tzinfo=UTC))
    assert len(github_api.sent) == cap


# ── The newest issue (#4540) ──────────────────────────────────────────────────


NEWEST_LISTING = f"/repos/{REPO}/issues?state=all&sort=created&direction=desc&per_page=10"


def _pull(number: int) -> dict[str, Any]:
    return issue_payload(number, pull_request={"url": f"{API}/repos/{REPO}/pulls/{number}"})


@pytest.mark.parametrize(
    ("page", "newest"),
    [
        ([_pull(12), _pull(11), issue_payload(10), _pull(9)], 10),
        ([_pull(number) for number in range(20, 10, -1)], None),
        ([], None),
    ],
    ids=["after-two-pulls", "ten-pulls", "empty"],
)
def test_the_newest_issue_is_read_from_one_page_newest_first_without_its_pulls(
    github_api: GitHubApiFake, page: list[dict[str, Any]], newest: int | None
) -> None:
    """The store reads the newest issue from the first page of the issue listing, newest first,
    and leaves out the pull requests on it. A page of ten pull requests, or an empty one, gives no
    issue, and the linked page is never asked for."""
    second = f"{NEWEST_LISTING}&page=2"
    github_api.route("GET", NEWEST_LISTING, github_json(page, headers=next_page(second)))
    github_api.route("GET", second, github_json({"message": "page 2 must not be read"}, status=500))
    store, _ = over_github()
    assert (store.newest_issue_number(), github_api.requested) == (
        newest,
        [f"GET {API}{NEWEST_LISTING}"],
    )
