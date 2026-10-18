"""The process's one GitHub session: one identity that owns its token, quota and pacing (#767).

The identity is whatever `gh auth token` prints, looked up once on the first GitHub call; that
command applies GH_TOKEN, then GITHUB_TOKEN, then gh's stored login. The lookup and the pin that
gives every gh and git child that token live in `core.process`, which does not import `github/`;
the session reads its token from there. Its quota ledger and response cache are the identity's
directory under the cache dir, and PyGithub is built here, from the session's token, and nowhere
else.

`rest()` sends a REST request as the identity through gidgethub (#983, ADR 0006), paced and
charged on the same ledger as `run_gh`; `github.session_transport` holds the client, the event
loop it runs on and the retry rules, and opens them on the first request.
"""

from __future__ import annotations

import threading
from functools import cached_property
from typing import TYPE_CHECKING, Any

from devops_cli.config.constants import CONST_GH_CLI
from devops_cli.core.process import github_token, reset_github_token
from devops_cli.github.rate_limiter import resolve_identity_cache_dir, run_gh

if TYPE_CHECKING:
    from pathlib import Path

    import httpx2

    from devops_cli.github.client import GitHubClient
    from devops_cli.github.session_transport import RestTransport


class GitHubSession:
    """One GitHub identity: its token, the login behind it, its ledger directory and its client."""

    def __init__(self, token: str, *, transport: httpx2.AsyncBaseTransport | None = None) -> None:
        """`transport` replaces the factory's network transport, as a test's fake GitHub does."""
        self._token = token
        self._http_transport = transport
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
        quota GitHub reports back, and follows redirects only within GitHub's API origin. A rate
        limit, and a read that GitHub fails with a 5xx, are retried; what still fails raises the
        `GitHubOperationError` subclass `github.error_classifier` gives it.
        """
        return self._rest_transport().send(method, path, accept=accept, body=body)

    def close(self) -> None:
        """Close the session's client and stop the loop it ran on; the next `rest` opens them."""
        with self._rest_lock:
            transport, self._rest = self._rest, None
        if transport is not None:
            transport.close()

    def _rest_transport(self) -> RestTransport:
        """The session's REST transport, opened on the first request."""
        from devops_cli.github.session_transport import RestTransport

        with self._rest_lock:
            if self._rest is None:
                self._rest = RestTransport(self._token, transport=self._http_transport)
            return self._rest


_SESSION: GitHubSession | None = None
_SESSION_LOCK = threading.Lock()


def get_github_session() -> GitHubSession:
    """The session of the process's GitHub identity, raising the unauthenticated error without one."""
    global _SESSION
    token = github_token()
    with _SESSION_LOCK:
        if _SESSION is None or _SESSION.token != token:
            _SESSION = GitHubSession(token)
        return _SESSION


def reset_github_session() -> None:
    """Close and forget the session and its token, so the next GitHub call resolves the identity
    again."""
    global _SESSION
    with _SESSION_LOCK:
        session, _SESSION = _SESSION, None
    if session is not None:
        session.close()
    reset_github_token()
