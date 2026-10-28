"""Unit tests for Kubernetes LogQL stream parser, evaluator, and query engine."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest

if TYPE_CHECKING:
    from tests.support.fakes.process import ProcessFake
    from tests.web_fakes import StubWeb

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


def test_execute_kubectl_logql_fallback(process_fake: ProcessFake) -> None:
    """Test fallback querying via kubectl logs when Loki is offline."""
    from tests.support.fakes.process import ProcessAnswer

    process_fake.answer(
        "kubectl logs",
        ProcessAnswer(
            returncode=0,
            stdout=(
                "2026-09-10T10:00:00Z [INFO] service ready\n"
                "2026-09-10T10:00:01Z [ERROR] trace_id=4bf92f3577b34da6a3ce929d0e0e4736 connection failed\n"
            ),
        ),
    )
    query = parse_logql_query('{app="my-app"} |= "ERROR"')
    res = execute_kubectl_logql(query, namespace="default", limit=50)

    assert res.source == "k8s_fallback"
    assert len(res.entries) == 1
    assert "connection failed" in res.entries[0].line
    assert res.entries[0].trace_id == "4bf92f3577b34da6a3ce929d0e0e4736"


def test_execute_loki_query_success(stub_web: StubWeb) -> None:
    """Test querying Loki REST API successfully."""
    import httpx2

    stub_web.serve(
        lambda req: httpx2.Response(
            200,
            json={
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
            },
        )
    )
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


def test_execute_loki_query_http_400_raises_domain_exception(stub_web: StubWeb) -> None:
    """Test execute_loki_query raises KubernetesLoggingError on HTTP 400 and does not swallow it."""
    import httpx2

    from devops_cli.exceptions.k8s import KubernetesLoggingError

    stub_web.serve(lambda req: httpx2.Response(400, text="parse error : syntax error"))
    query = parse_logql_query('{app="bad"}')
    with pytest.raises(KubernetesLoggingError) as exc_info:
        execute_loki_query(query, loki_url="http://localhost:3100")
    assert exc_info.value.status_code == 400
    assert "Invalid LogQL query" in str(exc_info.value)


def test_execute_logql_query_propagates_bad_query_error(stub_web: StubWeb) -> None:
    """Test execute_logql_query propagates KubernetesLoggingError and does not mask with kubectl fallback."""
    import httpx2

    from devops_cli.exceptions.k8s import KubernetesLoggingError

    stub_web.serve(lambda req: httpx2.Response(400, text="unsupported operation"))
    query = parse_logql_query('{app="bad"}')
    with pytest.raises(KubernetesLoggingError):
        execute_logql_query(query, loki_url="http://localhost:3100")


def test_parse_logql_query_invalid_regex_raises_domain_error() -> None:
    """Test malformed regular expressions in LogQL query raise KubernetesLoggingError."""
    import pytest

    from devops_cli.exceptions.k8s import KubernetesLoggingError

    with pytest.raises(KubernetesLoggingError):
        parse_logql_query(r'{app="web"} |~ "[unclosed-bracket"')


def test_execute_kubectl_logql_no_matching_pods_preserves_empty(process_fake: ProcessFake) -> None:
    """Test kubectl fallback returns empty results instead of querying unrelated pods when app selector has no matches."""
    from tests.support.fakes.process import ProcessAnswer

    process_fake.answer("kubectl logs", ProcessAnswer(returncode=1, stdout=""))
    query = parse_logql_query('{app="does-not-exist"}')
    res = execute_kubectl_logql(query, namespace="default")
    assert res.entries == []
    assert res.source == "k8s_fallback"


def test_mcp_k8s_logs_flag_injection_rejected() -> None:
    """Test FastMCP k8s_logs tool flag injection rejection."""
    import pytest

    from devops_cli.ai.mcp.server import k8s_logs
    from devops_cli.exceptions import ValidationError

    with pytest.raises(ValidationError):
        k8s_logs(query="--injected-flag")


def test_execute_kubectl_logql_since_parameter(process_fake: ProcessFake) -> None:
    """Test execute_kubectl_logql forwards --since to kubectl logs."""
    from tests.support.fakes.process import ProcessAnswer

    process_fake.answer(
        "kubectl logs",
        ProcessAnswer(returncode=0, stdout="2026-09-10T12:00:00Z app log line\n"),
    )
    query = parse_logql_query('{app="web"}')
    execute_kubectl_logql(query, namespace="prod", limit=20, since="45m")

    assert len(process_fake.calls) == 1
    cmd = process_fake.calls[0].argv
    assert "--since=45m" in cmd
    assert "-n" in cmd
    assert "prod" in cmd


def test_execute_logql_query_conflicting_namespace_raises_error() -> None:
    """Test execute_logql_query raises KubernetesLoggingError when query namespace conflicts with --namespace."""
    import pytest

    from devops_cli.exceptions.k8s import KubernetesLoggingError

    with pytest.raises(KubernetesLoggingError) as exc_info:
        execute_logql_query('{namespace="staging", app="web"}', namespace="production")
    assert "Conflicting namespace selector" in str(exc_info.value)


def test_execute_logql_query_fallback_passes_since(process_fake: ProcessFake) -> None:
    """Test execute_logql_query passes since duration to kubectl fallback on connection failure."""
    from tests.support.fakes.process import ProcessAnswer

    process_fake.answer(
        "kubectl logs",
        ProcessAnswer(returncode=0, stdout="2026-09-10T12:00:00Z line\n"),
    )
    with patch("devops_cli.k8s.logql.execute_loki_query", side_effect=ConnectionError("Loki down")):
        query = parse_logql_query('{app="worker", namespace="default"}')
        execute_logql_query(query, namespace="default", since="2h", limit=50)

    assert len(process_fake.calls) == 1
    cmd = process_fake.calls[0].argv
    assert "--since=2h" in cmd
    assert "--tail=50" in cmd


def test_execute_kubectl_logql_rejects_invalid_namespace_or_pod() -> None:
    """Test execute_kubectl_logql rejects argument injection in namespace or pod."""
    from devops_cli.exceptions import ValidationError

    query = parse_logql_query('{app="web"}')
    with pytest.raises(ValidationError, match="Invalid Kubernetes namespace identifier"):
        execute_kubectl_logql(query, namespace="--all-namespaces")

    bad_pod_query = parse_logql_query('{pod="--field-selector=foo"}')
    with pytest.raises(ValidationError, match="Invalid Kubernetes pod identifier"):
        execute_kubectl_logql(bad_pod_query, namespace="default")


def test_execute_loki_query_byte_for_byte_passthrough_and_since(stub_web: StubWeb) -> None:
    """The query and duration parameters recorded at the HTTP fake reach Loki unchanged."""
    import httpx2

    stub_web.serve(
        lambda req: httpx2.Response(
            200,
            json={
                "status": "success",
                "data": {"resultType": "streams", "result": []},
            },
        )
    )
    raw_query = '{app=~"api.*"} |= "error" | json | level="error"'
    parsed = parse_logql_query(raw_query)
    execute_loki_query(parsed, loki_url="http://localhost:3100", since="1h30m", limit=75)

    assert len(stub_web.sent) == 1
    req = stub_web.sent[0]
    assert req.url.params["query"] == raw_query
    assert req.url.params["since"] == "1h30m"
    assert req.url.params["limit"] == "75"
    assert req.url.params["direction"] == "BACKWARD"
    assert "start" not in req.url.params
    assert "end" not in req.url.params


def test_execute_logql_query_preserves_query_with_and_without_namespace(stub_web: StubWeb) -> None:
    """The query recorded at the HTTP fake equals the input byte for byte with and without --namespace."""
    import httpx2

    stub_web.serve(
        lambda req: httpx2.Response(
            200,
            json={
                "status": "success",
                "data": {"resultType": "streams", "result": []},
            },
        )
    )
    query_without_ns = '{app=~"api.*"} |= "error"'
    execute_logql_query(query_without_ns, loki_url="http://localhost:3100")
    assert stub_web.sent[-1].url.params["query"] == query_without_ns

    query_with_ns = '{app=~"api.*", namespace="prod"} |= "error"'
    execute_logql_query(query_with_ns, namespace="prod", loki_url="http://localhost:3100")
    assert stub_web.sent[-1].url.params["query"] == query_with_ns


def test_execute_logql_query_missing_namespace_fails_before_request(stub_web: StubWeb) -> None:
    """A missing namespace fails before any request and prints the selector to use."""
    from devops_cli.exceptions.k8s import KubernetesLoggingError

    with pytest.raises(KubernetesLoggingError) as exc_info:
        execute_logql_query(
            '{app="api"} |= "error"', namespace="prod", loki_url="http://localhost:3100"
        )

    assert len(stub_web.sent) == 0
    message = str(exc_info.value)
    assert "prod" in message
    assert '{app="api", namespace="prod"}' in message


def test_execute_kubectl_logql_fallback_supported_query(process_fake: ProcessFake) -> None:
    """In fallback mode, {app="api"} |= "error" runs kubectl logs with -l app=api."""
    from tests.support.fakes.process import ProcessAnswer

    process_fake.answer(
        "kubectl logs",
        ProcessAnswer(
            stdout="2026-09-10T10:00:00Z app log with error\n2026-09-10T10:00:01Z app log ok\n"
        ),
    )
    query = parse_logql_query('{app="api"} |= "error"')
    res = execute_kubectl_logql(query, namespace="prod", limit=50, since="30m")

    assert len(process_fake.calls) == 1
    call = process_fake.calls[0]
    cmd_str = " ".join(call.argv)
    assert "-l app=api" in cmd_str or ("-l" in call.argv and "app=api" in call.argv)
    assert "-n" in call.argv
    assert "prod" in call.argv
    assert "--since=30m" in call.argv
    assert "--tail=50" in call.argv

    assert res.source == "k8s_fallback"
    assert len(res.entries) == 1
    assert "with error" in res.entries[0].line


@pytest.mark.parametrize(
    "unsupported_query",
    [
        '{app=~"api.*"}',
        '{app!="api"}',
        '{app="api"} != "error"',
        '{app="api"} | level="error"',
        '{app="api"} | json',
        '{app="api"} | logfmt',
        r'{app="api"} |~ "5\d\d"',
        '{app="api"} !~ "healthz"',
    ],
)
def test_execute_kubectl_logql_fallback_refuses_unsupported_queries(
    unsupported_query: str,
) -> None:
    """In fallback mode, queries with regex matchers, !=, label filters, or pipelines fail with an error naming loki.url."""
    from devops_cli.exceptions.k8s import KubernetesLoggingError

    query = parse_logql_query(unsupported_query)
    with pytest.raises(KubernetesLoggingError) as exc_info:
        execute_kubectl_logql(query, namespace="default")

    assert "loki.url" in str(exc_info.value)
