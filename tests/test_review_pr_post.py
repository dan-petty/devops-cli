"""Tests for PR review comment formatting and --post execution (Issue #604 Part 2)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from devops_cli.ai.personas import PERSONAS, Persona, PersonaDefinition
from devops_cli.ai.review.runner import format_pr_review_comment
from devops_cli.ai.review_schema import Finding, ReviewResult
from devops_cli.commands.review import app as review_app

runner = CliRunner()


def test_zero_findings_comment_names_files_personas_and_analyzers() -> None:
    """Verify zero-findings PR comment states exact files, personas, and analyzers that ran."""
    persona_devsec = PERSONAS[Persona.DEVSECOPS]
    res = ReviewResult(
        persona=Persona.DEVSECOPS,
        recommendation="APPROVE",
        findings=[],
        summary="No defects found; consider adding docstrings.",
    )
    reviews: list[tuple[PersonaDefinition, ReviewResult | str]] = [(persona_devsec, res)]
    files = ["src/auth.py", "src/token.py"]
    analyzers = {
        "Bandit": "ran",
        "Gitleaks": "built-in patterns",
        "Semgrep": "not installed",
        "Trivy": "no files",
    }

    comment = format_pr_review_comment(
        reviews=reviews,
        files=files,
        static_analyzers=analyzers,
    )

    expected_fragments = (
        "## 🤖 AI Code Review",
        "Zero findings identified.",
        "- **Files checked:** `src/auth.py`, `src/token.py`",
        f"- **Personas:** {persona_devsec.title}",
        "- **Analyzers:** Bandit, Gitleaks",
        "## Model Notes (Not Verified)",
        "No defects found; consider adding docstrings.",
    )
    assert (
        all(frag in comment for frag in expected_fragments),
        "Positive observations" in comment,
    ) == (True, False)


def test_zero_findings_comment_with_no_analyzers_and_no_summary() -> None:
    """Verify zero-findings comment when no analyzers ran and no summary was emitted."""
    persona_qa = PERSONAS[Persona.QA]
    res = ReviewResult(
        persona=Persona.QA,
        recommendation="APPROVE",
        findings=[],
        summary="",
    )
    reviews: list[tuple[PersonaDefinition, ReviewResult | str]] = [(persona_qa, res)]

    comment = format_pr_review_comment(
        reviews=reviews,
        files=[],
        static_analyzers={},
    )

    expected_lines = [
        "## 🤖 AI Code Review",
        "",
        "Zero findings identified.",
        "",
        "- **Files checked:** None",
        f"- **Personas:** {persona_qa.title}",
        "- **Analyzers:** None",
    ]
    assert (
        comment.strip().splitlines() == expected_lines,
        "Model Notes (Not Verified)" in comment,
    ) == (True, False)


def test_zero_findings_comment_multiple_personas_model_notes() -> None:
    """Verify model notes from multiple personas are formatted under persona subheadings."""
    p_devsec = PERSONAS[Persona.DEVSECOPS]
    p_arch = PERSONAS[Persona.ARCHITECT]
    r1 = ReviewResult(
        persona=Persona.DEVSECOPS,
        recommendation="APPROVE",
        findings=[],
        summary="Security posture is clean.",
    )
    r2 = ReviewResult(
        persona=Persona.ARCHITECT,
        recommendation="APPROVE",
        findings=[],
        summary="Architecture exhibits low coupling.",
    )
    reviews: list[tuple[PersonaDefinition, ReviewResult | str]] = [
        (p_devsec, r1),
        (p_arch, r2),
    ]

    comment = format_pr_review_comment(
        reviews=reviews,
        files=["main.py"],
        static_analyzers={"Bandit": "ran"},
    )

    expected_fragments = (
        "## 🤖 AI Code Review",
        "Zero findings identified.",
        "- **Files checked:** `main.py`",
        f"- **Personas:** {p_devsec.title}, {p_arch.title}",
        "- **Analyzers:** Bandit",
        "## Model Notes (Not Verified)",
        f"### {p_devsec.title}\n\nSecurity posture is clean.",
        f"### {p_arch.title}\n\nArchitecture exhibits low coupling.",
    )
    assert all(frag in comment for frag in expected_fragments) is True


def test_comment_with_findings_renders_findings_and_model_notes() -> None:
    """Verify PR comment with findings renders finding details and unverified notes."""
    p_devsec = PERSONAS[Persona.DEVSECOPS]
    finding = Finding(
        severity="HIGH",
        title="Unvalidated URL Redirect",
        description="Redirect target not validated against allowlist",
        location="src/auth.py:42-50",
        fix="Use validate_redirect_url(target)",
        verified=True,
    )
    res = ReviewResult(
        persona=Persona.DEVSECOPS,
        recommendation="REQUEST CHANGES",
        findings=[finding],
        summary="Review completed with 1 high finding.",
    )
    reviews: list[tuple[PersonaDefinition, ReviewResult | str]] = [(p_devsec, res)]

    comment = format_pr_review_comment(reviews=reviews, files=["src/auth.py"])

    expected_fragments = (
        "## 🤖 AI Code Review",
        f"## Review by {p_devsec.title}",
        "## Findings",
        "### [HIGH] Unvalidated URL Redirect",
        "**Location:** `src/auth.py:42-50`",
        "Redirect target not validated against allowlist",
        "**Fix:** Use validate_redirect_url(target)",
        "## Model Notes (Not Verified)",
        "Review completed with 1 high finding.",
    )
    assert (
        all(frag in comment for frag in expected_fragments),
        "Zero findings identified" in comment,
        "Positive Observations" in comment,
    ) == (True, False, False)


def test_devops_review_pr_post_publishes_comment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify devops review pr --post creates an issue comment on the PR."""
    monkeypatch.setattr(
        "devops_cli.core.validation.validate_service_url", lambda *args, **kwargs: None
    )
    mock_pull = MagicMock()
    mock_pull.title = "Test PR"
    mock_pull.get_files.return_value = [MagicMock(filename="src/app.py", status="modified")]

    p_qa = PERSONAS[Persona.QA]
    res_clean = ReviewResult(
        persona=Persona.QA,
        recommendation="APPROVE",
        findings=[],
        summary="Clean implementation.",
    )
    mock_reviews = [(p_qa, res_clean)]

    with (
        patch("devops_cli.commands.review._init_logfire_if_enabled"),
        patch("devops_cli.config.settings.get_github_token", return_value="ghp_test"),
        patch(
            "devops_cli.commands.review._prepare_pr_content",
            return_value=(
                ["diff --git a/src/app.py b/src/app.py\n+pass\n"],
                "PR 42: Test PR",
                "AGENTS.md",
                mock_pull,
                "org/repo",
            ),
        ),
        patch("devops_cli.commands.review._execute_review_workflow", return_value=mock_reviews),
        patch("devops_cli.commands.review.load_settings"),
    ):
        result = runner.invoke(review_app, ["pr", "42", "--persona", "qa", "--post"])

    posted_body = mock_pull.create_issue_comment.call_args[0][0]
    assert (
        result.exit_code,
        mock_pull.create_issue_comment.call_count,
        "Zero findings identified." in posted_body,
        "- **Files checked:** `src/app.py`" in posted_body,
        f"- **Personas:** {p_qa.title}" in posted_body,
        "## Model Notes (Not Verified)" in posted_body,
    ) == (0, 1, True, True, True, True)


