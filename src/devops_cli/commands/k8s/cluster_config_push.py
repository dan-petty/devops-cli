"""`devops k8s push-config`: write the devops-cli-config ConfigMap from active configuration.

Render and apply the in-cluster devops-cli-config ConfigMap from active configuration
(e.g. `service.repos`, `service.machine_account`, or `k8s.github_account`) without modifying git.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

import devops_cli.commands.k8s.cluster_runtime as runtime
from devops_cli.config.defaults import DEFAULT_K8S_DIR
from devops_cli.dry_run import is_dry_run, render_dry_run_result
from devops_cli.k8s.configmap import push_devops_configmap
from devops_cli.lang import HELP, MESSAGES
from devops_cli.output import print_error, print_info, print_success, print_warning


def _restart_roadmap_service(effective_context: str | None) -> None:
    """Trigger rollout restart for roadmap-service deployment."""
    cmd = ["kubectl", "rollout", "restart", "deployment/roadmap-service", "-n", "devops"]
    if effective_context:
        cmd.extend(["--context", effective_context])
    res = runtime._run_cmd(cmd, check=False, capture=True)
    if res.returncode == 0:
        print_success("Restarted deployment/roadmap-service in namespace devops")
    else:
        err = (res.stderr or res.stdout or "").strip()
        print_warning(f"Failed to restart deployment/roadmap-service: {err}")


def push_config(
    k8s_dir: Annotated[Path, typer.Option("--k8s-dir", help=HELP.k8s.k8s_dir)] = DEFAULT_K8S_DIR,
    context: Annotated[
        str | None, typer.Option("--context", "-c", help=HELP.options.context)
    ] = None,
    restart: Annotated[
        bool,
        typer.Option("--restart/--no-restart", help=HELP.k8s.push_config_restart),
    ] = True,
    dry_run: Annotated[bool, typer.Option("--dry-run", help=HELP.options.dry_run)] = False,
) -> None:
    """Push in-cluster devops-cli-config ConfigMap from active configuration without modifying git."""
    effective_context = runtime.resolve_effective_context(context)
    if effective_context:
        runtime._validate_kubeconfig_context_name(effective_context, "context")

    if dry_run or is_dry_run():
        rendered = push_devops_configmap(
            k8s_dir=k8s_dir,
            context=effective_context,
            dry_run=True,
        )
        render_dry_run_result(
            command="devops k8s push-config",
            target="devops-cli-config",
            action="apply_configmap",
            details={
                "k8s_dir": str(k8s_dir),
                "context": effective_context,
                "restart": restart,
                "rendered_bytes": len(rendered.encode("utf-8")),
            },
        )
        return

    if not runtime._cluster_reachable(context=effective_context):
        print_error(MESSAGES.k8s.cluster_not_reachable, prefix=False)
        raise typer.Exit(1)

    print_info("Pushing devops-cli-config ConfigMap from active configuration...", prefix=False)
    result = push_devops_configmap(
        k8s_dir=k8s_dir,
        context=effective_context,
        dry_run=False,
    )
    print_success(f"ConfigMap updated: {result}")

    if restart:
        _restart_roadmap_service(effective_context)
