"""The names that a benchmark shows and records for a server and for a model."""

from __future__ import annotations

from devops_cli.ai.benchmark.model_spec import parse_model_spec
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


def model_label(entry: str) -> str:
    """The name of a `model[@endpoint]` entry in output and reports: `model[@host[:port]]`.

    The endpoint is a URL that can hold userinfo, so the label names it with `server_label`.
    """
    model, endpoint = parse_model_spec(entry)
    return f"{model}@{server_label(endpoint)}" if endpoint else model
