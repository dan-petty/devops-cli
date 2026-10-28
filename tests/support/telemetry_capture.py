"""Metric payloads an enabled telemetry client would send, captured instead (#1312).

A test hands a `Captured` sink to the client in place of its sender and reads back the data
points of each metric. The `captured` fixture does it for the tracer that `emit` reaches.
#1319's OTLP fake starts from here.
"""

from __future__ import annotations

from typing import Any

import pytest

from devops_cli.telemetry import tracer as tracer_module
from devops_cli.telemetry.tracer import OTelTelemetryClient


class Captured:
    """Metric data points an enabled client would send, with their resource."""

    def __init__(self) -> None:
        self.payloads: list[dict[str, Any]] = []

    def __call__(self, path: str, payload: dict[str, Any]) -> None:
        # An LLM call also sends its spans; only the metrics are kept.
        if "resourceMetrics" in payload:
            self.payloads.append(payload)

    def clear(self) -> None:
        """Send what the client holds now, and forget every payload captured so far."""
        tracer_module.get_tracer().flush()
        self.payloads.clear()

    @property
    def metrics(self) -> list[dict[str, Any]]:
        tracer_module.get_tracer().flush()
        return [
            metric
            for payload in self.payloads
            for resource in payload["resourceMetrics"]
            for scope in resource["scopeMetrics"]
            for metric in scope["metrics"]
        ]

    def points(self, name: str) -> list[tuple[dict[str, Any], float]]:
        """Each data point of a metric, as (attributes, value)."""
        found = []
        for metric in self.metrics:
            if metric["name"] != name:
                continue
            data = (
                metric.get("sum")
                or metric.get("exponentialHistogram")
                or metric.get("histogram")
                or metric["gauge"]
            )
            for point in data["dataPoints"]:
                attrs = {a["key"]: next(iter(a["value"].values())) for a in point["attributes"]}
                found.append((attrs, point.get("asDouble", point.get("sum"))))
        return found


@pytest.fixture
def captured(monkeypatch: pytest.MonkeyPatch) -> Captured:
    """An enabled telemetry client whose payloads are captured instead of sent."""
    sink = Captured()
    client = OTelTelemetryClient(endpoint="http://127.0.0.1:9")
    monkeypatch.setattr(client, "_send_payload", sink)
    monkeypatch.setattr(tracer_module, "get_tracer", lambda: client)
    return sink
