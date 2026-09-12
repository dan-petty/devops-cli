"""Subsystem data providers for workstation status, metrics, and review state."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from devops_cli.config.settings import load_settings
from devops_cli.core.paths import is_forbidden_system_path, validate_no_path_traversal
from devops_cli.telemetry.metrics import GLOBAL_METRICS
from devops_cli.valkey.client import ValkeyClient

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
    """Docker daemon and container metrics summary."""

    connected: bool = False
    containers: list[dict[str, str]] = Field(default_factory=list)
    error_message: str = ""


class TelemetrySummary(BaseModel):
    """OpenTelemetry metrics and telemetry summary."""

    counter_count: int = 0
    gauge_count: int = 0
    histogram_count: int = 0
    counters: dict[str, float] = Field(default_factory=dict)
    gauges: dict[str, float] = Field(default_factory=dict)


class ReviewSummary(BaseModel):
    """Latest AI code review session and findings summary."""

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


# =============================================================================
# Helper Client Resolution
# =============================================================================


def _get_k8s_client() -> Any:
    """Retrieve initialized Kubernetes CoreV1Api client."""
    from kubernetes import client, config  # type: ignore[import-untyped]

    try:
        config.load_kube_config()
    except Exception:
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


def fetch_docker_status() -> DockerSummary:
    """Retrieve Docker containers defensively."""
    try:
        client = _get_docker_client()
        containers = [_format_container_record(c) for c in client.containers.list()]
        return DockerSummary(connected=True, containers=containers)
    except Exception as exc:
        return DockerSummary(connected=False, error_message=str(exc))


def fetch_telemetry_status() -> TelemetrySummary:
    """Retrieve in-memory OpenTelemetry metric counters and gauges."""
    snapshot = GLOBAL_METRICS.get_metrics_snapshot()
    return TelemetrySummary(
        counter_count=snapshot["counter_count"],
        gauge_count=snapshot["gauge_count"],
        histogram_count=snapshot["histogram_count"],
        counters=snapshot["counters"],
        gauges=snapshot["gauges"],
    )


def _get_latest_review_session_dir() -> Path | None:
    """Locate the most recent review session directory."""
    raw_data_dir = os.getenv("DEVOPS_CLI_DATA_DIR")
    if not raw_data_dir:
        try:
            raw_data_dir = str(load_settings().data.dir)
        except Exception:
            raw_data_dir = "./.data"
    try:
        validate_no_path_traversal(raw_data_dir, label="DEVOPS_CLI_DATA_DIR")
        data_path = Path(raw_data_dir).resolve()
        if is_forbidden_system_path(data_path):
            return None
    except Exception:
        return None
    reviews_dir = data_path / "reviews"
    if not (reviews_dir.exists() and reviews_dir.is_dir()):
        return None
    sessions = sorted(
        [d for d in reviews_dir.iterdir() if d.is_dir()],
        key=lambda d: d.name,
        reverse=True,
    )
    return sessions[0] if sessions else None


def fetch_review_status() -> ReviewSummary:
    """Retrieve findings and severity distribution from latest review session."""
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
            findings=raw_findings[:50],
        )
    except Exception:
        return ReviewSummary(has_session=True, session_name=session_dir.name)


def fetch_valkey_status() -> ValkeySummary:
    """Retrieve Valkey server info, memory stats, and hit ratios."""
    try:
        client = ValkeyClient(timeout=1.0)
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
        except Exception:
            key_count = 0

        return ValkeySummary(
            connected=True,
            version=str(server_dict.get("valkey_version", "unknown")),
            uptime_seconds=int(server_dict.get("uptime_in_seconds", 0)),
            used_memory=str(memory_dict.get("used_memory_human", "0M")),
            hit_ratio=hit_ratio,
            connected_clients=int(clients_dict.get("connected_clients", 0)),
            total_commands=int(stats_dict.get("total_commands_processed", 0)),
            key_count=key_count,
        )
    except Exception:
        return ValkeySummary(connected=False, version="Offline")
