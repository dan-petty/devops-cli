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
from devops_cli.core.validation import validate_url_egress
from devops_cli.k8s.service_proxy import (
    ServiceAddressError,
    is_service_url,
    parse_service_url,
    resolve_proxy_target,
)

logger = logging.getLogger(__name__)


def get_json(
    url: str,
    path: str | None = None,
    *,
    timeout: float = DEFAULT_K8S_PROXY_TIMEOUT_SECONDS,
    context: str | None = None,
    purpose: str = "cluster service",
) -> Any:
    """Fetch JSON from a plain URL or a `k8s://` Service reference."""
    import httpx2

    if is_service_url(url):
        ref = parse_service_url(url)
        target = resolve_proxy_target(ref, path, context)
        with httpx2.Client(
            timeout=timeout, headers=target.headers, verify=target.ssl_context
        ) as client:
            response = client.get(target.url)
            response.raise_for_status()
            return json.loads(response.text)

    # A direct URL is validated for egress. The endpoint is operator-configured and
    # ordinarily private, which is the case SSRF protection is not aimed at.
    full_url = f"{url.rstrip('/')}/{path.lstrip('/')}" if path else url
    validate_url_egress(full_url, purpose=purpose, allow_private=True)
    with httpx2.Client(timeout=timeout) as client:
        response = client.get(full_url)
        response.raise_for_status()
        return json.loads(response.text)


def describe_endpoint(url: str) -> str:
    """Render an endpoint for display, naming the cluster service when it is one."""
    if not is_service_url(url):
        return url
    try:
        return parse_service_url(url).describe()
    except ServiceAddressError:
        return url


__all__ = ["describe_endpoint", "get_json"]
