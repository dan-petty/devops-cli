"""Dry-run request plan builders for OpenTofu and Terraform operations.

A dry run makes zero external requests and returns ordered PlannedRequest items.
"""

from __future__ import annotations

from pathlib import Path

from devops_cli.dry_run.requests import PlannedRequest


def build_tf_init_cmd(
    binary: str = "tofu",
    upgrade: bool = False,
    reconfigure: bool = False,
) -> list[str]:
    """Build the command vector for OpenTofu directory initialization."""
    cmd = [binary, "init"]
    if upgrade:
        cmd.append("-upgrade")
    if reconfigure:
        cmd.append("-reconfigure")
    return cmd


def plan_tf_init(
    directory: Path | str,
    upgrade: bool = False,
    reconfigure: bool = False,
    binary: str = "tofu",
) -> list[PlannedRequest]:
    """Plan initialization requests for an OpenTofu working directory."""
    cmd = build_tf_init_cmd(binary=binary, upgrade=upgrade, reconfigure=reconfigure)
    return [
        PlannedRequest(
            method="EXEC",
            target=f"{binary} init",
            argv=tuple(cmd),
        )
    ]


def build_tf_plan_cmd(
    binary: str = "tofu",
    var_file: Path | str | None = None,
    out: Path | str | None = None,
    destroy: bool = False,
) -> list[str]:
    """Build the command vector for generating an OpenTofu execution plan."""
    cmd = [binary, "plan"]
    if var_file:
        vf = Path(var_file)
        resolved = str(vf.resolve()) if vf.is_absolute() or vf.exists() else str(vf)
        cmd.extend(["-var-file", resolved])
    if out:
        of = Path(out)
        resolved = str(of.resolve()) if of.is_absolute() or of.exists() else str(of)
        cmd.extend(["-out", resolved])
    if destroy:
        cmd.append("-destroy")
    return cmd


def plan_tf_plan(
    directory: Path | str,
    var_file: Path | str | None = None,
    out: Path | str | None = None,
    destroy: bool = False,
    binary: str = "tofu",
) -> list[PlannedRequest]:
    """Plan OpenTofu plan generation requests."""
    cmd = build_tf_plan_cmd(binary=binary, var_file=var_file, out=out, destroy=destroy)
    return [
        PlannedRequest(
            method="EXEC",
            target=f"{binary} plan",
            argv=tuple(cmd),
        )
    ]


def build_tf_apply_cmd(
    binary: str = "tofu",
    var_file: Path | str | None = None,
    plan_file: Path | str | None = None,
    auto_approve: bool = False,
) -> list[str]:
    """Build the command vector for applying OpenTofu infrastructure."""
    cmd = [binary, "apply"]
    if plan_file:
        pf = Path(plan_file)
        resolved = str(pf.resolve()) if pf.is_absolute() or pf.exists() else str(pf)
        cmd.append(resolved)
    else:
        if var_file:
            vf = Path(var_file)
            resolved = str(vf.resolve()) if vf.is_absolute() or vf.exists() else str(vf)
            cmd.extend(["-var-file", resolved])
        if auto_approve:
            cmd.append("-auto-approve")
    return cmd


def plan_tf_apply(
    directory: Path | str,
    var_file: Path | str | None = None,
    plan_file: Path | str | None = None,
    auto_approve: bool = False,
    binary: str = "tofu",
) -> list[PlannedRequest]:
    """Plan OpenTofu apply execution requests."""
    cmd = build_tf_apply_cmd(
        binary=binary,
        var_file=var_file,
        plan_file=plan_file,
        auto_approve=auto_approve,
    )
    return [
        PlannedRequest(
            method="EXEC",
            target=f"{binary} apply",
            argv=tuple(cmd),
        )
    ]


def build_tf_destroy_cmd(
    binary: str = "tofu",
    var_file: Path | str | None = None,
    auto_approve: bool = False,
) -> list[str]:
    """Build the command vector for destroying OpenTofu infrastructure."""
    cmd = [binary, "destroy"]
    if var_file:
        vf = Path(var_file)
        resolved = str(vf.resolve()) if vf.is_absolute() or vf.exists() else str(vf)
        cmd.extend(["-var-file", resolved])
    if auto_approve:
        cmd.append("-auto-approve")
    return cmd


