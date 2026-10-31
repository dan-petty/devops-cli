"""HTTP access to cluster services, whether addressed directly or through the API server.

Callers should not have to know whether an endpoint is a plain URL or a `k8s://` Service
reference. `get_json` accepts either and does the right thing, so a configuration value can
move between the two without touching the code that reads it.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from devops_cli.config.defaults import DEFAULT_K8S_PROXY_TIMEOUT_SECONDS
from devops_cli.http.egress import EgressLevel
from devops_cli.http.pool import get_shared_client
from devops_cli.k8s.service_proxy import (
    ServiceAddressError,
    is_service_url,
    parse_service_url,
    resolve_proxy_target,
)

logger = logging.getLogger(__name__)


def transport_key(url: str) -> str:
    """Identify the transport a URL uses: scheme, host and port.

    The path is deliberately excluded. Every path on one host shares a connection, so
    keying on it would create a client per endpoint and reinstate the churn.
    """
    import httpx2

    origin = httpx2.URL(url).origin
    return str(httpx2.URL(scheme=origin.scheme, host=origin.host, port=origin.port))


def get_json(
    url: str,
    path: str | None = None,
    *,
    timeout: float = DEFAULT_K8S_PROXY_TIMEOUT_SECONDS,
    context: str | None = None,
) -> Any:
    """Fetch JSON from a plain URL or a `k8s://` Service reference."""
    from devops_cli.http.urls import append_path
    from devops_cli.k8s.service_proxy import _has_dot_segments

    if path is not None and _has_dot_segments(path):
        raise ServiceAddressError(f"Path '{path}' contains dot segments.")

    if is_service_url(url):
        ref = parse_service_url(url)
        target = resolve_proxy_target(ref, path, context)
        # Keyed on the API server and its TLS material, which is what a connection can be
        # shared across. Headers carry the credential and are passed per request, so two
        # callers of the same cluster reuse one connection instead of renegotiating TLS.
        client = get_shared_client(
            f"k8s-proxy:{transport_key(target.url)}",
            EgressLevel.PRIVATE,
            verify=target.ssl_context,
        )
        response = client.get(target.url, headers=target.headers, timeout=timeout)
        response.raise_for_status()
        return json.loads(response.text)

    # The endpoint is operator-configured and ordinarily private, which is the case SSRF
    # protection is not aimed at. The connect resolves the host once and refuses a cloud
    # metadata address, as it does for the API server proxy above.
    full_url = str(append_path(url, path)) if path else url
    client = get_shared_client(f"direct:{transport_key(full_url)}", EgressLevel.PRIVATE)
    response = client.get(full_url, timeout=timeout)
    response.raise_for_status()
    return json.loads(response.text)


def _is_dial_failure(status_code: int, body: str) -> bool:
    """Report whether an answer is the API server's own Status for a backend it could not dial.

    The API server answers 503 with a `Status` of reason `ServiceUnavailable` when no endpoint
    of the Service answers its dial. An answer of any other form comes from the Service.
    """
    if status_code != 503:
        return False
    try:
        status = json.loads(body)
    except ValueError:
        return False
    return (
        isinstance(status, dict)
        and status.get("kind") == "Status"
        and status.get("reason") == "ServiceUnavailable"
    )


def reaches_service(
    url: str,
    *,
    timeout: float = DEFAULT_K8S_PROXY_TIMEOUT_SECONDS,
    context: str | None = None,
) -> bool:
    """Report whether the API server reaches the Service that a `k8s://` address names.

    The API server dials the Service's endpoints itself. A NetworkPolicy that admits only pods
    refuses that dial for an endpoint on another node than the API server, so an address can
    resolve and still never answer. One GET of the Service's root path tells the two apart: any
    answer from the Service, a redirect or an error included, means that the address works.
    """
    ref = parse_service_url(url)
    target = resolve_proxy_target(ref, "/", context)
    client = get_shared_client(
        f"k8s-proxy:{transport_key(target.url)}",
        EgressLevel.PRIVATE,
        verify=target.ssl_context,
    )
    # A redirect is an answer from the Service; following it could leave the API server.
    response = client.get(
        target.url, headers=target.headers, timeout=timeout, follow_redirects=False
    )
    return not _is_dial_failure(response.status_code, response.text)


def describe_endpoint(url: str) -> str:
    """Render an endpoint for display, naming the cluster service when it is one."""
    if not is_service_url(url):
        return url
    try:
        return parse_service_url(url).describe()
    except ServiceAddressError:
        return url


__all__ = ["describe_endpoint", "get_json", "reaches_service", "transport_key"]
