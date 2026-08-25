"""Unit and CLI tests for devops scan subcommands."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from devops_cli.ai.review_schema import Finding
from devops_cli.commands.scan import app as scan_app

runner = CliRunner()


def test_scan_dry_run() -> None:
    """devops scan --dry-run prints simulated scan results."""
    mock_finding = Finding(
        severity="HIGH",
        location="src/main.py:10",
        title="Test Flaw",
        description="Test description",
        fix="Fix flaw",
    )
    with patch("devops_cli.commands.scan.run_trivy_scan", return_value=[mock_finding]):
        result = runner.invoke(scan_app, ["--dry-run"])
        assert result.exit_code == 0
        assert "Trivy Security Scan" in result.output or "DRY-RUN" in result.output


def test_scan_individual_tools(tmp_path: Path) -> None:
    """Verify scan tool dispatching for trivy, secrets, semgrep, and checkov."""
    mock_finding = Finding(
        severity="HIGH",
        location="src/main.py:10",
        title="Test Flaw",
        description="Test description",
        fix="Fix flaw",
    )

    with (
        patch("devops_cli.commands.scan.run_trivy_scan", return_value=[mock_finding]),
        patch("devops_cli.commands.scan.run_gitleaks_scan", return_value=[mock_finding]),
        patch("devops_cli.commands.scan.run_semgrep_scan", return_value=[mock_finding]),
        patch("devops_cli.commands.scan.run_checkov_scan", return_value=[mock_finding]),
    ):
        res_trivy = runner.invoke(scan_app, ["trivy", str(tmp_path), "--json"])
        assert res_trivy.exit_code == 0

        res_secrets = runner.invoke(scan_app, ["secrets", str(tmp_path), "--json"])
        assert res_secrets.exit_code == 0

        res_semgrep = runner.invoke(scan_app, ["semgrep", str(tmp_path), "--json"])
        assert res_semgrep.exit_code == 0

        res_checkov = runner.invoke(scan_app, ["checkov", str(tmp_path), "--json"])
        assert res_checkov.exit_code == 0

        res_sast = runner.invoke(scan_app, ["sast", str(tmp_path)])
        assert res_sast.exit_code == 0

        res_iac = runner.invoke(scan_app, ["iac", str(tmp_path)])
        assert res_iac.exit_code == 0
