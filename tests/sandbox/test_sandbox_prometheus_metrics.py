"""The Prometheus exposition a sandbox serves: parsing, scraping and the scrape target."""

from __future__ import annotations

from typing import Any

import pytest

from devops_cli.sandbox.metrics import (
    collect_sandbox_metrics,
    parse_prometheus_exposition,
    scrape_prometheus_metrics,
)
from devops_cli.sandbox.models import (
    PrometheusMetric,
)
from tests.support.fakes.dial import http_response, record_connects
from tests.support.fakes.dns import PUBLIC_ADDRESS, DnsFake
from tests.support.sandbox import (
    SAMPLE_PROMETHEUS_TEXT,
)


def _scraped_request(recorder: Any) -> tuple[str, str]:
    """The request line and the Host header of the scrape the recorder saw."""
    request = next(bytes(w) for w in recorder.written if bytes(w).startswith(b"GET "))
    return request.split(b"\r\n", 1)[0].decode(), recorder.requested_hosts[-1]


@pytest.mark.parametrize(
    ("target", "endpoint", "dialled", "request_line", "host"),
    [
        (
            "httpbin.example.com:8080",
            "metrics",
            (PUBLIC_ADDRESS, 8080),
            "GET /metrics HTTP/1.1",
            "httpbin.example.com:8080",
        ),
        (
            "HTTP://example.com",
            "metrics",
            (PUBLIC_ADDRESS, 80),
            "GET /metrics HTTP/1.1",
            "example.com",
        ),
        (
            "http://example.com:9100/prefix",
            "metrics",
            (PUBLIC_ADDRESS, 9100),
            "GET /prefix/metrics HTTP/1.1",
            "example.com:9100",
        ),
        (
            "http://example.com:9100/prefix",
            "/metrics",
            (PUBLIC_ADDRESS, 9100),
            "GET /prefix/metrics HTTP/1.1",
            "example.com:9100",
        ),
    ],
)
def test_a_metrics_target_is_scraped_at_its_host_port_and_path(
    monkeypatch: pytest.MonkeyPatch,
    target: str,
    endpoint: str,
    dialled: tuple[str, int],
    request_line: str,
    host: str,
    dns: DnsFake,
) -> None:
    """A target is scraped over http at its own host and port, below its path prefix."""
    dns.script("httpbin.example.com", [PUBLIC_ADDRESS])
    dns.script("example.com", [PUBLIC_ADDRESS])
    recorder = record_connects(monkeypatch, [http_response(200, "up 1\n")])

    snapshot = collect_sandbox_metrics(target, prom_endpoint=endpoint, timeout=1.0)

    assert (
        snapshot.scrape_error,
        [dial for dial in recorder.dialled if dial[0] == PUBLIC_ADDRESS],
        _scraped_request(recorder),
    ) == (None, [dialled], (request_line, host))


def test_a_metrics_target_with_a_scheme_other_than_http_is_refused() -> None:
    """Only http and https targets are scraped."""
    with pytest.raises(ValueError, match="scheme"):
        collect_sandbox_metrics("ftp://example.com")


def test_an_ipv6_metrics_target_is_scraped_at_its_bracketed_address(refusing_port: int) -> None:
    """An IPv6 target keeps its brackets and its port in the scrape URL."""
    snapshot = collect_sandbox_metrics(f"[::1]:{refusing_port}", timeout=0.5)

    assert f"http://[::1]:{refusing_port}/metrics" in (snapshot.scrape_error or "")


def test_prometheus_metric_model() -> None:
    """Test PrometheusMetric model parsing and validation."""
    metric = PrometheusMetric(
        name="http_requests_total",
        metric_type="counter",
        labels={"method": "GET", "status": "200"},
        value=1542.0,
    )
    assert metric.name == "http_requests_total"
    assert metric.labels["method"] == "GET"
    assert metric.value == 1542.0


def test_parse_prometheus_exposition() -> None:
    """Test parsing Prometheus text exposition format into structured models."""
    metrics = parse_prometheus_exposition(SAMPLE_PROMETHEUS_TEXT)
    assert len(metrics) >= 6

    # Verify counter with labels
    http_200 = next(
        (
            m
            for m in metrics
            if m.name == "http_requests_total"
            and m.labels.get("code") == "200"
            and m.labels.get("method") == "post"
        ),
        None,
    )
    assert http_200 is not None
    assert http_200.value == 1027.0
    assert http_200.metric_type == "counter"

    # Verify gauge
    mem_gauge = next((m for m in metrics if m.name == "process_resident_memory_bytes"), None)
    assert mem_gauge is not None
    assert mem_gauge.value == 67108864.0
    assert mem_gauge.metric_type == "gauge"


def test_scrape_prometheus_metrics_success(prom_server: str) -> None:
    """Test scraping Prometheus endpoint over HTTP."""
    url = f"{prom_server}/metrics"
    metrics = scrape_prometheus_metrics(url, timeout=2.0)
    assert len(metrics) >= 6
    names = {m.name for m in metrics}
    assert "http_requests_total" in names
    assert "process_resident_memory_bytes" in names


def test_scrape_prometheus_metrics_server_error(prom_server: str) -> None:
    """Test scraping Prometheus endpoint returning HTTP 500."""
    url = f"{prom_server}/error"
    metrics = scrape_prometheus_metrics(url, timeout=2.0)
    assert metrics == []


