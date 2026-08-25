"""Unit tests for OpenTelemetry tracer and metrics emitter."""

from __future__ import annotations

import pytest

from devops_cli.telemetry.tracer import (
    OTelTelemetryClient,
    get_tracer,
    record_metric,
    trace_span,
)


def test_telemetry_disabled() -> None:
    client = OTelTelemetryClient(enabled=False)
    with client.span("test_span") as span_id:
        assert span_id == ""
    # Should not raise
    client.record_metric("test_metric", 1.0)


def test_telemetry_span_and_metric(monkeypatch: pytest.MonkeyPatch) -> None:
    sent_payloads: list[tuple[str, dict]] = []

    client = OTelTelemetryClient(endpoint="http://localhost:4318", enabled=True)
    monkeypatch.setattr(client, "_send_payload", lambda path, p: sent_payloads.append((path, p)))

    with client.span("pipeline_stage", {"persona": "devsecops"}) as span_id:
        assert len(span_id) == 16  # 8 bytes hex = 16 hex chars
        client.record_metric("findings_count", 3, unit="1", attributes={"severity": "HIGH"})

    assert len(sent_payloads) == 2
    # First was metric
    assert sent_payloads[0][0] == "/v1/metrics"
    assert (
        sent_payloads[0][1]["resourceMetrics"][0]["scopeMetrics"][0]["metrics"][0]["name"]
        == "findings_count"
    )

    # Second was trace span
    assert sent_payloads[1][0] == "/v1/traces"
    span_data = sent_payloads[1][1]["resourceSpans"][0]["scopeSpans"][0]["spans"][0]
    assert span_data["name"] == "pipeline_stage"
    assert span_data["status"]["code"] == "STATUS_CODE_OK"


def test_telemetry_span_error_recording(monkeypatch: pytest.MonkeyPatch) -> None:
    sent_payloads: list[tuple[str, dict]] = []

    client = OTelTelemetryClient(endpoint="http://localhost:4318", enabled=True)
    monkeypatch.setattr(client, "_send_payload", lambda path, p: sent_payloads.append((path, p)))

    with pytest.raises(ValueError, match="simulated failure"):
        with client.span("failing_span"):
            raise ValueError("simulated failure")

    assert len(sent_payloads) == 1
    span_data = sent_payloads[0][1]["resourceSpans"][0]["scopeSpans"][0]["spans"][0]
    assert span_data["status"]["code"] == "STATUS_CODE_ERROR"
    assert span_data["status"]["message"] == "simulated failure"


def test_global_trace_helpers(monkeypatch: pytest.MonkeyPatch) -> None:
    tracer = get_tracer()
    sent_payloads: list[tuple[str, dict]] = []
    monkeypatch.setattr(tracer, "_send_payload", lambda path, p: sent_payloads.append((path, p)))

    with trace_span("helper_span", {"env": "test"}):
        record_metric("helper_metric", 42.0)

    assert len(sent_payloads) == 2


def test_inject_and_extract_trace_context() -> None:
    client = OTelTelemetryClient(enabled=True)
    headers = client.inject_trace_context({"existing": "header"})
    assert "existing" in headers
    assert "traceparent" in headers
    assert headers["traceparent"].startswith("00-")

    trace_id, span_id = client.extract_trace_context(headers)
    assert trace_id is not None
    assert span_id is not None
    assert len(trace_id) == 32
    assert len(span_id) == 16


def test_traced_decorator(monkeypatch: pytest.MonkeyPatch) -> None:
    from devops_cli.telemetry.tracer import traced

    client = get_tracer()
    sent_payloads: list[tuple[str, dict]] = []
    monkeypatch.setattr(client, "_send_payload", lambda path, p: sent_payloads.append((path, p)))

    @traced(name="decorated_func", attributes={"module": "test"})
    def my_function(x: int) -> int:
        return x * 2

    res = my_function(5)
    assert res == 10
    span_name = sent_payloads[0][1]["resourceSpans"][0]["scopeSpans"][0]["spans"][0]["name"]
    assert span_name == "decorated_func"


