"""Agent filing quota and ratio formulas (ADR 0001, #1153).

A pure module computing the throttle ratio r(n), release credit, and allowance
for agent-sourced candidates without I/O or network calls.
"""

from __future__ import annotations

import math
from decimal import Decimal
from fractions import Fraction

from devops_cli.roadmap.config import RoadmapConfig

__all__ = ["allowance", "ratio", "ratio_exact", "release_credit"]

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


def release_credit(delivered: int, config: RoadmapConfig | None = None) -> int:
    """Calculate the initial release credit granted at release start.

    credit = min(base + per_delivered * delivered, target)
    """
    cfg = _resolve_config(config)
    base = cfg.release_credit_base
    per_item = cfg.release_credit_per_delivered_item
    target = cfg.release_item_target
    return min(base + per_item * delivered, target)


def allowance(
    n: int,
    delivered: int,
    closures: int,
    config: RoadmapConfig | None = None,
) -> int | float:
    """Calculate the allowed agent openings for the current release cycle.

    When ratio(n) is 0, the allowance has no limit (math.inf).
    Otherwise, returns credit + floor(closures / ratio(n)).
    """
    r_exact = ratio_exact(n, config)
    if r_exact == Fraction(0):
        return math.inf
    credit = release_credit(delivered, config)
    from_closures = math.floor(Fraction(closures) / r_exact)
    return credit + from_closures
