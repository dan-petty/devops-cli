"""CLI subcommand for security scanning via Trivy, Semgrep, and Gitleaks."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Annotated, Any

import typer

from devops_cli.ai.review_schema import Finding
from devops_cli.config.commands import build_zizmor_cmd
from devops_cli.config.constants import CONST_OUTPUT_FORMAT_TABLE, CONST_SCAN_NO_RESULT_STATUSES
from devops_cli.config.defaults import (
    DEFAULT_CURRENT_PATH,
    DEFAULT_SEMGREP_CONFIG,
    DEFAULT_TABLE_FORMAT,
    DEFAULT_TRIVY_SCAN_TYPE,
    DEFAULT_TRIVY_SEVERITIES,
    DEFAULT_WORKFLOWS_SCAN_PATH,
)
from devops_cli.core.cli import new_typer
from devops_cli.dry_run.models import CommandDryRunResult
from devops_cli.dry_run.state import is_dry_run, set_dry_run
from devops_cli.exceptions.tools import ToolExecutionError
from devops_cli.lang import HELP, MESSAGES
from devops_cli.output import (
    format_json,
    print_error,
    print_info,
    print_muted,
    print_success,
    print_table,
    print_warning,
    render_table,
    write_stdout,
)
from devops_cli.output.serialization import emit_serialized, resolve_format
from devops_cli.security.aibom import generate_aibom
from devops_cli.security.checkov import run_checkov_scan
from devops_cli.security.complexity import run_complexity_scan
from devops_cli.security.gitleaks import run_gitleaks_scan
from devops_cli.security.pipeline import ScanReport, build_report, report_from_findings
from devops_cli.security.registry import global_scanner_registry
from devops_cli.security.sarif import SarifError, read_sarif, write_sarif
from devops_cli.security.sbom import generate_cyclonedx_sbom, generate_spdx_sbom
from devops_cli.security.semgrep import run_semgrep_scan
from devops_cli.security.semgrep_registry import (
    CachedRuleset,
    cached_ruleset,
    is_registry_id,
    warn_of_old_cache,
)
from devops_cli.security.suppression import (
    SuppressionPolicy,
    SuppressionPolicyError,
    load_policy,
)
from devops_cli.security.trivy import run_trivy_scan
from devops_cli.security.zizmor import ZizmorFinding, run_zizmor

logger = logging.getLogger(__name__)

app = new_typer(
    help=HELP.scan.app,
    no_args_is_help=False,
)

_SEV_COLORS = {
    "CRITICAL": "bold red",
    "HIGH": "red",
    "MEDIUM": "yellow",
    "LOW": "cyan",
    "INFO": "dim",
}


def _render_scan_results_table(title: str, findings: list[Finding]) -> None:
    """Render structured rich table for security findings."""
    columns: list[str | tuple[str, str]] = [
        ("Severity", "bold"),
        "Location",
        "Title",
        "Suggested Fix",
    ]
    rows: list[list[str]] = []
    for f in findings:
        style = _SEV_COLORS.get(f.severity.upper(), "white")
        rows.append(
            [
                f"[{style}]{f.severity}[/{style}]",
                f.location,
                f.title,
                f.fix or "-",
            ]
        )

    table = render_table(title=title, columns=columns, rows=rows)
    print_table(table)


def _handle_single_scanner_result(
    tool_name: str,
    findings: Any,
    success_message: str,
) -> bool:
    """Handle unrun or empty scanner findings. Return True if handled (table not rendered).

    A scan that gave no result, such as one whose tool is not installed, is not run, never passed
    (#1435)."""
    status = getattr(findings, "status", "ran")
    reason = getattr(findings, "reason", "")
    if status in CONST_SCAN_NO_RESULT_STATUSES:
        detail = f" ({reason})" if reason else ""
        print_warning(f"{tool_name} was not run{detail}.", safe=True)
        return True
    if not findings:
        print_success(success_message)
        return True
    return False


# =============================================================================
# Root Callback & Subcommands
# =============================================================================


@app.callback(invoke_without_command=True)
def callback(
    ctx: typer.Context,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help=HELP.options.dry_run),
    ] = False,
    json_output: Annotated[
        bool,
        typer.Option("--json", help=HELP.options.json_output),
    ] = False,
) -> None:
    """Security, vulnerability, secret, and AST scanner (Trivy, Semgrep, Gitleaks)."""
    if ctx.invoked_subcommand is None:
        scan_trivy(target=DEFAULT_CURRENT_PATH, dry_run=dry_run, json_output=json_output)


# =============================================================================
# Command: devops scan trivy
# =============================================================================