def test_devops_review_pr_post_dry_run_skips_comment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify devops review pr --post --dry-run does not invoke GitHub API."""
    monkeypatch.setattr(
        "devops_cli.core.validation.validate_service_url", lambda *args, **kwargs: None
    )
    mock_pull = MagicMock()
    p_qa = PERSONAS[Persona.QA]
    res_clean = ReviewResult(
        persona=Persona.QA,
        recommendation="APPROVE",
        findings=[],
        summary="",
    )
    mock_reviews = [(p_qa, res_clean)]

    with (
        patch("devops_cli.commands.review._init_logfire_if_enabled"),
        patch("devops_cli.config.settings.get_github_token", return_value="ghp_test"),
        patch(
            "devops_cli.commands.review._prepare_pr_content",
            return_value=(["diff content"], "PR 42", "AGENTS.md", mock_pull, "org/repo"),
        ),
        patch("devops_cli.commands.review._execute_review_workflow", return_value=mock_reviews),
        patch("devops_cli.commands.review.load_settings"),
    ):
        result = runner.invoke(review_app, ["pr", "42", "--persona", "qa", "--post", "--dry-run"])

    assert (
        result.exit_code,
        mock_pull.create_issue_comment.call_count,
        "Would post PR comment on #42" in result.output,
    ) == (0, 0, True)
