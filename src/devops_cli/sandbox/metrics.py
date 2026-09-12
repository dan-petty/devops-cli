"""Real-time container cgroup v2 metrics telemetry and Prometheus scraping engine."""

from __future__ import annotations

import json
import re
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx2

from devops_cli.core.validation import validate_url_egress
from devops_cli.sandbox.models import (
    CgroupV2Metrics,
    PrometheusMetric,
    SandboxInstance,
    SandboxMetricsSnapshot,
)

_MAX_ERROR_LEN = 256
_METRIC_LINE_REGEX = re.compile(
    r"^(?P<name>[a-zA-Z_:][a-zA-Z0-9_:]*)(?:\{(?P<labels>[^}]*)\})?\s+(?P<value>[^\s]+)(?:\s+(?P<ts>\d+))?$"
)
_LABEL_REGEX = re.compile(r'([a-zA-Z_][a-zA-Z0-9_]*)="([^"\\]*(?:\\.[^"\\]*)*)"')
_UNESCAPE_MAP = {r"\"": '"', r"\\": "\\", r"\n": "\n"}
_UNESCAPE_REGEX = re.compile(r'\\["\\n]')


def _unescape_prom_label(val: str) -> str:
    """Unescape standard Prometheus exposition label value escape sequences."""
    return _UNESCAPE_REGEX.sub(lambda m: _UNESCAPE_MAP.get(m.group(0), m.group(0)), val)


def _truncate(text: Any, max_len: int = _MAX_ERROR_LEN) -> str:
    """Safely truncate strings to prevent log bloat and injection."""
    s = str(text)
    return s if len(s) <= max_len else s[: max_len - 3] + "..."


def _calculate_cpu_percent(
    cpu_usec: int,
    previous_cpu_usec: int | None,
    elapsed_sec: float | None,
) -> float:
    """Calculate CPU percentage from cumulative microseconds delta."""
    if previous_cpu_usec is not None and elapsed_sec is not None and elapsed_sec > 0:
        delta_usec = max(0, cpu_usec - previous_cpu_usec)
        return round(min((delta_usec / (elapsed_sec * 1_000_000.0)) * 100.0, 100.0), 2)
    return 0.0


def _calculate_memory_percent(
    current_bytes: int | None,
    limit_bytes: int | None,
) -> float | None:
    """Calculate memory consumption percentage against cgroup limit."""
    if current_bytes and limit_bytes and limit_bytes > 0:
        return round((current_bytes / limit_bytes) * 100.0, 2)
    return None


def parse_cgroup_v2_directory(
    cgroup_dir: Path | str,
    previous_cpu_usec: int | None = None,
    elapsed_sec: float | None = None,
) -> CgroupV2Metrics | None:
    """Parse cgroup v2 filesystem controllers and extract resource metrics."""
    base = Path(cgroup_dir)
    if not base.is_dir():
        return None

    mem_current = _read_int_file(base / "memory.current")
    mem_peak = _read_int_file(base / "memory.peak")
    mem_max_raw = _read_str_file(base / "memory.max")
    mem_limit = int(mem_max_raw) if mem_max_raw.isdigit() else None
    mem_pct = _calculate_memory_percent(mem_current, mem_limit)

    pids_current = _read_int_file(base / "pids.current") or 0
    cpu_stats = _parse_key_value_file(base / "cpu.stat")
    mem_stats = _parse_key_value_file(base / "memory.stat")
    io_bytes = _parse_io_stat(base / "io.stat")
    net_io = _parse_network_stat(base)

    page_faults = int(mem_stats.get("pgfault", 0))
    cpu_usec = int(cpu_stats.get("usage_usec", 0))
    cpu_percent = _calculate_cpu_percent(cpu_usec, previous_cpu_usec, elapsed_sec)

    return CgroupV2Metrics(
        cpu_percent=cpu_percent,
        cpu_usage_usec=cpu_usec,
        memory_current_bytes=mem_current or 0,
        memory_peak_bytes=mem_peak,
        memory_limit_bytes=mem_limit,
        memory_usage_percent=mem_pct,
        page_faults_total=page_faults,
        pids_current=pids_current,
        io_read_bytes=io_bytes[0],
        io_write_bytes=io_bytes[1],
        network_rx_bytes=net_io[0],
        network_tx_bytes=net_io[1],
    )