@app.command("trivy")
def scan_trivy(
    target: Annotated[
        Path,
        typer.Argument(help=HELP.scan.target),
    ] = DEFAULT_CURRENT_PATH,
    scan_type: Annotated[
        str,
        typer.Option("--type", "-t", help=HELP.scan.scan_type),
    ] = DEFAULT_TRIVY_SCAN_TYPE,
    severity: Annotated[
        str,
        typer.Option("--severity", "-s", help=HELP.scan.severity),
    ] = DEFAULT_TRIVY_SEVERITIES,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help=HELP.options.dry_run),
    ] = False,
    output_format: Annotated[
        str,
        typer.Option("--format", "-f", help=HELP.options.format_type),
    ] = DEFAULT_TABLE_FORMAT,
    json_output: Annotated[
        bool,
        typer.Option("--json", help=HELP.options.json_output),
    ] = False,
) -> CommandDryRunResult | None:
    """Run Aqua Trivy vulnerability, secret, and misconfiguration scan."""
    set_dry_run(dry_run)
    target_abs = target.resolve() if target.exists() else target

    if not is_dry_run():
        print_muted(MESSAGES.scan.trivy_executing.format(target=target_abs, scan_type=scan_type))

    findings = run_trivy_scan(target=target_abs, scan_type=scan_type, severity=severity)

    resolved = resolve_format(output_format, json_output=json_output)
    if resolved != CONST_OUTPUT_FORMAT_TABLE:
        data = [f.model_dump() for f in findings]
        emit_serialized(data, resolved)
        if is_dry_run():
            return CommandDryRunResult(
                command=f"devops scan trivy {target} --type {scan_type}",
                target=str(target_abs),
                action="trivy_security_scan",
                details={"scan_type": scan_type, "findings_count": len(findings)},
            )
        return None

    if _handle_single_scanner_result("Trivy", findings, MESSAGES.scan.no_flaws_found):
        if is_dry_run():
            return CommandDryRunResult(
                command=f"devops scan trivy {target} --type {scan_type}",
                target=str(target_abs),
                action="trivy_security_scan",
                details={"scan_type": scan_type, "findings_count": 0},
            )
        return None

    _render_scan_results_table(
        title=f"Trivy Security Scan: {target_abs.name or target_abs}",
        findings=findings,
    )

    if is_dry_run():
        return CommandDryRunResult(
            command=f"devops scan trivy {target} --type {scan_type}",
            target=str(target_abs),
            action="trivy_security_scan",
            details={"scan_type": scan_type, "findings_count": len(findings)},
        )

    return None


# =============================================================================
# Command: devops scan secrets / devops scan gitleaks
# =============================================================================


@app.command("secrets")
def scan_secrets(
    target: Annotated[
        Path,
        typer.Argument(help=HELP.scan.target_secrets),
    ] = DEFAULT_CURRENT_PATH,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help=HELP.options.dry_run),
    ] = False,
    output_format: Annotated[
        str,
        typer.Option("--format", "-f", help=HELP.options.format_type),
    ] = DEFAULT_TABLE_FORMAT,
    json_output: Annotated[
        bool,
        typer.Option("--json", help=HELP.options.json_output),
    ] = False,
) -> CommandDryRunResult | None:
    """Run Gitleaks secret pre-filter scan across workspace or targets."""
    set_dry_run(dry_run)
    target_abs = target.resolve() if target.exists() else target

    if not is_dry_run():
        print_muted(MESSAGES.scan.gitleaks_executing.format(target=target_abs))

    findings = run_gitleaks_scan(target=target_abs)

    resolved = resolve_format(output_format, json_output=json_output)
    if resolved != CONST_OUTPUT_FORMAT_TABLE:
        data = [f.model_dump() for f in findings]
        emit_serialized(data, resolved)
        if is_dry_run():
            return CommandDryRunResult(
                command=f"devops scan secrets {target}",
                target=str(target_abs),
                action="gitleaks_secret_scan",
                details={"findings_count": len(findings)},
            )
        return None

    if _handle_single_scanner_result("Gitleaks", findings, MESSAGES.scan.gitleaks_passed):
        if is_dry_run():
            return CommandDryRunResult(
                command=f"devops scan secrets {target}",
                target=str(target_abs),
                action="gitleaks_secret_scan",
                details={"findings_count": 0},
            )
        return None

    _render_scan_results_table(
        title=f"Gitleaks Secret Scan: {target_abs.name or target_abs}",
        findings=findings,
    )

    if is_dry_run():
        return CommandDryRunResult(
            command=f"devops scan secrets {target}",
            target=str(target_abs),
            action="gitleaks_secret_scan",
            details={"findings_count": len(findings)},
        )
    return None


# =============================================================================
# Command: devops scan workflows
# =============================================================================


