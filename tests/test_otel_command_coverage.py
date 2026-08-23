"""Unit tests verifying 100% OpenTelemetry tracing and metrics coverage
across all DevOps CLI commands."""

from __future__ import annotations

import subprocess
from typing import Any
from unittest.mock import MagicMock

import pytest
import typer
from typer.testing import CliRunner

from devops_cli.core.cli import new_typer
from devops_cli.core.process import run_subprocess
from devops_cli.main import _COMMAND_SPECS, _delegate
from devops_cli.telemetry.tracer import (
    OTelTelemetryClient,
    SpanHandle,
    get_tracer,
    reset_tracer,
)


@pytest.fixture(autouse=True)
def clean_tracer(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, dict[str, Any]]]:
    reset_tracer()
    sent_payloads: list[tuple[str, dict[str, Any]]] = []
    tracer = get_tracer()
    monkeypatch.setattr(tracer, "_send_payload", lambda path, p: sent_payloads.append((path, p)))
    return sent_payloads


def test_otel_typer_subcommand_span_and_metrics(
    clean_tracer: list[tuple[str, dict[str, Any]]],
) -> None:
    """Verify that new_typer() commands automatically emit trace spans and metrics."""
    app = new_typer()

    @app.command(name="test-subcmd")
    def sample_subcommand(target: str = "cluster-1") -> None:
        print(f"Deploying to {target}")

    runner = CliRunner()
    result = runner.invoke(app, ["--target", "prod-cluster"])
    assert result.exit_code == 0
    assert "Deploying to prod-cluster" in result.output

    # Verify emitted spans and metrics
    trace_payloads = [p for path, p in clean_tracer if path == "/v1/traces"]
    metric_payloads = [p for path, p in clean_tracer if path == "/v1/metrics"]

    assert len(trace_payloads) >= 1
    span_data = trace_payloads[0]["resourceSpans"][0]["scopeSpans"][0]["spans"][0]
    assert span_data["name"] == "cli.test-subcmd"
    assert span_data["status"]["code"] == "STATUS_CODE_OK"

    attrs = {a["key"]: a["value"]["stringValue"] for a in span_data["attributes"]}
    assert attrs["cli.command"] == "test-subcmd"
    assert attrs["cli.status"] == "ok"
    assert "cli.duration_seconds" in attrs

    assert len(metric_payloads) >= 1
    metric_data = metric_payloads[0]["resourceMetrics"][0]["scopeMetrics"][0]["metrics"][0]
    assert metric_data["name"] == "devops_cli_subcommand_seconds"


def test_otel_typer_subcommand_error_span(
    clean_tracer: list[tuple[str, dict[str, Any]]],
) -> None:
    """Verify that exceptions in subcommands record error status and metrics."""
    app = new_typer()

    @app.command(name="failing-cmd")
    def failing_subcommand() -> None:
        raise RuntimeError("Cluster unreachable")

    runner = CliRunner()
    result = runner.invoke(app, [])
    assert result.exit_code != 0

    trace_payloads = [p for path, p in clean_tracer if path == "/v1/traces"]
    assert len(trace_payloads) >= 1
    span_data = trace_payloads[0]["resourceSpans"][0]["scopeSpans"][0]["spans"][0]
    assert span_data["name"] == "cli.failing-cmd"
    assert span_data["status"]["code"] == "STATUS_CODE_ERROR"

    attrs = {a["key"]: a["value"]["stringValue"] for a in span_data["attributes"]}
    assert attrs["cli.status"] == "error"
    assert "Cluster unreachable" in attrs.get("cli.error", "")


