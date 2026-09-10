"""Native LogQL stream parser, evaluator, and cluster logging engine."""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

import httpx2

from devops_cli.core.process import run_subprocess
from devops_cli.core.validation import validate_url_egress
from devops_cli.dry_run import is_dry_run, render_dry_run_result
from devops_cli.exceptions.k8s import KubernetesLoggingError
from devops_cli.telemetry.tracer import trace_span

logger = logging.getLogger(__name__)

DEFAULT_LOKI_URL = "http://loki.logging.svc.cluster.local:3100"
_TRACE_ID_REGEX = re.compile(
    r'(?:trace_id|traceId|traceID)[=:"\s]+([0-9a-fA-F]{16,32})', re.IGNORECASE
)
_LOGFMT_REGEX = re.compile(r'([a-zA-Z0-9_\-\.]+)=(?:"([^"]*)"|([^\s]+))')
_SELECTOR_REGEX = re.compile(r'([a-zA-Z0-9_\-\.]+)\s*=\s*"([^"]*)"')
_FILTER_REGEX = re.compile(r'(\|=|\!=|\|~|!~)\s*"([^"]*)"')


class FilterOp(StrEnum):
    """LogQL line filter operations."""

    CONTAINS = "|="
    NOT_CONTAINS = "!="
    REGEX_MATCH = "|~"
    NOT_REGEX_MATCH = "!~"


@dataclass(frozen=True)
class LogQLFilter:
    """A single LogQL line filter."""

    op: FilterOp
    pattern: str


@dataclass
class LogQLQuery:
    """Parsed LogQL expression containing selectors, filters, and pipeline format."""

    raw_query: str
    selectors: dict[str, str] = field(default_factory=dict)
    filters: list[LogQLFilter] = field(default_factory=list)
    format_pipeline: str | None = None


@dataclass
class LogEntry:
    """A single parsed and correlated log entry."""

    timestamp: str
    line: str
    stream_labels: dict[str, str] = field(default_factory=dict)
    fields: dict[str, Any] = field(default_factory=dict)
    trace_id: str | None = None


@dataclass
class LogQueryResult:
    """Result of evaluating a LogQL query against Loki or Kubernetes fallback."""

    query: LogQLQuery
    entries: list[LogEntry] = field(default_factory=list)
    source: str = "loki"
    duration_ms: float = 0.0


def extract_trace_id(line: str) -> str | None:
    """Extract OpenTelemetry trace ID from log line if present."""
    match = _TRACE_ID_REGEX.search(line)
    return match.group(1).lower() if match else None


def extract_fields_json(line: str) -> dict[str, Any]:
    """Safely parse JSON formatted log line into dictionary."""
    start = line.find("{")
    end = line.rfind("}")
    if start == -1 or end == -1 or start >= end:
        return {}
    try:
        data = json.loads(line[start : end + 1])
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def extract_fields_logfmt(line: str) -> dict[str, str]:
    """Parse logfmt key=value pairs into dictionary."""
    matches = _LOGFMT_REGEX.findall(line)
    return {k: v1 if v1 else v2 for k, v1, v2 in matches}


def _parse_stream_selectors(selector_part: str) -> dict[str, str]:
    """Extract stream label selectors from LogQL braces block {app="x", ...}."""
    content = selector_part.strip().lstrip("{").rstrip("}").strip()
    if not content:
        return {}
    return dict(_SELECTOR_REGEX.findall(content))


def _parse_filters_and_pipeline(
    remaining_text: str,
) -> tuple[list[LogQLFilter], str | None]:
    """Parse line filters and pipeline stages from query body."""
    filters: list[LogQLFilter] = []
    pipeline: str | None = None

    if "| json" in remaining_text:
        pipeline = "json"
        remaining_text = remaining_text.replace("| json", "")
    elif "| logfmt" in remaining_text:
        pipeline = "logfmt"
        remaining_text = remaining_text.replace("| logfmt", "")

    for op_str, pattern in _FILTER_REGEX.findall(remaining_text):
        try:
            op = FilterOp(op_str)
            if op in (FilterOp.REGEX_MATCH, FilterOp.NOT_REGEX_MATCH):
                try:
                    re.compile(pattern)
                except re.error as exc:
                    raise KubernetesLoggingError(
                        f"Invalid LogQL regular expression '{pattern}': {exc}",
                        query=pattern,
                    ) from exc
            filters.append(LogQLFilter(op=op, pattern=pattern))
        except ValueError:
            continue

    return filters, pipeline


