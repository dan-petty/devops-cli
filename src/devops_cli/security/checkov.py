"""Checkov IaC Static Policy and Security Compliance Scanner.

Integrates with Checkov CLI to perform static compliance audits across
Terraform, CloudFormation, Kubernetes, and Dockerfile manifests.
"""

from __future__ import annotations

import json
import logging
import re
import shutil
import subprocess
from pathlib import Path

from devops_cli.ai.review_schema import Finding
from devops_cli.telemetry import trace_span

logger = logging.getLogger(__name__)


def _run_native_fallback_iac_checks(target_path: Path) -> list[Finding]:
    """Fallback static checks for Dockerfiles and Kubernetes when checkov is not installed."""
    findings: list[Finding] = []
    resolved = target_path.resolve()
    target_files = [resolved] if resolved.is_file() else list(resolved.rglob("*"))

    for f in target_files:
        if not f.is_file():
            continue
        rel_str = str(f.relative_to(resolved if resolved.is_dir() else resolved.parent))

        # Check Dockerfiles for root user or latest tag
        if f.name.lower() == "dockerfile" or f.name.lower().endswith(".dockerfile"):
            try:
                lines = f.read_text(encoding="utf-8", errors="replace").splitlines()
                has_user = False
                for idx, line in enumerate(lines, start=1):
                    stripped = line.strip()
                    if re.match(r"^FROM\s+\S+:latest", stripped, re.IGNORECASE):
                        findings.append(
                            Finding(
                                severity="MEDIUM",
                                location=f"{rel_str}:{idx}",
                                title="Use of ':latest' tag in base image",
                                description="Base images should pin specific digests.",
                                fix="Pin an explicit SHA256 digest or immutable version tag.",
                            )
                        )
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

        # Check Kubernetes manifests for privileged mode or missing resources
        if f.suffix.lower() in (".yaml", ".yml") and not f.name.startswith("."):
            try:
                content = f.read_text(encoding="utf-8", errors="replace")
                if "kind: Deployment" in content or "kind: Pod" in content:
                    lines = content.splitlines()
                    for idx, line in enumerate(lines, start=1):
                        if "privileged: true" in line:
                            findings.append(
                                Finding(
                                    severity="CRITICAL",
                                    location=f"{rel_str}:{idx}",
                                    title="Privileged container execution allowed",
                                    description="SecurityContext allows container root access.",
                                    fix="Set privileged: false and drop unnecessary capabilities.",
                                )
                            )
            except Exception as exc:
                logger.debug("Failed reading %s during k8s fallback: %s", f, exc)

    return findings


@trace_span("security.checkov")
def run_checkov_scan(
    target_path: Path,
    framework: str | None = None,
    timeout: float = 60.0,
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
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        if not proc.stdout.strip():
            return []

        raw_data = json.loads(proc.stdout)
        results = raw_data if isinstance(raw_data, list) else [raw_data]
        findings: list[Finding] = []

        for res in results:
            failed_checks = res.get("results", {}).get("failed_checks", [])
            for check in failed_checks:
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
                findings.append(
                    Finding(
                        severity=severity,
                        location=loc,
                        title=f"[{check_id}] {check_name}",
                        description=check.get("check_result", {}).get("evaluated_keys", "")
                        or check_name,
                        fix=guideline or "Review Checkov policy remediation guidance.",
                    )
                )

        return findings
    except Exception as exc:
        logger.debug("Checkov execution encountered an error: %s; falling back", exc)
        return _run_native_fallback_iac_checks(target_path)
