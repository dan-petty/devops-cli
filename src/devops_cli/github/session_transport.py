"""The GitHub session's REST transport: gidgethub over one httpx2 client in one anyio portal (#983).

gidgethub builds each request and decodes each answer; its httpx2 adapter sends them through an
`httpx2.AsyncClient` the factory builds at the public egress level. That client follows redirects
and runs one request hook, `refuse_other_origins`, before the first request and before every hop,
so the session's token goes to GitHub's API origin and nowhere else. An async client is bound to
the event loop it first runs on, so the transport owns one anyio blocking portal and every
synchronous caller's request runs on that portal's loop.

`SessionGitHubAPI._request` paces each attempt on the identity's ledger, as `run_gh` paces
`gh api <path>`, and charges the quota the answer reports to the resource GitHub names. gidgethub's
`handle_rate_limit_error` hook retries a rate limit, and a read GitHub failed with a 5xx, up to
`DEFAULT_GH_MAX_RETRIES` times, waiting what the ledger's `retry_delay` gives. A write that got a
5xx may have been applied, so it is not sent again; a refused connect and a refused origin are not
retried either. What still fails is raised as the error `github.error_classifier` names for it.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Mapping
from contextlib import ExitStack
from functools import partial
from typing import Any, Final

import anyio
import anyio.to_thread
import httpx2
from anyio.from_thread import start_blocking_portal
from gidgethub import HTTPException, sansio
from gidgethub.httpx import GitHubAPI

from devops_cli.config.constants import (
    CONST_GH_API_SUBCOMMAND,
    CONST_GITHUB_API_VERSION,
    CONST_GITHUB_HEADER_API_VERSION,
    CONST_GITHUB_HEADER_RATE_LIMIT_RESOURCE,
    CONST_GITHUB_USER_AGENT,
    CONST_MAX_ERROR_DETAIL_LENGTH,
    CONST_URL_GITHUB_API_BASE,
)
from devops_cli.config.defaults import (
    DEFAULT_GH_MAX_RETRIES,
    DEFAULT_GH_SERVER_ERROR_RETRY_FLOOR_SECONDS,
)
from devops_cli.exceptions.git import GitHubUnreadError
from devops_cli.github.error_classifier import (
    classify_http_error,
    is_rate_limited,
    is_server_error,
    retry_after_seconds,
)
from devops_cli.github.rate_limiter import (
    get_github_rate_limiter,
    gh_request_is_paced,
    gh_request_resource,
)
from devops_cli.github.request_classifier import GitHubRequest, is_write_request
from devops_cli.http.client import ClientOptions, new_async_http_client
from devops_cli.http.egress import EgressLevel

logger = logging.getLogger(__name__)

_API_ORIGIN: Final[httpx2.Origin] = httpx2.URL(CONST_URL_GITHUB_API_BASE).origin

# What leaves a request without an answer to read: no connection or no complete response, and a
# body that does not decode as the content type it claims.
_UNREAD: Final = (httpx2.HTTPError, json.JSONDecodeError, UnicodeDecodeError)


def _origin_text(origin: httpx2.Origin) -> str:
    """An origin as `scheme://host:port`."""
    return f"{origin.scheme}://{origin.host}:{origin.port}"


async def refuse_other_origins(request: httpx2.Request) -> None:
    """Refuse a request, or a redirect hop, to any origin but GitHub's API's, before it is sent.

    httpx2 compares origins as scheme, lower-cased host and effective port, so another host, a
    look-alike, userinfo naming GitHub and a scheme downgrade are all another origin.
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


def session_client(transport: httpx2.AsyncBaseTransport | None = None) -> httpx2.AsyncClient:
    """The session's client: the factory's at the public egress level, or one over `transport`,
    following redirects under the origin hook and pinning the REST API version."""
    options: ClientOptions = {
        "follow_redirects": True,
        "headers": {CONST_GITHUB_HEADER_API_VERSION: CONST_GITHUB_API_VERSION},
        "event_hooks": {"request": [refuse_other_origins]},
    }
    if transport is None:
        return new_async_http_client(level=EgressLevel.PUBLIC, **options)
    return httpx2.AsyncClient(transport=transport, **options)


def _gh_api_command(url: str) -> list[str]:
    """The `gh api` command that sends what a request to `url` sends, as `run_gh` classifies it."""
    return [CONST_GH_API_SUBCOMMAND, httpx2.URL(url).path]


