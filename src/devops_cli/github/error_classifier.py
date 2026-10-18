"""What a failed GitHub request was, read from its exception's type, HTTP status and headers.

gidgethub raises one exception per failed answer: `RateLimitExceeded` for a 403 that reports no
quota left, `GitHubBroken` for a 5xx, `RedirectionException` for a 3xx it was left with, and
`BadRequest` and its subclasses for any other 4xx. httpx2 raises `HTTPError` when no answer
arrived, and a body that does not decode raises a `ValueError`. `classify_http_error` maps each
onto the project's `GitHubOperationError` classes, so a caller tells a missing scope from a
rate limit or a missing resource by type. Nothing here reads a response's message text: GitHub
words its messages for people, and the status and headers are what its REST documentation
specifies. Every error carries the request's path, at most `CONST_MAX_ERROR_DETAIL_LENGTH`
characters, and an HTTP failure its status, so a caller can treat a 422 as it needs to.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from http import HTTPStatus
from typing import Any, Final
from urllib.request import parse_http_list

from gidgethub import GitHubBroken, HTTPException, RateLimitExceeded, RedirectionException

from devops_cli.config.constants import (
    CONST_GITHUB_HEADER_ACCEPTED_OAUTH_SCOPES,
    CONST_GITHUB_HEADER_OAUTH_SCOPES,
    CONST_GITHUB_HEADER_RATE_LIMIT_RESOURCE,
    CONST_GITHUB_HEADER_RETRY_AFTER,
    CONST_MAX_ERROR_DETAIL_LENGTH,
)
from devops_cli.config.defaults import DEFAULT_GH_RESOURCE
from devops_cli.exceptions.git import (
    GitHubNotFoundError,
    GitHubOperationError,
    GitHubRateLimitError,
    GitHubScopeError,
    GitHubUnauthenticatedError,
    GitHubUnreadError,
)
from devops_cli.github.rate_limiter import parse_retry_after

_OPERATION: Final[str] = "github_request"


@dataclass(frozen=True, slots=True)
class FailedRequest:
    """The request a failure answered: its method and its path on GitHub's API."""

    method: str
    path: str

    def __str__(self) -> str:
        return f"{self.method} {self.path}"[:CONST_MAX_ERROR_DETAIL_LENGTH]

    def details(self, error: HTTPException | None = None) -> dict[str, Any]:
        """The path, bounded, and the HTTP status when GitHub answered."""
        bounded = {"path": self.path[:CONST_MAX_ERROR_DETAIL_LENGTH]}
        return bounded if error is None else {**bounded, "status": int(error.status_code)}


def is_rate_limited(error: HTTPException) -> bool:
    """Whether GitHub refused the request for a primary or secondary rate limit: a 403 that
    reports no quota left (`RateLimitExceeded`), a 429, or a 403 that says when to retry."""
    if isinstance(error, RateLimitExceeded) or error.status_code == HTTPStatus.TOO_MANY_REQUESTS:
        return True
    return (
        error.status_code == HTTPStatus.FORBIDDEN
        and CONST_GITHUB_HEADER_RETRY_AFTER in error.headers
    )


def is_server_error(error: HTTPException) -> bool:
    """Whether GitHub failed to answer the request (a 5xx)."""
    return isinstance(error, GitHubBroken)


def retry_after_seconds(error: HTTPException) -> float | None:
    """The wait GitHub's Retry-After header asks for, or None without one."""
    value = error.headers.get(CONST_GITHUB_HEADER_RETRY_AFTER)
    return None if value is None else parse_retry_after(value)


def _scopes(error: HTTPException, header: str) -> frozenset[str]:
    """The OAuth scopes a comma-separated scope header lists."""
    return frozenset(scope.strip() for scope in parse_http_list(error.headers.get(header, "")))


