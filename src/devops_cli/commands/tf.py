"""OpenTofu and Terraform Infrastructure-as-Code subcommands."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Annotated

import typer
from rich.table import Table

from devops_cli.config.constants import (
    CONST_OPENTOFU_BINARIES,
    CONST_TF_AWS_DIR,
    CONST_TF_AZURE_DIR,
    CONST_TF_ENVIRONMENTS_DIR,
    CONST_TF_GCP_DIR,
)
from devops_cli.config.defaults import DEFAULT_SUBPROCESS_TIMEOUT_SECONDS
from devops_cli.core.cli import new_typer
from devops_cli.core.process import run_subprocess
from devops_cli.core.repo import find_top_level_repo_root
from devops_cli.core.validation import validate_dir
from devops_cli.dry_run import is_dry_run, render_dry_run_result
from devops_cli.lang import HELP, MESSAGES
from devops_cli.output import (
    print_error,
    print_info,
    print_success,
    print_table,
    write_stdout,
)

app = new_typer(
    help=HELP.tf.app,
    no_args_is_help=True,
)


# =============================================================================
# OpenTofu / Terraform Binary & Path Helpers
# =============================================================================


def _resolve_tf_binary() -> str:
    """Find available OpenTofu or Terraform executable in PATH."""
    for binary_name in CONST_OPENTOFU_BINARIES:
        if shutil.which(binary_name):
            return binary_name

    if is_dry_run():
        return "tofu"

    print_error(MESSAGES.tf.binary_not_found, prefix=False)
    raise typer.Exit(1)


def _validate_dir(path: Path) -> Path:
    """Ensure the target directory exists and is a directory."""
    return validate_dir(path, must_exist=True)


def _get_cloud_dir(cloud_provider: str, repo_root: Path) -> Path:
    """Resolve directory path for a supported cloud provider."""
    provider_map = {
        "aws": repo_root / CONST_TF_AWS_DIR,
        "azure": repo_root / CONST_TF_AZURE_DIR,
        "gcp": repo_root / CONST_TF_GCP_DIR,
    }
    key = cloud_provider.lower()
    if key not in provider_map:
        print_error(
            f"Unsupported cloud provider '{cloud_provider}'. Supported providers: aws, azure, gcp",
            prefix=False,
        )
        raise typer.Exit(1)
    return provider_map[key]


def _get_default_var_file(cloud_provider: str, repo_root: Path) -> Path | None:
    """Find default example tfvars file for a cloud provider."""
    key = cloud_provider.lower()
    candidate = repo_root / CONST_TF_ENVIRONMENTS_DIR / f"{key}.tfvars.example"
    return candidate if candidate.exists() else None


# =============================================================================
# Command: devops tf init
# =============================================================================


@app.command()
def init(
    directory: Annotated[
        Path, typer.Argument(help="Target directory containing OpenTofu configuration")
    ] = Path("."),
    upgrade: Annotated[
        bool, typer.Option("--upgrade", "-u", help="Upgrade modules and plugins")
    ] = False,
    reconfigure: Annotated[
        bool, typer.Option("--reconfigure", help="Reconfigure backend, ignoring existing state")
    ] = False,
) -> None:
    """Initialize an OpenTofu working directory."""
    target = _validate_dir(directory)
    binary = _resolve_tf_binary()

    cmd = [binary, "init"]
    if upgrade:
        cmd.append("-upgrade")
    if reconfigure:
        cmd.append("-reconfigure")

    print_info(MESSAGES.tf.init_header.format(path=str(target)), prefix=False)
    if is_dry_run():
        render_dry_run_result(
            command=" ".join(cmd),
            action="init",
            target=str(target),
        )
        return

    result = run_subprocess(
        cmd,
        cwd=target,
        check=True,
        timeout=DEFAULT_SUBPROCESS_TIMEOUT_SECONDS,
    )
    if result.returncode == 0:
        print_success(MESSAGES.tf.init_success)


# =============================================================================
# Command: devops tf plan
# =============================================================================


@app.command()
def plan(
    directory: Annotated[
        Path, typer.Argument(help="Target directory containing OpenTofu configuration")
    ] = Path("."),
    var_file: Annotated[
        Path | None, typer.Option("--var-file", "-v", help="Path to variable definitions file")
    ] = None,
    out: Annotated[
        Path | None, typer.Option("--out", "-o", help="Write generated plan to file")
    ] = None,
    destroy: Annotated[
        bool, typer.Option("--destroy", help="Generate a plan to destroy all resources")
    ] = False,
) -> None:
    """Generate and show an OpenTofu execution plan."""
    target = _validate_dir(directory)
    binary = _resolve_tf_binary()

    cmd = [binary, "plan"]
    if var_file:
        cmd.extend(["-var-file", str(var_file.resolve())])
    if out:
        cmd.extend(["-out", str(out.resolve())])
    if destroy:
        cmd.append("-destroy")

    print_info(MESSAGES.tf.plan_header.format(path=str(target)), prefix=False)
    if is_dry_run():
        render_dry_run_result(
            command=" ".join(cmd),
            action="plan",
            target=str(target),
        )
        return

    result = run_subprocess(
        cmd,
        cwd=target,
        check=True,
        timeout=DEFAULT_SUBPROCESS_TIMEOUT_SECONDS,
    )
    if result.returncode == 0:
        print_success(MESSAGES.tf.plan_success)


# =============================================================================
# Command: devops tf apply
# =============================================================================


@app.command()
def apply(
    directory: Annotated[
        Path, typer.Argument(help="Target directory containing OpenTofu configuration")
    ] = Path("."),
    var_file: Annotated[
        Path | None, typer.Option("--var-file", "-v", help="Path to variable definitions file")
    ] = None,
    plan_file: Annotated[
        Path | None, typer.Option("--plan-file", "-p", help="Explicit plan file to apply")
    ] = None,
    auto_approve: Annotated[
        bool, typer.Option("--auto-approve", help="Skip interactive approval before applying")
    ] = False,
) -> None:
    """Create or update OpenTofu infrastructure."""
    target = _validate_dir(directory)
    binary = _resolve_tf_binary()

    cmd = [binary, "apply"]
    if plan_file:
        cmd.append(str(plan_file.resolve()))
    else:
        if var_file:
            cmd.extend(["-var-file", str(var_file.resolve())])
        if auto_approve:
            cmd.append("-auto-approve")

    print_info(MESSAGES.tf.apply_header.format(path=str(target)), prefix=False)
    if is_dry_run():
        render_dry_run_result(
            command=" ".join(cmd),
            action="apply",
            target=str(target),
        )
        return

    result = run_subprocess(
        cmd,
        cwd=target,
        check=True,
        timeout=DEFAULT_SUBPROCESS_TIMEOUT_SECONDS,
    )
    if result.returncode == 0:
        print_success(MESSAGES.tf.apply_success)


# =============================================================================
# Command: devops tf destroy
# =============================================================================


@app.command()
def destroy(
    directory: Annotated[
        Path, typer.Argument(help="Target directory containing OpenTofu configuration")
    ] = Path("."),
    var_file: Annotated[
        Path | None, typer.Option("--var-file", "-v", help="Path to variable definitions file")
    ] = None,
    auto_approve: Annotated[
        bool, typer.Option("--auto-approve", help="Skip interactive approval before destroying")
    ] = False,
) -> None:
    """Destroy OpenTofu-managed infrastructure."""
    target = _validate_dir(directory)
    binary = _resolve_tf_binary()

    cmd = [binary, "destroy"]
    if var_file:
        cmd.extend(["-var-file", str(var_file.resolve())])
    if auto_approve:
        cmd.append("-auto-approve")

    print_info(MESSAGES.tf.destroy_header.format(path=str(target)), prefix=False)
    if is_dry_run():
        render_dry_run_result(
            command=" ".join(cmd),
            action="destroy",
            target=str(target),
        )
        return

    result = run_subprocess(
        cmd,
        cwd=target,
        check=True,
        timeout=DEFAULT_SUBPROCESS_TIMEOUT_SECONDS,
    )
    if result.returncode == 0:
        print_success(MESSAGES.tf.destroy_success)


# =============================================================================
# Command: devops tf output
# =============================================================================


@app.command()
def output(
    directory: Annotated[
        Path, typer.Argument(help="Target directory containing OpenTofu configuration")
    ] = Path("."),
    json_output: Annotated[
        bool, typer.Option("--json", "-j", help="Output values formatted as JSON")
    ] = False,
    raw: Annotated[
        bool, typer.Option("--raw", "-r", help="Output raw string without shell escapes")
    ] = False,
) -> None:
    """Read an output variable from the OpenTofu state."""
    target = _validate_dir(directory)
    binary = _resolve_tf_binary()

    cmd = [binary, "output"]
    if json_output:
        cmd.append("-json")
    elif raw:
        cmd.append("-raw")

    if is_dry_run():
        render_dry_run_result(
            command=" ".join(cmd),
            action="output",
            target=str(target),
        )
        return

    result = run_subprocess(
        cmd,
        cwd=target,
        check=True,
        capture_output=True,
        text=True,
        timeout=DEFAULT_SUBPROCESS_TIMEOUT_SECONDS,
    )
    write_stdout(result.stdout)


# =============================================================================
# Command: devops tf validate
# =============================================================================


@app.command()
def validate(
    directory: Annotated[
        Path, typer.Argument(help="Target directory containing OpenTofu configuration")
    ] = Path("."),
    no_color: Annotated[bool, typer.Option("--no-color", help="Disable color codes")] = False,
) -> None:
    """Validate the OpenTofu configuration files in a directory."""
    target = _validate_dir(directory)
    binary = _resolve_tf_binary()

    cmd = [binary, "validate"]
    if no_color:
        cmd.append("-no-color")

    print_info(MESSAGES.tf.validate_header.format(path=str(target)), prefix=False)
    if is_dry_run():
        render_dry_run_result(
            command=" ".join(cmd),
            action="validate",
            target=str(target),
        )
        return

    result = run_subprocess(
        cmd,
        cwd=target,
        check=True,
        timeout=DEFAULT_SUBPROCESS_TIMEOUT_SECONDS,
    )
    if result.returncode == 0:
        print_success(MESSAGES.tf.validate_success)


# =============================================================================
# Command: devops tf fmt
# =============================================================================


@app.command()
def fmt(
    directory: Annotated[
        Path, typer.Argument(help="Target directory containing OpenTofu configuration")
    ] = Path("."),
    check: Annotated[
        bool, typer.Option("--check", "-c", help="Check formatting without writing files")
    ] = False,
    recursive: Annotated[
        bool, typer.Option("--recursive", "-r", help="Format subdirectories recursively")
    ] = True,
) -> None:
    """Rewrites OpenTofu configuration files to canonical format."""
    target = _validate_dir(directory)
    binary = _resolve_tf_binary()

    cmd = [binary, "fmt"]
    if check:
        cmd.append("-check")
    if recursive:
        cmd.append("-recursive")

    print_info(MESSAGES.tf.fmt_header.format(path=str(target)), prefix=False)
    if is_dry_run():
        render_dry_run_result(
            command=" ".join(cmd),
            action="fmt",
            target=str(target),
        )
        return

    result = run_subprocess(
        cmd,
        cwd=target,
        check=True,
        timeout=DEFAULT_SUBPROCESS_TIMEOUT_SECONDS,
    )
    if result.returncode == 0:
        print_success(MESSAGES.tf.fmt_success)


# =============================================================================
# Command: devops tf status
# =============================================================================


@app.command(name="status")
def status_command(
    directory: Annotated[
        Path, typer.Argument(help="Target directory containing OpenTofu configuration")
    ] = Path("."),
) -> None:
    """Show OpenTofu directory state, initialization status, and provider plugins."""
    target = _validate_dir(directory)
    binary = _resolve_tf_binary()

    tf_dir = target / ".terraform"
    lock_file = target / ".terraform.lock.hcl"
    state_file = target / "terraform.tfstate"

    table = Table(
        title=f"OpenTofu Status — {target.name}",
        border_style="cyan",
        header_style="bold magenta",
    )
    table.add_column("Property", style="bold white")
    table.add_column("Status / Value", style="green")

    table.add_row("Directory", str(target))
    table.add_row("Resolved Binary", binary)
    table.add_row("Initialized (.terraform)", "✓ Yes" if tf_dir.exists() else "[red]✗ No[/red]")
    table.add_row("Lock File (.lock.hcl)", "✓ Yes" if lock_file.exists() else "[dim]None[/dim]")
    table.add_row("Local State File", "✓ Yes" if state_file.exists() else "[dim]None[/dim]")

    print_table(table)


# =============================================================================
# Command: devops tf deploy-cloud
# =============================================================================


@app.command(name="deploy-cloud")
def deploy_cloud(
    provider: Annotated[
        str, typer.Option("--provider", "-p", help="Target cloud provider: aws, azure, or gcp")
    ],
    auto_approve: Annotated[
        bool, typer.Option("--auto-approve", help="Automatically approve apply without prompt")
    ] = False,
    var_file: Annotated[
        Path | None, typer.Option("--var-file", "-v", help="Path to custom tfvars file")
    ] = None,
) -> None:
    """Deploy cloud Kubernetes infrastructure for AWS, Azure, or GCP."""
    repo_root = find_top_level_repo_root(Path.cwd())
    cloud_dir = _get_cloud_dir(provider, repo_root)
    resolved_var_file = var_file or _get_default_var_file(provider, repo_root)
    binary = _resolve_tf_binary()

    print_info(
        MESSAGES.tf.deploy_cloud_header.format(provider=provider.upper(), path=str(cloud_dir)),
        prefix=False,
    )

    # Step 1: Init
    init_cmd = [binary, "init"]
    if is_dry_run():
        render_dry_run_result(
            command=" ".join(init_cmd),
            action="init",
            target=str(cloud_dir),
        )
    else:
        run_subprocess(
            init_cmd,
            cwd=cloud_dir,
            check=True,
            timeout=DEFAULT_SUBPROCESS_TIMEOUT_SECONDS,
        )

    # Step 2: Apply
    apply_cmd = [binary, "apply"]
    if resolved_var_file and resolved_var_file.exists():
        apply_cmd.extend(["-var-file", str(resolved_var_file.resolve())])
    if auto_approve:
        apply_cmd.append("-auto-approve")

    if is_dry_run():
        render_dry_run_result(
            command=" ".join(apply_cmd),
            action="apply",
            target=str(cloud_dir),
        )
        return

    run_subprocess(
        apply_cmd,
        cwd=cloud_dir,
        check=True,
        timeout=DEFAULT_SUBPROCESS_TIMEOUT_SECONDS,
    )
    msg = MESSAGES.tf.deploy_cloud_success.format(provider=provider.upper())
    print_success(msg)


@app.command("lint")
def tf_lint(
    directory: Annotated[
        Path,
        typer.Argument(help="Target directory containing Terraform / OpenTofu files"),
    ] = Path("."),
    config: Annotated[
        Path | None,
        typer.Option("--config", "-c", help="Path to .tflint.hcl config file"),
    ] = None,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Simulate TFLint execution"),
    ] = False,
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Output findings as JSON"),
    ] = False,
) -> None:
    """Run TFLint static analysis on Terraform/OpenTofu configurations."""
    from devops_cli.output import format_json, print_muted
    from devops_cli.security.tflint import run_tflint_scan

    target_dir = directory.resolve()
    if dry_run:
        render_dry_run_result(
            command=f"devops tf lint {directory}",
            action="tflint",
            target=str(target_dir),
        )
        return

    print_muted(f"Executing TFLint static analysis on '{target_dir}'...")
    findings = run_tflint_scan(target_dir=target_dir, config_file=config)

    if json_output:
        write_stdout(format_json([f.model_dump() for f in findings]) + "\n")
        return

    if not findings:
        print_success("✓ No Terraform / OpenTofu lint issues detected.")
        return

    table = Table(title=f"TFLint Findings: {target_dir.name or str(target_dir)}")
    table.add_column("Severity", style="bold")
    table.add_column("Location")
    table.add_column("Rule / Title")
    table.add_column("Description")

    for f in findings:
        table.add_row(f.severity, f.location, f.title, f.description)
    print_table(table)
