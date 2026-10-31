"""Planned execution requests for scan commands under dry run (#2250)."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from devops_cli.config.commands import build_trivy_scan_cmd
from devops_cli.config.defaults import (
    DEFAULT_SEMGREP_CONFIG,
    DEFAULT_TRIVY_HIGH_SEVERITY,
    DEFAULT_TRIVY_SCAN_TYPE,
)
from devops_cli.dry_run.requests import PlannedRequest
from devops_cli.security.dependency_remediator import (
    DependencyRemediator,
    build_upgrade_command,
)
from devops_cli.security.registry import global_scanner_registry
from devops_cli.security.semgrep import _build_scan_command
from devops_cli.security.semgrep_registry import CachedRuleset


def plan_trivy_scan(
    target: Path | str,
    scan_type: str = DEFAULT_TRIVY_SCAN_TYPE,
    severity: str = DEFAULT_TRIVY_HIGH_SEVERITY,
) -> list[PlannedRequest]:
    """Generate planned request for Aqua Trivy scan."""
    cmd = build_trivy_scan_cmd(target, scan_type=scan_type, severity=severity)
    return [
        PlannedRequest(
            method="EXEC",
            target=f"trivy {scan_type}",
            argv=tuple(cmd),
        )
    ]


def plan_semgrep_scan(
    target: Path | list[Path],
    config: str = DEFAULT_SEMGREP_CONFIG,
    ruleset: CachedRuleset | None = None,
) -> list[PlannedRequest]:
    """Generate planned request for Semgrep SAST scan."""
    cmd = _build_scan_command(target, config, ruleset) or [
        "semgrep",
        "scan",
        "--config",
        config,
        "--json",
        str(target if isinstance(target, Path) else target[0]),
    ]
    return [
        PlannedRequest(
            method="EXEC",
            target="semgrep scan",
            argv=tuple(cmd),
        )
    ]


def plan_scan_report(
    target: Path | str,
    selected_scanners: Sequence[str] | None = None,
    min_severity: str | None = None,
) -> list[PlannedRequest]:
    """Generate planned requests for all selected scanners in registry."""
    target_path = Path(target).resolve() if Path(target).exists() else Path(target)
    registry = global_scanner_registry
    names = selected_scanners if selected_scanners is not None else registry.list_scanners()

    plans: list[PlannedRequest] = []
    for name in names:
        scanner = registry.get(name)
        if scanner is None:
            continue
        try:
            kwargs = {}
            if min_severity is not None:
                kwargs["min_severity"] = min_severity
            cmd = scanner.build_command(target_path, **kwargs)
            plans.append(
                PlannedRequest(
                    method="EXEC",
                    target=f"{name} scan",
                    argv=tuple(cmd),
                )
            )
        except Exception:
            plans.append(
                PlannedRequest(
                    method="EXEC",
                    target=f"{name} scan",
                    argv=(name, str(target_path)),
                )
            )
    return plans


def plan_scan_fix(
    target: Path | str,
    package: str | None = None,
    min_severity: str = "HIGH",
    apply: bool = False,
    create_branch: bool = False,
) -> list[PlannedRequest]:
    """Generate planned requests for dependency vulnerability remediation."""
    target_path = Path(target).resolve() if Path(target).exists() else Path(target)
    remediator = DependencyRemediator(target_dir=target_path)
    requests: list[PlannedRequest] = []

    # 1. OSV API query
    endpoint = "https://api.osv.dev/v1/query" if package else "https://api.osv.dev/v1/querybatch"
    requests.append(
        PlannedRequest(
            method="POST",
            target=endpoint,
            condition="vulnerable dependencies present",
        )
    )

    # 2. Package upgrade command if --apply
    if apply:
        pkg_spec = package or "<vulnerable-package>"
        upgrade_cmd = build_upgrade_command(remediator.ecosystem, pkg_spec, "<fixed-version>")
        requests.append(
            PlannedRequest(
                method="EXEC",
                target=f"{remediator.ecosystem} upgrade",
                argv=tuple(upgrade_cmd),
                condition="vulnerabilities found",
            )
        )

    # 3. Branch creation if --create-branch
    if create_branch:
        clean_pkg = package or "dependencies"
        requests.append(
            PlannedRequest(
                method="EXEC",
                target="git branch",
                argv=("git", "checkout", "-b", f"fix/security-{clean_pkg}-<cve>"),
                condition="remediation applied",
            )
        )

    return requests
