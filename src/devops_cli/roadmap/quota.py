"""Agent filing quota and ratio formulas (ADR 0001, #1153).

A pure module that computes the throttle ratio r(n), the window credit and the allowance for
agent-sourced candidates, with no I/O or network calls. The quota counts over a rolling window of
`quota_window_days` days that ends now, so no release or milestone starts or ends it.
"""

from __future__ import annotations

import math
from decimal import Decimal
from fractions import Fraction

from devops_cli.roadmap.config import RoadmapConfig

__all__ = ["allowance", "ratio", "ratio_exact", "window_credit"]

_DEFAULT_CONFIG = RoadmapConfig(board=1)


def _resolve_config(config: RoadmapConfig | None) -> RoadmapConfig:
    """Return caller's config or default roadmap configuration."""
    return config if config is not None else _DEFAULT_CONFIG


def ratio_exact(n: int, config: RoadmapConfig | None = None) -> Fraction:
    """Calculate the exact throttle ratio r(n) as a stdlib Fraction.

    - n < s*L: 0
    - s*L <= n < L: (n - s*L) / ((1 - s)*L)
    - n >= L: 1 + (n - L) / (o*L)
    """
    cfg = _resolve_config(config)
    open_issue_limit = Fraction(cfg.open_issue_limit)
    start_fraction = Fraction(Decimal(str(cfg.throttle_start_fraction)))
    overage_fraction = Fraction(Decimal(str(cfg.overage_step_fraction)))
    open_count = Fraction(n)
    throttle_start = start_fraction * open_issue_limit

    if open_count < throttle_start:
        return Fraction(0)
    if open_count < open_issue_limit:
        return (open_count - throttle_start) / ((Fraction(1) - start_fraction) * open_issue_limit)
    return Fraction(1) + (open_count - open_issue_limit) / (overage_fraction * open_issue_limit)


def ratio(n: int, config: RoadmapConfig | None = None) -> float:
    """Calculate the throttle ratio r(n) as a floating-point number."""
    return float(ratio_exact(n, config))


def window_credit(delivered: int, config: RoadmapConfig | None = None) -> int:
    """Calculate the credit the window gives for `delivered`, the items closed as completed in it.

    credit = min(base + per_delivered * delivered, cap)
    """
    cfg = _resolve_config(config)
    earned = cfg.quota_credit_base + cfg.quota_credit_per_delivered_item * delivered
    return min(earned, cfg.quota_credit_cap)


def allowance(
    n: int,
    delivered: int,
    closures: int,
    config: RoadmapConfig | None = None,
) -> int | float:
    """Calculate the agent openings the window allows.

    When ratio(n) is 0, the allowance has no limit (math.inf).
    Otherwise, returns credit + floor(closures / ratio(n)).
    """
    r_exact = ratio_exact(n, config)
    if r_exact == Fraction(0):
        return math.inf
    credit = window_credit(delivered, config)
    from_closures = math.floor(Fraction(closures) / r_exact)
    return credit + from_closures
