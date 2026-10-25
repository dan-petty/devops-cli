"""Subsystem data providers for workstation status, metrics, and review state."""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from devops_cli.config.constants import (
    CONST_K8S_IN_CLUSTER_CONTEXT,
    CONST_K8S_POD_EVENT_FIELD_SELECTOR,
    CONST_K8S_SERVICE_HOST_ENV,
    CONST_TELEMETRY_PANEL_MAX_SERIES,
)
from devops_cli.config.defaults import (
    DEFAULT_K8S_CONNECT_TIMEOUT_SECONDS,
    DEFAULT_K8S_POD_EVENT_LIMIT,
    DEFAULT_TELEMETRY_QUERY_TIMEOUT_SECONDS,
    DEFAULT_VALKEY_PANEL_TIMEOUT_SECONDS,
)
from devops_cli.config.settings import get_valkey_password, load_settings
from devops_cli.exceptions import DevOpsCLIError
from devops_cli.k8s.service_http import describe_endpoint
from devops_cli.models.k8s import PodEventInfo, PodInfo, node_is_ready
from devops_cli.review.session import ReviewSessionStore
from devops_cli.security.sanitizer import mask_secrets
from devops_cli.telemetry.metrics import GLOBAL_METRICS
from devops_cli.valkey.client import ValkeyClient

logger = logging.getLogger(__name__)

# =============================================================================
# Summary Data Models
# =============================================================================


class K8sSummary(BaseModel):
    """Kubernetes cluster and pods summary."""

    connected: bool = False
    # The kubeconfig context the dashboard connects with, named so the banner says which
    # cluster it is showing; empty when none could be determined.
    context: str = ""
    pods: list[PodInfo] = Field(default_factory=list)
    nodes_ready: int = 0
    nodes_total: int = 0
    # Why the node list failed. Listing nodes needs a cluster-scoped permission that
    # listing pods does not, so pods still render without it.
    nodes_error: str = ""
    error_message: str = ""

    @property
    def unhealthy_pods(self) -> int:
        """Count pods whose status or READY count needs attention."""
        return sum(pod.unhealthy for pod in self.pods)


class DockerSummary(BaseModel):
    """Docker daemon inventory: containers, images, networks, volumes, registries."""

    connected: bool = False
    containers: list[dict[str, str]] = Field(default_factory=list)
    images: list[dict[str, str]] = Field(default_factory=list)
    networks: list[dict[str, str]] = Field(default_factory=list)
    volumes: list[dict[str, str]] = Field(default_factory=list)
    registries: list[dict[str, str]] = Field(default_factory=list)
    error_message: str = ""

    @property
    def running_containers(self) -> int:
        """Count containers currently running, as opposed to merely present."""
        return sum(1 for record in self.containers if record.get("status") == "running")


class TelemetrySummary(BaseModel):
    """OpenTelemetry metrics and telemetry summary."""

    counter_count: int = 0
    gauge_count: int = 0
    histogram_count: int = 0
    counters: dict[str, float] = Field(default_factory=dict)
    gauges: dict[str, float] = Field(default_factory=dict)
    # Which registry produced these figures. The in-process registry is empty in a freshly
    # launched dashboard, which reads as "telemetry is broken" rather than "this process
    # has not recorded anything yet".
    source: str = "in-process"
    error_message: str = ""
    latency_samples: list[float] = Field(default_factory=list)
    token_throughput_samples: list[float] = Field(default_factory=list)
    cache_hit_ratio: float = 0.0
    cache_hit_samples: list[float] = Field(default_factory=list)
    recent_traces: list[dict[str, Any]] = Field(default_factory=list)


class ReviewSessionInfo(BaseModel):
    """One review session on disk."""

    name: str
    completed: bool = False


class ReviewSummary(BaseModel):
    """AI code review session and findings summary."""

    has_session: bool = False
    session_name: str = ""
    total_findings: int = 0
    verified_count: int = 0
    unverified_count: int = 0
    severity_distribution: dict[str, int] = Field(default_factory=dict)
    findings: list[dict[str, Any]] = Field(default_factory=list)


