"""Unit tests for Semgrep multilingual static AST pattern matching scanner."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from devops_cli.commands.scan import app as scan_app
from devops_cli.security.base import ScanOutcome
from devops_cli.security.semgrep import (
    parse_semgrep_json,
    run_semgrep_scan,
)

runner = CliRunner()


def test_parse_semgrep_json() -> None:
    raw_data = {
        "results": [
            {
                "check_id": "python.lang.security.deserialization.pickle.avoid-pickle",
                "path": "src/cache.py",
                "start": {"line": 20, "col": 5},
                "end": {"line": 20, "col": 25},
                "extra": {
                    "message": "Avoid using pickle for untrusted deserialization",
                    "severity": "ERROR",
                    "metadata": {"cve": "CVE-2023-XXXX", "owasp": "A08:2021"},
                },
            },
            {
                "check_id": "python.flask.security.audit.xss.direct-use-of-jinja2",
                "path": "src/views.py",
                "start": {"line": 40, "col": 1},
                "end": {"line": 45, "col": 1},
                "extra": {
                    "message": "Potential XSS via unescaped template string",
                    "severity": "WARNING",
                },
            },
        ]
    }

    findings = parse_semgrep_json(raw_data)
    assert len(findings) == 2
    assert findings[0].location == "src/cache.py:20"
    assert findings[0].severity == "HIGH"
    assert "CVE: CVE-2023-XXXX" in (findings[0].fix or "")
    assert findings[1].location == "src/views.py:40-45"
    assert findings[1].severity == "MEDIUM"

    # Fallback to lang catalog message when extra.message is absent
    from devops_cli.lang import MESSAGES

    data_no_msg = {"results": [{"check_id": "test-check", "extra": {}}]}
    findings_no_msg = parse_semgrep_json(data_no_msg)
    assert MESSAGES.scan.semgrep_default_message in findings_no_msg[0].description
    assert MESSAGES.scan.semgrep_default_message in findings_no_msg[0].title


def test_run_semgrep_scan_subprocess_mock(tmp_path: Path) -> None:
    test_file = tmp_path / "app.py"
    test_file.write_text("import pickle\npickle.loads(b'...')\n", encoding="utf-8")

    mock_stdout = json.dumps(
        {
            "results": [
                {
                    "check_id": "avoid-pickle",
                    "path": str(test_file),
                    "start": {"line": 2},
                    "end": {"line": 2},
                    "extra": {
                        "message": "Avoid using pickle",
                        "severity": "ERROR",
                    },
                }
            ]
        }
    )

    with patch("devops_cli.security.semgrep.run_subprocess") as mock_proc:
        mock_proc.return_value = subprocess.CompletedProcess(
            args=["semgrep"], returncode=0, stdout=mock_stdout, stderr=""
        )
        findings = run_semgrep_scan(test_file)
        assert len(findings) == 1
        assert "[avoid-pickle]" in findings[0].title
        assert findings[0].location == f"{test_file}:2"


def test_run_semgrep_scan_dry_run(tmp_path: Path) -> None:
    with patch("devops_cli.security.semgrep.is_dry_run", return_value=True):
        findings = run_semgrep_scan(tmp_path / "main.py")
        assert len(findings) == 1
        assert "[DRY-RUN]" in findings[0].title


def test_scan_semgrep_cli(tmp_path: Path) -> None:
    test_file = tmp_path / "test.py"
    test_file.write_text("x = 1\n", encoding="utf-8")

    clean_outcome = ScanOutcome(status="ran", findings=[], reason="")
    with patch("devops_cli.commands.scan.run_semgrep_scan", return_value=clean_outcome):
        res = runner.invoke(scan_app, ["sast", str(test_file)])
        assert (res.exit_code, "No static AST pattern flaws detected" in res.stdout) == (0, True)

        res_json = runner.invoke(scan_app, ["sast", str(test_file), "--json"])
        assert (res_json.exit_code, "[]" in res_json.stdout) == (0, True)


def test_semgrep_build_scan_command_target_filtering(tmp_path: Path) -> None:
    """_build_scan_command filters out doc, lockfile, and binary extensions."""
    from devops_cli.config.defaults import DEFAULT_SEMGREP_CONFIG
    from devops_cli.security.semgrep import _build_scan_command

    py_file = tmp_path / "service.py"
    yaml_file = tmp_path / "deploy.yaml"
    md_file = tmp_path / "README.md"
    lock_file = tmp_path / "uv.lock"
    bin_file = tmp_path / "image.png"

    for f in (py_file, yaml_file, md_file, lock_file, bin_file):
        f.write_text("content", encoding="utf-8")

    cmd = _build_scan_command(
        [py_file, yaml_file, md_file, lock_file, bin_file], DEFAULT_SEMGREP_CONFIG
    )
    assert cmd is not None
    assert (
        str(py_file.resolve()) in cmd,
        str(yaml_file.resolve()) in cmd,
        str(md_file.resolve()) in cmd,
        str(lock_file.resolve()) in cmd,
        str(bin_file.resolve()) in cmd,
    ) == (True, True, False, False, False)

    none_cmd = _build_scan_command([md_file, lock_file, bin_file], DEFAULT_SEMGREP_CONFIG)
    assert none_cmd is None


def test_resolve_cwd_commonpath(tmp_path: Path) -> None:
    """BaseSecurityScanner._resolve_cwd returns common ancestor directory for file lists."""
    from devops_cli.security.semgrep import SemgrepScanner

    scanner = SemgrepScanner()
    sub_a = tmp_path / "src" / "pkg"
    sub_b = tmp_path / "tests" / "unit"
    sub_a.mkdir(parents=True)
    sub_b.mkdir(parents=True)

    file_a = sub_a / "a.py"
    file_b = sub_b / "b.py"
    file_a.write_text("a", encoding="utf-8")
    file_b.write_text("b", encoding="utf-8")

    resolved_cwd = scanner._resolve_cwd([file_a, file_b])
    assert resolved_cwd == tmp_path