def pace_request(method: str, url: str) -> str:
    """Wait for the request's turn on the identity's ledger, as `run_gh` waits for
    `gh api <path>`, a write as a write; return the rate-limit resource it spends."""
    command = _gh_api_command(url)
    resource = gh_request_resource(command)
    if gh_request_is_paced(command):
        is_mutation = is_write_request(GitHubRequest(method, command[1]))
        get_github_rate_limiter().acquire(subcommand=resource, is_mutation=is_mutation)
    return resource


def charge_response(headers: Mapping[str, str], resource: str) -> None:
    """Record the quota an answer reports, for the resource GitHub names or else the one paced."""
    quota = sansio.RateLimit.from_http(headers)
    if quota is None:
        return
    get_github_rate_limiter().update_quota(
        headers.get(CONST_GITHUB_HEADER_RATE_LIMIT_RESOURCE) or resource,
        remaining=quota.remaining,
        limit=quota.limit,
        reset_epoch=quota.reset_datetime.timestamp(),
    )


def retry_wait(error: HTTPException, *, method: str, url: str, attempt: int) -> float | None:
    """The wait before sending a failed request again, or None when it is not sent again.

    A rate limit is retried, whatever the method, since GitHub did not act on it. A 5xx is
    retried for a read only, from a shorter floor than a rate limit's.
    """
    command = _gh_api_command(url)
    resource = gh_request_resource(command)
    retry_after = retry_after_seconds(error)
    limiter = get_github_rate_limiter()
    if is_rate_limited(error):
        return limiter.retry_delay(retry_after, attempt=attempt, subcommand=resource)
    if is_server_error(error) and not is_write_request(GitHubRequest(method, command[1])):
        return limiter.retry_delay(
            retry_after,
            attempt=attempt,
            subcommand=resource,
            floor=DEFAULT_GH_SERVER_ERROR_RETRY_FLOOR_SECONDS,
        )
    return None


class SessionGitHubAPI(GitHubAPI):
    """gidgethub's httpx2 adapter, paced, charged and retried on the identity's ledger."""

    def __init__(self, client: httpx2.AsyncClient, token: str) -> None:
        super().__init__(
            client,
            CONST_GITHUB_USER_AGENT,
            oauth_token=token,
            base_url=CONST_URL_GITHUB_API_BASE,
        )

    async def _request(
        self, method: str, url: str, headers: Mapping[str, str], body: bytes = b""
    ) -> tuple[int, Mapping[str, str], bytes]:
        """Send one attempt once the ledger allows it, and charge what its answer reports."""
        resource = await anyio.to_thread.run_sync(pace_request, method, url)
        answer = await super()._request(method, url, headers, body)
        await anyio.to_thread.run_sync(charge_response, answer[1], resource)
        return answer

    async def sleep(self, seconds: float) -> None:
        """Wait on the portal's loop, so other requests keep running."""
        await anyio.sleep(seconds)

    async def handle_rate_limit_error(
        self, *, method: str, url: str, exception: HTTPException, attempt: int
    ) -> bool:
        """Wait and retry a rate limit, or a read's 5xx, up to `DEFAULT_GH_MAX_RETRIES` times."""
        wait = None
        if attempt <= DEFAULT_GH_MAX_RETRIES:
            wait = retry_wait(exception, method=method, url=url, attempt=attempt)
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
        get_github_rate_limiter().record_throttle(wait)
        await self.sleep(wait)
        return True

    async def send(self, method: str, path: str, *, accept: str | None, body: Any) -> Any:
        """One REST request's decoded answer: JSON as Python values, any other body as text."""
        try:
            answer, _, _ = await self._make_request(
                method,
                path,
                None,
                b"" if body is None else body,
                accept or sansio.accept_format(),
            )
        except (HTTPException, *_UNREAD) as error:
            raise classify_http_error(error, method=method, path=path) from error
        return answer


class RestTransport:
    """One identity's REST transport: an anyio portal, the client on its loop and gidgethub."""

    def __init__(self, token: str, *, transport: httpx2.AsyncBaseTransport | None = None) -> None:
        self._resources = ExitStack()
        self._portal = self._resources.enter_context(start_blocking_portal())
        client = session_client(transport)
        self._resources.callback(self._portal.call, client.aclose)
        self._api = SessionGitHubAPI(client, token)

    def send(self, method: str, path: str, *, accept: str | None = None, body: Any = None) -> Any:
        """Send one request on the portal's loop and wait for its decoded answer."""
        return self._portal.call(partial(self._api.send, method, path, accept=accept, body=body))

    def close(self) -> None:
        """Close the client on the portal's loop, then stop the loop and its thread."""
        self._resources.close()
