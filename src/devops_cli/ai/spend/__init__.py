"""AI/LLM request spend tracking and open-source pricing engine."""

from __future__ import annotations

from devops_cli.ai.spend.ledger import SpendLedger, get_spend_ledger, track_request_spend
from devops_cli.ai.spend.models import (
    HardwarePayoffSummary,
    LifetimeSpendReport,
    ModelPricing,
    ModelSpendSummary,
    ProviderSpendSummary,
    ServerSpendSummary,
    SpendRecord,
    StageSpendSummary,
)
from devops_cli.ai.spend.payoff import compute_hardware_payoff
from devops_cli.ai.spend.pricing import PricingRegistry, get_pricing_registry, is_local
from devops_cli.ai.spend.prometheus import export_ai_spend_prometheus
from devops_cli.ai.spend.stage import current_stage, resolve_spend_stage, stage_scope

__all__ = [
    "HardwarePayoffSummary",
    "LifetimeSpendReport",
    "ModelPricing",
    "ModelSpendSummary",
    "PricingRegistry",
    "ProviderSpendSummary",
    "ServerSpendSummary",
    "SpendLedger",
    "SpendRecord",
    "StageSpendSummary",
    "compute_hardware_payoff",
    "current_stage",
    "export_ai_spend_prometheus",
    "get_pricing_registry",
    "get_spend_ledger",
    "is_local",
    "resolve_spend_stage",
    "stage_scope",
    "track_request_spend",
]
