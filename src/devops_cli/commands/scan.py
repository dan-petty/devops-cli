"""CLI subcommand for security, vulnerability, secret, and IaC scanning via Aqua Trivy."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer
from rich import print as rprint
from rich.console import Console
from rich.table import Table

from devops_cli.config.defaults import DEFAULT_TRIVY_SCAN_TYPE, DEFAULT_TRIVY_SEVERITIES
from devops_cli.dry_run.models import CommandDryRunResult
from devops_cli.dry_run.state import is_dry_run, set_dry_run
from devops_cli.security.trivy import run_trivy_scan

app = typer.Typer(
    name="scan",
    help="Security, vulnerability, secret, and IaC scanner via Aqua Trivy.",
    no_args_is_help=False,
)

console = Console()


@app.callback(invoke_without_command=True)
def main(
    target: Annotated[
        Path,
        typer.Argument(help="Target directory, file, or repository to scan"),
    ] = Path("."),
    scan_type: Annotated[
        str,
        typer.Option("--type", "-t", help="Trivy scan mode: fs, image, iac, repo"),
    ] = DEFAULT_TRIVY_SCAN_TYPE,
    severity: Annotated[
        str,
        typer.Option("--severity", "-s", help="Comma-separated severity levels to include"),
    ] = DEFAULT_TRIVY_SEVERITIES,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Simulate security scan execution."),
    ] = False,
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Output raw findings as JSON"),
    ] = False,
) -> CommandDryRunResult | None:
    """Run Aqua Trivy vulnerability, secret, and misconfiguration scan."""
    set_dry_run(dry_run)
    target_abs = target.resolve() if target.exists() else target

    if not is_dry_run():
        rprint(f"[dim]Executing Trivy security scan on '{target_abs}' (type: {scan_type})...[/dim]")

    findings = run_trivy_scan(target=target_abs, scan_type=scan_type, severity=severity)

    if json_output:
        data = [f.model_dump() for f in findings]
        rprint(json.dumps(data, indent=2))
        if is_dry_run():
            return CommandDryRunResult(
                command=f"devops scan {target} --type {scan_type}",
                target=str(target_abs),
                action="trivy_security_scan",
                details={"scan_type": scan_type, "findings_count": len(findings)},
            )
        return None

    if not findings:
        rprint("[bold green]✓ No security vulnerabilities, secrets, or flaws found.[/bold green]")
        if is_dry_run():
            return CommandDryRunResult(
                command=f"devops scan {target} --type {scan_type}",
                target=str(target_abs),
                action="trivy_security_scan",
                details={"scan_type": scan_type, "findings_count": 0},
            )
        return None

    table = Table(title=f"Security Scan Results: {target_abs.name or target_abs}")
    table.add_column("Severity", style="bold")
    table.add_column("Location")
    table.add_column("Title")
    table.add_column("Suggested Fix")

    sev_colors = {
        "CRITICAL": "bold red",
        "HIGH": "red",
        "MEDIUM": "yellow",
        "LOW": "cyan",
        "INFO": "dim",
    }

    for f in findings:
        style = sev_colors.get(f.severity.upper(), "white")
        table.add_row(
            f"[{style}]{f.severity}[/{style}]",
            f.location,
            f.title,
            f.fix or "-",
        )

    console.print(table)

    if is_dry_run():
        return CommandDryRunResult(
            command=f"devops scan {target} --type {scan_type}",
            target=str(target_abs),
            action="trivy_security_scan",
            details={"scan_type": scan_type, "findings_count": len(findings)},
        )

    return None
