"""The `devops sandbox metrics` command: its tables, JSON, alerts and spans."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

from devops_cli.sandbox.engine import WorkloadSandboxEngine
from devops_cli.sandbox.models import (
    SandboxInstance,
)
from devops_cli.telemetry import get_recent_spans
from tests.support.fakes.docker_engine import DockerEngineFake
from tests.support.fakes.otlp import plain_attributes
from tests.support.sandbox import (
    engine_stats_frame,
    port_of,
)


def test_cli_sandbox_metrics_dry_run(cli: Callable[..., Any]) -> None:
    """Test sandbox metrics CLI command with --dry-run flag."""
    result = cli("sandbox", "metrics", "sandbox-123", "--dry-run")
    assert result.exit_code == 0
    assert "dry-run" in result.output.lower() or "metrics" in result.output.lower()


def test_cli_sandbox_metrics_success(
    cli: Callable[..., Any], register_sandbox: Callable[..., SandboxInstance], prom_server: str
) -> None:
    """Test sandbox metrics CLI command execution and table rendering."""
    register_sandbox("sandbox-metrics-cli", name="cli-svc", host_ports=[port_of(prom_server)])

    result = cli("sandbox", "metrics", "sandbox-metrics-cli")

    assert result.exit_code == 0
    assert "Cgroup v2 Resource Telemetry: cli-svc" in result.output
    assert "Prometheus Application Metrics: cli-svc" in result.output
    assert "http_requests_total" in result.output


def test_cli_sandbox_metrics_with_warnings(
    cli: Callable[..., Any],
    register_sandbox: Callable[..., SandboxInstance],
    docker_daemon: DockerEngineFake,
    prom_server: str,
) -> None:
    """Test sandbox metrics CLI command rendering warning callouts."""
    register_sandbox("sandbox-warn-cli", name="warn-svc", host_ports=[port_of(prom_server)])
    frame = engine_stats_frame()
    frame["memory_stats"] = {"usage": 471_859_200, "limit": 524_288_000, "stats": {"cache": 0}}
    docker_daemon.script_stats("sandbox-warn-cli", [frame, frame])

    result = cli("sandbox", "metrics", "sandbox-warn-cli")

    assert result.exit_code == 0
    assert "THRESHOLD ALERT: Memory usage (90.0%) exceeds" in result.output
    assert "Workload 'warn-svc' exceeded 1 operating threshold(s)." in result.output


def test_cli_sandbox_metrics_json_output(
    cli: Callable[..., Any], register_sandbox: Callable[..., SandboxInstance], prom_server: str
) -> None:
    """Test sandbox metrics CLI command with --json output flag."""
    register_sandbox("sandbox-json-cli", name="json-svc", host_ports=[port_of(prom_server)])

    result = cli("sandbox", "metrics", "sandbox-json-cli", "--json")

    assert result.exit_code == 0
    data = json.loads(result.output)
    assert (data["instance_id"], data["target"], data["cgroup"]["cpu_percent"]) == (
        "sandbox-json-cli",
        "json-svc",
        2.0,
    )


def test_cli_sandbox_metrics_not_found(cli: Callable[..., Any], docker_daemon: Any) -> None:
    """Test sandbox metrics CLI command when target instance is not found."""
    result = cli("sandbox", "metrics", "missing")

    assert result.exit_code != 0
    assert "not found" in result.output.lower()


def test_cli_sandbox_metrics_url_target(cli: Callable[..., Any], prom_server: str) -> None:
    """Test CLI metrics invocation with raw URL target when instance not found."""
    result = cli("sandbox", "metrics", prom_server)

    assert result.exit_code == 0
    assert "Prometheus" in result.output


def test_cli_sandbox_metrics_help_metrics_timeout(cli: Callable[..., Any]) -> None:
    """Test CLI metrics --help displays dedicated Prometheus scrape timeout description."""
    result = cli("sandbox", "metrics", "--help")
    assert result.exit_code == 0
    assert "HTTP timeout in seconds for" in result.output
    assert "Prometheus metrics scraping" in result.output


_COMMAND_SPAN_ATTRIBUTES = ("sandbox.identifier", "sandbox.prom_endpoint", "sandbox.dry_run")
_ENGINE_SPAN_ATTRIBUTES = ("sandbox.identifier", "sandbox.container_id", "sandbox.prom_endpoint")


def test_the_metrics_command_and_the_engine_each_record_a_span(
    cli: Callable[..., Any],
    register_sandbox: Callable[..., SandboxInstance],
    tracer: Any,
    prom_server: str,
) -> None:
    """The command records `sandbox.metrics`, and the engine `sandbox.engine.metrics`."""
    dry_run = cli("sandbox", "metrics", "test-inst", "--dry-run")
    instance = register_sandbox("inst-tracer", name="tracer-svc", host_ports=[port_of(prom_server)])
    WorkloadSandboxEngine().metrics("inst-tracer")

    spans = {span["name"]: plain_attributes(span["attributes"]) for span in get_recent_spans()}
    assert dry_run.exit_code == 0
    command_span = {key: spans["sandbox.metrics"][key] for key in _COMMAND_SPAN_ATTRIBUTES}
    engine_span = {key: spans["sandbox.engine.metrics"][key] for key in _ENGINE_SPAN_ATTRIBUTES}
    assert command_span == {
        "sandbox.identifier": "test-inst",
        "sandbox.prom_endpoint": "/metrics",
        "sandbox.dry_run": True,
    }
    assert engine_span == {
        "sandbox.identifier": "inst-tracer",
        "sandbox.container_id": instance.container_id,
        "sandbox.prom_endpoint": "/metrics",
    }


def test_cli_sandbox_metrics_renders_a_scrape_warning(
    cli: Callable[..., Any], register_sandbox: Callable[..., SandboxInstance], prom_server: str
) -> None:
    """Test CLI renders the scrape warning apart from the resource table."""
    register_sandbox("sandbox-test-scrape", name="scrape-svc", host_ports=[port_of(prom_server)])

    result = cli("sandbox", "metrics", "sandbox-test-scrape", "--prom-endpoint", "/error")

    assert result.exit_code == 0
    assert "SCRAPE WARNING" in result.output
    assert "HTTP 500" in result.output


def test_cli_sandbox_metrics_latency_sla_option(
    cli: Callable[..., Any], register_sandbox: Callable[..., SandboxInstance], prom_server: str
) -> None:
    """The --latency-sla-ms flag sets the average request latency that raises an alert."""
    register_sandbox("sandbox-test-sla", name="sla-svc", host_ports=[port_of(prom_server)])

    within = cli("sandbox", "metrics", "sandbox-test-sla", "--latency-sla-ms", "250.0")
    over = cli("sandbox", "metrics", "sandbox-test-sla", "--latency-sla-ms", "10.0")

    assert (
        within.exit_code,
        "High average request latency" in within.output,
        over.exit_code,
        "High average request latency" in over.output,
    ) == (0, False, 0, True)


def test_prom_table_prints_scraped_labels_as_written(
    cli: Callable[..., Any], register_sandbox: Callable[..., SandboxInstance], prom_server: str
) -> None:
    """Label values come from the scraped endpoint: their brackets print as written instead of
    raising MarkupError or styling the table. A long label string is cut before it is escaped, so
    the cut never lands inside an escape (#955)."""
    register_sandbox("sandbox-brackets", name="svc", host_ports=[port_of(prom_server)])

    result = cli("sandbox", "metrics", "sandbox-brackets", "--prom-endpoint", "/bracketed")

    assert [
        literal in result.output
        for literal in (
            "Prometheus Application Metrics: svc",
            "job=[/]",
            "[bold red]FAKE",
            "path=" + "a" * 30 + "[/...",
        )
    ] == [True] * 4


def test_metrics_snapshot_prints_scrape_errors_and_target_as_written(
    cli: Callable[..., Any],
    register_sandbox: Callable[..., SandboxInstance],
    malformed_endpoint: int,
) -> None:
    """A scrape error carries the HTTP client's exception text, which can quote the endpoint's own
    bytes, as a malformed header line does: it prints as written in the warning and in the error
    line, instead of raising MarkupError. So does the target in the table title (#955)."""
    target = "svc[/x]"
    register_sandbox("sandbox-malformed", name=target, host_ports=[malformed_endpoint])

    result = cli("sandbox", "metrics", "sandbox-malformed")

    assert result.exit_code == 0
    assert [
        literal in result.output
        for literal in (
            f"Cgroup v2 Resource Telemetry: {target}",
            "SCRAPE WARNING: ",
            "[/x] [link=https://example.com]y",
            f"Workload '{target}' encountered telemetry collection error: ",
        )
    ] == [True] * 4


def test_metrics_snapshot_prints_the_target_as_written_in_every_summary_line(
    cli: Callable[..., Any],
    register_sandbox: Callable[..., SandboxInstance],
    docker_daemon: DockerEngineFake,
    prom_server: str,
) -> None:
    """The target is the instance name or the URL the user gave, and a URL can hold brackets: it
    prints as written in the healthy line and in the threshold-exceeded line. A threshold alert is
    the CLI's own text and holds no markup, so its line prints it as written too (#955)."""
    target = "svc[/x]"
    register_sandbox("sandbox-healthy", name=target, host_ports=[port_of(prom_server)])
    register_sandbox("sandbox-loaded", name=target, host_ports=[port_of(prom_server)])
    loaded = engine_stats_frame()
    loaded["memory_stats"] = {"usage": 471_859_200, "limit": 524_288_000, "stats": {"cache": 0}}
    docker_daemon.script_stats("sandbox-loaded", [loaded, loaded])

    healthy = cli("sandbox", "metrics", "sandbox-healthy")
    exceeded = cli("sandbox", "metrics", "sandbox-loaded")

    assert [
        literal in output
        for output, literal in (
            (healthy.output, f"Workload '{target}' operating within normal performance bounds."),
            (exceeded.output, "THRESHOLD ALERT: Memory usage (90.0%) exceeds"),
            (exceeded.output, f"Workload '{target}' exceeded 1 operating threshold(s)."),
        )
    ] == [True] * 3
