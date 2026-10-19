"""The contract of the GitHub session's fake: it answers the session as GitHub does (#983, ADR 0007).

Each case runs twice through the real GitHub session: once over `GitHubApiFake`, routed as a test
over the fake routes it, and once over GitHub's own answers to the same requests, recorded on
2026-10-19 in `tests/fixtures/github_api/recorded_answers.json` and replayed in order by
`RecordedGitHubApi` through `httpx2.MockTransport`, offline. Both runs must give the same answers,
errors, requests and ledger, which each case writes out; where they differ, the fake is wrong.
The recording is only what the replay serves. The requests read `octocat/Hello-World`, GitHub's
own example repository, search issues with no query, render Markdown, which changes nothing, and
read `/user` with the pinned fake token.

Covered: a REST read, and its conditional read after a read GitHub answers 404; a listing over
the pages GitHub links, stopped early, and read again from its first page's ETag; a write
answered with text; and the typed errors for a 404, a refused token, a 422 and a refused write.
Not recorded: a rate limit, since provoking one spends a quota to zero; a 5xx and a refused
connect, which GitHub cannot be made to send; a redirect, for want of a moved repository that
names no person; and a 403 for a missing scope, which the session reads from the token's
`x-oauth-scopes`, a header the recordings remove. The session's handling of those is tested over
the fake in `tests/test_github_session.py` and `tests/test_github_errors.py`, and so is the page
cap, which is the session's own rule rather than GitHub's. The session sends no GraphQL, since
every GraphQL call stays on gh, so the fake answers none.
"""

from __future__ import annotations

import json
import re
import time
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from typing import Any

import httpx2
import pytest

from devops_cli.config.constants import (
    CONST_GITHUB_NOT_FOUND_ERROR_CODE,
    CONST_GITHUB_UNAUTHENTICATED_ERROR_CODE,
)
from devops_cli.exceptions.git import (
    GitHubNotFoundError,
    GitHubOperationError,
    GitHubUnauthenticatedError,
)
from devops_cli.github.pages import get_pages_status
from devops_cli.github.rate_limiter import get_github_rate_limiter
from devops_cli.github.session import get_github_session
from tests.support.fakes.github import (
    API,
    GitHubApiDouble,
    GitHubApiFake,
    RecordedGitHubApi,
    github_json,
    github_text,
    next_page,
    quota_headers,
    serve_github_api,
)
from tests.support.paths import FIXTURES

_RECORDED_ANSWERS = FIXTURES / "github_api" / "recorded_answers.json"

_LABEL = "/repos/octocat/Hello-World/labels/bug"
_MISSING_LABEL = "/repos/octocat/Hello-World/labels/no-such-label"
_BRANCHES = "/repos/octocat/Hello-World/branches?per_page=2"
# GitHub links a listing's next page by the repository's id, not its name.
_BRANCHES_PAGE_2 = f"{API}/repositories/1296269/branches?per_page=2&page=2"
_SEARCH = "/search/issues?q="
_MARKDOWN = "/markdown"

_LABEL_ETAG = 'W/"fbc60fb507394e61bfe123db07644f0bfbc07094f3ec0d8b24da284a62f537ac"'
_BRANCHES_ETAG = 'W/"90b66b5693398898eabfa6ef90b1acd5f40193f72ecd06601ae17ffb19d547ce"'
_LAST_BRANCHES_ETAG = 'W/"fd6f1ea358a3e8e4aa77a5e8d275b7bea994aa766e35dc2de778c9a10c551ae3"'

_BUG_LABEL = {
    "id": 600797884,
    "node_id": "MDU6TGFiZWw2MDA3OTc4ODQ=",
    "url": "https://api.github.com/repos/octocat/Hello-World/labels/bug",
    "name": "bug",
    "color": "c5def5",
    "default": True,
    "description": None,
    "archived_at": None,
    "archived_by": None,
}


def _branch(name: str, sha: str) -> dict[str, Any]:
    """A branch as GitHub lists it."""
    url = f"https://api.github.com/repos/octocat/Hello-World/commits/{sha}"
    return {"name": name, "commit": {"sha": sha, "url": url}, "protected": False}


_FIRST_BRANCHES = [
    _branch("master", "7fd1a60b01f91b314f59955a4e4d4e80d8edf11d"),
    _branch("octocat-patch-1", "b1b3f9723831141a31a1a7252a213e216ea76e56"),
]
_LAST_BRANCHES = [_branch("test", "b3cbd5bbd7e81436d2eee04537ea2b4c0cad4cdf")]
_RENDERED = "<p>Hello <strong>world</strong></p>\n"


