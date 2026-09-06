"""Checkov IaC Static Policy and Security Compliance Scanner.

Integrates with Checkov CLI to perform static compliance audits across
Terraform, CloudFormation, Kubernetes, and Dockerfile manifests.
"""

from __future__ import annotations

import logging
import re
import shutil
from pathlib import Path
from typing import Any

from devops_cli.ai.review_schema import Finding
from devops_cli.config.defaults import DEFAULT_MCP_TOOL_SHORT_TIMEOUT_SECONDS
from devops_cli.telemetry import trace_span

logger = logging.getLogger(__name__)


def _build_latest_tag_finding(rel_str: str, idx: int) -> Finding:
    """Construct finding for base image using :latest tag."""
    return Finding(
        severity="MEDIUM",
        location=f"{rel_str}:{idx}",
        title="Use of ':latest' tag in base image",
        description="Base images should pin specific digests.",
        fix="Pin an explicit SHA256 digest or immutable version tag.",
    )


def _build_privileged_container_finding(rel_str: str, idx: int) -> Finding:
    """Construct finding for privileged container configuration."""
    return Finding(
        severity="CRITICAL",
        location=f"{rel_str}:{idx}",
        title="Privileged container execution allowed",
        description="SecurityContext allows container root access.",
        fix="Set privileged: false and drop unnecessary capabilities.",
    )


def _check_dockerfile_fallback(f: Path, rel_str: str) -> list[Finding]:
    """Scan Dockerfile for missing USER directive and :latest base image tags."""
    findings: list[Finding] = []
    try:
        lines = f.read_text(encoding="utf-8", errors="replace").splitlines()
        has_user = False
        for idx, line in enumerate(lines, start=1):
            stripped = line.strip()
            if re.match(r"^FROM\s+\S+:latest", stripped, re.IGNORECASE):
                findings.append(_build_latest_tag_finding(rel_str, idx))
            if stripped.startswith("USER "):
                has_user = True
        if not has_user and lines:
            findings.append(
                Finding(
                    severity="HIGH",
                    location=f"{rel_str}:1",
                    title="Container runs as root user",
                    description="No explicit USER directive defined in Dockerfile.",
                    fix="Specify a non-root USER (e.g., USER 1000:1000).",
                )
            )
    except Exception as exc:
        logger.debug("Failed reading %s during fallback scan: %s", f, exc)
    return findings


def _check_k8s_fallback(f: Path, rel_str: str) -> list[Finding]:
    """Scan Kubernetes YAML manifests for privileged container configurations."""
    findings: list[Finding] = []
    try:
        content = f.read_text(encoding="utf-8", errors="replace")
        if "kind: Deployment" not in content and "kind: Pod" not in content:
            return findings
        for idx, line in enumerate(content.splitlines(), start=1):
            if "privileged: true" in line:
                findings.append(_build_privileged_container_finding(rel_str, idx))
    except Exception as exc:
        logger.debug("Failed reading %s during k8s fallback: %s", f, exc)
    return findings


def _run_native_fallback_iac_checks(target_path: Path) -> list[Finding]:
    """Fallback static checks for Dockerfiles and Kubernetes when checkov is not installed."""
    findings: list[Finding] = []
    resolved = target_path.resolve()
    target_files = [resolved] if resolved.is_file() else list(resolved.rglob("*"))

    for f in target_files:
        if not f.is_file():
            continue
        rel_root = resolved if resolved.is_dir() else resolved.parent
        rel_str = str(f.relative_to(rel_root)) if f.is_relative_to(rel_root) else f.name

        if f.name.lower() == "dockerfile" or f.name.lower().endswith(".dockerfile"):
            findings.extend(_check_dockerfile_fallback(f, rel_str))
        elif f.suffix.lower() in (".yaml", ".yml") and not f.name.startswith("."):
            findings.extend(_check_k8s_fallback(f, rel_str))

    return findings


def _parse_checkov_check(check: dict[str, Any]) -> Finding:
    """Transform a single Checkov failed check dict into a structured Finding model."""
    check_id = check.get("check_id", "CKV_UNKNOWN")
    check_name = check.get("check_name", "IaC Policy Violation")
    file_path = check.get("file_path", "")
    file_line_range = check.get("file_line_range", [1, 1])
    start_line = file_line_range[0] if file_line_range else 1
    guideline = check.get("guideline", "")

    severity = "HIGH"
    if "CRITICAL" in check_name.upper():
        severity = "CRITICAL"
    elif "LOW" in check_name.upper():
        severity = "LOW"

    loc = f"{file_path.lstrip('/')}:{start_line}" if file_path else f":{start_line}"
    return Finding(
        severity=severity,
        location=loc,
        title=f"[{check_id}] {check_name}",
        description=check.get("check_result", {}).get("evaluated_keys", "") or check_name,
        fix=guideline or "Review Checkov policy remediation guidance.",
    )


def _parse_checkov_results(results_data: Any) -> list[Finding]:
    """Parse raw Checkov CLI JSON output into a list of normalized Finding models."""
    results = results_data if isinstance(results_data, list) else [results_data]
    findings: list[Finding] = []
    for res in results:
        failed_checks = res.get("results", {}).get("failed_checks", [])
        for check in failed_checks:
            findings.append(_parse_checkov_check(check))
    return findings


@trace_span("security.checkov")
def run_checkov_scan(
    target_path: Path,
    framework: str | None = None,
    timeout: float = DEFAULT_MCP_TOOL_SHORT_TIMEOUT_SECONDS,
) -> list[Finding]:
    """Execute Checkov IaC security scanner on target_path and return normalized findings."""
    checkov_bin = shutil.which("checkov")
    if not checkov_bin:
        logger.debug("Checkov CLI binary not found in PATH; using native fallback rules.")
        return _run_native_fallback_iac_checks(target_path)

    cmd = [checkov_bin, "-d" if target_path.is_dir() else "-f", str(target_path), "-o", "json"]
    if framework:
        cmd.extend(["--framework", framework])

    try:
        from devops_cli.core.process import run_json_subprocess

        raw_data = run_json_subprocess(cmd, timeout=timeout, default={})
        return _parse_checkov_results(raw_data)
    except Exception as exc:
        logger.debug("Checkov execution encountered an error: %s; falling back", exc)
        return _run_native_fallback_iac_checks(target_path)
