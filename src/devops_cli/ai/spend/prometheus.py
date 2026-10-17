"""Prometheus metrics exporter for AI/LLM request spend, tokens, and model pricing."""

from __future__ import annotations

from collections.abc import Iterator
from typing import TYPE_CHECKING, Any

from prometheus_client import CollectorRegistry, generate_latest
from prometheus_client.core import CounterMetricFamily, GaugeMetricFamily

if TYPE_CHECKING:
    from devops_cli.ai.spend.ledger import SpendLedger
    from devops_cli.ai.spend.models import LifetimeSpendReport


def _yield_overview_gauges(report: LifetimeSpendReport) -> Iterator[GaugeMetricFamily]:
    """Yield high-level aggregate gauge metric families."""
    yield GaugeMetricFamily(
        "devops_cli_ai_active_servers",
        "Number of active AI backend services tracked",
        value=report.active_servers_count,
    )
    yield GaugeMetricFamily(
        "devops_cli_ai_active_models",
        "Number of unique AI models used",
        value=report.active_models_count,
    )
    yield GaugeMetricFamily(
        "devops_cli_ai_local_cost_equivalent_usd",
        "Cost equivalent in USD of local model calls under reference model",
        value=round(report.local_cost_equivalent_usd, 6),
    )
    yield GaugeMetricFamily(
        "devops_cli_ai_counterfactual_spend_usd",
        "Counterfactual hosted spend in USD under reference model",
        value=round(report.counterfactual_spend_usd, 6),
    )
    yield GaugeMetricFamily(
        "devops_cli_ai_counterfactual_savings_usd",
        "Estimated cloud spend avoided in USD",
        value=round(report.counterfactual_savings_usd, 6),
    )
    if report.hardware_payoff:
        payoff = report.hardware_payoff
        yield GaugeMetricFamily(
            "devops_cli_ai_hardware_cost_usd",
            "Total hardware investment cost in USD",
            value=round(payoff.hardware_cost_usd, 2),
        )
        yield GaugeMetricFamily(
            "devops_cli_ai_hardware_payoff_percentage",
            "Percentage of hardware investment amortized by local savings",
            value=round(payoff.payoff_percentage, 2),
        )
        yield GaugeMetricFamily(
            "devops_cli_ai_hardware_net_value_usd",
            "Net profit or remaining investment in USD",
            value=round(payoff.net_value_usd, 4),
        )


def _yield_server_spend_gauges(report: LifetimeSpendReport) -> Iterator[GaugeMetricFamily]:
    """Yield per-server lifetime spend gauge metric family."""
    if not report.servers:
        return
    family = GaugeMetricFamily(
        "devops_cli_ai_server_spend_usd",
        "Cumulative spend in USD aggregated by backend server",
        labels=["provider", "server"],
    )
    for srv in report.servers:
        family.add_metric([srv.provider, srv.server], round(srv.approx_spend_usd, 6))
    yield family


def _yield_model_counters(report: LifetimeSpendReport) -> Iterator[CounterMetricFamily]:
    """Yield model-level spend, request, and token counter metric families."""
    if not report.models:
        return
    spend_family = CounterMetricFamily(
        "devops_cli_ai_spend_usd_total",
        "Total approximate AI spend in USD per model",
        labels=["model", "provider"],
    )
    requests_family = CounterMetricFamily(
        "devops_cli_ai_requests_total",
        "Total number of AI model requests executed",
        labels=["model", "provider"],
    )
    tokens_family = CounterMetricFamily(
        "devops_cli_ai_tokens_total",
        "Total tokens processed by model and token type",
        labels=["model", "provider", "type"],
    )
    # Replies the response cache answered ran no model, and add no tokens or spend here.
    for mdl in report.models:
        spend_family.add_metric([mdl.model, mdl.provider], round(mdl.approx_spend_usd, 6))
        requests_family.add_metric(
            [mdl.model, mdl.provider], mdl.request_count - mdl.cached_requests
        )
        for token_type, token_val in (
            ("prompt", mdl.prompt_tokens),
            ("completion", mdl.completion_tokens),
            ("total", mdl.total_tokens),
        ):
            tokens_family.add_metric([mdl.model, mdl.provider, token_type], token_val)
    yield spend_family
    yield requests_family
    yield tokens_family


def _resolve_spend_report(
    ledger: SpendLedger | None = None,
    report: LifetimeSpendReport | None = None,
    days: int | None = None,
    reference_model: str | None = None,
    hardware_cost_usd: float | None = None,
) -> LifetimeSpendReport | None:
    if report is not None:
        return report
    from devops_cli.ai.spend.ledger import get_spend_ledger

    active_ledger = ledger or get_spend_ledger()
    try:
        return active_ledger.get_lifetime_report(
            days=days,
            group_by="all",
            reference_model=reference_model,
            hardware_cost_usd=hardware_cost_usd,
        )
    except Exception:
        return None


class AISpendCollector:
    """Custom prometheus_client collector computing AI spend metric families at scrape time."""

    def __init__(
        self,
        ledger: SpendLedger | None = None,
        report: LifetimeSpendReport | None = None,
        days: int | None = None,
        reference_model: str | None = None,
        hardware_cost_usd: float | None = None,
    ) -> None:
        self._ledger = ledger
        self._report = report
        self._days = days
        self._reference_model = reference_model
        self._hardware_cost_usd = hardware_cost_usd

    def collect(self) -> Iterator[Any]:
        """Yield AI spend gauge and counter metric families."""
        resolved = _resolve_spend_report(
            ledger=self._ledger,
            report=self._report,
            days=self._days,
            reference_model=self._reference_model,
            hardware_cost_usd=self._hardware_cost_usd,
        )
        if resolved is None:
            return
        yield from _yield_overview_gauges(resolved)
        yield from _yield_server_spend_gauges(resolved)
        yield from _yield_model_counters(resolved)


def export_ai_spend_prometheus(
    ledger: SpendLedger | None = None,
    report: LifetimeSpendReport | None = None,
    days: int | None = None,
    reference_model: str | None = None,
    hardware_cost_usd: float | None = None,
) -> str:
    """Export lifetime AI spend, tokens, and server metrics in Prometheus text exposition format."""
    resolved = _resolve_spend_report(
        ledger=ledger,
        report=report,
        days=days,
        reference_model=reference_model,
        hardware_cost_usd=hardware_cost_usd,
    )
    if resolved is None:
        return ""
    registry = CollectorRegistry(auto_describe=True)
    registry.register(AISpendCollector(report=resolved))
    return generate_latest(registry).decode("utf-8")
