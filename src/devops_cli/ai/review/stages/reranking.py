"""Finding Deduplication, Severity Re-Ranking & Group Consolidation."""

from __future__ import annotations

import logging

from devops_cli.ai.review_schema import (
    FileReviewPayload,
    SavedFinding,
    _parse_location,
    consolidate_duplicate_findings,
)
from devops_cli.telemetry import trace_span

logger = logging.getLogger(__name__)


@trace_span("review.stage.reranking")
def run_reranking(payload: FileReviewPayload) -> list[SavedFinding]:
    """Consolidate duplicate findings, re-rank by severity, and sort by location."""
    if not payload.findings:
        return []

    # Consolidate duplicates across personas
    consolidated = consolidate_duplicate_findings(payload.findings)

    # Sort deterministically by line number extracted from location
    def _line_sort_key(f: SavedFinding) -> int:
        _, s_line, _ = _parse_location(f.location)
        return s_line if s_line is not None else 0

    consolidated.sort(key=_line_sort_key)
    return consolidated
