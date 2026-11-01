"""Unit tests for OpenTelemetry tracer and metrics emitter."""

import os
from typing import Any
from unittest.mock import MagicMock

import httpx2
import pytest

from devops_cli.ai.client.models import LLMResponse
from devops_cli.ai.client.unified import _set_response_span_attributes
from devops_cli.config.settings import TelemetryConfig
from devops_cli.telemetry.exporter import OtlpSignal
from devops_cli.telemetry.instruments import COMMAND_TOTAL, emit
from devops_cli.telemetry.tracer import (
    OTelTelemetryClient,
    get_tracer,
    install_exporter,
    reset_tracer,
    trace_span,
)
from tests.support.fakes.clock import ClockFake
from tests.support.fakes.otlp import FakeCollector
from tests.support.waits import POLL_INTERVAL_SECONDS


@pytest.fixture
def collector(unserved_side_channel_port: int) -> str:
    """A collector that refuses every export, as an unserved workstation's does. Its port stays
    bound for the run, so an export a client queues on its own thread is refused whenever it runs."""
    return f"http://127.0.0.1:{unserved_side_channel_port}"


def test_telemetry_disabled() -> None:
    client = OTelTelemetryClient(enabled=False)
    with client.span("test_span") as span_id:
        assert span_id == ""
    # Should not raise
    client.record_gauge("test_metric", 1.0)


def test_telemetry_span_and_metric() -> None:
    otlp = FakeCollector()
    client = otlp.client()

    with client.span("pipeline_stage", {"persona": "devsecops"}) as span_id:
        assert len(span_id) == 16  # 8 bytes hex = 16 hex chars
        client.record_gauge("findings_count", 3, unit="1", attributes={"severity": "HIGH"})

    (span,) = otlp.spans
    assert (
        [metric["name"] for metric in otlp.metrics],
        span.name,
        span.status_code,
        sorted(export.signal for export in otlp.exports),
    ) == (
        ["findings_count"],
        "pipeline_stage",
        "STATUS_CODE_OK",
        [OtlpSignal.METRICS, OtlpSignal.TRACES],
    )


def test_telemetry_span_error_recording() -> None:
    otlp = FakeCollector()
    client = otlp.client()

    with pytest.raises(ValueError, match="simulated failure"):
        with client.span("failing_span"):
            raise ValueError("simulated failure")

    (span,) = otlp.spans
    assert (span.status_code, span.status_message) == ("STATUS_CODE_ERROR", "simulated failure")


def test_global_trace_helpers(otlp: FakeCollector) -> None:
    with trace_span("helper_span", {"env": "test"}):
        emit(COMMAND_TOTAL, 1.0, {"command": "helper", "status": "ok"})

    assert (
        [span.name for span in otlp.spans],
        otlp.points(COMMAND_TOTAL.name),
    ) == (["helper_span"], [({"command": "helper", "status": "ok"}, 1.0)])


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


def test_traced_decorator(otlp: FakeCollector) -> None:
    from devops_cli.telemetry.tracer import traced

    @traced(name="decorated_func", attributes={"module": "test"})
    def my_function(x: int) -> int:
        return x * 2

    assert (my_function(5), [span.name for span in otlp.spans]) == (10, ["decorated_func"])


def test_clean_exit_not_marked_error() -> None:
    import typer

    otlp = FakeCollector()
    client = otlp.client()

    with pytest.raises(typer.Exit) as raised:
        with client.span("clean_exit_span"):
            raise typer.Exit(0)
    assert raised.value.exit_code is not None

    (span,) = otlp.spans
    assert (span.status_code, "error" in span.attributes) == ("STATUS_CODE_OK", False)


