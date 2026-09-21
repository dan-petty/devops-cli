"""Unit tests for PromQL structural validation and client-side metric analysis."""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from devops_cli.commands.prometheus import app as prometheus_app
from devops_cli.models.prometheus import TrendDirection
from devops_cli.prometheus.analysis import (
    analyze_series,
    detect_anomalies,
    ewma,
    extract_series_values,
    forecast,
)
from devops_cli.prometheus.promql import validate_promql

runner = CliRunner()


# ─────────────────────────────────────────────────────────────────────────────
# 1. Valid PromQL must never be rejected
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "expression",
    [
        "up",
        "rate(http_requests_total[5m])",
        'sum by (job) (rate(http_requests_total{code=~"5.."}[5m]))',
        "avg_over_time(cpu_usage[1h:5m])",
        "histogram_quantile(0.99, sum(rate(latency_bucket[5m])) by (le))",
        'node_memory_bytes{instance="host:9100"} / 1024 / 1024',
        "increase(errors_total[1h30m])",
        "rate(x[500ms])",
        "topk(5, sum(rate(requests[5m])) by (path))",
        # A regex containing brackets inside a string literal: the structural checker
        # must not mistake them for grouping delimiters.
        '{__name__=~"node_[a-z]+_total"}',
        'label_replace(up, "host", "$1", "instance", "(.*):.*")',
        "(1 - avg(rate(idle[5m]))) * 100",
        "predict_linear(disk_free[6h], 4 * 3600)",
        "up offset 1w",
        "count(up == 0)",
    ],
)
def test_valid_expressions_are_never_rejected(expression: str) -> None:
    """A false rejection blocks work the server would have served.

    That is strictly worse than forwarding a malformed query the server would reject
    anyway, so this is the property that matters most for a client-side validator.
    """
    result = validate_promql(expression)
    assert result.valid is True, f"{expression!r} rejected: {result.summary}"
    assert bool(result) is True


# ─────────────────────────────────────────────────────────────────────────────
# 2. Malformed PromQL is caught before dispatch
# ─────────────────────────────────────────────────────────────────────────────


def test_unclosed_bracket_is_reported_with_position() -> None:
    """An unbalanced delimiter names the character and where it opened."""
    result = validate_promql("rate(http_requests_total[5m]")
    assert result.valid is False
    assert "Unclosed '('" in result.summary


def test_unmatched_closing_bracket_is_reported() -> None:
    """A stray closing delimiter is caught even when everything else balances."""
    result = validate_promql("sum(rate(x[5m]))]")
    assert (result.valid, "Unmatched closing" in result.summary) == (False, True)


def test_mismatched_bracket_types_are_reported() -> None:
    """Delimiters must nest correctly, not merely balance in count."""
    result = validate_promql("sum(rate(x[5m)])")
    assert result.valid is False
    assert "Mismatched" in result.summary


def test_unterminated_string_is_reported() -> None:
    """An unclosed literal is caught rather than swallowing the rest of the query."""
    result = validate_promql('up{job="api}')
    assert (result.valid, "Unterminated string" in result.summary) == (False, True)


def test_invalid_duration_literal_is_reported() -> None:
    """A malformed range duration is caught before the server sees it."""
    result = validate_promql("rate(x[5 m])")
    assert result.valid is False
    assert "Invalid duration" in result.summary


def test_empty_range_selector_is_reported() -> None:
    """An empty selector cannot express a range."""
    assert validate_promql("rate(x[])").valid is False


def test_empty_expression_is_reported() -> None:
    """A blank query is rejected rather than dispatched."""
    assert (validate_promql("").valid, validate_promql("   ").valid) == (False, False)


def test_duration_checks_are_suppressed_while_brackets_are_broken() -> None:
    """Structural errors are reported first, without confusing derived diagnostics.

    Reporting a duration error computed from a mis-parsed selector would point at the
    wrong character and send the reader chasing the wrong problem.
    """
    result = validate_promql("rate(x[5m")
    assert result.valid is False
    assert all("duration" not in error.lower() for error in result.errors)


def test_escaped_quote_does_not_terminate_a_literal() -> None:
    """A backslash-escaped quote stays inside the string."""
    assert validate_promql(r'up{msg="say \"hi\""}').valid is True


