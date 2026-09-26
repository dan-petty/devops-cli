"""Unit tests for hardware payoff, ROI projections, and local savings amortization."""

from __future__ import annotations

from devops_cli.ai.spend.payoff import (
    _calculate_days_active,
    _estimate_days_to_payoff,
    compute_hardware_payoff,
)


def test_calculate_days_active_branches() -> None:
    """Verify days active calculation from filters, timestamps, and fallbacks."""
    res_filter = _calculate_days_active(None, None, days_filter=7)
    res_fallback = _calculate_days_active(None, None, days_filter=None)
    res_timestamps = _calculate_days_active(
        "2026-09-01T00:00:00Z",
        "2026-09-11T00:00:00Z",
        days_filter=None,
    )
    res_malformed = _calculate_days_active("invalid", "dates", days_filter=None)

    assert (
        res_filter,
        res_fallback,
        res_timestamps,
        res_malformed,
    ) == (
        7.0,
        1.0,
        10.0,
        1.0,
    )


def test_estimate_days_to_payoff_branches() -> None:
    """Verify estimate days to payoff when paid off, with zero savings, or amortizing."""
    paid_off = _estimate_days_to_payoff(True, 0.0, 10.0)
    zero_savings = _estimate_days_to_payoff(False, 500.0, 0.0)
    amortizing = _estimate_days_to_payoff(False, 500.0, 25.0)

    assert (paid_off, zero_savings, amortizing) == (0.0, None, 20.0)


def test_compute_hardware_payoff_amortizing() -> None:
    """Verify hardware payoff calculations for actively amortizing hardware."""
    payoff = compute_hardware_payoff(
        hardware_cost_usd=1600.0,
        local_cost_equivalent_usd=400.0,
        reference_model="gpt-4o",
        first_recorded_at="2026-09-01T00:00:00Z",
        last_recorded_at="2026-09-11T00:00:00Z",
    )

    assert (
        payoff.hardware_cost_usd,
        payoff.cumulative_savings_usd,
        payoff.net_value_usd,
        payoff.payoff_percentage,
        payoff.is_paid_off,
        payoff.remaining_usd,
        payoff.daily_savings_usd,
        payoff.estimated_days_to_payoff,
        payoff.reference_model,
    ) == (
        1600.0,
        400.0,
        -1200.0,
        25.0,
        False,
        1200.0,
        40.0,
        30.0,
        "gpt-4o",
    )


def test_compute_hardware_payoff_fully_paid_off() -> None:
    """Verify hardware payoff calculations when local savings exceed purchase cost."""
    payoff = compute_hardware_payoff(
        hardware_cost_usd=1000.0,
        local_cost_equivalent_usd=1500.0,
        reference_model="gpt-4o",
    )

    assert (
        payoff.is_paid_off,
        payoff.payoff_percentage,
        payoff.net_value_usd,
        payoff.remaining_usd,
        payoff.estimated_days_to_payoff,
    ) == (
        True,
        150.0,
        500.0,
        0.0,
        0.0,
    )


def test_compute_hardware_payoff_zero_hardware_cost() -> None:
    """Verify payoff calculations when hardware cost is unset (0.0)."""
    payoff = compute_hardware_payoff(
        hardware_cost_usd=0.0,
        local_cost_equivalent_usd=250.0,
        reference_model="gpt-4o",
    )

    assert (
        payoff.hardware_cost_usd,
        payoff.cumulative_savings_usd,
        payoff.payoff_percentage,
        payoff.is_paid_off,
        payoff.remaining_usd,
        payoff.net_value_usd,
    ) == (
        0.0,
        250.0,
        0.0,
        False,
        0.0,
        250.0,
    )
