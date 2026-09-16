"""Kubernetes Falco eBPF runtime security streaming, anomaly detection, and alert filtering."""

from __future__ import annotations

import json
import logging
import re
import time
from typing import Any

from devops_cli.config.constants import CONST_FALCO_SEVERITY_LEVELS
from devops_cli.core.process import run_subprocess
from devops_cli.models.k8s import (
    FalcoAlert,
    SecurityStreamRequest,
    SecurityStreamResult,
)
from devops_cli.output import (
    print_info,
    print_panel,
)
from devops_cli.telemetry import record_metric, trace_span

logger = logging.getLogger(__name__)

SEVERITY_LEVELS = CONST_FALCO_SEVERITY_LEVELS

# Text alert line regex pattern for standard Falco syslog/terminal output
_TEXT_ALERT_RE = re.compile(
    r"^(?P<time>[^:]+:\d+:\d+(?:\.\d+)?):\s*(?P<priority>[A-Za-z]+)\s*(?P<output>.*)$"
)


def matches_severity_filter(priority: str, min_severity: str | None) -> bool:
    """Evaluate whether an alert priority meets or exceeds the minimum severity threshold."""
    if not min_severity:
        return True
    target_rank = SEVERITY_LEVELS.get(min_severity.upper().strip())
    if target_rank is None:
        return False
    alert_rank = SEVERITY_LEVELS.get(priority.upper().strip())
    if alert_rank is None:
        return False
    return alert_rank >= target_rank


def _parse_json_falco_alert(data: dict[str, Any]) -> FalcoAlert:
    """Construct FalcoAlert model instance from decoded JSON dictionary."""
    return FalcoAlert(
        time=str(data.get("time", "")),
        rule=str(data.get("rule", "Custom Security Rule")),
        priority=str(data.get("priority", "Warning")),
        source=str(data.get("source", "syscall")),
        output=str(data.get("output", "")),
        output_fields=data.get("output_fields", {}),
        tags=data.get("tags", []),
    )


def _parse_text_falco_alert(line: str) -> FalcoAlert | None:
    """Parse traditional formatted text line into FalcoAlert."""
    match = _TEXT_ALERT_RE.match(line)
    if not match:
        return FalcoAlert(
            time="",
            rule="Raw Syscall Alert",
            priority="Warning",
            source="syscall",
            output=line,
        )
    prio = match.group("priority").capitalize()
    return FalcoAlert(
        time=match.group("time"),
        rule="Syscall Anomaly Detected",
        priority=prio if prio.upper() in SEVERITY_LEVELS else "Warning",
        source="syscall",
        output=match.group("output").strip(),
    )


def parse_falco_alert(raw_line: str) -> FalcoAlert | None:
    """Parse raw log line into a structured FalcoAlert object."""
    clean_line = raw_line.strip()
    if not clean_line:
        return None
    if clean_line.startswith("{") and clean_line.endswith("}"):
        try:
            data = json.loads(clean_line)
            if isinstance(data, dict):
                return _parse_json_falco_alert(data)
        except Exception:
            pass
    return _parse_text_falco_alert(clean_line)


def generate_simulated_alerts(count: int = 3) -> list[FalcoAlert]:
    """Generate realistic eBPF syscall anomaly detection alerts for dry-runs and validation."""
    templates = [
        FalcoAlert(
            time="2026-09-16T04:20:00.100000Z",
            rule="Terminal shell in container",
            priority="Critical",
            source="syscall",
            output="A shell was spawned in a running container with root privileges (user=root proc=sh k8s.pod=app-worker-67b4c9)",
            output_fields={
                "container.id": "c8f2190ab7e",
                "container.name": "worker",
                "k8s.pod.name": "app-worker-67b4c9",
                "k8s.ns.name": "default",
                "proc.name": "sh",
                "user.name": "root",
            },
            tags=["container", "privilege_escalation", "mitre_execution"],
        ),
        FalcoAlert(
            time="2026-09-16T04:20:01.250000Z",
            rule="Read sensitive file untrusted",
            priority="Warning",
            source="syscall",
            output="Sensitive file /etc/shadow opened for reading by untrusted program (user=app proc=cat fd.name=/etc/shadow)",
            output_fields={
                "container.id": "d14e821bc34",
                "container.name": "api-gateway",
                "k8s.pod.name": "api-gateway-549df",
                "k8s.ns.name": "default",
                "proc.name": "cat",
                "fd.name": "/etc/shadow",
                "user.name": "app",
            },
            tags=["filesystem", "credential_access", "mitre_credential_access"],
        ),
        FalcoAlert(
            time="2026-09-16T04:20:02.500000Z",
            rule="Unexpected outbound connection to external IP",
            priority="Warning",
            source="syscall",
            output="Outbound connection to unapproved public destination (user=root proc=nc rip=198.51.100.25 rport=4444)",
            output_fields={
                "container.id": "f55c340ae11",
                "container.name": "payment-service",
                "k8s.pod.name": "payment-service-89cb1",
                "k8s.ns.name": "production",
                "proc.name": "nc",
                "fd.rip": "198.51.100.25",
                "fd.rport": 4444,
                "user.name": "root",
            },
            tags=["network", "exfiltration", "command_and_control"],
        ),
    ]
    return templates[: max(1, min(count, len(templates)))]