def _parse_network_stat(base: Path) -> tuple[int, int]:
    """Parse network rx and tx bytes from cgroup v2 directory or network stat file."""
    for candidate in ("network.stat", "net.stat"):
        stat_file = base / candidate
        if stat_file.is_file():
            stats = _parse_key_value_file(stat_file)
            rx = _safe_int(stats.get("rx_bytes", "0"))
            tx = _safe_int(stats.get("tx_bytes", "0"))
            return rx, tx
    return 0, 0


def _read_int_file(file_path: Path) -> int | None:
    """Read single integer from file if readable."""
    try:
        if file_path.is_file():
            return int(file_path.read_text(encoding="utf-8").strip())
    except OSError, ValueError:
        return None
    return None


def _read_str_file(file_path: Path) -> str:
    """Read string contents from file if readable."""
    try:
        if file_path.is_file():
            return file_path.read_text(encoding="utf-8").strip()
    except OSError:
        return ""
    return ""


def _parse_key_value_file(file_path: Path) -> dict[str, str]:
    """Parse space-separated key-value file into dictionary."""
    result: dict[str, str] = {}
    content = _read_str_file(file_path)
    for line in content.splitlines():
        parts = line.strip().split(maxsplit=1)
        if len(parts) == 2:
            result[parts[0]] = parts[1]
    return result


def _parse_io_stat(file_path: Path) -> tuple[int, int]:
    """Parse io.stat file and sum read/write bytes across block devices."""
    rbytes_total = 0
    wbytes_total = 0
    content = _read_str_file(file_path)
    for line in content.splitlines():
        parts = line.strip().split()
        for token in parts[1:]:
            if token.startswith("rbytes="):
                rbytes_total += _safe_int(token.split("=")[1])
            elif token.startswith("wbytes="):
                wbytes_total += _safe_int(token.split("=")[1])
    return rbytes_total, wbytes_total


def _safe_int(val: str) -> int:
    """Safely convert string to integer."""
    try:
        return int(val)
    except ValueError:
        return 0


def _parse_size_bytes(size_str: str) -> int:
    """Parse human readable size string (e.g. '100MiB', '1.2MB') to bytes."""
    clean = size_str.strip().replace(" ", "")
    units = {
        "b": 1,
        "k": 1000,
        "kb": 1000,
        "kib": 1024,
        "m": 1000 * 1000,
        "mb": 1000 * 1000,
        "mib": 1024 * 1024,
        "g": 1000 * 1000 * 1000,
        "gb": 1000 * 1000 * 1000,
        "gib": 1024 * 1024 * 1024,
    }
    match = re.match(r"^([0-9.]+)([a-zA-Z]*)$", clean)
    if not match:
        return 0
    num, unit = match.groups()
    multiplier = units.get(unit.lower(), 1)
    try:
        return int(float(num) * multiplier)
    except ValueError:
        return 0


def _read_container_stats_fallback(container_id: str) -> CgroupV2Metrics | None:
    """Read container stats via docker stats command as cgroup fallback."""
    cmd = ["docker", "stats", "--no-stream", "--format", "{{json .}}", container_id]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=5.0, check=False)
        if res.returncode != 0 or not res.stdout.strip():
            return None
        data = json.loads(res.stdout.strip().splitlines()[0])
        return _build_metrics_from_docker_dict(data)
    except subprocess.SubprocessError, json.JSONDecodeError, OSError:
        return None


def _parse_docker_net_io(net_io_str: str) -> tuple[int, int]:
    """Parse docker stats NetIO string (e.g. '1.2MB / 3.4MB') into rx and tx bytes."""
    if "/" in net_io_str:
        parts = net_io_str.split("/", 1)
        return _parse_size_bytes(parts[0]), _parse_size_bytes(parts[1])
    return 0, 0


