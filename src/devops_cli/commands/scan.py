"""CLI subcommand for security scanning via Trivy, Semgrep, and Gitleaks."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from devops_cli.ai.review_schema import Finding
from devops_cli.config.defaults import (
    DEFAULT_SEMGREP_CONFIG,
    DEFAULT_TRIVY_SCAN_TYPE,
    DEFAULT_TRIVY_SEVERITIES,
)
from devops_cli.core.cli import new_typer
from devops_cli.dry_run.models import CommandDryRunResult
from devops_cli.dry_run.state import is_dry_run, set_dry_run
from devops_cli.lang import HELP, MESSAGES
from devops_cli.output import (
    format_json,
    print_muted,
    print_success,
    print_table,
    render_table,
    write_stdout,
)
from devops_cli.security.checkov import run_checkov_scan
from devops_cli.security.gitleaks import run_gitleaks_scan
from devops_cli.security.semgrep import run_semgrep_scan
from devops_cli.security.trivy import run_trivy_scan

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
        scan_trivy(target=Path("."), dry_run=dry_run, json_output=json_output)


# =============================================================================
# Command: devops scan trivy
# =============================================================================


@app.command("trivy")
def scan_trivy(
    target: Annotated[
        Path,
        typer.Argument(help=HELP.scan.target),
    ] = Path("."),
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

    if json_output:
        data = [f.model_dump() for f in findings]
        write_stdout(format_json(data) + "\n")
        if is_dry_run():
            return CommandDryRunResult(
                command=f"devops scan trivy {target} --type {scan_type}",
                target=str(target_abs),
                action="trivy_security_scan",
                details={"scan_type": scan_type, "findings_count": len(findings)},
            )
        return None

    if not findings:
        print_success(MESSAGES.scan.no_flaws_found)
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
    ] = Path("."),
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help=HELP.options.dry_run),
    ] = False,
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

    if json_output:
        data = [f.model_dump() for f in findings]
        write_stdout(format_json(data) + "\n")
        if is_dry_run():
            return CommandDryRunResult(
                command=f"devops scan secrets {target}",
                target=str(target_abs),
                action="gitleaks_secret_scan",
                details={"findings_count": len(findings)},
            )
        return None

    if not findings:
        print_success(MESSAGES.scan.gitleaks_passed)
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


@app.command("gitleaks")
def scan_gitleaks_cmd(
    target: Annotated[
        Path,
        typer.Argument(help=HELP.scan.target_secrets),
    ] = Path("."),
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help=HELP.options.dry_run),
    ] = False,
    json_output: Annotated[
        bool,
        typer.Option("--json", help=HELP.options.json_output),
    ] = False,
) -> CommandDryRunResult | None:
    """Alias for devops scan secrets."""
    return scan_secrets(target=target, dry_run=dry_run, json_output=json_output)


# =============================================================================
# Command: devops scan semgrep / devops scan sast
# =============================================================================


@app.command("semgrep")
def scan_semgrep_cmd(
    target: Annotated[
        Path,
        typer.Argument(help=HELP.scan.target_semgrep),
    ] = Path("."),
    config: Annotated[
        str,
        typer.Option("--config", "-c", help=HELP.scan.semgrep_config),
    ] = DEFAULT_SEMGREP_CONFIG,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help=HELP.options.dry_run),
    ] = False,
    json_output: Annotated[
        bool,
        typer.Option("--json", help=HELP.options.json_output),
    ] = False,
) -> CommandDryRunResult | None:
    """Run Semgrep multilingual static AST pattern matching scan."""
    return scan_sast(target=target, config=config, dry_run=dry_run, json_output=json_output)


@app.command("sast")
def scan_sast(
    target: Annotated[
        Path,
        typer.Argument(help=HELP.scan.target_semgrep),
    ] = Path("."),
    config: Annotated[
        str,
        typer.Option("--config", "-c", help=HELP.scan.semgrep_config),
    ] = DEFAULT_SEMGREP_CONFIG,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help=HELP.options.dry_run),
    ] = False,
    json_output: Annotated[
        bool,
        typer.Option("--json", help=HELP.options.json_output),
    ] = False,
) -> CommandDryRunResult | None:
    """Run static application security testing (SAST) via Semgrep."""
    set_dry_run(dry_run)
    target_abs = target.resolve() if target.exists() else target

    if not is_dry_run():
        print_muted(MESSAGES.scan.semgrep_executing.format(target=target_abs, config=config))

    findings = run_semgrep_scan(target=target_abs, config=config)

    if json_output:
        data = [f.model_dump() for f in findings]
        write_stdout(format_json(data) + "\n")
        if is_dry_run():
            return CommandDryRunResult(
                command=f"devops scan sast {target} --config {config}",
                target=str(target_abs),
                action="semgrep_ast_scan",
                details={"config": config, "findings_count": len(findings)},
            )
        return None

    if not findings:
        print_success(MESSAGES.scan.semgrep_passed)
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


@app.command("checkov")
def scan_checkov(
    target: Annotated[
        Path,
        typer.Argument(help=HELP.scan.target_checkov),
    ] = Path("."),
    framework: Annotated[
        str | None,
        typer.Option("--framework", "-f", help=HELP.scan.framework),
    ] = None,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help=HELP.options.dry_run),
    ] = False,
    json_output: Annotated[
        bool,
        typer.Option("--json", help=HELP.options.json_output),
    ] = False,
) -> CommandDryRunResult | None:
    """Run Checkov Infrastructure-as-Code (IaC) compliance scanner."""
    return scan_iac(target=target, framework=framework, dry_run=dry_run, json_output=json_output)


@app.command("iac")
def scan_iac(
    target: Annotated[
        Path,
        typer.Argument(help=HELP.scan.target_checkov),
    ] = Path("."),
    framework: Annotated[
        str | None,
        typer.Option("--framework", "-f", help=HELP.scan.framework),
    ] = None,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help=HELP.options.dry_run),
    ] = False,
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

    if json_output:
        data = [f.model_dump() for f in findings]
        write_stdout(format_json(data) + "\n")
        if is_dry_run():
            return CommandDryRunResult(
                command=f"devops scan iac {target}",
                target=str(target_abs),
                action="checkov_iac_scan",
                details={"framework": framework, "findings_count": len(findings)},
            )
        return None

    if not findings:
        print_success(MESSAGES.scan.checkov_passed)
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


main = scan_trivy
scan_main = scan_trivy
