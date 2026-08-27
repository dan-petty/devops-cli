"""Unit tests for Kubernetes admission policy validation (Kyverno & OPA)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from devops_cli.commands.k8s import app
from devops_cli.k8s.policy import (
    _parse_kyverno_output,
    _parse_opa_output,
    validate_k8s_policy,
)

runner = CliRunner()


def test_parse_kyverno_output_empty() -> None:
    assert _parse_kyverno_output("") == []
    assert _parse_kyverno_output("invalid json") == []


def test_parse_kyverno_output_valid() -> None:
    sample_json = json.dumps(
        [
            {
                "policy": {"name": "disallow-privileged"},
                "rule": {"name": "check-privileged"},
                "resource": {"kind": "Pod", "name": "nginx"},
                "result": "pass",
                "message": "Resource is non-privileged",
            },
            {
                "policy": {"name": "require-labels"},
                "rule": {"name": "check-app-label"},
                "resource": {"kind": "Deployment", "name": "web"},
                "result": "fail",
                "message": "Missing app label",
            },
        ]
    )
    results = _parse_kyverno_output(sample_json)
    assert len(results) == 2
    assert results[0].status == "pass"
    assert results[1].status == "fail"
    assert results[0].resource_kind == "Pod"


def test_parse_opa_output_valid() -> None:
    sample_opa = json.dumps(
        {
            "result": [
                {
                    "expressions": [
                        {
                            "value": {
                                "violation_root_user": False,
                                "violation_host_network": True,
                            }
                        }
                    ]
                }
            ]
        }
    )
    results = _parse_opa_output(sample_opa)
    assert len(results) == 2
    assert results[0].status == "pass"
    assert results[1].status == "fail"


def test_validate_k8s_policy_dry_run(tmp_path: Path) -> None:
    manifest = tmp_path / "deployment.yaml"
    manifest.write_text("apiVersion: apps/v1\nkind: Deployment\n")
    report = validate_k8s_policy(manifest, dry_run=True)
    assert report.engine == "kyverno"
    assert report.passed_count == 1
    assert len(report.rule_results) == 1


@patch("devops_cli.k8s.policy.run_subprocess")
def test_validate_k8s_policy_live(mock_run: MagicMock, tmp_path: Path) -> None:
    mock_run.return_value = MagicMock(returncode=0, stdout="[]", stderr="")
    manifest = tmp_path / "deployment.yaml"
    manifest.write_text("apiVersion: apps/v1\nkind: Deployment\n")
    report = validate_k8s_policy(manifest, engine="kyverno")
    assert report.engine == "kyverno"
    assert report.failed_count == 0


def test_cli_validate_policy_dry_run() -> None:
    result = runner.invoke(app, ["validate-policy", "--dry-run"])
    assert result.exit_code == 0
    assert "DRY_RUN" in result.stdout