class ValkeySummary(BaseModel):
    """Valkey distributed cache status and metrics summary."""

    connected: bool = False
    version: str = "Offline"
    uptime_seconds: int = 0
    used_memory: str = "0M"
    hit_ratio: float = 0.0
    connected_clients: int = 0
    total_commands: int = 0
    key_count: int = 0
    # An "Offline" banner that does not say which endpoint was tried, or why it failed,
    # sends the reader to the wrong place: a cache that is simply not deployed looks
    # identical to one that is deployed and refusing connections.
    endpoint: str = ""
    error_message: str = ""


# =============================================================================
# Helper Client Resolution
# =============================================================================


def _get_k8s_client() -> Any:
    """Retrieve an initialized Kubernetes CoreV1Api client for the configured context.

    The dashboard must show the cluster the workstation is configured for. Loading the
    kubeconfig without a context silently follows `kubectl config current-context`, so the
    panel would report on a different cluster than every other command.

    A pod's service account is used only inside a pod and only when no kubeconfig context
    can be named. Falling back whenever the kubeconfig failed replaced its error, such as a
    context missing from the file, with the fallback's own, and inside a pod connected to
    a cluster other than the one the banner named.
    """
    from kubernetes import client, config  # type: ignore[import-untyped]

    from devops_cli.k8s.context import resolve_context

    if _in_a_pod() and not _kubeconfig_context():
        config.load_incluster_config()
    else:
        config.load_kube_config(context=resolve_context())
    return client.CoreV1Api()


def _in_a_pod() -> bool:
    """Whether this process runs in a Kubernetes pod, which has a service account."""
    return bool(os.environ.get(CONST_K8S_SERVICE_HOST_ENV))


def _kubeconfig_context() -> str:
    """Name the kubeconfig context to connect with: the configured one, else kubectl's.

    Empty when neither exists, as for a pod with no kubeconfig.
    """
    from kubernetes import config

    from devops_cli.k8s.context import resolve_context

    configured = resolve_context()
    if configured:
        return configured
    try:
        _contexts, current = config.list_kube_config_contexts()
    except Exception as exc:
        logger.debug("No current kubeconfig context to name: %s", exc)
        return ""
    return str(current.get("name") or "")


def _k8s_context_name() -> str:
    """Name the context `_get_k8s_client` connects with, or the pod's service account.

    Read from the kubeconfig rather than from the client, so a cluster that cannot be
    reached is still named in the banner that says so.
    """
    context = _kubeconfig_context()
    return context or (CONST_K8S_IN_CLUSTER_CONTEXT if _in_a_pod() else "")


def describe_api_error(exc: Exception) -> str:
    """Describe a failed cluster call in one line, with any credential in it masked.

    An API error's text runs to its response headers and body, so it is named by status
    and reason instead, as in `403 Forbidden`.
    """
    status, reason = getattr(exc, "status", None), getattr(exc, "reason", None)
    if status and reason:
        return f"{status} {reason}"
    first_line = next(iter(str(exc).splitlines()), "")
    return mask_secrets(f"{type(exc).__name__}: {first_line}")[:256]


# =============================================================================
# Data Provider Functions
# =============================================================================


def _node_readiness(core: Any) -> dict[str, Any]:
    """Count the nodes that are Ready, or say why the nodes could not be listed."""
    try:
        nodes = core.list_node(_request_timeout=DEFAULT_K8S_CONNECT_TIMEOUT_SECONDS).items
    except Exception as exc:
        return {"nodes_error": describe_api_error(exc)}
    return {"nodes_ready": sum(map(node_is_ready, nodes)), "nodes_total": len(nodes)}


def fetch_k8s_status() -> K8sSummary:
    """Retrieve every pod, with the status kubectl prints, and how many nodes are Ready.

    Both calls carry a client-side timeout: a server-side one does not bound a connection
    to a server that never answers, and this runs on every refresh.
    """
    context = _k8s_context_name()
    try:
        core = _get_k8s_client()
        pods = core.list_pod_for_all_namespaces(
            _request_timeout=DEFAULT_K8S_CONNECT_TIMEOUT_SECONDS
        ).items
        records = [PodInfo.from_pod(pod) for pod in pods]
    except Exception as exc:
        return K8sSummary(context=context, error_message=describe_api_error(exc))
    return K8sSummary(connected=True, context=context, pods=records, **_node_readiness(core))


