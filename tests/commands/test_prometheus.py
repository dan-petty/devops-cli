"""Unit tests for Prometheus CLI commands (devops_cli.commands.prometheus).

The commands run through the `cli` fixture. The `web` fixture answers the Prometheus API below the
HTTP entry point, so the tests read the requests that the fake received and patch no name.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

import httpx2
import pytest

from tests.support.fakes.dial import record_connects
from tests.support.fakes.dns import PUBLIC_ADDRESS, DnsFake
from tests.support.fakes.http import WebFake

PROMETHEUS_ENV = {"DEVOPS_CLI_PROMETHEUS_URL": "http://prometheus.example.com:9090"}

VECTOR = {
    "status": "success",
    "data": {
        "resultType": "vector",
        "result": [
            {
                "metric": {"__name__": "node_cpu_seconds_total", "instance": "localhost:9100"},
                "value": [1700000000, "100.5"],
            }
        ],
    },
}
MATRIX = {
    "status": "success",
    "data": {
        "resultType": "matrix",
        "result": [
            {
                "metric": {"instance": "localhost:9100"},
                "values": [[1700000000, "100.5"], [1700000060, "101.0"]],
            }
        ],
    },
}


def _serve(web: WebFake, path: str, response: httpx2.Response) -> None:
    """Answer each request to `path` with `response`."""
    web.serve(lambda request: response if request.url.path == path else None)


def test_query_prints_each_series_with_its_value(cli: Callable[..., Any], web: WebFake) -> None:
    """The instant query sends the expression and prints the series as a table."""
    _serve(web, "/api/v1/query", httpx2.Response(200, json=VECTOR))

    result = cli("prometheus", "query", "up", env=PROMETHEUS_ENV)

    assert (
        result.exit_code,
        "localhost:9100" in result.output,
        "100.5" in result.output,
        [dict(request.url.params) for request in web.sent],
    ) == (0, True, True, [{"query": "up"}])


def test_query_range_sums_the_series_and_the_points(cli: Callable[..., Any], web: WebFake) -> None:
    """The range query asks for the window and the step, and prints the series and point counts."""
    _serve(web, "/api/v1/query_range", httpx2.Response(200, json=MATRIX))

    result = cli(
        "prometheus", "query-range", "up", "--start", "30m", "--step", "30s", env=PROMETHEUS_ENV
    )

    [params] = [dict(request.url.params) for request in web.sent]
    assert (result.exit_code, "1 series, 2 total data points" in result.output, params["step"]) == (
        0,
        True,
        "30s",
    )
    assert float(params["end"]) - float(params["start"]) == pytest.approx(1800, abs=5)


def test_targets_prints_the_scrape_targets(cli: Callable[..., Any], web: WebFake) -> None:
    """The targets command prints each active target with its job and state."""
    targets = {
        "data": {
            "activeTargets": [
                {
                    "health": "up",
                    "labels": {"job": "node-exporter", "instance": "localhost:9100"},
                    "lastScrape": "2026-08-26T00:00:00Z",
                }
            ]
        }
    }
    _serve(web, "/api/v1/targets", httpx2.Response(200, json=targets))

    result = cli("prometheus", "targets", env=PROMETHEUS_ENV)

    assert (result.exit_code, "node-exporter" in result.output) == (0, True)


def test_rules_prints_each_rule_with_its_health(cli: Callable[..., Any], web: WebFake) -> None:
    """The rules command prints the group, the name and the health of each rule."""
    rules = {
        "data": {
            "groups": [
                {
                    "name": "node-alerts",
                    "rules": [{"name": "HighCPU", "type": "alerting", "health": "ok"}],
                }
            ]
        }
    }
    _serve(web, "/api/v1/rules", httpx2.Response(200, json=rules))

    result = cli("prometheus", "rules", env=PROMETHEUS_ENV)

    assert (result.exit_code, "HighCPU" in result.output, "node-alerts" in result.output) == (
        0,
        True,
        True,
    )


def test_a_query_with_no_series_says_there_are_no_results(
    cli: Callable[..., Any], web: WebFake
) -> None:
    """An empty vector is not a failure."""
    empty = {"status": "success", "data": {"resultType": "vector", "result": []}}
    _serve(web, "/api/v1/query", httpx2.Response(200, json=empty))

    result = cli("prometheus", "query", "empty_metric", env=PROMETHEUS_ENV)

    assert (result.exit_code, "No results." in result.output) == (0, True)


def test_a_server_error_status_in_the_answer_ends_the_query_with_its_message(
    cli: Callable[..., Any], web: WebFake
) -> None:
    """A `status: error` body ends the query with exit 1 and names the error."""
    failed = {"status": "error", "error": "parse error at char 5"}
    _serve(web, "/api/v1/query", httpx2.Response(200, json=failed))

    result = cli("prometheus", "query", "up", env=PROMETHEUS_ENV)

    assert (result.exit_code, "parse error at char 5" in result.output) == (1, True)


def test_a_missing_url_ends_the_query_before_a_request(
    cli: Callable[..., Any], web: WebFake
) -> None:
    """With no `prometheus.url` the command names the setting, exits 1, and sends nothing."""
    result = cli("prometheus", "query", "up", env={"DEVOPS_CLI_PROMETHEUS_URL": ""})

    assert (result.exit_code, "Prometheus URL not configured" in result.output, web.recorded) == (
        1,
        True,
        [],
    )


def test_an_expression_over_the_limit_is_refused_before_a_request(
    cli: Callable[..., Any], web: WebFake
) -> None:
    """An expression of 5000 characters exits 1 with the limit, and sends nothing."""
    result = cli("prometheus", "query", "a" * 5000, env=PROMETHEUS_ENV)

    assert (result.exit_code, "maximum length" in result.output, web.recorded) == (1, True, [])


def test_an_answer_that_is_not_json_ends_the_query_with_its_content_type(
    cli: Callable[..., Any], web: WebFake
) -> None:
    """A server that sends a web page ends the query with exit 1 and the content type it sent."""
    _serve(web, "/api/v1/query", httpx2.Response(200, html="<html></html>"))

    result = cli("prometheus", "query", "up", env=PROMETHEUS_ENV)

    assert (result.exit_code, "text/html" in result.output) == (1, True)


def test_a_duration_over_a_year_is_a_usage_error(cli: Callable[..., Any], web: WebFake) -> None:
    """`--start 400d` is refused as a bad parameter before any request."""
    result = cli("prometheus", "query-range", "up", "--start", "400d", env=PROMETHEUS_ENV)

    assert (result.exit_code, "365 days" in result.output, web.recorded) == (2, True, [])


def test_a_global_dry_run_plans_the_query_and_sends_nothing(
    cli: Callable[..., Any], web: WebFake
) -> None:
    """With `--dry-run` the command prints the plan of the request and makes none."""
    result = cli("--dry-run", "prometheus", "query", "node_cpu_seconds_total", env=PROMETHEUS_ENV)

    assert (result.exit_code, web.recorded) == (0, [])


def test_cli_rejects_malformed_promql_before_any_request(
    cli: Callable[..., Any], web: WebFake
) -> None:
    """An invalid query fails locally, with no request issued to the Prometheus API.

    Catching the typo here is the whole point: the round trip is avoided and the error
    names the offending character rather than relaying the server's phrasing.
    """
    result = cli("prometheus", "query", "rate(x[5m", env=PROMETHEUS_ENV)

    assert (result.exit_code, "Invalid PromQL" in result.output, web.recorded) == (1, True, [])


def test_cli_analyze_reports_anomalies(cli: Callable[..., Any], web: WebFake) -> None:
    """The analyze command summarises a series and surfaces its outliers."""
    payload = {
        "status": "success",
        "data": {
            "result": [
                {
                    "metric": {"job": "api"},
                    "values": [[1000 + i, "10"] for i in range(20)] + [[1020, "500"]],
                }
            ]
        },
    }
    _serve(web, "/api/v1/query_range", httpx2.Response(200, json=payload))

    result = cli("prometheus", "analyze", "up", "--json", env=PROMETHEUS_ENV)

    assert result.exit_code == 0
    analysis = json.loads(result.output)
    assert (analysis["sample_count"], len(analysis["anomalies"])) == (21, 1)


def test_cli_analyze_handles_an_empty_result(cli: Callable[..., Any], web: WebFake) -> None:
    """A query matching no series reports so rather than failing."""
    empty = {"status": "success", "data": {"result": []}}
    _serve(web, "/api/v1/query_range", httpx2.Response(200, json=empty))

    result = cli("prometheus", "analyze", "up", env=PROMETHEUS_ENV)

    assert (result.exit_code, "no series to analyze" in result.output) == (0, True)


def test_cli_analyze_supports_dry_run(cli: Callable[..., Any], web: WebFake) -> None:
    """Analysis can be previewed without contacting the server."""
    result = cli("prometheus", "analyze", "up", env={"DEVOPS_CLI_DRY_RUN": "true"})

    assert (result.exit_code, "query_range" in result.output, web.recorded) == (0, True, [])


def test_a_k8s_address_in_the_prometheus_url_stops_the_query_before_a_lookup(
    cli: Callable[..., Any], monkeypatch: pytest.MonkeyPatch, dns: DnsFake
) -> None:
    """Old vs new (#2424): the error names the setting, and the URL check makes no lookup.

    `devops k8s configure-urls --addressing proxy` writes a `k8s://` address, which this command
    cannot dial. The command reads the scheme of the URL and stops before any lookup or dial.
    """
    dns.script("monitoring", [PUBLIC_ADDRESS])
    recorder = record_connects(monkeypatch, [])

    result = cli(
        "prometheus",
        "query",
        "up",
        env={"DEVOPS_CLI_PROMETHEUS_URL": "k8s://monitoring/prometheus-server:9090"},
    )

    assert (
        result.exit_code,
        "prometheus.url" in result.output,
        len(dns.lookups_of("monitoring")),
        recorder.dialled,
    ) == (1, True, 0, [])


def test_a_refused_prometheus_address_ends_the_query_with_the_refusal(
    cli: Callable[..., Any], monkeypatch: pytest.MonkeyPatch, dns: DnsFake
) -> None:
    """The connect refuses a private answer without the flag, and the command prints why (#2424).

    The command exits with the status of `SSRFBlockedError` (`SSRF_BLOCKED`, docs/ERRORS.md).
    """
    dns.script("example.com", ["192.0.2.10"])
    recorder = record_connects(monkeypatch, [])

    result = cli(
        "prometheus",
        "query",
        "up",
        env={
            "DEVOPS_CLI_PROMETHEUS_URL": "http://example.com:9090",
            "DEVOPS_CLI_AI_ALLOW_PRIVATE_NETWORK": "false",
        },
    )

    assert (
        result.exit_code,
        type(result.exception),
        "the loopback egress level refuses" in result.output,
        recorder.dialled,
    ) == (2, SystemExit, True, [])
