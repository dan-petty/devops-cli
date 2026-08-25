"""Unit tests for modular review pipeline stages."""

from __future__ import annotations

from devops_cli.ai.review.stages import (
    run_reporting,
    run_reranking,
)
from devops_cli.ai.review_schema import FileReviewPayload, SavedFinding


def test_stage_reranking_deduplication() -> None:
    f1 = SavedFinding(
        title="Unvalidated URL input",
        description="SSRF risk",
        severity="high",
        location="src/main.py:45",
        persona="devsecops",
    )
    f2 = SavedFinding(
        title="Unvalidated URL input",
        description="Duplicate SSRF risk",
        severity="high",
        location="src/main.py:45",
        persona="auditor",
    )
    f3 = SavedFinding(
        title="Hardcoded port number",
        description="Config risk",
        severity="low",
        location="src/main.py:10",
        persona="architect",
    )

    payload = FileReviewPayload(
        file_path="src/main.py",
        findings=[f1, f2, f3],
    )

    reranked = run_reranking(payload)
    # Deduplication should reduce 3 findings to 2
    assert len(reranked) == 2
    # Deterministic line sorting: line 10 before line 45
    assert ":10" in reranked[0].location
    assert ":45" in reranked[1].location


def test_stage_reporting() -> None:
    finding = SavedFinding(
        title="SQL injection vulnerability",
        description="Raw query concatenation",
        severity="critical",
        location="db.py:22",
        fix="Use parameterized queries",
        persona="devsecops",
    )

    payload = FileReviewPayload(
        file_path="db.py",
        findings=[finding],
    )

    result, report_md = run_reporting([payload], session_id="test-session-123")
    assert len(result.findings) == 1
    assert result.findings[0].title == "SQL injection vulnerability"

    assert "# AI Code Review Report — Session `test-session-123`" in report_md
    assert "[CRITICAL] SQL injection vulnerability" in report_md
    assert "- **Location**: `db.py:22`" in report_md
    assert "- **Suggested Fix**: Use parameterized queries" in report_md
