"""Shared domain models for Prometheus API responses."""

from __future__ import annotations

from pydantic import BaseModel, field_validator


class PrometheusSeries(BaseModel):
    """A single time-series result from a Prometheus query."""

    labels: dict[str, str] = {}
    value: str = ""  # instant query: single value string
    values: list[tuple[float, str]] = []  # range query: list of (timestamp, value)

    @property
    def label_str(self) -> str:
        """Render labels as a comma-separated key=value string, excluding __name__."""
        return ", ".join(f"{k}={v}" for k, v in self.labels.items() if k != "__name__")


class PrometheusQueryResult(BaseModel):
    """Parsed response from /api/v1/query or /api/v1/query_range."""

    status: str
    series: list[PrometheusSeries] = []
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
            for item in results:
                if not isinstance(item, dict):
                    continue
                labels = item.get("metric", {})
                val_pair = item.get("value", [None, ""])
                value = str(val_pair[1]) if isinstance(val_pair, list) and len(val_pair) > 1 else ""
                series.append(PrometheusSeries(labels=labels, value=value))
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
            for item in results:
                if not isinstance(item, dict):
                    continue
                labels = item.get("metric", {})
                raw_values = item.get("values", [])
                values: list[tuple[float, str]] = []
                if isinstance(raw_values, list):
                    for pair in raw_values:
                        if isinstance(pair, list) and len(pair) == 2:
                            values.append((float(pair[0]), str(pair[1])))
                series.append(PrometheusSeries(labels=labels, values=values))
        return cls(status=status, series=series, error=error)
