"""GitHub SSH key registration: authentication + commit signing."""

from __future__ import annotations

from collections.abc import Iterable
from http import HTTPStatus
from typing import Any

from devops_cli.config.constants import (
    CONST_GITHUB_SSH_KEY_ENDPOINT_SCOPES,
    CONST_GITHUB_SSH_KEY_REFRESH_SCOPES,
)
from devops_cli.exceptions.git import (
    GitHubNotFoundError,
    GitHubOperationError,
    GitHubScopeError,
)
from devops_cli.github.session import GitHubSession, get_github_session


class SSHRegistrationError(GitHubOperationError):
    """Raised when SSH/signing key registration on GitHub fails."""


def register_key_on_github(pub_key: str, title: str) -> None:
    """Add *pub_key* to GitHub as both an auth key and a signing key, as the session's identity.

    A refusal on either endpoint is an `SSHRegistrationError`, which the `devops ssh` commands
    report, and on which `rotate` removes the key it generated (#983).
    """
    try:
        session = get_github_session()
        for endpoint, body in key_requests(pub_key, title):
            _add_key(session, endpoint, body)
    except GitHubOperationError as exc:
        raise SSHRegistrationError(str(exc)) from exc


def key_requests(pub_key: str, title: str) -> list[tuple[str, dict[str, str]]]:
    """The endpoint and the body of each `POST` that registers a key, in order: the
    authentication key, then the signing key. `register_key_on_github` sends them, and a dry
    run lists them."""
    return [
        (endpoint, {"title": title, "key": pub_key})
        for endpoint in CONST_GITHUB_SSH_KEY_ENDPOINT_SCOPES
    ]


def _key_body(key: str) -> str:
    """A key as GitHub lists it: its type and its base64, without the comment."""
    return " ".join(key.split()[:2])


def _listed_key_bodies(entries: Iterable[Any]) -> set[str]:
    """The keys a key listing holds, as `_key_body` gives each; an entry with no key is skipped."""
    return {
        _key_body(entry["key"])
        for entry in entries
        if isinstance(entry, dict) and isinstance(entry.get("key"), str)
    }


def _add_key(session: GitHubSession, endpoint: str, body: dict[str, str]) -> None:
    """Register the key at `endpoint`. GitHub answers 422 for a key it already holds, but also
    for one it rejects as invalid and one in use on another account, so a 422 counts as
    registered only when the session's listing at `endpoint` holds the key or can't be read."""
    try:
        session.rest("POST", endpoint, body=body)
    except GitHubNotFoundError as exc:
        raise _hidden_by_scope(endpoint, exc) from exc
    except GitHubOperationError as exc:
        if exc.details.get("status") != HTTPStatus.UNPROCESSABLE_ENTITY or not _session_lists_key(
            session, endpoint, body["key"]
        ):
            raise


def _hidden_by_scope(endpoint: str, refusal: GitHubNotFoundError) -> GitHubScopeError:
    """The error for a 404 at a key endpoint. The endpoint has no resource to be missing, and
    GitHub answers a token whose scopes cannot reach an endpoint with a 404, so the token lacks
    the endpoint's scope; the error names it and the command that adds the scopes registration
    needs."""
    scope = CONST_GITHUB_SSH_KEY_ENDPOINT_SCOPES[endpoint]
    return GitHubScopeError(
        f"GitHub answered POST {endpoint} with HTTP 404, which it sends a token without the scope "
        f"{scope}. Run `gh auth refresh -h github.com -s {CONST_GITHUB_SSH_KEY_REFRESH_SCOPES}` "
        "to add the scopes registering a key needs",
        details={**refusal.details, "accepted_scopes": scope},
    )


def _session_lists_key(session: GitHubSession, endpoint: str, pub_key: str) -> bool:
    """Whether the session's listing at `endpoint` holds `pub_key`; a listing that can't be read
    counts as holding it."""
    try:
        listed = _listed_key_bodies(session.paginate(endpoint))
    except GitHubOperationError:
        return True
    return _key_body(pub_key) in listed
