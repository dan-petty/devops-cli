"""Unit tests verifying 100% OpenTelemetry tracing and metrics coverage
across all DevOps CLI commands."""

from __future__ import annotations

import asyncio
import json
import subprocess
import sys
from collections.abc import Callable
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

import pytest
import typer
from opentelemetry.semconv._incubating.attributes.process_attributes import (
    PROCESS_ARGS_COUNT,
    PROCESS_COMMAND_ARGS,
    PROCESS_COMMAND_LINE,
    PROCESS_EXECUTABLE_NAME,
)
from typer.testing import CliRunner

from devops_cli.core.cli import new_typer
from devops_cli.core.process import run_subprocess, run_subprocess_async
from devops_cli.main import _COMMAND_SPECS, _delegate
from devops_cli.telemetry.tracer import (
    OTelTelemetryClient,
    SpanHandle,
    get_tracer,
    reset_tracer,
)
from tests.support.session_spawns import record_spawns


@pytest.fixture(autouse=True)
def clean_tracer(monkeypatch: pytest.MonkeyPatch, config: Any) -> list[tuple[str, dict[str, Any]]]:
    config(telemetry={"enabled": True})
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
    get_tracer().flush()

    # Verify emitted spans and metrics
    trace_payloads = [p for path, p in clean_tracer if path == "/v1/traces"]
    metric_payloads = [p for path, p in clean_tracer if path == "/v1/metrics"]

    assert len(trace_payloads) >= 1
    span_data = trace_payloads[0]["resourceSpans"][0]["scopeSpans"][0]["spans"][0]
    assert span_data["name"] == "cli.test-subcmd"
    assert span_data["status"]["code"] == "STATUS_CODE_OK"

    attrs = {a["key"]: str(next(iter(a["value"].values()))) for a in span_data["attributes"]}
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

    attrs = {a["key"]: str(next(iter(a["value"].values()))) for a in span_data["attributes"]}
    assert attrs["cli.status"] == "error"
    assert "Cluster unreachable" in attrs.get("error.message", attrs.get("cli.error", ""))


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


# A credential that no secret pattern of `mask_secrets` finds, typed as the value of a secret key
# whose name the patterns also miss.
_TYPED_CREDENTIAL = "correct-horse-battery-staple"
_SET_A_CREDENTIAL = ["set", "cloudflare.tunnel_token", _TYPED_CREDENTIAL]