def _newest_first(event: PodEventInfo) -> float:
    """Sort key placing the most recent event first and undated ones last."""
    return -event.last_seen.timestamp() if event.last_seen is not None else float("inf")


def fetch_pod_events(namespace: str, name: str, uid: str) -> list[PodEventInfo]:
    """Return a pod's most recent events, newest first.

    Matched by kind, name and uid, as `kubectl describe pod` matches them, so a pod
    recreated under the same name does not show its predecessor's events. Raises on a
    failed call, for the caller to report.
    """
    core = _get_k8s_client()
    events = core.list_namespaced_event(
        namespace,
        field_selector=CONST_K8S_POD_EVENT_FIELD_SELECTOR.format(name=name, uid=uid),
        _request_timeout=DEFAULT_K8S_CONNECT_TIMEOUT_SECONDS,
    ).items
    records = sorted(map(PodEventInfo.from_event, events), key=_newest_first)
    return records[:DEFAULT_K8S_POD_EVENT_LIMIT]


def _format_container_record(container: Any) -> dict[str, str]:
    """Format Docker container into record dictionary."""
    cid = getattr(container, "id", "")[:12]
    name = getattr(container, "name", "unknown")
    image = "unknown"
    if hasattr(container, "image") and hasattr(container.image, "tags"):
        tags = container.image.tags
        image = tags[0] if tags else "none"
    status = getattr(container, "status", "unknown")
    return {"id": cid, "name": name, "image": image, "status": status}


def _humanize_bytes(size: Any) -> str:
    """Render a byte count in the units an operator reads sizes in."""
    try:
        value = float(size)
    except TypeError, ValueError:
        return "-"
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(value) < 1024.0:
            return f"{value:.0f}{unit}" if unit == "B" else f"{value:.1f}{unit}"
        value /= 1024.0
    return f"{value:.1f}PB"


def _format_image_record(image: Any) -> dict[str, str]:
    """Format a Docker image into a record dictionary."""
    tags = getattr(image, "tags", []) or []
    attrs = getattr(image, "attrs", {}) or {}
    return {
        "id": str(getattr(image, "id", "")).removeprefix("sha256:")[:12],
        # An untagged image is a real thing to see: it is usually a dangling layer set
        # occupying disk that nothing references.
        "tag": tags[0] if tags else "<none>:<none>",
        "size": _humanize_bytes(attrs.get("Size")),
        "created": str(attrs.get("Created", ""))[:19].replace("T", " "),
    }


def _format_network_record(network: Any) -> dict[str, str]:
    """Format a Docker network into a record dictionary."""
    attrs = getattr(network, "attrs", {}) or {}
    containers = attrs.get("Containers")
    return {
        "id": str(getattr(network, "id", ""))[:12],
        "name": str(getattr(network, "name", "unknown")),
        "driver": str(attrs.get("Driver", "-")),
        "scope": str(attrs.get("Scope", "-")),
        "containers": str(len(containers) if isinstance(containers, dict) else 0),
    }


def _format_volume_record(volume: Any) -> dict[str, str]:
    """Format a Docker volume into a record dictionary."""
    attrs = getattr(volume, "attrs", {}) or {}
    usage = attrs.get("UsageData")
    size = usage.get("Size") if isinstance(usage, dict) else None
    return {
        "name": str(getattr(volume, "name", "unknown")),
        "driver": str(attrs.get("Driver", "-")),
        "mountpoint": str(attrs.get("Mountpoint", "-")),
        # Docker only populates UsageData when explicitly requested; -1 means "not
        # computed", which must not be rendered as a real size of -1 bytes.
        "size": _humanize_bytes(size) if isinstance(size, int) and size >= 0 else "-",
        "created": str(attrs.get("CreatedAt", ""))[:19].replace("T", " "),
    }


