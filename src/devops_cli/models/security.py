"""Pydantic resource models for security scanning, intelligence, and audit operations."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class SecurityScanRequest(BaseModel):
    """Request parameters for security and vulnerability scans."""

    target_path: str = Field(default=".", description="File or directory path to scan")
    scanner: str = Field(
        default="all",
        description="Target scanner engine (all, bandit, checkov, gitleaks, kubelinter, pluto, semgrep, trivy)",
    )
    severity_threshold: str = Field(
        default="LOW",
        description="Minimum severity to include in report (LOW, MEDIUM, HIGH, CRITICAL)",
    )


class StaticFindingEntry(BaseModel):
    """Detailed static code analysis or secret finding."""

    scanner: str = Field(..., description="Scanner engine that produced the finding")
    rule_id: str = Field(..., description="Scanner rule ID or vulnerability identifier")
    title: str = Field(..., description="Finding title or summary")
    description: str = Field(default="", description="Detailed issue description")
    location: str = Field(..., description="File location in canonical file.ext:line format")
    severity: str = Field(default="MEDIUM", description="Finding severity")
    fix_guidance: str | None = Field(default=None, description="Remediation guidance or code fix")


class SecurityScanResult(BaseModel):
    """Consolidated security analysis report."""

    target_path: str = Field(..., description="Target path scanned")
    scanners_executed: list[str] = Field(
        default_factory=list, description="List of scanners executed"
    )
    total_findings: int = Field(default=0, description="Total count of security findings")
    findings: list[StaticFindingEntry] = Field(
        default_factory=list, description="Structured finding records"
    )
    passed: bool = Field(default=True, description="Whether scan passed without blocking findings")


class PackageIntelRequest(BaseModel):
    """Request parameters for querying package threat intelligence and vulnerabilities."""

    package_name: str = Field(
        ..., description="Target package identifier (e.g. requests, pydantic)"
    )
    version: str = Field(default="", description="Package version string")
    ecosystem: str = Field(default="PyPI", description="Package ecosystem (PyPI, npm, Go, Maven)")


class PackageIntelResult(BaseModel):
    """Vulnerability and threat intelligence lookup result for a package."""

    package_name: str = Field(..., description="Queried package name")
    version: str = Field(default="", description="Queried package version")
    ecosystem: str = Field(default="PyPI", description="Package ecosystem")
    is_vulnerable: bool = Field(default=False, description="Whether known CVEs or advisories exist")
    vulnerabilities_count: int = Field(default=0, description="Total count of matching advisories")
    advisories: list[dict[str, Any]] = Field(
        default_factory=list, description="Detailed advisory records from OSV/NVD"
    )
    security_status: str = Field(default="Clean", description="High-level security evaluation")


class NetworkIntelRequest(BaseModel):
    """Request parameters for querying network target threat intelligence."""

    target: str = Field(..., description="IP address, domain name, or URL endpoint")


class NetworkIntelResult(BaseModel):
    """Threat intelligence and reputation report for a network target."""

    target: str = Field(..., description="Target IP or hostname queried")
    target_type: str = Field(default="domain", description="Target classification (ip | domain)")
    is_malicious: bool = Field(default=False, description="Whether target is flagged as malicious")
    risk_level: str = Field(default="LOW", description="Evaluated risk level")
    open_ports: list[int] = Field(default_factory=list, description="Discovered open ports")
    reputation_summary: str = Field(
        default="Safe", description="High-level reputation summary from Shodan/Cloudflare"
    )


class UvAuditRequest(BaseModel):
    """Request parameters for running uv package dependency audit."""

    project_dir: str = Field(
        default=".", description="Project directory containing pyproject.toml / uv.lock"
    )


class UvAuditResult(BaseModel):
    """Result of uv package dependency audit."""

    passed: bool = Field(
        default=True, description="Whether dependencies are free of known vulnerabilities"
    )
    vulnerabilities_count: int = Field(
        default=0, description="Number of vulnerable packages detected"
    )
    packages_audited: int = Field(default=0, description="Total count of audited packages")
    audit_output: str = Field(default="", description="Raw output from uv audit command")


class SSHKeyAuditRequest(BaseModel):
    """Request parameters for auditing SSH keys."""

    ssh_dir: str = Field(default="~/.ssh", description="Directory path containing SSH keys")


class SSHKeyAuditResult(BaseModel):
    """Security audit report for local SSH keys."""

    keys_scanned: int = Field(default=0, description="Total count of SSH keys audited")
    weak_keys_count: int = Field(
        default=0, description="Count of weak/deprecated keys (e.g. RSA < 2048, DSA)"
    )
    permission_issues_count: int = Field(
        default=0, description="Count of keys with overly permissive permissions"
    )
    passed: bool = Field(default=True, description="Whether all SSH keys meet security standards")
    recommendations: list[str] = Field(
        default_factory=list, description="Key hardening recommendations"
    )
