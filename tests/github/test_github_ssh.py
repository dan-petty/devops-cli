"""Unit tests for GitHub SSH and signing key registration through the GitHub session."""

from __future__ import annotations

import json

import httpx2
import pytest

from devops_cli.config.constants import CONST_EXIT_FAILURE
from devops_cli.exceptions.base import DevOpsCLIError
from devops_cli.exceptions.git import (
    GitHubNotFoundError,
    GitHubOperationError,
    GitHubScopeError,
    GitHubUnauthenticatedError,
    GitHubUnreadError,
)
from devops_cli.github.ssh import SSHRegistrationError, register_key_on_github
from tests.support.fakes.github import GitHubApiFake, github_json, next_page

_AUTH_KEYS = "/user/keys"
_SIGNING_KEYS = "/user/ssh_signing_keys"
_ENDPOINTS = [_AUTH_KEYS, _SIGNING_KEYS]
_KEY = "ssh-ed25519 AAAAC3 test@example.com"
_LISTED_KEY = {"id": 1, "key": "ssh-ed25519 AAAAC3", "title": "Title"}
_CREATED = github_json({"id": 1}, status=201)


def _validation_failed(reason: str) -> httpx2.Response:
    """GitHub's 422 for a key it won't add, with its reason."""
    error = {"resource": "PublicKey", "code": "custom", "field": "key", "message": reason}
    return github_json({"message": "Validation Failed", "errors": [error]}, status=422)


def _refused_scope(scope: str) -> httpx2.Response:
    """GitHub's 403 for a token that holds none of the scopes the endpoint accepts."""
    return github_json(
        {"message": "Forbidden"},
        status=403,
        headers={"x-oauth-scopes": "repo", "x-accepted-oauth-scopes": scope},
    )


def _sent(api: GitHubApiFake) -> list[str]:
    """Each request the fake received, as its method and path."""
    return [f"{request.method} {request.url.path}" for request in api.sent]


def _posts(endpoints: list[str]) -> list[str]:
    """The POST registration sends to each of `endpoints`."""
    return [f"POST {endpoint}" for endpoint in endpoints]


def test_a_key_is_added_as_an_auth_key_and_a_signing_key_with_the_sessions_token(
    github_api: GitHubApiFake, pin_github_session: str
) -> None:
    """Registration is one POST to each key endpoint, in that order, as the session's identity,
    and sends no GET: a key GitHub accepts needs no listing."""
    for endpoint in _ENDPOINTS:
        github_api.route("POST", endpoint, _CREATED)
    register_key_on_github(_KEY, "My Key")
    assert [
        (f"{r.method} {r.url.path}", json.loads(r.content), r.headers["authorization"])
        for r in github_api.sent
    ] == [
        (f"POST {endpoint}", {"title": "My Key", "key": _KEY}, f"token {pin_github_session}")
        for endpoint in _ENDPOINTS
    ]


def test_registration_without_a_github_login_is_a_registration_error(
    github_api: GitHubApiFake, no_github_identity: None
) -> None:
    """No identity registers no key: the registration error names `gh auth login`, its cause is
    the unauthenticated error, and nothing is sent to GitHub."""
    with pytest.raises(SSHRegistrationError, match="gh auth login") as raised:
        register_key_on_github(_KEY, "My Key")
    assert (type(raised.value.__cause__), github_api.requested) == (
        GitHubUnauthenticatedError,
        [],
    )


@pytest.mark.parametrize("endpoint", _ENDPOINTS)
@pytest.mark.parametrize(
    ("reason", "listing", "registered"),
    [
        pytest.param("key is already in use", github_json([_LISTED_KEY]), True, id="listed"),
        pytest.param(
            "key is invalid. You must supply a key in OpenSSH public key format",
            github_json([]),
            False,
            id="invalid-key",
        ),
        pytest.param("key is already in use", github_json([]), False, id="in-use-elsewhere"),
        pytest.param(
            "key is already in use",
            github_json({"message": "x"}, status=502),
            True,
            id="listing-unread",
        ),
        pytest.param(
            "key is already in use",
            github_json({"message": "Not Found"}, status=404),
            True,
            id="listing-not-found",
        ),
    ],
)
def test_a_422_counts_as_registered_only_when_the_session_lists_the_key(
    github_api: GitHubApiFake,
    endpoint: str,
    reason: str,
    listing: httpx2.Response,
    registered: bool,
) -> None:
    """GitHub answers 422 for a key it already holds, but also for one it rejects as invalid and
    one in use on another account, at either endpoint. The session lists the keys there: a
    listed key, or a listing that can't be read, is registered and registration goes on, and a
    listing read without the key is the registration error, with the 422 as its cause."""
    for other in _ENDPOINTS:
        github_api.route("POST", other, _CREATED)
    github_api.route("POST", endpoint, _validation_failed(reason))
    github_api.route("GET", endpoint, listing)
    if registered:
        register_key_on_github(_KEY, "Title")
    else:
        with pytest.raises(SSHRegistrationError, match="HTTP 422") as raised:
            register_key_on_github(_KEY, "Title")
        assert isinstance(raised.value.__cause__, GitHubOperationError)
        assert raised.value.__cause__.details["status"] == 422
    listed_at = _ENDPOINTS.index(endpoint) + 1
    # The session retries a read GitHub fails with a 5xx, so a request may repeat.
    assert list(dict.fromkeys(_sent(github_api))) == [
        *_posts(_ENDPOINTS[:listed_at]),
        f"GET {endpoint}",
        *(_posts(_ENDPOINTS[listed_at:]) if registered else []),
    ]