@pytest.fixture
def delegated_set(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    """Run `devops dummy set <key> <credential>` through `_delegate` and return each payload the
    tracer exported. The tracer is made after `sys.argv` holds the command line, as it is when a
    person runs the command."""
    monkeypatch.setattr(sys, "argv", ["devops", "dummy", *_SET_A_CREDENTIAL])
    reset_tracer()
    exported: list[dict[str, Any]] = []
    monkeypatch.setattr(get_tracer(), "_send_payload", lambda _path, p: exported.append(p))

    dummy_app = new_typer()

    @dummy_app.callback()
    def dummy_cb() -> None:
        pass

    @dummy_app.command(name="set")
    def dummy_set(key: str, value: str) -> None:
        pass

    module = SimpleNamespace(app=dummy_app)
    monkeypatch.setattr("devops_cli.main.import_module", lambda _path: module)

    _delegate("devops_cli.commands.dummy", "dummy", list(_SET_A_CREDENTIAL))
    return exported


def test_no_exported_attribute_holds_an_argument_value(
    delegated_set: list[dict[str, Any]],
) -> None:
    """A credential given as an argument (`devops config set <key> <value>`) is in no span
    attribute, event or resource attribute that goes to the trace backend (#1996)."""
    assert (bool(delegated_set), _TYPED_CREDENTIAL in json.dumps(delegated_set, default=str)) == (
        True,
        False,
    )


def test_the_command_spans_keep_the_command_path_and_the_argument_count(
    delegated_set: list[dict[str, Any]],
) -> None:
    """With no argument value, the trace still names the command that ran and how many arguments
    it got."""
    spans = {
        span["name"]: {a["key"]: next(iter(a["value"].values())) for a in span["attributes"]}
        for payload in delegated_set
        if "resourceSpans" in payload
        for span in payload["resourceSpans"][0]["scopeSpans"][0]["spans"]
    }
    assert (
        spans["cli.dummy"]["cli.command"],
        spans["cli.dummy"]["cli.args_count"],
        "cli.args" in spans["cli.dummy"],
        spans["cli.set"].get("cli.command_path"),
    ) == ("dummy", "3", False, "devops dummy set")


# `devops uv run` passes the arguments of a person on to uv: here a credential that no secret
# pattern finds (#2025).
_PASSED_ON = ["uv", "run", "devops", "config", "set", "cloudflare.tunnel_token", _TYPED_CREDENTIAL]
# Built at run time, so that no secret scanner reads the test as a leaked token.
_GITHUB_SHAPED_TOKEN = "ghp_" + "1234567890abcdef" * 2 + "1234"
_ARGUMENT_KEYS = (PROCESS_COMMAND_ARGS, PROCESS_COMMAND_LINE, "subprocess.cmd")


def _attribute_value(value: dict[str, Any]) -> Any:
    """The Python value of an OTLP AnyValue: a list for an array, else the text of the scalar."""
    if "arrayValue" in value:
        return [_attribute_value(item) for item in value["arrayValue"].get("values", [])]
    return str(next(iter(value.values())))


@pytest.fixture(params=["run_subprocess", "run_subprocess_async"])
def subprocess_export(
    request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch, config: Any
) -> Callable[..., tuple[dict[str, Any], str]]:
    """Run a command through `run_subprocess` or `run_subprocess_async` with the given telemetry
    settings and the export captured. Return the attributes of its span and the text of every
    payload that the tracer exported."""

    def run(cmd: list[str], **telemetry: Any) -> tuple[dict[str, Any], str]:
        config(telemetry={"enabled": True, **telemetry})
        exported: list[dict[str, Any]] = []
        monkeypatch.setattr(get_tracer(), "_send_payload", lambda _path, p: exported.append(p))
        if request.param == "run_subprocess_async":
            record_spawns(monkeypatch)
            asyncio.run(run_subprocess_async(list(cmd)))
        else:
            monkeypatch.setattr(
                subprocess, "run", lambda argv, **_: subprocess.CompletedProcess(argv, 0, "", "")
            )
            run_subprocess(list(cmd))
        get_tracer().flush()
        [span] = [
            span
            for payload in exported
            if "resourceSpans" in payload
            for span in payload["resourceSpans"][0]["scopeSpans"][0]["spans"]
            if span["name"] == f"subprocess.{cmd[0]}"
        ]
        attrs = {a["key"]: _attribute_value(a["value"]) for a in span["attributes"]}
        return attrs, json.dumps(exported, default=str)

    return run


def test_a_subprocess_span_holds_the_executable_and_the_argument_count_and_no_argument(
    subprocess_export: Callable[..., tuple[dict[str, Any], str]],
) -> None:
    """By default a subprocess span names the program and counts its arguments, and no exported
    payload holds an argument value (#2025)."""
    attrs, exported = subprocess_export(_PASSED_ON)
    assert (
        attrs.get(PROCESS_EXECUTABLE_NAME),
        attrs.get(PROCESS_ARGS_COUNT),
        [key for key in _ARGUMENT_KEYS if key in attrs],
        _TYPED_CREDENTIAL in exported,
    ) == ("uv", "7", [], False)


def test_a_person_who_turns_on_capture_gets_each_argument_through_the_secret_mask(
    subprocess_export: Callable[..., tuple[dict[str, Any], str]],
) -> None:
    """`telemetry.capture_command_args` puts the arguments in `process.command_args`, each one
    through the secret mask, and the span still holds no `process.command_line`."""
    from devops_cli.security.sanitizer import mask_secrets

    attrs, exported = subprocess_export(
        [*_PASSED_ON, "--token", _GITHUB_SHAPED_TOKEN], capture_command_args=True
    )
    assert (
        attrs.get(PROCESS_COMMAND_ARGS),
        attrs.get(PROCESS_ARGS_COUNT),
        [key for key in _ARGUMENT_KEYS if key in attrs],
        _GITHUB_SHAPED_TOKEN in exported,
    ) == (
        [*_PASSED_ON, "--token", mask_secrets(_GITHUB_SHAPED_TOKEN)],
        "9",
        [PROCESS_COMMAND_ARGS],
        False,
    )


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
    get_tracer().flush()

    trace_payloads = [p for path, p in clean_tracer if path == "/v1/traces"]
    metric_payloads = [p for path, p in clean_tracer if path == "/v1/metrics"]

    assert len(trace_payloads) >= 1
    span_data = trace_payloads[0]["resourceSpans"][0]["scopeSpans"][0]["spans"][0]
    assert span_data["name"] == "subprocess.kubectl"

    attrs = {a["key"]: str(next(iter(a["value"].values()))) for a in span_data["attributes"]}
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
    attrs = {a["key"]: str(next(iter(a["value"].values()))) for a in span_data["attributes"]}
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


def test_all_command_specs_registered() -> None:
    """Verify that all CLI command specs are present in _COMMAND_SPECS."""
    expected_commands = {
        "repos",
        "ssh",
        "branches",
        "devcontainer",
        "workspace",
        "install-tools",
        "openspec",
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
        "roadmap",
        "pr",
        "gh",
        "tf",
        "tls",
        "telemetry",
        "cloudflare",
        "serve",
        "test",
        "pipeline",
        "vault",
        "valkey",
        "sandbox",
        "dashboard",
        "tui",
        "format",
        "lint",
        "status",
        "survey",
    }
    assert set(_COMMAND_SPECS.keys()) == expected_commands


def test_span_events_and_exception_stacktrace(
    clean_tracer: list[tuple[str, dict[str, Any]]],
) -> None:
    """Verify that SpanHandle records custom events and captures full exception stack traces."""
    tracer = get_tracer()

    with tracer.span("test.milestones") as handle:
        handle.add_event("milestone_1", {"key": "value1"})
        handle.add_event("milestone_2", {"step": 2})

    trace_payloads = [p for path, p in clean_tracer if path == "/v1/traces"]
    assert len(trace_payloads) >= 1
    span = trace_payloads[0]["resourceSpans"][0]["scopeSpans"][0]["spans"][0]
    assert "events" in span
    events = span["events"]
    assert len(events) == 2
    assert events[0]["name"] == "milestone_1"
    assert events[1]["name"] == "milestone_2"

    # Test exception event capture
    with pytest.raises(ValueError, match="Boom"):
        with tracer.span("test.failing"):
            raise ValueError("Boom")

    failing_payloads = [p for path, p in clean_tracer if path == "/v1/traces"]
    failing_span = failing_payloads[-1]["resourceSpans"][0]["scopeSpans"][0]["spans"][0]
    assert failing_span["status"]["code"] == "STATUS_CODE_ERROR"
    attrs = {a["key"]: str(next(iter(a["value"].values()))) for a in failing_span["attributes"]}
    assert attrs["exception.type"] == "ValueError"
    assert "Boom" in attrs["exception.message"]
    assert "exception.stacktrace" in attrs
    assert "events" in failing_span
    assert any(e["name"] == "exception" for e in failing_span["events"])


def test_resource_attributes_standard() -> None:
    """Verify that standardized OTel resource attributes include runtime and SDK details."""
    tracer = get_tracer()
    res_attrs = {
        a["key"]: str(next(iter(a["value"].values()))) for a in tracer._get_resource_attributes()
    }
    assert res_attrs["service.name"] == "devops-cli"
    assert res_attrs["process.runtime.name"] == "cpython"
    assert res_attrs["telemetry.sdk.name"] == "devops-cli-otel"
    assert res_attrs["telemetry.sdk.language"] == "python"


def test_subprocess_rich_telemetry_emission(
    clean_tracer: list[tuple[str, dict[str, Any]]], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify that run_subprocess emits rich telemetry with args, sizes, and events."""
    import subprocess as sp

    monkeypatch.setattr(
        sp,
        "run",
        lambda *args, **kwargs: sp.CompletedProcess(
            args[0], returncode=0, stdout="hello world\n", stderr=""
        ),
    )

    proc = run_subprocess(["echo", "hello", "world"])
    assert proc.returncode == 0

    trace_payloads = [p for path, p in clean_tracer if path == "/v1/traces"]
    subproc_spans = [
        s
        for p in trace_payloads
        for s in p["resourceSpans"][0]["scopeSpans"][0]["spans"]
        if s["name"] == "subprocess.echo"
    ]
    assert len(subproc_spans) >= 1
    span = subproc_spans[0]
    attrs = {a["key"]: str(next(iter(a["value"].values()))) for a in span["attributes"]}
    assert attrs["subprocess.bin"] == "echo"
    assert attrs["subprocess.status"] == "ok"
    assert attrs["subprocess.args_count"] == "3"
    assert int(attrs["subprocess.stdout_bytes"]) > 0
    assert any(e["name"] == "subprocess_completed" for e in span.get("events", []))
