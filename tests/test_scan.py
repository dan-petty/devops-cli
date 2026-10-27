"""Unit and CLI tests for devops scan subcommands."""

from __future__ import annotations

import json
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from devops_cli.ai.review_schema import Finding
from devops_cli.commands.scan import app as scan_app
from devops_cli.security.zizmor import ZizmorFinding

runner = CliRunner()


def _finding() -> Finding:
    return Finding(
        severity="HIGH",
        location="src/main.py:10",
        title="Test Flaw",
        description="Test description",
        fix="Fix flaw",
    )


def _zizmor_finding() -> ZizmorFinding:
    # A rule outside the blocking set, so `scan workflows` exits 0.
    return ZizmorFinding(
        rule="hardcoded-secrets",
        description="Hardcoded secret",
        severity="High",
        confidence="High",
        path=".github/workflows/ci.yml",
        line=1,
    )


def _patched_scanners() -> ExitStack:
    """Mocks for every scan runner the scan commands dispatch to; use as a context manager."""
    finding = _finding()
    stack = ExitStack()
    stack.enter_context(patch("devops_cli.commands.scan.run_trivy_scan", return_value=[finding]))
    stack.enter_context(patch("devops_cli.commands.scan.run_gitleaks_scan", return_value=[finding]))
    stack.enter_context(patch("devops_cli.commands.scan.run_semgrep_scan", return_value=[finding]))
    stack.enter_context(patch("devops_cli.commands.scan.run_checkov_scan", return_value=[finding]))
    stack.enter_context(
        patch("devops_cli.commands.scan.run_complexity_scan", return_value=[finding])
    )
    stack.enter_context(
        patch("devops_cli.commands.scan.run_zizmor", return_value=[_zizmor_finding()])
    )
    # `scan injection` exits 1 when it reports a finding without `--fail-on`, so it gets no
    # findings: the point is that stdout stays valid JSON, not that a finding is present.
    stack.enter_context(
        patch("devops_cli.commands.scan._collect_injection_findings", return_value=[])
    )
    stack.enter_context(
        patch(
            "devops_cli.commands.scan.generate_aibom",
            return_value={"bomFormat": "cyclonedx", "components": []},
        )
    )
    return stack


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


@pytest.mark.usefixtures("cached_default_ruleset")
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

        res_sast = runner.invoke(scan_app, ["sast", str(tmp_path), "--json"])
        assert res_sast.exit_code == 0

        res_iac = runner.invoke(scan_app, ["iac", str(tmp_path), "--json"])
        assert res_iac.exit_code == 0

        res_secrets_dry = runner.invoke(scan_app, ["secrets", str(tmp_path), "--dry-run"])
        assert res_secrets_dry.exit_code == 0

        res_iac_framework = runner.invoke(
            scan_app, ["iac", str(tmp_path), "--framework", "terraform", "--dry-run"]
        )
        assert res_iac_framework.exit_code == 0


def test_scan_clean_and_dry_run(tmp_path: Path) -> None:
    """Verify scan tool dispatching when no findings are detected."""
    with (
        patch("devops_cli.commands.scan.run_trivy_scan", return_value=[]),
        patch("devops_cli.commands.scan.run_gitleaks_scan", return_value=[]),
        patch("devops_cli.commands.scan.run_semgrep_scan", return_value=[]),
        patch("devops_cli.commands.scan.run_checkov_scan", return_value=[]),
    ):
        res_trivy_clean = runner.invoke(scan_app, ["trivy", str(tmp_path), "--dry-run"])
        assert res_trivy_clean.exit_code == 0

        res_secrets_clean = runner.invoke(scan_app, ["secrets", str(tmp_path), "--dry-run"])
        assert res_secrets_clean.exit_code == 0

        res_sast_clean = runner.invoke(scan_app, ["sast", str(tmp_path), "--dry-run"])
        assert res_sast_clean.exit_code == 0

        res_iac_clean = runner.invoke(scan_app, ["iac", str(tmp_path), "--dry-run"])
        assert res_iac_clean.exit_code == 0

        res_trivy_json_dry = runner.invoke(
            scan_app, ["trivy", str(tmp_path), "--json", "--dry-run"]
        )
        assert res_trivy_json_dry.exit_code == 0

        res_secrets_json_dry = runner.invoke(
            scan_app, ["secrets", str(tmp_path), "--json", "--dry-run"]
        )
        assert res_secrets_json_dry.exit_code == 0

        res_sast_json_dry = runner.invoke(scan_app, ["sast", str(tmp_path), "--json", "--dry-run"])
        assert res_sast_json_dry.exit_code == 0

        res_iac_json_dry = runner.invoke(scan_app, ["iac", str(tmp_path), "--json", "--dry-run"])
        assert res_iac_json_dry.exit_code == 0


@pytest.mark.usefixtures("cached_default_ruleset")
@pytest.mark.parametrize(
    "sub", ["trivy", "secrets", "sast", "iac", "complexity", "workflows", "injection"]
)
@pytest.mark.parametrize("flags", [["--json"], ["--format", "json"]])
def test_scan_json_stdout_is_valid_json(tmp_path: Path, sub: str, flags: list[str]) -> None:
    """stdout of --json and --format json is valid JSON for each scan command (#2216)."""
    with _patched_scanners():
        res = runner.invoke(scan_app, [sub, str(tmp_path), *flags])
    assert res.exit_code == 0, res.output
    json.loads(res.stdout)


@pytest.mark.parametrize("flags", [["--format", "json"]])
def test_aibom_json_stdout_is_valid_json(tmp_path: Path, flags: list[str]) -> None:
    """stdout of `scan aibom --format json` is valid JSON, with no progress line ahead of it (#2216)."""
    with _patched_scanners():
        res = runner.invoke(scan_app, ["aibom", str(tmp_path), *flags])
    assert res.exit_code == 0, res.output
    json.loads(res.stdout)
