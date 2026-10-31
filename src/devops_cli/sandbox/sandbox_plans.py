"""Planned execution requests for sandbox commands under dry run (#2251)."""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from devops_cli.dry_run.requests import PlannedRequest


def plan_sandbox_deploy(
    image: str = "python:3.14-slim",
    name: str | None = None,
    ports: Sequence[int] | None = None,
    command: Sequence[str] | None = None,
    workspace: Path | str = ".",
    memory: str = "2g",
    cpus: float = 2.0,
    read_only: bool = True,
    network_mode: str = "isolated",
    network_config: dict[str, Any] | None = None,
    declared_controls: dict[str, Any] | None = None,
    seccomp_profile: str | Path | None = None,
) -> list[PlannedRequest]:
    """Generate planned requests for deploying a sandbox container."""
    details: dict[str, Any] = {
        "image": image,
        "name": name,
        "ports": list(ports or []),
        "command": list(command or ["sleep", "infinity"]),
        "workspace": str(workspace),
        "memory": memory,
        "cpus": cpus,
        "read_only": read_only,
        "network_mode": network_mode,
    }
    if network_config is not None:
        details["network_config"] = network_config
    if declared_controls is not None:
        details["declared_controls"] = declared_controls
    if seccomp_profile is not None:
        details["seccomp_profile"] = str(seccomp_profile)
    return [
        PlannedRequest(
            method="DOCKER",
            target=f"POST /containers/create (name: {name or '<auto>'})",
            stdin=json.dumps(details),
        ),
        PlannedRequest(
            method="DOCKER",
            target=f"POST /containers/{name or '<container-id>'}/start",
        ),
    ]


def plan_sandbox_status(
    instance_id: str | None = None,
    all_instances: bool = False,
) -> list[PlannedRequest]:
    """Generate planned request for inspecting sandbox status."""
    if instance_id:
        return [
            PlannedRequest(
                method="DOCKER",
                target=f"GET /containers/{instance_id}/json",
            )
        ]
    query = "?all=true" if all_instances else ""
    return [
        PlannedRequest(
            method="DOCKER",
            target=f"GET /containers/json{query}",
        )
    ]


def plan_sandbox_stop(
    targets: Sequence[str],
    timeout: int = 10,
) -> list[PlannedRequest]:
    """Generate planned requests for stopping and removing sandboxes."""
    requests: list[PlannedRequest] = []
    target_list = list(targets) if targets else ["<container-id>"]
    for t in target_list:
        requests.append(
            PlannedRequest(
                method="DOCKER",
                target=f"POST /containers/{t}/stop (timeout: {timeout}s)",
            )
        )
        requests.append(
            PlannedRequest(
                method="DOCKER",
                target=f"DELETE /containers/{t}",
            )
        )
    return requests


def plan_sandbox_exec(
    instance_id: str,
    command: Sequence[str],
    workdir: str | None = None,
) -> list[PlannedRequest]:
    """Generate planned requests for executing a command in a sandbox container."""
    details = {"command": list(command), "workdir": workdir}
    return [
        PlannedRequest(
            method="DOCKER",
            target=f"POST /containers/{instance_id}/exec",
            stdin=json.dumps(details),
        ),
        PlannedRequest(
            method="DOCKER",
            target=f"POST /exec/<exec-id>/start (container: {instance_id})",
        ),
    ]


def plan_sandbox_probe(
    identifier: str,
    protocols: Sequence[str] | None = None,
    paths: Sequence[str] | None = None,
    timeout: float = 5.0,
) -> list[PlannedRequest]:
    """Generate planned requests for probing sandbox endpoints."""
    requests: list[PlannedRequest] = []
    protos = list(protocols) if protocols else ["tcp", "http"]
    probe_paths = list(paths) if paths else ["/healthz"]

    if "tcp" in protos:
        requests.append(
            PlannedRequest(
                method="TCP",
                target=f"connect {identifier}:<port> (timeout: {timeout}s)",
            )
        )
    if "http" in protos:
        for p in probe_paths:
            path_clean = p if p.startswith("/") else f"/{p}"
            requests.append(
                PlannedRequest(
                    method="GET",
                    target=f"http://{identifier}:<port>{path_clean} (timeout: {timeout}s)",
                )
            )
    return requests


