"""Unit tests covering devops ci command options including --dry-run and --fix."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from devops_cli.commands.ci import CheckResult, app
from devops_cli.dry_run import is_dry_run, set_dry_run

runner = CliRunner()


@pytest.fixture(autouse=True)
def reset_dry_run_state() -> None:
    """Ensure dry-run state is clean before and after each test."""
    set_dry_run(False)
    yield
    set_dry_run(False)


def test_ci_all_checks_dry_run() -> None:
    """Test devops ci with --dry-run and --fix flags."""
    with patch("devops_cli.commands.ci._run_all_checks_async") as mock_run:
        mock_result = CheckResult(
            name="test",
            display_title="Pytest",
            passed=True,
            duration_seconds=0.5,
            stdout="",
            stderr="",
        )
        mock_run.return_value = [mock_result]

        res = runner.invoke(app, ["--dry-run", "--fix"])
        assert res.exit_code == 0
        assert is_dry_run() is True


def test_ci_format_dry_run_and_fix() -> None:
    """Test devops ci format with --fix and --dry-run."""
    with patch("devops_cli.commands.ci._run", return_value=True) as mock_run:
        res = runner.invoke(app, ["format", "--fix", "--dry-run"])
        assert res.exit_code == 0
        mock_run.assert_called_once()
        cmd = mock_run.call_args[0][0]
        assert "format" in cmd
        assert "--check" not in cmd
        assert is_dry_run() is True


def test_ci_lint_dry_run_and_fix() -> None:
    """Test devops ci lint with --fix and --dry-run."""
    with patch("devops_cli.commands.ci._run", return_value=True) as mock_run:
        res = runner.invoke(app, ["lint", "--fix", "--dry-run"])
        assert res.exit_code == 0
        mock_run.assert_called_once()
        cmd = mock_run.call_args[0][0]
        assert "--fix" in cmd
        assert is_dry_run() is True


def test_ci_test_dry_run_and_options() -> None:
    """Test devops ci test with various flags and --dry-run."""
    with patch("devops_cli.commands.ci._run", return_value=True) as mock_run:
        res = runner.invoke(app, ["test", "-v", "-x", "-n", "2", "-k", "unit", "--dry-run"])
        assert res.exit_code == 0
        mock_run.assert_called_once()
        cmd = mock_run.call_args[0][0]
        assert "-v" in cmd
        assert "-x" in cmd
        assert "-k" in cmd
        assert "unit" in cmd
        assert is_dry_run() is True


def test_ci_coverage_typecheck_audit_security_docs_dry_run() -> None:
    """Test coverage, typecheck, audit, security, actionlint, and docs with --dry-run."""
    with patch("devops_cli.commands.ci._run", return_value=True):
        assert runner.invoke(app, ["coverage", "--html", "--dry-run"]).exit_code == 0
        assert runner.invoke(app, ["coverage", "--xml", "--dry-run"]).exit_code == 0
        assert runner.invoke(app, ["typecheck", "--dry-run"]).exit_code == 0
        assert runner.invoke(app, ["audit", "--dry-run"]).exit_code == 0
        assert runner.invoke(app, ["security", "--severity", "high", "--dry-run"]).exit_code == 0
        assert runner.invoke(app, ["actionlint", "--dry-run"]).exit_code == 0
        assert runner.invoke(app, ["docs", "--dry-run"]).exit_code == 0