def plan_tf_destroy(
    directory: Path | str,
    var_file: Path | str | None = None,
    auto_approve: bool = False,
    binary: str = "tofu",
) -> list[PlannedRequest]:
    """Plan OpenTofu destroy execution requests."""
    cmd = build_tf_destroy_cmd(binary=binary, var_file=var_file, auto_approve=auto_approve)
    return [
        PlannedRequest(
            method="EXEC",
            target=f"{binary} destroy",
            argv=tuple(cmd),
        )
    ]


def build_tf_output_cmd(
    binary: str = "tofu",
    json_mode: bool = False,
    raw: bool = False,
) -> list[str]:
    """Build the command vector for querying OpenTofu outputs."""
    cmd = [binary, "output"]
    if json_mode:
        cmd.append("-json")
    elif raw:
        cmd.append("-raw")
    return cmd


def plan_tf_output(
    directory: Path | str,
    json_mode: bool = False,
    raw: bool = False,
    binary: str = "tofu",
) -> list[PlannedRequest]:
    """Plan OpenTofu output queries."""
    cmd = build_tf_output_cmd(binary=binary, json_mode=json_mode, raw=raw)
    return [
        PlannedRequest(
            method="EXEC",
            target=f"{binary} output",
            argv=tuple(cmd),
        )
    ]


def build_tf_deploy_cloud_cmds(
    binary: str = "tofu",
    resolved_var_file: Path | str | None = None,
    auto_approve: bool = False,
) -> tuple[list[str], list[str]]:
    """Build the command vectors for cloud infrastructure init and apply steps."""
    init_cmd = [binary, "init"]
    apply_cmd = [binary, "apply"]
    if resolved_var_file:
        vf = Path(resolved_var_file)
        resolved = str(vf.resolve()) if vf.is_absolute() or vf.exists() else str(vf)
        apply_cmd.extend(["-var-file", resolved])
    if auto_approve:
        apply_cmd.append("-auto-approve")
    return init_cmd, apply_cmd


def plan_tf_deploy_cloud(
    cloud_dir: Path | str,
    resolved_var_file: Path | str | None = None,
    auto_approve: bool = False,
    binary: str = "tofu",
) -> list[PlannedRequest]:
    """Plan cloud deployment requests spanning init and apply."""
    init_cmd, apply_cmd = build_tf_deploy_cloud_cmds(
        binary=binary,
        resolved_var_file=resolved_var_file,
        auto_approve=auto_approve,
    )
    return [
        PlannedRequest(
            method="EXEC",
            target=f"{binary} init",
            argv=tuple(init_cmd),
        ),
        PlannedRequest(
            method="EXEC",
            target=f"{binary} apply",
            argv=tuple(apply_cmd),
        ),
    ]


def build_infracost_breakdown_cmd(directory: Path | str) -> list[str]:
    """Build the command vector for Infracost breakdown."""
    return ["infracost", "breakdown", "--path", str(directory), "--format", "json"]


def plan_tf_cost_breakdown(directory: Path | str) -> list[PlannedRequest]:
    """Plan Infracost breakdown cost estimation requests."""
    cmd = build_infracost_breakdown_cmd(directory)
    return [
        PlannedRequest(
            method="EXEC",
            target="infracost breakdown",
            argv=tuple(cmd),
        )
    ]


def build_infracost_diff_cmd(
    directory: Path | str,
    compare_to: Path | str | None = None,
) -> list[str]:
    """Build the command vector for Infracost diff."""
    cmd = ["infracost", "diff", "--path", str(directory), "--format", "json"]
    if compare_to:
        cmd.extend(["--compare-to", str(compare_to)])
    return cmd


def plan_tf_cost_diff(
    directory: Path | str,
    compare_to: Path | str | None = None,
) -> list[PlannedRequest]:
    """Plan Infracost diff cost calculation requests."""
    cmd = build_infracost_diff_cmd(directory, compare_to=compare_to)
    return [
        PlannedRequest(
            method="EXEC",
            target="infracost diff",
            argv=tuple(cmd),
        )
    ]


def plan_tf_lint(
    directory: Path | str,
    config: Path | str | None = None,
) -> list[PlannedRequest]:
    """Plan TFLint static analysis requests."""
    from devops_cli.security.tflint import TflintScanner

    scanner = TflintScanner()
    cfg_path = Path(config) if config is not None else None
    cmd = scanner.build_command(Path(directory), config_file=cfg_path)
    return [
        PlannedRequest(
            method="EXEC",
            target="tflint scan",
            argv=tuple(cmd),
        )
    ]
