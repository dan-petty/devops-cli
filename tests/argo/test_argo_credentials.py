"""`argocd_api_request` replaces a token that Argo CD refuses, one time (#2576).

Argo CD is faked at the HTTP edge with `stub_web`, and the keyring with `keyring_store`. No test
patches a devops-cli name. Each test reads the `Authorization` header of each request, so it
can tell the stored token from the new one.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

import httpx2
import pytest

from devops_cli.argo.credentials import argocd_api_request
from devops_cli.config.settings import Settings, load_settings
from devops_cli.exceptions.argo import ArgoError
from devops_cli.exceptions.base import DevOpsCLIError
from devops_cli.exceptions.k8s import StackCredentialError
from devops_cli.http.client import new_http_client
from devops_cli.http.egress import configured_level
from tests.web_fakes import StubWeb

ARGOCD = "https://argocd.example.com"
APPLICATIONS = f"{ARGOCD}/api/v1/applications"
SESSION = f"{ARGOCD}/api/v1/session"


@pytest.fixture
def settings(config: Callable[..., Path], keyring_store: Any) -> Settings:
    """Settings for a fake Argo CD, with the stored token `stale`."""
    config(argocd={"url": ARGOCD})
    keyring_store.values["argocd_token"] = "stale"
    return load_settings()


def _argocd(
    stub_web: StubWeb, *, data: Callable[[str], int], session: int = 200
) -> list[tuple[str, str]]:
    """Serve Argo CD: `data` gives the status of a data request for its bearer token, and the
    session request answers `session` with the token `fresh`. Return the log of requests as
    (path, bearer token) pairs."""
    log: list[tuple[str, str]] = []

    def server(request: httpx2.Request) -> httpx2.Response:
        bearer = request.headers.get("Authorization", "").removeprefix("Bearer ")
        log.append((request.url.path, bearer))
        if str(request.url) == SESSION:
            return httpx2.Response(session, json={"token": "fresh"} if session == 200 else {})
        return httpx2.Response(data(bearer), json={"items": []})

    stub_web.serve(server)
    return log


def _request(settings: Settings) -> httpx2.Response:
    headers = {"Content-Type": "application/json", "Authorization": "Bearer stale"}
    with new_http_client(level=configured_level(settings.ai)) as client:
        return argocd_api_request(
            settings, headers, lambda sent: client.get(APPLICATIONS, headers=sent)
        )


def _only_fresh(bearer: str) -> int:
    return 200 if bearer == "fresh" else 401


def test_a_refused_token_is_replaced_and_the_request_is_sent_again(
    settings: Settings, stub_web: StubWeb, keyring_store: Any
) -> None:
    """With the admin password stored, a 401 mints a new token, stores it and retries once."""
    keyring_store.values["argocd_password"] = "admin-pw"
    log = _argocd(stub_web, data=_only_fresh)

    response = _request(settings)

    assert (response.status_code, log, keyring_store.values["argocd_token"]) == (
        200,
        [
            ("/api/v1/applications", "stale"),
            ("/api/v1/session", ""),
            ("/api/v1/applications", "fresh"),
        ],
        "fresh",
    )


def test_a_refused_token_with_no_password_names_the_setting_and_the_command(
    settings: Settings, stub_web: StubWeb
) -> None:
    """With no admin password, a 401 is one ArgoError that tells how to set the token."""
    log = _argocd(stub_web, data=_only_fresh)

    with pytest.raises(ArgoError) as caught:
        _request(settings)

    message = str(caught.value)
    assert ("401" in message, "argocd.token" in message, "devops k8s sync-secrets" in message) == (
        True,
        True,
        True,
    )
    assert log == [("/api/v1/applications", "stale")]


def test_a_refused_new_token_ends_the_request(
    settings: Settings, stub_web: StubWeb, keyring_store: Any
) -> None:
    """The request is sent two times at most: a 401 for the new token is an ArgoError."""
    keyring_store.values["argocd_password"] = "admin-pw"
    log = _argocd(stub_web, data=lambda _bearer: 401)

    with pytest.raises(ArgoError, match="401"):
        _request(settings)

    assert [path for path, _ in log] == [
        "/api/v1/applications",
        "/api/v1/session",
        "/api/v1/applications",
    ]


@pytest.mark.parametrize("status", [403, 500])
def test_another_error_status_ends_the_request_with_no_mint(
    settings: Settings, stub_web: StubWeb, keyring_store: Any, status: int
) -> None:
    """A 403 is an RBAC denial of a valid session, so only 401 mints a new token."""
    keyring_store.values["argocd_password"] = "admin-pw"
    log = _argocd(stub_web, data=lambda _bearer: status)

    with pytest.raises(ArgoError, match=f"HTTP {status}"):
        _request(settings)

    assert log == [("/api/v1/applications", "stale")]


def test_an_accepted_token_sends_one_request(settings: Settings, stub_web: StubWeb) -> None:
    log = _argocd(stub_web, data=lambda _bearer: 200)

    response = _request(settings)

    assert (response.status_code, log) == (200, [("/api/v1/applications", "stale")])


def test_a_refused_admin_session_ends_the_request_with_its_cause(
    settings: Settings, stub_web: StubWeb, keyring_store: Any
) -> None:
    """The error of the mint leaves the helper as it is: a DevOpsCLIError with its cause."""
    keyring_store.values["argocd_password"] = "admin-pw"
    _argocd(stub_web, data=_only_fresh, session=401)

    with pytest.raises(StackCredentialError, match="refused the admin session") as caught:
        _request(settings)

    assert isinstance(caught.value, DevOpsCLIError)
    assert keyring_store.values["argocd_token"] == "stale"


def test_argo_error_is_a_devops_cli_error() -> None:
    """The exit seam of `new_typer()` reports a DevOpsCLIError as one line, with no traceback."""
    assert issubclass(ArgoError, DevOpsCLIError)
