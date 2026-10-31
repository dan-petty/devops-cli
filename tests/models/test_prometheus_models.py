"""Unit tests for Prometheus API response domain models."""

from __future__ import annotations

from devops_cli.models.prometheus import PrometheusQueryResult, PrometheusSeries


def test_prometheus_series_label_str() -> None:
    """Verify label_str filters __name__ and formats comma-separated key=value pairs."""
    series = PrometheusSeries(
        labels={"__name__": "http_requests_total", "method": "POST", "status": "200"},
        value="42",
    )
    assert series.label_str == "method=POST, status=200"


def test_prometheus_instant_response_parsing() -> None:
    """Verify parsing of instant query API responses."""
    raw_api_data = {
        "status": "success",
        "data": {
            "resultType": "vector",
            "result": [
                {
                    "metric": {"__name__": "up", "instance": "localhost:9090", "job": "prometheus"},
                    "value": [1620000000.0, "1"],
                },
                {"metric": {"service": "auth"}, "value": [1620000000.0, "5"]},
                "malformed_item",
            ],
        },
    }
    res = PrometheusQueryResult.from_instant_response(raw_api_data)
    assert res.status == "success"
    assert len(res.series) == 2
    assert res.series[0].value == "1"
    assert res.series[0].labels["instance"] == "localhost:9090"
    assert res.series[1].value == "5"


def test_prometheus_range_response_parsing() -> None:
    """Verify parsing of range query API responses."""
    raw_range_data = {
        "status": "success",
        "data": {
            "resultType": "matrix",
            "result": [
                {
                    "metric": {"instance": "node-1"},
                    "values": [
                        [1620000000.0, "10.5"],
                        [1620000060.0, "12.0"],
                        ["invalid", "val"],
                    ],
                }
            ],
        },
    }
    res = PrometheusQueryResult.from_range_response(raw_range_data)
    assert res.status == "success"
    assert len(res.series) == 1
    assert len(res.series[0].values) == 2
    assert res.series[0].values[0] == (1620000000.0, "10.5")
    assert res.series[0].values[1] == (1620000060.0, "12.0")


def test_prometheus_error_response_parsing() -> None:
    """Verify error parsing from Prometheus query responses."""
    raw_err_data = {"status": "error", "error": "parse error: unexpected identifier"}
    res = PrometheusQueryResult.from_instant_response(raw_err_data)
    assert res.status == "error"
    assert res.error == "parse error: unexpected identifier"
    assert res.series == []
