"""The counters and histograms devops-cli sends over OTLP (#564).

Every command runs as its own short-lived process, so a counter or histogram cannot keep a
running total. Each observation is sent as a delta, and the collector's `deltatocumulative`
processor adds a series' deltas up across processes before Prometheus stores them. Dashboards
query only the metrics defined here; `tests/test_telemetry_instruments.py` checks each query.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any
from urllib.parse import urlparse


class InstrumentKind(StrEnum):
    """How a metric accumulates."""

    COUNTER = "counter"
    HISTOGRAM = "histogram"


@dataclass(frozen=True)
class Instrument:
    """A metric devops-cli sends, named as Prometheus stores it."""

    name: str
    kind: InstrumentKind
    unit: str
    description: str
    # Histogram bucket upper bounds.
    bounds: tuple[float, ...] = ()

    @property
    def series(self) -> tuple[str, ...]:
        """The names Prometheus stores the metric under."""
        if self.kind is InstrumentKind.HISTOGRAM:
            return tuple(f"{self.name}_{suffix}" for suffix in ("bucket", "sum", "count"))
        return (self.name,)


_SECONDS = (0.5, 1, 2.5, 5, 10, 30, 60, 120, 300, 600)
_REVIEW_SECONDS = (30, 60, 120, 300, 600, 900, 1800, 3600, 7200)
_MILLISECONDS = (10, 25, 50, 100, 250, 500, 1000, 2500, 5000)

COMMAND_TOTAL = Instrument(
    "devops_cli_command_total", InstrumentKind.COUNTER, "1", "Commands run, by command and status"
)
COMMAND_DURATION = Instrument(
    "devops_cli_command_duration_seconds",
    InstrumentKind.HISTOGRAM,
    "s",
    "Command wall time, by command",
    _SECONDS,
)
REVIEW_DURATION = Instrument(
    "devops_cli_review_duration_seconds",
    InstrumentKind.HISTOGRAM,
    "s",
    "Review wall time, by target type",
    _REVIEW_SECONDS,
)
FINDINGS_TOTAL = Instrument(
    "devops_cli_findings_total",
    InstrumentKind.COUNTER,
    "1",
    "Review findings, by persona, severity and status",
)
AI_REQUESTS_TOTAL = Instrument(
    "devops_cli_ai_requests_total",
    InstrumentKind.COUNTER,
    "1",
    "LLM calls, by provider, model, server, serving backend and whether the cache answered",
)
AI_TOKENS_TOTAL = Instrument(
    "devops_cli_ai_tokens_total",
    InstrumentKind.COUNTER,
    "1",
    "LLM tokens, by type (prompt or completion), provider, model, server and backend",
)
AI_SPEND_USD_TOTAL = Instrument(
    "devops_cli_ai_spend_usd_total",
    InstrumentKind.COUNTER,
    "USD",
    "Approximate LLM spend, by provider, model, server and backend",
)
RAG_QUERY_DURATION = Instrument(
    "devops_cli_rag_query_duration_ms",
    InstrumentKind.HISTOGRAM,
    "ms",
    "RAG retrieval time",
    _MILLISECONDS,
)

INSTRUMENTS: tuple[Instrument, ...] = (
    COMMAND_TOTAL,
    COMMAND_DURATION,
    REVIEW_DURATION,
    FINDINGS_TOTAL,
    AI_REQUESTS_TOTAL,
    AI_TOKENS_TOTAL,
    AI_SPEND_USD_TOTAL,
    RAG_QUERY_DURATION,
)


def emit(instrument: Instrument, value: float, attributes: dict[str, Any] | None = None) -> None:
    """Add to a counter or observe a histogram value."""
    from devops_cli.telemetry.tracer import get_tracer

    tracer = get_tracer()
    if instrument.kind is InstrumentKind.COUNTER:
        tracer.increment_counter(
            instrument.name, value, unit=instrument.unit, attributes=attributes
        )
    else:
        tracer.record_histogram(
            instrument.name,
            value,
            bounds=instrument.bounds,
            unit=instrument.unit,
            attributes=attributes,
        )


def backend_name(served_by: str | None) -> str:
    """A serving backend's short name: its host's first label, e.g. `vllm` or `ollama-0`."""
    if not served_by:
        return ""
    host = urlparse(served_by if "://" in served_by else f"//{served_by}").hostname or served_by
    return host.split(".", 1)[0]


__all__ = [
    "AI_REQUESTS_TOTAL",
    "AI_SPEND_USD_TOTAL",
    "AI_TOKENS_TOTAL",
    "COMMAND_DURATION",
    "COMMAND_TOTAL",
    "FINDINGS_TOTAL",
    "INSTRUMENTS",
    "RAG_QUERY_DURATION",
    "REVIEW_DURATION",
    "Instrument",
    "InstrumentKind",
    "backend_name",
    "emit",
]