def _report_zizmor(target: Path, found: list[ZizmorFinding]) -> bool:
    """Show every finding, then which of them block; True when none does."""
    if not found:
        print_success(MESSAGES.scan.zizmor_passed)
        return True
    _render_scan_results_table(
        title=MESSAGES.scan.zizmor_title.format(target=target),
        findings=[finding.as_finding() for finding in found],
    )
    blocking = [finding for finding in found if finding.blocks]
    if len(blocking) < len(found):
        reported = MESSAGES.scan.zizmor_reported.format(count=len(found) - len(blocking))
        print_info(reported, prefix=False)
    if blocking:
        rules = ", ".join(sorted({finding.rule for finding in blocking}))
        print_error(MESSAGES.scan.zizmor_blocking.format(count=len(blocking), rules=rules))
    return not blocking


@app.command("workflows")
def scan_workflows(
    target: Annotated[
        Path,
        typer.Argument(help=HELP.scan.target_workflows),
    ] = DEFAULT_WORKFLOWS_SCAN_PATH,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help=HELP.options.dry_run),
    ] = False,
    output_format: Annotated[
        str,
        typer.Option("--format", "-f", help=HELP.options.format_type),
    ] = DEFAULT_TABLE_FORMAT,
    json_output: Annotated[
        bool,
        typer.Option("--json", help=HELP.options.json_output),
    ] = False,
) -> CommandDryRunResult | None:
    """Audit GitHub Actions workflows with zizmor offline: template injection, unpinned actions
    and excessive permissions fail it, and every other finding is shown."""
    set_dry_run(dry_run)
    if is_dry_run():
        return CommandDryRunResult(
            command=f"devops scan workflows {target}",
            target=str(target),
            action="zizmor_workflow_audit",
            details={"command": build_zizmor_cmd(target)},
        )
    print_muted(MESSAGES.scan.zizmor_executing.format(target=target))
    try:
        found = run_zizmor(target)
    except ToolExecutionError as exc:
        print_error(str(exc), safe=True)
        raise typer.Exit(1) from exc
    resolved = resolve_format(output_format, json_output=json_output)
    if resolved == CONST_OUTPUT_FORMAT_TABLE:
        passed = _report_zizmor(target, found)
    else:
        emit_serialized(
            [finding.model_dump() | {"blocks": finding.blocks} for finding in found], resolved
        )
        passed = not any(finding.blocks for finding in found)
    if not passed:
        raise typer.Exit(1)
    return None


# =============================================================================
# Command: devops scan sast
# =============================================================================


def _registry_ruleset_for(config: str) -> CachedRuleset | None:
    """The cached ruleset of a registry-id `config`, which the scan reads offline (#1144).

    An old cache is used with a warning on stderr. A registry id that has no cached ruleset
    exits 1 with the fetch command: nothing here reaches the registry. A dry run reads no cache.
    """
    if is_dry_run() or not is_registry_id(config):
        return None
    cached = cached_ruleset(config)
    if cached is None:
        print_error(MESSAGES.review.registry_not_cached.format(ruleset=config))
        raise typer.Exit(1)
    warn_of_old_cache(config, cached)
    return cached


@app.command("sast")
def scan_sast(
    target: Annotated[
        Path,
        typer.Argument(help=HELP.scan.target_semgrep),
    ] = DEFAULT_CURRENT_PATH,
    config: Annotated[
        str,
        typer.Option("--config", "-c", help=HELP.scan.semgrep_config),
    ] = DEFAULT_SEMGREP_CONFIG,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help=HELP.options.dry_run),
    ] = False,
    output_format: Annotated[
        str,
        typer.Option("--format", "-f", help=HELP.options.format_type),
    ] = DEFAULT_TABLE_FORMAT,
    json_output: Annotated[
        bool,
        typer.Option("--json", help=HELP.options.json_output),
    ] = False,
) -> CommandDryRunResult | None:
    """Run static application security testing (SAST) via Semgrep."""
    set_dry_run(dry_run)
    target_abs = target.resolve() if target.exists() else target
    ruleset = _registry_ruleset_for(config)

    if not is_dry_run():
        print_muted(MESSAGES.scan.semgrep_executing.format(target=target_abs, config=config))

    findings = run_semgrep_scan(target=target_abs, config=config, ruleset=ruleset)

    resolved = resolve_format(output_format, json_output=json_output)
    if resolved != CONST_OUTPUT_FORMAT_TABLE:
        data = [f.model_dump() for f in findings]
        emit_serialized(data, resolved)
        if is_dry_run():
            return CommandDryRunResult(
                command=f"devops scan sast {target} --config {config}",
                target=str(target_abs),
                action="semgrep_ast_scan",
                details={"config": config, "findings_count": len(findings)},
            )
        return None

    if _handle_single_scanner_result("Semgrep", findings, MESSAGES.scan.semgrep_passed):
        if is_dry_run():
            return CommandDryRunResult(
                command=f"devops scan sast {target} --config {config}",
                target=str(target_abs),
                action="semgrep_ast_scan",
                details={"config": config, "findings_count": 0},
            )
        return None

    _render_scan_results_table(
        title=f"Semgrep AST Scan: {target_abs.name or target_abs}",
        findings=findings,
    )

    if is_dry_run():
        return CommandDryRunResult(
            command=f"devops scan sast {target} --config {config}",
            target=str(target_abs),
            action="semgrep_ast_scan",
            details={"config": config, "findings_count": len(findings)},
        )
    return None


