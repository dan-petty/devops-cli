"""Unit and CLI tests for devops scan subcommands."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

from devops_cli.ai.review_schema import Finding
from devops_cli.commands.scan import _serialize_scanner_outcome
from devops_cli.commands.scan import app as scan_app
from devops_cli.main import app as main_app
from devops_cli.security.base import ScanOutcome
from devops_cli.security.zizmor import ZizmorFinding
from tests.support.fakes.process import ProcessAnswer, ProcessFake
from tests.support.fakes.scanners import ScannerFake, ToolAnswer


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


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


def test_scan_dry_run(runner: CliRunner) -> None:
    """devops scan --dry-run prints planned scan requests."""
    result = runner.invoke(scan_app, ["--dry-run"])
    assert result.exit_code == 0
    assert "Trivy scan for" in result.output or "trivy" in result.output


@pytest.mark.usefixtures("cached_default_ruleset")
def test_scan_individual_tools(tmp_path: Path, runner: CliRunner) -> None:
    """Verify scan tool dispatching for trivy, secrets, and semgrep."""
    res_trivy = runner.invoke(scan_app, ["trivy", str(tmp_path), "--json"])
    assert res_trivy.exit_code == 0

    res_secrets = runner.invoke(scan_app, ["secrets", str(tmp_path), "--json"])
    assert res_secrets.exit_code == 0

    res_sast = runner.invoke(scan_app, ["sast", str(tmp_path), "--json"])
    assert res_sast.exit_code == 0

    res_secrets_dry = runner.invoke(main_app, ["--dry-run", "scan", "secrets", str(tmp_path)])
    assert res_secrets_dry.exit_code == 0


def test_scan_clean_and_dry_run(tmp_path: Path, runner: CliRunner) -> None:
    """Verify scan tool dispatching when no findings are detected."""
    res_trivy_clean = runner.invoke(scan_app, ["trivy", str(tmp_path), "--dry-run"])
    assert res_trivy_clean.exit_code == 0

    res_secrets_clean = runner.invoke(main_app, ["--dry-run", "scan", "secrets", str(tmp_path)])
    assert res_secrets_clean.exit_code == 0

    res_sast_clean = runner.invoke(scan_app, ["sast", str(tmp_path), "--dry-run"])
    assert res_sast_clean.exit_code == 0

    res_trivy_json_dry = runner.invoke(scan_app, ["trivy", str(tmp_path), "--json", "--dry-run"])
    assert res_trivy_json_dry.exit_code == 0

    res_secrets_json_dry = runner.invoke(
        main_app, ["--dry-run", "scan", "secrets", str(tmp_path), "--json"]
    )
    assert res_secrets_json_dry.exit_code == 0

    res_sast_json_dry = runner.invoke(scan_app, ["sast", str(tmp_path), "--json", "--dry-run"])
    assert res_sast_json_dry.exit_code == 0


@pytest.mark.usefixtures("cached_default_ruleset")
@pytest.mark.parametrize(
    "sub", ["trivy", "secrets", "sast", "complexity", "workflows", "injection"]
)
@pytest.mark.parametrize("flags", [["--json"], ["--format", "json"]])
def test_scan_json_stdout_is_valid_json(
    tmp_path: Path, sub: str, flags: list[str], process_fake: ProcessFake, runner: CliRunner
) -> None:
    """stdout of --json and --format json is valid JSON for each scan command (#2216)."""
    process_fake.answer("zizmor", ProcessAnswer(stdout="[]", returncode=0))
    res = runner.invoke(scan_app, [sub, str(tmp_path), *flags])
    assert res.exit_code == 0, res.output
    json.loads(res.stdout)


def test_scan_has_no_iac_command(tmp_path: Path, runner: CliRunner) -> None:
    """`devops scan iac` ran Checkov, which `tools.lock` does not pin. Trivy's misconfiguration
    scan, `devops scan trivy --type config`, scans the IaC files in its place (#2214)."""
    result = runner.invoke(scan_app, ["iac", str(tmp_path)])

    assert (result.exit_code, "No such command 'iac'" in result.output) == (2, True)


@pytest.mark.parametrize("flags", [["--format", "json"]])
def test_aibom_json_stdout_is_valid_json(
    tmp_path: Path, flags: list[str], runner: CliRunner
) -> None:
    """stdout of `scan aibom --format json` is valid JSON, with no progress line ahead of it (#2216)."""
    res = runner.invoke(scan_app, ["aibom", str(tmp_path), *flags])
    assert res.exit_code == 0, res.output
    json.loads(res.stdout)


@pytest.mark.parametrize(
    ("status", "reason"),
    [
        ("not installed", "Binary 'test' not found on PATH"),
        ("failed", "Scanner exited with code 2"),
        ("not_applicable", "No target files matched"),
        ("ran", ""),
    ],
)
def test_scan_serialized_outcome_model(status: str, reason: str) -> None:
    """_serialize_scanner_outcome preserves status, reason, and findings (#2107)."""
    outcome = ScanOutcome(status=status, findings=[], reason=reason)
    assert _serialize_scanner_outcome(outcome) == {
        "status": status,
        "reason": reason,
        "findings": [],
    }


@pytest.mark.usefixtures("cached_default_ruleset")
@pytest.mark.parametrize("sub", ["trivy", "secrets", "sast"])
def test_scan_serialized_output_holds_status_reason_and_findings(
    tmp_path: Path, sub: str, runner: CliRunner
) -> None:
    """JSON and YAML output of devops scan holds status, reason, and findings (#2107)."""
    res_json = runner.invoke(scan_app, [sub, str(tmp_path), "--json"])
    assert res_json.exit_code == 0, res_json.output
    data_json = json.loads(res_json.stdout)
    assert "status" in data_json
    assert "reason" in data_json
    assert "findings" in data_json

    res_yaml = runner.invoke(scan_app, [sub, str(tmp_path), "--format", "yaml"])
    assert res_yaml.exit_code == 0, res_yaml.output
    data_yaml = yaml.safe_load(res_yaml.stdout)
    assert "status" in data_yaml
    assert "reason" in data_yaml
    assert "findings" in data_yaml


@pytest.mark.usefixtures("cached_default_ruleset")
def test_scan_serialized_output_with_findings(
    tmp_path: Path, scanner_fake: ScannerFake, runner: CliRunner
) -> None:
    """JSON output includes findings list along with status and reason (#2107)."""
    payload = {
        "Results": [
            {
                "Target": str(tmp_path),
                "Vulnerabilities": [
                    {
                        "VulnerabilityID": "CVE-2026-0001",
                        "Severity": "HIGH",
                        "Title": "Test Flaw",
                    }
                ],
            }
        ]
    }
    scanner_fake.script("trivy", ToolAnswer(exit_code=0, stdout=json.dumps(payload)))
    res = runner.invoke(scan_app, ["trivy", str(tmp_path), "--json"])
    assert res.exit_code == 0, res.output
    data = json.loads(res.stdout)
    assert data["status"] == "ran"
    assert data["reason"] == ""
    assert len(data["findings"]) == 1
    assert data["findings"][0]["title"] == "[CVE-2026-0001] Test Flaw"
