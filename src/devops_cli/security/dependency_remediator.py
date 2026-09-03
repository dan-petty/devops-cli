"""Automated dependency vulnerability remediation and lockfile patching engine."""

from __future__ import annotations

import logging
from collections.abc import Sequence
from pathlib import Path

from devops_cli.config.defaults import DEFAULT_CURRENT_PATH, DEFAULT_SUBPROCESS_TIMEOUT_SECONDS
from devops_cli.core.process import run_subprocess
from devops_cli.models.vulnerability import (
    VulnerabilityFixAction,
    VulnerabilityRecord,
    VulnerabilityRemediationResult,
)
from devops_cli.telemetry import trace_span

logger = logging.getLogger(__name__)

_ECOSYSTEM_LOCKFILES: dict[str, str] = {
    "uv.lock": "PyPI",
    "requirements.txt": "PyPI",
    "package-lock.json": "npm",
    "pnpm-lock.yaml": "npm",
    "yarn.lock": "npm",
    "Cargo.lock": "crates.io",
    "go.sum": "Go",
}


def detect_lockfile_ecosystem(target_dir: Path) -> tuple[str, str | None]:
    """Detect dominant dependency ecosystem and authoritative lockfile in target directory."""
    for lockfile, eco in _ECOSYSTEM_LOCKFILES.items():
        if (target_dir / lockfile).is_file():
            return eco, lockfile
    return "PyPI", None


def build_upgrade_command(
    ecosystem: str, package: str, fixed_version: str | None = None
) -> list[str]:
    """Build canonical package manager upgrade command for target ecosystem."""
    spec = f"{package}=={fixed_version}" if fixed_version else package
    if ecosystem == "PyPI":
        return ["uv", "lock", "--upgrade-package", spec]
    if ecosystem == "npm":
        return ["npm", "update", spec]
    if ecosystem == "crates.io":
        return ["cargo", "update", "-p", package]
    if ecosystem == "Go":
        return ["go", "get", "-u", spec]
    return ["uv", "lock", "--upgrade-package", spec]


_SEVERITY_WEIGHTS: dict[str, int] = {
    "LOW": 1,
    "MEDIUM": 2,
    "HIGH": 3,
    "CRITICAL": 4,
}


def create_remediation_branch(target_dir: Path, package: str, cve_id: str | None) -> str | None:
    """Create a git topic branch for the remediation and return branch name if successful."""
    clean_cve = (cve_id or "cve").lower().replace(":", "-").replace("/", "-")
    branch_name = f"fix/security-{package}-{clean_cve}"
    res = run_subprocess(
        ["git", "checkout", "-b", branch_name],
        cwd=target_dir,
        timeout=DEFAULT_SUBPROCESS_TIMEOUT_SECONDS,
        check=False,
    )
    if res.returncode == 0:
        return branch_name
    return None


class DependencyRemediator:
    """Automated dependency vulnerability remediation and lockfile patching coordinator."""

    def __init__(self, target_dir: Path = DEFAULT_CURRENT_PATH) -> None:
        self.target_dir = Path(target_dir).resolve()
        self.ecosystem, self.lockfile = detect_lockfile_ecosystem(self.target_dir)

    def plan_remediation(
        self,
        vulnerabilities: Sequence[VulnerabilityRecord],
        installed_versions: dict[str, str] | None = None,
        package_filter: str | None = None,
        min_severity: str = "HIGH",
    ) -> VulnerabilityRemediationResult:
        """Formulate a structured remediation plan without executing lockfile updates."""
        versions = installed_versions or {}
        actions: list[VulnerabilityFixAction] = []
        min_weight = _SEVERITY_WEIGHTS.get(min_severity.upper(), 3)

        for v in vulnerabilities:
            if package_filter and v.package.lower() != package_filter.lower():
                continue
            v_weight = _SEVERITY_WEIGHTS.get(v.severity.upper(), 0)
            if v_weight < min_weight:
                continue

            curr = versions.get(v.package, "")
            fix_ver = v.fixed_version or None
            cmd = build_upgrade_command(self.ecosystem, v.package, fix_ver)

            action = VulnerabilityFixAction(
                package=v.package,
                current_version=curr,
                fixed_version=fix_ver,
                cve_id=v.id,
                severity=v.severity,
                upgrade_command=cmd,
                status="PENDING",
            )
            actions.append(action)

        summary = f"Planned {len(actions)} vulnerability remediations across {self.ecosystem}"
        return VulnerabilityRemediationResult(
            target_path=str(self.target_dir),
            ecosystem=self.ecosystem,
            actions=actions,
            summary=summary,
        )

    def apply_action(self, action: VulnerabilityFixAction) -> VulnerabilityFixAction:
        """Execute the upgrade command for a single vulnerability action."""
        if not action.upgrade_command:
            action.status = "SKIPPED"
            return action

        try:
            res = run_subprocess(
                action.upgrade_command,
                cwd=self.target_dir,
                timeout=DEFAULT_SUBPROCESS_TIMEOUT_SECONDS,
                check=False,
            )
            if res.returncode == 0:
                action.status = "APPLIED"
                action.error_message = None
            else:
                action.status = "FAILED"
                action.error_message = res.stderr.strip() or res.stdout.strip() or "Upgrade failed"
        except Exception as exc:
            action.status = "FAILED"
            action.error_message = str(exc)

        return action

    def remediate(
        self,
        actions: Sequence[VulnerabilityFixAction],
        create_branch: bool = False,
    ) -> VulnerabilityRemediationResult:
        """Apply actions sequentially and optionally stage changes on a new git branch."""
        with trace_span(
            "security.dependency_remediator.remediate",
            attributes={"target_dir": str(self.target_dir), "actions_count": len(actions)},
        ):
            branch_name: str | None = None
            if create_branch and actions:
                first = actions[0]
                branch_name = create_remediation_branch(
                    self.target_dir, first.package, first.cve_id
                )

            applied_actions: list[VulnerabilityFixAction] = []
            applied_count = 0

            for act in actions:
                updated = self.apply_action(act)
                if updated.status == "APPLIED":
                    applied_count += 1
                applied_actions.append(updated)

            summary = f"Remediated {applied_count}/{len(actions)} dependencies in {self.ecosystem}"
            return VulnerabilityRemediationResult(
                target_path=str(self.target_dir),
                ecosystem=self.ecosystem,
                actions=applied_actions,
                applied_count=applied_count,
                branch_name=branch_name,
                summary=summary,
            )

    def scan_and_plan(
        self,
        package_filter: str | None = None,
        min_severity: str = "HIGH",
    ) -> VulnerabilityRemediationResult:
        """Audit target directory using OSV or scanner findings and plan remediations."""
        from devops_cli.security.vulnerability_lookup import OSVClient

        client = OSVClient()
        vulnerabilities: list[VulnerabilityRecord] = []
        if package_filter:
            vulnerabilities = client.query_package(package_filter, ecosystem=self.ecosystem)
        else:
            from devops_cli.security.trivy import run_trivy_scan

            findings = run_trivy_scan(self.target_dir, scan_type="fs")
            for f in findings:
                pkg_name = f.location.split(":")[-1] if ":" in f.location else f.location
                cve_match = (
                    f.title.split("]")[0].replace("[", "").strip() if "[" in f.title else None
                )
                vulnerabilities.append(
                    VulnerabilityRecord(
                        id=cve_match or "CVE-UNKNOWN",
                        summary=f.description,
                        severity=f.severity,
                        package=pkg_name,
                        source="Trivy",
                    )
                )

        return self.plan_remediation(
            vulnerabilities, package_filter=package_filter, min_severity=min_severity
        )
