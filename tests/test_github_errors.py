"""How a failed GitHub request is classified: by exception type, HTTP status and headers (#983).

Every HTTP case goes through the session over the fake GitHub API, so gidgethub raises what it
raises for GitHub's answer and the session's retries run first. No HTTP case reads a response's
message: the 403 whose message says "rate limit" without the headers that mean one is a plain
failure. A failed gh command has only its exit status and its stderr, so it is classified from
gh's exit status and the gh-output table in `config/constants.py`, matched against what gh wrote
to stderr, never GitHub's answer on stdout. The table is the one place gh's failures are
classified by its text; the modules its comment names still match gh's text of their own.
"""

from __future__ import annotations

from collections.abc import Callable

import httpx2
import pytest

from devops_cli.exceptions import (
    GitHubFileNotFoundError,
    GitHubNotFoundError,
    GitHubOperationError,
    GitHubRateLimitError,
    GitHubScopeError,
    GitHubUnauthenticatedError,
    GitHubUnreadError,
)
from devops_cli.github.rate_limiter import get_github_rate_limiter
from devops_cli.github.session import get_github_session
from tests.support.fakes.github import JSON_TYPE, GitHubApiFake, github_json, quota_headers

_PATH = "/user/keys"
_SCOPES = {
    "x-oauth-scopes": "repo, read:org",
    "x-accepted-oauth-scopes": "admin:public_key, write:public_key",
}


@pytest.mark.parametrize(
    ("answer", "error", "status"),
    [
        pytest.param(
            lambda: github_json({"message": "Bad credentials"}, status=401),
            GitHubUnauthenticatedError,
            401,
            id="401",
        ),
        pytest.param(
            lambda: github_json(
                {"message": "API rate limit exceeded"},
                status=403,
                headers=quota_headers(0, reset_in=30.0),
            ),
            GitHubRateLimitError,
            403,
            id="403-with-no-quota-left",
        ),
        pytest.param(
            lambda: github_json({"message": "abuse"}, status=403, headers={"retry-after": "5"}),
            GitHubRateLimitError,
            403,
            id="403-with-retry-after",
        ),
        pytest.param(
            lambda: github_json({"message": "Too Many Requests"}, status=429),
            GitHubRateLimitError,
            429,
            id="429",
        ),
        pytest.param(
            lambda: github_json({"message": "Forbidden"}, status=403, headers=_SCOPES),
            GitHubScopeError,
            403,
            id="403-with-a-missing-scope",
        ),
        pytest.param(
            lambda: github_json(
                {"message": "Forbidden"},
                status=403,
                headers={**_SCOPES, "x-oauth-scopes": "repo, write:public_key"},
            ),
            GitHubOperationError,
            403,
            id="403-with-an-accepted-scope-held",
        ),
        pytest.param(
            lambda: github_json({"message": "API rate limit exceeded for user ID 1."}, status=403),
            GitHubOperationError,
            403,
            id="403-whose-message-says-rate-limit-without-its-headers",
        ),
        pytest.param(
            lambda: github_json({"message": "Not Found"}, status=404),
            GitHubNotFoundError,
            404,
            id="404",
        ),
        pytest.param(
            lambda: github_json(
                {
                    "message": "Validation Failed",
                    "errors": [{"code": "custom", "field": "key", "message": "in use"}],
                },
                status=422,
            ),
            GitHubOperationError,
            422,
            id="422",
        ),
        pytest.param(
            lambda: github_json({"message": "Server Error"}, status=503),
            GitHubUnreadError,
            503,
            id="5xx-after-the-retries",
        ),
    ],
)
def test_an_http_failure_is_classified_by_status_and_headers(
    github_api: GitHubApiFake,
    answer: Callable[[], httpx2.Response],
    error: type[Exception],
    status: int,
) -> None:
    """Each failed answer raises its class, carrying the status and the request path.

    Each answer is built when its test runs, so a quota's reset is still ahead of the clock.
    """
    github_api.route("GET", _PATH, answer())
    with pytest.raises(GitHubOperationError) as raised:
        get_github_session().rest("GET", _PATH)
    details = raised.value.details
    assert (type(raised.value), details["status"], details["path"]) == (error, status, _PATH)


