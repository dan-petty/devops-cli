"""The one HTTP path every Vault request takes.

Vault is internal infrastructure, so requests go through the shared broker's private-level client,
which the `devops_cli.http.client` factory builds: it dials every address but cloud metadata,
checked at the connect for each redirect hop. Each request also carries a same-origin egress
policy, which the broker's request hook applies to every redirect hop: a hop to any origin but the
configured Vault address's is refused before it is sent. httpx2 strips only `Authorization` on a
cross-origin redirect, so without the policy `X-Vault-Token`, and on a 307 or 308 a login body,
would follow a redirect to another host.
"""

from __future__ import annotations

from collections.abc import Callable
from functools import partial
from typing import Any

import httpx2

from devops_cli.config.constants import (
    CONST_HTTP_EGRESS_POLICY_EXTENSION,
    CONST_VAULT_API_PREFIX,
)
from devops_cli.config.defaults import DEFAULT_VAULT_REQUEST_TIMEOUT_SECONDS
from devops_cli.exceptions.vault import VaultOperationError, VaultUnreachableError


def _origin_text(origin: httpx2.Origin) -> str:
    """Render an origin as the URL a user would set `VAULT_ADDR` to."""
    return str(httpx2.URL(scheme=origin.scheme, host=origin.host, port=origin.port))


def _refuse_other_origin(url: str, *, origin: httpx2.Origin) -> None:
    """Refuse a request hop whose origin is not the configured Vault address's."""
    target = httpx2.URL(url).origin
    if target == origin:
        return
    target_text = _origin_text(target)
    raise VaultOperationError(
        f"Vault at {_origin_text(origin)} redirected the request to {target_text}, which is not "
        "the configured Vault address, so nothing was sent there. If that is the active Vault "
        "node, set VAULT_ADDR to it or to a load balancer in front of it.",
        details={"target_origin": target_text[:256]},
    )


def same_origin_policy(vault_addr: str) -> Callable[[str], None]:
    """Return the egress policy holding every hop to the origin of `vault_addr`."""
    return partial(_refuse_other_origin, origin=httpx2.URL(vault_addr).origin)


def vault_url(vault_addr: str, path: str) -> str:
    """Build the Vault HTTP API URL for `path`."""
    return f"{vault_addr.rstrip('/')}{CONST_VAULT_API_PREFIX}/{path.lstrip('/')}"


def vault_request(
    method: str,
    vault_addr: str,
    path: str,
    *,
    headers: dict[str, str],
    payload: dict[str, Any] | None = None,
    timeout: float = DEFAULT_VAULT_REQUEST_TIMEOUT_SECONDS,
) -> httpx2.Response:
    """Send one Vault API request, every hop held to the origin of `vault_addr`.

    Raises `VaultUnreachableError` when no reply came back, and `VaultOperationError` when a
    redirect leaves the Vault origin or cannot be followed. The caller judges the status.
    """
    from devops_cli.http import broker as http_broker
    from devops_cli.http.egress import EgressLevel

    url = vault_url(vault_addr, path)
    try:
        return http_broker.get_broker().request(
            method,
            url,
            level=EgressLevel.PRIVATE,
            headers=headers,
            json=payload,
            timeout=timeout,
            extensions={CONST_HTTP_EGRESS_POLICY_EXTENSION: same_origin_policy(vault_addr)},
        )
    except httpx2.TransportError as exc:
        raise VaultUnreachableError(
            f"Vault at {vault_addr} did not answer: {type(exc).__name__}",
            details={"path": path[:256]},
        ) from exc
    except httpx2.HTTPError as exc:
        raise VaultOperationError(
            f"Vault request to '{path}' failed: {type(exc).__name__}",
            details={"path": path[:256]},
        ) from exc


__all__ = ["same_origin_policy", "vault_request", "vault_url"]
