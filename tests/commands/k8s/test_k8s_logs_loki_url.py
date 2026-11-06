"""`devops k8s logs` and its dry-run plan use the `loki.url` setting, and the option still wins.

Issue #2651: the command dialled a localhost default that nobody configured.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import httpx2

from tests.support.fakes.http import WebFake

LOKI_ANSWER = json.dumps(
    {
        "data": {
            "result": [
                {
                    "stream": {"app": "web"},
                    "values": [["1788950400000000000", "LOG-LINE-2651 from the configured loki"]],
                }
            ]
        }
    }
)


def _serve(web: WebFake) -> None:
    web.serve(lambda _request: httpx2.Response(200, text=LOKI_ANSWER))


def test_the_command_queries_the_setting(
    config: Callable[..., Path], web: WebFake, cli: Callable[..., Any]
) -> None:
    """With no `--loki-url`, the command dials the address in `loki.url`."""
    config(loki={"url": "http://example.com:3100"})
    _serve(web)

    result = cli("k8s", "logs", '{app="web"}')

    assert (result.exit_code, [request.url.split("?")[0] for request in web.recorded]) == (
        0,
        ["http://example.com:3100/loki/api/v1/query_range"],
    )
    assert "LOG-LINE-2651 from the configured loki" in result.output


def test_the_option_wins_over_the_setting(
    config: Callable[..., Path], web: WebFake, cli: Callable[..., Any]
) -> None:
    """`--loki-url` is dialled even when `loki.url` is set."""
    config(loki={"url": "http://example.com:3100"})
    _serve(web)

    result = cli("k8s", "logs", '{app="web"}', "--loki-url", "http://192.0.2.1:3100")

    assert (result.exit_code, [request.url.split("?")[0] for request in web.recorded]) == (
        0,
        ["http://192.0.2.1:3100/loki/api/v1/query_range"],
    )


def test_the_dry_run_plan_shows_the_setting(
    config: Callable[..., Path], web: WebFake, cli: Callable[..., Any]
) -> None:
    """The dry-run plan names the configured address and the command sends no request."""
    config(loki={"url": "http://example.com:3100"})

    result = cli("k8s", "logs", '{app="web"}', "--dry-run")

    assert result.exit_code == 0
    assert "http://example.com:3100/loki/api/v1/query_range" in result.output
    assert web.sent == []


def test_the_help_names_the_setting(cli: Callable[..., Any]) -> None:
    """The help of `--loki-url` names `loki.url`."""
    result = cli("k8s", "logs", "--help")

    assert result.exit_code == 0
    assert "loki.url" in result.output