@app.command("iac")
def scan_iac(
    target: Annotated[
        Path,
        typer.Argument(help=HELP.scan.target_checkov),
    ] = DEFAULT_CURRENT_PATH,
    framework: Annotated[
        str | None,
        typer.Option("--framework", "-f", help=HELP.scan.framework),
    ] = None,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help=HELP.options.dry_run),
    ] = False,
    output_format: Annotated[
        str,
        typer.Option("--format", help=HELP.options.format_type),
    ] = DEFAULT_TABLE_FORMAT,
    json_output: Annotated[
        bool,
        typer.Option("--json", help=HELP.options.json_output),
    ] = False,
) -> CommandDryRunResult | None:
    """Run Checkov IaC static policy and security compliance scan."""
    set_dry_run(dry_run)
    target_abs = target.resolve() if target.exists() else target

    if not is_dry_run():
        print_muted(MESSAGES.scan.checkov_executing.format(target=target_abs))

    findings = run_checkov_scan(target_path=target_abs, framework=framework)

    resolved = resolve_format(output_format, json_output=json_output)
    if resolved != CONST_OUTPUT_FORMAT_TABLE:
        data = [f.model_dump() for f in findings]
        emit_serialized(data, resolved)
        if is_dry_run():
            return CommandDryRunResult(
                command=f"devops scan iac {target}",
                target=str(target_abs),
                action="checkov_iac_scan",
                details={"framework": framework, "findings_count": len(findings)},
            )
        return None

    if _handle_single_scanner_result("Checkov", findings, MESSAGES.scan.checkov_passed):
        if is_dry_run():
            return CommandDryRunResult(
                command=f"devops scan iac {target}",
                target=str(target_abs),
                action="checkov_iac_scan",
                details={"framework": framework, "findings_count": 0},
            )
        return None

    _render_scan_results_table(
        title=f"Checkov IaC Scan: {target_abs.name or target_abs}",
        findings=findings,
    )

    if is_dry_run():
        return CommandDryRunResult(
            command=f"devops scan iac {target}",
            target=str(target_abs),
            action="checkov_iac_scan",
            details={"framework": framework, "findings_count": len(findings)},
        )
    return None


# =============================================================================
# Command: devops scan complexity
# =============================================================================


@app.command("complexity")
def scan_complexity(
    target: Annotated[
        Path,
        typer.Argument(help=HELP.scan.target_complexity),
    ] = DEFAULT_CURRENT_PATH,
    max_complexity: Annotated[
        int,
        typer.Option("--max-complexity", "-c", help=HELP.scan.max_complexity),
    ] = 10,
    max_indent: Annotated[
        int,
        typer.Option("--max-indent", "-i", help=HELP.scan.max_indent),
    ] = 5,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help=HELP.options.dry_run),
    ] = False,
    output_format: Annotated[
        str,
        typer.Option("--format", "-f", help=HELP.options.format_type),
    ] = DEFAULT_TABLE_FORMAT,
    json_output: Annotated[
        bool,
        typer.Option("--json", help=HELP.options.json_output),
    ] = False,
) -> CommandDryRunResult | None:
    """Run AST-based cyclomatic complexity and indentation depth analysis."""
    set_dry_run(dry_run)
    target_abs = target.resolve() if target.exists() else target

    if not is_dry_run() and not json_output:
        print_muted(f"Analyzing code complexity and indentation depth in {target_abs}...")

    findings = run_complexity_scan(
        target_path=target_abs,
        max_complexity=max_complexity,
        max_nesting_depth=max_indent,
    )

    resolved = resolve_format(output_format, json_output=json_output)
    if resolved != CONST_OUTPUT_FORMAT_TABLE:
        data = [f.model_dump() for f in findings]
        emit_serialized(data, resolved)
        if is_dry_run():
            return CommandDryRunResult(
                command=f"devops scan complexity {target}",
                target=str(target_abs),
                action="ast_complexity_scan",
                details={"findings_count": len(findings)},
            )
        return None

    if not findings:
        print_success("✓ Code complexity and indentation depth within standard limits.")
        if is_dry_run():
            return CommandDryRunResult(
                command=f"devops scan complexity {target}",
                target=str(target_abs),
                action="ast_complexity_scan",
                details={"findings_count": 0},
            )
        return None

    _render_scan_results_table(
        title=f"Code Complexity Analysis: {target_abs.name or target_abs}",
        findings=findings,
    )

    if is_dry_run():
        return CommandDryRunResult(
            command=f"devops scan complexity {target}",
            target=str(target_abs),
            action="ast_complexity_scan",
            details={"findings_count": len(findings)},
        )
    return None


