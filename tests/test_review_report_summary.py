"""Tests for AI code review report Executive Summary generation with key good and bad patterns."""

from __future__ import annotations

from pathlib import Path

from devops_cli.ai.review.pipeline import ReviewPipelineOrchestrator
from devops_cli.ai.review.stages.reporting import run_reporting_stage
from devops_cli.ai.review_schema import SavedFinding


def _make_dummy_pipeline(tmp_path: Path) -> ReviewPipelineOrchestrator:
    pipeline = ReviewPipelineOrchestrator(
        target_dir=tmp_path,
        session_id="20260906-test-exec-summary",
    )
    return pipeline


def test_consolidated_markdown_report_clean_executive_summary(tmp_path: Path) -> None:
    pipeline = _make_dummy_pipeline(tmp_path)
    report_md = pipeline._build_consolidated_markdown_report(
        session_id="test-clean-session",
        generated_at="2026-09-06T12:00:00Z",
        reportable_findings=[],
        all_deps=[],
        all_nets=[],
    )

    assert "# Code Review Report (Session `test-clean-session`)" in report_md
    assert "## Executive Summary" in report_md
    assert "### Key Good Patterns Observed" in report_md
    assert (
        "### Key Bad Patterns Observed" in report_md
        or "### Key Anti-Patterns Observed" in report_md
    )
    assert "No critical anti-patterns or recurring defect patterns identified" in report_md
    assert "✅ **No critical issues found during review.**" in report_md


def test_consolidated_markdown_report_with_findings_patterns(tmp_path: Path) -> None:
    pipeline = _make_dummy_pipeline(tmp_path)

    findings = [
        SavedFinding(
            id=1,
            severity="CRITICAL",
            location="src/devops_cli/core/repo.py:168-174",
            title="list_repo_files can expose files outside repository via symlink traversal",
            description="Symlink traversal allows path traversal outside repo root.",
            status="VERIFIED",
            verified=True,
            reportable=True,
            persona_title="Principal DevSecOps Engineer",
        ),
        SavedFinding(
            id=2,
            severity="HIGH",
            location="k8s/argocd/apps/infra-apps.yaml:13",
            title="Insecure git:// protocol used for ArgoCD repoURL",
            description="Cleartext git protocol permits network tampering.",
            status="VERIFIED",
            verified=True,
            reportable=True,
            persona_title="Principal DevSecOps Engineer",
        ),
        SavedFinding(
            id=3,
            severity="HIGH",
            location="src/devops_cli/ai/agents/tools.py:45-46",
            title="Missing argument validation for tools with no defined parameters",
            description="Unbounded parameters skip path traversal checking.",
            status="VERIFIED",
            verified=True,
            reportable=True,
            persona_title="Principal DevSecOps Engineer",
        ),
    ]

    report_md = pipeline._build_consolidated_markdown_report(
        session_id="test-findings-session",
        generated_at="2026-09-06T12:00:00Z",
        reportable_findings=findings,
        all_deps=[],
        all_nets=[],
    )

    assert "## Executive Summary" in report_md
    assert "### Key Good Patterns Observed" in report_md
    assert (
        "### Key Bad Patterns Observed" in report_md
        or "### Key Anti-Patterns Observed" in report_md
    )

    # Check that bad patterns synthesized key risk categories
    lower_report = report_md.lower()
    assert "path traversal" in lower_report or "filesystem" in lower_report
    assert "protocol" in lower_report or "network" in lower_report or "insecure" in lower_report
    assert "validation" in lower_report or "parameter" in lower_report or "input" in lower_report


def test_reporting_stage_generates_executive_summary(tmp_path: Path) -> None:
    session_dir = tmp_path / "test_session_dir"
    report_path = run_reporting_stage(
        session_id="20260906-reporting-stage",
        session_dir=session_dir,
        reportable_findings=[],
        all_deps=[],
        all_nets=[],
        n_files=5,
    )

    content = report_path.read_text(encoding="utf-8")
    assert "## Executive Summary" in content
    assert "### Key Good Patterns Observed" in content
    assert "### Key Bad Patterns Observed" in content


def test_consolidated_markdown_report_with_errored_files(tmp_path: Path) -> None:
    """Ensure that reviews encountering provider or analysis errors do not report a false-clean executive summary."""
    pipeline = _make_dummy_pipeline(tmp_path)
    pipeline.errored_files["src/devops_cli/commands/ai.py"] = "Review: Cannot connect to Ollama"

    report_md = pipeline._build_consolidated_markdown_report(
        session_id="test-errored-session",
        generated_at="2026-09-11T02:00:00Z",
        reportable_findings=[],
        all_deps=[],
        all_nets=[],
    )

    assert "## Executive Summary" in report_md
    assert "The automated review encountered errors on **1 file(s)**" in report_md
    assert "The codebase demonstrates exceptional engineering quality" not in report_md
    assert "## Skipped / Errored Files" in report_md
    assert "`src/devops_cli/commands/ai.py`" in report_md
    assert "Cannot connect to Ollama" in report_md


def test_format_error_detail_sanitizes_and_bounds() -> None:
    """Verify _format_error_detail masks secrets and bounds error strings to <= 256 chars."""
    from devops_cli.ai.review.pipeline import _format_error_detail

    # 1. Credential masking
    secret_exc = ValueError(
        "Failed with token ghp_1234567890abcdef1234 and pass password='secret_pwd_1234!'"
    )
    cleaned = _format_error_detail("Review", secret_exc)
    assert "ghp_1234567890abcdef1234" not in cleaned
    assert "<masked-github-token>" in cleaned
    assert "secret_pwd_1234!" not in cleaned

    # 2. Length bounding to <= 256 chars
    huge_exc = RuntimeError("Server returned huge body: " + "A" * 500)
    bounded = _format_error_detail("Initialization", huge_exc, max_len=256)
    assert len(bounded) <= 256
    assert bounded.endswith("...")
