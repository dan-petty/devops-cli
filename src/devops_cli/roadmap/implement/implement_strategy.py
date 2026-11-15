"""The strategy of each attempt of an implement step (#3569).

A repair round sent the same inputs again with the text of the failure, so a second failure of the
same kind repeated the strategy that failed. Each attempt now tries something that an earlier
attempt did not: the first runs as planned, the second adds the repository map of the files that
the failure names, and the third and each later attempt run on the next healthy tier of the
ladder. An attempt that follows a failure which selects `change_tier` runs on another tier, so its
strategy is `tier` too.
"""

from __future__ import annotations

from enum import StrEnum

__all__ = ["AttemptStrategy", "strategy_for"]


class AttemptStrategy(StrEnum):
    """What an attempt of a step tries that the earlier attempts did not."""

    PLANNED = "planned"
    REPO_MAP = "repo_map"
    TIER = "tier"


def strategy_for(number: int, moves_tier: bool = False) -> AttemptStrategy:
    """The strategy of attempt `number`: the planned run first, the repository map on the second,
    and the next tier on the third and each later one. `moves_tier` says that the failure of the
    attempt before selected `change_tier`, so this attempt runs on another tier."""
    if moves_tier or number >= 3:
        return AttemptStrategy.TIER
    if number == 2:
        return AttemptStrategy.REPO_MAP
    return AttemptStrategy.PLANNED