# =============================================================================
# Command: devops scan sbom
# =============================================================================


@app.command("sbom")
def scan_sbom(
    target: Annotated[
        Path,
        typer.Argument(help=HELP.scan.target),
    ] = DEFAULT_CURRENT_PATH,
    format_type: Annotated[
        str,
        typer.Option("--format", "-f", help=HELP.scan.sbom_format),
    ] = "cyclonedx",
    output_file: Annotated[
        Path | None,
        typer.Option("--output", "-o", help=HELP.scan.sbom_output),
    ] = None,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help=HELP.options.dry_run),
    ] = False,
) -> CommandDryRunResult | None:
    """Generate Software Bill of Materials (SBOM) in CycloneDX, SPDX, or JSON format."""
    set_dry_run(dry_run)
    target_abs = target.resolve() if target.exists() else target

    if not is_dry_run():
        print_muted(f"Generating {format_type.upper()} SBOM for {target_abs}...")

    norm_format = format_type.lower().strip()
    if norm_format in ("cyclonedx", "json"):
        sbom_data = generate_cyclonedx_sbom(workspace_dir=target_abs)
    elif norm_format == "spdx":
        sbom_data = generate_spdx_sbom(workspace_dir=target_abs)
    else:
        print_error(
            f"Unsupported SBOM format: '{format_type}'. Supported formats: 'cyclonedx', 'spdx', 'json'."
        )
        raise typer.Exit(1)

    rendered_json = format_json(sbom_data) + "\n"

    if output_file:
        out_path = output_file.resolve()
        if not is_dry_run():
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(rendered_json, encoding="utf-8")
            print_success(f"✓ Generated {norm_format.upper()} SBOM at {out_path}")
    else:
        write_stdout(rendered_json)

    if is_dry_run():
        return CommandDryRunResult(
            command=f"devops scan sbom {target} --format {format_type}",
            target=str(target_abs),
            action="generate_sbom",
            details={
                "format": norm_format,
                "components_count": len(sbom_data.get("components", sbom_data.get("packages", []))),
            },
        )
    return None


@app.command("aibom")
def scan_aibom(
    target: Annotated[
        Path,
        typer.Argument(help=HELP.scan.target_aibom),
    ] = DEFAULT_CURRENT_PATH,
    format_type: Annotated[
        str,
        typer.Option("--format", "-f", help=HELP.scan.aibom_format),
    ] = "cyclonedx",
    output_file: Annotated[
        Path | None,
        typer.Option("--output", "-o", help=HELP.scan.aibom_output),
    ] = None,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help=HELP.options.dry_run),
    ] = False,
) -> CommandDryRunResult | None:
    """Generate AI Bill of Materials (AIBOM) with model licenses and hardware estimates."""
    set_dry_run(dry_run)
    target_abs = target.resolve() if target.exists() else target

    if not is_dry_run():
        print_muted(f"Generating AI Bill of Materials (AIBOM) for {target_abs}...")

    norm_format = format_type.lower().strip()
    if norm_format in ("cyclonedx", "json"):
        aibom_data = generate_aibom(workspace_dir=target_abs)
    else:
        print_error(
            f"Unsupported AIBOM format: '{format_type}'. Supported formats: 'cyclonedx', 'json'."
        )
        raise typer.Exit(1)

    rendered_json = format_json(aibom_data) + "\n"

    if output_file:
        out_path = output_file.resolve()
        if not is_dry_run():
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(rendered_json, encoding="utf-8")
            print_success(f"✓ Generated AIBOM manifest at {out_path}")
    else:
        write_stdout(rendered_json)

    if is_dry_run():
        return CommandDryRunResult(
            command=f"devops scan aibom {target} --format {format_type}",
            target=str(target_abs),
            action="generate_aibom",
            details={
                "format": norm_format,
                "models_count": len(aibom_data.get("components", [])),
            },
        )
    return None


