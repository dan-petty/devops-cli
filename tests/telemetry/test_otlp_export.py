"""Telemetry export goes to the collector over OTLP/HTTP only, and tests read it from the OTLP
fake (#1319)."""

from __future__ import annotations

import logging
from collections.abc import Callable
from pathlib import Path

import pytest

from devops_cli.exceptions.telemetry import OtlpProtocolError
from devops_cli.telemetry.exporter import HttpOtlpExporter, otlp_exporter
from devops_cli.telemetry.instruments import COMMAND_TOTAL, emit
from devops_cli.telemetry.tracer import (
    get_tracer,
    install_exporter,
    remove_exporter,
    reset_tracer,
    trace_span,
)
from tests.support.fakes.otlp import FakeCollector


@pytest.mark.parametrize("protocol", ["grpc", "GRPC", "kafka"])
def test_a_protocol_other_than_otlp_http_is_refused_by_its_variable(
    monkeypatch: pytest.MonkeyPatch, protocol: str
) -> None:
    """Verify a gRPC or unknown protocol fails with an error that names its variable."""
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_PROTOCOL", protocol)

    with pytest.raises(OtlpProtocolError, match="OTEL_EXPORTER_OTLP_PROTOCOL"):
        otlp_exporter("http://collector.example.com:4318")


@pytest.mark.parametrize(
    "endpoint",
    ["grpc://collector.example.com", "http://collector.example.com:4317", "localhost:4317"],
)
def test_a_grpc_endpoint_is_refused_by_its_setting(
    monkeypatch: pytest.MonkeyPatch, endpoint: str
) -> None:
    """Verify an endpoint with the grpc scheme or the OTLP gRPC port names `telemetry.endpoint`."""
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_PROTOCOL", raising=False)

    with pytest.raises(OtlpProtocolError, match=r"telemetry\.endpoint"):
        otlp_exporter(endpoint)


@pytest.mark.parametrize("protocol", ["http/json", "http/protobuf"])
def test_an_otlp_http_protocol_sends_to_the_endpoint_it_names(
    monkeypatch: pytest.MonkeyPatch, protocol: str
) -> None:
    """Verify an OTLP/HTTP protocol sends over HTTP, also to a port that suggests gRPC."""
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_PROTOCOL", protocol)

    exporter = otlp_exporter("http://collector.example.com:4317/")

    assert (type(exporter), exporter.endpoint) == (
        HttpOtlpExporter,
        "http://collector.example.com:4317",
    )


def test_a_refused_protocol_keeps_the_command_running_with_export_off(
    monkeypatch: pytest.MonkeyPatch,
    config: Callable[..., Path],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Verify the process tracer exports nothing, warns once, and its probe names the setting."""
    config(telemetry={"enabled": True})
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_PROTOCOL", "grpc")
    reset_tracer()

    with caplog.at_level(logging.WARNING, logger="devops_cli.telemetry.tracer"):
        tracer = get_tracer()
    reachable, detail, _ = tracer.test_connection(timeout=0.1)

    assert (
        tracer.enabled,
        reachable,
        "OTEL_EXPORTER_OTLP_PROTOCOL" in detail,
        [r.getMessage().startswith("Telemetry export is off:") for r in caplog.records],
    ) == (False, False, True, [True])


def test_the_process_tracer_exports_to_the_configured_collector(
    monkeypatch: pytest.MonkeyPatch, config: Callable[..., Path]
) -> None:
    """Verify `get_tracer` builds the real exporter for the configured endpoint."""
    config(telemetry={"enabled": True})
    monkeypatch.setenv("DEVOPS_CLI_TELEMETRY_ENDPOINT", "http://collector.example.com:4318")
    reset_tracer()

    exporter = get_tracer().exporter

    assert (type(exporter), exporter.endpoint) == (
        HttpOtlpExporter,
        "http://collector.example.com:4318",
    )


def test_spans_and_metrics_reach_the_otlp_fake(otlp: FakeCollector) -> None:
    """Verify code under test exports to the fake that the `otlp` fixture installs."""
    with trace_span("fake_reached", {"case": "fixture"}):
        emit(COMMAND_TOTAL, 1.0, {"command": "fixture", "status": "ok"})

    assert (
        [(span.name, span.attributes.get("case")) for span in otlp.spans],
        otlp.points(COMMAND_TOTAL.name),
    ) == ([("fake_reached", "fixture")], [({"command": "fixture", "status": "ok"}, 1.0)])


def test_an_installed_exporter_stays_until_it_is_removed() -> None:
    """Verify each tracer exports to the installed exporter, with export on, until its removal."""
    fake = FakeCollector()
    install_exporter(fake)
    reset_tracer()
    while_installed = (get_tracer().exporter is fake, get_tracer().enabled)

    remove_exporter()

    assert (while_installed, type(get_tracer().exporter)) == ((True, True), HttpOtlpExporter)
