"""The Loki address of a query: the option, else the `loki.url` setting, else the default.

Issue #2651: the setting now names the address that the command, the dry-run plan and the live
log pane dial, at the private egress level.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

import httpx2
import pytest

from devops_cli.exceptions import SSRFBlockedError
from devops_cli.k8s.cluster_plans import plan_k8s_logs
from devops_cli.k8s.logql import execute_logql_query
from tests.support.fakes.dns import DnsFake
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


def _query_target(web: WebFake) -> str:
    """The URL of the one request the fake received, without its query string."""
    assert len(web.recorded) == 1
    return web.recorded[0].url.split("?")[0]


def test_execute_logql_query_dials_the_setting(config: Callable[..., Path], web: WebFake) -> None:
    """`execute_logql_query` uses `loki.url` when it gets no URL argument."""
    config(loki={"url": "http://example.com:3100"})
    _serve(web)

    result = execute_logql_query('{app="web"}')

    assert (_query_target(web), result.source) == (
        "http://example.com:3100/loki/api/v1/query_range",
        "loki",
    )


def test_the_argument_wins_over_the_setting(
    config: Callable[..., Path], web: WebFake, dns: DnsFake
) -> None:
    """An explicit `loki_url` is dialled and the setting's host is not looked up."""
    config(loki={"url": "http://example.com:3100"})
    _serve(web)

    execute_logql_query('{app="web"}', loki_url="http://192.0.2.1:3100")

    assert (_query_target(web), dns.lookups_of("example.com")) == (
        "http://192.0.2.1:3100/loki/api/v1/query_range",
        [],
    )


def test_no_option_and_no_setting_dials_localhost(web: WebFake) -> None:
    """With neither the setting nor an argument, the query goes to the default Loki."""
    _serve(web)

    execute_logql_query('{app="web"}')

    assert _query_target(web) == "http://localhost:3100/loki/api/v1/query_range"


def test_plan_k8s_logs_names_the_setting(config: Callable[..., Path]) -> None:
    """The dry-run plan names the same host as the real query."""
    config(loki={"url": "http://example.com:3100"})

    requests = plan_k8s_logs("api-pod", query='{app="web"}')

    assert [request.target.split("?")[0] for request in requests] == [
        "http://example.com:3100/loki/api/v1/query_range"
    ]


@pytest.mark.parametrize("address", ["127.0.0.1", "192.0.2.10"])
def test_the_setting_dials_a_loopback_or_private_host(
    address: str,
    config: Callable[..., Path],
    web: WebFake,
    dns: DnsFake,
) -> None:
    """A host that answers a loopback or private address is dialled, whatever the AI setting says."""
    config(loki={"url": "http://example.com:3100"}, ai={"allow_private_network": False})
    dns.add("example.com", address)
    _serve(web)

    result = execute_logql_query('{app="web"}')

    assert (_query_target(web), result.source) == (
        "http://example.com:3100/loki/api/v1/query_range",
        "loki",
    )


def test_the_setting_refuses_a_cloud_metadata_host(
    config: Callable[..., Path], web: WebFake, dns: DnsFake
) -> None:
    """A host that answers a cloud metadata address raises `SSRFBlockedError` with no dial."""
    config(loki={"url": "http://example.com:3100"})
    dns.add("example.com", "169.254.169.254")
    _serve(web)

    with pytest.raises(SSRFBlockedError) as raised:
        execute_logql_query('{app="web"}')

    assert (type(raised.value), web.sent) == (SSRFBlockedError, [])
