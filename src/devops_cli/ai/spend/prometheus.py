"""The spend ledger in Prometheus exposition format, for `--format prometheus` and `/metrics`.

Each value is a snapshot of the ledger over the date range of a report, which gets smaller
with `--days`, so each family is a gauge. Each name starts with `devops_cli_ai_ledger_` and is
not the name of an OTLP instrument in `devops_cli.telemetry.instruments`. A dashboard that adds
up a counter by its name thus never adds a ledger snapshot to it (#1631).
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import TYPE_CHECKING, Any

from prometheus_client import CollectorRegistry, generate_latest
from prometheus_client.core import GaugeMetricFamily

if TYPE_CHECKING:
    from devops_cli.ai.spend.ledger import SpendLedger
    from devops_cli.ai.spend.models import LifetimeSpendReport


def _yield_overview_gauges(report: LifetimeSpendReport) -> Iterator[GaugeMetricFamily]:
    """Yield high-level aggregate gauge metric families."""
    yield GaugeMetricFamily(
        "devops_cli_ai_ledger_active_servers",
        "Number of active AI backend services tracked",
        value=report.active_servers_count,
    )
    yield GaugeMetricFamily(
        "devops_cli_ai_ledger_active_models",
        "Number of unique AI models used",
        value=report.active_models_count,
    )
    # A savings value is None when a reference model has no price, and its gauge is left out,
    # so a scrape reads no savings rather than $0 (#1672).
    for name, documentation, value in (
        (
            "devops_cli_ai_ledger_local_cost_equivalent_usd",
            "Cost equivalent in USD of local model calls under reference model",
            report.local_cost_equivalent_usd,
        ),
        (
            "devops_cli_ai_ledger_counterfactual_spend_usd",
            "Counterfactual hosted spend in USD under reference model",
            report.counterfactual_spend_usd,
        ),
        (
            "devops_cli_ai_ledger_counterfactual_savings_usd",
            "Estimated cloud spend avoided in USD",
            report.counterfactual_savings_usd,
        ),
    ):
        if value is not None:
            yield GaugeMetricFamily(name, documentation, value=round(value, 6))
    if report.hardware_payoff:
        payoff = report.hardware_payoff
        yield GaugeMetricFamily(
            "devops_cli_ai_ledger_hardware_cost_usd",
            "Total hardware investment cost in USD",
            value=round(payoff.hardware_cost_usd, 2),
        )
        yield GaugeMetricFamily(
            "devops_cli_ai_ledger_hardware_payoff_percentage",
            "Percentage of hardware investment amortized by local savings",
            value=round(payoff.payoff_percentage, 2),
        )
        yield GaugeMetricFamily(
            "devops_cli_ai_ledger_hardware_net_value_usd",
            "Net profit or remaining investment in USD",
            value=round(payoff.net_value_usd, 4),
        )


def _yield_server_spend_gauges(report: LifetimeSpendReport) -> Iterator[GaugeMetricFamily]:
    """Yield per-server lifetime spend gauge metric family."""
    if not report.servers:
        return
    family = GaugeMetricFamily(
        "devops_cli_ai_ledger_server_spend_usd",
        "Cumulative spend in USD aggregated by backend server",
        labels=["provider", "server"],
    )
    for srv in report.servers:
        family.add_metric([srv.provider, srv.server], round(srv.approx_spend_usd, 6))
    yield family


def _yield_model_gauges(report: LifetimeSpendReport) -> Iterator[GaugeMetricFamily]:
    """Yield model-level spend, request, and token gauge metric families."""
    if not report.models:
        return
    spend_family = GaugeMetricFamily(
        "devops_cli_ai_ledger_spend_usd",
        "Approximate AI spend in USD per model in the ledger",
        labels=["model", "provider"],
    )
    requests_family = GaugeMetricFamily(
        "devops_cli_ai_ledger_requests",
        "AI model requests executed per model in the ledger",
        labels=["model", "provider"],
    )
    tokens_family = GaugeMetricFamily(
        "devops_cli_ai_ledger_tokens",
        "Tokens processed per model in the ledger, by token type (prompt, completion, or reasoning)",
        labels=["model", "provider", "type"],
    )
    # Replies the response cache answered ran no model, and add no tokens or spend here. No
    # sample holds the total tokens: a sum by name would count each token twice.
    for mdl in report.models:
        spend_family.add_metric([mdl.model, mdl.provider], round(mdl.approx_spend_usd, 6))
        requests_family.add_metric(
            [mdl.model, mdl.provider], mdl.request_count - mdl.cached_requests
        )
        for token_type, token_val in (
            ("prompt", mdl.prompt_tokens),
            ("completion", mdl.completion_tokens),
        ):
            tokens_family.add_metric([mdl.model, mdl.provider, token_type], token_val)
        if mdl.reasoning_tokens > 0:
            tokens_family.add_metric([mdl.model, mdl.provider, "reasoning"], mdl.reasoning_tokens)
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
    """Custom prometheus_client collector computing the ledger's gauge families at scrape time."""

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
        """Yield the ledger's gauge metric families."""
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
        yield from _yield_model_gauges(resolved)


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
