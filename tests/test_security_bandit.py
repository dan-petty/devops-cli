"""Unit tests for Bandit Python security scanner integration."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from devops_cli.ai.review_schema import Finding
from devops_cli.dry_run.state import set_dry_run
from devops_cli.security.bandit import parse_bandit_json, run_bandit_scan


def test_parse_bandit_json_valid() -> None:
    """parse_bandit_json parses Bandit JSON issues correctly into Finding models."""
    sample_payload = {
        "results": [
            {
                "code": "subprocess.Popen(cmd, shell=True)",
                "filename": "src/devops_cli/core/process.py",
                "issue_confidence": "HIGH",
                "issue_severity": "HIGH",
                "issue_text": "Possible shell injection via subprocess",
                "line_number": 42,
                "more_info": "https://bandit.readthedocs.io/rules/B602",
                "test_id": "B602",
                "test_name": "subprocess_popen_with_shell_equals_true",
            }
        ]
    }
    findings = parse_bandit_json(sample_payload, target_path="src/devops_cli/core/process.py")
    assert len(findings) == 1
    f = findings[0]
    assert isinstance(f, Finding)
    assert f.severity == "HIGH"
    assert "B602" in f.title
    assert "src/devops_cli/core/process.py:42" in f.location
    assert "https://bandit.readthedocs.io" in f.fix
    assert f.confidence_score == 0.95


def test_run_bandit_scan_dry_run(tmp_path: Path) -> None:
    """run_bandit_scan returns simulated finding under dry-run mode."""
    set_dry_run(True)
    try:
        findings = run_bandit_scan(tmp_path)
        assert len(findings) == 1
        assert "DRY-RUN" in findings[0].title
        assert findings[0].confidence_score == 1.0
    finally:
        set_dry_run(False)


@patch("devops_cli.security.bandit.run_subprocess")
def test_run_bandit_scan_mocked(mock_proc: MagicMock, tmp_path: Path) -> None:
    """run_bandit_scan executes subprocess and parses stdout results."""
    set_dry_run(False)
    fake_output = {
        "results": [
            {
                "filename": str(tmp_path / "app.py"),
                "issue_confidence": "MEDIUM",
                "issue_severity": "MEDIUM",
                "issue_text": "Hardcoded temporary file used",
                "line_number": 12,
                "test_id": "B108",
                "test_name": "hardcoded_tmp_directory",
            }
        ]
    }
    mock_proc.return_value = MagicMock(stdout=json.dumps(fake_output), returncode=0)
    findings = run_bandit_scan(tmp_path / "app.py")
    assert len(findings) == 1
    assert findings[0].severity == "MEDIUM"
    assert "B108" in findings[0].title
    assert findings[0].confidence_score == 0.85
