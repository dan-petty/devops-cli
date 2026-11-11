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


# A Trivy scan that finds nothing. No recorded Trivy run is in `scanner_fake`, so a test that
# starts `scan trivy` scripts this one, and the scan has the same result on every host (#4321).
_CLEAN_TRIVY_RUN = ToolAnswer(stdout=json.dumps({"Results": []}))


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
def test_scan_individual_tools(
    tmp_path: Path, scanner_fake: ScannerFake, runner: CliRunner
) -> None:
    """Each of `scan trivy`, `scan secrets` and `scan sast` starts its own scanner, and a dry run
    of `scan secrets` starts none. `scanner_fake` answers each scanner, so no test reaches a
    scanner that the host has installed (#4321)."""
    scanner_fake.script("trivy", _CLEAN_TRIVY_RUN)

    exit_codes = [
        runner.invoke(scan_app, [sub, str(tmp_path), "--json"]).exit_code
        for sub in ("trivy", "secrets", "sast")
    ]
    res_secrets_dry = runner.invoke(main_app, ["--dry-run", "scan", "secrets", str(tmp_path)])

    assert (
        exit_codes,
        res_secrets_dry.exit_code,
        [Path(run.argv[0]).name for run in scanner_fake.runs],
    ) == ([0, 0, 0], 0, ["trivy", "gitleaks", "semgrep"])


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
    tmp_path: Path, sub: str, scanner_fake: ScannerFake, runner: CliRunner
) -> None:
    """JSON and YAML output of devops scan holds status, reason, and findings (#2107). Each
    scanner is answered by `scanner_fake` with a clean run, so the scan ran on every host
    (#4321)."""
    scanner_fake.script("trivy", _CLEAN_TRIVY_RUN)
    clean = {"status": "ran", "reason": "", "findings": []}

    res_json = runner.invoke(scan_app, [sub, str(tmp_path), "--json"])
    assert res_json.exit_code == 0, res_json.output
    assert json.loads(res_json.stdout) == clean

    res_yaml = runner.invoke(scan_app, [sub, str(tmp_path), "--format", "yaml"])
    assert res_yaml.exit_code == 0, res_yaml.output
    assert yaml.safe_load(res_yaml.stdout) == clean


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
