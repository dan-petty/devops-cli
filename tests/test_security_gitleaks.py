"""Unit tests for Gitleaks sub-millisecond secret pre-filter and fallback scanning."""

from __future__ import annotations

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


def test_run_gitleaks_scan_fallback_native(tmp_path: Path) -> None:
    secret_file = tmp_path / "secret.env"
    secret_file.write_text("AWS_KEY=AKIAIOSFODNN7EXAMPLE\n", encoding="utf-8")

    clean_file = tmp_path / "clean.py"
    clean_file.write_text("def add(a: int, b: int) -> int:\n    return a + b\n", encoding="utf-8")

    with patch("devops_cli.security.gitleaks.run_subprocess", side_effect=FileNotFoundError):
        findings_secret = run_gitleaks_scan(secret_file)
        assert len(findings_secret) >= 1
        assert "AWS Access Key ID" in findings_secret[0].title

        findings_clean = run_gitleaks_scan(clean_file)
        assert len(findings_clean) == 0


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

    res_scan = runner.invoke(scan_app, ["secrets", str(secret_file)])
    assert res_scan.exit_code == 0
    assert "Gitleaks Secret Scan" in res_scan.stdout

    res_json = runner.invoke(scan_app, ["secrets", str(secret_file), "--json"])
    assert res_json.exit_code == 0
    assert "GITLEAKS" in res_json.stdout
