"""Unit tests for Semgrep multilingual static AST pattern matching scanner."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from devops_cli.commands.scan import app as scan_app
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

    with patch("devops_cli.security.semgrep.run_semgrep_scan", return_value=[]):
        res = runner.invoke(scan_app, ["semgrep", str(test_file)])
        assert res.exit_code == 0
        assert "No static AST pattern flaws detected" in res.stdout

        res_json = runner.invoke(scan_app, ["semgrep", str(test_file), "--json"])
        assert res_json.exit_code == 0
        assert "[]" in res_json.stdout
