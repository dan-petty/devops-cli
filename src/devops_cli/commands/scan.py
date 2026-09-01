"""CLI subcommand for security scanning via Trivy, Semgrep, and Gitleaks."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from devops_cli.ai.review_schema import Finding
from devops_cli.config.defaults import (
    DEFAULT_CURRENT_PATH,
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
    print_error,
    print_muted,
    print_success,
    print_table,
    render_table,
    write_stdout,
)
from devops_cli.security.aibom import generate_aibom
from devops_cli.security.checkov import run_checkov_scan
from devops_cli.security.complexity import run_complexity_scan
from devops_cli.security.gitleaks import run_gitleaks_scan
from devops_cli.security.sbom import generate_cyclonedx_sbom, generate_spdx_sbom
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
    ] = DEFAULT_CURRENT_PATH,
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
    ] = DEFAULT_CURRENT_PATH,
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
    ] = DEFAULT_CURRENT_PATH,
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
    ] = DEFAULT_CURRENT_PATH,
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
    ] = DEFAULT_CURRENT_PATH,
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
    ] = DEFAULT_CURRENT_PATH,
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

    if json_output:
        data = [f.model_dump() for f in findings]
        write_stdout(format_json(data) + "\n")
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


main = scan_trivy
scan_main = scan_trivy