def _recording(name: str) -> list[dict[str, Any]]:
    """The exchanges recorded under `name`, in the order GitHub answered them."""
    recordings = json.loads(_RECORDED_ANSWERS.read_text(encoding="utf-8"))["recordings"]
    exchanges: list[dict[str, Any]] = recordings[name]
    return exchanges


@dataclass(frozen=True)
class Case:
    """GitHub's recorded answers to a case's requests, and how a test over the fake routes them."""

    recording: str
    exchanges: slice
    route: Callable[[GitHubApiFake], None]

    def recorded(self) -> list[dict[str, Any]]:
        return _recording(self.recording)[self.exchanges]


def _route_label(fake: GitHubApiFake) -> None:
    fake.route(
        "GET", _LABEL, github_json(_BUG_LABEL, headers={**quota_headers(4993), "etag": _LABEL_ETAG})
    )


def _leave_the_label_unrouted(fake: GitHubApiFake) -> None:
    """A test reads a missing label by routing nothing; the fake holds the quota as it stood
    before the read, which its own 404 spends one of."""
    fake.quota["core"] = quota_headers(4993)


def _route_first_branches_page(fake: GitHubApiFake) -> None:
    headers = {**quota_headers(4904), "etag": _BRANCHES_ETAG, **next_page(_BRANCHES_PAGE_2)}
    fake.route("GET", _BRANCHES, github_json(_FIRST_BRANCHES, headers=headers))


def _route_branches(fake: GitHubApiFake) -> None:
    _route_first_branches_page(fake)
    fake.route(
        "GET",
        _BRANCHES_PAGE_2,
        *(
            github_json(
                _LAST_BRANCHES, headers={**quota_headers(left), "etag": _LAST_BRANCHES_ETAG}
            )
            for left in (4903, 4902)
        ),
    )


def _route_user(fake: GitHubApiFake) -> None:
    refusal = {
        "message": "Bad credentials",
        "documentation_url": "https://docs.github.com/rest",
        "status": "401",
    }
    fake.route("GET", "/user", github_json(refusal, status=401))


def _route_search(fake: GitHubApiFake) -> None:
    refusal = {
        "message": "Validation Failed",
        "errors": [{"resource": "Search", "field": "q", "code": "missing"}],
        "documentation_url": "https://docs.github.com/v3/search",
        "status": "422",
    }
    quota = quota_headers(29, resource="search", limit=30)
    fake.route("GET", _SEARCH, github_json(refusal, status=422, headers=quota))


def _route_rendered_markdown(fake: GitHubApiFake) -> None:
    answer = github_text(_RENDERED, media_type="text/html", headers=quota_headers(4991))
    fake.route("POST", _MARKDOWN, answer)


def _route_refused_markdown(fake: GitHubApiFake) -> None:
    refusal = {
        "message": "Invalid rendering mode",
        "documentation_url": "https://docs.github.com/v3/markdown/",
        "status": "400",
    }
    fake.route("POST", _MARKDOWN, github_json(refusal, status=400, headers=quota_headers(4990)))


_A_READ = Case("label_read_twice_around_a_missing_label", slice(0, 1), _route_label)
_A_READ_AROUND_A_404 = Case("label_read_twice_around_a_missing_label", slice(0, 3), _route_label)
_A_READ_OF_NOTHING = Case(
    "label_read_twice_around_a_missing_label", slice(1, 2), _leave_the_label_unrouted
)
_THE_FIRST_PAGE = Case("branches_listed_twice", slice(0, 1), _route_first_branches_page)
_A_LISTING = Case("branches_listed_twice", slice(0, 2), _route_branches)
_A_LISTING_READ_TWICE = Case("branches_listed_twice", slice(0, 4), _route_branches)
_A_REFUSED_TOKEN = Case("user_with_a_refused_token", slice(0, 1), _route_user)
_A_SEARCH_WITHOUT_A_QUERY = Case("search_without_a_query", slice(0, 1), _route_search)
_A_WRITE = Case("markdown_rendered", slice(0, 1), _route_rendered_markdown)
_A_REFUSED_WRITE = Case("markdown_in_an_unknown_mode", slice(0, 1), _route_refused_markdown)


@pytest.fixture(params=["fake", "recorded"])
def github(
    request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch, public_dns: str
) -> Iterator[Callable[[Case], GitHubApiDouble]]:
    """Serve a case's GitHub to the process's session: the fake as the case routes it, or
    GitHub's recorded answers. A recorded answer the session never asked for fails the test."""
    served: list[RecordedGitHubApi] = []

    def serve(case: Case) -> GitHubApiDouble:
        if request.param == "recorded":
            replay = RecordedGitHubApi(case.recorded())
            served.append(replay)
            serve_github_api(monkeypatch, replay)
            return replay
        fake = GitHubApiFake()
        case.route(fake)
        serve_github_api(monkeypatch, fake)
        return fake

    yield serve
    assert [replay.unanswered for replay in served] in ([], [[]])


