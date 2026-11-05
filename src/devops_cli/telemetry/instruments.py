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

from devops_cli.config.constants import CONST_METRIC_LABEL_MAX_LENGTH, CONST_METRIC_LABEL_UNSAFE_RE


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
SUBCOMMAND_DURATION = Instrument(
    "devops_cli_subcommand_duration_seconds",
    InstrumentKind.HISTOGRAM,
    "s",
    "Sub-command wall time, by command group, sub-command (the command path below devops, such as pr threads reply) and status: ok or error",
)
SUBPROCESS_DURATION = Instrument(
    "devops_cli_subprocess_duration_seconds",
    InstrumentKind.HISTOGRAM,
    "s",
    "Wall time of a program that devops-cli ran, by program and status: ok or error",
)
TELEMETRY_TESTS_TOTAL = Instrument(
    "devops_cli_telemetry_tests_total",
    InstrumentKind.COUNTER,
    "1",
    "Test points that devops telemetry test sent, to show that metrics reach the collector",
)
CI_CHECKS_TOTAL = Instrument(
    "devops_cli_ci_checks_total",
    InstrumentKind.COUNTER,
    "1",
    "Checks that devops ci ran, by step and outcome: pass or fail",
)
CI_GATE_SLOT_WAIT = Instrument(
    "devops_cli_ci_gate_slot_wait_seconds",
    InstrumentKind.HISTOGRAM,
    "s",
    "Time a devops ci run waited for a free gate slot before its checks started",
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
    "provider, model, server, backend and local: true when a local model ran them. The AI spend "
    "dashboard prices local tokens as savings at the reference price that its constant "
    "reference_price_usd_per_token holds for their operation and type",
)
AI_SPEND_USD_TOTAL = Instrument(
    "devops_cli_ai_spend_usd_total",
    InstrumentKind.COUNTER,
    "USD",
    "Approximate LLM and embedding spend, by operation, provider, model, server and backend. "
    "Each request that a model answers adds to it, and a local request adds 0. A hosted gateway "
    "call is priced at the deployment model that the gateway names, and its model label is the "
    "model that the client asked for, such as the route name",
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
AI_OLLAMA_SLOT_WAIT = Instrument(
    "devops_cli_ai_ollama_slot_wait_seconds",
    InstrumentKind.HISTOGRAM,
    "s",
    "Time a call to Ollama waited in this process for a slot on one of its nodes, by priority "
    "(high, normal or as_available) and outcome: ok once it held one, or timeout",
)
AI_CHAT_DURATION = Instrument(
    "devops_cli_ai_chat_duration_seconds",
    InstrumentKind.HISTOGRAM,
    "s",
    "LLM chat call wall time, by provider and model, from the request to the reply. A gateway "
    "call's time includes its wait for a backend slot",
)
AI_STRUCTURED_ATTEMPTS_TOTAL = Instrument(
    "devops_cli_ai_structured_attempts_total",
    InstrumentKind.COUNTER,
    "1",
    "Structured-output attempts, by model and outcome: valid when the reply matched its schema, "
    "else invalid. Each invalid attempt but the last is retried",
)
AI_PREWARMS_TOTAL = Instrument(
    "devops_cli_ai_prewarms_total",
    InstrumentKind.COUNTER,
    "1",
    "devops ai prewarm runs, by model, evict (true when the run unloaded the model) and outcome: "
    "ok or failed",
)
AI_GATEWAY_PROBE_DURATION = Instrument(
    "devops_cli_ai_gateway_probe_duration_seconds",
    InstrumentKind.HISTOGRAM,
    "s",
    "Time a health probe of the LLM gateway took",
)
AI_GATEWAY_HEALTHY = Instrument(
    "devops_cli_ai_gateway_healthy",
    InstrumentKind.GAUGE,
    "1",
    "Whether the last health probe of the LLM gateway passed: 1, or 0",
)
AI_GATEWAY_FAILOVERS_TOTAL = Instrument(
    "devops_cli_ai_gateway_failovers_total",
    InstrumentKind.COUNTER,
    "1",
    "Failovers of a gateway model alias to its fallback, by virtual model and simulate: true "
    "for a simulated failover",
)
AI_CAPABILITY_GATE_TOTAL = Instrument(
    "devops_cli_ai_capability_gate_total",
    InstrumentKind.COUNTER,
    "1",
    "Failovers to a model below the capability tier of their role, by role, model and decision: "
    "rejection when the gate refused it, or override when --force let it through",
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
GITHUB_REQUESTS_TOTAL = Instrument(
    "devops_cli_github_requests_total",
    InstrumentKind.COUNTER,
    "1",
    "GitHub requests the rate limiter paced, each attempt and retry once, by resource, method, "
    "repo and row. The resource is the rate limit resource the request spends, such as core, "
    "graphql or search. The method is the HTTP method; a GraphQL request is a POST, and a gh "
    "command other than gh api is a POST when it writes and a GET when it reads. The repo is the "
    "repository of the roadmap Service worker that sent the request, one of service.repos, and "
    "the row is the job row that sent it, such as metrics, intake, refine or alternatives; each is "
    "other outside a worker or a row. A gh command and a request of the GitHub session both count",
)
GITHUB_THROTTLE_WAIT = Instrument(
    "devops_cli_github_throttle_wait_seconds",
    InstrumentKind.HISTOGRAM,
    "s",
    "Time devops-cli waited before it sent a refused GitHub request again, by resource: one "
    "observation for each throttle. GitHub refused the request with a rate limit, or the GitHub "
    "session got a 5xx for a read",
)
GITHUB_GRAPHQL_POINTS_TOTAL = Instrument(
    "devops_cli_github_graphql_points_total",
    InstrumentKind.COUNTER,
    "1",
    "GraphQL points that GitHub reported each answer cost in its rateLimit field",
)
FIRECRAWL_SEARCHES_TOTAL = Instrument(
    "devops_cli_firecrawl_searches_total",
    InstrumentKind.COUNTER,
    "1",
    "Firecrawl web searches, by result: ok, the HTTP status of a search that Firecrawl refused, "
    "such as 402 when the account has no credits or 429 at its rate limit, or error for a search "
    "that got no answer or a reply with no web results",
)
ROADMAP_REFINE_COMMENTS_CAPPED_TOTAL = Instrument(
    "devops_cli_roadmap_refine_comments_capped_total",
    InstrumentKind.COUNTER,
    "1",
    "Refine comments that the cap on refine's comments on one item in 24 hours stopped: one "
    "count for each newest comment on an item that the cap left with no answer. The item waits "
    "on a person and takes no place under the round's limit. A later round that finds no newer "
    "comment on the item does not count it again",
)
ROADMAP_ALTERNATIVES_TOTAL = Instrument(
    "devops_cli_roadmap_alternatives_total",
    InstrumentKind.COUNTER,
    "1",
    "Checks of open items for an open tool that covers them, by verdict: covers, partly, none or "
    "not-applicable. One count for each check that the alternatives job writes to an item. A "
    "check that fails, or that the job skips because a person changed the item, counts nothing",
)
ROADMAP_STAGE_TOTAL = Instrument(
    "devops_cli_roadmap_stage_total",
    InstrumentKind.COUNTER,
    "1",
    "Items that a stage round handled, one count for each item, by result: staged for an item "
    "written as a branch and a draft pull request, needs_split for an item stopped on a task "
    "group over the budget, failed for an item that failed in the plan or in the writes, and "
    "skipped for an item the job left out with a reason. A plan with no write counts nothing",
)
EMBEDDING_CACHE_LOOKUPS_TOTAL = Instrument(
    "devops_cli_embedding_cache_lookups_total",
    InstrumentKind.COUNTER,
    "1",
    "Embedding cache lookups, one for each text that an embedding request gets, by result: hit "
    "or miss. A hit names its tier: memory for the cache of the process, or valkey",
)
EMBEDDING_CACHE_SIZE = Instrument(
    "devops_cli_embedding_cache_size",
    InstrumentKind.GAUGE,
    "1",
    "Embeddings that the memory cache of the process held after its last embedding request",
)
RAG_EMBEDDING_BATCH_SIZE = Instrument(
    "devops_cli_rag_embedding_batch_size",
    InstrumentKind.GAUGE,
    "1",
    "Texts in each embedding request after the last change of the adaptive batch size",
)
RAG_EMBEDDING_BATCH_RESIZES_TOTAL = Instrument(
    "devops_cli_rag_embedding_batch_resizes_total",
    InstrumentKind.COUNTER,
    "1",
    "Changes of the adaptive embedding batch size, by action: additive_increase after enough "
    "fast batches, or multiplicative_decrease after a slow or failed batch",
)
RAG_DRIFT_SCORE = Instrument(
    "devops_cli_rag_drift_score",
    InstrumentKind.GAUGE,
    "1",
    "Share of a project's files that changed, were added or were deleted since its last index, "
    "from its last drift check, by project. A drifted knowledge base scores 1",
)
RAG_DRIFT_DETECTED = Instrument(
    "devops_cli_rag_drift_detected",
    InstrumentKind.GAUGE,
    "1",
    "Whether the last drift check of a project found drift in its files, its git head or its "
    "knowledge base: 1, or 0, by project",
)
RAG_INVESTIGATIONS_TOTAL = Instrument(
    "devops_cli_rag_investigations_total",
    InstrumentKind.COUNTER,
    "1",
    "RAG context retrievals that finished, by outcome: found when they returned context, or empty",
)
RAG_STOPS_TOTAL = Instrument(
    "devops_cli_rag_stops_total",
    InstrumentKind.COUNTER,
    "1",
    "Processes that turned RAG off for the rest of their run after an embedding failure",
)
VULNERABILITY_LOOKUPS_TOTAL = Instrument(
    "devops_cli_vulnerability_lookups_total",
    InstrumentKind.COUNTER,
    "1",
    "Packages looked up in a vulnerability database, by source, status and batch: true when one "
    "batch request looked them up",
)
THREAT_INTEL_LOOKUPS_TOTAL = Instrument(
    "devops_cli_threat_intel_lookups_total",
    InstrumentKind.COUNTER,
    "1",
    "Domains that a threat-intelligence source was asked about, by source and status: ok, "
    "unavailable or failed. A domain that the cache answered is not counted",
)

PROJECT_RELEASES = Instrument(
    "devops_cli_project_releases",
    InstrumentKind.GAUGE,
    "1",
    "Total project releases tracked",
)
PROJECT_COMMITS = Instrument(
    "devops_cli_project_commits",
    InstrumentKind.GAUGE,
    "1",
    "Project commits count by release",
)
PROJECT_PRS = Instrument(
    "devops_cli_project_prs",
    InstrumentKind.GAUGE,
    "1",
    "Project pull requests merged by release",
)
PROJECT_CI_RUNS = Instrument(
    "devops_cli_project_ci_runs",
    InstrumentKind.GAUGE,
    "1",
    "CI workflow runs by name, status and conclusion",
)
PROJECT_ITEMS = Instrument(
    "devops_cli_project_items",
    InstrumentKind.GAUGE,
    "1",
    "Roadmap items, the issues with a priority label, by release, state, type and "
    "priority. "
    "The release is the first v* tag whose commits close the item. "
    "A label is empty when the item has no value for it",
)
PROJECT_ITEM_LABELS = ("release", "state", "type", "priority")
"""The labels of `PROJECT_ITEMS`, in the order the dashboard names them."""
PROJECT_RELEASE_INTERVAL_DAYS = Instrument(
    "devops_cli_project_release_interval_days",
    InstrumentKind.HISTOGRAM,
    "d",
    "Days elapsed between consecutive project releases",
)
PROJECT_TRAFFIC_VIEWS = Instrument(
    "devops_cli_project_traffic_views",
    InstrumentKind.GAUGE,
    "1",
    "GitHub repository total page views count",
)
PROJECT_TRAFFIC_VIEWS_UNIQUES = Instrument(
    "devops_cli_project_traffic_views_uniques",
    InstrumentKind.GAUGE,
    "1",
    "GitHub repository unique visitors count",
)
PROJECT_TRAFFIC_CLONES = Instrument(
    "devops_cli_project_traffic_clones",
    InstrumentKind.GAUGE,
    "1",
    "GitHub repository total git clones count",
)
PROJECT_TRAFFIC_CLONES_UNIQUES = Instrument(
    "devops_cli_project_traffic_clones_uniques",
    InstrumentKind.GAUGE,
    "1",
    "GitHub repository unique cloners count",
)
PROJECT_TRAFFIC_REFERRERS = Instrument(
    "devops_cli_project_traffic_referrers",
    InstrumentKind.GAUGE,
    "1",
    "GitHub repository traffic referrals count by referrer source",
)
PROJECT_TRAFFIC_PATHS = Instrument(
    "devops_cli_project_traffic_paths",
    InstrumentKind.GAUGE,
    "1",
    "GitHub repository traffic page views by content path",
)
PROJECT_STARS = Instrument(
    "devops_cli_project_stars",
    InstrumentKind.GAUGE,
    "1",
    "GitHub repository stargazers count",
)
PROJECT_FORKS = Instrument(
    "devops_cli_project_forks",
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
    SUBCOMMAND_DURATION,
    SUBPROCESS_DURATION,
    TELEMETRY_TESTS_TOTAL,
    CI_CHECKS_TOTAL,
    CI_GATE_SLOT_WAIT,
    REVIEW_DURATION,
    FINDINGS_TOTAL,
    AI_REQUESTS_TOTAL,
    AI_TOKENS_TOTAL,
    AI_SPEND_USD_TOTAL,
    AI_JSON_REPAIRS_TOTAL,
    AI_GATEWAY_SLOT_WAIT,
    AI_OLLAMA_SLOT_WAIT,
    AI_CHAT_DURATION,
    AI_STRUCTURED_ATTEMPTS_TOTAL,
    AI_PREWARMS_TOTAL,
    AI_GATEWAY_PROBE_DURATION,
    AI_GATEWAY_HEALTHY,
    AI_GATEWAY_FAILOVERS_TOTAL,
    AI_CAPABILITY_GATE_TOTAL,
    RAG_QUERY_DURATION,
    QDRANT_RETRIES_TOTAL,
    RAG_POINTS,
    GITHUB_REQUESTS_TOTAL,
    GITHUB_THROTTLE_WAIT,
    GITHUB_GRAPHQL_POINTS_TOTAL,
    FIRECRAWL_SEARCHES_TOTAL,
    ROADMAP_REFINE_COMMENTS_CAPPED_TOTAL,
    ROADMAP_ALTERNATIVES_TOTAL,
    ROADMAP_STAGE_TOTAL,
    EMBEDDING_CACHE_LOOKUPS_TOTAL,
    EMBEDDING_CACHE_SIZE,
    RAG_EMBEDDING_BATCH_SIZE,
    RAG_EMBEDDING_BATCH_RESIZES_TOTAL,
    RAG_DRIFT_SCORE,
    RAG_DRIFT_DETECTED,
    RAG_INVESTIGATIONS_TOTAL,
    RAG_STOPS_TOTAL,
    VULNERABILITY_LOOKUPS_TOTAL,
    THREAT_INTEL_LOOKUPS_TOTAL,
    PROJECT_RELEASES,
    PROJECT_COMMITS,
    PROJECT_PRS,
    PROJECT_CI_RUNS,
    PROJECT_ITEMS,
    PROJECT_RELEASE_INTERVAL_DAYS,
    PROJECT_TRAFFIC_VIEWS,
    PROJECT_TRAFFIC_VIEWS_UNIQUES,
    PROJECT_TRAFFIC_CLONES,
    PROJECT_TRAFFIC_CLONES_UNIQUES,
    PROJECT_TRAFFIC_REFERRERS,
    PROJECT_TRAFFIC_PATHS,
    PROJECT_STARS,
    PROJECT_FORKS,
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


def bounded_label(value: str) -> str:
    """A label value that a caller set, cut to a safe length and set of characters.

    Each character outside `CONST_METRIC_LABEL_UNSAFE_RE`'s allowed set becomes `_`, and the
    text keeps at most `CONST_METRIC_LABEL_MAX_LENGTH` characters.
    """
    return CONST_METRIC_LABEL_UNSAFE_RE.sub("_", value)[:CONST_METRIC_LABEL_MAX_LENGTH]


def backend_name(served_by: str | None) -> str:
    """A serving backend's short name: its host's first label, e.g. `ollama-16gib` or `ollama-0`."""
    if not served_by:
        return ""
    from devops_cli.http.urls import extract_domain_target

    host = extract_domain_target(served_by) or served_by
    return host.split(".", 1)[0]


__all__ = [
    "AI_CAPABILITY_GATE_TOTAL",
    "AI_CHAT_DURATION",
    "AI_GATEWAY_FAILOVERS_TOTAL",
    "AI_GATEWAY_HEALTHY",
    "AI_GATEWAY_PROBE_DURATION",
    "AI_GATEWAY_SLOT_WAIT",
    "AI_JSON_REPAIRS_TOTAL",
    "AI_OLLAMA_SLOT_WAIT",
    "AI_PREWARMS_TOTAL",
    "AI_REQUESTS_TOTAL",
    "AI_SPEND_USD_TOTAL",
    "AI_STRUCTURED_ATTEMPTS_TOTAL",
    "AI_TOKENS_TOTAL",
    "CI_CHECKS_TOTAL",
    "CI_GATE_SLOT_WAIT",
    "COMMAND_DURATION",
    "COMMAND_TOTAL",
    "EMBEDDING_CACHE_LOOKUPS_TOTAL",
    "EMBEDDING_CACHE_SIZE",
    "FINDINGS_TOTAL",
    "FIRECRAWL_SEARCHES_TOTAL",
    "GITHUB_GRAPHQL_POINTS_TOTAL",
    "GITHUB_REQUESTS_TOTAL",
    "GITHUB_THROTTLE_WAIT",
    "INSTRUMENTS",
    "PROJECT_CI_RUNS",
    "PROJECT_COMMITS",
    "PROJECT_FORKS",
    "PROJECT_ITEMS",
    "PROJECT_ITEM_LABELS",
    "PROJECT_PRS",
    "PROJECT_RELEASES",
    "PROJECT_RELEASE_INTERVAL_DAYS",
    "PROJECT_STARS",
    "PROJECT_TRAFFIC_CLONES",
    "PROJECT_TRAFFIC_CLONES_UNIQUES",
    "PROJECT_TRAFFIC_PATHS",
    "PROJECT_TRAFFIC_REFERRERS",
    "PROJECT_TRAFFIC_VIEWS",
    "PROJECT_TRAFFIC_VIEWS_UNIQUES",
    "QDRANT_RETRIES_TOTAL",
    "RAG_DRIFT_DETECTED",
    "RAG_DRIFT_SCORE",
    "RAG_EMBEDDING_BATCH_RESIZES_TOTAL",
    "RAG_EMBEDDING_BATCH_SIZE",
    "RAG_INVESTIGATIONS_TOTAL",
    "RAG_POINTS",
    "RAG_QUERY_DURATION",
    "RAG_STOPS_TOTAL",
    "REVIEW_DURATION",
    "ROADMAP_ALTERNATIVES_TOTAL",
    "ROADMAP_REFINE_COMMENTS_CAPPED_TOTAL",
    "ROADMAP_STAGE_TOTAL",
    "SUBCOMMAND_DURATION",
    "SUBPROCESS_DURATION",
    "TELEMETRY_TESTS_TOTAL",
    "THREAT_INTEL_LOOKUPS_TOTAL",
    "UPSTREAM_COMPONENT_STATUS",
    "UPSTREAM_SERVICE_STATUS",
    "VULNERABILITY_LOOKUPS_TOTAL",
    "Instrument",
    "InstrumentKind",
    "backend_name",
    "bounded_label",
    "emit",
]
