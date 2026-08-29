"""Bootstrap Minikube Kubernetes cluster with GPU acceleration and deploy stacks."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

import devops_cli.commands.k8s as k8s
from devops_cli.config.defaults import (
    DEFAULT_K8S_ALL_STACK,
    DEFAULT_K8S_DIR,
)
from devops_cli.dry_run import is_dry_run, render_dry_run_result
from devops_cli.lang import MESSAGES
from devops_cli.output import (
    print_error,
    print_info,
)


def bootstrap(
    k8s_dir: Annotated[
        Path, typer.Option("--dir", "-d", help="Directory containing Kubernetes manifests")
    ] = DEFAULT_K8S_DIR,
    auto_start: Annotated[
        bool, typer.Option("--auto-start/--no-auto-start", help="Auto-start minikube if stopped")
    ] = True,
    stack: Annotated[
        str,
        typer.Option("--stack", "-s", help="Stack to deploy after bootstrap: infra | llm | all"),
    ] = DEFAULT_K8S_ALL_STACK,
) -> None:
    """Bootstrap minikube Kubernetes cluster and deploy infrastructure/LLM stack."""
    selected_stacks = k8s._resolve_stacks(stack)
    if is_dry_run():
        render_dry_run_result(
            command="devops k8s bootstrap",
            target=str(k8s_dir),
            action="minikube_bootstrap",
            details={
                "auto_start": auto_start,
                "k8s_dir": str(k8s_dir),
                "stack": stack,
                "stacks": selected_stacks,
            },
        )
        return

    if not k8s._minikube_running():
        if auto_start:
            print_info(MESSAGES.k8s.starting_minikube, prefix=False)
            has_gpu = k8s.shutil.which("nvidia-smi") is not None
            started = False
            if has_gpu:
                start_res = k8s._run_cmd(
                    ["minikube", "start", "--driver=docker", "--gpus=all"], check=False
                )
                started = start_res.returncode == 0 and k8s._minikube_running()
            if not started:
                start_res = k8s._run_cmd(["minikube", "start", "--driver=docker"], check=False)
                started = start_res.returncode == 0 and k8s._minikube_running()
            if not started:
                print_error(MESSAGES.k8s.failed_start_minikube, prefix=False)
                raise typer.Exit(1)
            k8s._run_cmd(["minikube", "update-context"], check=False)
        else:
            print_error(
                MESSAGES.k8s.minikube_not_running,
                prefix=False,
            )
            raise typer.Exit(1)
    else:
        k8s._run_cmd(["minikube", "update-context"], check=False)

    k8s.deploy_stack(k8s_dir=k8s_dir, stack=stack)
