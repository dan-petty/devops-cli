"""Unit tests for Kubernetes LogQL stream parser, evaluator, and query engine."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from devops_cli.k8s.logql import (
    FilterOp,
    LogQLFilter,
    evaluate_log_lines,
    execute_kubectl_logql,
    execute_logql_query,
    execute_loki_query,
    extract_fields_json,
    extract_fields_logfmt,
    extract_trace_id,
    parse_logql_query,
)


def test_parse_logql_query_basic() -> None:
    """Test parsing simple stream selector and line filters."""
    query_str = '{app="frontend", namespace="default"} |= "error" != "timeout"'
    query = parse_logql_query(query_str)

    assert query.selectors == {"app": "frontend", "namespace": "default"}
    assert len(query.filters) == 2
    assert query.filters[0] == LogQLFilter(op=FilterOp.CONTAINS, pattern="error")
    assert query.filters[1] == LogQLFilter(op=FilterOp.NOT_CONTAINS, pattern="timeout")
    assert query.format_pipeline is None


def test_parse_logql_query_regex_and_pipeline() -> None:
    """Test parsing regex filters and format pipeline stages."""
    query_str = r'{component="ingress"} |~ "5\d\d" !~ "healthz" | json'
    query = parse_logql_query(query_str)

    assert query.selectors == {"component": "ingress"}
    assert len(query.filters) == 2
    assert query.filters[0] == LogQLFilter(op=FilterOp.REGEX_MATCH, pattern=r"5\d\d")
    assert query.filters[1] == LogQLFilter(op=FilterOp.NOT_REGEX_MATCH, pattern="healthz")
    assert query.format_pipeline == "json"


def test_parse_logql_query_logfmt_pipeline() -> None:
    """Test parsing logfmt pipeline stage."""
    query_str = '{app="worker"} | logfmt |= "finished"'
    query = parse_logql_query(query_str)

    assert query.selectors == {"app": "worker"}
    assert query.format_pipeline == "logfmt"
    assert len(query.filters) == 1
    assert query.filters[0] == LogQLFilter(op=FilterOp.CONTAINS, pattern="finished")


def test_parse_logql_query_empty_or_plain() -> None:
    """Test parsing plain text query or empty selector."""
    query = parse_logql_query("error")
    assert query.filters == [LogQLFilter(op=FilterOp.CONTAINS, pattern="error")]

    empty_query = parse_logql_query("{}")
    assert empty_query.selectors == {}
    assert empty_query.filters == []


def test_extract_trace_id() -> None:
    """Test extracting OpenTelemetry trace IDs from diverse log line patterns."""
    assert (
        extract_trace_id(
            "2026-09-10 INFO trace_id=4bf92f3577b34da6a3ce929d0e0e4736 request completed"
        )
        == "4bf92f3577b34da6a3ce929d0e0e4736"
    )
    assert (
        extract_trace_id(
            '{"level":"error","traceId":"0af7651916cd43dd8448eb211c80319c","msg":"failed"}'
        )
        == "0af7651916cd43dd8448eb211c80319c"
    )
    assert (
        extract_trace_id('traceID="1234567890abcdef1234567890abcdef" message="ok"')
        == "1234567890abcdef1234567890abcdef"
    )
    assert extract_trace_id("regular log line without trace") is None


def test_extract_fields_json() -> None:
    """Test structured JSON field extraction."""
    line = '{"level": "warn", "status": 404, "path": "/api/v1/missing"}'
    fields = extract_fields_json(line)
    assert fields == {"level": "warn", "status": 404, "path": "/api/v1/missing"}

    invalid_line = "not a valid json string"
    assert extract_fields_json(invalid_line) == {}


def test_extract_fields_logfmt() -> None:
    """Test logfmt key=value field extraction."""
    line = 'ts=2026-09-10 level=error caller=main.go:42 msg="connection refused" attempt=3'
    fields = extract_fields_logfmt(line)
    assert fields["level"] == "error"
    assert fields["caller"] == "main.go:42"
    assert fields["msg"] == "connection refused"
    assert fields["attempt"] == "3"


def test_evaluate_log_lines() -> None:
    """Test in-memory LogQL line evaluation with filters and pipeline extraction."""
    raw_lines = [
        '{"level": "info", "msg": "started worker", "trace_id": "4bf92f3577b34da6a3ce929d0e0e4736"}',
        '{"level": "error", "msg": "connection timeout", "trace_id": "0af7651916cd43dd8448eb211c80319c"}',
        '{"level": "error", "msg": "database deadlocked", "trace_id": "aabbccddeeff00112233445566778899"}',
        '{"level": "debug", "msg": "ping healthz"}',
    ]
    query = parse_logql_query('{app="service"} |= "error" != "timeout" | json')
    entries = evaluate_log_lines(raw_lines, query, default_labels={"app": "service"})

    assert len(entries) == 1
    entry = entries[0]
    assert "deadlocked" in entry.line
    assert entry.fields.get("level") == "error"
    assert entry.trace_id == "aabbccddeeff00112233445566778899"
    assert entry.stream_labels == {"app": "service"}


def test_execute_kubectl_logql_fallback() -> None:
    """Test fallback querying via kubectl logs when Loki is offline."""
    mock_proc = MagicMock()
    mock_proc.returncode = 0
    mock_proc.stdout = (
        "2026-09-10T10:00:00Z [INFO] service ready\n"
        "2026-09-10T10:00:01Z [ERROR] trace_id=4bf92f3577b34da6a3ce929d0e0e4736 connection failed\n"
    )

    with (
        patch("devops_cli.k8s.logql.run_subprocess", return_value=mock_proc),
        patch("devops_cli.k8s.logql._get_matching_pods", return_value=["pod-abc"]),
    ):
        query = parse_logql_query('{app="my-app"} |= "ERROR"')
        res = execute_kubectl_logql(query, namespace="default", limit=50)

        assert res.source == "k8s_fallback"
        assert len(res.entries) == 1
        assert "connection failed" in res.entries[0].line
        assert res.entries[0].trace_id == "4bf92f3577b34da6a3ce929d0e0e4736"


def test_execute_loki_query_success() -> None:
    """Test querying Loki REST API successfully."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "status": "success",
        "data": {
            "resultType": "streams",
            "result": [
                {
                    "stream": {"app": "web", "namespace": "prod"},
                    "values": [
                        [
                            "1788950400000000000",
                            "2026-09-10T10:00:00Z ERROR trace_id=11223344556677881122334455667788 fail",
                        ],
                    ],
                }
            ],
        },
    }

    with patch("httpx2.get", return_value=mock_response):
        query = parse_logql_query('{app="web"} |= "ERROR"')
        res = execute_loki_query(query, loki_url="http://localhost:3100")

        assert res.source == "loki"
        assert len(res.entries) == 1
        assert "fail" in res.entries[0].line
        assert res.entries[0].trace_id == "11223344556677881122334455667788"
        assert res.entries[0].stream_labels == {"app": "web", "namespace": "prod"}


