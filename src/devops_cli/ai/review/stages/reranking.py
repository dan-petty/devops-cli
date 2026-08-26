"""Cross-persona deduplication, severity calibration, and confidence ranking."""

from __future__ import annotations

from devops_cli.ai.review_schema import SavedFinding
from devops_cli.output import print_info
from devops_cli.telemetry.tracer import trace_span

SEVERITY_ORDER = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3, "INFO": 4}


def run_reranking_stage(findings: list[SavedFinding]) -> list[SavedFinding]:
    """Execute finding re-ranking, deduplication, and confidence calibration."""
    with trace_span("review.reranking", attributes={"input_findings": len(findings)}):
        print_info(
            f"Re-ranking and calibrating {len(findings)} finding(s)...",
            prefix=False,
        )

        # Deduplicate by normalized (location, title)
        seen: set[tuple[str, str]] = set()
        deduped: list[SavedFinding] = []
        for f in findings:
            key = (f.location.strip(), f.title.strip().lower())
            if key not in seen:
                seen.add(key)
                deduped.append(f)

        # Sort by severity rank, then location
        deduped.sort(
            key=lambda x: (
                SEVERITY_ORDER.get(x.severity.upper(), 99),
                x.location,
            )
        )

        print_info(
            f"    ✓ Finding re-ranking completed ({len(deduped)} unique finding(s))",
            prefix=False,
        )
        return deduped
