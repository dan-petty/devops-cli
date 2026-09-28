"""Subsystem data providers for workstation status, metrics, and review state."""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from devops_cli.config.constants import CONST_TELEMETRY_PANEL_MAX_SERIES
from devops_cli.config.defaults import (
    DEFAULT_TELEMETRY_QUERY_TIMEOUT_SECONDS,
    DEFAULT_VALKEY_HOST,
    DEFAULT_VALKEY_PANEL_TIMEOUT_SECONDS,
    DEFAULT_VALKEY_PORT,
)
from devops_cli.config.settings import load_settings
from devops_cli.core.paths import is_forbidden_system_path, validate_no_path_traversal
from devops_cli.core.repo import resolve_data_path
from devops_cli.exceptions import DevOpsCLIError
from devops_cli.k8s.service_http import describe_endpoint
from devops_cli.telemetry.metrics import GLOBAL_METRICS
from devops_cli.valkey.client import ValkeyClient

logger = logging.getLogger(__name__)

# =============================================================================
# Summary Data Models
# =============================================================================


class K8sSummary(BaseModel):
    """Kubernetes cluster and pods summary."""

    connected: bool = False
    minikube_active: bool = False
    pods: list[dict[str, str]] = Field(default_factory=list)
    services: list[dict[str, str]] = Field(default_factory=list)
    error_message: str = ""


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


class ReviewSessionInfo(BaseModel):
    """One review session on disk."""

    name: str
    completed: bool = False
    finding_count: int = 0


