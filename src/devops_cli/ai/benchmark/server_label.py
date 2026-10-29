"""The name that a benchmark shows and records for a server."""

from __future__ import annotations

from devops_cli.ai.client.models import origin_label
from devops_cli.config.constants import CONST_AI_BACKEND_HOST_UNKNOWN
from devops_cli.http.urls import get_url_origin


def server_label(url: str) -> str:
    """The `host[:port]` text of a server URL, as the AI client names the server of a reply.

    The URL can hold userinfo, which the client sends as Basic authentication. The label never
    holds it. A URL with no httpx2 origin shows as `unknown`, never as its own text.
    """
    origin = get_url_origin(url)
    return origin_label(origin) if origin is not None else CONST_AI_BACKEND_HOST_UNKNOWN
