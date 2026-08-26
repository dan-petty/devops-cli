"""Unit tests for Kubeconform OpenAPI manifest validator."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from devops_cli.security.kubeconform import (
    _run_native_fallback_k8s_validation,
    run_kubeconform_validation,
)


def test_kubeconform_fallback_validation(tmp_path: Path) -> None:
    bad_yaml = tmp_path / "bad.yaml"
    bad_yaml.write_text("foo: bar\ncount: 5\n", encoding="utf-8")

    findings = _run_native_fallback_k8s_validation(tmp_path)
    assert len(findings) == 1
    assert "Invalid Kubernetes manifest" in findings[0].title
    assert findings[0].location == "bad.yaml:1"


def test_kubeconform_mocked_binary(tmp_path: Path) -> None:
    fake_line = json.dumps(
        {
            "filename": "service.yaml",
            "kind": "Service",
            "version": "v1",
            "status": "invalid",
            "msg": "spec.ports[0].port: Invalid type. Expected: integer, given: string",
        }
    )

    mock_proc = MagicMock()
    mock_proc.stdout = fake_line + "\n"

    with patch("shutil.which", return_value="/usr/local/bin/kubeconform"):
        with patch("subprocess.run", return_value=mock_proc):
            findings = run_kubeconform_validation(tmp_path, strict=False)
            assert len(findings) == 1
            assert "Kubeconform Schema Validation Error" in findings[0].title
            assert findings[0].location == "service.yaml:1"

        # Non-json and invalid json lines
        mock_proc.stdout = "not json\n{invalid json\n" + json.dumps({"status": "valid"}) + "\n"
        with patch("subprocess.run", return_value=mock_proc):
            findings_non_json = run_kubeconform_validation(tmp_path)
            assert len(findings_non_json) == 0

        # Empty output
        mock_proc.stdout = ""
        with patch("subprocess.run", return_value=mock_proc):
            findings_empty = run_kubeconform_validation(tmp_path)
            assert len(findings_empty) == 0

        # Subprocess exception fallback
        with patch("subprocess.run", side_effect=Exception("Timeout")):
            findings_exc = run_kubeconform_validation(tmp_path)
            assert isinstance(findings_exc, list)

    # When kubeconform binary not in PATH
    with patch("shutil.which", return_value=None):
        findings_nobin = run_kubeconform_validation(tmp_path)
        assert isinstance(findings_nobin, list)