@pytest.mark.parametrize(
    "answer",
    [
        pytest.param(httpx2.ConnectError, id="connect-error"),
        pytest.param(
            httpx2.Response(200, headers={"content-type": JSON_TYPE}, content=b'{"login": '),
            id="undecodable-body",
        ),
        pytest.param(
            httpx2.Response(
                200, headers={"content-type": "application/json; charset=x-nope"}, content=b"{}"
            ),
            id="unknown-charset",
        ),
        pytest.param(
            httpx2.Response(520, headers={"content-type": JSON_TYPE}, content=b'{"message": "x"}'),
            id="status-outside-http",
        ),
        pytest.param(
            httpx2.Response(
                200,
                headers={
                    "content-type": JSON_TYPE,
                    "x-ratelimit-limit": "5000",
                    "x-ratelimit-remaining": "lots",
                    "x-ratelimit-reset": "1",
                },
                content=b"{}",
            ),
            id="quota-that-is-no-number",
        ),
    ],
)
def test_no_readable_answer_raises_the_unread_error_without_a_retry(
    github_api: GitHubApiFake, answer: httpx2.Response | type[httpx2.TransportError]
) -> None:
    """A refused connect, a body that does not decode, a status HTTP does not define and quota
    headers that are not numbers are unread, and the request is not sent again."""
    github_api.route("GET", _PATH, answer)
    with pytest.raises(GitHubOperationError) as raised:
        get_github_session().rest("GET", _PATH)
    assert (type(raised.value), raised.value.details["path"], len(github_api.sent)) == (
        GitHubUnreadError,
        _PATH,
        1,
    )


def test_a_retry_wait_past_the_limit_names_the_request_and_its_status(
    github_api: GitHubApiFake,
) -> None:
    """When GitHub asks for a longer wait than `max_rate_limit_wait`, the refusal carries the
    path and the status that asked for it, and nothing is sent again."""
    get_github_rate_limiter().max_rate_limit_wait = 1.0
    github_api.route(
        "GET", _PATH, github_json({"message": "abuse"}, status=429, headers={"retry-after": "30"})
    )
    with pytest.raises(GitHubRateLimitError) as raised:
        get_github_session().rest("GET", _PATH)
    details = raised.value.details
    assert (details["status"], details["path"], len(github_api.sent)) == (429, _PATH, 1)


@pytest.mark.parametrize(
    ("headers", "error"),
    [
        pytest.param(dict, GitHubUnauthenticatedError, id="no-quota-headers"),
        pytest.param(lambda: quota_headers(4000), GitHubOperationError, id="quota-headers"),
    ],
)
def test_a_403_to_a_write_that_reports_no_quota_is_a_refused_identity(
    github_api: GitHubApiFake,
    headers: Callable[[], dict[str, str]],
    error: type[GitHubOperationError],
) -> None:
    """GitHub sends `x-ratelimit-*` with each answer it counts against an identity's quota, and
    its refusal of an identity counts against none (#2474). A 403 to a read with no such header
    stays a plain failure (`403-whose-message-says-rate-limit-without-its-headers` above)."""
    github_api.route(
        "POST", _PATH, github_json({"message": "Forbidden"}, status=403, headers=headers())
    )
    with pytest.raises(GitHubOperationError) as raised:
        get_github_session().rest("POST", _PATH, body={"title": "laptop", "key": "ssh-ed25519 A"})
    details = raised.value.details
    assert (type(raised.value), details["status"], details["path"]) == (error, 403, _PATH)


def test_a_long_path_is_bounded_in_the_details(github_api: GitHubApiFake) -> None:
    """The path a classified error carries is at most 256 characters."""
    path = f"/repos/octo/repo/contents/{'a' * 400}"
    with pytest.raises(GitHubNotFoundError) as raised:
        get_github_session().rest("GET", path)
    assert raised.value.details["path"] == path[:256]


