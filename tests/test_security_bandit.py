"""Unit tests for Bandit Python security scanner integration."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from devops_cli.ai.review_schema import Finding
from devops_cli.dry_run.state import set_dry_run
from devops_cli.security.bandit import BanditScanner, parse_bandit_json, run_bandit_scan


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
    assert "B602" in f.fix
    assert f.confidence_score is None


def test_run_bandit_scan_dry_run(tmp_path: Path) -> None:
    """run_bandit_scan returns simulated finding under dry-run mode."""
    set_dry_run(True)
    try:
        findings = run_bandit_scan(tmp_path)
        assert len(findings) == 1
        assert "DRY-RUN" in findings[0].title
        assert findings[0].confidence_score is None
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
    app_file = tmp_path / "app.py"
    app_file.write_text("import tempfile\n")
    findings = run_bandit_scan(app_file)
    assert len(findings) == 1
    assert findings[0].severity == "MEDIUM"
    assert "B108" in findings[0].title
    assert findings[0].confidence_score is None


# Bandit 1.9 draws a progress bar over more than this many files (bandit/core/manager.py:29).
_BANDIT_PROGRESS_THRESHOLD = 50


def _fake_bandit_1_9(cmd: list[str], **_: object) -> subprocess.CompletedProcess[str]:
    """Answer as Bandit 1.9 does: without -q, a progress bar ahead of the JSON past 50 files.

    It flags each file that calls a shell, at HIGH (above the -ll level the scanner passes), and
    exits 1 when it reports a result.
    """
    if "-r" in cmd:
        files = sorted(Path(cmd[cmd.index("-r") + 1]).rglob("*.py"))
    else:
        files = [Path(arg) for arg in cmd if arg.endswith(".py")]
    results = [
        {
            "filename": str(path),
            "issue_severity": "HIGH",
            "issue_text": "subprocess call with shell=True identified, security issue.",
            "line_number": 2,
            "test_id": "B602",
            "test_name": "subprocess_popen_with_shell_equals_true",
        }
        for path in files
        if "shell=True" in path.read_text(encoding="utf-8")
    ]
    report = json.dumps({"errors": [], "results": results}, indent=2)
    quiet = "-q" in cmd
    progress = not quiet and len(files) > _BANDIT_PROGRESS_THRESHOLD
    bar = "Working... ━━━━ 100% 0:00:20\n" if progress else ""
    stderr = "" if quiet else "[main]\tINFO\tprofile include tests: None\n"
    return subprocess.CompletedProcess(cmd, 1 if results else 0, stdout=bar + report, stderr=stderr)


@pytest.mark.parametrize("shape", ["file list", "directory"])
def test_bandit_reports_its_findings_over_more_than_fifty_files(tmp_path: Path, shape: str) -> None:
    """Verify a scan of 51 files reads Bandit's JSON and its exit 1 as findings, not a failure."""
    for n in range(_BANDIT_PROGRESS_THRESHOLD + 1):
        (tmp_path / f"m{n:02}.py").write_text("x = 1\n", encoding="utf-8")
    (tmp_path / "m07.py").write_text(
        "import subprocess\nsubprocess.call(cmd, shell=True)\n", encoding="utf-8"
    )
    target = sorted(tmp_path.glob("*.py")) if shape == "file list" else tmp_path

    with patch("devops_cli.security.bandit.run_subprocess", side_effect=_fake_bandit_1_9):
        outcome = BanditScanner().scan(target)

    assert (outcome.status, outcome.reason, [(f.location, f.title) for f in outcome]) == (
        "ran",
        "",
        [
            (
                f"{(tmp_path / 'm07.py').resolve()}:2",
                "[B602] subprocess call with shell=True identified, security issue.",
            )
        ],
    )


def test_bandit_asks_for_quiet_output_in_every_command_shape(tmp_path: Path) -> None:
    """Verify each command shape passes -q, which keeps Bandit's progress bar off stdout."""
    app = tmp_path / "app.py"
    app.write_text("x = 1\n", encoding="utf-8")
    scanner = BanditScanner()

    commands = (
        scanner.build_command([app]),
        scanner.build_command(app),
        scanner.build_command(tmp_path),
    )

    assert tuple("-q" in cmd for cmd in commands) == (True, True, True)
