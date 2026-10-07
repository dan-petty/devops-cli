"""Anchor protocols and implementations for review findings (#871).

Every finding records its producer (scanner rule or advisory) via an anchor.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@runtime_checkable
class Anchor(Protocol):
    """Protocol representing a verified provenance anchor for a review finding."""

    @property
    def kind(self) -> str:
        """Type of producer anchor (e.g. 'tool' or 'advisory')."""
        ...

    @property
    def location(self) -> str:
        """Canonical producer location string."""
        ...

    def recheck(self) -> bool:
        """Validate that the anchor parameters remain structurally valid."""
        ...


@dataclass(frozen=True)
class ToolAnchor:
    """Provenance anchor for an automated tool or scanner run."""

    run_id: str
    result_index: int
    rule_id: str

    @property
    def kind(self) -> str:
        return "tool"

    @property
    def location(self) -> str:
        return f"{self.run_id}#{self.result_index}:{self.rule_id}"

    def recheck(self) -> bool:
        return bool(self.run_id.strip() and self.rule_id.strip() and self.result_index >= 0)


@dataclass(frozen=True)
class AdvisoryAnchor:
    """Provenance anchor for a package vulnerability or advisory catalog entry."""

    db: str
    snapshot: str
    advisory_id: str
    purl: str
    locked_version: str

    @property
    def kind(self) -> str:
        return "advisory"

    @property
    def location(self) -> str:
        return f"{self.db}/{self.advisory_id}@{self.purl}#{self.locked_version}"

    def recheck(self) -> bool:
        return bool(
            self.db.strip()
            and self.advisory_id.strip()
            and self.purl.strip()
            and self.locked_version.strip()
        )