@app.command("fix")
def scan_fix(
    target: Annotated[
        Path,
        typer.Argument(
            help="Target project directory containing lockfile or dependencies",
            exists=False,
        ),
    ] = DEFAULT_CURRENT_PATH,
    package: Annotated[
        str | None,
        typer.Option("--package", "-p", help="Specific vulnerable package to remediate"),
    ] = None,
    min_severity: Annotated[
        str,
        typer.Option(
            "--min-severity", "-s", help="Minimum vulnerability severity (LOW|MEDIUM|HIGH|CRITICAL)"
        ),
    ] = "HIGH",
    apply: Annotated[
        bool,
        typer.Option("--apply", help="Apply lockfile upgrades directly"),
    ] = False,
    create_branch: Annotated[
        bool,
        typer.Option("--create-branch", "-b", help="Create a git topic branch for the remediation"),
    ] = False,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help=HELP.options.dry_run),
    ] = False,
) -> CommandDryRunResult | None:
    """Remediate vulnerable dependencies via lockfile upgrades and optional git branch creation."""
    set_dry_run(dry_run)
    target_abs = target.resolve() if target.exists() else target
    from devops_cli.security.dependency_remediator import DependencyRemediator

    remediator = DependencyRemediator(target_dir=target_abs)
    result = remediator.scan_and_plan(package_filter=package, min_severity=min_severity)

    columns: list[str | tuple[str, str]] = [
        ("Package", "bold"),
        "Current",
        "Fixed",
        "CVE",
        "Severity",
        "Status",
    ]
    rows: list[list[str]] = [
        [
            a.package,
            a.current_version or "-",
            a.fixed_version or "latest",
            a.cve_id or "-",
            a.severity,
            a.status,
        ]
        for a in result.actions
    ]

    if is_dry_run():
        print_table(
            "Planned Dependency Vulnerability Remediations (DRY-RUN)", columns=columns, rows=rows
        )
        return CommandDryRunResult(
            command=f"devops scan fix {target}",
            target=str(target_abs),
            action="remediate_dependencies",
            details={"actions_count": len(result.actions), "ecosystem": result.ecosystem},
        )

    if not apply:
        print_table("Planned Dependency Vulnerability Remediations", columns=columns, rows=rows)
        print_muted(
            "Run with --apply to execute lockfile updates, or --create-branch to isolate on a git branch."
        )
        return None

    # Apply remediations
    exec_result = remediator.remediate(result.actions, create_branch=create_branch)
    res_columns: list[str | tuple[str, str]] = [
        ("Package", "bold"),
        "Fixed",
        "CVE",
        "Status",
        "Message",
    ]
    res_rows: list[list[str]] = [
        [
            a.package,
            a.fixed_version or "latest",
            a.cve_id or "-",
            a.status,
            a.error_message or "✓ Applied",
        ]
        for a in exec_result.actions
    ]
    print_table("Remediation Execution Results", columns=res_columns, rows=res_rows)
    if exec_result.branch_name:
        print_success(f"✓ Changes staged on git branch '{exec_result.branch_name}'")
    return None


def _render_report_table(report: ScanReport) -> None:
    """Render correlated findings, most severe and most corroborated first."""
    if not report.clusters:
        print_success(f"No findings at or above the configured threshold in {report.target}.")
        return

    columns: list[str | tuple[str, str]] = [
        ("Severity", "bold"),
        "Location",
        "Tools",
        "Rule",
        "Finding",
    ]
    rows: list[list[str]] = []
    for cluster in report.clusters:
        representative = cluster.representative
        colour = _SEV_COLORS.get(cluster.severity, "white")
        tools = ",".join(cluster.tools)
        # A count is only worth showing when more than one tool agreed.
        if cluster.confirmations > 1:
            tools = f"{tools} ({cluster.confirmations}x)"
        rows.append(
            [
                f"[{colour}]{cluster.severity}[/{colour}]",
                representative.location or "-",
                tools,
                representative.rule_id,
                representative.message[:80],
            ]
        )
    print_table(f"Security Findings — {report.target}", columns, rows)

    counts = report.counts
    summary = "  ".join(f"{name}: {counts[name]}" for name in counts)
    print_muted(summary)
    if report.duplicates_removed:
        print_muted(f"{report.duplicates_removed} duplicate finding(s) collapsed.")
    if report.suppressed:
        print_muted(f"{len(report.suppressed)} finding(s) hidden by the suppression policy.")


def _render_suppressed(report: ScanReport) -> None:
    """List what the policy hid and which rule hid it."""
    if not report.suppressed:
        return
    columns: list[str | tuple[str, str]] = [("Severity", "bold"), "Location", "Rule", "Reason"]
    rows = [
        [finding.severity, finding.location or "-", rule.rule, rule.reason or "-"]
        for finding, rule in report.suppressed
    ]
    print_table("Suppressed Findings", columns, rows)


def _warn_expired(report: ScanReport) -> None:
    """Surface lapsed suppressions, which are no longer hiding anything."""
    for rule in report.expired_suppressions:
        print_muted(
            f"Suppression for '{rule.rule}' expired on {rule.expires}; "
            f"its findings are being reported again ({rule.source})."
        )


def _load_policy_or_exit(policy_path: Path | None) -> SuppressionPolicy | None:
    """Load a suppression policy, failing loudly rather than scanning without it.

    Continuing with no policy after being handed one would report findings the operator
    believes are accepted, training them to ignore the output.
    """
    if policy_path is None:
        return None
    try:
        return load_policy(policy_path)
    except SuppressionPolicyError as exc:
        print_error(str(exc))
        raise typer.Exit(2) from exc


