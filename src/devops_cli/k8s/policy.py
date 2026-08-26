"""Kubernetes admission policy validation engine (Kyverno & OPA Gatekeeper)."""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, Field

from devops_cli.config.commands import (
    build_kyverno_validate_cmd,
    build_opa_eval_cmd,
)
from devops_cli.core.process import run_subprocess
from devops_cli.dry_run import is_dry_run, render_dry_run_result
from devops_cli.telemetry.tracer import trace_span


class PolicyRuleResult(BaseModel):
    """Result of a single policy rule evaluation."""

    policy_name: str
    rule_name: str
    resource_kind: str
    resource_name: str
    status: str  # "pass", "fail", "warn", "skip"
    message: str = ""


class PolicyValidationReport(BaseModel):
    """Aggregated policy validation report."""

    engine: str
    manifest_path: str
    policy_path: str | None = None
    passed_count: int = 0
    failed_count: int = 0
    warning_count: int = 0
    rule_results: list[PolicyRuleResult] = Field(default_factory=list)


def _parse_kyverno_output(raw_stdout: str) -> list[PolicyRuleResult]:
    """Parse JSON output from Kyverno CLI."""
    if not raw_stdout.strip():
        return []
    try:
        data = json.loads(raw_stdout)
    except json.JSONDecodeError:
        return []

    results: list[PolicyRuleResult] = []
    items = data if isinstance(data, list) else data.get("results", [])
    for item in items:
        p_name = item.get("policy", {}).get("name", item.get("policy", "unknown-policy"))
        r_name = item.get("rule", {}).get("name", item.get("rule", "unknown-rule"))
        res_info = item.get("resource", {})
        res_kind = res_info.get("kind", "Unknown")
        res_name = res_info.get("name", "unnamed")
        status = item.get("result", item.get("status", "pass")).lower()
        msg = item.get("message", "")
        results.append(
            PolicyRuleResult(
                policy_name=str(p_name),
                rule_name=str(r_name),
                resource_kind=str(res_kind),
                resource_name=str(res_name),
                status=status,
                message=str(msg),
            )
        )
    return results


def _parse_opa_output(raw_stdout: str) -> list[PolicyRuleResult]:
    """Parse JSON output from OPA CLI eval."""
    if not raw_stdout.strip():
        return []
    try:
        data = json.loads(raw_stdout)
    except json.JSONDecodeError:
        return []

    results: list[PolicyRuleResult] = []
    eval_results = data.get("result", [])
    for entry in eval_results:
        bindings = entry.get("expressions", [{}])[0].get("value", {})
        if isinstance(bindings, dict):
            for rule_k, rule_v in bindings.items():
                status = "fail" if rule_v else "pass"
                results.append(
                    PolicyRuleResult(
                        policy_name="opa-gatekeeper",
                        rule_name=rule_k,
                        resource_kind="Manifest",
                        resource_name="input",
                        status=status,
                        message=f"OPA evaluated rule: {rule_k}",
                    )
                )
    return results


def validate_k8s_policy(
    manifest_path: Path,
    policy_path: Path | None = None,
    engine: str = "kyverno",
    dry_run: bool = False,
) -> PolicyValidationReport:
    """Validate Kubernetes manifests against Kyverno or OPA admission policies."""
    norm_engine = engine.lower().strip()
    if dry_run or is_dry_run():
        mock_rule = PolicyRuleResult(
            policy_name="require-non-root-user",
            rule_name="check-run-as-non-root",
            resource_kind="Deployment",
            resource_name="sample-app",
            status="pass",
            message="[DRY-RUN] Manifest adheres to non-root execution policy.",
        )
        report = PolicyValidationReport(
            engine=norm_engine,
            manifest_path=str(manifest_path),
            policy_path=str(policy_path) if policy_path else None,
            passed_count=1,
            failed_count=0,
            warning_count=0,
            rule_results=[mock_rule],
        )
        render_dry_run_result(
            command="devops k8s validate-policy",
            action="validate_admission_policy",
            details=report.model_dump(),
        )
        return report

    with trace_span("k8s.validate_policy", attributes={"engine": norm_engine}):
        if norm_engine == "opa":
            cmd = build_opa_eval_cmd(
                data_path=policy_path or manifest_path, input_path=manifest_path
            )
        else:
            cmd = build_kyverno_validate_cmd(manifest_path=manifest_path, policy_path=policy_path)

        res = run_subprocess(cmd, check=False)
        rule_results = (
            _parse_opa_output(res.stdout)
            if norm_engine == "opa"
            else _parse_kyverno_output(res.stdout)
        )

        passed_c = sum(1 for r in rule_results if r.status in ("pass", "success"))
        failed_c = sum(1 for r in rule_results if r.status in ("fail", "error"))
        warn_c = sum(1 for r in rule_results if r.status in ("warn", "warning"))

        return PolicyValidationReport(
            engine=norm_engine,
            manifest_path=str(manifest_path),
            policy_path=str(policy_path) if policy_path else None,
            passed_count=passed_c,
            failed_count=failed_c,
            warning_count=warn_c,
            rule_results=rule_results,
        )