def test_scrape_prometheus_metrics_unreachable(refusing_port: int) -> None:
    """Test scraping unreachable Prometheus endpoint gracefully returns empty list."""
    metrics = scrape_prometheus_metrics(f"http://127.0.0.1:{refusing_port}/metrics", timeout=0.2)
    assert metrics == []


def test_scrape_prometheus_metrics_invalid_scheme() -> None:
    """Test scraping URL with non-http/https scheme is rejected."""
    metrics = scrape_prometheus_metrics("ftp://127.0.0.1:8080/metrics", timeout=1.0)
    assert metrics == []


def test_scrape_prometheus_metrics_ssrf_protection() -> None:
    """Test scrape_prometheus_metrics blocks non-permitted protocols and invalid hosts via SSRF check."""
    from devops_cli.sandbox.metrics import PrometheusScrapeResult

    # Block non-HTTP schemes
    res_ftp = scrape_prometheus_metrics("ftp://127.0.0.1:8080/metrics")
    assert isinstance(res_ftp, PrometheusScrapeResult)
    assert len(res_ftp) == 0
    assert res_ftp.error is not None
    assert "SSRF" in res_ftp.error or "scheme" in res_ftp.error

    res_file = scrape_prometheus_metrics("file:///etc/passwd")
    assert len(res_file) == 0
    assert res_file.error is not None

    # Invalid host
    res_bad_host = scrape_prometheus_metrics("http:///missing-host")
    assert len(res_bad_host) == 0
    assert res_bad_host.error is not None

    # Cloud metadata and RFC1918 private IPs are blocked
    res_metadata = scrape_prometheus_metrics("http://169.254.169.254/latest/meta-data")
    assert len(res_metadata) == 0
    assert res_metadata.error is not None
    assert "SSRF" in res_metadata.error or "private" in res_metadata.error.lower()

    res_rfc1918 = scrape_prometheus_metrics("http://10.0.0.1/metrics")
    assert len(res_rfc1918) == 0
    assert res_rfc1918.error is not None
    assert "SSRF" in res_rfc1918.error or "private" in res_rfc1918.error.lower()


def test_a_scrape_looks_up_its_host_once(monkeypatch: pytest.MonkeyPatch, dns: DnsFake) -> None:
    """A scrape resolves its host one time, at the connect, and dials the address it checked.

    No check before the request resolves the name again, so a rebinding DNS server gets no second
    question (#2431).
    """
    dns.script("example.com", [PUBLIC_ADDRESS])
    recorder = record_connects(monkeypatch, [http_response(200, "up 1\n")])

    result = scrape_prometheus_metrics("http://example.com:9100/metrics", timeout=1.0)

    assert (
        result.error,
        [metric.name for metric in result],
        len(dns.lookups_of("example.com")),
        [dial for dial in recorder.dialled if dial[0] == PUBLIC_ADDRESS],
    ) == (None, ["up"], 1, [(PUBLIC_ADDRESS, 9100)])


def test_parse_prometheus_exposition_label_unescaping() -> None:
    """Test parse_prometheus_exposition unescapes quotes, backslashes, and newlines in labels."""
    exposition = (
        'http_requests_total{path="/api/v1?q=\\"test\\"",note="line1\\nline2",bs="a\\\\b"} 42\n'
    )
    metrics = parse_prometheus_exposition(exposition)
    assert len(metrics) == 1
    m = metrics[0]
    assert m.labels["path"] == '/api/v1?q="test"'
    assert m.labels["note"] == "line1\nline2"
    assert m.labels["bs"] == "a\\b"
    assert m.value == 42.0


def test_prometheus_exposition_timestamp_preservation() -> None:
    """Test parse_prometheus_exposition preserves exposition timestamp."""
    text = "http_requests_total 42.0 1716300000000\n"
    metrics = parse_prometheus_exposition(text)
    assert len(metrics) == 1
    assert metrics[0].name == "http_requests_total"
    assert metrics[0].value == 42.0
    assert metrics[0].timestamp == "1716300000000"


def test_scrape_prometheus_metrics_sanitizes_credentials_and_errors(refusing_port: int) -> None:
    """Test scrape_prometheus_metrics masks credentials in scrape target and error message."""
    url = f"http://admin:supersecret@127.0.0.1:{refusing_port}/metrics"
    res = scrape_prometheus_metrics(url, timeout=0.5)
    assert res.error is not None
    assert "supersecret" not in res.error
    assert "admin:***@" in res.error


def test_parse_prometheus_exposition_braces_in_labels_untyped_and_non_finite() -> None:
    """`text_string_to_metric_families` parses `}` inside quoted label values, maps `unknown`
    families to `untyped`, skips `NaN`/`Inf` samples, and rejects invalid `# TYPE` tokens."""
    exposition = "\n".join(
        [
            "# TYPE http_requests_total counter",
            'http_requests_total{route="/users/{id}",note="a}b"} 12',
            "bare_untyped_metric 7",
            "nan_metric NaN",
            "inf_metric +Inf",
        ]
    )
    parsed = parse_prometheus_exposition(exposition)
    assert [(m.name, m.metric_type, m.labels, m.value) for m in parsed] == [
        ("http_requests_total", "counter", {"route": "/users/{id}", "note": "a}b"}, 12.0),
        ("bare_untyped_metric", "untyped", {}, 7.0),
    ]
    with pytest.raises(ValueError, match="Invalid metric type"):
        parse_prometheus_exposition("# TYPE up [/]\nup 1\n")