def parse_logql_query(query_str: str) -> LogQLQuery:
    """Parse raw LogQL string into structured LogQLQuery model."""
    cleaned = query_str.strip()
    if not cleaned:
        return LogQLQuery(raw_query="")

    if cleaned.startswith("{") and "}" in cleaned:
        brace_end = cleaned.find("}")
        selector_part = cleaned[: brace_end + 1]
        remaining = cleaned[brace_end + 1 :].strip()
        selectors = _parse_stream_selectors(selector_part)
        filters, pipeline = _parse_filters_and_pipeline(remaining)
        return LogQLQuery(
            raw_query=cleaned,
            selectors=selectors,
            filters=filters,
            format_pipeline=pipeline,
        )

    # Plain text search without stream selector
    filters, pipeline = _parse_filters_and_pipeline(cleaned)
    if not filters and cleaned:
        filters = [LogQLFilter(op=FilterOp.CONTAINS, pattern=cleaned)]
    return LogQLQuery(
        raw_query=cleaned,
        selectors={},
        filters=filters,
        format_pipeline=pipeline,
    )


def _matches_single_filter(line: str, f: LogQLFilter) -> bool:
    """Evaluate a single LogQL filter condition against a log line."""
    if f.op == FilterOp.CONTAINS:
        return f.pattern in line
    if f.op == FilterOp.NOT_CONTAINS:
        return f.pattern not in line
    if f.op == FilterOp.REGEX_MATCH:
        try:
            return bool(re.search(f.pattern, line))
        except re.error as exc:
            raise KubernetesLoggingError(
                f"Invalid regex pattern '{f.pattern}': {exc}", query=f.pattern
            ) from exc
    if f.op == FilterOp.NOT_REGEX_MATCH:
        try:
            return not bool(re.search(f.pattern, line))
        except re.error as exc:
            raise KubernetesLoggingError(
                f"Invalid regex pattern '{f.pattern}': {exc}", query=f.pattern
            ) from exc
    return True


def line_matches_query(line: str, query: LogQLQuery) -> bool:
    """Check whether a log line satisfies all filter predicates in a query."""
    return all(_matches_single_filter(line, f) for f in query.filters)


def _extract_entry_fields(line: str, pipeline: str | None) -> dict[str, Any]:
    """Extract structured fields based on configured format pipeline."""
    if pipeline == "json":
        return extract_fields_json(line)
    if pipeline == "logfmt":
        return extract_fields_logfmt(line)
    # Automatic fallback if line starts with {
    if line.strip().startswith("{"):
        return extract_fields_json(line)
    return {}


def evaluate_log_lines(
    lines: list[str],
    query: LogQLQuery,
    default_labels: dict[str, str] | None = None,
) -> list[LogEntry]:
    """Evaluate and enrich raw log lines using parsed LogQL criteria."""
    results: list[LogEntry] = []
    labels = default_labels or {}

    for line in lines:
        stripped = line.strip()
        if not stripped or not line_matches_query(stripped, query):
            continue

        trace_id = extract_trace_id(stripped)
        fields = _extract_entry_fields(stripped, query.format_pipeline)
        if not trace_id and isinstance(fields, dict):
            for k in ("trace_id", "traceId", "traceID"):
                if k in fields:
                    trace_id = str(fields[k])
                    break

        results.append(
            LogEntry(
                timestamp="",
                line=stripped,
                stream_labels=dict(labels),
                fields=fields,
                trace_id=trace_id,
            )
        )
    return results


def _get_matching_pods(namespace: str, selectors: dict[str, str]) -> list[str]:
    """Discover active pod names matching namespace and stream selectors."""
    cmd = ["kubectl", "get", "pods", "-n", namespace, "-o", "jsonpath={.items[*].metadata.name}"]
    label_filters = [f"{k}={v}" for k, v in selectors.items() if k not in ("namespace", "pod")]
    if label_filters:
        cmd.extend(["-l", ",".join(label_filters)])
    proc = run_subprocess(cmd, check=False)
    if proc.returncode == 0 and proc.stdout.strip():
        return proc.stdout.strip().split()
    return []


