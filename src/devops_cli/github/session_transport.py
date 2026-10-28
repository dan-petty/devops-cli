"""The GitHub session's REST transport: gidgethub over one httpx2 client in one anyio portal (#983).

gidgethub builds each request and decodes each answer; its httpx2 adapter sends them through an
`httpx2.AsyncClient` the factory builds at the public egress level. That client follows redirects
and runs one request hook, `refuse_other_origins`, before the first request and before every hop,
so the session's token goes to GitHub's API origin and nowhere else. An async client is bound to
the event loop it first runs on, so the transport owns one anyio blocking portal and every
synchronous caller's request runs on that portal's loop.

`SessionGitHubAPI._request` paces each attempt on the ledger of the session's own identity, as
`run_gh` paces `gh api <path>`, sends it with the process's current token, which a GitHub App
mints again before it expires, and charges the quota the answer reports to the resource GitHub
names. gidgethub's `handle_rate_limit_error` hook retries a rate limit, and a read GitHub failed
with a 5xx, up to `DEFAULT_GH_MAX_RETRIES` times, waiting what the ledger's `retry_delay` gives.
A write that got a 5xx may have been applied, so it is not sent again; a refused connect and a
refused origin are not retried either. Every use of the ledger runs in a worker thread, since its
lock may be held through another thread's quota refresh. What still fails is raised as the error
`github.error_classifier` names for it.

A GET is conditional (#983): gidgethub keeps each GET's answer with its ETag in the transport's
bounded LRU store, `DEFAULT_GH_SESSION_ETAG_CACHE_SIZE` answers in memory, and sends the next GET
of that URL with `If-None-Match`; a 304 gives back the stored answer. Each attempt, a 304 too, is
still paced and charged by `_request`, retried by the same hook and sent through the same origin
hook, and a stored page is still checked by `listed_items`. Every GET's answer is handed out as a
copy, so no caller changes a stored one. GitHub's ETag covers a page's body only and its 304
carries no `Link`, so a page that links no next page is read in full and not kept, leaving the
store to pages that can answer 304: a page added after a full last page leaves that page's ETag
as it was.

A transport is closed by `close()`, when it is garbage-collected, or at interpreter exit, while
the portal's thread can still run; closing cancels the requests still in flight and drops its
stored answers.
"""

from __future__ import annotations

import copy
import logging
import weakref
from collections.abc import Awaitable, Callable, Mapping
from concurrent.futures import CancelledError
from contextlib import ExitStack
from functools import partial
from typing import Any, Final
from urllib.parse import quote

import anyio
import anyio.to_thread
import httpx2
from anyio.from_thread import start_blocking_portal
from cachetools import LRUCache
from gidgethub import HTTPException, sansio
from gidgethub.httpx import GitHubAPI

from devops_cli.config.constants import (
    CONST_GH_API_SUBCOMMAND,
    CONST_GITHUB_API_VERSION,
    CONST_GITHUB_DIFF_MEDIA_TYPE,
    CONST_GITHUB_HEADER_API_VERSION,
    CONST_GITHUB_HEADER_RATE_LIMIT_RESOURCE,
    CONST_GITHUB_USER_AGENT,
    CONST_MAX_ERROR_DETAIL_LENGTH,
    CONST_URI_TEMPLATE_EXPRESSION_DELIMITERS,
    CONST_URL_GITHUB_API_BASE,
)
from devops_cli.config.defaults import (
    DEFAULT_GH_MAX_RETRIES,
    DEFAULT_GH_SERVER_ERROR_RETRY_FLOOR_SECONDS,
    DEFAULT_GH_SESSION_CONNECT_TIMEOUT_SECONDS,
    DEFAULT_GH_SESSION_ETAG_CACHE_SIZE,
)
from devops_cli.core.process import github_token
from devops_cli.exceptions.base import DevOpsCLIError
from devops_cli.exceptions.git import GitHubRateLimitError, GitHubUnreadError
from devops_cli.github.error_classifier import (
    classify_http_error,
    is_rate_limited,
    is_server_error,
    refused_retry,
    retry_after_seconds,
    unlisted_page,
    unread_after_close,
)
from devops_cli.github.rate_limiter import (
    gh_request_is_paced,
    gh_request_resource,
    identity_rate_limiter,
)
from devops_cli.github.request_classifier import GitHubRequest, is_write_request
from devops_cli.http.client import ClientOptions, new_async_http_client, request_timeout
from devops_cli.http.egress import EgressLevel

