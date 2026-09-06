"""Unit tests for Checkov IaC static policy scanner."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

from devops_cli.security.checkov import _run_native_fallback_iac_checks, run_checkov_scan


def test_fallback_iac_checks_dockerfile(tmp_path: Path) -> None:
    dockerfile = tmp_path / "Dockerfile"
    dockerfile.write_text("FROM alpine:latest\nRUN apk add curl\n", encoding="utf-8")

    findings = _run_native_fallback_iac_checks(tmp_path)
    assert len(findings) >= 2  # :latest tag and missing non-root USER
    titles = [f.title for f in findings]
    assert any("latest" in t for t in titles)
    assert any("root" in t for t in titles)


def test_fallback_iac_checks_k8s_privileged(tmp_path: Path) -> None:
    k8s_file = tmp_path / "deployment.yaml"
    k8s_file.write_text(
        """apiVersion: apps/v1
kind: Deployment
metadata:
  name: test
spec:
  template:
    spec:
      containers:
      - name: test
        securityContext:
          privileged: true
""",
        encoding="utf-8",
    )

    findings = _run_native_fallback_iac_checks(tmp_path)
    assert any(f.severity == "CRITICAL" and "Privileged" in f.title for f in findings)


def test_run_checkov_scan_list_output(tmp_path: Path) -> None:
    """Verify checkov list output parsing with severity and location extraction."""
    fake_output = json.dumps(
        [
            {
                "results": {
                    "failed_checks": [
                        {
                            "check_id": "CKV_AWS_1",
                            "check_name": "CRITICAL S3 bucket has public read policy",
                            "file_path": "/main.tf",
                            "file_line_range": [10, 20],
                            "guideline": "Restrict public access to S3.",
                        },
                        {
                            "check_id": "CKV_AWS_2",
                            "check_name": "LOW S3 bucket tagging missing",
                            "file_path": "",
                            "file_line_range": [],
                            "guideline": "",
                        },
                    ]
                }
            }
        ]
    )
    mock_proc = MagicMock(stdout=fake_output)
    with (
        patch("shutil.which", return_value="/usr/local/bin/checkov"),
        patch("subprocess.run", return_value=mock_proc),
    ):
        findings = run_checkov_scan(tmp_path, framework="terraform")
        assert len(findings) == 2
        assert findings[0].severity == "CRITICAL"
        assert findings[0].location == "main.tf:10"


def test_run_checkov_scan_single_dict_output(tmp_path: Path) -> None:
    """Verify checkov single dictionary output format parsing."""
    single_dict_output = json.dumps(
        {
            "results": {
                "failed_checks": [
                    {
                        "check_id": "CKV_DOCKER_1",
                        "check_name": "Ensure container has healthcheck",
                        "file_path": "/Dockerfile",
                        "file_line_range": [1, 2],
                        "guideline": "Add HEALTHCHECK instruction.",
                    }
                ]
            }
        }
    )
    mock_proc = MagicMock(stdout=single_dict_output)
    with (
        patch("shutil.which", return_value="/usr/local/bin/checkov"),
        patch("subprocess.run", return_value=mock_proc),
    ):
        findings_dict = run_checkov_scan(tmp_path)
        assert len(findings_dict) == 1


def test_run_checkov_scan_error_and_empty_output(tmp_path: Path) -> None:
    """Verify checkov handling of invalid json, empty stdout, and exceptions."""
    with patch("shutil.which", return_value="/usr/local/bin/checkov"):
        # Invalid JSON
        with patch("subprocess.run", return_value=MagicMock(stdout="invalid json checkov output")):
            assert isinstance(run_checkov_scan(tmp_path), list)

        # Empty output
        with patch("subprocess.run", return_value=MagicMock(stdout="")):
            assert len(run_checkov_scan(tmp_path)) == 0

        # Exception fallback
        with patch("subprocess.run", side_effect=Exception("Execution failed")):
            assert isinstance(run_checkov_scan(tmp_path), list)


def test_run_checkov_scan_missing_binary(tmp_path: Path) -> None:
    """Verify graceful handling when checkov binary is not in PATH."""
    with patch("shutil.which", return_value=None):
        findings_nobin = run_checkov_scan(tmp_path)
        assert isinstance(findings_nobin, list)


def test_run_checkov_scan_nonzero_exit_with_findings(tmp_path: Path) -> None:
    """Verify checkov scan parses findings even when checkov CLI exits non-zero (failed checks found)."""
    fake_output = json.dumps(
        {
            "results": {
                "failed_checks": [
                    {
                        "check_id": "CKV_AWS_1",
                        "check_name": "S3 bucket has public read policy",
                        "file_path": "/main.tf",
                        "file_line_range": [10, 20],
                        "guideline": "Restrict public access.",
                    }
                ]
            }
        }
    )
    # Checkov returns exit code 1 when failed checks exist
    mock_proc = subprocess.CompletedProcess(
        args=["checkov", "-d", str(tmp_path), "-o", "json"],
        returncode=1,
        stdout=fake_output,
        stderr="",
    )
    with (
        patch("shutil.which", return_value="/usr/local/bin/checkov"),
        patch("subprocess.run", return_value=mock_proc),
    ):
        findings = run_checkov_scan(tmp_path)
        assert len(findings) == 1
        assert findings[0].location == "main.tf:10"
        assert "[CKV_AWS_1]" in findings[0].title