# ─────────────────────────────────────────────────────────────────────────────
# 3. Anomaly detection
# ─────────────────────────────────────────────────────────────────────────────


def test_outlier_is_detected_with_direction() -> None:
    """A sample far from the mean is flagged, with the side it deviates toward."""
    values = [10.0] * 20 + [500.0]
    anomalies = detect_anomalies(values, threshold=3.0)

    assert len(anomalies) == 1
    assert (anomalies[0].index, anomalies[0].direction) == (20, "above")
    assert anomalies[0].z_score > 3.0


def test_stable_series_reports_no_anomalies() -> None:
    """Ordinary variation is not an anomaly."""
    values = [10.0, 10.5, 9.8, 10.2, 9.9, 10.1, 10.3, 9.7, 10.0, 10.4]
    assert detect_anomalies(values) == []


def test_flat_series_has_no_outliers() -> None:
    """A zero-variance series divides by no standard deviation and flags nothing."""
    assert detect_anomalies([5.0] * 20) == []


def test_short_series_is_not_analysed() -> None:
    """Too few samples cannot establish a baseline, so nothing is reported.

    Flagging an "anomaly" against three points would be noise presented as signal.
    """
    assert detect_anomalies([1.0, 100.0, 1.0]) == []


def test_anomaly_carries_its_timestamp() -> None:
    """Detected anomalies report when they occurred, not just where in the array."""
    values = [1.0] * 20 + [99.0]
    stamps = [1000.0 + index for index in range(21)]
    anomalies = detect_anomalies(values, stamps, threshold=3.0)
    assert anomalies[0].timestamp == 1020.0


# ─────────────────────────────────────────────────────────────────────────────
# 4. Smoothing, slope, and forecasting
# ─────────────────────────────────────────────────────────────────────────────


def test_ewma_starts_at_the_first_sample_and_tracks_upward() -> None:
    """Smoothing anchors on the first value then follows the series."""
    smoothed = ewma([10.0, 20.0, 30.0], alpha=0.5)
    assert smoothed[0] == 10.0
    assert smoothed[1] == 15.0
    assert smoothed[2] == 22.5


def test_ewma_of_empty_series_is_empty() -> None:
    """No samples produce no smoothed line."""
    assert ewma([]) == []


def test_forecast_extends_a_rising_series_upward() -> None:
    """A projection of a rising series continues to rise."""
    projected = forecast([1.0, 2.0, 3.0, 4.0, 5.0], horizon=3)
    assert len(projected) == 3
    assert projected[0] < projected[1] < projected[2]


def test_forecast_respects_a_zero_horizon() -> None:
    """Asking for no projection returns none."""
    assert forecast([1.0, 2.0], horizon=0) == []


def test_trend_classification_scales_with_series_magnitude() -> None:
    """A slope is judged relative to the metric's own scale.

    A metric measured in bytes must not be called "rising" for a slope that would be
    negligible at its magnitude but dramatic for a ratio.
    """
    rising = analyze_series([1.0, 2.0, 3.0, 4.0, 5.0])
    falling = analyze_series([5.0, 4.0, 3.0, 2.0, 1.0])
    flat = analyze_series([1_000_000.0, 1_000_001.0, 1_000_000.0, 1_000_001.0])

    assert (rising.trend, falling.trend, flat.trend) == (
        TrendDirection.RISING,
        TrendDirection.FALLING,
        TrendDirection.FLAT,
    )


# ─────────────────────────────────────────────────────────────────────────────
# 5. Series analysis
# ─────────────────────────────────────────────────────────────────────────────


def test_analysis_summarises_the_distribution() -> None:
    """Analysis reports the series' shape alongside its trend."""
    analysis = analyze_series([1.0, 2.0, 3.0, 4.0, 5.0])

    assert (
        analysis.sample_count,
        analysis.minimum,
        analysis.maximum,
        analysis.mean,
        analysis.median,
        analysis.latest,
    ) == (5, 1.0, 5.0, 3.0, 3.0, 5.0)


def test_analysis_of_empty_series_is_empty_not_an_error() -> None:
    """An empty series analyses to zero samples rather than raising."""
    analysis = analyze_series([])
    assert (analysis.sample_count, analysis.has_anomalies) == (0, False)


