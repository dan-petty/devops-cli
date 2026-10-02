"""Per-category false-positive rate tracking and cross-run baseline analytics.

Computes verification statistics and false-positive rates segmented by finding
category across individual review sessions and historical review runs. The historical
side reads review history (`history.py`): every finding raised by the sessions it
counts, with the session being compared left out.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from devops_cli.ai.review.history import HistoryFinding, ReviewHistory
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


def resolve_finding_category(finding: Finding | SavedFinding | HistoryFinding) -> str:
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
    findings: Sequence[Finding | SavedFinding | HistoryFinding],
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


def collect_historical_category_metrics(
    reviews_dir: Path | None = None,
    exclude: Path | None = None,
) -> tuple[dict[str, CategoryMetric], ReviewHistory]:
    """Aggregate per-category metrics over every finding raised by the sessions history counts.

    `exclude`, the session being compared, is left out before repeats of a subject collapse.

    Returns:
        (category_metrics, history)
    """
    from devops_cli.ai.review.history import load_review_history
    from devops_cli.ai.review.review_environment import _get_reviews_base_dir

    history = load_review_history(reviews_dir or _get_reviews_base_dir(), exclude=exclude)
    raised = [f for session in history.counted for f in session.raised]
    return compute_category_metrics(raised), history


def format_category_baseline_markdown(
    session_findings: Sequence[Finding | SavedFinding],
    reviews_dir: Path | None = None,
    exclude: Path | None = None,
) -> list[str]:
    """Render Markdown section comparing session category false-positive rates to historical baseline.

    `exclude` is the current session's directory, which the pipeline writes before the report.
    """
    session_metrics = compute_category_metrics(session_findings)
    if not session_metrics:
        return []

    hist_metrics, history = collect_historical_category_metrics(reviews_dir, exclude)

    lines = [
        "## Category Verification & False-Positive Baseline",
        "",
        "| Category | Session Total | Session Invalidated | Session FP Rate | Historical Baseline FP Rate |",
        "| :--- | :--- | :--- | :--- | :--- |",
    ]

    for cat, s_metric in session_metrics.items():
        # History leaves out the session being compared, so a category it has is one that at
        # least one counted earlier session raised.
        h_metric = hist_metrics.get(cat)
        if h_metric is not None:
            h_str = f"{h_metric.false_positive_rate:.1f}% ({h_metric.invalidated}/{h_metric.total})"
        else:
            h_str = "— (baseline established)"

        clean_cat = cat.replace("|", "\\|")
        lines.append(
            f"| `{clean_cat}` | {s_metric.total} | {s_metric.invalidated} | "
            f"{s_metric.false_positive_rate:.1f}% | {h_str} |"
        )

    lines.append("")
    lines.append(
        f"_Baseline: {len(history.counted)} earlier session(s), {history.repeats} repeat "
        "session(s) collapsed, this session excluded._"
    )
    lines.append("")
    return lines
