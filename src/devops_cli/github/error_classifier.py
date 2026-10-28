"""What a failed GitHub request was, read from its exception's type, HTTP status and headers.

gidgethub raises one exception per failed answer: `RateLimitExceeded` for a 403 that reports no
quota left, `GitHubBroken` for a 5xx, `RedirectionException` for a 3xx it was left with, and
`BadRequest` and its subclasses for any other 4xx. httpx2 raises `HTTPError` when no answer
arrived. An answer that cannot be read at all raises `ValueError` or `LookupError` from the
decoding: a body that is not the JSON or text it claims, a charset Python does not know, a status
outside `http.HTTPStatus`, or rate-limit headers that are not numbers. `classify_http_error` maps
each onto the project's `GitHubOperationError` classes, so a caller tells a missing scope from a
rate limit or a missing resource by type. A 403 to a write whose answer carries no `x-ratelimit-*`
header is a refused identity, as a 401 is: GitHub sends those headers with each answer it counts
against an identity's quota, and its refusal of the identity, such as of a suspended App
installation's token, counts against none (#2474). Nothing here reads a response's message text:
GitHub words its messages for people, and the status and headers are what its REST documentation
specifies. Every error carries the request's path, at most `CONST_MAX_ERROR_DETAIL_LENGTH`
characters, and an HTTP failure its status as an int, so a caller can treat a 422 as it needs to.

A failed gh command has no exception to read, only its exit status and what it wrote to stderr,
so `classify_gh_failure` reads those against the gh-output table in `config/constants.py`, the
one place gh's failures are classified by its text: a rate limit, a missing scope, an owner gh
project could not look up, or no login GitHub accepts, which gh's exit status 4 ("requires
authentication") also means. gh writes every failure to stderr; its stdout holds GitHub's
answer, which for a failed GraphQL read may carry partial data such as item titles, so stdout is
never classified. The status gh names on stderr is carried as an int, like an HTTP failure's. A
few modules outside this one still match gh's text of their own; the table's comment names them.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from email.utils import parsedate_to_datetime
from http import HTTPStatus
from typing import Any, Final
from urllib.request import parse_http_list

from gidgethub import GitHubBroken, HTTPException, RateLimitExceeded, RedirectionException

from devops_cli.config.constants import (
    CONST_GH_AUTH_REQUIRED_EXIT_CODE,
    CONST_GH_HTTP_STATUS_RE,
    CONST_GH_UNKNOWN_OWNER_TYPE,
    CONST_GITHUB_HEADER_ACCEPTED_OAUTH_SCOPES,
    CONST_GITHUB_HEADER_OAUTH_SCOPES,
    CONST_GITHUB_HEADER_RATE_LIMIT_PREFIX,
    CONST_GITHUB_HEADER_RATE_LIMIT_RESOURCE,
    CONST_GITHUB_HEADER_RETRY_AFTER,
    CONST_GITHUB_RATE_LIMIT_PATTERNS,
    CONST_GITHUB_SCOPE_PATTERNS,
    CONST_GITHUB_SECONDARY_RATE_LIMIT_PATTERNS,
    CONST_GITHUB_UNAUTHENTICATED_PATTERNS,
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
from devops_cli.github.request_classifier import GitHubRequest, is_write_request

_OPERATION: Final[str] = "github_request"
_GH_OPERATION: Final[str] = "gh_command"


def parse_retry_after(value: str, default: float | None = None) -> float | None:
    """A Retry-After value as seconds: its delay-seconds, or the time until its HTTP-date."""
    try:
        return float(value.strip())
    except ValueError:
        return _seconds_until(value, default)


def _seconds_until(http_date: str, default: float | None) -> float | None:
    """The seconds until an HTTP-date, none if it has passed, or `default` for no date."""
    try:
        delay = parsedate_to_datetime(http_date.strip()).timestamp() - time.time()
    except ValueError, TypeError:
        return default
    return max(0.0, delay)


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


def _status_is(status: HTTPStatus) -> Callable[[HTTPException, FailedRequest], bool]:
    """A predicate true of an answer with `status`."""
    return lambda error, _request: error.status_code == status


def _unanswered(error: HTTPException, _request: FailedRequest) -> bool:
    """Whether the answer holds nothing to read: a 5xx, or a 3xx that was not followed."""
    return is_server_error(error) or isinstance(error, RedirectionException)


def _reports_no_quota(error: HTTPException) -> bool:
    """Whether the answer carries no `x-ratelimit-*` header, so GitHub counted the request
    against no identity's quota."""
    prefix = CONST_GITHUB_HEADER_RATE_LIMIT_PREFIX
    return not any(name.lower().startswith(prefix) for name in error.headers)


def _refused_write(error: HTTPException, request: FailedRequest) -> bool:
    """Whether GitHub refused a write with a 403 that it counted against no quota (#2474)."""
    return (
        error.status_code == HTTPStatus.FORBIDDEN
        and is_write_request(GitHubRequest(request.method, request.path))
        and _reports_no_quota(error)
    )


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


