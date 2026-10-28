"""uv audit: the known vulnerabilities and adverse project statuses of the packages that the
`uv.lock` of a project pins (#2106).

uv audit queries OSV for each package of the lockfile, and the package index for the status of
each project (PEP 792). Its JSON report has the layout of `crates/uv-audit-operations/src/json.rs`
in uv. uv exits 1 when it reports a vulnerability, 0 when it reports none, also with adverse
statuses, and 1 or 2 with no report when the audit could not run. The report gives no severity.

The audit needs the network, so a review, whose sandbox has none, does not run it: osv-scanner
audits the lockfiles of a review from its offline database. The agent tool `scan_uv_audit` and
its MCP tool run this adapter.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, Field

from devops_cli.ai.review_schema import DefectClass, Finding
from devops_cli.config.commands import BIN_UV, build_uv_audit_cmd
from devops_cli.config.constants import CONST_UV_LOCK_FILENAME
from devops_cli.config.defaults import DEFAULT_CURRENT_PATH
from devops_cli.security.base import BaseSecurityScanner, ScanOutcome

if TYPE_CHECKING:
    from devops_cli.security.tool_executor import ToolExecutor


class _Dependency(BaseModel):
    """The package of a vulnerability, at the version that the lockfile pins."""

    name: str
    version: str


class _Vulnerability(BaseModel):
    """One vulnerability of a pinned package, as the report of uv audit gives it."""

    dependency: _Dependency
    display_id: str
    summary: str | None = None
    description: str | None = None
    link: str | None = None
    fix_versions: list[str] = Field(default_factory=list)


class _AdverseStatus(BaseModel):
    """The status of a project that its index marks archived, deprecated or quarantined."""

    name: str
    status: str
    reason: str | None = None


class _Report(BaseModel):
    """The parts of a uv audit JSON report that hold its findings.

    uv writes both lists in each report, also when they are empty. Each is required, so a report
    of another layout fails the scan, and does not read as a scan that found nothing."""

    vulnerabilities: list[_Vulnerability]
    adverse_statuses: list[_AdverseStatus]


def _vulnerability_finding(vulnerability: _Vulnerability) -> Finding:
    """A vulnerability as a finding at its package in the lockfile, with the releases that fix it.

    The report names no path: the lockfile is the `uv.lock` of the project that uv found from the
    directory that it started in."""
    name, version = vulnerability.dependency.name, vulnerability.dependency.version
    advisory = vulnerability.display_id
    summary = vulnerability.summary or f"{name} {version} has a known vulnerability"
    if vulnerability.fix_versions:
        fix = f"Upgrade {name} from {version} to {' or '.join(vulnerability.fix_versions)}"
    else:
        fix = f"No known release of {name} fixes {advisory}. Replace or remove {name}."
    return Finding(
        location=f"{CONST_UV_LOCK_FILENAME}:{name}",
        title=f"[{advisory}] {summary}",
        description=vulnerability.description or "",
        fix=fix,
        references=[vulnerability.link] if vulnerability.link else [],
        category=DefectClass.SUPPLY_CHAIN.value,
        confidence_score=None,
    )


def _adverse_status_finding(status: _AdverseStatus) -> Finding:
    """An adverse project status as a finding at the package in the lockfile."""
    return Finding(
        location=f"{CONST_UV_LOCK_FILENAME}:{status.name}",
        title=f"[{status.status}] {status.name} is {status.status} on its index",
        description=status.reason or "",
        fix=f"Replace {status.name} with a maintained project.",
        category=DefectClass.SUPPLY_CHAIN.value,
        confidence_score=None,
    )


def parse_uv_audit_json(data: Any) -> list[Finding]:
    """The findings of a uv audit JSON report: one for each vulnerability, then one for each
    adverse project status. Each has the default severity, since uv gives none."""
    report = _Report.model_validate(data)
    return [
        *(_vulnerability_finding(vulnerability) for vulnerability in report.vulnerabilities),
        *(_adverse_status_finding(status) for status in report.adverse_statuses),
    ]


class UvAuditScanner(BaseSecurityScanner):
    """Scanner adapter for uv audit, over the project of its target directory."""

    name: str = "uv-audit"
    binary_name: str = BIN_UV

    def build_command(self, target_path: Path, **kwargs: Any) -> list[str]:
        """The audit command. uv finds the project from the directory that the scan starts in."""
        return build_uv_audit_cmd()

    def parse_output(self, data: Any, target_path: Path) -> list[Finding]:
        """The findings of the JSON report of uv audit."""
        return parse_uv_audit_json(data)


def run_uv_audit_scan(
    target: Path = DEFAULT_CURRENT_PATH, *, tool_executor: ToolExecutor | None = None
) -> ScanOutcome:
    """Audit the `uv.lock` of the project of the directory `target`, as it is, and return the
    outcome. uv audit starts in `target` through `tool_executor`."""
    return UvAuditScanner(tool_executor).scan(target)


__all__ = ["UvAuditScanner", "parse_uv_audit_json", "run_uv_audit_scan"]
