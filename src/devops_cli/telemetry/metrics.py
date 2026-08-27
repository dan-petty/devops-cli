"""In-Memory Metrics Registry and Prometheus Text Formatter."""

from __future__ import annotations

import threading
import time
from collections import defaultdict
from typing import Any

from pydantic import BaseModel, Field

from devops_cli.config.defaults import DEFAULT_OTEL_COUNTER_AMOUNT


class MetricSample(BaseModel):
    """Individual metric sample with name, labels, and value."""

    name: str
    labels: dict[str, str] = Field(default_factory=dict)
    value: float
    timestamp: float = Field(default_factory=time.time)


def _format_prometheus_labels(labels_items: Any) -> str:
    """Format label pairs into Prometheus {k="v",...} string."""
    if not labels_items:
        return ""
    items_iter = labels_items.items() if hasattr(labels_items, "items") else labels_items
    items = [f'{k}="{v}"' for k, v in items_iter]
    return "{" + ",".join(items) + "}" if items else ""


class InMemoryMetricsRegistry:
    """Thread-safe in-memory metric registry tracking counters, histograms, and gauges."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._counters: dict[str, dict[tuple[tuple[str, str], ...], float]] = defaultdict(
            lambda: defaultdict(float)
        )
        self._gauges: dict[str, dict[tuple[tuple[str, str], ...], float]] = defaultdict(
            lambda: defaultdict(float)
        )
        self._histograms: dict[str, dict[tuple[tuple[str, str], ...], list[float]]] = defaultdict(
            lambda: defaultdict(list)
        )

    def _freeze_labels(self, labels: dict[str, str] | None) -> tuple[tuple[str, str], ...]:
        if not labels:
            return ()
        return tuple(sorted(labels.items()))

    def increment_counter(
        self,
        name: str,
        value: float = DEFAULT_OTEL_COUNTER_AMOUNT,
        labels: dict[str, str] | None = None,
    ) -> None:
        """Increment a counter by the specified value (default 1.0)."""
        key = self._freeze_labels(labels)
        with self._lock:
            self._counters[name][key] += value

    def set_gauge(
        self,
        name: str,
        value: float,
        labels: dict[str, str] | None = None,
    ) -> None:
        """Set a gauge value for a metric."""
        key = self._freeze_labels(labels)
        with self._lock:
            self._gauges[name][key] = value

    def record_histogram(
        self,
        name: str,
        value: float,
        labels: dict[str, str] | None = None,
    ) -> None:
        """Record an observation in a histogram."""
        key = self._freeze_labels(labels)
        with self._lock:
            self._histograms[name][key].append(value)

    def get_counter(
        self,
        name: str,
        labels: dict[str, str] | None = None,
    ) -> float:
        """Retrieve counter value."""
        key = self._freeze_labels(labels)
        with self._lock:
            return self._counters.get(name, {}).get(key, 0.0)

    get_counter_value = get_counter

    def get_gauge(
        self,
        name: str,
        labels: dict[str, str] | None = None,
    ) -> float:
        """Retrieve gauge value."""
        key = self._freeze_labels(labels)
        with self._lock:
            return self._gauges.get(name, {}).get(key, 0.0)

    get_gauge_value = get_gauge

    def get_histogram_samples(
        self,
        name: str,
        labels: dict[str, str] | None = None,
    ) -> list[float]:
        """Retrieve recorded histogram observations."""
        key = self._freeze_labels(labels)
        with self._lock:
            return list(self._histograms.get(name, {}).get(key, []))

    def reset(self) -> None:
        """Reset all in-memory metric collections."""
        with self._lock:
            self._counters.clear()
            self._gauges.clear()
            self._histograms.clear()

    def export_prometheus_text(self) -> str:
        """Export all recorded metrics in Prometheus text exposition format."""
        lines: list[str] = []
        with self._lock:
            for name, counter_dict in self._counters.items():
                lines.append(f"# TYPE {name} counter")
                for key, val in counter_dict.items():
                    lines.append(f"{name}{_format_prometheus_labels(key)} {val}")

            for name, gauge_dict in self._gauges.items():
                lines.append(f"# TYPE {name} gauge")
                for key, val in gauge_dict.items():
                    lines.append(f"{name}{_format_prometheus_labels(key)} {val}")

            for name, hist_dict in self._histograms.items():
                lines.append(f"# TYPE {name} histogram")
                for key, observations in hist_dict.items():
                    count = len(observations)
                    total = sum(observations)
                    label_str = _format_prometheus_labels(dict(key))
                    lines.append(f"{name}_count{label_str} {count}")
                    lines.append(f"{name}_sum{label_str} {total}")

        return "\n".join(lines) + "\n" if lines else ""


# Global singleton registry
GLOBAL_METRICS = InMemoryMetricsRegistry()
