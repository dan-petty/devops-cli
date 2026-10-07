"""Frozen Finding model for review findings (#871).

A frozen Finding is constructed exclusively by `devops_cli.review.admission.admit()`.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from devops_cli.review.anchors import AdvisoryAnchor, ToolAnchor
from devops_cli.review.state import FindingState


class Finding(BaseModel):
    """An immutable, admitted review finding with verified producer anchor and location."""

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    anchor: ToolAnchor | AdvisoryAnchor
    tool: str
    tool_version: str | None = None
    rule_id: str
    path: str
    line: int | None = None
    end_line: int | None = None
    symbol: str | None = None
    region_sha256: str | None = None
    logical_location: str | None = None
    message: str
    description: str = ""
    fix: str = ""
    severity: str
    severity_derivation: str
    state: FindingState = FindingState.OPEN
    suppression_reason: str | None = None
    suppression_expiry: str | None = None
    suppressed_by_change: bool = False
    confirmed_by: str | None = None
    baseline_state: str = "new"  # "new" or "unchanged" (SARIF 2.1.0)
    introduced: bool = True
    fingerprint_v2: str
    partial_fingerprints: dict[str, str] = Field(default_factory=dict)
    properties: dict[str, Any] = Field(default_factory=dict)

    @property
    def location_display(self) -> str:
        """Render location for user-facing tables and summaries."""
        if not self.path:
            return self.logical_location or ""
        if self.line is not None:
            if self.end_line is not None and self.end_line != self.line:
                return f"{self.path}:{self.line}-{self.end_line}"
            return f"{self.path}:{self.line}"
        return self.path