def test_an_entry_that_is_no_object_names_its_type_and_the_bounded_path() -> None:
    """The error for a listing entry that is not an object names the entry's type, never its
    text, and carries the listing's path at most 256 characters long."""
    from devops_cli.github.error_classifier import unlisted_entry

    path = f"/repos/octo/repo/issues?q={'a' * 400}"
    error = unlisted_entry("ghp_not_shown", path=path)
    assert (
        type(error),
        "holds a str, not an object" in error.message,
        "ghp_not_shown" in error.message,
        error.details["path"],
    ) == (GitHubUnreadError, True, False, path[:256])


def test_the_session_errors_are_github_operation_errors_with_their_own_codes() -> None:
    """Every `except GitHubOperationError` still catches them, and each has its error code."""
    errors = (
        GitHubScopeError("scope"),
        GitHubNotFoundError("missing"),
        GitHubUnreadError("unread"),
        GitHubUnauthenticatedError("refused", operation="github_request"),
    )
    assert (
        all(isinstance(error, GitHubOperationError) for error in errors),
        [error.error_code for error in errors],
        errors[3].details["operation"],
        issubclass(GitHubFileNotFoundError, GitHubNotFoundError),
        GitHubFileNotFoundError("gone").error_code,
    ) == (
        True,
        [
            "GITHUB_SCOPE_MISSING",
            "GITHUB_NOT_FOUND",
            "GITHUB_UNREAD",
            "GITHUB_UNAUTHENTICATED",
        ],
        "github_request",
        True,
        "GITHUB_FILE_NOT_FOUND",
    )


def _every_phrase_of_the_gh_table() -> dict[tuple[str, int], type[GitHubOperationError] | None]:
    """Each phrase of the gh-output table, written as gh writes a failure and upper-cased, with
    the class its row means. A phrase two rows hold maps to the later row here, so a phrase the
    classifier reads as another class fails the table."""
    from devops_cli.config.constants import (
        CONST_GITHUB_RATE_LIMIT_PATTERNS,
        CONST_GITHUB_SCOPE_PATTERNS,
        CONST_GITHUB_SECONDARY_RATE_LIMIT_PATTERNS,
        CONST_GITHUB_UNAUTHENTICATED_PATTERNS,
    )

    rows: dict[str, type[GitHubOperationError]] = {
        **dict.fromkeys(
            CONST_GITHUB_RATE_LIMIT_PATTERNS + CONST_GITHUB_SECONDARY_RATE_LIMIT_PATTERNS,
            GitHubRateLimitError,
        ),
        **dict.fromkeys(CONST_GITHUB_SCOPE_PATTERNS, GitHubScopeError),
        **dict.fromkeys(CONST_GITHUB_UNAUTHENTICATED_PATTERNS, GitHubUnauthenticatedError),
    }
    return {(f"gh: {phrase.upper()}", 1): error for phrase, error in rows.items()}


_SCOPE_SUGGESTION = (
    "gh: Not Found (HTTP 404)\n"
    'gh: This API operation needs the "admin:public_key" scope. To request it, run:  '
    "gh auth refresh -h github.com -s admin:public_key"
)