def test_test_connection_mock(monkeypatch: pytest.MonkeyPatch) -> None:
    from unittest.mock import MagicMock

    client = OTelTelemetryClient(enabled=True)
    mock_post = MagicMock(return_value=MagicMock(status_code=200, text="OK"))
    monkeypatch.setattr("httpx2.Client.post", mock_post)

    ok, msg, latency = client.test_connection(timeout=1.0)
    assert ok is True
    assert "HTTP 200 OK" in msg
    assert latency >= 0


def test_clean_exit_not_marked_error(monkeypatch: pytest.MonkeyPatch) -> None:
    import typer

    sent_payloads: list[tuple[str, dict]] = []
    client = OTelTelemetryClient(endpoint="http://localhost:4318", enabled=True)
    monkeypatch.setattr(client, "_send_payload", lambda path, p: sent_payloads.append((path, p)))

    with pytest.raises(typer.Exit):
        with client.span("clean_exit_span"):
            raise typer.Exit(0)

    assert len(sent_payloads) == 1
    span_data = sent_payloads[0][1]["resourceSpans"][0]["scopeSpans"][0]["spans"][0]
    assert span_data["status"]["code"] == "STATUS_CODE_OK"
    attrs = {a["key"]: next(iter(a["value"].values())) for a in span_data.get("attributes", [])}
    assert "error" not in attrs


def test_concurrent_threads_context_isolation(monkeypatch: pytest.MonkeyPatch) -> None:
    import concurrent.futures

    sent_payloads: list[tuple[str, dict]] = []
    client = OTelTelemetryClient(endpoint="http://localhost:4318", enabled=True)
    monkeypatch.setattr(client, "_send_payload", lambda path, p: sent_payloads.append((path, p)))

    def task(i: int) -> None:
        with client.span(f"parent_span_{i}"):
            with client.span(f"child_span_{i}"):
                pass

    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(task, range(10)))

    # Should have 20 spans total (10 parents, 10 children)
    assert len(sent_payloads) == 20


def test_context_propagating_thread_pool_executor(monkeypatch: pytest.MonkeyPatch) -> None:
    from devops_cli.telemetry import ContextPropagatingThreadPoolExecutor

    sent_payloads: list[tuple[str, dict]] = []
    client = OTelTelemetryClient(endpoint="http://localhost:4318", enabled=True)
    monkeypatch.setattr(client, "_send_payload", lambda path, p: sent_payloads.append((path, p)))

    with client.span("root_cli_span"):

        def worker_task(idx: int) -> str:
            with client.span(f"worker_child_span_{idx}") as child_id:
                return str(child_id)

        with ContextPropagatingThreadPoolExecutor(max_workers=2) as pool:
            # Test submit
            fut = pool.submit(worker_task, 1)
            fut.result()
            # Test map
            list(pool.map(worker_task, [2, 3]))

    # We should have 4 spans total: 1 root and 3 worker children
    assert len(sent_payloads) == 4
    all_spans = [
        p[1]["resourceSpans"][0]["scopeSpans"][0]["spans"][0]
        for p in sent_payloads
        if p[0] == "/v1/traces"
    ]
    root_span = [s for s in all_spans if s["name"] == "root_cli_span"][0]
    child_spans = [s for s in all_spans if s["name"].startswith("worker_child_span_")]

    assert len(child_spans) == 3
    for cs in child_spans:
        assert cs["traceId"] == root_span["traceId"]
        assert cs["parentSpanId"] == root_span["spanId"]


