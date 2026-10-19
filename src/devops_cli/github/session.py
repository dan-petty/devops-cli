"""The process's one GitHub session: one identity that owns its token, quota and pacing (#767).

The identity is whatever `gh auth token` prints, looked up once on the first GitHub call; that
command applies GH_TOKEN, then GITHUB_TOKEN, then gh's stored login. The lookup and the pin that
gives every gh and git child that token live in `core.process`, which does not import `github/`;
the session reads its token from there. Its quota ledger and response cache are the identity's
directory under the cache dir, and PyGithub is built here, from the session's token, and nowhere
else.

`rest()` sends a REST request as the identity through gidgethub (#983, ADR 0006), paced and
charged on the same ledger as `run_gh`, and `paginate()` reads a REST listing page by page; a GET
is conditional on the ETag of the session's last answer for its URL. `github.session_transport`
holds the client, the event loop it runs on, the retry rules and those answers, in memory, and
opens them on the first request.
"""

from __future__ import annotations

import threading
from functools import cached_property
from typing import TYPE_CHECKING, Any

from devops_cli.config.constants import CONST_GH_CLI
from devops_cli.config.defaults import DEFAULT_GH_MAX_PAGINATED_PAGES
from devops_cli.core.process import github_token, reset_github_token
from devops_cli.github.error_classifier import listing_past_page_cap
from devops_cli.github.rate_limiter import resolve_identity_cache_dir, run_gh

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

    from devops_cli.github.client import GitHubClient
    from devops_cli.github.session_transport import RestTransport


class GitHubSession:
    """One GitHub identity: its token, the login behind it, its ledger directory and its client."""

    def __init__(self, token: str) -> None:
        self._token = token
        self._rest: RestTransport | None = None
        self._rest_lock = threading.Lock()

    def __repr__(self) -> str:
        return f"{type(self).__name__}(cache_dir={self.cache_dir.name!r})"

    @property
    def token(self) -> str:
        """The token every GitHub call of this process is made with."""
        return self._token

    @property
    def cache_dir(self) -> Path:
        """The identity's directory, which holds its quota ledger and response cache."""
        return resolve_identity_cache_dir(self._token)

    @cached_property
    def login(self) -> str:
        """The account the token belongs to, from `GET /user` the first time it is read."""
        proc = run_gh([CONST_GH_CLI, "api", "user", "--jq", ".login"], check=True, quiet=True)
        return proc.stdout.strip()

    @cached_property
    def client(self) -> GitHubClient:
        """PyGithub with the session's token, until #891 removes it."""
        from devops_cli.github.client import GitHubClient

        return GitHubClient(self._token)

    def rest(self, method: str, path: str, *, accept: str | None = None, body: Any = None) -> Any:
        """Send one request to GitHub's REST API as the session's identity; return its answer.

        JSON comes back as Python values and any other body as text, as `accept` asks for; `body`
        is sent as JSON. The request waits its turn on the identity's ledger, which takes the
        quota GitHub reports back, and follows redirects only within GitHub's API origin. A GET is
        sent with `If-None-Match` when the session holds an answer for its URL, and a 304 gives
        that answer back, as a copy. A rate limit, and a read that GitHub fails with a 5xx, are
        retried; what still fails raises the `GitHubOperationError` subclass
        `github.error_classifier` gives it.
        """
        return self._rest_transport().send(method, path, accept=accept, body=body)

    def paginate(self, path: str, *, iterable_key: str | None = None) -> Iterator[Any]:
        """Every item of the REST listing at `path`, one page read at a time as they are asked for.

        A page is a JSON array, or an object holding the array under `iterable_key` (such as
        `check_runs`, `workflow_runs` or `items`); its items come out as one flat sequence. Pages
        follow GitHub's `Link: rel="next"`, by page number or by cursor, within GitHub's API
        origin only; an empty page or one without a next link ends the listing. A consumer that
        stops early sends no further request. A page that holds no list of items raises
        `GitHubUnreadError` naming `path` and the page, and a failed page raises what `rest`
        would, so a listing never ends short without saying so (#1034). A listing still linking
        a next page after `DEFAULT_GH_MAX_PAGINATED_PAGES` pages, read when the listing runs,
        raises `GitHubUnreadError` naming `path` and the cap instead of reading on. A page the
        session holds an answer for is read with `If-None-Match`, and a 304 gives back its items
        and next link; a page that links no next one is read in full and not kept, since its 304
        could not show a page added after it.
        """
        max_pages = DEFAULT_GH_MAX_PAGINATED_PAGES
        url: str | None = path
        number = 1
        while url is not None:
            if number > max_pages:
                raise listing_past_page_cap(path=path, max_pages=max_pages)
            items, url = self._rest_transport().page(
                path, url, number=number, iterable_key=iterable_key
            )
            yield from items
            number += 1

    def close(self) -> None:
        """Close the session's client, cancel its requests in flight, stop the loop they ran on
        and drop the answers it kept for conditional requests; the next `rest` opens them again.
        A transport left open is closed when it is garbage-collected or at interpreter exit."""
        with self._rest_lock:
            transport, self._rest = self._rest, None
        if transport is not None:
            transport.close()

    def _rest_transport(self) -> RestTransport:
        """The session's REST transport, opened on the first request."""
        from devops_cli.github.session_transport import RestTransport

        with self._rest_lock:
            if self._rest is None:
                self._rest = RestTransport(self._token)
            return self._rest


_SESSION: GitHubSession | None = None
_SESSION_LOCK = threading.Lock()


def get_github_session() -> GitHubSession:
    """The session of the process's GitHub identity, raising the unauthenticated error without one.

    A session the identity's change replaces is closed.
    """
    global _SESSION
    token = github_token()
    replaced = None
    with _SESSION_LOCK:
        if _SESSION is None or _SESSION.token != token:
            replaced, _SESSION = _SESSION, GitHubSession(token)
        current = _SESSION
    if replaced is not None:
        replaced.close()
    return current


def reset_github_session() -> None:
    """Close and forget the session and its token, so the next GitHub call resolves the identity
    again."""
    global _SESSION
    with _SESSION_LOCK:
        session, _SESSION = _SESSION, None
    if session is not None:
        session.close()
    reset_github_token()