def plan_sandbox_metrics(
    identifier: str,
    prom_endpoint: str = "/metrics",
    timeout: float = 5.0,
) -> list[PlannedRequest]:
    """Generate planned requests for scraping Prometheus metrics and cgroup stats."""
    path_clean = prom_endpoint if prom_endpoint.startswith("/") else f"/{prom_endpoint}"
    return [
        PlannedRequest(
            method="GET",
            target=f"http://{identifier}:<port>{path_clean} (timeout: {timeout}s)",
        ),
        PlannedRequest(
            method="DOCKER",
            target=f"GET /containers/{identifier}/stats",
        ),
    ]


def plan_sandbox_traces(
    identifier: str | None = None,
    trace_id: str | None = None,
    probe: bool = False,
    tempo_url: str | None = None,
) -> list[PlannedRequest]:
    """Generate planned requests for querying distributed trace waterfalls."""
    requests: list[PlannedRequest] = []
    target_id = identifier or "<instance-id>"
    if probe:
        requests.append(
            PlannedRequest(
                method="GET",
                target=f"/probe-healthz ({target_id})",
            )
        )
    base_tempo = tempo_url or "http://tempo.monitoring.svc:3200"
    target_trace = trace_id or "<latest-trace-id>"
    requests.append(
        PlannedRequest(
            method="GET",
            target=f"{base_tempo}/api/traces/{target_trace}",
        )
    )
    return requests


def plan_sandbox_logs(
    identifier: str | None = None,
    follow: bool = False,
    tail: int = 100,
    timestamps: bool = True,
) -> list[PlannedRequest]:
    """Generate planned request for streaming container logs."""
    target_id = identifier or "<container-id>"
    params = f"follow={str(follow).lower()}&tail={tail}&timestamps={str(timestamps).lower()}"
    return [
        PlannedRequest(
            method="DOCKER",
            target=f"GET /containers/{target_id}/logs?{params}",
        )
    ]


def _parse_host_port(entry: str, default_port: int = 443) -> tuple[str, int]:
    """Extract host and port from a whitelist specification."""
    clean = entry.strip()
    scheme = urlsplit(clean).scheme
    split = urlsplit(clean if scheme else f"//{clean}")
    host = split.hostname or clean
    port = split.port or (80 if scheme == "http" else default_port)
    return host, port


def plan_sandbox_network_policy(
    network_mode: str = "isolated",
    name: str = "app-sandbox",
    namespace: str = "sandbox",
    public_whitelist: str | None = None,
    local_whitelist: str | None = None,
    allow_collector: bool = False,
) -> list[PlannedRequest]:
    """Generate planned requests for NetworkPolicy generation including DNS resolutions."""
    requests: list[PlannedRequest] = []
    entries: list[tuple[str, int]] = []

    if public_whitelist:
        for item in public_whitelist.split(","):
            if item.strip():
                entries.append(_parse_host_port(item.strip(), default_port=443))
    if local_whitelist:
        for item in local_whitelist.split(","):
            if item.strip():
                entries.append(_parse_host_port(item.strip(), default_port=80))

    for host, port in entries:
        requests.append(
            PlannedRequest(
                method="DNS",
                target=f"resolve {host}:{port}",
            )
        )

    collector_note = " (with OTel collector egress)" if allow_collector else ""
    requests.append(
        PlannedRequest(
            method="PLAN",
            target=f"generate NetworkPolicy '{name}' in namespace '{namespace}' (mode: {network_mode}){collector_note}",
        )
    )
    return requests