# What gh writes, as gh 2.102.0 and go-gh format it, and the status gh exits with.
_GH_FAILURES: dict[tuple[str, int], type[GitHubOperationError] | None] = {
    ("gh: Bad credentials (HTTP 401)", 1): GitHubUnauthenticatedError,
    ("HTTP 401: Bad credentials (https://api.github.com/graphql)", 1): GitHubUnauthenticatedError,
    (
        "You are not logged into any GitHub hosts. To log in, run: gh auth login",
        1,
    ): GitHubUnauthenticatedError,
    # `gh api` relays GitHub's 401 for a request without a token as `<message> (HTTP 401)`.
    ("gh: Requires authentication (HTTP 401)", 1): GitHubUnauthenticatedError,
    # GitHub's 403 for a suspended account, as the Service's log shows it (#2161).
    ("gh: Sorry. Your account was suspended. (HTTP 403)", 1): GitHubUnauthenticatedError,
    # GitHub's 403 for a suspended App installation: to the request for a token, and to a request
    # with a token minted before the suspension, as probot/probot#1482 shows them (#2474).
    ("gh: This installation has been suspended (HTTP 403)", 1): GitHubUnauthenticatedError,
    (
        "gh: Sorry. This installation owned by example-org suspended your access at "
        "2021-03-02T22:29:29Z. (HTTP 403)",
        1,
    ): GitHubUnauthenticatedError,
    # A proxy that wants credentials answers 407, which Go's net/http names by its reason phrase:
    # no GitHub login failure.
    ('Post "https://api.github.com/graphql": Proxy Authentication Required', 1): None,
    (
        "To get started with GitHub CLI, please run:  gh auth login",
        4,
    ): GitHubUnauthenticatedError,
    ("", 4): GitHubUnauthenticatedError,
    ("gh: API rate limit exceeded for user ID 1. (HTTP 403)", 1): GitHubRateLimitError,
    ("GraphQL: API rate limit already exceeded for user ID 1.", 1): GitHubRateLimitError,
    ("gh: Too Many Requests (HTTP 429)", 1): GitHubRateLimitError,
    (_SCOPE_SUGGESTION, 1): GitHubScopeError,
    (
        "error: your authentication token is missing required scopes [read:project]\n"
        "To request it, run:  gh auth refresh -s read:project",
        1,
    ): GitHubScopeError,
    # gh project's owner lookup dropped its error: no rate-limit row, a rate limit of its own.
    ("unknown owner type", 1): GitHubRateLimitError,
    ("gh: Not Found (HTTP 404)", 1): None,
    ("gh: Validation Failed (HTTP 422)", 1): None,
    ("gh: Server Error (HTTP 500)", 1): None,
    ("", 1): None,
}


def _class_of(error: GitHubOperationError | None) -> type[GitHubOperationError] | None:
    return None if error is None else type(error)


def test_a_gh_failure_is_classified_by_its_exit_status_and_the_gh_output_table() -> None:
    """Every phrase of the table, `HTTP 401`, `Bad credentials`, `not logged in` and gh's exit
    status 4 ("requires authentication", `gh help exit-codes`) map to their class in any case;
    anything else is no class."""
    from devops_cli.github.error_classifier import classify_gh_failure

    table = {**_every_phrase_of_the_gh_table(), **_GH_FAILURES}
    classified = {
        (output, exit_code): _class_of(classify_gh_failure(output, exit_code=exit_code))
        for output, exit_code in table
    }
    assert classified == table


# Rows the gh-output table took from the board scope check's old phrase list, and the
# "authentication required" row. Neither gh 2.102.0 nor go-gh 2.16.1, the version gh 2.102.0
# builds with, writes any of them for a GitHub failure. In their sources at those tags the scope
# wordings appear nowhere, "project scope" only in the help of gh's skill installer, and
# "authentication required" only in the exit-codes section of gh's man page; gh's stderr holds it
# only inside "Proxy Authentication Required", the reason phrase of a proxy's 407, which is no
# GitHub login failure.
_PHRASES_OF_NO_GITHUB_FAILURE: tuple[str, ...] = (
    "scope 'project'",
    'scope "project"',
    "requires additional permissions",
    "requires the 'project' scope",
    "need the 'project' scope",
    "project scope",
    "authentication required",
)


def test_a_phrase_gh_writes_for_no_github_failure_names_no_class() -> None:
    """The table holds only what gh writes for a GitHub failure, so other text, which a command
    could still echo from what it was given, is no class of failure."""
    from devops_cli.github.error_classifier import classify_gh_failure

    classified = {
        phrase: _class_of(classify_gh_failure(f"gh: {phrase}", exit_code=1))
        for phrase in _PHRASES_OF_NO_GITHUB_FAILURE
    }
    assert classified == dict.fromkeys(_PHRASES_OF_NO_GITHUB_FAILURE)