def _fetch_registries(client: Any) -> list[dict[str, str]]:
    """List the registries this Docker client is authenticated against.

    Read from the daemon's own view rather than parsing ~/.docker/config.json, so a
    credential helper that stores secrets outside that file is still represented.
    """
    registries: list[dict[str, str]] = []
    try:
        info = client.info()
    except Exception as exc:
        logger.debug("Failed to query Docker info for registries: %s", exc)
        return registries

    index = info.get("IndexServerAddress")
    if index:
        registries.append({"name": str(index), "kind": "default", "status": "configured"})

    mirrors = info.get("RegistryConfig", {}).get("Mirrors") or []
    registries.extend(
        {"name": str(mirror), "kind": "mirror", "status": "configured"} for mirror in mirrors
    )
    insecure = info.get("RegistryConfig", {}).get("IndexConfigs") or {}
    registries.extend(
        {
            "name": str(name),
            "kind": "insecure" if not cfg.get("Secure", True) else "index",
            "status": "configured",
        }
        for name, cfg in insecure.items()
        if isinstance(cfg, dict) and str(name) != str(index)
    )
    return registries


def _collect(label: str, loader: Any, formatter: Any) -> list[dict[str, str]]:
    """Collect one Docker inventory list, tolerating a failure of that list alone.

    One unavailable endpoint must not blank the whole Docker view; a daemon that lists
    containers but refuses volumes should still show the containers.
    """
    try:
        return [formatter(item) for item in loader()]
    except Exception as exc:
        logger.debug("Failed to list Docker %s: %s", label, exc)
        return []


def fetch_docker_status() -> DockerSummary:
    """Retrieve the whole Docker inventory in one pass.

    Every Docker sub-tab is projected from this one summary, so the panel costs a single
    set of daemon queries per refresh no matter how many resource views are displayed.
    """
    from devops_cli.docker.engine import get_engine

    try:
        client = get_engine().client()
    except Exception as exc:
        return DockerSummary(connected=False, error_message=str(exc))

    # all=True: a stopped container is the one an operator is usually looking for, and
    # omitting it made the panel disagree with `docker ps -a`.
    containers = _collect(
        "containers", lambda: client.containers.list(all=True), _format_container_record
    )
    return DockerSummary(
        connected=True,
        containers=containers,
        images=_collect("images", client.images.list, _format_image_record),
        networks=_collect("networks", client.networks.list, _format_network_record),
        volumes=_collect("volumes", client.volumes.list, _format_volume_record),
        registries=_fetch_registries(client),
    )


def _extract_recent_traces(max_traces: int = 10) -> list[dict[str, Any]]:
    """Extract recent trace summaries grouped by trace ID from in-memory spans."""
    from devops_cli.telemetry.tracer import get_recent_spans

    spans = get_recent_spans()
    if not spans:
        return []

    grouped: dict[str, list[dict[str, Any]]] = {}
    for s in spans:
        tid = str(s.get("traceId", ""))
        if tid:
            grouped.setdefault(tid, []).append(s)

    traces: list[dict[str, Any]] = []
    for tid, trace_spans in list(grouped.items())[-max_traces:]:
        root = next((s for s in trace_spans if not s.get("parentSpanId")), trace_spans[0])
        start_nano = min(int(s.get("startTimeUnixNano", 0)) for s in trace_spans)
        end_nano = max(int(s.get("endTimeUnixNano", start_nano)) for s in trace_spans)
        dur_ms = max(0.0, (end_nano - start_nano) / 1_000_000.0)
        has_error = any(
            "ERROR" in str(s.get("status", {}).get("code", "")).upper() for s in trace_spans
        )
        status = "ERROR" if has_error else "OK"

        traces.append(
            {
                "trace_id": tid,
                "root_name": str(root.get("name", "unknown")),
                "span_count": len(trace_spans),
                "duration_ms": dur_ms,
                "status": status,
                "spans": trace_spans,
            }
        )
    return list(reversed(traces))


def _extract_latency_samples(spans: list[dict[str, Any]], max_samples: int = 20) -> list[float]:
    """Extract execution latencies in milliseconds from recent span durations."""
    samples: list[float] = []
    for s in spans:
        start_ns = int(s.get("startTimeUnixNano", 0))
        end_ns = int(s.get("endTimeUnixNano", start_ns))
        dur_ms = max(0.0, (end_ns - start_ns) / 1_000_000.0)
        samples.append(dur_ms)
    return samples[-max_samples:]


