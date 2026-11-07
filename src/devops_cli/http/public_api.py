"""The client and the bounded JSON read for the fixed public APIs (OSV, GitHub advisories, CISA KEV).

A fixed public API has a host that no configuration names, so its client dials public addresses
only, whatever `ai.allow_private_network` says, and names itself `devops-cli/<version>`: no contact
data goes to a third party. `read_json` follows no redirect and reads a body up to a byte cap, so a
reply that is too large or that moved is an error and never a partial answer.
"""

from __future__ import annotations

import json
from typing import Any, NamedTuple

import httpx2

from devops_cli.exceptions.security import ResponseTooLargeError
from devops_cli.http.client import user_agent
from devops_cli.http.egress import EgressLevel
from devops_cli.http.entry import http_client

__all__ = ["JsonAnswer", "public_api_client", "read_json"]


class JsonAnswer(NamedTuple):
    """The JSON body of one answer, and the URL of its next page when a `Link` header names one."""

    data: Any
    next_url: str | None


def public_api_client(timeout: float, headers: dict[str, str] | None = None) -> httpx2.Client:
    """A client for a fixed public API: it dials only public addresses, with a 1 s connect.

    `ai.allow_private_network` does not widen it: no configuration names these hosts, so a
    non-public answer for one of them is a bad DNS answer. The client follows no redirect, so
    a header that it carries (a token) reaches the host of the client only.
    """
    return http_client(
        EgressLevel.PUBLIC,
        timeout=httpx2.Timeout(timeout, connect=1.0),
        headers={"User-Agent": user_agent(), **(headers or {})},
    )


def read_json(
    client: httpx2.Client,
    method: str,
    url: str,
    *,
    source: str,
    max_bytes: int,
    payload: dict[str, Any] | None = None,
    params: dict[str, str] | None = None,
) -> JsonAnswer:
    """The JSON body of one answer of `source`.

    The client follows no redirect, so a redirect is a status that is not 200. The body is read as a
    stream and refused when it passes `max_bytes`.
    """
    with client.stream(method, url, json=payload, params=params) as res:
        if res.status_code != 200:
            raise httpx2.HTTPStatusError(
                f"{source} returned status {res.status_code}", request=res.request, response=res
            )
        too_large = ResponseTooLargeError(f"{source} answered with more than {max_bytes} bytes")
        if int(res.headers.get("content-length", "0") or 0) > max_bytes:
            raise too_large
        body = bytearray()
        for chunk in res.iter_bytes():
            body += chunk
            if len(body) > max_bytes:
                raise too_large
        next_url = res.links.get("next", {}).get("url")
    return JsonAnswer(json.loads(body), next_url)
