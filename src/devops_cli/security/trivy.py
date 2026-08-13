"""Aqua Trivy security vulnerability and misconfiguration scanner integration."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from devops_cli.ai.review_schema import Finding
from devops_cli.core.process import run_subprocess
from devops_cli.dry_run.state import is_dry_run

logger = logging.getLogger(__name__)

CONST_TRIVY_TIMEOUT_SECONDS = 120.0


def parse_trivy_json(data: dict[str, Any], target_path: str = "") -> list[Finding]:
    """Parse Trivy JSON payload into structured Finding objects."""
    findings: list[Finding] = []
    results = data.get("Results") or []

    for res in results:
        target_name = res.get("Target") or target_path or "workspace"

        # Vulnerabilities (CVEs)
        for vuln in res.get("Vulnerabilities") or []:
            cve_id = vuln.get("VulnerabilityID") or "CVE-UNKNOWN"
            pkg = vuln.get("PkgName") or "package"
            installed = vuln.get("InstalledVersion") or "unknown"
            fixed = vuln.get("FixedVersion") or "N/A"
            sev = str(vuln.get("Severity") or "MEDIUM").upper()
            title = vuln.get("Title") or f"Security Vulnerability {cve_id} in {pkg}"
            desc = vuln.get("Description") or f"{cve_id} detected in {pkg} v{installed}."
            fix_msg = (
                f"Upgrade {pkg} from {installed} to {fixed}"
                if fixed != "N/A"
                else "Check upstream for security patches"
            )

            findings.append(
                Finding(
                    severity=sev,
                    location=f"{target_name}:{pkg}",
                    title=f"[{cve_id}] {title}",
                    description=desc[:500],
                    fix=fix_msg,
                    confidence_score=0.95,
                )
            )

        # Misconfigurations (IaC & K8s)
        for misconf in res.get("Misconfigurations") or []:
            rule_id = misconf.get("ID") or "MISCONF"
            title = misconf.get("Title") or f"Misconfiguration {rule_id}"
            desc = (
                misconf.get("Description")
                or misconf.get("Message")
                or "Security misconfiguration detected."
            )
            resolution = misconf.get("Resolution") or "Remediate according to security policy"
            sev = str(misconf.get("Severity") or "MEDIUM").upper()

            findings.append(
                Finding(
                    severity=sev,
                    location=f"{target_name}:{rule_id}",
                    title=f"[{rule_id}] {title}",
                    description=desc[:500],
                    fix=resolution,
                    confidence_score=0.9,
                )
            )

        # Secrets
        for sec in res.get("Secrets") or []:
            rule_id = sec.get("RuleID") or "SECRET"
            title = sec.get("Title") or "Plaintext Secret Detected"
            sev = str(sec.get("Severity") or "HIGH").upper()

            findings.append(
                Finding(
                    severity=sev,
                    location=f"{target_name}:{rule_id}",
                    title=f"[SECRET] {title}",
                    description="Plaintext secret or token identified in workspace file.",
                    fix="Remove hardcoded secret and store in OS Keyring or environment variables",
                    confidence_score=0.95,
                )
            )

    return findings


def run_trivy_scan(
    target: Path = Path("."),
    scan_type: str = "fs",
    severity: str = "UNKNOWN,LOW,MEDIUM,HIGH,CRITICAL",
) -> list[Finding]:
    """Execute Trivy scanner subprocess and return parsed findings."""
    if is_dry_run():
        return [
            Finding(
                severity="HIGH",
                location=f"{target}:CVE-2026-DRYRUN",
                title="[DRY-RUN] Simulated Trivy Vulnerability Scan Result",
                description="Trivy security scan simulation mode active.",
                fix="No action required (dry-run mode)",
                confidence_score=1.0,
            )
        ]

    cmd = [
        "trivy",
        scan_type,
        "--format",
        "json",
        "--severity",
        severity,
        str(target),
    ]

    try:
        proc = run_subprocess(cmd, timeout=CONST_TRIVY_TIMEOUT_SECONDS)
        if proc.stdout:
            data = json.loads(proc.stdout)
            if isinstance(data, dict):
                return parse_trivy_json(data, target_path=str(target))
    except Exception as exc:
        logger.debug(f"Trivy scan execution skipped or failed: {exc}")

    return []
