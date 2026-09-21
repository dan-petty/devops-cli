"""End-to-end aggregation of scanner output into a single reportable result.

Running every scanner and printing each one's table separately leaves the reader to notice
that three tools flagged the same line and that two of those results are the same finding
reported twice. This module does that work: normalize, suppress, deduplicate, correlate,
rank, and count.

It is deliberately free of Typer and Rich so the whole pipeline can be exercised without a
console, which is what the existing per-scanner commands could not do.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from devops_cli.ai.review_schema import Finding
from devops_cli.config.constants import CONST_SEVERITY_ORDER
from devops_cli.security.normalization import (
    FindingCluster,
    NormalizedFinding,
    correlate,
    deduplicate,
    filter_by_severity,
    normalize_results,
    rank,
    severity_rank,
    summarize,
)
from devops_cli.security.suppression import SuppressionPolicy, SuppressionRule, empty_policy

logger = logging.getLogger(__name__)


@dataclass
class ScanReport:
    """The result of aggregating every scanner's output over one target."""

    target: str
    findings: list[NormalizedFinding] = field(default_factory=list)
    clusters: list[FindingCluster] = field(default_factory=list)
    suppressed: list[tuple[NormalizedFinding, SuppressionRule]] = field(default_factory=list)
    expired_suppressions: list[SuppressionRule] = field(default_factory=list)
    tools_run: tuple[str, ...] = ()
    duplicates_removed: int = 0

    @property
    def counts(self) -> dict[str, int]:
        """Findings by severity, including severities with none."""
        return summarize(self.findings)

    @property
    def total(self) -> int:
        """Number of findings that survived suppression and deduplication."""
        return len(self.findings)

    def highest_severity(self) -> str | None:
        """The most severe surviving finding's severity, or ``None`` if there are none."""
        if not self.findings:
            return None
        return min(self.findings, key=lambda finding: finding.rank).severity

    def exceeds(self, threshold: str) -> bool:
        """Report whether any surviving finding is at or above a severity threshold."""
        highest = self.highest_severity()
        if highest is None:
            return False
        return severity_rank(highest) <= severity_rank(threshold)

    def as_dict(self) -> dict[str, Any]:
        """Render the report as a JSON-serializable mapping."""
        from devops_cli.security.normalization import as_dict as finding_as_dict

        return {
            "target": self.target,
            "tools": list(self.tools_run),
            "counts": self.counts,
            "total": self.total,
            "duplicates_removed": self.duplicates_removed,
            "suppressed": len(self.suppressed),
            "expired_suppressions": [rule.rule for rule in self.expired_suppressions],
            "findings": [finding_as_dict(finding) for finding in self.findings],
            "clusters": [
                {
                    "path": cluster.representative.path,
                    "line": cluster.representative.line,
                    "severity": cluster.severity,
                    "tools": list(cluster.tools),
                    "confirmations": cluster.confirmations,
                    "message": cluster.representative.message,
                }
                for cluster in self.clusters
            ],
        }


def build_report(
    results: dict[str, list[Finding]],
    target: Path,
    *,
    policy: SuppressionPolicy | None = None,
    min_severity: str | None = None,
    base: Path | None = None,
) -> ScanReport:
    """Aggregate raw scanner results into a single report.

    Suppression is applied *before* deduplication so the suppressed list names every
    occurrence the policy hid, not just the first. Reporting one suppression where a rule
    silenced four results would understate what the policy is doing.
    """
    active_policy = policy or empty_policy()
    normalized = normalize_results(results, base if base is not None else target)

    kept, suppressed = active_policy.apply(normalized)

    deduplicated = deduplicate(kept)
    duplicates_removed = len(kept) - len(deduplicated)

    if min_severity:
        deduplicated = filter_by_severity(deduplicated, min_severity)

    return ScanReport(
        target=str(target),
        findings=rank(deduplicated),
        clusters=correlate(deduplicated),
        suppressed=suppressed,
        expired_suppressions=active_policy.expired_rules(),
        tools_run=tuple(sorted(results)),
        duplicates_removed=duplicates_removed,
    )


def report_from_findings(
    findings: list[NormalizedFinding],
    target: str,
    *,
    policy: SuppressionPolicy | None = None,
    min_severity: str | None = None,
) -> ScanReport:
    """Build a report from already-normalized findings, such as an ingested SARIF file."""
    active_policy = policy or empty_policy()
    kept, suppressed = active_policy.apply(findings)
    deduplicated = deduplicate(kept)
    duplicates_removed = len(kept) - len(deduplicated)

    if min_severity:
        deduplicated = filter_by_severity(deduplicated, min_severity)

    return ScanReport(
        target=target,
        findings=rank(deduplicated),
        clusters=correlate(deduplicated),
        suppressed=suppressed,
        expired_suppressions=active_policy.expired_rules(),
        tools_run=tuple(sorted({finding.tool for finding in findings})),
        duplicates_removed=duplicates_removed,
    )


def severity_choices() -> tuple[str, ...]:
    """The accepted severity vocabulary, most severe first."""
    return CONST_SEVERITY_ORDER


__all__ = [
    "ScanReport",
    "build_report",
    "report_from_findings",
    "severity_choices",
]