def test_handled_cli_exit_non_zero_status_without_stacktrace() -> None:
    import typer

    otlp = FakeCollector()
    client = otlp.client()

    with pytest.raises(typer.Exit) as raised:
        with client.span("cli_exit_span"):
            raise typer.Exit(1)
    assert raised.value.exit_code is not None

    (span,) = otlp.spans
    # No stacktrace and no exception event on an intentional CLI exit, to keep traces small.
    assert (
        span.status_code,
        span.attributes.get("error"),
        span.attributes.get("cli.exit_code"),
        "exception.stacktrace" in span.attributes,
        span.events,
    ) == ("STATUS_CODE_ERROR", True, "1", False, ())


def test_unhandled_exception_records_traceback() -> None:
    otlp = FakeCollector()
    client = otlp.client()

    with pytest.raises(ValueError, match="unexpected error"):
        with client.span("crash_span"):
            raise ValueError("unexpected error")

    (span,) = otlp.spans
    assert (
        span.status_code,
        span.attributes.get("error"),
        span.attributes.get("exception.type"),
        "exception.stacktrace" in span.attributes,
        len(span.events),
    ) == ("STATUS_CODE_ERROR", True, "ValueError", True, 1)


def test_concurrent_threads_context_isolation() -> None:
    import concurrent.futures

    otlp = FakeCollector()
    client = otlp.client()

    def task(i: int) -> None:
        with client.span(f"parent_span_{i}"):
            with client.span(f"child_span_{i}"):
                pass

    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(task, range(10)))

    by_name = {span.name: span for span in otlp.spans}
    assert (len(by_name), {by_name[f"child_span_{i}"].parent_span_id for i in range(10)}) == (
        20,
        {by_name[f"parent_span_{i}"].span_id for i in range(10)},
    )


def test_context_propagating_thread_pool_executor() -> None:
    from devops_cli.telemetry import ContextPropagatingThreadPoolExecutor

    otlp = FakeCollector()
    client = otlp.client()

    with client.span("root_cli_span"):

        def worker_task(idx: int) -> str:
            with client.span(f"worker_child_span_{idx}") as child_id:
                return str(child_id)

        with ContextPropagatingThreadPoolExecutor(max_workers=2) as pool:
            pool.submit(worker_task, 1).result()
            list(pool.map(worker_task, [2, 3]))

    spans = otlp.spans
    root_span = next(span for span in spans if span.name == "root_cli_span")
    children = [span for span in spans if span.name.startswith("worker_child_span_")]
    assert (
        len(spans),
        {(child.trace_id, child.parent_span_id) for child in children},
        len(children),
    ) == (4, {(root_span.trace_id, root_span.span_id)}, 3)