def test_execute_logql_query_dry_run() -> None:
    """Test dry run execution returns mock log entries."""
    query = parse_logql_query('{app="test"} |= "error"')
    res = execute_logql_query(query, dry_run=True)

    assert res.source == "dry_run"
    assert len(res.entries) > 0
    assert res.entries[0].trace_id is not None


def test_execute_loki_query_ssrf_blocked() -> None:
    """Test execute_loki_query rejects invalid or disallowed schemes."""
    import pytest

    from devops_cli.exceptions.security import SSRFBlockedError

    query = parse_logql_query('{app="web"}')
    with pytest.raises(SSRFBlockedError):
        execute_loki_query(query, loki_url="ftp://malicious.host:3100")


def test_execute_loki_query_http_400_raises_domain_exception() -> None:
    """Test execute_loki_query raises KubernetesLoggingError on HTTP 400 and does not swallow it."""
    import pytest

    from devops_cli.exceptions.k8s import KubernetesLoggingError

    mock_resp = MagicMock()
    mock_resp.status_code = 400
    mock_resp.text = "parse error : syntax error"

    with patch("httpx2.get", return_value=mock_resp):
        query = parse_logql_query('{app="bad"}')
        with pytest.raises(KubernetesLoggingError) as exc_info:
            execute_loki_query(query, loki_url="http://localhost:3100")
        assert exc_info.value.status_code == 400
        assert "Invalid LogQL query" in str(exc_info.value)


def test_execute_logql_query_propagates_bad_query_error() -> None:
    """Test execute_logql_query propagates KubernetesLoggingError and does not mask with kubectl fallback."""
    import pytest

    from devops_cli.exceptions.k8s import KubernetesLoggingError

    mock_resp = MagicMock()
    mock_resp.status_code = 400
    mock_resp.text = "unsupported operation"

    with patch("httpx2.get", return_value=mock_resp):
        query = parse_logql_query('{app="bad"}')
        with pytest.raises(KubernetesLoggingError):
            execute_logql_query(query, loki_url="http://localhost:3100")


def test_parse_logql_query_invalid_regex_raises_domain_error() -> None:
    """Test malformed regular expressions in LogQL query raise KubernetesLoggingError."""
    import pytest

    from devops_cli.exceptions.k8s import KubernetesLoggingError

    with pytest.raises(KubernetesLoggingError):
        parse_logql_query(r'{app="web"} |~ "[unclosed-bracket"')


def test_execute_kubectl_logql_no_matching_pods_preserves_empty() -> None:
    """Test kubectl fallback returns empty results instead of querying unrelated pods when app selector has no matches."""
    with patch("devops_cli.k8s.logql._get_matching_pods", return_value=[]):
        query = parse_logql_query('{app="does-not-exist"}')
        res = execute_kubectl_logql(query, namespace="default")
        assert res.entries == []
        assert res.source == "k8s_fallback"


def test_mcp_k8s_logs_bounds_validation() -> None:
    """Test FastMCP tool input bound validation for limit and lines."""
    import pytest

    from devops_cli.ai.mcp.server import k8s_logs_query, k8s_logs_tail
    from devops_cli.exceptions import ValidationError

    with pytest.raises(ValidationError):
        k8s_logs_query(query='{app="web"}', limit=0)

    with pytest.raises(ValidationError):
        k8s_logs_tail(query='{app="web"}', lines=-5)
