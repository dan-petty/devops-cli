"""Shared domain models for Prometheus API responses."""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class PrometheusSeries(BaseModel):
    """A single time-series result from a Prometheus query."""

    labels: dict[str, str] = Field(default_factory=dict)
    value: str = ""  # instant query: single value string
    values: list[tuple[float, str]] = Field(default_factory=list)  # (timestamp, value)

    @property
    def label_str(self) -> str:
        """Render labels as a comma-separated key=value string, excluding __name__."""
        return ", ".join(f"{k}={v}" for k, v in self.labels.items() if k != "__name__")


def _parse_instant_series(item: dict[str, object]) -> PrometheusSeries:
    """Parse single series entry from instant query result."""
    labels = item.get("metric", {}) if isinstance(item.get("metric"), dict) else {}
    val_pair = item.get("value", [None, ""])
    value = str(val_pair[1]) if isinstance(val_pair, list) and len(val_pair) > 1 else ""
    return PrometheusSeries(labels=labels, value=value)  # type: ignore[arg-type]


def _parse_prometheus_series_values(raw_values: object) -> list[tuple[float, str]]:
    """Parse timestamp-value pairs for a Prometheus series."""
    if not isinstance(raw_values, list):
        return []
    values: list[tuple[float, str]] = []
    for pair in raw_values:
        if not (isinstance(pair, list) and len(pair) == 2):
            continue
        try:
            values.append((float(pair[0]), str(pair[1])))
        except ValueError, TypeError:
            continue
    return values


def _parse_range_series(item: dict[str, object]) -> PrometheusSeries:
    """Parse single series entry from range query result."""
    labels = item.get("metric", {}) if isinstance(item.get("metric"), dict) else {}
    raw_values = item.get("values", [])
    values = _parse_prometheus_series_values(raw_values)
    return PrometheusSeries(labels=labels, values=values)  # type: ignore[arg-type]


class PrometheusQueryResult(BaseModel):
    """Parsed response from /api/v1/query or /api/v1/query_range."""

    status: str
    series: list[PrometheusSeries] = Field(default_factory=list)
    error: str = ""

    @field_validator("status", mode="before")
    @classmethod
    def _normalize_status(cls, v: object) -> str:
        return str(v)

    @classmethod
    def from_instant_response(cls, data: dict[str, object]) -> PrometheusQueryResult:
        """Parse a Prometheus instant query API response dict."""
        status = str(data.get("status", ""))
        error = str(data.get("error", ""))
        results = data.get("data", {})
        if isinstance(results, dict):
            results = results.get("result", [])
        series: list[PrometheusSeries] = []
        if isinstance(results, list):
            series = [_parse_instant_series(item) for item in results if isinstance(item, dict)]
        return cls(status=status, series=series, error=error)

    @classmethod
    def from_range_response(cls, data: dict[str, object]) -> PrometheusQueryResult:
        """Parse a Prometheus range query API response dict."""
        status = str(data.get("status", ""))
        error = str(data.get("error", ""))
        results = data.get("data", {})
        if isinstance(results, dict):
            results = results.get("result", [])
        series: list[PrometheusSeries] = []
        if isinstance(results, list):
            series = [_parse_range_series(item) for item in results if isinstance(item, dict)]
        return cls(status=status, series=series, error=error)
