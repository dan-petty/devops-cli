"""What a failed GitHub request was, read from its exception's type, HTTP status and headers.

gidgethub raises one exception per failed answer: `RateLimitExceeded` for a 403 that reports no
quota left, `GitHubBroken` for a 5xx, `RedirectionException` for a 3xx it was left with, and
`BadRequest` and its subclasses for any other 4xx. httpx2 raises `HTTPError` when no answer
arrived. An answer that cannot be read at all raises `ValueError` or `LookupError` from the
decoding: a body that is not the JSON or text it claims, a charset Python does not know, a status
outside `http.HTTPStatus`, or rate-limit headers that are not numbers. `classify_http_error` maps
each onto the project's `GitHubOperationError` classes, so a caller tells a missing scope from a
rate limit or a missing resource by type. Nothing here reads a response's message text: GitHub
words its messages for people, and the status and headers are what its REST documentation
specifies. Every error carries the request's path, at most `CONST_MAX_ERROR_DETAIL_LENGTH`
characters, and an HTTP failure its status as an int, so a caller can treat a 422 as it needs to.
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
    """The request a failure answered: its method, its path on GitHub's API and, for a listing
    read page by page, the page."""

    method: str
    path: str
    page: int | None = None

    def __str__(self) -> str:
        page = "" if self.page is None else f" (page {self.page})"
        return f"{self.method} {self.path[:CONST_MAX_ERROR_DETAIL_LENGTH]}{page}"

    def details(self, error: HTTPException | None = None) -> dict[str, Any]:
        """The path, bounded, the page of a listing, and the HTTP status when GitHub answered."""
        bounded: dict[str, Any] = {"path": self.path[:CONST_MAX_ERROR_DETAIL_LENGTH]}
        if self.page is not None:
            bounded["page"] = self.page
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


def classify_http_error(
    error: Exception, *, method: str, path: str, page: int | None = None
) -> GitHubOperationError:
    """The project's error for a failed request, or for one page of a listing: by gidgethub's
    exception type, status and headers for an answer, and `GitHubUnreadError` when no answer
    could be read."""
    request = FailedRequest(method, path, page)
    if not isinstance(error, HTTPException):
        return GitHubUnreadError(
            f"GitHub gave no readable answer to {request}: {type(error).__name__}",
            details=request.details(),
        )
    classify = next((build for matches, build in _HTTP_CLASSES if matches(error)), _refused_error)
    return classify(error, request)


def refused_retry(
    refusal: GitHubRateLimitError, error: HTTPException, *, method: str, path: str
) -> GitHubRateLimitError:
    """The ledger's refusal to wait as long as GitHub asked before a retry, carrying the request's
    path and the status that asked for the wait."""
    request = FailedRequest(method, path)
    return GitHubRateLimitError(
        f"{refusal.message} ({request}, HTTP {int(error.status_code)})",
        subcommand=str(refusal.details.get("subcommand", DEFAULT_GH_RESOURCE)),
        operation=_OPERATION,
        details={**refusal.details, "operation": _OPERATION, **request.details(error)},
    )


def unlisted_page(
    answer: Any, *, path: str, page: int, iterable_key: str | None
) -> GitHubUnreadError:
    """The error for a page of a listing that holds no list of items: not a JSON array, or not an
    object holding one under `iterable_key`. Its type is named, never its text."""
    request = FailedRequest("GET", path, page)
    expected = (
        "a JSON array" if iterable_key is None else f"an object with a list at {iterable_key!r}"
    )
    return GitHubUnreadError(
        f"GitHub's answer to {request} is {type(answer).__name__}, not {expected}",
        details=request.details(),
    )


def listing_past_page_cap(*, path: str, max_pages: int) -> GitHubUnreadError:
    """The error for a listing still linking a next page after `max_pages` pages: a chain that
    never ends is read no further, and the listing is never taken as whole."""
    request = FailedRequest("GET", path)
    return GitHubUnreadError(
        f"The listing at {request} runs past {max_pages} pages, so the read can't complete",
        details={**request.details(), "max_pages": max_pages},
    )


def unread_after_close(*, method: str, path: str) -> GitHubUnreadError:
    """The error of a request the session's close stopped before GitHub's answer was read."""
    request = FailedRequest(method, path)
    return GitHubUnreadError(
        f"The GitHub session closed before {request} was answered", details=request.details()
    )