def test_analysis_of_single_sample_has_no_deviation() -> None:
    """One sample has no spread to report."""
    analysis = analyze_series([42.0])
    assert (analysis.stdev, analysis.latest, analysis.sample_count) == (0.0, 42.0, 1)


# ─────────────────────────────────────────────────────────────────────────────
# 6. Prometheus payload extraction
# ─────────────────────────────────────────────────────────────────────────────


def test_range_samples_are_extracted_as_numbers() -> None:
    """Prometheus encodes values as strings; they are parsed to floats."""
    stamps, values = extract_series_values(
        {"values": [[1000, "1.5"], [1001, "2.5"], [1002, "3.5"]]}
    )
    assert (stamps, values) == ([1000.0, 1001.0, 1002.0], [1.5, 2.5, 3.5])


def test_unparseable_and_nan_samples_are_skipped() -> None:
    """A gap is skipped rather than coerced, so it never masquerades as zero."""
    stamps, values = extract_series_values(
        {"values": [[1000, "1.5"], [1001, "NaN"], [1002, "bogus"], [1003], [1004, "2.5"]]}
    )
    assert (stamps, values) == ([1000.0, 1004.0], [1.5, 2.5])


def test_malformed_payload_yields_no_samples() -> None:
    """A payload without a values array extracts nothing rather than raising."""
    assert extract_series_values({}) == ([], [])
    assert extract_series_values({"values": "not-a-list"}) == ([], [])


# ─────────────────────────────────────────────────────────────────────────────
# 7. CLI integration
# ─────────────────────────────────────────────────────────────────────────────


def _settings_with_url() -> Any:
    """Build settings pointing at a documentation Prometheus endpoint."""
    settings = MagicMock()
    settings.prometheus.url = "http://example.com:9090"
    return settings


def test_cli_rejects_malformed_promql_before_any_request() -> None:
    """An invalid query fails locally, with no request issued to the Prometheus API.

    Catching the typo here is the whole point: the round trip is avoided and the error
    names the offending character rather than relaying the server's phrasing.
    """
    with patch("devops_cli.commands.prometheus.httpx2.Client") as client_cls:
        result = runner.invoke(prometheus_app, ["query", "rate(x[5m"])

    assert result.exit_code == 1
    assert "Invalid PromQL" in result.output
    assert client_cls.return_value.__enter__.return_value.get.called is False


def test_cli_analyze_reports_anomalies(monkeypatch: pytest.MonkeyPatch) -> None:
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
    response = MagicMock()
    response.status_code = 200
    response.headers = {"content-type": "application/json"}
    response.json.return_value = payload

    monkeypatch.setattr(
        "devops_cli.commands.prometheus.load_settings", lambda: _settings_with_url()
    )
    with patch("devops_cli.commands.prometheus.httpx2.Client") as client_cls:
        client_cls.return_value.__enter__.return_value.get.return_value = response
        result = runner.invoke(prometheus_app, ["analyze", "up", "--json"])

    assert result.exit_code == 0
    analysis = json.loads(result.output)
    assert (analysis["sample_count"], len(analysis["anomalies"])) == (21, 1)


def test_cli_analyze_handles_an_empty_result(monkeypatch: pytest.MonkeyPatch) -> None:
    """A query matching no series reports so rather than failing."""
    response = MagicMock()
    response.status_code = 200
    response.headers = {"content-type": "application/json"}
    response.json.return_value = {"status": "success", "data": {"result": []}}

    monkeypatch.setattr(
        "devops_cli.commands.prometheus.load_settings", lambda: _settings_with_url()
    )
    with patch("devops_cli.commands.prometheus.httpx2.Client") as client_cls:
        client_cls.return_value.__enter__.return_value.get.return_value = response
        result = runner.invoke(prometheus_app, ["analyze", "up"])

    assert result.exit_code == 0
    assert "no series to analyze" in result.output


def test_cli_analyze_supports_dry_run() -> None:
    """Analysis can be previewed without contacting the server."""
    result = runner.invoke(prometheus_app, ["analyze", "up"], env={"DEVOPS_CLI_DRY_RUN": "true"})
    assert result.exit_code == 0
    assert "analyze_metric_series" in result.output