def missing_scopes(error: HTTPException) -> frozenset[str]:
    """The scopes a 403 accepts when the token holds none of them, else none.

    Both headers must be present: a fine-grained or app token reports no OAuth scopes, so its
    403 says nothing about one.
    """
    headers = (CONST_GITHUB_HEADER_ACCEPTED_OAUTH_SCOPES, CONST_GITHUB_HEADER_OAUTH_SCOPES)
    if error.status_code != HTTPStatus.FORBIDDEN or not all(h in error.headers for h in headers):
        return frozenset()
    accepted = _scopes(error, CONST_GITHUB_HEADER_ACCEPTED_OAUTH_SCOPES)
    return frozenset() if accepted & _scopes(error, CONST_GITHUB_HEADER_OAUTH_SCOPES) else accepted


def _status_is(status: HTTPStatus) -> Callable[[HTTPException], bool]:
    """A predicate true of an answer with `status`."""
    return lambda error: error.status_code == status


def _unanswered(error: HTTPException) -> bool:
    """Whether the answer holds nothing to read: a 5xx, or a 3xx that was not followed."""
    return is_server_error(error) or isinstance(error, RedirectionException)


def _rate_limit_error(error: HTTPException, request: FailedRequest) -> GitHubOperationError:
    return GitHubRateLimitError(
        f"GitHub rate-limited {request} (HTTP {int(error.status_code)}) beyond the retries",
        subcommand=error.headers.get(CONST_GITHUB_HEADER_RATE_LIMIT_RESOURCE, DEFAULT_GH_RESOURCE),
        operation=_OPERATION,
        details=request.details(error),
    )


def _scope_error(error: HTTPException, request: FailedRequest) -> GitHubOperationError:
    needed = ", ".join(sorted(missing_scopes(error)))[:CONST_MAX_ERROR_DETAIL_LENGTH]
    return GitHubScopeError(
        f"The GitHub token lacks the scope {request} needs ({needed}); add one with "
        f"`gh auth refresh -s <scope>`",
        details={**request.details(error), "accepted_scopes": needed},
    )


def _unauthenticated_error(error: HTTPException, request: FailedRequest) -> GitHubOperationError:
    return GitHubUnauthenticatedError(
        f"GitHub refused the session's token for {request} (HTTP 401); log in again with "
        "`gh auth login`, or set GH_TOKEN to a valid token",
        operation=_OPERATION,
        details=request.details(error),
    )


def _not_found_error(error: HTTPException, request: FailedRequest) -> GitHubOperationError:
    return GitHubNotFoundError(
        f"GitHub has nothing at {request} (HTTP 404)", details=request.details(error)
    )


def _unread_error(error: HTTPException, request: FailedRequest) -> GitHubOperationError:
    return GitHubUnreadError(
        f"GitHub gave no readable answer to {request} (HTTP {int(error.status_code)})",
        details=request.details(error),
    )


def _refused_error(error: HTTPException, request: FailedRequest) -> GitHubOperationError:
    reason = str(error)[:CONST_MAX_ERROR_DETAIL_LENGTH]
    return GitHubOperationError(
        f"GitHub refused {request} (HTTP {int(error.status_code)}): {reason}",
        operation=_OPERATION,
        details=request.details(error),
    )


_Classifier = Callable[[HTTPException, FailedRequest], GitHubOperationError]

# In order: a 403 may be a rate limit or a missing scope, and a rate limit wins.
_HTTP_CLASSES: Final[tuple[tuple[Callable[[HTTPException], bool], _Classifier], ...]] = (
    (is_rate_limited, _rate_limit_error),
    (lambda error: bool(missing_scopes(error)), _scope_error),
    (_status_is(HTTPStatus.UNAUTHORIZED), _unauthenticated_error),
    (_status_is(HTTPStatus.NOT_FOUND), _not_found_error),
    (_unanswered, _unread_error),
)


def classify_http_error(error: Exception, *, method: str, path: str) -> GitHubOperationError:
    """The project's error for a failed request: by gidgethub's exception type, status and
    headers for an answer, and `GitHubUnreadError` when no answer could be read."""
    request = FailedRequest(method, path)
    if not isinstance(error, HTTPException):
        return GitHubUnreadError(
            f"GitHub gave no readable answer to {request}: {type(error).__name__}",
            details=request.details(),
        )
    classify = next((build for matches, build in _HTTP_CLASSES if matches(error)), _refused_error)
    return classify(error, request)