def execute_kubectl_logql(
    query: LogQLQuery,
    namespace: str = "default",
    limit: int = 100,
) -> LogQueryResult:
    """Query logs via kubectl across matching pods with in-memory LogQL filtering."""
    ns = query.selectors.get("namespace", namespace)
    if "pod" in query.selectors:
        pods = [query.selectors["pod"]]
    else:
        pods = _get_matching_pods(ns, query.selectors)

    # If stream selectors were specified (e.g. app="x") and no pods matched, return empty result
    if not pods and query.selectors:
        return LogQueryResult(
            query=query,
            entries=[],
            source="k8s_fallback",
            duration_ms=0.0,
        )
    if not pods:
        pods = _get_matching_pods(ns, {})

    all_entries: list[LogEntry] = []
    for pod in pods[:5]:
        cmd = ["kubectl", "logs", pod, "-n", ns, f"--tail={limit}"]
        proc = run_subprocess(cmd, check=False)
        if proc.returncode != 0:
            continue
        raw_lines = proc.stdout.splitlines()
        entries = evaluate_log_lines(
            raw_lines,
            query,
            default_labels={"pod": pod, "namespace": ns, **query.selectors},
        )
        all_entries.extend(entries)
        if len(all_entries) >= limit:
            break

    return LogQueryResult(
        query=query,
        entries=all_entries[:limit],
        source="k8s_fallback",
        duration_ms=0.0,
    )


def execute_loki_query(
    query: LogQLQuery,
    loki_url: str = DEFAULT_LOKI_URL,
    limit: int = 100,
    since: str = "1h",
) -> LogQueryResult:
    """Execute LogQL query against Loki REST API (/loki/api/v1/query_range)."""
    valid_url = validate_url_egress(loki_url, purpose="Loki", allow_private=True)
    endpoint = f"{valid_url.rstrip('/')}/loki/api/v1/query_range"
    params: dict[str, Any] = {
        "query": query.raw_query,
        "limit": limit,
        "since": since,
        "direction": "BACKWARD",
    }
    try:
        resp = httpx2.get(endpoint, params=params, timeout=10.0)
    except (httpx2.ConnectError, httpx2.ConnectTimeout, httpx2.NetworkError) as conn_err:
        raise ConnectionError(f"Loki connection failed: {conn_err}") from conn_err

    if resp.status_code == 400:
        raise KubernetesLoggingError(
            f"Invalid LogQL query: {resp.text.strip()}",
            status_code=400,
            query=query.raw_query,
        )
    if resp.status_code != 200:
        raise KubernetesLoggingError(
            f"Loki query failed with HTTP {resp.status_code}: {resp.text.strip()}",
            status_code=resp.status_code,
            query=query.raw_query,
        )

    payload = resp.json()
    entries: list[LogEntry] = []
    data = payload.get("data", {})
    streams = data.get("result", [])

    for s in streams:
        stream_labels = s.get("stream", {})
        values = s.get("values", [])
        for val in values:
            if len(val) >= 2:
                ts, raw_line = val[0], val[1]
                trace_id = extract_trace_id(raw_line)
                fields = _extract_entry_fields(raw_line, query.format_pipeline)
                entries.append(
                    LogEntry(
                        timestamp=ts,
                        line=raw_line,
                        stream_labels=stream_labels,
                        fields=fields,
                        trace_id=trace_id,
                    )
                )

    return LogQueryResult(
        query=query,
        entries=entries[:limit],
        source="loki",
        duration_ms=0.0,
    )


def execute_logql_query(
    query: LogQLQuery | str,
    namespace: str | None = None,
    loki_url: str | None = None,
    limit: int = 100,
    since: str = "1h",
    dry_run: bool = False,
) -> LogQueryResult:
    """High-level query entrypoint with automatic Loki to kubectl fallback."""
    parsed = query if isinstance(query, LogQLQuery) else parse_logql_query(query)
    target_ns = namespace or parsed.selectors.get("namespace", "default")
    url = loki_url or DEFAULT_LOKI_URL

    if dry_run or is_dry_run():
        render_dry_run_result(
            command="devops k8s logs",
            action="logql_query",
            details={
                "query": parsed.raw_query,
                "namespace": target_ns,
                "limit": limit,
                "since": since,
            },
        )
        mock_entry = LogEntry(
            timestamp="2026-09-10T10:00:00Z",
            line=f"[DRY-RUN] Sample log entry matching query '{parsed.raw_query}' trace_id=4bf92f3577b34da6a3ce929d0e0e4736",
            stream_labels={"app": "demo", "namespace": target_ns},
            trace_id="4bf92f3577b34da6a3ce929d0e0e4736",
        )
        return LogQueryResult(query=parsed, entries=[mock_entry], source="dry_run")

    with trace_span("k8s.logql.query", attributes={"query": parsed.raw_query}):
        try:
            return execute_loki_query(parsed, loki_url=url, limit=limit, since=since)
        except (ConnectionError, httpx2.ConnectError, httpx2.TimeoutException) as exc:
            logger.info("Loki unreachable (%s); falling back to kubectl logs stream", exc)
            return execute_kubectl_logql(parsed, namespace=target_ns, limit=limit)
        except KubernetesLoggingError:
            raise
