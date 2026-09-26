"""Hardware investment payoff, break-even projection, and local LLM savings calculation."""

from __future__ import annotations

from datetime import datetime

from devops_cli.ai.spend.models import HardwarePayoffSummary


def _calculate_days_active(
    first_ts: str | None, last_ts: str | None, days_filter: int | None
) -> float:
    """Calculate active calendar days represented in the spend window."""
    if days_filter is not None and days_filter > 0:
        return float(days_filter)
    if not first_ts or not last_ts:
        return 1.0
    try:
        t0 = datetime.fromisoformat(first_ts)
        t1 = datetime.fromisoformat(last_ts)
        diff = (t1 - t0).total_seconds() / 86400.0
        return max(1.0, round(diff, 2))
    except Exception:
        return 1.0


def _estimate_days_to_payoff(
    is_paid_off: bool, remaining_usd: float, daily_savings_usd: float
) -> float | None:
    """Estimate remaining calendar days to break even given current daily run-rate."""
    if is_paid_off:
        return 0.0
    if daily_savings_usd <= 0.0:
        return None
    return round(remaining_usd / daily_savings_usd, 1)


def compute_hardware_payoff(
    *,
    hardware_cost_usd: float,
    local_cost_equivalent_usd: float,
    reference_model: str,
    first_recorded_at: str | None = None,
    last_recorded_at: str | None = None,
    days: int | None = None,
) -> HardwarePayoffSummary:
    """Calculate hardware purchase payoff, net ROI, and break-even trajectory."""
    safe_hardware_cost = max(0.0, float(hardware_cost_usd))
    safe_local_savings = max(0.0, float(local_cost_equivalent_usd))

    days_active = _calculate_days_active(first_recorded_at, last_recorded_at, days)
    daily_savings = round(safe_local_savings / days_active, 4) if days_active > 0 else 0.0
    net_value = round(safe_local_savings - safe_hardware_cost, 4)
    payoff_pct = (
        round((safe_local_savings / safe_hardware_cost) * 100.0, 2)
        if safe_hardware_cost > 0
        else 0.0
    )
    is_paid_off = safe_hardware_cost > 0 and safe_local_savings >= safe_hardware_cost
    remaining = max(0.0, round(safe_hardware_cost - safe_local_savings, 4))
    est_days = _estimate_days_to_payoff(is_paid_off, remaining, daily_savings)

    return HardwarePayoffSummary(
        hardware_cost_usd=round(safe_hardware_cost, 2),
        cumulative_savings_usd=round(safe_local_savings, 4),
        net_value_usd=net_value,
        payoff_percentage=payoff_pct,
        is_paid_off=is_paid_off,
        remaining_usd=remaining,
        daily_savings_usd=daily_savings,
        estimated_days_to_payoff=est_days,
        reference_model=reference_model,
    )