def _warn_missing_scanners(report: ScanReport) -> None:
    """Warn about missing/unavailable or failed scanners."""
    for name, outcome in report.outcomes.items():
        if outcome.status == "unavailable":
            print_warning(f"Scanner '{name}' was not run ({outcome.reason}).", safe=True)
        elif outcome.status == "failed":
            print_warning(f"Scanner '{name}' failed during execution: {outcome.reason}", safe=True)


def _check_failed_scanners(report: ScanReport, json_output: bool) -> bool:
    """Return True if any scanner failed, printing an error message if not json_output."""
    failed = [name for name, o in report.outcomes.items() if o.status == "failed"]
    if failed and not json_output:
        print_error(f"Scanner(s) failed during execution: {', '.join(sorted(failed))}")
    return bool(failed)


def _check_explicit_scanners_not_run(
    report: ScanReport, explicit_scanners: list[str], json_output: bool
) -> bool:
    """Return True if any explicitly named scanner did not run."""
    not_run = [
        name
        for name in explicit_scanners
        if report.outcomes.get(name) is None
        or report.outcomes[name].status not in ("ran", "built-in patterns")
    ]
    if not_run and not json_output:
        print_error(f"Requested scanner(s) did not run: {', '.join(sorted(not_run))}")
    return bool(not_run)


def _evaluate_fail_on(
    report: ScanReport,
    *,
    fail_on: str | None,
    explicit_scanners: list[str] | None,
    json_output: bool,
) -> None:
    """Enforce failure criteria when --fail-on is specified."""
    if not fail_on:
        return

    if _check_failed_scanners(report, json_output):
        raise typer.Exit(1)

    if explicit_scanners and _check_explicit_scanners_not_run(
        report, explicit_scanners, json_output
    ):
        raise typer.Exit(1)

    if report.exceeds(fail_on):
        raise typer.Exit(1)


def _collect_injection_findings(target_abs: Path) -> list[Finding]:
    """Scan target path or file for injection findings."""
    from devops_cli.security.prompt_injection import scan_injection_file, scan_injection_paths

    if target_abs.is_file():
        return scan_injection_file(target_abs)
    return scan_injection_paths([target_abs])


def _render_injection_report(
    report: ScanReport,
    resolved: str,
    show_suppressed: bool,
    sarif: Path | None,
) -> None:
    """Render injection scan report in either serialized or table format."""
    if resolved != CONST_OUTPUT_FORMAT_TABLE:
        emit_serialized(report.as_dict(), resolved)
        return

    if report.total == 0:
        print_success(MESSAGES.scan.injection_passed)
    else:
        _render_report_table(report)
    _warn_expired(report)
    if show_suppressed:
        _render_suppressed(report)
    if sarif is not None:
        print_success(f"SARIF document written to {sarif}")


def _check_injection_exit(report: ScanReport, fail_on: str | None) -> None:
    """Exit with non-zero status if findings exceed fail_on or findings exist."""
    if fail_on:
        if report.exceeds(fail_on):
            raise typer.Exit(1)
    elif report.findings:
        raise typer.Exit(1)


@app.command("injection")
def scan_injection(
    target: Annotated[
        Path,
        typer.Argument(help=HELP.scan.target_injection),
    ] = DEFAULT_CURRENT_PATH,
    sarif: Annotated[
        Path | None,
        typer.Option("--sarif", help=HELP.scan.sarif_output),
    ] = None,
    min_severity: Annotated[
        str | None,
        typer.Option("--min-severity", help=HELP.scan.min_severity),
    ] = None,
    suppress: Annotated[
        Path | None,
        typer.Option("--suppress", help=HELP.scan.suppression_policy),
    ] = None,
    show_suppressed: Annotated[
        bool,
        typer.Option("--show-suppressed", help=HELP.scan.show_suppressed),
    ] = False,
    fail_on: Annotated[
        str | None,
        typer.Option("--fail-on", help=HELP.scan.fail_on),
    ] = None,
    output_format: Annotated[
        str,
        typer.Option("--format", "-f", help=HELP.options.format_type),
    ] = DEFAULT_TABLE_FORMAT,
    json_output: Annotated[
        bool,
        typer.Option("--json", help=HELP.options.json_output),
    ] = False,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help=HELP.options.dry_run),
    ] = False,
) -> CommandDryRunResult | None:
    """Scan target files for prompt-injection smuggling vectors and canary tokens."""
    set_dry_run(dry_run)
    target_abs = target.resolve() if target.exists() else target
    policy = _load_policy_or_exit(suppress)

    if is_dry_run():
        return CommandDryRunResult(
            command=f"devops scan injection {target}",
            target=str(target_abs),
            action="prompt_injection_scan",
            details={"sarif": str(sarif) if sarif else None},
        )

    resolved = resolve_format(output_format, json_output=json_output)
    if resolved == CONST_OUTPUT_FORMAT_TABLE:
        print_muted(MESSAGES.scan.injection_executing.format(target=target_abs))

    raw_findings = _collect_injection_findings(target_abs)
    report = build_report(
        {"injection": raw_findings},
        target_abs,
        policy=policy,
        min_severity=min_severity,
    )

    if sarif is not None:
        write_sarif(report.findings, sarif, report.outcomes)

    _render_injection_report(report, resolved, show_suppressed, sarif)
    _check_injection_exit(report, fail_on)
    return None


