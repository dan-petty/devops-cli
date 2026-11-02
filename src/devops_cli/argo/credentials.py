"""Argo CD server and authentication token resolution (#1343)."""

from __future__ import annotations

import urllib.parse
from collections.abc import Callable, Mapping
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import httpx2

    from devops_cli.config.settings import Settings


def resolve_argocd_server_address(url: str) -> str:
    """Extract host:port address from Argo CD URL for the CLI --server flag."""
    parsed = urllib.parse.urlsplit(url)
    return parsed.netloc or url.split("://")[-1].rstrip("/")


def resolve_argocd_server_and_token(
    settings: Settings | None = None,
) -> tuple[str | None, str | None]:
    """Resolve Argo CD server URL and bearer token from configuration or keyring."""
    if settings is None:
        from devops_cli.config.settings import load_settings

        settings = load_settings()

    url = settings.argocd.url
    if not url:
        return None, None

    from devops_cli.config.settings import get_argocd_token
    from devops_cli.k8s.credentials import get_or_mint_argocd_token

    clean_url = url.rstrip("/")
    token = get_argocd_token(settings) or get_or_mint_argocd_token(settings)
    if token and token.startswith("*"):
        token = None
    return clean_url, token


def argocd_api_request(
    settings: Settings,
    headers: Mapping[str, str],
    send: Callable[[Mapping[str, str]], httpx2.Response],
) -> httpx2.Response:
    """Send an Argo CD API request with `send(headers)`, and replace a refused token one time.

    On HTTP 401 with `argocd.password` stored, mint a new token, which the keyring keeps as
    `argocd_token`, and send the request again with it. Only 401 tells of a session that is not
    valid; a 403 is an RBAC denial of a valid session. Raise ArgoError for each other failed
    answer. A failed mint raises its StackCredentialError with the cause.
    """
    from devops_cli.config.settings import get_argocd_password
    from devops_cli.exceptions.argo import ArgoError
    from devops_cli.http.egress import configured_level
    from devops_cli.k8s.credentials import mint_argocd_token
    from devops_cli.lang import MESSAGES

    resp = send(headers)
    if resp.status_code == 401:
        password = get_argocd_password(settings)
        if not password:
            raise ArgoError(MESSAGES.argo.token_refused_no_password.format(status=401))
        token = mint_argocd_token(
            settings.argocd.url or "", password, level=configured_level(settings.ai)
        )
        resp = send({**headers, "Authorization": f"Bearer {token}"})
        if resp.status_code == 401:
            raise ArgoError(
                MESSAGES.argo.new_token_refused.format(status=401, url=settings.argocd.url)
            )
    if not 200 <= resp.status_code < 300:
        raise ArgoError(
            MESSAGES.argo.request_failed.format(url=resp.request.url, status=resp.status_code)
        )
    return resp