def _url(path: str) -> str:
    return str(httpx2.URL(API).join(path))


def _conditions(api: GitHubApiDouble) -> list[str | None]:
    """The `If-None-Match` each request was sent with, in order."""
    return [request.headers.get("if-none-match") for request in api.sent]


def _remaining(resource: str = "core") -> int | None:
    """What the ledger holds as the resource's remaining quota."""
    remaining: int | None = get_github_rate_limiter().get_quota(resource).remaining
    return remaining


def _raised(error: GitHubOperationError) -> tuple[type[GitHubOperationError], dict[str, Any]]:
    return type(error), error.to_dict()


def test_a_read_answers_the_json_github_sent_and_charges_the_quota_it_reported(
    github: Callable[[Case], GitHubApiDouble],
) -> None:
    """A REST read gives back GitHub's JSON, sends one GET to its URL and leaves the ledger at
    the quota GitHub reported."""
    api = github(_A_READ)
    label = get_github_session().rest("GET", _LABEL)
    assert (label, api.requested, _remaining()) == (_BUG_LABEL, [f"GET {_url(_LABEL)}"], 4993)


def test_a_read_after_a_404_is_answered_from_its_etag_with_the_quota_github_reports(
    github: Callable[[Case], GitHubApiDouble],
) -> None:
    """Read again after a read GitHub answers 404, a label is sent with the ETag of its first
    answer, and GitHub's 304 gives back the stored label with the quota as it stands: the 404
    spent one, the 304 spends none."""
    api = github(_A_READ_AROUND_A_404)
    session = get_github_session()
    label = session.rest("GET", _LABEL)
    with pytest.raises(GitHubNotFoundError):
        session.rest("GET", _MISSING_LABEL)
    again = session.rest("GET", _LABEL)
    assert (label, again, _conditions(api), _remaining()) == (
        _BUG_LABEL,
        _BUG_LABEL,
        [None, None, _LABEL_ETAG],
        4992,
    )


def test_a_read_of_nothing_raises_the_not_found_error_and_charges_the_quota_github_reported(
    github: Callable[[Case], GitHubApiDouble],
) -> None:
    """GitHub's 404 raises the not-found error naming the path and the status, and the quota it
    reports, one less for the read, reaches the ledger, as every REST answer's does."""
    api = github(_A_READ_OF_NOTHING)
    with pytest.raises(GitHubNotFoundError) as raised:
        get_github_session().rest("GET", _MISSING_LABEL)
    assert (_raised(raised.value), api.requested, _remaining()) == (
        (
            GitHubNotFoundError,
            {
                "error_code": CONST_GITHUB_NOT_FOUND_ERROR_CODE,
                "message": f"GitHub has nothing at GET {_MISSING_LABEL} (HTTP 404)",
                "exit_code": 1,
                "details": {"operation": "github_request", "path": _MISSING_LABEL, "status": 404},
            },
        ),
        [f"GET {_url(_MISSING_LABEL)}"],
        4992,
    )


def test_a_listing_reads_every_page_github_links(
    github: Callable[[Case], GitHubApiDouble],
) -> None:
    """A listing follows GitHub's `rel="next"` link, by the repository's id, to its last page and
    yields every page's items in one sequence."""
    api = github(_A_LISTING)
    branches = list(get_github_session().paginate(_BRANCHES))
    assert (branches, api.requested, _remaining()) == (
        _FIRST_BRANCHES + _LAST_BRANCHES,
        [f"GET {_url(_BRANCHES)}", f"GET {_BRANCHES_PAGE_2}"],
        4903,
    )


def test_a_listing_whose_reader_stops_at_its_first_item_sends_one_request(
    github: Callable[[Case], GitHubApiDouble],
) -> None:
    """A reader that takes one item reads no further page."""
    api = github(_THE_FIRST_PAGE)
    branch = next(iter(get_github_session().paginate(_BRANCHES)))
    assert (branch, api.requested) == (_FIRST_BRANCHES[0], [f"GET {_url(_BRANCHES)}"])


def test_a_listing_read_again_answers_its_first_page_from_its_etag(
    github: Callable[[Case], GitHubApiDouble],
) -> None:
    """Read again, a listing's first page, which links a next one, is sent with its ETag and
    GitHub's 304 keeps its items and next link; the last page is read in full."""
    api = github(_A_LISTING_READ_TWICE)
    session = get_github_session()
    listings = [list(session.paginate(_BRANCHES)) for _ in range(2)]
    assert (listings, _conditions(api), _remaining()) == (
        [_FIRST_BRANCHES + _LAST_BRANCHES] * 2,
        [None, None, _BRANCHES_ETAG, None],
        4902,
    )


