"""Planned requests for Dashboard and Telemetry commands in dry-run mode.

A dry run makes zero external requests and returns ordered PlannedRequest items (#412, #886).
"""

from __future__ import annotations

import shlex
from pathlib import Path

from devops_cli.dry_run.requests import PlannedRequest


def plan_dashboard() -> list[PlannedRequest]:
    """Generate planned requests for workstation dashboard status probes."""
    return [
        PlannedRequest(
            method="kubectl",
            target="get pods -A",
            argv=("kubectl", "get", "pods", "-A"),
        ),
        PlannedRequest(
            method="docker",
            target="ps",
            argv=("docker", "ps", "--format", "json"),
        ),
        PlannedRequest(
            method="GET",
            target="http://localhost:4318/v1/traces",
        ),
        PlannedRequest(
            method="sqlite",
            target="review_sessions.db",
        ),
        PlannedRequest(
            method="valkey",
            target="INFO",
        ),
    ]


def plan_telemetry_status(endpoint: str) -> list[PlannedRequest]:
    """Generate planned requests for telemetry status collector probe."""
    return [
        PlannedRequest(
            method="PROBE",
            target=f"{endpoint}/v1/traces",
        )
    ]


def plan_telemetry_connect(
    context: str | None,
    namespace: str,
    service: str,
    save: bool,
) -> list[PlannedRequest]:
    """Generate planned requests for telemetry connect cluster probe."""
    argv: tuple[str, ...]
    if context:
        argv = (
            "kubectl",
            "--context",
            context,
            "get",
            "service",
            service,
            "-n",
            namespace,
            "-o",
            "json",
        )
    else:
        argv = ("kubectl", "get", "service", service, "-n", namespace, "-o", "json")

    return [
        PlannedRequest(
            method="kubectl",
            target=f"service/{service}",
            argv=argv,
        ),
        PlannedRequest(
            method="PROBE",
            target="<collector-endpoint>",
        ),
    ]


def plan_telemetry_test(
    name: str,
    endpoint: str,
    logfire: bool = False,
) -> list[PlannedRequest]:
    """Generate planned requests for telemetry test trace emission."""
    requests = [
        PlannedRequest(
            method="POST",
            target=f"{endpoint}/v1/traces",
            stdin=f"<span-payload:{name}>",
        )
    ]
    if logfire:
        requests.append(
            PlannedRequest(
                method="POST",
                target="https://logfire-api.pydantic.dev/v1/traces",
                condition="logfire configured",
            )
        )
    return requests


def plan_telemetry_profile(
    command: str | None,
    trace_id: str | None,
    tempo_url: str | None,
) -> list[PlannedRequest]:
    """Generate planned requests for telemetry profile trace inspection."""
    requests: list[PlannedRequest] = []
    if command:
        argv = tuple(shlex.split(command))
        requests.append(
            PlannedRequest(
                method="exec",
                target=command,
                argv=argv,
            )
        )
    target_trace = trace_id or "<trace-id>"
    base_tempo = tempo_url or "<tempo-url>"
    requests.append(
        PlannedRequest(
            method="GET",
            target=f"{base_tempo}/api/traces/{target_trace}",
        )
    )
    return requests


def plan_telemetry_semconv_refresh(commit: str) -> list[PlannedRequest]:
    """Generate planned requests for semantic conventions refresh."""
    from devops_cli.telemetry.semconv import weaver_package_argv

    argv = tuple(weaver_package_argv("weaver", commit, Path("<tmp>/package")))
    return [
        PlannedRequest(
            method="weaver",
            target=f"registry@{commit}",
            argv=argv,
        )
    ]