logger = logging.getLogger(__name__)

_API_ORIGIN: Final[httpx2.Origin] = httpx2.URL(CONST_URL_GITHUB_API_BASE).origin

# What leaves a request without an answer to read: no connection or no complete response
# (httpx2), and an answer that does not decode (ValueError, LookupError; see the classifier).
_UNREAD: Final = (httpx2.HTTPError, ValueError, LookupError)

# A path's template delimiters, percent-encoded, so gidgethub's expansion keeps them as text.
_LITERAL_PATH: Final = str.maketrans(
    {c: quote(c) for c in CONST_URI_TEMPLATE_EXPRESSION_DELIMITERS}
)

# What gidgethub stores for a GET it may send again conditionally: the answer's ETag, its
# Last-Modified, its decoded body, and the `rel="next"` link it carried.
type StoredAnswer = tuple[str | None, str | None, Any, str | None]


def _origin_text(origin: httpx2.Origin) -> str:
    """An origin as `scheme://host:port`."""
    return f"{origin.scheme}://{origin.host}:{origin.port}"


async def refuse_other_origins(request: httpx2.Request) -> None:
    """Refuse a request, or a redirect hop, to any origin but GitHub's API's, before it is sent.

    httpx2 compares origins as scheme, lower-cased host and effective port, so another host,
    another port, userinfo naming GitHub and a scheme downgrade are all another origin.
    """
    origin = request.url.origin
    if origin == _API_ORIGIN:
        return
    raise GitHubUnreadError(
        f"The GitHub session sends requests only to {_origin_text(_API_ORIGIN)} and refused one "
        f"to {_origin_text(origin)}",
        details={
            "origin": _origin_text(origin)[:CONST_MAX_ERROR_DETAIL_LENGTH],
            "path": request.url.path[:CONST_MAX_ERROR_DETAIL_LENGTH],
        },
    )


def session_client() -> httpx2.AsyncClient:
    """The session's client from the egress factory at the public level, following redirects
    under the origin hook and pinning the REST API version. It connects within
    `DEFAULT_GH_SESSION_CONNECT_TIMEOUT_SECONDS`, a public-internet bound, and keeps the
    factory's read timeout; a connect that still fails is not retried."""
    options: ClientOptions = {
        "follow_redirects": True,
        "headers": {CONST_GITHUB_HEADER_API_VERSION: CONST_GITHUB_API_VERSION},
        "event_hooks": {"request": [refuse_other_origins]},
    }
    timeout = request_timeout(connect=DEFAULT_GH_SESSION_CONNECT_TIMEOUT_SECONDS)
    return new_async_http_client(level=EgressLevel.PUBLIC, timeout=timeout, **options)


def _gh_api_command(url: str) -> list[str]:
    """The `gh api` command that sends what a request to `url` sends, as `run_gh` classifies it."""
    return [CONST_GH_API_SUBCOMMAND, httpx2.URL(url).path]


def pace_request(method: str, url: str, identity: str) -> str:
    """Wait for the request's turn on the ledger of the identity `identity` names, as `run_gh`
    waits for `gh api <path>`, a write as a write; return the rate-limit resource it spends."""
    command = _gh_api_command(url)
    resource = gh_request_resource(command)
    if gh_request_is_paced(command):
        is_mutation = is_write_request(GitHubRequest(method, command[1]))
        identity_rate_limiter(identity).acquire(subcommand=resource, is_mutation=is_mutation)
    return resource


def charge_response(headers: Mapping[str, str], resource: str, identity: str) -> None:
    """Record the quota an answer reports on the ledger of the identity `identity` names, for the
    resource GitHub names or else the one the request was paced on."""
    quota = sansio.RateLimit.from_http(headers)
    if quota is None:
        return
    identity_rate_limiter(identity).update_quota(
        headers.get(CONST_GITHUB_HEADER_RATE_LIMIT_RESOURCE) or resource,
        remaining=quota.remaining,
        limit=quota.limit,
        reset_epoch=quota.reset_datetime.timestamp(),
    )


def _is_retried(error: HTTPException, method: str, path: str) -> bool:
    """A rate limit is retried whatever the method, since GitHub did not act on it; a 5xx only
    for a read, since GitHub may have applied a write it failed to answer."""
    if is_rate_limited(error):
        return True
    return is_server_error(error) and not is_write_request(GitHubRequest(method, path))