def _build_kubectl_command(request: SecurityStreamRequest) -> list[str]:
    """Construct safe argument list for kubectl logs query against Falco pods."""
    cmd = ["kubectl", "logs", "-n", request.namespace, "-l", request.label_selector]
    cmd.extend(["--tail", str(request.tail_lines)])
    if request.follow:
        cmd.append("-f")
    return cmd


def _tally_severity_counts(alerts: list[FalcoAlert]) -> tuple[int, int, int]:
    """Calculate critical, warning, and notice alert frequency buckets."""
    crit_count = 0
    warn_count = 0
    note_count = 0
    for a in alerts:
        prio = a.priority.upper()
        if prio in ("CRITICAL", "EMERGENCY", "ALERT"):
            crit_count += 1
        elif prio in ("WARNING", "ERROR"):
            warn_count += 1
        elif prio in ("NOTICE", "INFO", "INFORMATIONAL"):
            note_count += 1
    return crit_count, warn_count, note_count


def _process_stream_output(stdout: str, min_severity: str | None) -> list[FalcoAlert]:
    """Parse raw stream output lines and apply minimum severity filtering."""
    matched: list[FalcoAlert] = []
    for line in stdout.splitlines():
        parsed = parse_falco_alert(line)
        if parsed and matches_severity_filter(parsed.priority, min_severity):
            matched.append(parsed)
    return matched


def stream_security_events(
    request: SecurityStreamRequest,
    dry_run: bool = False,
) -> SecurityStreamResult:
    """Stream and filter runtime security anomaly events from Kubernetes Falco probes."""
    start_time = time.monotonic()

    with trace_span(
        "k8s.security_stream",
        attributes={
            "k8s.namespace": request.namespace,
            "k8s.label_selector": request.label_selector,
            "stream.simulate": request.simulate,
            "stream.dry_run": dry_run,
        },
    ) as span:
        if dry_run or request.simulate:
            simulated = generate_simulated_alerts(count=3)
            filtered = [
                a for a in simulated if matches_severity_filter(a.priority, request.severity)
            ]
            elapsed = time.monotonic() - start_time
            crit, warn, note = _tally_severity_counts(filtered)
            span.set_attribute("alerts.count", len(filtered))
            span.set_attribute("alerts.critical", crit)
            return SecurityStreamResult(
                alerts=filtered,
                total_alerts=len(filtered),
                critical_count=crit,
                warning_count=warn,
                notice_count=note,
                duration_seconds=round(elapsed, 3),
            )

        cmd = _build_kubectl_command(request)
        proc = run_subprocess(cmd, timeout=float(request.duration_seconds + 5))

        if proc.returncode != 0:
            logger.debug("kubectl logs failed: %s", proc.stderr[:256])
            elapsed = time.monotonic() - start_time
            return SecurityStreamResult(
                alerts=[],
                total_alerts=0,
                duration_seconds=round(elapsed, 3),
            )

        alerts = _process_stream_output(proc.stdout, request.severity)
        crit, warn, note = _tally_severity_counts(alerts)
        elapsed = time.monotonic() - start_time

        span.set_attribute("alerts.count", len(alerts))
        span.set_attribute("alerts.critical", crit)
        record_metric(
            "devops_cli_k8s_security_alerts_total",
            float(len(alerts)),
            attributes={"namespace": request.namespace, "critical": str(crit > 0)},
        )

        return SecurityStreamResult(
            alerts=alerts,
            total_alerts=len(alerts),
            critical_count=crit,
            warning_count=warn,
            notice_count=note,
            duration_seconds=round(elapsed, 3),
        )


def _get_severity_color(priority: str) -> str:
    """Return styling color markup based on alert priority."""
    prio = priority.upper()
    if prio in ("CRITICAL", "EMERGENCY", "ALERT"):
        return "bold red"
    if prio in ("WARNING", "ERROR"):
        return "bold yellow"
    return "bold blue"


def render_security_alerts(result: SecurityStreamResult) -> None:
    """Format and render security alert events with Rich badges to stdout."""
    if not result.alerts:
        print_info("No security anomaly events detected.")
        return

    for alert in result.alerts:
        color = _get_severity_color(alert.priority)
        time_str = f"[{alert.time}] " if alert.time else ""
        header = f"{time_str}[{color}]{alert.priority.upper()}[/{color}] — {alert.rule}"
        body_lines = [alert.output]
        if alert.output_fields:
            fields_str = " | ".join(f"{k}={v}" for k, v in alert.output_fields.items())
            body_lines.append(f"[dim]{fields_str}[/dim]")
        if alert.tags:
            tags_str = " ".join(f"#{t}" for t in alert.tags)
            body_lines.append(f"[cyan]{tags_str}[/cyan]")

        print_panel("\n".join(body_lines), title=header)