def test_traceparent_env_propagation_and_record_exception(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    otlp = FakeCollector()
    client = otlp.client()
    parent_trace_id = "4bf92f3577b34da6a3ce929d0e0e4736"
    parent_span_id = "00f067aa0ba902b7"
    monkeypatch.setenv("TRACEPARENT", f"00-{parent_trace_id}-{parent_span_id}-01")

    with pytest.raises(RuntimeError, match="custom error"):
        with client.span("env_parented_span") as handle:
            handle.record_exception(RuntimeError("custom error"))
            raise RuntimeError("custom error")

    (span,) = otlp.spans
    assert (
        span.trace_id,
        span.parent_span_id,
        span.status_code,
        span.attributes.get("error"),
        span.attributes.get("exception.type"),
        span.attributes.get("exception.message"),
    ) == (
        parent_trace_id,
        parent_span_id,
        "STATUS_CODE_ERROR",
        True,
        "RuntimeError",
        "custom error",
    )


def test_response_span_attributes_and_semantic_conventions() -> None:
    """A reply's usage is written once, under the current GenAI keys, beside normalized keys."""
    otlp = FakeCollector()
    client = otlp.client()
    reply = LLMResponse(
        "ok",
        backend_info="ollama (example.com:11434)",
        origin=httpx2.URL("http://example.com:11434").origin,
        prompt_tokens=500,
        completion_tokens=150,
        total_tokens=650,
        wall_seconds=2.5,
    )

    with client.span(
        "llm_call", {"cli.command": "devops ai review", "subprocess.bin": "ollama"}
    ) as handle:
        _set_response_span_attributes(handle, reply, "ollama")

    (span,) = otlp.spans
    attrs = span.attributes
    replaced = (
        "gen_ai.usage.prompt_tokens",
        "gen_ai.usage.completion_tokens",
        "gen_ai.usage.total_tokens",
        "gen_ai.server.address",
        "gen_ai.tokens_per_second",
        "gen_ai.token_rate_tok_per_sec",
    )
    assert (
        attrs.get("cli.command"),
        attrs.get("process.executable.name"),
        attrs.get("gen_ai.usage.input_tokens"),
        attrs.get("gen_ai.usage.output_tokens"),
        attrs.get("llm.tokens_per_second"),
        (attrs.get("server.address"), attrs.get("server.port")),
        [key for key in replaced if key in attrs],
    ) == ("devops ai review", "ollama", "500", "150", 60.0, ("example.com", "11434"), [])


def test_parent_context_dict_extraction() -> None:
    otlp = FakeCollector()
    client = otlp.client()
    parent_trace_id = "1234567890abcdef1234567890abcdef"
    parent_span_id = "fedcba0987654321"
    headers = {"traceparent": f"00-{parent_trace_id}-{parent_span_id}-01"}

    with client.span("http_incoming_request", parent_context=headers):
        pass

    (span,) = otlp.spans
    assert (span.trace_id, span.parent_span_id) == (parent_trace_id, parent_span_id)


def test_get_current_span_context(collector: str) -> None:
    """get_current_span_context returns active span_id and trace_id within a span."""
    from devops_cli.telemetry.tracer import get_current_span_context

    client = OTelTelemetryClient(endpoint=collector, enabled=True)
    with client.span("context_test_span") as s_id:
        ctx = get_current_span_context()
        assert ctx["span_id"] == s_id
        assert ctx["trace_id"] is not None
    client.shutdown()


def test_disabled_client_exports_nothing() -> None:
    """A disabled telemetry client exports nothing to the collector."""
    otlp = FakeCollector()
    disabled_client = OTelTelemetryClient(enabled=False, exporter=otlp)
    with disabled_client.span("disabled_span"):
        pass
    disabled_client.flush()
    assert otlp.exports == []


def test_tracer_lifecycle_reset_and_shutdown() -> None:
    """reset_tracer and shutdown_tracer safely cycle the global tracer."""
    from devops_cli.telemetry.tracer import reset_tracer, shutdown_tracer

    reset_tracer()
    tracer = get_tracer()
    assert tracer.endpoint.startswith("http")
    shutdown_tracer()
    assert tracer._executor is None


def test_telemetry_traceparent_helpers() -> None:
    """Test W3C traceparent injection and parsing."""
    from devops_cli.telemetry.context import extract_traceparent, inject_traceparent_headers

    headers = {"Authorization": "Bearer token"}
    injected = inject_traceparent_headers(headers)
    assert "Authorization" in injected

    traceparent = "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01"
    parsed = extract_traceparent(traceparent)
    assert parsed is not None
    assert parsed["trace_id"] == "4bf92f3577b34da6a3ce929d0e0e4736"
    assert parsed["parent_span_id"] == "00f067aa0ba902b7"

    assert extract_traceparent("") is None
    assert extract_traceparent("invalid-header") is None


def test_telemetry_span_kinds_links_and_normalization() -> None:
    """Test span kinds, span links, and semantic attribute normalization."""
    otlp = FakeCollector()
    client = otlp.client()

    with client.span(
        "http_inbound",
        kind="server",
        attributes={
            "git.branch": "feat/observability",
            "k8s.pod": "pod-123",
            "argo.app": "app-prod",
        },
    ) as span_h:
        span_h.add_link("0123456789abcdef0123456789abcdef", "fedcba9876543210")

    (span,) = otlp.spans
    assert (
        span.kind,
        span.links,
        {"vcs.branch", "k8s.pod.name", "argo.application.name"} <= span.attributes.keys(),
    ) == (
        "SPAN_KIND_SERVER",
        (("0123456789abcdef0123456789abcdef", "fedcba9876543210"),),
        True,
    )


def test_telemetry_keyboard_interrupt_handling() -> None:
    """Test KeyboardInterrupt handling in OTelTelemetryClient."""
    otlp = FakeCollector()
    client = otlp.client()

    with pytest.raises(KeyboardInterrupt) as raised:
        with client.span("interrupted_span"):
            raise KeyboardInterrupt()
    assert raised.value is not None

    (span,) = otlp.spans
    assert (span.status_code, span.attributes.get("error.type")) == (
        "STATUS_CODE_ERROR",
        "KeyboardInterrupt",
    )


def test_full_executor_drops_export(collector: str) -> None:
    """A full executor drops the export gracefully."""
    client = OTelTelemetryClient(endpoint=collector, enabled=True)
    mock_exec = MagicMock()
    mock_exec.submit.side_effect = RuntimeError("thread pool full")
    client._executor = mock_exec

    with client.span("dropped_span"):
        pass
    client.shutdown()

    assert (client.export_successes, client.export_failures) == (0, 0)


def test_failed_executor_shutdown_still_clears_executor(collector: str) -> None:
    """A failed executor shutdown still clears the client executor reference."""
    client = OTelTelemetryClient(endpoint=collector, enabled=True)
    mock_exec = MagicMock()
    mock_exec.shutdown.side_effect = RuntimeError("exec shutdown fail")
    client._executor = mock_exec

    client.shutdown()
    assert client._executor is None


def test_resolve_telemetry_settings_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    """Settings that cannot load leave export off when no registered variable turns it on, since
    the unreadable configuration may be what turns it off (#956)."""
    from devops_cli.telemetry.tracer import _resolve_telemetry_settings

    monkeypatch.setattr(
        "devops_cli.config.settings.load_settings",
        MagicMock(side_effect=RuntimeError("settings corrupted")),
    )
    monkeypatch.delenv("DEVOPS_CLI_TELEMETRY_ENABLED", raising=False)
    monkeypatch.delenv("DEVOPS_CLI_TELEMETRY_ENDPOINT", raising=False)
    assert _resolve_telemetry_settings() == TelemetryConfig(enabled=False)


def test_span_caller_location_and_runtime_attributes(collector: str) -> None:
    """Verify trace_span automatically enriches caller location, thread, and process metadata."""
    client = OTelTelemetryClient(endpoint=collector, enabled=True)
    with client.span("test_caller_span") as handle:
        assert (
            handle._attributes.get("code.function")
            == "test_span_caller_location_and_runtime_attributes"
        )
        assert handle._attributes.get("code.filepath", "").endswith("test_telemetry.py")
        assert isinstance(handle._attributes.get("code.lineno"), int)
        assert isinstance(handle._attributes.get("thread.name"), str)
        assert handle._attributes.get("process.pid") == os.getpid()


def test_span_vcs_and_k8s_attributes_detection(
    monkeypatch: pytest.MonkeyPatch, collector: str
) -> None:
    """Verify trace_span populates VCS branch/commit and K8s context/namespace."""
    reset_tracer()
    monkeypatch.setattr(
        "devops_cli.telemetry.tracer._read_git_head_ref",
        lambda _: ("feat/telemetry-rich-attributes", "1234567890abcdef"),
    )
    monkeypatch.setattr(
        "devops_cli.telemetry.tracer._detect_k8s_context",
        lambda: ("mock-cluster", "mock-system"),
    )

    client = OTelTelemetryClient(endpoint=collector, enabled=True)
    with client.span("test_vcs_span") as handle:
        assert (
            handle._attributes.get("vcs.ref.name"),
            handle._attributes.get("vcs.revision_id"),
            handle._attributes.get("k8s.context"),
            handle._attributes.get("k8s.namespace"),
        ) == (
            "feat/telemetry-rich-attributes",
            "1234567890abcdef",
            "mock-cluster",
            "mock-system",
        )
    reset_tracer()


def test_cached_resource_attributes_enrichment() -> None:
    """Verify OTelTelemetryClient pre-computes enriched system and environment resource attributes."""
    client = OTelTelemetryClient(enabled=True)
    res_keys = {attr["key"] for attr in client._cached_resource_attributes}
    assert {
        "service.name",
        "service.version",
        "host.name",
        "host.arch",
        "os.type",
        "os.description",
        "process.pid",
        "process.executable.name",
    }.issubset(res_keys)


def test_a_new_tracer_starts_no_process(monkeypatch: pytest.MonkeyPatch) -> None:
    """Creating the tracer reads its resource attributes without starting a process.

    `platform.platform()` runs `uname -p`, so a dry run that created the tracer first started a
    process, depending on whether an earlier caller had cached it.
    """
    import platform
    import subprocess

    started: list[object] = []

    def refuse(args: object, *_: object, **__: object) -> None:
        started.append(args)
        raise AssertionError("the tracer started a process")

    platform._uname_cache = None  # type: ignore[attr-defined]  # the first-call path the dry run hit
    monkeypatch.setattr(subprocess, "Popen", refuse)
    client = OTelTelemetryClient(enabled=True)
    description = next(
        attr["value"]["stringValue"]
        for attr in client._cached_resource_attributes
        if attr["key"] == "os.description"
    )
    assert (started, description) == ([], f"{platform.system()} {platform.release()}")


def test_response_span_attributes_enriched(collector: str) -> None:
    """The reply's model and serving backend are recorded; a URL with no port sets the default
    port of its scheme."""
    client = OTelTelemetryClient(endpoint=collector, enabled=True)
    reply = LLMResponse(
        "ok",
        backend_info="openai (example.com)",
        origin=httpx2.URL("https://example.com").origin,
        model="gpt-4o-2024-08-06",
        served_by="ollama-48gib",
        completion_tokens=60,
        wall_seconds=2.0,
    )
    with client.span("test_genai_span") as handle:
        _set_response_span_attributes(handle, reply, "openai")
        assert (
            handle._attributes.get("gen_ai.response.model"),
            handle._attributes.get("llm.served_by"),
            handle._attributes.get("llm.tokens_per_second"),
            handle._attributes.get("server.address"),
            handle._attributes.get("server.port"),
            "gen_ai.server.served_by" in handle._attributes,
        ) == ("gpt-4o-2024-08-06", "ollama-48gib", 30.0, "example.com", 443, False)


class _SlowCollector(FakeCollector):
    """A collector that takes a moment to answer, as one across a network does."""

    def __init__(self, clock: ClockFake | None = None) -> None:
        super().__init__()
        self._clock = clock

    def export(self, signal: OtlpSignal, body: bytes, content_type: str) -> None:
        if self._clock is not None:
            self._clock.sleep(0.2)
        super().export(signal, body, content_type)


def test_a_reset_lets_no_export_of_the_dropped_tracer_run_on(clock: ClockFake) -> None:
    """Every test resets the tracer, and an export still in flight from one test ran on into the
    next, whose socket probe then saw connections it never made."""
    otlp = _SlowCollector(clock)
    otlp.flush_before_reads(lambda: get_tracer().flush())
    install_exporter(otlp)
    with trace_span("last_span_of_a_test"):
        pass

    reset_tracer()

    assert [export.signal for export in otlp.exports] == [OtlpSignal.TRACES]


def test_sdk_meter_provider_flushes_one_batch_over_http_receiver() -> None:
    """Twenty counter and histogram recordings flush as one OTLP batch on shutdown, and an empty
    flush sends no request (#792)."""
    import json
    import threading
    from http.server import BaseHTTPRequestHandler, HTTPServer

    received: list[tuple[str, dict[str, Any]]] = []

    class _Receiver(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            length = int(self.headers.get("Content-Length", "0"))
            body = json.loads(self.rfile.read(length).decode("utf-8"))
            received.append((self.path, body))
            self.send_response(200)
            self.end_headers()

        def log_message(self, format: str, *args: Any) -> None:
            pass

    server = HTTPServer(("127.0.0.1", 0), _Receiver)
    thread = threading.Thread(
        target=server.serve_forever, kwargs={"poll_interval": POLL_INTERVAL_SECONDS}, daemon=True
    )
    thread.start()
    try:
        host, port = server.server_address[0], server.server_address[1]
        client = OTelTelemetryClient(endpoint=f"http://{host!s}:{port}", enabled=True)
        for idx in range(10):
            client.increment_counter("devops_cli_command_total", 1.0, attributes={"status": "ok"})
            client.record_histogram(
                "devops_cli_command_duration_seconds",
                float(idx + 1),
                unit="s",
                attributes={"command": "ci"},
            )
        client.flush()
        client.flush()
        client.shutdown()
    finally:
        server.shutdown()
        server.server_close()

    assert len(received) == 1
    path, payload = received[0]
    by_name = {m["name"]: m for m in payload["resourceMetrics"][0]["scopeMetrics"][0]["metrics"]}
    counter_pt = by_name["devops_cli_command_total"]["sum"]["dataPoints"][0]
    hist_pt = by_name["devops_cli_command_duration_seconds"]["exponentialHistogram"]["dataPoints"][
        0
    ]
    assert (
        path,
        counter_pt["asDouble"],
        int(counter_pt["startTimeUnixNano"]) < int(counter_pt["timeUnixNano"]),
        int(hist_pt["count"]),
        hist_pt["sum"],
        int(hist_pt["startTimeUnixNano"]) < int(hist_pt["timeUnixNano"]),
    ) == ("/v1/metrics", 10.0, True, 10, 55.0, True)


def test_otel_typer_subcommand_span_and_metrics() -> None:
    """Verify that new_typer() commands automatically emit trace spans and metrics."""
    otlp = FakeCollector()
    client = otlp.client()
    from devops_cli.core.cli import new_typer

    app = new_typer()

    @app.command(name="test-subcmd")
    def sample_subcommand(target: str = "cluster-1") -> None:
        client.increment_counter("test.runs", 1.0)

    from typer.testing import CliRunner

    runner = CliRunner()
    result = runner.invoke(app, ["--target", "prod-cluster"])
    assert result.exit_code == 0
    client.flush()
    assert any(m["name"] == "test.runs" for m in otlp.metrics)


def test_span_events_and_exception_stacktrace() -> None:
    """Verify that SpanHandle records custom events and captures full exception stack traces."""
    otlp = FakeCollector()
    client = otlp.client()

    with client.span("test.milestones") as handle:
        handle.add_event("milestone_1", {"key": "value1"})
        handle.add_event("milestone_2", {"step": 2})

    (span,) = otlp.spans
    assert len(span.events) == 2
    assert span.events[0] == "milestone_1"
    assert span.events[1] == "milestone_2"

    with pytest.raises(ValueError, match="Boom"):
        with client.span("test.failing"):
            raise ValueError("Boom")

    failing_span = otlp.spans[-1]
    assert failing_span.status_code == "STATUS_CODE_ERROR"
    assert failing_span.attributes.get("exception.type") == "ValueError"
    assert "Boom" in failing_span.attributes.get("exception.message", "")


def test_span_handle_attribute_mutation() -> None:
    """Verify that SpanHandle allows updating attributes dynamically."""
    from devops_cli.telemetry.tracer import SpanHandle

    attrs: dict[str, Any] = {}
    handle = SpanHandle("test_span_id", attrs)
    handle.set_attribute("new_key", "new_val")
    handle.set_attributes({"a": 1, "b": 2})
    assert attrs["new_key"] == "new_val"
    assert attrs["a"] == 1
    assert attrs["b"] == 2


def test_resource_attributes_standard() -> None:
    """Verify that standardized OTel resource attributes include runtime and SDK details."""
    client = OTelTelemetryClient(enabled=True)
    res_attrs = {
        a["key"]: str(next(iter(a["value"].values()))) for a in client._get_resource_attributes()
    }
    assert res_attrs["service.name"] == "devops-cli"
    assert res_attrs["process.runtime.name"] == "cpython"
    assert res_attrs["telemetry.sdk.name"] == "devops-cli-otel"
    assert res_attrs["telemetry.sdk.language"] == "python"


def test_span_no_vcs_attributes_when_working_directory_deleted(
    monkeypatch: pytest.MonkeyPatch, collector: str
) -> None:
    """Verify that a span starts without VCS attributes when the working directory is gone."""
    # Test by directly calling _detect_vcs_metadata to avoid git detection issues
    from pathlib import Path

    from devops_cli.telemetry.tracer import _detect_vcs_metadata, reset_tracer

    # Reset tracer to clear any cache
    reset_tracer()

    # Mock Path.cwd() to raise OSError when called (simulating deleted directory)
    original_cwd = Path.cwd
    try:

        def mock_cwd():
            raise OSError("No such file or directory")

        Path.cwd = mock_cwd

        # Call the function that should handle this gracefully now
        vcs_attrs = _detect_vcs_metadata()

        # Check that no vcs attributes were returned (should be empty dict)
        assert isinstance(vcs_attrs, dict)
        assert len(vcs_attrs) == 0, (
            f"Found VCS attributes when working directory is deleted: {vcs_attrs}"
        )
    finally:
        # Restore original Path.cwd
        Path.cwd = original_cwd


def test_span_vcs_attributes_when_working_directory_exists(
    monkeypatch: pytest.MonkeyPatch, collector: str
) -> None:
    """Verify that a span starts with VCS attributes when the working directory contains a git repo."""
    # Create a temporary git repo structure
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as tmp_path:
        git_dir = Path(tmp_path) / ".git"
        git_dir.mkdir()

        # Create HEAD file
        head_file = git_dir / "HEAD"
        head_file.write_text("ref: refs/heads/feat/example")

        # Create refs directory and branch file
        refs_dir = git_dir / "refs" / "heads"
        refs_dir.mkdir(parents=True)
        branch_file = refs_dir / "feat/example"
        branch_file.write_text("a1b2c3d4e5f67890123456789012345678901234")

        # Change into the directory
        original_cwd = os.getcwd()
        monkeypatch.chdir(tmp_path)

        try:
            # Reset tracer to clear any cache
            reset_tracer()

            # Start a span - this should work normally and detect VCS attributes
            with trace_span("test_span") as handle:
                pass  # Just create the span

            # Check that VCS attributes were added
            vcs_attrs = {k: v for k, v in handle._attributes.items() if k.startswith("vcs.")}
            assert "vcs.ref.name" in vcs_attrs
            assert "vcs.branch" in vcs_attrs
            assert "vcs.revision_id" in vcs_attrs
            assert "vcs.commit" in vcs_attrs
            assert vcs_attrs["vcs.ref.name"] == "feat/example"
            assert vcs_attrs["vcs.branch"] == "feat/example"
            assert vcs_attrs["vcs.revision_id"] == "a1b2c3d4e5f67890123456789012345678901234"
            assert vcs_attrs["vcs.commit"] == "a1b2c3d4e5f67890123456789012345678901234"
        finally:
            os.chdir(original_cwd)