def _build_metrics_from_docker_dict(data: dict[str, Any]) -> CgroupV2Metrics:
    """Convert docker stats JSON dictionary into CgroupV2Metrics model."""
    cpu_str = str(data.get("CPUPerc", "0.0%")).replace("%", "").strip()
    cpu_val = float(cpu_str) if cpu_str.replace(".", "", 1).isdigit() else 0.0

    mem_usage_str = str(data.get("MemUsage", ""))
    mem_curr, mem_lim = 0, None
    if "/" in mem_usage_str:
        used_part, lim_part = mem_usage_str.split("/", 1)
        mem_curr = _parse_size_bytes(used_part)
        mem_lim = _parse_size_bytes(lim_part)

    mem_pct_str = str(data.get("MemPerc", "0.0%")).replace("%", "").strip()
    mem_pct = float(mem_pct_str) if mem_pct_str.replace(".", "", 1).isdigit() else None

    pids_str = str(data.get("PIDs", "0")).strip()
    pids_val = int(pids_str) if pids_str.isdigit() else 0

    net_io_str = str(data.get("NetIO", ""))
    rx_bytes, tx_bytes = _parse_docker_net_io(net_io_str)

    return CgroupV2Metrics(
        cpu_percent=cpu_val,
        memory_current_bytes=mem_curr,
        memory_limit_bytes=mem_lim,
        memory_usage_percent=mem_pct,
        pids_current=pids_val,
        network_rx_bytes=rx_bytes,
        network_tx_bytes=tx_bytes,
    )


def read_cgroup_v2_metrics(
    container_id: str | None = None,
    cgroup_path: Path | str | None = None,
    previous_cpu_usec: int | None = None,
    elapsed_sec: float | None = None,
) -> CgroupV2Metrics | None:
    """Read cgroup v2 metrics from filesystem path with fallback to container inspect."""
    has_delta = previous_cpu_usec is not None or elapsed_sec is not None

    if cgroup_path:
        return (
            parse_cgroup_v2_directory(
                cgroup_path,
                previous_cpu_usec=previous_cpu_usec,
                elapsed_sec=elapsed_sec,
            )
            if has_delta
            else parse_cgroup_v2_directory(cgroup_path)
        )

    if container_id:
        standard_paths = [
            Path(f"/sys/fs/cgroup/system.slice/docker-{container_id}.scope"),
            Path(f"/sys/fs/cgroup/docker/{container_id}"),
            Path(f"/sys/fs/cgroup/{container_id}"),
        ]
        for candidate in standard_paths:
            metrics = (
                parse_cgroup_v2_directory(
                    candidate,
                    previous_cpu_usec=previous_cpu_usec,
                    elapsed_sec=elapsed_sec,
                )
                if has_delta
                else parse_cgroup_v2_directory(candidate)
            )
            if metrics is not None:
                return metrics

        return _read_container_stats_fallback(container_id)

    return None


def parse_prometheus_exposition(text: str) -> list[PrometheusMetric]:
    """Parse Prometheus text exposition format into structured models."""
    type_map: dict[str, str] = {}
    metrics: list[PrometheusMetric] = []

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("# HELP"):
            continue
        if line.startswith("# TYPE"):
            _record_type(line, type_map)
            continue
        metric = _parse_metric_line(line, type_map)
        if metric is not None:
            metrics.append(metric)

    return metrics


def _record_type(line: str, type_map: dict[str, str]) -> None:
    """Record metric type definition from comment line."""
    parts = line.split(maxsplit=3)
    if len(parts) >= 4:
        type_map[parts[2]] = parts[3].lower()


def _parse_metric_line(line: str, type_map: dict[str, str]) -> PrometheusMetric | None:
    """Parse single metric sample line with labels and value."""
    match = _METRIC_LINE_REGEX.match(line)
    if not match:
        return None

    name = match.group("name")
    val_str = match.group("value")
    labels_str = match.group("labels")

    try:
        val = float(val_str)
    except ValueError:
        return None

    labels: dict[str, str] = {}
    if labels_str:
        for lbl_match in _LABEL_REGEX.finditer(labels_str):
            labels[lbl_match.group(1)] = _unescape_prom_label(lbl_match.group(2))

    metric_type = type_map.get(name, _infer_metric_type(name))

    return PrometheusMetric(
        name=name,
        metric_type=metric_type,
        labels=labels,
        value=val,
    )


def _infer_metric_type(name: str) -> str:
    """Infer metric type from naming conventions if not explicitly typed."""
    if name.endswith("_total") or name.endswith("_count"):
        return "counter"
    if name.endswith("_bucket"):
        return "histogram"
    return "gauge"


class PrometheusScrapeResult(list[PrometheusMetric]):
    """Result of scraping a Prometheus metrics endpoint with error tracking."""

    def __init__(
        self,
        metrics: list[PrometheusMetric] | None = None,
        error: str | None = None,
    ) -> None:
        super().__init__(metrics or [])
        self.error = error


