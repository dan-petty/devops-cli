"""How a failed GitHub request is classified: by exception type, HTTP status and headers (#983).

Every case goes through the session over the fake GitHub API, so gidgethub raises what it raises
for GitHub's answer and the session's retries run first. No case reads a response's message: the
403 whose message says "rate limit" without the headers that mean one is a plain failure.
"""

from __future__ import annotations

from collections.abc import Callable

import httpx2
import pytest

from devops_cli.config.constants import (
    CONST_GITHUB_NOT_FOUND_ERROR_CODE,
    CONST_GITHUB_SCOPE_ERROR_CODE,
    CONST_GITHUB_UNAUTHENTICATED_ERROR_CODE,
    CONST_GITHUB_UNREAD_ERROR_CODE,
)
from devops_cli.exceptions import (
    GitHubFileNotFoundError,
    GitHubNotFoundError,
    GitHubOperationError,
    GitHubRateLimitError,
    GitHubScopeError,
    GitHubUnauthenticatedError,
    GitHubUnreadError,
)
from devops_cli.github.session import get_github_session
from tests.github_session_fakes import JSON_TYPE, GitHubApiFake, github_json, quota_headers

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
    assert (type(raised.value), int(details["status"]), details["path"]) == (error, status, _PATH)


@pytest.mark.parametrize(
    "answer",
    [
        pytest.param(httpx2.ConnectError, id="connect-error"),
        pytest.param(
            httpx2.Response(200, headers={"content-type": JSON_TYPE}, content=b'{"login": '),
            id="undecodable-body",
        ),
    ],
)
def test_no_readable_answer_raises_the_unread_error_without_a_retry(
    github_api: GitHubApiFake, answer: httpx2.Response | type[httpx2.TransportError]
) -> None:
    """A refused connect or a body that does not decode is unread, and is not sent again."""
    github_api.route("GET", _PATH, answer)
    with pytest.raises(GitHubOperationError) as raised:
        get_github_session().rest("GET", _PATH)
    assert (type(raised.value), raised.value.details["path"], len(github_api.sent)) == (
        GitHubUnreadError,
        _PATH,
        1,
    )


def test_a_long_path_is_bounded_in_the_details(github_api: GitHubApiFake) -> None:
    """The path a classified error carries is at most 256 characters."""
    path = f"/repos/octo/repo/contents/{'a' * 400}"
    with pytest.raises(GitHubNotFoundError) as raised:
        get_github_session().rest("GET", path)
    assert raised.value.details["path"] == path[:256]


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
            CONST_GITHUB_SCOPE_ERROR_CODE,
            CONST_GITHUB_NOT_FOUND_ERROR_CODE,
            CONST_GITHUB_UNREAD_ERROR_CODE,
            CONST_GITHUB_UNAUTHENTICATED_ERROR_CODE,
        ],
        "github_request",
        True,
        "GITHUB_FILE_NOT_FOUND",
    )
