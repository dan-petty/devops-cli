"""Per-category false-positive rate tracking and cross-run baseline analytics.

Computes verification statistics and false-positive rates segmented by finding
category across individual review sessions and historical review runs.
"""

from __future__ import annotations

import json
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from devops_cli.ai.review_schema import Finding, SavedFinding


@dataclass(frozen=True, slots=True)
class CategoryMetric:
    """Aggregated verification metrics and false-positive rate for a category."""

    category: str
    total: int
    invalidated: int
    verified: int
    unverified: int
    mitigated: int
    false_positive_rate: float


def resolve_finding_category(finding: Finding | SavedFinding) -> str:
    """Determine the canonical category for a finding.

    Honors explicit finding category when present; otherwise infers the category
    from title, invalidation reason, and description.
    """
    if finding.category and finding.category.strip():
        return finding.category.strip().lower()

    from devops_cli.ai.review.common_hallucinations import _infer_hallucination_category

    reason_or_desc = finding.invalidation_reason or finding.description or ""
    inferred = _infer_hallucination_category(finding.title, reason_or_desc)
    return inferred.value


def _build_category_metric(category: str, counts: dict[str, int]) -> CategoryMetric:
    """Construct a CategoryMetric instance from raw status counts."""
    total = counts.get("total", 0)
    inval = counts.get("INVALIDATED", 0)
    ver = counts.get("VERIFIED", 0)
    unver = counts.get("UNVERIFIED", 0)
    mit = counts.get("MITIGATED", 0)
    fp_rate = (inval / total * 100.0) if total > 0 else 0.0
    return CategoryMetric(
        category=category,
        total=total,
        invalidated=inval,
        verified=ver,
        unverified=unver,
        mitigated=mit,
        false_positive_rate=round(fp_rate, 2),
    )


def compute_category_metrics(
    findings: Sequence[Finding | SavedFinding],
) -> dict[str, CategoryMetric]:
    """Calculate per-category total, status counts, and false-positive rates."""
    tallies: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for f in findings:
        cat = resolve_finding_category(f)
        status = (f.status or "UNVERIFIED").upper().strip()
        tallies[cat]["total"] += 1
        tallies[cat][status] += 1

    results: dict[str, CategoryMetric] = {}
    for cat, counts in sorted(tallies.items(), key=lambda item: (-item[1]["total"], item[0])):
        results[cat] = _build_category_metric(cat, counts)
    return results


def _load_session_findings(session_dir: Path) -> list[Any]:
    """Safely load and return findings from a saved session directory."""
    findings_file = session_dir / "findings.json"
    if not findings_file.is_file():
        return []
    try:
        from devops_cli.ai.review_schema import ReviewSessionPayload

        content = findings_file.read_text(encoding="utf-8")
        payload = ReviewSessionPayload.model_validate_json(content)
        return list(payload.findings)
    except OSError, json.JSONDecodeError, ValueError:
        return []


def collect_historical_category_metrics(
    reviews_dir: Path | None = None,
) -> tuple[dict[str, CategoryMetric], int, int]:
    """Aggregate per-category findings and false-positive metrics across saved sessions.

    Returns:
        (category_metrics, total_sessions, total_findings)
    """
    from devops_cli.ai.review.review_environment import _get_reviews_base_dir

    r_dir = reviews_dir or _get_reviews_base_dir()
    if not r_dir.exists() or not r_dir.is_dir():
        return {}, 0, 0

    session_dirs = [d for d in r_dir.iterdir() if d.is_dir() and (d / "findings.json").exists()]
    if not session_dirs:
        return {}, 0, 0

    all_historical_findings: list[Any] = []
    for s_dir in session_dirs:
        all_historical_findings.extend(_load_session_findings(s_dir))

    total_sessions = len(session_dirs)
    total_findings = len(all_historical_findings)
    metrics = compute_category_metrics(all_historical_findings)
    return metrics, total_sessions, total_findings


def format_category_baseline_markdown(
    session_findings: Sequence[Finding | SavedFinding],
    reviews_dir: Path | None = None,
) -> list[str]:
    """Render Markdown section comparing session category false-positive rates to historical baseline."""
    session_metrics = compute_category_metrics(session_findings)
    if not session_metrics:
        return []

    hist_metrics, total_sessions, _ = collect_historical_category_metrics(reviews_dir)

    lines = [
        "## Category Verification & False-Positive Baseline",
        "",
        "| Category | Session Total | Session Invalidated | Session FP Rate | Historical Baseline FP Rate |",
        "| :--- | :--- | :--- | :--- | :--- |",
    ]

    for cat, s_metric in session_metrics.items():
        h_metric = hist_metrics.get(cat)
        if h_metric and total_sessions > 1:
            h_str = f"{h_metric.false_positive_rate:.1f}% ({h_metric.invalidated}/{h_metric.total})"
        else:
            h_str = "— (baseline established)"

        clean_cat = cat.replace("|", "\\|")
        lines.append(
            f"| `{clean_cat}` | {s_metric.total} | {s_metric.invalidated} | "
            f"{s_metric.false_positive_rate:.1f}% | {h_str} |"
        )

    lines.append("")
    return lines