@app.command("report")
def scan_report(
    target: Annotated[
        Path,
        typer.Argument(help=HELP.scan.target_report),
    ] = DEFAULT_CURRENT_PATH,
    scanners: Annotated[
        list[str] | None,
        typer.Option("--scanner", "-s", help=HELP.scan.scanners),
    ] = None,
    sarif: Annotated[
        Path | None,
        typer.Option("--sarif", help=HELP.scan.sarif_output),
    ] = None,
    min_severity: Annotated[
        str | None,
        typer.Option("--min-severity", help=HELP.scan.min_severity),
    ] = None,
    suppress: Annotated[
        Path | None,
        typer.Option("--suppress", help=HELP.scan.suppression_policy),
    ] = None,
    show_suppressed: Annotated[
        bool,
        typer.Option("--show-suppressed", help=HELP.scan.show_suppressed),
    ] = False,
    fail_on: Annotated[
        str | None,
        typer.Option("--fail-on", help=HELP.scan.fail_on),
    ] = None,
    output_format: Annotated[
        str,
        typer.Option("--format", "-f", help=HELP.options.format_type),
    ] = DEFAULT_TABLE_FORMAT,
    json_output: Annotated[
        bool,
        typer.Option("--json", help=HELP.options.json_output),
    ] = False,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help=HELP.options.dry_run),
    ] = False,
) -> None:
    """Run every registered scanner and report deduplicated, correlated findings."""
    set_dry_run(dry_run)
    target_abs = target.resolve() if target.exists() else target
    policy = _load_policy_or_exit(suppress)

    registry = global_scanner_registry
    selected = scanners or registry.list_scanners()
    unknown = [name for name in selected if registry.get(name) is None]
    if unknown:
        print_error(f"Unknown scanner(s): {', '.join(sorted(unknown))}")
        raise typer.Exit(2)

    results = registry.scan_all(target_abs, names=selected)
    report = build_report(results, target_abs, policy=policy, min_severity=min_severity)

    if sarif is not None:
        write_sarif(report.findings, sarif, report.outcomes)

    resolved = resolve_format(output_format, json_output=json_output)
    if resolved != CONST_OUTPUT_FORMAT_TABLE:
        emit_serialized(report.as_dict(), resolved)
    else:
        _render_report_table(report)
        _warn_expired(report)
        _warn_missing_scanners(report)
        if show_suppressed:
            _render_suppressed(report)
        if sarif is not None:
            print_success(f"SARIF document written to {sarif}")

    _evaluate_fail_on(
        report,
        fail_on=fail_on,
        explicit_scanners=scanners,
        json_output=(resolved != CONST_OUTPUT_FORMAT_TABLE),
    )


@app.command("sarif")
def scan_sarif(
    document: Annotated[
        Path,
        typer.Argument(help=HELP.scan.sarif_import),
    ],
    min_severity: Annotated[
        str | None,
        typer.Option("--min-severity", help=HELP.scan.min_severity),
    ] = None,
    suppress: Annotated[
        Path | None,
        typer.Option("--suppress", help=HELP.scan.suppression_policy),
    ] = None,
    show_suppressed: Annotated[
        bool,
        typer.Option("--show-suppressed", help=HELP.scan.show_suppressed),
    ] = False,
    fail_on: Annotated[
        str | None,
        typer.Option("--fail-on", help=HELP.scan.fail_on),
    ] = None,
    output_format: Annotated[
        str,
        typer.Option("--format", "-f", help=HELP.options.format_type),
    ] = DEFAULT_TABLE_FORMAT,
    json_output: Annotated[
        bool,
        typer.Option("--json", help=HELP.options.json_output),
    ] = False,
) -> None:
    """Ingest a SARIF document from any tool and report it in the unified taxonomy."""
    policy = _load_policy_or_exit(suppress)
    try:
        findings = read_sarif(document)
    except SarifError as exc:
        print_error(str(exc))
        raise typer.Exit(2) from exc

    report = report_from_findings(findings, str(document), policy=policy, min_severity=min_severity)

    resolved = resolve_format(output_format, json_output=json_output)
    if resolved != CONST_OUTPUT_FORMAT_TABLE:
        emit_serialized(report.as_dict(), resolved)
    else:
        _render_report_table(report)
        _warn_expired(report)
        if show_suppressed:
            _render_suppressed(report)

    if fail_on and report.exceeds(fail_on):
        raise typer.Exit(1)
