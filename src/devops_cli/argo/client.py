"""Where the Argo CD REST API is, how a request authenticates, and the client that sends it.

The commands, the fleet sync and the GitOps sync reach Argo CD the same way: the URL from
`argocd.url`, a bearer token from the keyring (or one minted from the admin password), and a client
that dials only what the egress level allows. `resolve_argocd_endpoint` does the first two once and
`ArgoCDEndpoint.client` does the third, so no caller repeats the steps. It raises
`ConfigurationError`; a command prints it and exits.
"""

from __future__ import annotations

from dataclasses import dataclass

import httpx2

from devops_cli.argo.credentials import resolve_argocd_server_and_token
from devops_cli.config.settings import Settings
from devops_cli.exceptions.config import ConfigurationError
from devops_cli.http.egress import EgressLevel, configured_level
from devops_cli.http.entry import http_client
from devops_cli.http.urls import service_base_url
from devops_cli.lang import MESSAGES


@dataclass(frozen=True)
class ArgoCDEndpoint:
    """The base URL of Argo CD, the headers of a request to it, and the level a client dials at."""

    base_url: str
    headers: dict[str, str]
    level: EgressLevel

    def client(self) -> httpx2.Client:
        """Build a client for the caller to close. It checks each address at the connect."""
        return http_client(self.level)


def resolve_argocd_endpoint(settings: Settings) -> ArgoCDEndpoint:
    """Read `argocd.url` and the token of `settings`.

    The URL check reads only the URL, and it runs before the token is read, so a mint is never
    tried for an address the client cannot dial. A token that is masked is no token. A failed mint
    raises its own error with the cause. A missing or unusable URL raises `ConfigurationError`
    that names the setting.
    """
    if not settings.argocd.url:
        raise ConfigurationError(MESSAGES.argo.url_not_configured, key="argocd.url")
    base_url = service_base_url(settings.argocd.url, "argocd.url")
    _, token = resolve_argocd_server_and_token(settings)
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return ArgoCDEndpoint(base_url, headers, configured_level(settings.ai))
