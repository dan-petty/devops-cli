"""Unit tests for TFLint static analysis integration."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from devops_cli.security.tflint import _run_native_fallback_tf_lint, run_tflint_scan
from tests.support.fakes.scanners import ScannerFake
from tests.support.fakes.tool_executor import ToolAnswer


def test_tflint_native_fallback(tmp_path: Path) -> None:
    """_run_native_fallback_tf_lint detects unrestricted CIDRs."""
    tf_file = tmp_path / "main.tf"
    tf_file.write_text(
        'resource "aws_security_group" "allow_all" {\n  cidr_blocks = ["0.0.0.0/0"]\n}\n',
        encoding="utf-8",
    )

    findings = _run_native_fallback_tf_lint(tmp_path)
    assert len(findings) >= 1
    assert "Unrestricted CIDR" in findings[0].title
    assert findings[0].severity == "HIGH"


def test_tflint_native_fallback_clean(tmp_path: Path) -> None:
    """_run_native_fallback_tf_lint returns empty list when no security group issues exist."""
    tf_file = tmp_path / "main.tf"
    tf_file.write_text('resource "aws_s3_bucket" "b" {}\n', encoding="utf-8")

    findings = _run_native_fallback_tf_lint(tmp_path)
    assert findings == []


def test_run_tflint_scan_missing_binary(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """When tflint is missing, run_tflint_scan uses fallback."""
    tf_file = tmp_path / "main.tf"
    tf_file.write_text(
        'resource "aws_security_group" "web" { cidr_blocks = ["0.0.0.0/0"] }\n',
        encoding="utf-8",
    )
    monkeypatch.setenv("PATH", str(tmp_path / "no-programs"))

    findings = run_tflint_scan(tmp_path)

    assert len(findings) >= 1


def test_run_tflint_scan_with_binary(tmp_path: Path, scanner_fake: ScannerFake) -> None:
    """When tflint binary is present, runs it and parses JSON output."""
    mock_tflint_output = {
        "issues": [
            {
                "rule": {"name": "terraform_unused_declarations", "severity": "ERROR"},
                "message": "variable declared but not used",
                "range": {"filename": "variables.tf", "start": {"line": 5}},
            },
            {
                "rule": {"name": "terraform_deprecated_syntax", "severity": "INFO"},
                "message": "syntax is deprecated",
                "range": {"filename": "main.tf", "start": {"line": 12}},
            },
            {
                "rule": {"name": "aws_db_instance_unencrypted", "severity": "WARNING"},
                "message": "database storage is not encrypted",
                "range": {"filename": "db.tf", "start": {"line": 20}},
            },
        ]
    }
    scanner_fake.script("tflint", ToolAnswer(exit_code=2, stdout=json.dumps(mock_tflint_output)))
    config_file = tmp_path / ".tflint.hcl"
    config_file.write_text("config {}", encoding="utf-8")

    findings = run_tflint_scan(tmp_path, config_file=config_file)

    assert [f.severity for f in findings] == ["HIGH", "LOW", "MEDIUM"]


def test_run_tflint_scan_empty_output(tmp_path: Path, scanner_fake: ScannerFake) -> None:
    """When tflint returns empty stdout, returns empty list."""
    scanner_fake.script("tflint", ToolAnswer(stdout=""))

    assert run_tflint_scan(tmp_path) == []


def test_run_tflint_scan_exception_fallback(tmp_path: Path, scanner_fake: ScannerFake) -> None:
    """When tflint cannot start, falls back to native inspection."""
    scanner_fake.fail("tflint", RuntimeError("Subprocess failed"))

    assert run_tflint_scan(tmp_path) == []
