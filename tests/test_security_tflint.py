"""Unit tests for TFLint static analysis."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from devops_cli.security.tflint import _run_native_fallback_tf_lint, run_tflint_scan


def test_tflint_fallback_cidr_check(tmp_path: Path) -> None:
    tf_file = tmp_path / "main.tf"
    tf_file.write_text(
        """resource "aws_security_group_rule" "ingress" {
  cidr_blocks = ["0.0.0.0/0"]
}
""",
        encoding="utf-8",
    )

    findings = _run_native_fallback_tf_lint(tmp_path)
    assert len(findings) == 1
    assert "CIDR" in findings[0].title
    assert findings[0].location == "main.tf:2"


def test_tflint_scan_mocked_binary(tmp_path: Path) -> None:
    fake_output = json.dumps(
        {
            "issues": [
                {
                    "rule": {"name": "terraform_deprecated_interpolation", "severity": "WARNING"},
                    "message": "Interpolation syntax is deprecated in Terraform 0.12+",
                    "range": {"filename": "variables.tf", "start": {"line": 5}},
                }
            ]
        }
    )

    mock_proc = MagicMock()
    mock_proc.stdout = fake_output

    with patch("shutil.which", return_value="/usr/local/bin/tflint"):
        with patch("subprocess.run", return_value=mock_proc):
            findings = run_tflint_scan(tmp_path)
            assert len(findings) == 1
            assert "deprecated" in findings[0].title
            assert findings[0].location == "variables.tf:5"
