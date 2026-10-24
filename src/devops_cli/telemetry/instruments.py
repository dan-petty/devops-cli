"""The counters and histograms devops-cli sends over OTLP (#564).

Every command runs as its own short-lived process, so a counter or histogram cannot keep a
running total. Each observation is sent as a delta, and the collector's `deltatocumulative`
processor adds a series' deltas up across processes before Prometheus stores them. A histogram
is exponential, so Prometheus stores it as a native histogram under the instrument's own name,
with no `_bucket`, `_sum` or `_count` series (#792); a dashboard reads it with
`histogram_quantile`, `histogram_avg` and `histogram_count`. Dashboards query only the metrics
defined here; `tests/test_telemetry_instruments.py` checks each query.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class InstrumentKind(StrEnum):
    """How a metric accumulates."""

    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"


@dataclass(frozen=True)
class Instrument:
    """A metric devops-cli sends, named as Prometheus stores it."""

    name: str
    kind: InstrumentKind
    unit: str
    description: str


COMMAND_TOTAL = Instrument(
    "devops_cli_command_total", InstrumentKind.COUNTER, "1", "Commands run, by command and status"
)
COMMAND_DURATION = Instrument(
    "devops_cli_command_duration_seconds",
    InstrumentKind.HISTOGRAM,
    "s",
    "Command wall time, by command",
)
REVIEW_DURATION = Instrument(
    "devops_cli_review_duration_seconds",
    InstrumentKind.HISTOGRAM,
    "s",
    "Review wall time, by target type",
)
FINDINGS_TOTAL = Instrument(
    "devops_cli_findings_total",
    InstrumentKind.COUNTER,
    "1",
    "Review findings, by producer, severity and status",
)
AI_REQUESTS_TOTAL = Instrument(
    "devops_cli_ai_requests_total",
    InstrumentKind.COUNTER,
    "1",
    "LLM calls and embedding requests, by operation (chat or embeddings), provider, model, server, "
    "serving backend and whether the cache answered",
)
AI_TOKENS_TOTAL = Instrument(
    "devops_cli_ai_tokens_total",
    InstrumentKind.COUNTER,
    "1",
    "LLM and embedding tokens, by operation (chat or embeddings), type (prompt or completion), "
    "provider, model, server and backend",
)
AI_SPEND_USD_TOTAL = Instrument(
    "devops_cli_ai_spend_usd_total",
    InstrumentKind.COUNTER,
    "USD",
    "Approximate LLM and embedding spend, by operation, provider, model, server and backend. "
    "Each request that a model answers adds to it, and a local request adds 0",
)
AI_LOCAL_COST_EQUIVALENT_USD_TOTAL = Instrument(
    "devops_cli_ai_local_cost_equivalent_usd_total",
    InstrumentKind.COUNTER,
    "USD",
    "Equivalent hosted cloud spend avoided by local model execution, by operation, at the "
    "reference model of the operation",
)
AI_JSON_REPAIRS_TOTAL = Instrument(
    "devops_cli_ai_json_repairs_total",
    InstrumentKind.COUNTER,
    "1",
    "LLM JSON replies repaired after strict parsing failed, by entry point source",
)
AI_GATEWAY_SLOT_WAIT = Instrument(
    "devops_cli_ai_gateway_slot_wait_seconds",
    InstrumentKind.HISTOGRAM,
    "s",
    "Time a chat call to the LLM gateway waited in this process for one of the gateway's backend "
    "slots, by outcome: ok once it held one, or timeout",
)
RAG_QUERY_DURATION = Instrument(
    "devops_cli_rag_query_duration_ms",
    InstrumentKind.HISTOGRAM,
    "ms",
    "RAG retrieval time, by stage: embedding, search, ranking, or total for the whole query",
)
QDRANT_RETRIES_TOTAL = Instrument(
    "devops_cli_qdrant_retries_total",
    InstrumentKind.COUNTER,
    "1",
    "Qdrant requests retried after a transient error, by operation and error type",
)
RAG_POINTS = Instrument(
    "devops_cli_rag_points",
    InstrumentKind.GAUGE,
    "1",
    "Points stored in RAG vector collections, by collection",
)

PROJECT_RELEASES_TOTAL = Instrument(
    "devops_cli_project_releases_total",
    InstrumentKind.GAUGE,
    "1",
    "Total project releases tracked",
)
PROJECT_COMMITS_TOTAL = Instrument(
    "devops_cli_project_commits_total",
    InstrumentKind.GAUGE,
    "1",
    "Project commits count by release",
)
PROJECT_PRS_TOTAL = Instrument(
    "devops_cli_project_prs_total",
    InstrumentKind.GAUGE,
    "1",
    "Project pull requests merged by release",
)
PROJECT_CI_RUNS_TOTAL = Instrument(
    "devops_cli_project_ci_runs_total",
    InstrumentKind.GAUGE,
    "1",
    "CI workflow runs by name, status and conclusion",
)
PROJECT_ITEMS_TOTAL = Instrument(
    "devops_cli_project_items_total",
    InstrumentKind.GAUGE,
    "1",
    "Project items by milestone, type, priority and state",
)
PROJECT_RELEASE_INTERVAL_DAYS = Instrument(
    "devops_cli_project_release_interval_days",
    InstrumentKind.HISTOGRAM,
    "d",
    "Days elapsed between consecutive project releases",
)
PROJECT_TRAFFIC_VIEWS_TOTAL = Instrument(
    "devops_cli_project_traffic_views_total",
    InstrumentKind.GAUGE,
    "1",
    "GitHub repository total page views count",
)
PROJECT_TRAFFIC_VIEWS_UNIQUES_TOTAL = Instrument(
    "devops_cli_project_traffic_views_uniques_total",
    InstrumentKind.GAUGE,
    "1",
    "GitHub repository unique visitors count",
)
PROJECT_TRAFFIC_CLONES_TOTAL = Instrument(
    "devops_cli_project_traffic_clones_total",
    InstrumentKind.GAUGE,
    "1",
    "GitHub repository total git clones count",
)
PROJECT_TRAFFIC_CLONES_UNIQUES_TOTAL = Instrument(
    "devops_cli_project_traffic_clones_uniques_total",
    InstrumentKind.GAUGE,
    "1",
    "GitHub repository unique cloners count",
)
PROJECT_TRAFFIC_REFERRERS_TOTAL = Instrument(
    "devops_cli_project_traffic_referrers_total",
    InstrumentKind.GAUGE,
    "1",
    "GitHub repository traffic referrals count by referrer source",
)
PROJECT_TRAFFIC_PATHS_TOTAL = Instrument(
    "devops_cli_project_traffic_paths_total",
    InstrumentKind.GAUGE,
    "1",
    "GitHub repository traffic page views by content path",
)
PROJECT_STARS_TOTAL = Instrument(
    "devops_cli_project_stars_total",
    InstrumentKind.GAUGE,
    "1",
    "GitHub repository stargazers count",
)
PROJECT_FORKS_TOTAL = Instrument(
    "devops_cli_project_forks_total",
    InstrumentKind.GAUGE,
    "1",
    "GitHub repository forks count",
)
UPSTREAM_SERVICE_STATUS = Instrument(
    "devops_cli_upstream_service_status",
    InstrumentKind.GAUGE,
    "1",
    "Upstream cloud service operational status severity code (0=none/operational, 1=minor, 2=major, 3=critical) by service and indicator",
)
UPSTREAM_COMPONENT_STATUS = Instrument(
    "devops_cli_upstream_component_status",
    InstrumentKind.GAUGE,
    "1",
    "Upstream cloud service component status code (0=operational, 1=degraded, 2=partial_outage, 3=major_outage) by service and component",
)

INSTRUMENTS: tuple[Instrument, ...] = (
    COMMAND_TOTAL,
    COMMAND_DURATION,
    REVIEW_DURATION,
    FINDINGS_TOTAL,
    AI_REQUESTS_TOTAL,
    AI_TOKENS_TOTAL,
    AI_SPEND_USD_TOTAL,
    AI_LOCAL_COST_EQUIVALENT_USD_TOTAL,
    AI_JSON_REPAIRS_TOTAL,
    AI_GATEWAY_SLOT_WAIT,
    RAG_QUERY_DURATION,
    QDRANT_RETRIES_TOTAL,
    RAG_POINTS,
    PROJECT_RELEASES_TOTAL,
    PROJECT_COMMITS_TOTAL,
    PROJECT_PRS_TOTAL,
    PROJECT_CI_RUNS_TOTAL,
    PROJECT_ITEMS_TOTAL,
    PROJECT_RELEASE_INTERVAL_DAYS,
    PROJECT_TRAFFIC_VIEWS_TOTAL,
    PROJECT_TRAFFIC_VIEWS_UNIQUES_TOTAL,
    PROJECT_TRAFFIC_CLONES_TOTAL,
    PROJECT_TRAFFIC_CLONES_UNIQUES_TOTAL,
    PROJECT_TRAFFIC_REFERRERS_TOTAL,
    PROJECT_TRAFFIC_PATHS_TOTAL,
    PROJECT_STARS_TOTAL,
    PROJECT_FORKS_TOTAL,
    UPSTREAM_SERVICE_STATUS,
    UPSTREAM_COMPONENT_STATUS,
)


def emit(instrument: Instrument, value: float, attributes: dict[str, Any] | None = None) -> None:
    """Add to a counter, record a gauge, or observe a histogram value."""
    from devops_cli.telemetry.tracer import get_tracer

    tracer = get_tracer()
    if instrument.kind is InstrumentKind.COUNTER:
        tracer.increment_counter(
            instrument.name, value, unit=instrument.unit, attributes=attributes
        )
    elif instrument.kind is InstrumentKind.GAUGE:
        tracer.record_gauge(instrument.name, value, unit=instrument.unit, attributes=attributes)
    else:
        tracer.record_histogram(
            instrument.name,
            value,
            unit=instrument.unit,
            attributes=attributes,
        )


def backend_name(served_by: str | None) -> str:
    """A serving backend's short name: its host's first label, e.g. `ollama-16gib` or `ollama-0`."""
    if not served_by:
        return ""
    from devops_cli.http.urls import extract_domain_target

    host = extract_domain_target(served_by) or served_by
    return host.split(".", 1)[0]


__all__ = [
    "AI_GATEWAY_SLOT_WAIT",
    "AI_JSON_REPAIRS_TOTAL",
    "AI_LOCAL_COST_EQUIVALENT_USD_TOTAL",
    "AI_REQUESTS_TOTAL",
    "AI_SPEND_USD_TOTAL",
    "AI_TOKENS_TOTAL",
    "COMMAND_DURATION",
    "COMMAND_TOTAL",
    "FINDINGS_TOTAL",
    "INSTRUMENTS",
    "PROJECT_CI_RUNS_TOTAL",
    "PROJECT_COMMITS_TOTAL",
    "PROJECT_FORKS_TOTAL",
    "PROJECT_ITEMS_TOTAL",
    "PROJECT_PRS_TOTAL",
    "PROJECT_RELEASES_TOTAL",
    "PROJECT_RELEASE_INTERVAL_DAYS",
    "PROJECT_STARS_TOTAL",
    "PROJECT_TRAFFIC_CLONES_TOTAL",
    "PROJECT_TRAFFIC_CLONES_UNIQUES_TOTAL",
    "PROJECT_TRAFFIC_PATHS_TOTAL",
    "PROJECT_TRAFFIC_REFERRERS_TOTAL",
    "PROJECT_TRAFFIC_VIEWS_TOTAL",
    "PROJECT_TRAFFIC_VIEWS_UNIQUES_TOTAL",
    "QDRANT_RETRIES_TOTAL",
    "RAG_POINTS",
    "RAG_QUERY_DURATION",
    "REVIEW_DURATION",
    "UPSTREAM_COMPONENT_STATUS",
    "UPSTREAM_SERVICE_STATUS",
    "Instrument",
    "InstrumentKind",
    "backend_name",
    "emit",
]
