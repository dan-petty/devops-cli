"""Unit tests covering the devops review CLI subcommands and workflows."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from devops_cli.ai.review_schema import ReviewSessionPayload
from devops_cli.commands.review import app as review_app

runner = CliRunner()


def test_review_explain() -> None:
    """Verify review subcommands with --explain flag."""
    res = runner.invoke(review_app, ["path", "--explain"])
    assert res.exit_code == 0

    res_pr = runner.invoke(review_app, ["pr", "123", "--explain"])
    assert res_pr.exit_code == 0

    res_br = runner.invoke(review_app, ["branch", "feat/test", "--explain"])
    assert res_br.exit_code == 0


def test_review_path_workflow(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify devops review path workflow execution."""
    monkeypatch.setattr(
        "devops_cli.core.validation.validate_service_url", lambda *args, **kwargs: None
    )
    py_file = tmp_path / "app.py"
    py_file.write_text("def run():\n    pass\n", encoding="utf-8")

    mock_wf = [(MagicMock(title="Architect", name="architect"), "Review comments")]
    with (
        patch(
            "devops_cli.commands.review._prepare_path_content",
            return_value=(["code page"], "Path Review", "AGENTS.md"),
        ),
        patch("devops_cli.commands.review._execute_review_workflow", return_value=mock_wf),
        patch("devops_cli.commands.review.load_settings"),
    ):
        res = runner.invoke(review_app, ["path", str(py_file), "--persona", "architect"])
        assert res.exit_code == 0


def test_review_branch_workflow(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify devops review branch workflow execution."""
    monkeypatch.setattr(
        "devops_cli.core.validation.validate_service_url", lambda *args, **kwargs: None
    )

    mock_wf = [(MagicMock(title="DevSecOps", name="devsecops"), "Security comments")]
    with (
        patch(
            "devops_cli.commands.review._prepare_branch_content",
            return_value=(["diff content"], "Branch Review", "AGENTS.md"),
        ),
        patch("devops_cli.commands.review._execute_review_workflow", return_value=mock_wf),
        patch("devops_cli.commands.review.load_settings"),
    ):
        res = runner.invoke(review_app, ["branch", "feat/my-feature", "--persona", "devsecops"])
        assert res.exit_code == 0


def test_review_pr_workflow(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify devops review pr workflow execution."""
    monkeypatch.setattr(
        "devops_cli.core.validation.validate_service_url", lambda *args, **kwargs: None
    )
    mock_pull = MagicMock()
    mock_wf = [(MagicMock(title="QA", name="qa"), "QA feedback")]

    with (
        patch("devops_cli.config.settings.get_github_token", return_value="ghp_test"),
        patch(
            "devops_cli.commands.review._prepare_pr_content",
            return_value=(["pr diff"], "PR 10", "AGENTS.md", mock_pull, "org/repo"),
        ),
        patch("devops_cli.commands.review._execute_review_workflow", return_value=mock_wf),
        patch("devops_cli.commands.review.load_settings"),
    ):
        res = runner.invoke(review_app, ["pr", "10", "--persona", "qa"])
        assert res.exit_code == 0


def test_review_verify_and_apply_patch(tmp_path: Path) -> None:
    """Verify apply-patch subcommand execution."""
    with patch("devops_cli.commands.review.stage_finding_patch", return_value=True):
        res_patch = runner.invoke(review_app, ["apply-patch", "session-123", "--index", "1"])
        assert res_patch.exit_code == 0


def test_review_findings_stats_export_feedback(tmp_path: Path) -> None:
    """Verify review findings, stats, and export-feedback subcommands."""
    session_dir = tmp_path / "session_1"
    session_dir.mkdir()
    findings_file = session_dir / "findings.json"
    session_payload = ReviewSessionPayload(
        target_type="path",
        target_ref=str(tmp_path),
        findings=[],
        generated_at=datetime.now(UTC).isoformat(),
    )
    findings_file.write_text(session_payload.model_dump_json(), encoding="utf-8")

    with (
        patch("devops_cli.commands.review._find_session_dir", return_value=session_dir),
        patch(
            "devops_cli.commands.review.export_invalidated_feedback",
            return_value=(1, tmp_path / "fb.jsonl"),
        ),
    ):
        res_find = runner.invoke(review_app, ["findings"])
        assert res_find.exit_code == 0

        res_stats = runner.invoke(review_app, ["stats"])
        assert res_stats.exit_code == 0

        res_fb = runner.invoke(
            review_app,
            [
                "export-feedback",
                "--reviews-dir",
                str(tmp_path),
                "--output",
                str(tmp_path / "fb.jsonl"),
            ],
        )
        assert res_fb.exit_code == 0
