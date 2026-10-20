"""Metric payloads an enabled telemetry client would send, captured instead (#1312).

A test hands a `Captured` sink to the client in place of its sender and reads back the data
points of each metric. #1319's OTLP fake starts from here.
"""

from __future__ import annotations

from typing import Any

from devops_cli.telemetry import tracer as tracer_module


class Captured:
    """Metric data points an enabled client would send, with their resource."""

    def __init__(self) -> None:
        self.payloads: list[dict[str, Any]] = []

    def __call__(self, path: str, payload: dict[str, Any]) -> None:
        # An LLM call also sends its spans; only the metrics are kept.
        if "resourceMetrics" in payload:
            self.payloads.append(payload)

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
