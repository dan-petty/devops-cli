"""Prometheus metrics exporter for AI/LLM request spend, tokens, and model pricing."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from devops_cli.ai.spend.ledger import SpendLedger
    from devops_cli.ai.spend.models import LifetimeSpendReport


def _escape_label_value(val: str) -> str:
    """Escape backslashes, double quotes, and newlines in Prometheus label values."""
    return str(val).replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def _format_labels(labels: dict[str, str]) -> str:
    """Format label dictionary into Prometheus {k="v",...} string."""
    if not labels:
        return ""
    pairs = [f'{k}="{_escape_label_value(v)}"' for k, v in sorted(labels.items())]
    return "{" + ",".join(pairs) + "}"


def _build_overview_gauges(report: LifetimeSpendReport) -> list[str]:
    """Format high-level aggregate gauge metrics."""
    return [
        "# HELP devops_cli_ai_active_servers Number of active AI backend services tracked",
        "# TYPE devops_cli_ai_active_servers gauge",
        f"devops_cli_ai_active_servers {report.active_servers_count}",
        "",
        "# HELP devops_cli_ai_active_models Number of unique AI models used",
        "# TYPE devops_cli_ai_active_models gauge",
        f"devops_cli_ai_active_models {report.active_models_count}",
        "",
    ]


def _build_server_spend_gauges(report: LifetimeSpendReport) -> list[str]:
    """Format per-server lifetime spend and token metrics."""
    if not report.servers:
        return []
    lines = [
        "# HELP devops_cli_ai_server_spend_usd Cumulative spend in USD aggregated by backend server",
        "# TYPE devops_cli_ai_server_spend_usd gauge",
    ]
    for s in report.servers:
        lbl = _format_labels({"server": s.server, "provider": s.provider})
        lines.append(f"devops_cli_ai_server_spend_usd{lbl} {s.approx_spend_usd:.6f}")
    lines.append("")
    return lines


def _build_model_counters(report: LifetimeSpendReport) -> list[str]:
    """Format model-level spend, request, and token counters."""
    if not report.models:
        return []
    lines = [
        "# HELP devops_cli_ai_spend_usd_total Total approximate AI spend in USD per model",
        "# TYPE devops_cli_ai_spend_usd_total counter",
    ]
    for m in report.models:
        lbl = _format_labels({"model": m.model, "provider": m.provider})
        lines.append(f"devops_cli_ai_spend_usd_total{lbl} {m.approx_spend_usd:.6f}")
    lines.append("")

    lines.extend(
        [
            "# HELP devops_cli_ai_requests_total Total number of AI model requests executed",
            "# TYPE devops_cli_ai_requests_total counter",
        ]
    )
    for m in report.models:
        lbl = _format_labels({"model": m.model, "provider": m.provider})
        lines.append(f"devops_cli_ai_requests_total{lbl} {m.request_count}")
    lines.append("")

    lines.extend(
        [
            "# HELP devops_cli_ai_tokens_total Total tokens processed by model and token type",
            "# TYPE devops_cli_ai_tokens_total counter",
        ]
    )
    for m in report.models:
        for t_name, t_val in (
            ("prompt", m.prompt_tokens),
            ("completion", m.completion_tokens),
            ("total", m.total_tokens),
        ):
            lbl = _format_labels({"model": m.model, "provider": m.provider, "type": t_name})
            lines.append(f"devops_cli_ai_tokens_total{lbl} {t_val}")
    lines.append("")
    return lines


def export_ai_spend_prometheus(ledger: SpendLedger | None = None) -> str:
    """Export lifetime AI spend, tokens, and server metrics in Prometheus text exposition format."""
    from devops_cli.ai.spend.ledger import get_spend_ledger

    active_ledger = ledger or get_spend_ledger()
    try:
        report = active_ledger.get_lifetime_report(group_by="all")
    except Exception:
        return ""

    lines: list[str] = []
    lines.extend(_build_overview_gauges(report))
    lines.extend(_build_server_spend_gauges(report))
    lines.extend(_build_model_counters(report))
    return "\n".join(lines).strip() + "\n" if lines else ""