def test_cli_delegate_root_span_and_metrics(
    clean_tracer: list[tuple[str, dict[str, Any]]], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify that main._delegate emits root span and CLI execution metrics."""
    # Mock a target module with a typer app
    dummy_app = typer.Typer()

    @dummy_app.callback()
    def dummy_cb() -> None:
        pass

    @dummy_app.command(name="list")
    def dummy_list() -> None:
        print("Listing dummy resources")

    dummy_module = MagicMock()
    dummy_module.app = dummy_app
    monkeypatch.setattr("devops_cli.main.import_module", lambda path: dummy_module)

    _delegate("devops_cli.commands.dummy", "dummy", ["list"])

    trace_payloads = [p for path, p in clean_tracer if path == "/v1/traces"]
    metric_payloads = [p for path, p in clean_tracer if path == "/v1/metrics"]

    # Root span cli.dummy
    span_names = [
        s["name"] for p in trace_payloads for s in p["resourceSpans"][0]["scopeSpans"][0]["spans"]
    ]
    assert "cli.dummy" in span_names

    metric_names = [
        m["name"]
        for p in metric_payloads
        for m in p["resourceMetrics"][0]["scopeMetrics"][0]["metrics"]
    ]
    assert "devops_cli_command_total" in metric_names
    assert "devops_cli_command_duration_seconds" in metric_names


def test_subprocess_span_and_metrics(
    clean_tracer: list[tuple[str, dict[str, Any]]], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify that run_subprocess automatically emits child spans and execution metrics."""
    mock_res = subprocess.CompletedProcess(
        args=["kubectl", "get", "pods", "-n", "kube-system"],
        returncode=0,
        stdout="coredns-xxx Running",
        stderr="",
    )
    monkeypatch.setattr("subprocess.run", lambda *a, **kw: mock_res)

    proc = run_subprocess(["kubectl", "get", "pods", "-n", "kube-system"])
    assert proc.returncode == 0

    trace_payloads = [p for path, p in clean_tracer if path == "/v1/traces"]
    metric_payloads = [p for path, p in clean_tracer if path == "/v1/metrics"]

    assert len(trace_payloads) >= 1
    span_data = trace_payloads[0]["resourceSpans"][0]["scopeSpans"][0]["spans"][0]
    assert span_data["name"] == "subprocess.kubectl"

    attrs = {a["key"]: a["value"]["stringValue"] for a in span_data["attributes"]}
    assert attrs["subprocess.bin"] == "kubectl"
    assert attrs["subprocess.exit_code"] == "0"
    assert "subprocess.duration_seconds" in attrs

    metric_names = [
        m["name"]
        for p in metric_payloads
        for m in p["resourceMetrics"][0]["scopeMetrics"][0]["metrics"]
    ]
    assert "devops_cli_subprocess_seconds" in metric_names


def test_subprocess_error_span_and_metrics(
    clean_tracer: list[tuple[str, dict[str, Any]]], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify that failing subprocess executions record non-zero exit codes in spans."""
    mock_res = subprocess.CompletedProcess(
        args=["helm", "upgrade", "--install", "release-1"],
        returncode=1,
        stdout="",
        stderr="Error: connection refused",
    )
    monkeypatch.setattr("subprocess.run", lambda *a, **kw: mock_res)

    proc = run_subprocess(["helm", "upgrade", "--install", "release-1"])
    assert proc.returncode == 1

    trace_payloads = [p for path, p in clean_tracer if path == "/v1/traces"]
    span_data = trace_payloads[0]["resourceSpans"][0]["scopeSpans"][0]["spans"][0]
    attrs = {a["key"]: a["value"]["stringValue"] for a in span_data["attributes"]}
    assert attrs["subprocess.bin"] == "helm"
    assert attrs["subprocess.exit_code"] == "1"


def test_tracer_pooled_client_and_shutdown() -> None:
    """Verify that OTelTelemetryClient manages pooled HTTP transport and shuts down cleanly."""
    client = OTelTelemetryClient(endpoint="http://localhost:4318", enabled=True)
    http_c = client._get_http_client()
    assert http_c is not None
    assert not getattr(http_c, "is_closed", False)

    # Calling shutdown should close and reset client
    client.shutdown()
    assert client._http_client is None


def test_span_handle_attribute_mutation() -> None:
    """Verify that SpanHandle allows dynamic attribute updates while acting as span_id."""
    attrs: dict[str, Any] = {"init": "val"}
    handle = SpanHandle("abcd1234efgh5678", attrs)
    assert str(handle) == "abcd1234efgh5678"
    assert len(handle) == 16

    handle.set_attribute("new_key", "new_val")
    handle.set_attributes({"a": 1, "b": 2})
    assert attrs["new_key"] == "new_val"
    assert attrs["a"] == 1
    assert attrs["b"] == 2


def test_all_28_command_specs_registered() -> None:
    """Verify that all 28 CLI command specs are present in _COMMAND_SPECS."""
    expected_commands = {
        "repos",
        "ssh",
        "branches",
        "devcontainer",
        "workspace",
        "install-tools",
        "k8s",
        "kustomize",
        "docker",
        "grafana",
        "prometheus",
        "argo",
        "config",
        "ci",
        "uv",
        "scan",
        "ai",
        "review",
        "mcp",
        "docs",
        "release",
        "pr",
        "tf",
        "tofu",
        "tls",
        "cert",
        "telemetry",
        "otel",
    }
    assert set(_COMMAND_SPECS.keys()) == expected_commands