def scrape_prometheus_metrics(
    metrics_url: str,
    timeout: float = 5.0,
) -> PrometheusScrapeResult:
    """Scrape Prometheus metrics endpoint over HTTP and parse exposition text."""
    try:
        validated_url = validate_url_egress(
            metrics_url,
            purpose="Prometheus metrics scrape",
            allow_private=True,
        )
    except Exception as exc:
        return PrometheusScrapeResult(
            [],
            error=_truncate(f"SSRF validation blocked scrape URL: {exc}"),
        )

    try:
        with httpx2.Client(timeout=timeout) as client:
            resp = client.get(validated_url, headers={"User-Agent": "devops-cli-metrics"})
            if resp.status_code != 200:
                return PrometheusScrapeResult(
                    [],
                    error=_truncate(f"HTTP {resp.status_code} response from {metrics_url}"),
                )
            metrics = parse_prometheus_exposition(resp.text)
            return PrometheusScrapeResult(metrics, error=None)
    except Exception as exc:
        return PrometheusScrapeResult(
            [],
            error=_truncate(f"Scrape request failed for {metrics_url}: {exc}"),
        )


def evaluate_threshold_warnings(
    cgroup: CgroupV2Metrics | None,
    prom_metrics: list[PrometheusMetric],
    memory_threshold_pct: float = 80.0,
    cpu_threshold_pct: float = 85.0,
    previous_cgroup: CgroupV2Metrics | None = None,
    latency_threshold_ms: float = 500.0,
) -> list[str]:
    """Evaluate container and application metrics against operating thresholds."""
    warnings: list[str] = []

    if cgroup:
        _evaluate_cgroup_thresholds(
            cgroup,
            memory_threshold_pct,
            cpu_threshold_pct,
            warnings,
            previous_cgroup=previous_cgroup,
        )

    if prom_metrics:
        _evaluate_prom_thresholds(
            prom_metrics,
            warnings,
            latency_threshold_ms=latency_threshold_ms,
        )

    return warnings


def _evaluate_cgroup_thresholds(
    cgroup: CgroupV2Metrics,
    mem_thresh: float,
    cpu_thresh: float,
    warnings: list[str],
    previous_cgroup: CgroupV2Metrics | None = None,
) -> None:
    """Evaluate cgroup memory and CPU limits and leak trajectories."""
    if cgroup.memory_usage_percent is not None and cgroup.memory_usage_percent > mem_thresh:
        warnings.append(
            _truncate(
                f"Memory usage ({cgroup.memory_usage_percent:.1f}%) exceeds warning threshold ({mem_thresh:.1f}%)"
            )
        )

    if cgroup.cpu_percent > cpu_thresh:
        warnings.append(
            _truncate(
                f"CPU utilization ({cgroup.cpu_percent:.1f}%) exceeds warning threshold ({cpu_thresh:.1f}%)"
            )
        )

    if previous_cgroup and previous_cgroup.memory_current_bytes > 0:
        growth_bytes = cgroup.memory_current_bytes - previous_cgroup.memory_current_bytes
        growth_pct = (growth_bytes / previous_cgroup.memory_current_bytes) * 100.0
        if growth_pct >= 20.0 and growth_bytes >= 5 * 1024 * 1024:
            warnings.append(
                _truncate(
                    f"Potential memory leak trajectory: usage increased by {growth_pct:.1f}% "
                    f"({growth_bytes // (1024 * 1024)}MB) between samples"
                )
            )


def _evaluate_prom_thresholds(
    prom_metrics: list[PrometheusMetric],
    warnings: list[str],
    latency_threshold_ms: float = 500.0,
) -> None:
    """Evaluate application error rates and latency SLAs from scraped Prometheus metrics."""
    _evaluate_prom_error_rate(prom_metrics, warnings)
    _evaluate_prom_latency(prom_metrics, latency_threshold_ms, warnings)


def _evaluate_prom_error_rate(
    prom_metrics: list[PrometheusMetric],
    warnings: list[str],
) -> None:
    """Evaluate HTTP 5xx error rate from Prometheus request counters."""
    req_total = 0.0
    err_total = 0.0

    for m in prom_metrics:
        if m.name in ("http_requests_total", "http_request_total", "requests_total"):
            code = m.labels.get("code") or m.labels.get("status") or ""
            req_total += m.value
            if code.startswith("5") or m.labels.get("error") in ("true", "1"):
                err_total += m.value

    if req_total > 0 and err_total > 0:
        err_pct = (err_total / req_total) * 100.0
        if err_pct >= 5.0:
            warnings.append(
                _truncate(
                    f"High HTTP 5xx error rate ({err_pct:.1f}% >= 5.0%) detected across {int(req_total)} requests"
                )
            )


