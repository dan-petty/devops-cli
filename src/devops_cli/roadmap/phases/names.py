"""The names of the phases of a phased roadmap step (#6601). A command imports this module at its
start, so it imports nothing more."""

from __future__ import annotations

from enum import StrEnum


class RunPhase(StrEnum):
    """The phase that `--phase` runs: one of the three, or `all`, the three in one process."""

    PREPARE = "prepare"
    AGENT = "agent"
    PUBLISH = "publish"
    ALL = "all"


__all__ = ["RunPhase"]