def test_a_refused_token_raises_the_unauthenticated_error(
    github: Callable[[Case], GitHubApiDouble],
) -> None:
    """GitHub's 401 for the pinned fake token raises the unauthenticated error when the session
    reads its login. GitHub reports no quota with it, so the ledger keeps its own count: the 5000
    it was given, less the request it paced."""
    api = github(_A_REFUSED_TOKEN)
    with pytest.raises(GitHubUnauthenticatedError) as raised:
        _ = get_github_session().login
    assert (_raised(raised.value), api.requested, _remaining()) == (
        (
            GitHubUnauthenticatedError,
            {
                "error_code": CONST_GITHUB_UNAUTHENTICATED_ERROR_CODE,
                "message": (
                    "GitHub refused the session's token for GET /user (HTTP 401); log in again "
                    "with `gh auth login`, or set GH_TOKEN to a valid token"
                ),
                "exit_code": 1,
                "details": {"operation": "github_request", "path": "/user", "status": 401},
            },
        ),
        [f"GET {_url('/user')}"],
        4999,
    )


def test_a_request_github_cannot_process_is_refused_with_its_status(
    github: Callable[[Case], GitHubApiDouble],
) -> None:
    """GitHub's 422 raises a plain `GitHubOperationError` carrying the status and GitHub's
    reason, and the search quota it reports reaches the ledger: from 25, which pacing the
    request lowers to 24, the ledger holds GitHub's 29."""
    get_github_rate_limiter().update_quota(
        "search", remaining=25, limit=30, reset_epoch=time.time() + 60.0
    )
    api = github(_A_SEARCH_WITHOUT_A_QUERY)
    with pytest.raises(GitHubOperationError) as raised:
        get_github_session().rest("GET", _SEARCH)
    assert (_raised(raised.value), api.requested, _remaining("search")) == (
        (
            GitHubOperationError,
            {
                "error_code": "GITHUB_OPERATION_FAILED",
                "message": f"GitHub refused GET {_SEARCH} (HTTP 422): Validation Failed for 'q'",
                "exit_code": 1,
                "details": {"operation": "github_request", "path": _SEARCH, "status": 422},
            },
        ),
        [f"GET {_url(_SEARCH)}"],
        29,
    )


def test_a_write_answers_the_text_github_rendered(
    github: Callable[[Case], GitHubApiDouble],
) -> None:
    """A POST sends its body as JSON once and gives back GitHub's text answer, charging the
    quota GitHub reported."""
    api = github(_A_WRITE)
    body = {"text": "Hello **world**"}
    rendered = get_github_session().rest("POST", _MARKDOWN, body=body)
    assert (rendered, api.requested, [json.loads(r.content) for r in api.sent], _remaining()) == (
        _RENDERED,
        [f"POST {_url(_MARKDOWN)}"],
        [body],
        4991,
    )


def test_a_write_github_refuses_is_sent_once_and_refused_with_its_status(
    github: Callable[[Case], GitHubApiDouble],
) -> None:
    """GitHub's 400 for a write raises a plain `GitHubOperationError` carrying the status and
    GitHub's reason, without sending the write again."""
    api = github(_A_REFUSED_WRITE)
    with pytest.raises(GitHubOperationError) as raised:
        get_github_session().rest("POST", _MARKDOWN, body={"text": "Hello", "mode": "no-such-mode"})
    assert (_raised(raised.value), api.requested, _remaining()) == (
        (
            GitHubOperationError,
            {
                "error_code": "GITHUB_OPERATION_FAILED",
                "message": f"GitHub refused POST {_MARKDOWN} (HTTP 400): Invalid rendering mode",
                "exit_code": 1,
                "details": {"operation": "github_request", "path": _MARKDOWN, "status": 400},
            },
        ),
        [f"POST {_url(_MARKDOWN)}"],
        4990,
    )


def test_a_reader_that_falls_back_to_gh_fails_offline_under_the_fake_api(
    github_api: GitHubApiFake,
) -> None:
    """A reader that reads through gh rather than the session, as one regressed to `run_gh`
    would, fails at once with the fixture's refusal: no gh child process starts, and nothing
    reaches the fake."""
    refusal = "A test over the fake GitHub API ran gh: ['gh', 'api', 'repos/octo/repo/pages']"
    with pytest.raises(AssertionError, match=re.escape(refusal)):
        get_pages_status("octo/repo")
    assert github_api.sent == []
