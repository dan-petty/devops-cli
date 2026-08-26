"""Unit tests for modular review pipeline stages."""

from __future__ import annotations

from pathlib import Path

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


def test_stage_pre_analysis(tmp_path: Path) -> None:
    """run_pre_analysis scans target directory and returns metadata dictionary."""
    from devops_cli.ai.review.stages.pre_analysis import run_pre_analysis

    file_a = tmp_path / "a.py"
    file_a.write_text("def a(): pass\n", encoding="utf-8")

    res = run_pre_analysis(tmp_path)
    assert isinstance(res, dict)


def test_stage_static_scan(tmp_path: Path) -> None:
    """run_static_scan aggregates findings from bandit, semgrep, gitleaks, trivy."""
    from unittest.mock import patch

    from devops_cli.ai.review.stages.static_scan import run_static_scan
    from devops_cli.ai.review_schema import Finding

    mock_f = Finding(
        title="Hardcoded Secret",
        description="Secret found",
        severity="high",
        location="a.py:1",
    )

    with (
        patch("devops_cli.ai.review.stages.static_scan.run_gitleaks_scan", return_value=[mock_f]),
        patch("devops_cli.ai.review.stages.static_scan.run_semgrep_scan", return_value=[mock_f]),
        patch("devops_cli.ai.review.stages.static_scan.run_bandit_scan", return_value=[mock_f]),
        patch("devops_cli.ai.review.stages.static_scan.run_trivy_scan", return_value=[mock_f]),
    ):
        findings = run_static_scan(tmp_path, enable_trivy=True)
        assert len(findings) == 4


def test_stage_persona_review() -> None:
    """run_persona_review executes review for active personas."""
    from unittest.mock import MagicMock

    from devops_cli.ai.review.stages.persona_review import run_persona_review

    payload = FileReviewPayload(file_path="src/main.py", findings=[])
    mock_client = MagicMock()

    findings = run_persona_review(payload, "def main(): pass", mock_client, personas=["devsecops"])
    assert isinstance(findings, list)


def test_stage_verification(tmp_path: Path) -> None:
    """run_verification runs AST check and converts findings to SavedFinding."""
    from devops_cli.ai.review.stages.verification import run_verification

    f = SavedFinding(
        title="Unvalidated input",
        description="SSRF risk",
        severity="medium",
        location="main.py:1",
        persona="devsecops",
    )
    payload = FileReviewPayload(file_path="main.py", findings=[f])

    verified = run_verification(payload, repo_root=tmp_path)
    assert len(verified) == 1
    assert isinstance(verified[0], SavedFinding)