def _refused_identity_error(error: HTTPException, request: FailedRequest) -> GitHubOperationError:
    reason = str(error)[:CONST_MAX_ERROR_DETAIL_LENGTH]
    return GitHubUnauthenticatedError(
        f"GitHub refused the identity for {request} (HTTP 403, with no rate-limit header): "
        f"{reason}",
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

# In order: a 403 may be a rate limit, a missing scope or a refused identity, and a rate limit
# wins.
_HTTP_CLASSES: Final[
    tuple[tuple[Callable[[HTTPException, FailedRequest], bool], _Classifier], ...]
] = (
    (lambda error, _request: is_rate_limited(error), _rate_limit_error),
    (lambda error, _request: bool(missing_scopes(error)), _scope_error),
    (_status_is(HTTPStatus.UNAUTHORIZED), _unauthenticated_error),
    (_refused_write, _refused_identity_error),
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
    classify = next(
        (build for matches, build in _HTTP_CLASSES if matches(error, request)), _refused_error
    )
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


def unlisted_entry(entry: Any, *, path: str) -> GitHubUnreadError:
    """The error for an entry of a listing of objects that is not one. Its type is named, never
    its text."""
    request = FailedRequest("GET", path)
    return GitHubUnreadError(
        f"GitHub's listing at {request} holds a {type(entry).__name__}, not an object",
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


def _gh_says(output: str, phrases: tuple[str, ...]) -> bool:
    """Whether what gh wrote holds one of `phrases`, in any case."""
    said = output.lower()
    return any(phrase in said for phrase in phrases)


def is_gh_rate_limited(output: str) -> bool:
    """Whether what gh wrote to stderr names a primary or secondary rate limit."""
    return _gh_says(
        output, CONST_GITHUB_RATE_LIMIT_PATTERNS + CONST_GITHUB_SECONDARY_RATE_LIMIT_PATTERNS
    )


def is_gh_owner_lookup_failure(output: str) -> bool:
    """Whether gh project wrote to stderr that it could not look up the owner it was given,
    dropping why."""
    return _gh_says(output, (CONST_GH_UNKNOWN_OWNER_TYPE,))


def gh_http_status(output: str) -> int | None:
    """The HTTP status gh names in what it wrote to stderr, or None when it names none."""
    found = CONST_GH_HTTP_STATUS_RE.search(output)
    return None if found is None else int(found.group("status"))


def gh_failure_details(output: str, *, exit_code: int | None) -> dict[str, Any]:
    """A failed gh command's details: its exit status, the HTTP status gh names, both as ints,
    and what gh wrote on one line, at most `CONST_MAX_ERROR_DETAIL_LENGTH` characters."""
    said = " ".join(output.split())[:CONST_MAX_ERROR_DETAIL_LENGTH]
    found = {"exit_code": exit_code, "status": gh_http_status(output), "output": said}
    return {key: value for key, value in found.items() if value is not None}


@dataclass(frozen=True, slots=True)
class _GhFailure:
    """A gh command that failed: what it wrote, its exit status and the operation it served."""

    output: str
    exit_code: int | None
    operation: str

    def details(self) -> dict[str, Any]:
        return gh_failure_details(self.output, exit_code=self.exit_code)

    def reason(self) -> str:
        """What gh wrote, bounded on one line, or its exit status when it wrote nothing."""
        return str(self.details()["output"]) or f"gh exited {self.exit_code}"


def _gh_rate_limit_error(failure: _GhFailure) -> GitHubOperationError:
    return GitHubRateLimitError(
        f"GitHub rate-limited a gh command ({failure.reason()}); wait for the quota to reset, "
        "which `devops gh rate-limit` shows",
        operation=failure.operation,
        details=failure.details(),
    )


def _gh_owner_lookup_error(failure: _GhFailure) -> GitHubOperationError:
    return GitHubRateLimitError(
        f"gh could not look up the board owner and did not say why ({failure.reason()}); a spent "
        "GraphQL quota is one cause, which `devops gh rate-limit` shows",
        operation=failure.operation,
        details=failure.details(),
    )


def _gh_scope_error(failure: _GhFailure) -> GitHubOperationError:
    return GitHubScopeError(
        f"The GitHub token lacks a scope a gh command needs ({failure.reason()}); add it with "
        "`gh auth refresh -s <scope>`",
        operation=failure.operation,
        details=failure.details(),
    )


def _gh_unauthenticated_error(failure: _GhFailure) -> GitHubOperationError:
    return GitHubUnauthenticatedError(
        f"gh has no GitHub login that GitHub accepts ({failure.reason()}); log in with "
        "`gh auth login`, or set GH_TOKEN to a valid token",
        operation=failure.operation,
        details=failure.details(),
    )


def _gh_requires_authentication(failure: _GhFailure) -> bool:
    return failure.exit_code == CONST_GH_AUTH_REQUIRED_EXIT_CODE


_GhClassifier = Callable[[_GhFailure], GitHubOperationError]

# In order: gh's documented exit status first, then its text, where a rate limit wins. An owner
# lookup that gh dropped the cause of is classified as a rate limit, but is no rate-limit row, so
# `run_gh` never backs off on it.
_GH_CLASSES: Final[tuple[tuple[Callable[[_GhFailure], bool], _GhClassifier], ...]] = (
    (_gh_requires_authentication, _gh_unauthenticated_error),
    (lambda failure: is_gh_rate_limited(failure.output), _gh_rate_limit_error),
    (lambda failure: is_gh_owner_lookup_failure(failure.output), _gh_owner_lookup_error),
    (lambda failure: _gh_says(failure.output, CONST_GITHUB_SCOPE_PATTERNS), _gh_scope_error),
    (
        lambda failure: _gh_says(failure.output, CONST_GITHUB_UNAUTHENTICATED_PATTERNS),
        _gh_unauthenticated_error,
    ),
)


def classify_gh_failure(
    output: str, *, exit_code: int | None = None, operation: str = _GH_OPERATION
) -> GitHubOperationError | None:
    """The project's error for a gh command that exited `exit_code` writing `output` to stderr:
    a rate limit, an owner gh could not look up, a missing scope or no accepted login, read from
    the exit status and the gh-output table; or None when neither names one, so the caller
    reports the failure as its own. `output` is gh's stderr, never GitHub's answer on stdout."""
    failure = _GhFailure(output, exit_code, operation)
    return next((build(failure) for matches, build in _GH_CLASSES if matches(failure)), None)
