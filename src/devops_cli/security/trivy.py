"""Aqua Trivy security vulnerability and misconfiguration scanner integration."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar

from platformdirs import user_cache_dir

from devops_cli.ai.review_schema import DefectClass, Finding
from devops_cli.config.commands import BIN_TRIVY, build_trivy_scan_cmd
from devops_cli.config.constants import (
    CONST_REVIEW_SCAN_TRIVY_CONFIG,
    CONST_TRIVY_CACHE_DIR_ENV,
    CONST_TRIVY_CACHE_DIR_NAME,
    CONST_TRIVY_CHECKS_METADATA,
    CONST_TRIVY_CONFIG_SCAN_TYPE,
    CONST_TRIVY_DB_METADATA,
)
from devops_cli.config.defaults import (
    DEFAULT_CURRENT_PATH,
    DEFAULT_TRIVY_SCAN_TYPE,
    DEFAULT_TRIVY_SEVERITIES,
)
from devops_cli.security.base import (
    BaseSecurityScanner,
    ScannerConfigFile,
    ScanOutcome,
    ToolDataDir,
)

if TYPE_CHECKING:
    from devops_cli.security.tool_executor import ToolExecutor

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
                    # A secret result is a secret's exposure, whatever words its rule uses.
                    category=DefectClass.SECRET_EXPOSURE.value,
                )
            )

    return findings


def _trivy_cache_dir() -> Path:
    """Where Trivy keeps its cache: `TRIVY_CACHE_DIR`, else `trivy` in the user cache directory of
    the platform. `platformdirs` names that directory as the Go standard library does for Trivy.
    A host with no home directory gives a path that does not exist, and a record must not fail a
    scan."""
    configured = os.environ.get(CONST_TRIVY_CACHE_DIR_ENV)
    return Path(
        os.path.expanduser(configured) if configured else user_cache_dir(CONST_TRIVY_CACHE_DIR_NAME)
    )


class TrivyScanner(BaseSecurityScanner):
    """Declarative security scanner adapter for Aqua Trivy vulnerability detector."""

    name: str = "trivy"
    binary_name: str = BIN_TRIVY
    gating: ClassVar[bool] = True
    has_builtin_patterns: ClassVar[bool] = False
    # Trivy reads `trivy.yaml` and `.trivyignore` from its working directory unless named.
    isolation_files: ClassVar[tuple[ScannerConfigFile, ...]] = (
        ScannerConfigFile("--config", "trivy.yaml", CONST_REVIEW_SCAN_TRIVY_CONFIG),
        ScannerConfigFile("--ignorefile", ".trivyignore", ""),
    )
    # The scan, `trivy <scan_type>`, of a run that names no scan type, as a registry run does.
    scan_type: ClassVar[str] = DEFAULT_TRIVY_SCAN_TYPE

    def data_dirs(self) -> tuple[ToolDataDir, ...]:
        """The cache of Trivy, which holds the checks bundle and the vulnerability database that
        Trivy fetched before (#2096). In the sandbox Trivy has no network to fetch them. With no
        bundle in its cache, a `config` scan uses the checks that the binary holds."""
        cache = _trivy_cache_dir()
        return (ToolDataDir(CONST_TRIVY_CACHE_DIR_ENV, cache, cache),)

    def ruleset_files(
        self,
        target_path: Any,
        cwd: Path,
        *,
        scan_type: str | None = None,
        **kwargs: Any,
    ) -> tuple[Path, ...]:
        """The metadata file of what Trivy scans with, if Trivy has fetched it already (#772).

        A `config` scan reads the checks bundle. Any other scan reads the vulnerability database.
        Trivy fetches either one during a scan when its cache holds none or an old one, so the
        file may change while the scan runs.
        """
        kind = (
            CONST_TRIVY_CHECKS_METADATA
            if (scan_type or self.scan_type) == CONST_TRIVY_CONFIG_SCAN_TYPE
            else CONST_TRIVY_DB_METADATA
        )
        metadata = _trivy_cache_dir().joinpath(*kind)
        return (metadata,) if metadata.is_file() else ()

    def build_command(
        self,
        target_path: Path,
        scan_type: str | None = None,
        severity: str = DEFAULT_TRIVY_SEVERITIES,
        **kwargs: Any,
    ) -> list[str]:
        """Build argument command list for invoking Trivy."""
        return build_trivy_scan_cmd(
            target_path, scan_type=scan_type or self.scan_type, severity=severity
        )

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


class TrivyConfigScanner(TrivyScanner):
    """Trivy's misconfiguration scan, `trivy config`, of the IaC files of the target: Dockerfiles,
    Kubernetes manifests, Helm charts, Terraform, CloudFormation, Azure ARM templates and Ansible
    (#2214). It runs the Trivy that `tools.lock` pins with the checks bundle of Trivy."""

    name: str = "trivy-config"
    scan_type: ClassVar[str] = CONST_TRIVY_CONFIG_SCAN_TYPE


def run_trivy_scan(
    target: Path = DEFAULT_CURRENT_PATH,
    scan_type: str = DEFAULT_TRIVY_SCAN_TYPE,
    severity: str = DEFAULT_TRIVY_SEVERITIES,
    *,
    isolated: bool = False,
    tool_executor: ToolExecutor | None = None,
) -> ScanOutcome:
    """Execute Trivy scanner and return scan outcome; `isolated` for a review (#972)."""
    scanner = TrivyScanner(tool_executor)
    return scanner.scan(target, isolated=isolated, scan_type=scan_type, severity=severity)
