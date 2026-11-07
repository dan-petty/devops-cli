"""How the GitHub roadmap store pages a REST listing through the session of the process, and which
cache it skips (#1335).
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any, NoReturn
from urllib.parse import parse_qs, urlsplit

import httpx2
import pytest

from devops_cli.exceptions.git import (
    GitHubUnreadError,
)
from devops_cli.roadmap.stores.github_store import (
    GitHubRoadmapStore,
)
from devops_cli.roadmap.stores.store import (
    ItemField,
    get_roadmap_store,
)
from tests.support.fakes.github import (
    API,
    JSON_TYPE,
    GitHubApiFake,
    github_json,
    next_page,
)
from tests.support.roadmap_github_store import (
    EVENTS,
    ISSUES_IN_MILESTONE,
    LISTING_MILESTONES,
    MILESTONES,
    OPEN_ISSUES,
    REPO,
    issue_payload,
    labeled,
    over_github,
    read,
    recorded,
    recorded_store,
)

# ── Paging and caching ────────────────────────────────────────────────────────


def test_every_rest_listing_is_read_through_the_session_a_full_page_at_a_time() -> None:
    """Each REST listing is read through the GitHub session at a full page, which follows
    GitHub's links itself; none goes through gh (#983)."""
    store, runner = recorded_store(
        {
            "milestones?state=all": MILESTONES,
            "issues?milestone=43": ISSUES_IN_MILESTONE,
            "issues?milestone=none": [],
            "issues?state=": OPEN_ISSUES,
        }
    )
    store.milestones()
    store.items(milestone=43)
    store.items()
    store.backlog()
    store.candidates()
    listings = [args for args, _ in runner.calls if args[0].startswith(API)]
    gh_listings = [args for args, _ in runner.calls if args[:2] == ["api", f"repos/{REPO}"]]
    assert (
        [len(args) for args in listings],
        [_query(args, "per_page", "page") for args in listings],
        gh_listings,
    ) == ([1] * 4, [(["100"], [])] * 4, [])


def _query(args: list[str], *names: str) -> tuple[list[str], ...]:
    """The values of `names` in the query of the URL or endpoint a REST read names last."""
    query = parse_qs(urlsplit(args[-1]).query)
    return tuple(query.get(name, []) for name in names)


LISTINGS: list[tuple[str, Any, Callable[[GitHubRoadmapStore], object]]] = [
    (f"/{LISTING_MILESTONES}", MILESTONES[0], lambda store: store.milestones()),
    (f"/repos/{REPO}/issues?state=all&per_page=100", OPEN_ISSUES[1], lambda store: store.issues()),
    (
        f"/repos/{REPO}/issues/844/comments?per_page=100",
        recorded("issue-844-comments.json")[0],
        lambda store: store.comments_on(844),
    ),
]


_HTML = httpx2.Response(
    200, headers={"content-type": "text/html; charset=utf-8"}, content=b"<html>upstream</html>"
)


@pytest.mark.parametrize("bad", [1, 2], ids=["first-page", "later-page"])
@pytest.mark.parametrize(
    "answer",
    [
        _HTML,
        httpx2.Response(200, headers={"content-type": JSON_TYPE}),
        github_json({"message": "x"}),
    ],
    ids=["html", "empty", "object"],
)
@pytest.mark.parametrize(
    ("path", "full", "read_listing"),
    LISTINGS,
    ids=["milestones", "issues", "comments"],
)
def test_a_listing_page_that_is_not_a_json_list_raises_naming_it(
    github_api: GitHubApiFake,
    path: str,
    full: Any,
    read_listing: Callable[[GitHubRoadmapStore], object],
    answer: httpx2.Response,
    bad: int,
) -> None:
    """The reviewers' replay: a page answered with a body that is not a JSON list, such as a
    proxy's HTML, read as the end of the listing, so a bad first page gave an empty listing and
    a bad later page a short one. The session raises, naming the listing and the page, before
    any write, and requests no page after it."""
    later = f"{path}&page=2"
    github_api.route(
        "GET", path, answer if bad == 1 else github_json([full] * 100, headers=next_page(later))
    )
    github_api.route("GET", later, answer)
    store, runner = over_github()
    with pytest.raises(GitHubUnreadError) as raised:
        read_listing(store)
    assert (
        (raised.value.details["path"], raised.value.details["page"]),
        len(github_api.sent),
        runner.writes,
    ) == ((path, bad), bad, [])


def test_a_listing_reads_on_while_github_links_a_next_page(github_api: GitHubApiFake) -> None:
    """The session follows each page's `rel="next"`: two linked pages of a hundred issues are
    two requests and two hundred issues, and the second page, which links none, ends the read."""
    first = f"/repos/{REPO}/issues?state=all&per_page=100"
    second = f"{first}&page=2"
    issues = [issue_payload(number) for number in range(1, 201)]
    github_api.route("GET", first, github_json(issues[:100], headers=next_page(second)))
    github_api.route("GET", second, github_json(issues[100:]))
    store, _ = over_github()
    assert (len(store.issues()), len(github_api.sent)) == (200, 2)


def test_every_read_and_write_passes_use_cache_false() -> None:
    issue = labeled(ISSUES_IN_MILESTONE[2], "priority/p1-high")
    store, runner = recorded_store(
        {
            "milestones?state=all": MILESTONES,
            "issues?milestone=43": ISSUES_IN_MILESTONE,
            "-X PATCH": issue,
            "issues/737": issue,
            "issues?state=all": OPEN_ISSUES,
            "issues/events": EVENTS,
        }
    )
    store.items(milestone=43)
    item = read(store, 737)
    store.candidates()
    store.changes_since(datetime(2026, 10, 1, tzinfo=UTC))
    store.set_field(item, ItemField.STATUS, "Ready")
    assert ([kwargs["use_cache"] for _, kwargs in runner.calls], len(runner.calls)) == (
        [False] * 6,
        6,
    )


# ── The factory ───────────────────────────────────────────────────────────────


def test_the_factory_opens_the_github_adapter_without_reading() -> None:
    store = get_roadmap_store(REPO)
    assert type(store) is GitHubRoadmapStore


def test_a_store_the_factory_opens_reads_its_listings_through_the_processs_session(
    github_api: GitHubApiFake,
) -> None:
    """Every roadmap command opens the store through the factory, which passes no session: its
    REST listings go through the process's GitHub session, and none through the gh runner
    (#983)."""
    github_api.route("GET", f"/{LISTING_MILESTONES}", github_json(MILESTONES))

    def refuse(args: list[str], **_: Any) -> NoReturn:
        raise AssertionError(f"the listing went through gh: {args}")

    store = get_roadmap_store(REPO, runner=refuse)
    titles = [milestone.title for milestone in store.milestones()]
    assert (titles[0], github_api.requested) == (
        "2026-10-29",
        [f"GET {API}/{LISTING_MILESTONES}"],
    )
