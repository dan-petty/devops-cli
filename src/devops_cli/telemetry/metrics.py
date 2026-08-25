"""In-memory Prometheus metric collector and recorder for devops-cli telemetry."""

from __future__ import annotations

import threading
import time
from collections import defaultdict
from dataclasses import dataclass, field


@dataclass
class MetricSample:
    """Individual metric sample with name, labels, and value."""

    name: str
    labels: dict[str, str]
    value: float
    timestamp: float = field(default_factory=time.time)


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
        value: float = 1.0,
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
        """Set the absolute value of a gauge."""
        key = self._freeze_labels(labels)
        with self._lock:
            self._gauges[name][key] = value

    def record_histogram(
        self,
        name: str,
        value: float,
        labels: dict[str, str] | None = None,
    ) -> None:
        """Record an observation value in a histogram."""
        key = self._freeze_labels(labels)
        with self._lock:
            self._histograms[name][key].append(value)

    def get_counter_value(self, name: str, labels: dict[str, str] | None = None) -> float:
        """Retrieve current value for a counter."""
        key = self._freeze_labels(labels)
        with self._lock:
            return self._counters.get(name, {}).get(key, 0.0)

    def get_gauge_value(self, name: str, labels: dict[str, str] | None = None) -> float:
        """Retrieve current value for a gauge."""
        key = self._freeze_labels(labels)
        with self._lock:
            return self._gauges.get(name, {}).get(key, 0.0)

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
                    label_str = ""
                    if key:
                        items = [f'{k}="{v}"' for k, v in key]
                        label_str = "{" + ",".join(items) + "}"
                    lines.append(f"{name}{label_str} {val}")

            for name, gauge_dict in self._gauges.items():
                lines.append(f"# TYPE {name} gauge")
                for key, val in gauge_dict.items():
                    label_str = ""
                    if key:
                        items = [f'{k}="{v}"' for k, v in key]
                        label_str = "{" + ",".join(items) + "}"
                    lines.append(f"{name}{label_str} {val}")

            for name, hist_dict in self._histograms.items():
                lines.append(f"# TYPE {name} histogram")
                for key, observations in hist_dict.items():
                    label_base = dict(key)
                    count = len(observations)
                    total = sum(observations)
                    labels_count = dict(label_base)
                    label_str = ""
                    if labels_count:
                        items = [f'{k}="{v}"' for k, v in labels_count.items()]
                        label_str = "{" + ",".join(items) + "}"
                    lines.append(f"{name}_count{label_str} {count}")
                    lines.append(f"{name}_sum{label_str} {total}")

        return "\n".join(lines) + "\n" if lines else ""


# Global singleton registry
GLOBAL_METRICS = InMemoryMetricsRegistry()
