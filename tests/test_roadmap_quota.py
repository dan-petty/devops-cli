"""Tests for agent filing quota and throttle ratio calculations (ADR 0001, #1153)."""

from __future__ import annotations

import math

from devops_cli.roadmap.config import RoadmapConfig
from devops_cli.roadmap.quota import allowance, ratio, release_credit


def test_ratio_rises_from_zero_to_overage_curve() -> None:
    """r(150)=0, r(160)=0, r(180)=0.5, r(200)=1, r(250)=2 and r(289)=2.78."""
    assert (
        ratio(150),
        ratio(160),
        ratio(180),
        ratio(200),
        ratio(250),
        ratio(289),
    ) == (0.0, 0.0, 0.5, 1.0, 2.0, 2.78)


def test_release_credit_caps_at_target() -> None:
    """credit for a previous release of 0, 30 and 70 delivered items = 10, 40 and 50."""
    assert (
        release_credit(0),
        release_credit(30),
        release_credit(70),
    ) == (10, 40, 50)


def test_allowance_unlimited_when_ratio_zero_and_floors_openings() -> None:
    """The allowance has no limit while r(n) is 0, allowance(250, 70, 20)=60, allowance(280, 70, 20)=57."""
    assert (
        math.isinf(allowance(150, 70, 20)),
        math.isinf(allowance(160, 70, 20)),
        allowance(250, 70, 20),
        allowance(280, 70, 20),
    ) == (True, True, 60, 57)


def test_allowance_exact_arithmetic_avoids_floating_point_round_down() -> None:
    """A boundary such as 0.5 closures per opening (n=180) never rounds down 1 closure to 1."""
    # At n=180, r=0.5. With 1 closure, 1 / 0.5 = 2.0 exactly.
    # credit for 0 delivered = 10. allowance = 10 + 2 = 12.
    assert allowance(180, 0, 1) == 12


def test_quota_honours_custom_configuration() -> None:
    """Custom configuration overrides limits, thresholds, and credit terms."""
    custom = RoadmapConfig(
        board=1,
        open_issue_limit=100,
        throttle_start_fraction=0.5,
        overage_step_fraction=0.5,
        release_credit_base=5,
        release_credit_per_delivered_item=2,
        release_item_target=30,
    )
    assert (
        ratio(40, custom),
        ratio(75, custom),
        ratio(150, custom),
        release_credit(10, custom),
        allowance(150, 10, 10, custom),
    ) == (0.0, 0.5, 2.0, 25, 30)