class ReviewSummary(BaseModel):
    """AI code review session and findings summary."""

    # Sessions newest first, so the panel can offer selection without re-sorting.
    sessions: list[ReviewSessionInfo] = Field(default_factory=list)
    # Sessions that created a directory but never wrote findings.json. A session writes
    # no running-marker, so one that is still in progress is indistinguishable on disk from
    # one that was abandoned; calling them "incomplete" claims only what can be observed.
    incomplete: list[str] = Field(default_factory=list)
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
    """
    from kubernetes import client, config  # type: ignore[import-untyped]

    from devops_cli.k8s.context import resolve_context

    try:
        config.load_kube_config(context=resolve_context())
    except Exception as exc:
        logger.debug("Falling back to incluster k8s config: %s", exc)
        config.load_incluster_config()
    return client.CoreV1Api()


def is_minikube_running() -> bool:
    """Determine if local Minikube cluster is active."""
    from devops_cli.core.process import run_subprocess

    res = run_subprocess(["minikube", "status", "--format={{.Host}}"], check=False, quiet=True)
    return res.returncode == 0 and "Running" in res.stdout


def _get_docker_client() -> Any:
    """Retrieve connected Docker client."""
    import docker  # type: ignore[import-untyped]

    return docker.from_env()


# =============================================================================
# Data Provider Functions
# =============================================================================


def _format_pod_record(pod: Any) -> dict[str, str]:
    """Format single Kubernetes pod into a record dictionary."""
    name = getattr(pod.metadata, "name", "unknown")
    ns = getattr(pod.metadata, "namespace", "default")
    phase = getattr(pod.status, "phase", "Unknown")
    statuses = getattr(pod.status, "container_statuses", []) or []
    ready_count = sum(1 for c in statuses if getattr(c, "ready", False))
    total_count = len(statuses)
    restarts = sum(getattr(c, "restart_count", 0) for c in statuses)
    return {
        "name": name,
        "namespace": ns,
        "status": phase,
        "ready": f"{ready_count}/{total_count}" if total_count else "0/0",
        "restarts": str(restarts),
    }


def fetch_k8s_status() -> K8sSummary:
    """Retrieve Kubernetes pods and Minikube status defensively."""
    try:
        k8s = _get_k8s_client()
        pod_list = k8s.list_pod_for_all_namespaces(timeout_seconds=3).items
        pods = [_format_pod_record(p) for p in pod_list]
        return K8sSummary(
            connected=True,
            minikube_active=is_minikube_running(),
            pods=pods,
        )
    except Exception as exc:
        return K8sSummary(connected=False, error_message=str(exc))


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
    try:
        client = _get_docker_client()
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


def _in_process_telemetry() -> TelemetrySummary:
    """Read the metric registry belonging to this process."""
    snapshot = GLOBAL_METRICS.get_metrics_snapshot()
    return TelemetrySummary(
        counter_count=snapshot["counter_count"],
        gauge_count=snapshot["gauge_count"],
        histogram_count=snapshot["histogram_count"],
        counters=snapshot["counters"],
        gauges=snapshot["gauges"],
        source="in-process",
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

    return TelemetrySummary(
        counter_count=len(counters),
        gauge_count=len(gauges),
        histogram_count=len(histograms),
        # Names only: fetching a current value per series would issue one query per metric
        # on every refresh, which is what makes a dashboard hammer its own backend.
        counters=dict(sorted(counters.items())[:CONST_TELEMETRY_PANEL_MAX_SERIES]),
        gauges=dict(sorted(gauges.items())[:CONST_TELEMETRY_PANEL_MAX_SERIES]),
        source=describe_endpoint(base_url),
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


def _reviews_root() -> Path | None:
    """Resolve the directory holding review sessions: a relative data directory is under the
    main worktree, where the review writer puts them, from any worktree."""
    raw_data_dir = os.getenv("DEVOPS_CLI_DATA_DIR")
    if not raw_data_dir:
        try:
            raw_data_dir = str(load_settings().data.dir)
        except Exception as exc:
            logger.debug("Failed loading settings for data.dir: %s", exc)
            raw_data_dir = "./.data"
    try:
        validate_no_path_traversal(raw_data_dir, label="DEVOPS_CLI_DATA_DIR")
        data_path = resolve_data_path(Path(raw_data_dir)).resolve()
        if is_forbidden_system_path(data_path):
            return None
    except (DevOpsCLIError, OSError, ValueError) as exc:
        logger.warning("Invalid review data directory %s: %s", raw_data_dir, exc)
        return None
    reviews_dir = data_path / "reviews"
    return reviews_dir if reviews_dir.exists() and reviews_dir.is_dir() else None


def _count_findings(findings_file: Path) -> int:
    """Count findings in a session file without raising on a malformed one."""
    try:
        data = json.loads(findings_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.debug("Unreadable findings file %s: %s", findings_file, exc)
        return 0
    findings = data.get("findings") if isinstance(data, dict) else None
    return len(findings) if isinstance(findings, list) else 0


def list_review_sessions() -> list[ReviewSessionInfo]:
    """List review sessions newest first, recording which ones actually completed.

    Session names are timestamps, so a reverse lexical sort is a reverse chronological one.
    """
    reviews_dir = _reviews_root()
    if reviews_dir is None:
        return []

    sessions: list[ReviewSessionInfo] = []
    for directory in sorted(reviews_dir.iterdir(), key=lambda d: d.name, reverse=True):
        if not directory.is_dir():
            continue
        findings_file = directory / "findings.json"
        completed = findings_file.is_file()
        sessions.append(
            ReviewSessionInfo(
                name=directory.name,
                completed=completed,
                finding_count=_count_findings(findings_file) if completed else 0,
            )
        )
    return sessions


def _get_latest_review_session_dir(session: str | None = None) -> Path | None:
    """Resolve the session directory to display.

    Defaults to the newest **completed** session. A review that is still running creates its
    directory immediately but writes findings.json only at the end, so taking the newest
    directory showed an empty in-flight session as the latest result and hid the last real
    one behind it.
    """
    reviews_dir = _reviews_root()
    if reviews_dir is None:
        return None

    if session:
        # A name chosen from the session list, so it is matched as a name rather than
        # interpreted as a path.
        candidate = reviews_dir / Path(session).name
        return candidate if candidate.is_dir() else None

    sessions = list_review_sessions()
    completed = [info for info in sessions if info.completed]
    if completed:
        return reviews_dir / completed[0].name
    # Nothing has completed yet. Showing the in-flight session beats showing nothing, and
    # the summary reports that it is still running.
    return reviews_dir / sessions[0].name if sessions else None


def fetch_review_status(session: str | None = None) -> ReviewSummary:
    """Summarise a review session, defaulting to the newest completed one."""
    sessions = list_review_sessions()
    incomplete = [info.name for info in sessions if not info.completed]

    session_dir = _get_latest_review_session_dir(session)
    if not session_dir:
        return ReviewSummary(has_session=False, sessions=sessions, incomplete=incomplete)

    findings_file = session_dir / "findings.json"
    if not (findings_file.exists() and findings_file.is_file()):
        return ReviewSummary(
            has_session=True,
            session_name=session_dir.name,
            sessions=sessions,
            incomplete=incomplete,
        )

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
            sessions=sessions,
            incomplete=incomplete,
            total_findings=len(raw_findings),
            verified_count=verified_count,
            unverified_count=unverified_count,
            severity_distribution=severities,
            findings=raw_findings[:50],
        )
    except Exception as exc:
        logger.warning("Failed to parse review summary from %s: %s", session_dir, exc)
        return ReviewSummary(has_session=True, session_name=session_dir.name)


def fetch_valkey_status() -> ValkeySummary:
    """Retrieve Valkey server info, memory stats, and hit ratios."""
    endpoint = "unknown"
    try:
        settings = load_settings()
        cfg = settings.valkey
        endpoint = str(getattr(cfg, "host", DEFAULT_VALKEY_HOST))
        client = ValkeyClient(
            host=endpoint,
            port=int(getattr(cfg, "port", DEFAULT_VALKEY_PORT)),
            password=getattr(cfg, "password", None),
            db=int(getattr(cfg, "db", 0)),
            timeout=DEFAULT_VALKEY_PANEL_TIMEOUT_SECONDS,
        )
        endpoint = f"{client.host}:{client.port}"
        info = client.info()
        server_raw = info.get("server")
        server_dict: dict[str, Any] = server_raw if isinstance(server_raw, dict) else {}
        clients_raw = info.get("clients")
        clients_dict: dict[str, Any] = clients_raw if isinstance(clients_raw, dict) else {}
        memory_raw = info.get("memory")
        memory_dict: dict[str, Any] = memory_raw if isinstance(memory_raw, dict) else {}
        stats_raw = info.get("stats")
        stats_dict: dict[str, Any] = stats_raw if isinstance(stats_raw, dict) else {}

        hits = float(stats_dict.get("keyspace_hits", 0))
        misses = float(stats_dict.get("keyspace_misses", 0))
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
            version=str(server_dict.get("valkey_version", "unknown")),
            uptime_seconds=int(server_dict.get("uptime_in_seconds", 0)),
            used_memory=str(memory_dict.get("used_memory_human", "0M")),
            hit_ratio=hit_ratio,
            connected_clients=int(clients_dict.get("connected_clients", 0)),
            total_commands=int(stats_dict.get("total_commands_processed", 0)),
            key_count=key_count,
        )
    except Exception as exc:
        logger.debug("Valkey server offline or unreachable: %s", exc)
        return ValkeySummary(
            connected=False, version="Offline", endpoint=endpoint, error_message=str(exc)
        )