def _in_process_telemetry() -> TelemetrySummary:
    """Read the metric registry belonging to this process."""
    from devops_cli.telemetry.tracer import get_recent_spans

    snapshot = GLOBAL_METRICS.get_metrics_snapshot()
    spans = get_recent_spans()
    recent_traces = _extract_recent_traces()
    latency_samples = _extract_latency_samples(spans)

    tokens = float(snapshot["counters"].get("devops_cli_ai_tokens_total", 0.0))
    token_samples = [tokens] if tokens > 0 else []

    return TelemetrySummary(
        counter_count=snapshot["counter_count"],
        gauge_count=snapshot["gauge_count"],
        histogram_count=snapshot["histogram_count"],
        counters=snapshot["counters"],
        gauges=snapshot["gauges"],
        source="in-process",
        latency_samples=latency_samples,
        token_throughput_samples=token_samples,
        cache_hit_ratio=0.0,
        cache_hit_samples=[],
        recent_traces=recent_traces,
    )


def _prometheus_base_url() -> str | None:
    """Resolve the configured Prometheus endpoint, if there is one."""
    try:
        settings = load_settings()
    except Exception as exc:
        logger.debug("Failed loading settings for Prometheus endpoint: %s", exc)
        return None
    url = getattr(getattr(settings, "prometheus", None), "url", None)
    return str(url).rstrip("/") if isinstance(url, str) and url.strip() else None


def _fetch_prometheus_metrics(base_url: str) -> TelemetrySummary:
    """Summarise the metrics Prometheus is currently scraping.

    The dashboard panel exists to answer "is telemetry flowing", and the only registry that
    can answer that is the one the exporters actually write to.

    The endpoint may be an ordinary URL or a `k8s://` service address; `get_json` resolves
    either, so a configuration can move to cluster-native addressing without this code
    changing.
    """
    from devops_cli.k8s.service_http import get_json

    payload = get_json(
        base_url,
        "api/v1/label/__name__/values",
        timeout=DEFAULT_TELEMETRY_QUERY_TIMEOUT_SECONDS,
        purpose="Prometheus",
    )
    names = payload.get("data") or []

    counters = {name: 0.0 for name in names if str(name).endswith("_total")}
    histograms = {name for name in names if str(name).endswith(("_bucket", "_sum", "_count"))}
    gauges = {
        name: 0.0
        for name in names
        if name not in counters and name not in histograms and not str(name).startswith("go_")
    }

    from devops_cli.telemetry.tracer import get_recent_spans

    recent_traces = _extract_recent_traces()
    spans = get_recent_spans()
    latency_samples = _extract_latency_samples(spans)

    return TelemetrySummary(
        counter_count=len(counters),
        gauge_count=len(gauges),
        histogram_count=len(histograms),
        # Names only: fetching a current value per series would issue one query per metric
        # on every refresh, which is what makes a dashboard hammer its own backend.
        counters=dict(sorted(counters.items())[:CONST_TELEMETRY_PANEL_MAX_SERIES]),
        gauges=dict(sorted(gauges.items())[:CONST_TELEMETRY_PANEL_MAX_SERIES]),
        source=describe_endpoint(base_url),
        latency_samples=latency_samples,
        token_throughput_samples=[],
        cache_hit_ratio=0.0,
        cache_hit_samples=[],
        recent_traces=recent_traces,
    )


def fetch_telemetry_status() -> TelemetrySummary:
    """Retrieve telemetry from Prometheus when configured, else from this process.

    A freshly launched dashboard has recorded no metrics of its own, so reading only the
    in-process registry made the panel permanently empty and indistinguishable from broken
    instrumentation.
    """
    base_url = _prometheus_base_url()
    if not base_url:
        return _in_process_telemetry()
    try:
        return _fetch_prometheus_metrics(base_url)
    except Exception as exc:
        logger.debug("Prometheus telemetry query failed: %s", exc)
        fallback = _in_process_telemetry()
        # Naming the endpoint that failed is what distinguishes "Prometheus is down" from
        # "nothing has been instrumented".
        return fallback.model_copy(update={"error_message": f"{base_url}: {exc}"})