def retry_wait(
    error: HTTPException, *, method: str, url: str, attempt: int, identity: str
) -> float | None:
    """The wait before sending a failed request again, recorded as a throttle on the identity's
    ledger, or None when it is not sent again. A 5xx waits from a shorter floor than a rate limit.
    Raises GitHubRateLimitError, naming the request, for a wait past `max_rate_limit_wait`."""
    command = _gh_api_command(url)
    if not _is_retried(error, method, command[1]):
        return None
    floor = None if is_rate_limited(error) else DEFAULT_GH_SERVER_ERROR_RETRY_FLOOR_SECONDS
    limiter = identity_rate_limiter(identity)
    try:
        wait = limiter.retry_delay(
            retry_after_seconds(error),
            attempt=attempt,
            subcommand=gh_request_resource(command),
            floor=floor,
        )
    except GitHubRateLimitError as refusal:
        raise refused_retry(refusal, error, method=method, path=command[1]) from refusal
    limiter.record_throttle(wait)
    return wait


class SessionGitHubAPI(GitHubAPI):
    """gidgethub's httpx2 adapter, paced, charged and retried on its identity's ledger, and sent
    with the process's current token."""

    def __init__(self, client: httpx2.AsyncClient, identity: str) -> None:
        self._stored: LRUCache[str, StoredAnswer] = LRUCache(
            maxsize=DEFAULT_GH_SESSION_ETAG_CACHE_SIZE
        )
        super().__init__(
            client,
            CONST_GITHUB_USER_AGENT,
            cache=self._stored,
            base_url=CONST_URL_GITHUB_API_BASE,
        )
        self._identity = identity

    def _pace(self, method: str, url: str) -> tuple[str, str]:
        """Wait for the attempt's turn on the ledger, then read the token to send it with: a
        GitHub App's token is minted again when it nears its expiry during the wait."""
        return pace_request(method, url, self._identity), github_token()

    async def _request(
        self, method: str, url: str, headers: Mapping[str, str], body: bytes = b""
    ) -> tuple[int, Mapping[str, str], bytes]:
        """Send one attempt once the ledger allows it, with the current token, and charge what
        its answer reports.

        The pacing wait may run until the quota resets, so a close does not wait it out.
        """
        resource, token = await anyio.to_thread.run_sync(
            self._pace, method, url, abandon_on_cancel=True
        )
        sent = {**headers, "authorization": f"token {token}"}
        answer = await super()._request(method, url, sent, body)
        self._last_body_empty = (answer[2] == b"") and bool(answer[1].get("content-type"))
        await anyio.to_thread.run_sync(charge_response, answer[1], resource, self._identity)
        return answer

    async def sleep(self, seconds: float) -> None:
        """Wait on the portal's loop, so other requests keep running."""
        await anyio.sleep(seconds)

    async def handle_rate_limit_error(
        self, *, method: str, url: str, exception: HTTPException, attempt: int
    ) -> bool:
        """Wait and retry a rate limit, or a read's 5xx, up to `DEFAULT_GH_MAX_RETRIES` times."""
        if attempt > DEFAULT_GH_MAX_RETRIES:
            return False
        wait = await anyio.to_thread.run_sync(
            partial(
                retry_wait,
                exception,
                method=method,
                url=url,
                attempt=attempt,
                identity=self._identity,
            )
        )
        if wait is None:
            return False
        logger.warning(
            "[RateLimit] GitHub answered %s %s with HTTP %d on attempt %d; retrying in %.2fs",
            method,
            httpx2.URL(url).path,
            exception.status_code,
            attempt,
            wait,
        )
        await self.sleep(wait)
        return True

    async def send(self, method: str, path: str, *, accept: str | None, body: Any) -> Any:
        """One REST request's decoded answer: JSON as Python values, any other body as text."""
        answer, _ = await self._exchange(method, path, path, accept=accept, body=body)
        return answer

    async def page(
        self, endpoint: str, url: str, *, number: int, iterable_key: str | None
    ) -> tuple[list[Any], str | None]:
        """Page `number` of the listing at `endpoint`, read from `url`: its items, and the URL of
        the next page, which an empty page or one without `rel="next"` has none of. A page that
        links no next page is read in full and not kept: an answer a `rest` GET stored for its
        URL is dropped before the read, and the page's own after it."""
        self._forget_last_page(url)
        answer, more = await self._exchange("GET", endpoint, url, page=number)
        self._forget_last_page(url)
        items = listed_items(answer, path=endpoint, page=number, iterable_key=iterable_key)
        return items, (more if items else None)

    async def _exchange(
        self,
        method: str,
        path: str,
        url: str,
        *,
        accept: str | None = None,
        body: Any = None,
        page: int | None = None,
    ) -> tuple[Any, str | None]:
        """One request to `url`, on behalf of `path` (and its `page`): the decoded answer and the
        `rel="next"` link GitHub sent with it, or the error the classifier names. A GET's answer
        is a copy of the one stored for its next conditional request."""
        try:
            answer, more, _ = await self._make_request(
                method,
                url.translate(_LITERAL_PATH),
                None,
                b"" if body is None else body,
                accept or sansio.accept_format(),
            )
            if (
                answer is None
                and getattr(self, "_last_body_empty", False)
                and accept == CONST_GITHUB_DIFF_MEDIA_TYPE
            ):
                answer = ""
        except DevOpsCLIError:
            raise
        except (HTTPException, *_UNREAD) as error:
            raise classify_http_error(error, method=method, path=path, page=page) from error
        return (copy.deepcopy(answer) if method == "GET" else answer), more

    def _forget_last_page(self, url: str) -> None:
        """Drop the answer stored for `url` when it linked no next page, as a last page does.
        GitHub's ETag covers a page's body only and its 304 carries no `Link`, so that page's 304
        could not show a next page added since."""
        filled_url = sansio.format_url(url.translate(_LITERAL_PATH), None, base_url=self.base_url)
        match self._stored.get(filled_url):
            case (_, _, _, None):
                del self._stored[filled_url]


