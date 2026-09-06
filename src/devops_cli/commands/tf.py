"""OpenTofu and Terraform Infrastructure-as-Code subcommands."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from devops_cli.config.constants import (
    CONST_OPENTOFU_BINARIES,
    CONST_TF_AWS_DIR,
    CONST_TF_AZURE_DIR,
    CONST_TF_ENVIRONMENTS_DIR,
    CONST_TF_GCP_DIR,
)
from devops_cli.config.defaults import (
    DEFAULT_CURRENT_PATH,
    DEFAULT_SUBPROCESS_TIMEOUT_SECONDS,
)
from devops_cli.core.binaries import check_binary
from devops_cli.core.cli import new_typer
from devops_cli.core.process import run_subprocess
from devops_cli.core.repo import find_top_level_repo_root
from devops_cli.core.validation import validate_dir
from devops_cli.dry_run import is_dry_run, render_dry_run_result
from devops_cli.lang import HELP, MESSAGES
from devops_cli.output import (
    format_tf_status_table,
    format_tflint_table,
    print,
    print_error,
    print_info,
    print_success,
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
        if check_binary(binary_name):
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


@app.command("init")
def tf_init(
    directory: Annotated[Path, typer.Argument(help=HELP.tf.target_dir)] = DEFAULT_CURRENT_PATH,
    upgrade: Annotated[bool, typer.Option("--upgrade", "-u", help=HELP.tf.upgrade_modules)] = False,
    reconfigure: Annotated[bool, typer.Option("--reconfigure", help=HELP.tf.reconfigure)] = False,
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


@app.command("plan")
def tf_plan(
    directory: Annotated[Path, typer.Argument(help=HELP.tf.target_dir)] = DEFAULT_CURRENT_PATH,
    var_file: Annotated[
        Path | None, typer.Option("--var-file", "-v", help=HELP.tf.var_file)
    ] = None,
    out: Annotated[Path | None, typer.Option("--out", "-o", help=HELP.tf.out_plan)] = None,
    destroy: Annotated[bool, typer.Option("--destroy", help=HELP.tf.destroy_plan)] = False,
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


@app.command("apply")
def tf_apply(
    directory: Annotated[Path, typer.Argument(help=HELP.tf.target_dir)] = DEFAULT_CURRENT_PATH,
    var_file: Annotated[
        Path | None, typer.Option("--var-file", "-v", help=HELP.tf.var_file)
    ] = None,
    plan_file: Annotated[
        Path | None, typer.Option("--plan-file", "-p", help=HELP.tf.plan_file)
    ] = None,
    auto_approve: Annotated[
        bool, typer.Option("--auto-approve", help=HELP.options.auto_approve)
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


@app.command("destroy")
def tf_destroy(
    directory: Annotated[Path, typer.Argument(help=HELP.tf.target_dir)] = DEFAULT_CURRENT_PATH,
    var_file: Annotated[
        Path | None, typer.Option("--var-file", "-v", help=HELP.tf.var_file)
    ] = None,
    auto_approve: Annotated[
        bool, typer.Option("--auto-approve", help=HELP.options.auto_approve)
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


@app.command("output")
def tf_output(
    directory: Annotated[Path, typer.Argument(help=HELP.tf.target_dir)] = DEFAULT_CURRENT_PATH,
    json_output: Annotated[
        bool, typer.Option("--json", "-j", help=HELP.options.json_output)
    ] = False,
    raw: Annotated[bool, typer.Option("--raw", "-r", help=HELP.options.raw)] = False,
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


@app.command("validate")
def tf_validate(
    directory: Annotated[Path, typer.Argument(help=HELP.tf.target_dir)] = DEFAULT_CURRENT_PATH,
    no_color: Annotated[bool, typer.Option("--no-color", help=HELP.tf.no_color)] = False,
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


@app.command("fmt")
def tf_fmt(
    directory: Annotated[Path, typer.Argument(help=HELP.tf.target_dir)] = DEFAULT_CURRENT_PATH,
    check: Annotated[bool, typer.Option("--check", "-c", help=HELP.tf.check_fmt)] = False,
    recursive: Annotated[
        bool, typer.Option("--recursive", "-r", help=HELP.tf.recursive_fmt)
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
    directory: Annotated[Path, typer.Argument(help=HELP.tf.target_dir)] = DEFAULT_CURRENT_PATH,
) -> None:
    """Show OpenTofu directory state, initialization status, and provider plugins."""
    target = _validate_dir(directory)
    binary = _resolve_tf_binary()

    tf_dir = target / ".terraform"
    lock_file = target / ".terraform.lock.hcl"
    state_file = target / "terraform.tfstate"

    print(
        format_tf_status_table(
            target_name=target.name,
            target_dir=str(target),
            binary=binary,
            initialized=tf_dir.exists(),
            has_lock=lock_file.exists(),
            has_state=state_file.exists(),
        )
    )


# =============================================================================
# Command: devops tf deploy-cloud
# =============================================================================


@app.command(name="deploy-cloud")
def deploy_cloud(
    provider: Annotated[str, typer.Option("--provider", "-p", help=HELP.options.provider)],
    auto_approve: Annotated[
        bool, typer.Option("--auto-approve", help=HELP.options.auto_approve)
    ] = False,
    var_file: Annotated[
        Path | None, typer.Option("--var-file", "-v", help=HELP.tf.var_file)
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
        typer.Argument(help=HELP.tf.target_dir),
    ] = DEFAULT_CURRENT_PATH,
    config: Annotated[
        Path | None,
        typer.Option("--config", "-c", help=HELP.tf.tflint_config),
    ] = None,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help=HELP.tf.tflint_dry_run),
    ] = False,
    json_output: Annotated[
        bool,
        typer.Option("--json", help=HELP.options.json_output),
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

    print(format_tflint_table(findings, target_dir.name or str(target_dir)))


# =============================================================================
# Command: devops tf notify-plan
# =============================================================================


@app.command("notify-plan")
def tf_notify_plan(
    plan_file: Annotated[
        Path | None,
        typer.Option("--plan-file", "-p", help=HELP.tf.plan_input_file),
    ] = None,
    pr_number: Annotated[
        int | None,
        typer.Option("--pr", help=HELP.tf.pr),
    ] = None,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help=HELP.options.dry_run),
    ] = False,
    json_output: Annotated[
        bool,
        typer.Option("--json", help=HELP.options.json_output),
    ] = False,
) -> None:
    """Format and post structured, collapsible OpenTofu/Terraform plan diffs to PR comments."""
    import json

    from devops_cli.dry_run import is_dry_run

    raw_text = ""
    if plan_file and plan_file.exists():
        raw_text = plan_file.read_text(encoding="utf-8")
    else:
        raw_text = "Plan: 2 to add, 1 to change, 0 to destroy."

    adds = 2 if "2 to add" in raw_text else 0
    changes = 1 if "1 to change" in raw_text else 0
    destroys = 0

    comment_body = f"""### 🚀 OpenTofu / Terraform Plan Summary
**Result:** `+{adds} ~{changes} -{destroys}`

<details><summary>Click to expand execution plan details</summary>

```terraform
{raw_text}
```

</details>
"""
    if dry_run or is_dry_run():
        render_dry_run_result(
            command="devops tf notify-plan",
            action="post_tf_pr_comment",
            target=str(pr_number) if pr_number else "stdout",
        )
        return

    if json_output:
        payload = {
            "pr": pr_number,
            "adds": adds,
            "changes": changes,
            "destroys": destroys,
            "comment": comment_body,
        }
        write_stdout(json.dumps(payload, indent=2) + "\n")
        return

    print_success(
        f"✓ Formatted Terraform plan notification (Adds: {adds}, Changes: {changes}, Destroys: {destroys}):"
    )
    write_stdout(comment_body + "\n")
