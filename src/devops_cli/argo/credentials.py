"""Argo CD server and authentication token resolution (#1343)."""

from __future__ import annotations

import urllib.parse
from typing import TYPE_CHECKING

if TYPE_CHECKING:
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
