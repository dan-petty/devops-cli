"""Aqua Trivy security vulnerability and misconfiguration scanner integration."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from devops_cli.ai.review_schema import Finding
from devops_cli.config.commands import BIN_TRIVY, build_trivy_scan_cmd
from devops_cli.config.defaults import (
    DEFAULT_CURRENT_PATH,
    DEFAULT_TRIVY_SCAN_TYPE,
    DEFAULT_TRIVY_SEVERITIES,
    DEFAULT_TRIVY_TIMEOUT_SECONDS,
)
from devops_cli.dry_run.state import is_dry_run
from devops_cli.security.base import BaseSecurityScanner

logger = logging.getLogger(__name__)


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
                    confidence_score=None,
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
                    confidence_score=None,
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
                    confidence_score=None,
                )
            )

    return findings


class TrivyScanner(BaseSecurityScanner):
    """Declarative security scanner adapter for Aqua Trivy vulnerability detector."""

    name: str = "trivy"
    binary_name: str = BIN_TRIVY

    def build_command(
        self,
        target_path: Path,
        scan_type: str = DEFAULT_TRIVY_SCAN_TYPE,
        severity: str = DEFAULT_TRIVY_SEVERITIES,
        **kwargs: Any,
    ) -> list[str]:
        """Build argument command list for invoking Trivy."""
        return build_trivy_scan_cmd(target_path, scan_type=scan_type, severity=severity)

    def parse_output(self, data: Any, target_path: Path) -> list[Finding]:
        """Parse raw Trivy JSON payload into Finding models."""
        if isinstance(data, dict):
            return parse_trivy_json(data, target_path=str(target_path))
        return []

    def dry_run_scan(self, target_path: Path, **kwargs: Any) -> list[Finding]:
        """Return simulated Trivy findings for dry-run validation."""
        return [
            Finding(
                severity="HIGH",
                location=f"{target_path}:simulation",
                title="[DRY-RUN] Simulated Trivy Vulnerability Scan Result",
                description="Trivy security scan simulation mode active.",
                fix="No action required (dry-run mode)",
                confidence_score=None,
            )
        ]


def run_trivy_scan(
    target: Path = DEFAULT_CURRENT_PATH,
    scan_type: str = DEFAULT_TRIVY_SCAN_TYPE,
    severity: str = DEFAULT_TRIVY_SEVERITIES,
) -> list[Finding]:
    """Execute Trivy scanner subprocess and return parsed findings."""
    from devops_cli.telemetry import trace_span

    scanner = TrivyScanner()
    with trace_span(
        "security.scan.trivy",
        attributes={
            "target": str(target),
            "scan_type": scan_type,
            "severity": severity,
        },
    ) as span_h:
        if is_dry_run():
            return scanner.dry_run_scan(target)

        cmd = scanner.build_command(target, scan_type=scan_type, severity=severity)
        findings: list[Finding] = []

        try:
            from devops_cli.core.process import run_json_subprocess

            data = run_json_subprocess(
                cmd,
                cwd=target if target.is_dir() else target.parent,
                timeout=DEFAULT_TRIVY_TIMEOUT_SECONDS,
                default={},
                check=False,
            )
            findings = scanner.parse_output(data, target)
        except Exception as exc:
            logger.debug(f"Trivy scan execution skipped or failed: {exc}")

        span_h.set_attribute("findings_count", len(findings))
        return findings