def listed_items(answer: Any, *, path: str, page: int, iterable_key: str | None) -> list[Any]:
    """The items on one page of a listing: the page itself when it is a JSON array, or the array
    it holds under `iterable_key` (`check_runs`, `workflow_runs`, `items`). Anything else, such
    as an HTML page, an error object or a missing body, raises `GitHubUnreadError`, so a string's
    characters or an object's keys are never read as items (#1034)."""
    if iterable_key is None:
        items = answer
    else:
        items = answer.get(iterable_key) if isinstance(answer, dict) else None
    if not isinstance(items, list):
        raise unlisted_page(answer, path=path, page=page, iterable_key=iterable_key)
    return items


class RestTransport:
    """One identity's REST transport: an anyio portal, the client on its loop and gidgethub.

    It is closed once: by `close()`, when it is garbage-collected, or at interpreter exit, while
    the portal's daemon thread still runs. Left to the shutdown of the portal's own context, the
    interpreter would wait forever on a thread that no longer runs.
    """

    def __init__(self, identity: str) -> None:
        with ExitStack() as resources:
            portal = resources.enter_context(start_blocking_portal())
            resources.callback(portal.call, portal.stop, True)
            client = session_client()
            resources.callback(portal.call, client.aclose)
            self._portal = portal
            self._api = SessionGitHubAPI(client, identity)
            self._close = weakref.finalize(self, resources.pop_all().close)

    def send(self, method: str, path: str, *, accept: str | None = None, body: Any = None) -> Any:
        """Send one request on the portal's loop and wait for its decoded answer.

        A request the transport's close stopped raises `GitHubUnreadError`.
        """
        return self._call(
            method, path, partial(self._api.send, method, path, accept=accept, body=body)
        )

    def page(
        self, endpoint: str, url: str, *, number: int, iterable_key: str | None = None
    ) -> tuple[list[Any], str | None]:
        """Read one page of the listing at `endpoint` on the portal's loop: its items and the
        next page's URL, or None after the last page."""
        read = partial(self._api.page, endpoint, url, number=number, iterable_key=iterable_key)
        result: tuple[list[Any], str | None] = self._call("GET", endpoint, read)
        return result

    def _call(self, method: str, path: str, request: Callable[[], Awaitable[Any]]) -> Any:
        """Run `request` on the portal's loop and wait for it; a request the transport's close
        stopped raises `GitHubUnreadError`."""
        try:
            return self._portal.call(request)
        except DevOpsCLIError:
            raise
        except (RuntimeError, CancelledError) as error:
            if self._close.alive:
                raise
            raise unread_after_close(method=method, path=path) from error

    def close(self) -> None:
        """Close the client on the portal's loop, cancel what is still in flight, and stop the
        loop and its thread."""
        self._close()
