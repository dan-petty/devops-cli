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
from devops_cli.core.binaries import check_binary
from devops_cli.dry_run import dry_run_command
from devops_cli.lang import HELP, MESSAGES
from devops_cli.output import (
    print_error,
    print_info,
)


@dry_run_command(
    command="devops k8s bootstrap",
    action="minikube_bootstrap",
    target_param="k8s_dir",
    detail_params=["auto_start", "k8s_dir", "stack"],
)
def bootstrap(
    k8s_dir: Annotated[
        Path, typer.Option("--dir", "-d", help=HELP.k8s.manifests_dir)
    ] = DEFAULT_K8S_DIR,
    auto_start: Annotated[
        bool, typer.Option("--auto-start/--no-auto-start", help=HELP.k8s.auto_start)
    ] = True,
    stack: Annotated[
        str,
        typer.Option("--stack", "-s", help=HELP.k8s.stack),
    ] = DEFAULT_K8S_ALL_STACK,
) -> None:
    """Bootstrap minikube Kubernetes cluster and deploy infrastructure/LLM stack."""
    if not k8s._minikube_running():
        if auto_start:
            print_info(MESSAGES.k8s.starting_minikube, prefix=False)
            has_gpu = check_binary("nvidia-smi")
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
