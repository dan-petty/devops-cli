"""Unit tests for Gitleaks sub-millisecond secret pre-filter and fallback scanning."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from devops_cli.commands.scan import app as scan_app
from devops_cli.security.gitleaks import (
    parse_gitleaks_json,
    run_gitleaks_scan,
)

runner = CliRunner()


def test_parse_gitleaks_json() -> None:
    raw_data = [
        {
            "RuleID": "aws-access-key-id",
            "Description": "AWS Access Key ID detected",
            "File": "config/aws.env",
            "StartLine": 12,
            "Match": "AKIAIOSFODNN7EXAMPLE",
        },
        {
            "RuleID": "github-pat",
            "Description": "GitHub Personal Access Token",
            "File": "src/auth.py",
            "Line": 45,
            "Match": "ghp_1234567890abcdefghijklmnopqrstuvwxyz",
        },
    ]

    findings = parse_gitleaks_json(raw_data)
    assert len(findings) == 2
    assert findings[0].location == "config/aws.env:12"
    assert findings[0].severity in ("HIGH", "CRITICAL")
    assert "[GITLEAKS:aws-access-key-id]" in findings[0].title
    assert findings[1].location == "src/auth.py:45"
    assert findings[1].severity == "CRITICAL"


def test_run_gitleaks_scan_missing_binary(tmp_path: Path) -> None:
    secret_file = tmp_path / "secret.env"
    secret_file.write_text("AWS_KEY=AKIAIOSFODNN7EXAMPLE\n", encoding="utf-8")

    with patch("devops_cli.security.base.check_binary", return_value=False):
        outcome = run_gitleaks_scan(secret_file)
        assert (outcome.status, len(outcome.findings)) == ("not installed", 0)


def test_run_gitleaks_scan_dry_run(tmp_path: Path) -> None:
    with patch("devops_cli.security.gitleaks.is_dry_run", return_value=True):
        findings = run_gitleaks_scan(tmp_path / "test.py")
        assert len(findings) == 1
        assert "[DRY-RUN]" in findings[0].title


def test_scan_secrets_cli(tmp_path: Path) -> None:
    secret_file = tmp_path / "creds.env"
    secret_file.write_text(
        "API_TOKEN=ghp_1234567890abcdefghijklmnopqrstuvwxyz123456\n",
        encoding="utf-8",
    )
    fake_json = """[
        {
            "RuleID": "github-pat",
            "Description": "GitHub Personal Access Token",
            "File": "creds.env",
            "StartLine": 1,
            "Match": "ghp_1234567890abcdefghijklmnopqrstuvwxyz123456"
        }
    ]"""
    mock_proc = subprocess.CompletedProcess(
        args=["gitleaks"], returncode=1, stdout=fake_json, stderr=""
    )
    with patch("devops_cli.security.gitleaks.run_subprocess", return_value=mock_proc):
        res_scan = runner.invoke(scan_app, ["secrets", str(secret_file)])
        assert (res_scan.exit_code, "Gitleaks Secret Scan" in res_scan.stdout) == (0, True)

        res_json = runner.invoke(scan_app, ["secrets", str(secret_file), "--json"])
        assert (res_json.exit_code, "GITLEAKS" in res_json.stdout) == (0, True)


def test_gitleaks_binary_mocked_execution(tmp_path: Path) -> None:
    """Verify mocked binary JSON output parsing and location extraction."""
    patterns_file = tmp_path / "all_secrets.txt"
    patterns_file.write_text("KEY=fake\n", encoding="utf-8")

    fake_gitleaks_json = """[
        {
            "RuleID": "generic-api-key",
            "Description": "Generic API Key",
            "File": "config/keys.env",
            "StartLine": 5,
            "Match": "secret12345"
        }
    ]"""
    mock_proc = subprocess.CompletedProcess(
        args=["gitleaks"], returncode=0, stdout=fake_gitleaks_json, stderr=""
    )
    with patch("devops_cli.security.gitleaks.run_subprocess", return_value=mock_proc):
        res_scan = run_gitleaks_scan([patterns_file])
        assert (len(res_scan), res_scan[0].location) == (1, "config/keys.env:5")


def test_run_gitleaks_scan_ignore_tests(tmp_path: Path) -> None:
    """Verify ignore_tests=True filters out test fixtures and test file paths."""
    test_dir = tmp_path / "tests"
    test_dir.mkdir()
    test_file = test_dir / "test_auth.py"
    test_file.write_text("AWS_KEY=AKIAIOSFODNN7EXAMPLE\n", encoding="utf-8")

    src_file = tmp_path / "src_auth.py"
    src_file.write_text("AWS_KEY=AKIAIOSFODNN7EXAMPLE\n", encoding="utf-8")

    def fake_gitleaks(cmd: list[str], **_: object) -> subprocess.CompletedProcess[str]:
        source = cmd[cmd.index("--source") + 1] if "--source" in cmd else str(tmp_path)
        leaks = [
            {
                "RuleID": "aws-key",
                "Description": "AWS Key",
                "File": source,
                "StartLine": 1,
                "Match": "AKIAIOSFODNN7EXAMPLE",
            }
        ]
        return subprocess.CompletedProcess(cmd, 1, stdout=json.dumps(leaks), stderr="")

    with patch("devops_cli.security.gitleaks.run_subprocess", side_effect=fake_gitleaks):
        # Scanning test file directly with ignore_tests=True returns no findings
        res_test_ignored = run_gitleaks_scan(test_file, ignore_tests=True)
        assert len(res_test_ignored) == 0

        # Scanning test file with ignore_tests=False returns findings
        res_test_included = run_gitleaks_scan(test_file, ignore_tests=False)
        assert len(res_test_included) >= 1

        # Scanning list containing both ignores the test file
        res_dir = run_gitleaks_scan([test_file, src_file], ignore_tests=True)
        assert (len(res_dir), "src_auth.py" in res_dir[0].location) == (1, True)


def test_run_gitleaks_scan_ignore_tests_windows_paths(tmp_path: Path) -> None:
    """Verify ignore_tests=True properly filters Windows paths (e.g. C:\\...:line)."""
    fake_gitleaks_json = """[
        {
            "RuleID": "generic-api-key",
            "Description": "Generic Key in Test",
            "File": "C:\\\\Users\\\\dev\\\\project\\\\tests\\\\test_login.py",
            "StartLine": 25,
            "Match": "secret12345"
        },
        {
            "RuleID": "generic-api-key",
            "Description": "Generic Key in Source",
            "File": "C:\\\\Users\\\\dev\\\\project\\\\src\\\\login.py",
            "StartLine": 10,
            "Match": "secret12345"
        }
    ]"""
    mock_proc = subprocess.CompletedProcess(
        args=["gitleaks"], returncode=0, stdout=fake_gitleaks_json, stderr=""
    )
    with patch("devops_cli.security.gitleaks.run_subprocess", return_value=mock_proc):
        # With ignore_tests=True, only the src file is kept
        res_ignored = run_gitleaks_scan(tmp_path, ignore_tests=True)
        assert len(res_ignored) == 1
        assert "login.py" in res_ignored[0].location
        assert "test_login" not in res_ignored[0].location

        # With ignore_tests=False, both are kept
        res_all = run_gitleaks_scan(tmp_path, ignore_tests=False)
        assert len(res_all) == 2


def test_run_gitleaks_scan_list_target_without_binary(tmp_path: Path) -> None:
    """Missing binary reports not installed with empty findings."""
    clean = tmp_path / "clean.py"
    clean.write_text("def add(a: int, b: int) -> int:\n    return a + b\n", encoding="utf-8")
    secret = tmp_path / "secret.env"
    secret.write_text("AWS_KEY=AKIAIOSFODNN7EXAMPLE\n", encoding="utf-8")

    with patch("devops_cli.security.base.check_binary", return_value=False):
        outcome = run_gitleaks_scan([clean, secret])

    assert (outcome.status, len(outcome.findings)) == ("not installed", 0)


def test_run_gitleaks_scan_list_target_runs_binary_on_every_file(tmp_path: Path) -> None:
    """Gitleaks takes one source per run, so a list target runs it once per file."""
    first = tmp_path / "first.py"
    first.write_text("x = 1\n", encoding="utf-8")
    second = tmp_path / "second.env"
    second.write_text("TOKEN=redacted\n", encoding="utf-8")
    sources: list[str] = []

    def fake_gitleaks(cmd: list[str], **_: object) -> subprocess.CompletedProcess[str]:
        source = cmd[cmd.index("--source") + 1]
        sources.append(source)
        leaks = []
        if source == str(second):
            leaks = [
                {
                    "RuleID": "generic-api-key",
                    "Description": "Generic API Key",
                    "File": source,
                    "StartLine": 1,
                    "Match": "TOKEN",
                }
            ]
        return subprocess.CompletedProcess(
            cmd, 1 if leaks else 0, stdout=json.dumps(leaks), stderr=""
        )

    with patch("devops_cli.security.gitleaks.run_subprocess", side_effect=fake_gitleaks):
        outcome = run_gitleaks_scan([first, second])

    assert sources == [str(first), str(second)]
    assert outcome.status == "ran"
    assert [f.location for f in outcome.findings] == [f"{second}:1"]