def test_traceparent_env_propagation_and_record_exception(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sent_payloads: list[tuple[str, dict]] = []
    client = OTelTelemetryClient(endpoint="http://localhost:4318", enabled=True)
    monkeypatch.setattr(client, "_send_payload", lambda path, p: sent_payloads.append((path, p)))

    # Set external TRACEPARENT in environment
    parent_trace_id = "4bf92f3577b34da6a3ce929d0e0e4736"
    parent_span_id = "00f067aa0ba902b7"
    monkeypatch.setenv("TRACEPARENT", f"00-{parent_trace_id}-{parent_span_id}-01")

    with pytest.raises(RuntimeError, match="custom error"):
        with client.span("env_parented_span") as handle:
            handle.record_exception(RuntimeError("custom error"))
            raise RuntimeError("custom error")

    assert len(sent_payloads) == 1
    span_data = sent_payloads[0][1]["resourceSpans"][0]["scopeSpans"][0]["spans"][0]
    assert span_data["traceId"] == parent_trace_id
    assert span_data["parentSpanId"] == parent_span_id
    assert span_data["status"]["code"] == "STATUS_CODE_ERROR"

    attrs = {a["key"]: next(iter(a["value"].values())) for a in span_data.get("attributes", [])}
    assert attrs.get("error") is True
    assert attrs.get("exception.type") == "RuntimeError"
    assert attrs.get("exception.message") == "custom error"


def test_record_llm_metrics_and_semantic_conventions(monkeypatch: pytest.MonkeyPatch) -> None:
    sent_payloads: list[tuple[str, dict]] = []
    client = OTelTelemetryClient(endpoint="http://localhost:4318", enabled=True)
    monkeypatch.setattr(client, "_send_payload", lambda path, p: sent_payloads.append((path, p)))

    with client.span(
        "llm_call", {"cli.command": "devops ai review", "subprocess.bin": "ollama"}
    ) as handle:
        handle.record_llm_metrics(
            provider="ollama",
            model="qwen2.5-coder:7b",
            prompt_tokens=500,
            completion_tokens=150,
            total_tokens=650,
            ttft_ms=120.5,
            duration_s=2.5,
            token_rate=60.0,
        )

    assert len(sent_payloads) == 1
    span_data = sent_payloads[0][1]["resourceSpans"][0]["scopeSpans"][0]["spans"][0]
    attrs = {a["key"]: next(iter(a["value"].values())) for a in span_data.get("attributes", [])}

    # Normalized semantic attributes
    assert attrs.get("process.command_line") == "devops ai review"
    assert attrs.get("process.executable.name") == "ollama"

    # GenAI standard attributes
    assert attrs.get("gen_ai.system") == "ollama"
    assert attrs.get("gen_ai.request.model") == "qwen2.5-coder:7b"
    assert str(attrs.get("gen_ai.usage.prompt_tokens")) == "500"
    assert str(attrs.get("gen_ai.usage.completion_tokens")) == "150"
    assert str(attrs.get("gen_ai.usage.total_tokens")) == "650"
    assert float(attrs.get("gen_ai.time_to_first_token_ms")) == 120.5
    assert float(attrs.get("gen_ai.token_rate_tok_per_sec")) == 60.0


def test_parent_context_dict_extraction(monkeypatch: pytest.MonkeyPatch) -> None:
    sent_payloads: list[tuple[str, dict]] = []
    client = OTelTelemetryClient(endpoint="http://localhost:4318", enabled=True)
    monkeypatch.setattr(client, "_send_payload", lambda path, p: sent_payloads.append((path, p)))

    parent_trace_id = "1234567890abcdef1234567890abcdef"
    parent_span_id = "fedcba0987654321"
    headers = {"traceparent": f"00-{parent_trace_id}-{parent_span_id}-01"}

    with client.span("http_incoming_request", parent_context=headers):
        pass

    assert len(sent_payloads) == 1
    span_data = sent_payloads[0][1]["resourceSpans"][0]["scopeSpans"][0]["spans"][0]
    assert span_data["traceId"] == parent_trace_id
    assert span_data["parentSpanId"] == parent_span_id
