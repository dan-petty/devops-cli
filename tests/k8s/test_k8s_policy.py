"""Unit tests for Kubernetes admission policy validation (Kyverno & OPA)."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

from devops_cli.k8s.policy import (
    parse_kyverno_output,
    parse_opa_output,
    validate_k8s_policy,
)
from tests.support.fakes.process import ProcessAnswer, ProcessFake


def test_parse_kyverno_output_empty() -> None:
    assert parse_kyverno_output("") == []
    assert parse_kyverno_output("invalid json") == []


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
    results = parse_kyverno_output(sample_json)
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
    results = parse_opa_output(sample_opa)
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


def test_validate_k8s_policy_live(process_fake: ProcessFake, tmp_path: Path) -> None:
    process_fake.answer(
        lambda call: "kyverno" in call.argv[0],
        ProcessAnswer(returncode=0, stdout="[]"),
    )
    manifest = tmp_path / "deployment.yaml"
    manifest.write_text("apiVersion: apps/v1\nkind: Deployment\n")
    report = validate_k8s_policy(manifest, engine="kyverno")
    assert report.engine == "kyverno"
    assert report.failed_count == 0


def test_cli_validate_policy_dry_run(cli: Callable[..., Any]) -> None:
    result = cli("k8s", "validate-policy", "--dry-run")
    assert result.exit_code == 0
    assert "DRY_RUN" in result.output
