"""Native LogQL stream parser, evaluator, and cluster logging engine."""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

import httpx2

from devops_cli.config.defaults import (
    DEFAULT_K8S_NAMESPACE,
    DEFAULT_LOG_QUERY_LIMIT,
    DEFAULT_LOG_QUERY_SINCE,
    DEFAULT_LOKI_URL,
)
from devops_cli.core.process import run_subprocess
from devops_cli.core.validation import is_valid_k8s_name, validate_url_egress
from devops_cli.dry_run import is_dry_run, render_dry_run_result
from devops_cli.exceptions import ValidationError
from devops_cli.exceptions.k8s import KubernetesLoggingError
from devops_cli.http.client import new_http_client
from devops_cli.http.egress import EgressLevel
from devops_cli.telemetry.tracer import trace_span

logger = logging.getLogger(__name__)


_TRACE_ID_REGEX = re.compile(
    r'(?:trace_id|traceId|traceID)[=:"\s]+([0-9a-fA-F]{16,32})', re.IGNORECASE
)
_LOGFMT_REGEX = re.compile(r'([a-zA-Z0-9_\-\.]+)=(?:"([^"]*)"|([^\s]+))')
_MATCHER_TOKEN_REGEX = re.compile(
    r'([a-zA-Z0-9_\-\.]+)\s*(=~|!~|!=|=)\s*(?:"([^"\\]*(?:\\.[^"\\]*)*)"|\'([^\'\\]*(?:\\.[^\'\\]*)*)\')'
)
_CONTAINS_FILTER_REGEX = re.compile(
    r'\|=\s*(?:"([^"\\]*(?:\\.[^"\\]*)*)"|\'([^\'\\]*(?:\\.[^\'\\]*)*)\')'
)
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
    return {
        m.group(1): m.group(3) if m.group(3) is not None else m.group(4)
        for m in _MATCHER_TOKEN_REGEX.finditer(content)
        if m.group(2) == "="
    }


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
        return LogQLQuery(raw_query=query_str)

    if cleaned.startswith("{") and "}" in cleaned:
        brace_end = cleaned.find("}")
        selector_part = cleaned[: brace_end + 1]
        remaining = cleaned[brace_end + 1 :].strip()
        selectors = _parse_stream_selectors(selector_part)
        filters, pipeline = _parse_filters_and_pipeline(remaining)
        return LogQLQuery(
            raw_query=query_str,
            selectors=selectors,
            filters=filters,
            format_pipeline=pipeline,
        )

    # Plain text search without stream selector
    filters, pipeline = _parse_filters_and_pipeline(cleaned)
    if not filters and cleaned:
        filters = [LogQLFilter(op=FilterOp.CONTAINS, pattern=cleaned)]
    return LogQLQuery(
        raw_query=query_str,
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


def _validate_fallback_query(raw_query: str) -> tuple[dict[str, str], list[str]]:
    """Verify that the query is supported by kubectl fallback, returning selectors and |= filters."""
    raw = raw_query.strip()
    err_msg = (
        'The kubectl fallback supports only label="value" matchers and |= filters. '
        "Configure loki.url to evaluate this query."
    )
    if not (raw.startswith("{") and "}" in raw):
        raise KubernetesLoggingError(err_msg, query=raw_query)

    brace_end = raw.find("}")
    selector_content = raw[1:brace_end].strip()
    remaining = raw[brace_end + 1 :].strip()

    if not selector_content:
        raise KubernetesLoggingError(err_msg, query=raw_query)

    selectors: dict[str, str] = {}
    for m in _MATCHER_TOKEN_REGEX.finditer(selector_content):
        if m.group(2) != "=":
            raise KubernetesLoggingError(err_msg, query=raw_query)
        selectors[m.group(1)] = m.group(3) if m.group(3) is not None else m.group(4)

    if not selectors:
        raise KubernetesLoggingError(err_msg, query=raw_query)

    reconstructed = _MATCHER_TOKEN_REGEX.sub("", selector_content)
    if reconstructed.replace(",", "").strip():
        raise KubernetesLoggingError(err_msg, query=raw_query)

    if remaining:
        cleaned_remaining = _CONTAINS_FILTER_REGEX.sub("", remaining).strip()
        if cleaned_remaining:
            raise KubernetesLoggingError(err_msg, query=raw_query)

    substring_filters = [
        m.group(1) if m.group(1) is not None else m.group(2)
        for m in _CONTAINS_FILTER_REGEX.finditer(remaining)
    ]
    return selectors, substring_filters


def _build_kubectl_logs_cmd(
    ns: str, selectors: dict[str, str], limit: int, since: str | None
) -> list[str]:
    """Construct argument list for kubectl logs execution."""
    cmd = ["kubectl", "logs", "-n", ns]
    if "pod" in selectors:
        pod = selectors["pod"].removeprefix("pod/")
        if not is_valid_k8s_name(pod):
            raise ValidationError(f"Invalid Kubernetes pod identifier: '{pod}'")
        cmd.append(pod)
    else:
        label_parts = [f"{k}={v}" for k, v in selectors.items() if k != "namespace"]
        if label_parts:
            cmd.extend(["-l", ",".join(label_parts)])

    cmd.append(f"--tail={limit}")
    if since:
        cmd.append(f"--since={since}")
    return cmd


def execute_kubectl_logql(
    query: LogQLQuery,
    namespace: str = DEFAULT_K8S_NAMESPACE,
    limit: int = DEFAULT_LOG_QUERY_LIMIT,
    since: str | None = None,
) -> LogQueryResult:
    """Query logs via kubectl across matching pods using native label selectors."""
    selectors, substring_filters = _validate_fallback_query(query.raw_query)
    ns = selectors.get("namespace", namespace)
    if not is_valid_k8s_name(ns, namespace=True):
        raise ValidationError(f"Invalid Kubernetes namespace identifier: '{ns}'")

    cmd = _build_kubectl_logs_cmd(ns, selectors, limit, since)
    proc = run_subprocess(cmd, check=False)
    if proc.returncode != 0 or not proc.stdout.strip():
        return LogQueryResult(
            query=query,
            entries=[],
            source="k8s_fallback",
            duration_ms=0.0,
        )

    all_entries: list[LogEntry] = []
    for line in proc.stdout.splitlines():
        stripped = line.strip()
        if not stripped or not all(pattern in stripped for pattern in substring_filters):
            continue
        all_entries.append(
            LogEntry(
                timestamp="",
                line=stripped,
                stream_labels={"namespace": ns, **selectors},
                fields={},
                trace_id=extract_trace_id(stripped),
            )
        )
        if len(all_entries) >= limit:
            break

    return LogQueryResult(
        query=query,
        entries=all_entries,
        source="k8s_fallback",
        duration_ms=0.0,
    )


def execute_loki_query(
    query: LogQLQuery,
    loki_url: str = DEFAULT_LOKI_URL,
    limit: int = DEFAULT_LOG_QUERY_LIMIT,
    since: str = DEFAULT_LOG_QUERY_SINCE,
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
        with new_http_client(level=EgressLevel.PRIVATE, timeout=10.0) as client:
            resp = client.get(endpoint, params=params)
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
    limit: int = DEFAULT_LOG_QUERY_LIMIT,
    since: str = DEFAULT_LOG_QUERY_SINCE,
    dry_run: bool = False,
) -> LogQueryResult:
    """High-level query entrypoint with automatic Loki to kubectl fallback."""
    parsed = query if isinstance(query, LogQLQuery) else parse_logql_query(query)

    if namespace:
        current_ns = parsed.selectors.get("namespace")
        if current_ns and current_ns != namespace:
            raise KubernetesLoggingError(
                f"Conflicting namespace selector: query specifies '{current_ns}' but --namespace is '{namespace}'",
                query=parsed.raw_query,
            )
        if not current_ns:
            suggested_selectors = dict(parsed.selectors)
            suggested_selectors["namespace"] = namespace
            suggested = "{" + ", ".join(f'{k}="{v}"' for k, v in suggested_selectors.items()) + "}"
            raise KubernetesLoggingError(
                f"Query selector lacks namespace '{namespace}'. Use selector '{suggested}'.",
                query=parsed.raw_query,
            )

    target_ns = parsed.selectors.get("namespace", namespace or "default")
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
            return execute_kubectl_logql(parsed, namespace=target_ns, limit=limit, since=since)
        except KubernetesLoggingError:
            raise