@pytest.mark.parametrize("endpoint", _ENDPOINTS)
def test_a_key_listed_on_a_later_page_counts_as_registered(
    github_api: GitHubApiFake, endpoint: str
) -> None:
    """The session reads every page of the listing, so a key past the first page is found."""
    for other in _ENDPOINTS:
        github_api.route("POST", other, _CREATED)
    github_api.route("POST", endpoint, _validation_failed("key is already in use"))
    github_api.route(
        "GET",
        endpoint,
        github_json([{"id": 2, "key": "ssh-rsa BBBB"}], headers=next_page(f"{endpoint}?page=2")),
    )
    github_api.route("GET", f"{endpoint}?page=2", github_json([_LISTED_KEY]))
    register_key_on_github(_KEY, "Title")
    assert [request.url.query for request in github_api.sent if request.method == "GET"] == [
        b"",
        b"page=2",
    ]


@pytest.mark.parametrize("endpoint", _ENDPOINTS)
def test_a_token_without_the_scope_is_a_registration_error_with_the_refresh_hint(
    github_api: GitHubApiFake, endpoint: str
) -> None:
    """A 403 whose accepted scopes the token holds none of is the scope error, which asks for
    the scope with `gh auth refresh`, at either endpoint, and registration stops there."""
    for other in _ENDPOINTS:
        github_api.route("POST", other, _CREATED)
    github_api.route("POST", endpoint, _refused_scope("write:ssh_signing_key"))
    with pytest.raises(SSHRegistrationError, match="gh auth refresh -s <scope>") as raised:
        register_key_on_github(_KEY, "Title")
    assert (type(raised.value.__cause__), _sent(github_api)) == (
        GitHubScopeError,
        _posts(_ENDPOINTS[: _ENDPOINTS.index(endpoint) + 1]),
    )


@pytest.mark.parametrize("endpoint", _ENDPOINTS)
def test_a_5xx_is_a_registration_error_with_the_sessions_error_as_its_cause(
    github_api: GitHubApiFake, endpoint: str
) -> None:
    """A refusal that is no 422 and no missing scope is not read as a registration: it raises the
    registration error with the class the session gave it, and no listing is read."""
    for other in _ENDPOINTS:
        github_api.route("POST", other, _CREATED)
    github_api.route("POST", endpoint, github_json({"message": "Server Error"}, status=500))
    with pytest.raises(SSHRegistrationError) as raised:
        register_key_on_github(_KEY, "Title")
    assert (type(raised.value.__cause__), {r.method for r in github_api.sent}) == (
        GitHubUnreadError,
        {"POST"},
    )


@pytest.mark.parametrize(
    ("endpoint", "scope"),
    [(_AUTH_KEYS, "admin:public_key"), (_SIGNING_KEYS, "write:ssh_signing_key")],
)
def test_a_404_at_a_key_endpoint_names_the_scopes_and_the_command_that_adds_them(
    github_api: GitHubApiFake, endpoint: str, scope: str
) -> None:
    """GitHub hides an endpoint a token's scopes cannot reach behind a 404, so at either key
    endpoint a 404 is a missing scope: the registration error names the scope of that endpoint
    and the command that adds the scopes registration needs, its cause is the scope error caused
    by the 404, and registration stops there with no listing read."""
    for other in _ENDPOINTS:
        github_api.route("POST", other, _CREATED)
    github_api.route("POST", endpoint, github_json({"message": "Not Found"}, status=404))
    with pytest.raises(SSHRegistrationError) as raised:
        register_key_on_github(_KEY, "Title")
    assert (
        scope in str(raised.value),
        "`gh auth refresh -h github.com -s admin:public_key,write:ssh_signing_key`"
        in str(raised.value),
        type(raised.value.__cause__),
        type(raised.value.__cause__.__cause__),
        _sent(github_api),
    ) == (
        True,
        True,
        GitHubScopeError,
        GitHubNotFoundError,
        _posts(_ENDPOINTS[: _ENDPOINTS.index(endpoint) + 1]),
    )


def test_a_registration_failure_is_a_github_operation_error_of_the_domain_taxonomy(
    github_api: GitHubApiFake,
) -> None:
    """The registration error is a domain error: GitHub's operation error, with its error code
    and its exit status, so a handler of GitHub failures reads it like any other."""
    github_api.route("POST", _AUTH_KEYS, github_json({"message": "Server Error"}, status=500))
    with pytest.raises(GitHubOperationError) as raised:
        register_key_on_github(_KEY, "Title")
    assert type(raised.value) is SSHRegistrationError
    assert isinstance(raised.value, DevOpsCLIError)
    assert (
        raised.value.error_code,
        raised.value.exit_code,
    ) == ("GITHUB_OPERATION_FAILED", CONST_EXIT_FAILURE)
