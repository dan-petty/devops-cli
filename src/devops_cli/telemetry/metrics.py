"""In-Memory Metrics Registry backed by prometheus_client."""

from __future__ import annotations

import contextlib
import threading
import time
from typing import Any

from prometheus_client import CollectorRegistry, Counter, Gauge, Histogram, generate_latest
from pydantic import BaseModel, Field

from devops_cli.config.defaults import DEFAULT_OTEL_COUNTER_AMOUNT


class MetricSample(BaseModel):
    """Individual metric sample with name, labels, and value."""

    name: str
    labels: dict[str, str] = Field(default_factory=dict)
    value: float
    timestamp: float = Field(default_factory=time.time)


def _read_sample_value(
    collector: Counter | Gauge | Histogram,
    labels: dict[str, str] | None,
    *,
    suffix: str = "",
) -> float:
    """Read a sample value matching `labels` from a prometheus_client collector."""
    target_labels = {str(k): str(v) for k, v in (labels or {}).items()}
    for family in collector.collect():
        expected_name = f"{family.name}{suffix}"
        for sample in family.samples:
            if sample.name == expected_name and sample.labels == target_labels:
                return float(sample.value)
    return 0.0


def _sum_counter_samples(collector: Counter) -> float:
    return sum(
        float(s.value)
        for fam in collector.collect()
        for s in fam.samples
        if s.name == f"{fam.name}_total"
    )


def _first_gauge_sample(collector: Gauge) -> float | None:
    for fam in collector.collect():
        for s in fam.samples:
            if s.name == fam.name:
                return float(s.value)
    return None


class InMemoryMetricsRegistry:
    """Thread-safe in-memory metric registry backed by prometheus_client.CollectorRegistry."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._registry = CollectorRegistry(auto_describe=True)
        self._collectors: dict[str, Counter | Gauge | Histogram] = {}
        self._label_names: dict[str, tuple[str, ...]] = {}

    @property
    def registry(self) -> CollectorRegistry:
        """Return the underlying prometheus_client CollectorRegistry."""
        return self._registry

    def _get_or_create_collector(
        self,
        name: str,
        cls: type[Counter | Gauge | Histogram],
        labels: dict[str, str] | None,
    ) -> tuple[Any, tuple[str, ...]]:
        label_keys = tuple(sorted((labels or {}).keys()))
        existing = self._collectors.get(name)
        if existing is None or not isinstance(existing, cls):
            collector = cls(name, f"{name} metric", labelnames=label_keys, registry=self._registry)
            self._collectors[name] = collector
            self._label_names[name] = label_keys
            return collector, label_keys
        return existing, self._label_names[name]

    def increment_counter(
        self,
        name: str,
        value: float = DEFAULT_OTEL_COUNTER_AMOUNT,
        labels: dict[str, str] | None = None,
    ) -> None:
        """Increment a counter by the specified value (default 1.0)."""
        with self._lock:
            collector, label_keys = self._get_or_create_collector(name, Counter, labels)
            if label_keys:
                label_vals = [str((labels or {})[k]) for k in label_keys]
                collector.labels(*label_vals).inc(value)
            else:
                collector.inc(value)

    def set_gauge(
        self,
        name: str,
        value: float,
        labels: dict[str, str] | None = None,
    ) -> None:
        """Set a gauge value for a metric."""
        with self._lock:
            collector, label_keys = self._get_or_create_collector(name, Gauge, labels)
            if label_keys:
                label_vals = [str((labels or {})[k]) for k in label_keys]
                collector.labels(*label_vals).set(value)
            else:
                collector.set(value)

    def record_histogram(
        self,
        name: str,
        value: float,
        labels: dict[str, str] | None = None,
    ) -> None:
        """Record an observation in a Prometheus histogram."""
        with self._lock:
            collector, label_keys = self._get_or_create_collector(name, Histogram, labels)
            if label_keys:
                label_vals = [str((labels or {})[k]) for k in label_keys]
                collector.labels(*label_vals).observe(value)
            else:
                collector.observe(value)

    def get_counter(
        self,
        name: str,
        labels: dict[str, str] | None = None,
    ) -> float:
        """Retrieve counter value."""
        with self._lock:
            collector = self._collectors.get(name)
            if not isinstance(collector, Counter):
                return 0.0
            return _read_sample_value(collector, labels, suffix="_total")

    get_counter_value = get_counter

    def get_gauge(
        self,
        name: str,
        labels: dict[str, str] | None = None,
    ) -> float:
        """Retrieve gauge value."""
        with self._lock:
            collector = self._collectors.get(name)
            if not isinstance(collector, Gauge):
                return 0.0
            return _read_sample_value(collector, labels)

    get_gauge_value = get_gauge

    def clear_metric(self, name: str) -> None:
        """Unregister and clear all stored values for a metric."""
        with self._lock:
            collector = self._collectors.pop(name, None)
            self._label_names.pop(name, None)
            if collector is not None:
                with contextlib.suppress(KeyError, ValueError):
                    self._registry.unregister(collector)

    def reset(self) -> None:
        """Reset all in-memory metric collections."""
        with self._lock:
            for collector in list(self._collectors.values()):
                with contextlib.suppress(KeyError, ValueError):
                    self._registry.unregister(collector)
            self._collectors.clear()
            self._label_names.clear()

    record_counter = increment_counter
    record_gauge = set_gauge

    def get_metrics_snapshot(self) -> dict[str, Any]:
        """Retrieve aggregated snapshot of recorded metrics (counters, gauges, histogram counts)."""
        with self._lock:
            items = list(self._collectors.items())
        counters = {
            name: _sum_counter_samples(col) for name, col in items if isinstance(col, Counter)
        }
        gauges = {
            name: val
            for name, col in items
            if isinstance(col, Gauge) and (val := _first_gauge_sample(col)) is not None
        }
        hist_count = sum(1 for _, col in items if isinstance(col, Histogram))
        return {
            "counters": counters,
            "gauges": gauges,
            "counter_count": len(counters),
            "gauge_count": len(gauges),
            "histogram_count": hist_count,
        }

    def export_prometheus_text(self) -> str:
        """Export all recorded metrics in Prometheus text exposition format."""
        with self._lock:
            return generate_latest(self._registry).decode("utf-8")


# Global singleton registry
GLOBAL_METRICS = InMemoryMetricsRegistry()

__all__ = [
    "GLOBAL_METRICS",
    "InMemoryMetricsRegistry",
    "MetricSample",
]