def _listed_sessions() -> list[tuple[ReviewSessionInfo, Path]]:
    """Each review session, newest first, with the directory it is read from.

    The published sessions are read from their own, the ones a review is still writing from
    staging. A refused or missing directory lists none: a settings file the schema refuses raises
    a `ValidationError`, a `ValueError`, which is answered as a refused directory is.
    """
    try:
        published = [
            (
                ReviewSessionInfo(name=session.name, completed=True),
                session.directory,
            )
            for session in ReviewSessionStore.sessions()
        ]
        running = [
            (ReviewSessionInfo(name=session.name), session.staging)
            for session in ReviewSessionStore.in_flight()
        ]
    except (DevOpsCLIError, OSError, ValueError) as exc:
        logger.warning("Invalid review data directory: %s", exc)
        return []
    return sorted(published + running, key=lambda listed: listed[0].name, reverse=True)


def _get_latest_review_session_dir() -> Path | None:
    """Resolve the session directory to display: the newest **completed** session.

    A review that is still running writes into staging and is published only at the end, so
    taking the newest session showed an empty in-flight one as the latest result and hid the
    last real one behind it.
    """
    listed = _listed_sessions()
    # With nothing completed yet, showing the in-flight session beats showing nothing, and
    # the summary reports that it is still running.
    return next(
        (directory for info, directory in listed if info.completed),
        listed[0][1] if listed else None,
    )


def fetch_review_status() -> ReviewSummary:
    """Summarise the newest completed review session."""
    session_dir = _get_latest_review_session_dir()
    if not session_dir:
        return ReviewSummary(has_session=False)

    findings_file = session_dir / "findings.json"
    if not (findings_file.exists() and findings_file.is_file()):
        return ReviewSummary(has_session=True, session_name=session_dir.name)

    try:
        data = json.loads(findings_file.read_text(encoding="utf-8"))
        raw_findings: list[dict[str, Any]] = data.get("findings", [])
        verified_count = sum(
            1 for f in raw_findings if f.get("status") == "VERIFIED" or f.get("verified") is True
        )
        unverified_count = len(raw_findings) - verified_count

        severities: dict[str, int] = {}
        for f in raw_findings:
            sev = str(f.get("severity", "MEDIUM")).upper()
            severities[sev] = severities.get(sev, 0) + 1

        return ReviewSummary(
            has_session=True,
            session_name=session_dir.name,
            total_findings=len(raw_findings),
            verified_count=verified_count,
            unverified_count=unverified_count,
            severity_distribution=severities,
            findings=raw_findings,
        )
    except Exception as exc:
        logger.warning("Failed to parse review summary from %s: %s", session_dir, exc)
        return ReviewSummary(has_session=True, session_name=session_dir.name)


def fetch_valkey_status() -> ValkeySummary:
    """Retrieve Valkey server info, memory stats, and hit ratios."""
    endpoint = "unknown"
    try:
        settings = load_settings()
        client = ValkeyClient(
            settings.valkey.endpoint,
            password=get_valkey_password(settings),
            timeout=DEFAULT_VALKEY_PANEL_TIMEOUT_SECONDS,
        )
        endpoint = f"{client.host}:{client.port}"
        info = client.info()
        hits = float(info.get("keyspace_hits", 0))
        misses = float(info.get("keyspace_misses", 0))
        total_queries = hits + misses
        hit_ratio = round((hits / total_queries) * 100.0, 1) if total_queries > 0 else 0.0

        try:
            key_count = client.dbsize()
        except Exception as exc:
            logger.debug("Failed to query Valkey dbsize: %s", exc)
            key_count = 0

        return ValkeySummary(
            connected=True,
            endpoint=endpoint,
            version=str(info.get("valkey_version", "unknown")),
            uptime_seconds=int(info.get("uptime_in_seconds", 0)),
            used_memory=str(info.get("used_memory_human", "0M")),
            hit_ratio=hit_ratio,
            connected_clients=int(info.get("connected_clients", 0)),
            total_commands=int(info.get("total_commands_processed", 0)),
            key_count=key_count,
        )
    except Exception as exc:
        logger.debug("Valkey server offline or unreachable: %s", exc)
        return ValkeySummary(
            connected=False, version="Offline", endpoint=endpoint, error_message=str(exc)
        )