def _evaluate_prom_latency(
    prom_metrics: list[PrometheusMetric],
    latency_threshold_ms: float,
    warnings: list[str],
) -> None:
    """Evaluate HTTP request latency SLA from Prometheus histogram sum and count."""
    sums: dict[str, float] = {}
    counts: dict[str, float] = {}

    for m in prom_metrics:
        if m.name.endswith("_duration_seconds_sum") or m.name.endswith("_latency_seconds_sum"):
            base_key = m.name.rsplit("_sum", 1)[0]
            sums[base_key] = sums.get(base_key, 0.0) + m.value
        elif m.name.endswith("_duration_seconds_count") or m.name.endswith(
            "_latency_seconds_count"
        ):
            base_key = m.name.rsplit("_count", 1)[0]
            counts[base_key] = counts.get(base_key, 0.0) + m.value

    for key, sum_val in sums.items():
        count_val = counts.get(key, 0.0)
        if count_val > 0:
            avg_latency_ms = (sum_val / count_val) * 1000.0
            if avg_latency_ms >= latency_threshold_ms:
                warnings.append(
                    _truncate(
                        f"High average request latency ({avg_latency_ms:.1f}ms >= {latency_threshold_ms:.1f}ms) "
                        f"detected for {key}"
                    )
                )


def collect_sandbox_metrics(
    instance_or_target: SandboxInstance | str,
    prom_endpoint: str = "/metrics",
    timeout: float = 5.0,
    memory_threshold_pct: float = 80.0,
    cpu_threshold_pct: float = 85.0,
    previous_cgroup: CgroupV2Metrics | None = None,
    previous_cpu_usec: int | None = None,
    elapsed_sec: float | None = None,
) -> SandboxMetricsSnapshot:
    """Execute end-to-end sandbox metrics collection pipeline."""
    if isinstance(instance_or_target, SandboxInstance):
        instance_id = instance_or_target.instance_id
        target = instance_or_target.name
        cgroup = read_cgroup_v2_metrics(
            container_id=instance_or_target.container_id,
            previous_cpu_usec=previous_cpu_usec,
            elapsed_sec=elapsed_sec,
        )
        host_port = _resolve_instance_port(instance_or_target)
        ep = prom_endpoint if prom_endpoint.startswith("/") else f"/{prom_endpoint}"
        scrape_url = f"http://127.0.0.1:{host_port}{ep}"
    else:
        instance_id = None
        target = str(instance_or_target)
        cgroup = None
        scrape_url = _build_scrape_url(target, prom_endpoint)

    scrape_res = scrape_prometheus_metrics(scrape_url, timeout=timeout)
    prom_metrics = list(scrape_res)
    scrape_error = scrape_res.error

    warnings = evaluate_threshold_warnings(
        cgroup=cgroup,
        prom_metrics=prom_metrics,
        memory_threshold_pct=memory_threshold_pct,
        cpu_threshold_pct=cpu_threshold_pct,
        previous_cgroup=previous_cgroup,
    )
    if scrape_error:
        warnings.append(f"Prometheus scrape warning: {scrape_error}")

    return SandboxMetricsSnapshot(
        instance_id=instance_id,
        target=target,
        cgroup=cgroup,
        prometheus_metrics=prom_metrics,
        scrape_error=scrape_error,
        warnings=warnings,
        timestamp=datetime.now(UTC).isoformat(),
    )


def _resolve_instance_port(instance: SandboxInstance) -> int:
    """Resolve primary host port for sandbox instance."""
    if instance.port_bindings:
        return instance.port_bindings[0].host_port
    return 8080


def _build_scrape_url(target: str, prom_endpoint: str) -> str:
    """Build normalized Prometheus scrape URL."""
    base = target if target.startswith("http") else f"http://{target}"
    ep = prom_endpoint if prom_endpoint.startswith("/") else f"/{prom_endpoint}"
    return f"{base.rstrip('/')}{ep}"


__all__ = [
    "PrometheusScrapeResult",
    "collect_sandbox_metrics",
    "evaluate_threshold_warnings",
    "parse_cgroup_v2_directory",
    "parse_prometheus_exposition",
    "read_cgroup_v2_metrics",
    "scrape_prometheus_metrics",
]
