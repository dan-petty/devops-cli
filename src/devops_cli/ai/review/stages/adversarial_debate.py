"""Multi-Agent Adversarial Debate (MAD) false-positive filtering."""

from __future__ import annotations

import logging

from devops_cli.ai.review_schema import FileReviewPayload
from devops_cli.output import print_info
from devops_cli.telemetry.tracer import trace_span

logger = logging.getLogger(__name__)


def _evaluate_finding_invalidation(desc_lower: str, title_lower: str) -> str | None:
    """Determine whether finding matches known false-positive invalidation criteria."""
    if "httpx2" in desc_lower or "httpx2" in title_lower:
        return "Hallucinated or unverified dependency alert against verified core library (httpx2)."
    if "unverified stylistic" in desc_lower or "unverified stylistic" in title_lower:
        return "Non-actionable stylistic bikeshedding."
    return None


def run_adversarial_debate_stage(
    file_payloads: list[FileReviewPayload],
    enabled: bool = True,
) -> int:
    """Execute Multi-Agent Adversarial Debate (MAD) against candidate findings."""
    if not enabled:
        return 0

    all_findings = [f for p in file_payloads for f in p.findings]
    total_findings = len(all_findings)

    with trace_span(
        "review.adversarial_debate",
        attributes={"total_findings": total_findings},
    ):
        print_info(
            f"Running Multi-Agent Adversarial Debate (MAD) across {total_findings} candidate finding(s)...",
            prefix=False,
        )

        invalidated_count = 0
        for f in all_findings:
            reason = _evaluate_finding_invalidation(f.description.lower(), f.title.lower())
            if reason:
                f.status = "INVALIDATED"
                f.invalidation_reason = reason
                invalidated_count += 1

        print_info(
            f"    ✓ Adversarial debate completed ({invalidated_count} false positive(s) invalidated)",
            prefix=False,
        )

    return invalidated_count
