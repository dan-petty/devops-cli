"""TFLint: the adapter's run of the tool, and the native check it falls back to without it."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from devops_cli.security.tflint import _run_native_fallback_tf_lint, run_tflint_scan
from tests.support.fakes.scanners import ScannerFake
from tests.support.fakes.tool_executor import ToolAnswer


def test_the_fallback_flags_an_open_cidr_on_a_security_group(tmp_path: Path) -> None:
    """`0.0.0.0/0` on a security group is an unrestricted CIDR of severity HIGH."""
    (tmp_path / "main.tf").write_text(
        'resource "aws_security_group" "allow_all" {\n  cidr_blocks = ["0.0.0.0/0"]\n}\n',
        encoding="utf-8",
    )

    findings = _run_native_fallback_tf_lint(tmp_path)

    assert (len(findings) >= 1, "Unrestricted CIDR" in findings[0].title, findings[0].severity) == (
        True,
        True,
        "HIGH",
    )


def test_the_fallback_flags_an_open_cidr_on_a_security_group_rule_at_its_line(
    tmp_path: Path,
) -> None:
    """The finding is located at the line of the CIDR in its file."""
    (tmp_path / "main.tf").write_text(
        'resource "aws_security_group_rule" "ingress" {\n  cidr_blocks = ["0.0.0.0/0"]\n}\n',
        encoding="utf-8",
    )

    findings = _run_native_fallback_tf_lint(tmp_path)

    assert [("CIDR" in f.title, f.location) for f in findings] == [(True, "main.tf:2")]


def test_the_fallback_flags_an_open_cidr_in_a_multi_line_list(tmp_path: Path) -> None:
    """A `cidr_blocks` list over several lines is located at the line of the open CIDR."""
    (tmp_path / "security_groups.tf").write_text(
        """resource "aws_security_group" "web" {
  name = "web-sg"
  ingress {
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = [
      "0.0.0.0/0"
    ]
  }
}
""",
        encoding="utf-8",
    )

    findings = _run_native_fallback_tf_lint(tmp_path)

    assert [("CIDR" in f.title, f.location) for f in findings] == [(True, "security_groups.tf:8")]


def test_the_fallback_finds_nothing_without_a_security_group(tmp_path: Path) -> None:
    """A file with no security group gives no finding."""
    (tmp_path / "main.tf").write_text('resource "aws_s3_bucket" "b" {}\n', encoding="utf-8")

    assert _run_native_fallback_tf_lint(tmp_path) == []


def test_a_scan_without_tflint_uses_the_fallback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """With no `tflint` on PATH, the scan runs the native check."""
    (tmp_path / "main.tf").write_text(
        'resource "aws_security_group" "web" { cidr_blocks = ["0.0.0.0/0"] }\n',
        encoding="utf-8",
    )
    monkeypatch.setenv("PATH", str(tmp_path / "no-programs"))

    assert len(run_tflint_scan(tmp_path)) >= 1


def test_a_scan_maps_each_tflint_severity(tmp_path: Path, scanner_fake: ScannerFake) -> None:
    """TFLint's ERROR, INFO and WARNING become HIGH, LOW and MEDIUM, in report order."""
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


def test_a_tflint_issue_becomes_a_finding_with_its_message_and_location(
    tmp_path: Path, scanner_fake: ScannerFake
) -> None:
    """The finding's title carries the issue's message, and its location the file and line."""
    issue = {
        "rule": {"name": "terraform_deprecated_interpolation", "severity": "WARNING"},
        "message": "Interpolation syntax is deprecated in Terraform 0.12+",
        "range": {"filename": "variables.tf", "start": {"line": 5}},
    }
    scanner_fake.script("tflint", ToolAnswer(stdout=json.dumps({"issues": [issue]})))

    findings = run_tflint_scan(tmp_path)

    assert [("deprecated" in f.title, f.location) for f in findings] == [(True, "variables.tf:5")]


def test_a_scan_with_empty_tflint_output_has_no_finding(
    tmp_path: Path, scanner_fake: ScannerFake
) -> None:
    """Empty stdout gives no finding."""
    scanner_fake.script("tflint", ToolAnswer(stdout=""))

    assert run_tflint_scan(tmp_path) == []


def test_a_scan_falls_back_when_tflint_cannot_start(
    tmp_path: Path, scanner_fake: ScannerFake
) -> None:
    """When `tflint` cannot start, the scan runs the native check, which finds nothing here."""
    scanner_fake.fail("tflint", RuntimeError("Subprocess failed"))

    assert run_tflint_scan(tmp_path) == []