@pytest.mark.parametrize(
    ("said", "error"),
    [
        pytest.param(
            "HTTP 404: Not Found "
            "(https://api.github.com/repos/o/r/actions/runs?branch=fix%2F705-retry-after-handling)",
            None,
            id="branch-in-the-url",
        ),
        pytest.param(
            "pull request create failed: GraphQL: No commits between main and "
            "fix/705-retry-after-handling (createPullRequest)",
            None,
            id="branch-in-the-message",
        ),
        pytest.param(
            "HTTP 401: Bad credentials "
            "(https://api.github.com/repos/o/r/actions/runs?branch=fix%2Fretry-after)",
            GitHubUnauthenticatedError,
            id="401-whose-url-names-retry-after",
        ),
    ],
)
def test_text_gh_echoes_from_the_request_names_no_rate_limit(
    said: str, error: type[GitHubOperationError] | None
) -> None:
    """gh echoes the request's URL and GraphQL echoes ref names, such as a `fix/...-retry-after`
    branch; gh never writes "retry-after" for a failure, so that text is no rate limit."""
    from devops_cli.github.error_classifier import classify_gh_failure

    assert _class_of(classify_gh_failure(said, exit_code=1)) is error


@pytest.mark.parametrize(
    ("output", "status"),
    [
        pytest.param("gh: Bad credentials (HTTP 401)", 401, id="gh-api-401"),
        pytest.param(
            "HTTP 401: Bad credentials (https://api.github.com/user)", 401, id="go-gh-401"
        ),
        pytest.param("gh: API rate limit exceeded for user ID 1. (HTTP 403)", 403, id="403"),
        pytest.param("gh: Too Many Requests (HTTP 429)", 429, id="429"),
        pytest.param(_SCOPE_SUGGESTION, 404, id="scope-404"),
        pytest.param("You are not logged into any GitHub hosts.", None, id="no-status"),
    ],
)
def test_a_classified_gh_failure_keeps_the_status_gh_wrote_as_an_int(
    output: str, status: int | None
) -> None:
    """The status gh names (`(HTTP 401)` or `HTTP 401:`) is carried as an int beside gh's exit
    status and the operation, so a caller reads a status, never gh's text."""
    from devops_cli.github.error_classifier import classify_gh_failure

    error = classify_gh_failure(output, exit_code=1, operation="verify_project_auth_scopes")
    assert error is not None
    details = error.details
    assert (
        details.get("status"),
        type(details.get("status")),
        details["exit_code"],
        details["operation"],
    ) == (status, type(status), 1, "verify_project_auth_scopes")


def test_a_classified_gh_failure_bounds_what_gh_wrote_on_one_line() -> None:
    """gh's output reaches the message and the details on one line, at most 256 characters."""
    from devops_cli.github.error_classifier import classify_gh_failure

    error = classify_gh_failure(f"gh: Bad credentials (HTTP 401)\n{'x' * 400}", exit_code=1)
    assert error is not None
    said = error.details["output"]
    assert (
        len(said),
        said.startswith("gh: Bad credentials (HTTP 401) xxx"),
        "\n" in error.message,
        said in error.message,
    ) == (256, True, False, True)


def test_the_status_gh_wrote_is_read_from_either_of_its_formats() -> None:
    """`gh api` writes `<message> (HTTP <status>)` or `HTTP <status>`, and other gh commands
    go-gh's `HTTP <status>: <message> (<url>)`; text naming no status has none."""
    from devops_cli.github.error_classifier import gh_http_status

    assert [
        gh_http_status(output)
        for output in (
            "gh: Validation Failed (HTTP 422)",
            "HTTP 502: Bad Gateway (https://api.github.com/graphql)",
            "gh: HTTP 404",
            "error: repository not found",
            "HTTP 4040",
        )
    ] == [422, 502, 404, None, None]


def test_a_refusal_by_the_token_is_a_403_that_names_the_integration() -> None:
    """GitHub answers a path that the permissions of an installation token do not cover with
    HTTP 403 "Resource not accessible by integration". A rate limit, a missing scope and a 404
    are not that refusal, nor is the phrase with another status (#2752)."""
    from devops_cli.github.error_classifier import is_gh_refused_by_token

    assert [
        is_gh_refused_by_token(output)
        for output in (
            "gh: Resource not accessible by integration (HTTP 403)",
            "gh: resource not accessible by integration (HTTP 403)",
            "gh: Resource not accessible by integration (HTTP 404)",
            "gh: You have exceeded a secondary rate limit (HTTP 403)",
            "gh: Bad Gateway (HTTP 502)",
            "",
        )
    ] == [True, True, False, False, False, False]
