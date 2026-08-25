"""Comprehensive unit tests covering review CLI workflows."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from devops_cli.commands.review import app as review_app

runner = CliRunner()


def test_review_explain() -> None:
    res = runner.invoke(review_app, ["path", "--explain"])
    assert res.exit_code == 0

    res_pr = runner.invoke(review_app, ["pr", "123", "--explain"])
    assert res_pr.exit_code == 0

    res_br = runner.invoke(review_app, ["branch", "feat/test", "--explain"])
    assert res_br.exit_code == 0


def test_review_path_workflow(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
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
    with patch("devops_cli.commands.review.stage_finding_patch", return_value=True):
        res_patch = runner.invoke(review_app, ["apply-patch", "session-123", "--index", "1"])
        assert res_patch.exit_code == 0
