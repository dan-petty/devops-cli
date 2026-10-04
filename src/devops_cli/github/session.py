"""The process's one GitHub session: one identity that owns its token, quota and pacing (#767).

The identity is whatever `gh auth token` prints, looked up once on the first GitHub call; that
command applies GH_TOKEN, then GITHUB_TOKEN, then gh's stored login. The lookup and the pin that
gives every gh and git child that token live in `core.process`, which does not import `github/`;
the session reads its token from there. Its quota ledger and response cache are the identity's
directory under the cache dir, and PyGithub is built here, from the session's token, and nowhere
else.
"""

from __future__ import annotations

import threading
from functools import cached_property
from typing import TYPE_CHECKING

from devops_cli.config.constants import CONST_GH_CLI
from devops_cli.core.process import github_token, reset_github_token
from devops_cli.github.rate_limiter import resolve_identity_cache_dir, run_gh

if TYPE_CHECKING:
    from pathlib import Path

    from devops_cli.github.client import GitHubClient


class GitHubSession:
    """One GitHub identity: its token, the login behind it, its ledger directory and its client."""

    def __init__(self, token: str) -> None:
        self._token = token

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
    """Forget the session and its token, so the next GitHub call resolves the identity again."""
    global _SESSION
    with _SESSION_LOCK:
        _SESSION = None
    reset_github_token()
