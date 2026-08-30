"""Runtime and subprocess execution helpers for Kubernetes commands."""

from __future__ import annotations

import subprocess
from typing import Any

import typer

from devops_cli.config.defaults import DEFAULT_SUBPROCESS_TIMEOUT_SECONDS
from devops_cli.core.validation import validate_k8s_name
from devops_cli.output import print_error


def _validate_k8s_identifier(val: str, label: str, *, namespace: bool = False) -> None:
    validate_k8s_name(val, label, namespace=namespace)


def _k8s_clients() -> tuple[Any, Any]:
    try:
        from kubernetes import client as k8s_client  # type: ignore[import-untyped]
        from kubernetes import config as k8s_config

        return k8s_config, k8s_client
    except ImportError:
        print_error("kubernetes package not installed. Run: pip install kubernetes", prefix=False)
        raise typer.Exit(1)


def _run_cmd(
    cmd: list[str],
    *,
    input: str | None = None,
    check: bool = True,
    capture: bool = False,
    timeout: float = DEFAULT_SUBPROCESS_TIMEOUT_SECONDS,
) -> subprocess.CompletedProcess[str]:
    import devops_cli.commands.k8s as k8s

    return k8s.run_subprocess(
        cmd,
        input=input,
        check=check,
        capture_output=capture,
        text=True,
        timeout=timeout,
    )


def _minikube_running() -> bool:
    import devops_cli.commands.k8s as k8s

    try:
        result = k8s._run_cmd(
            ["minikube", "status", "--format", "{{.Host}}"], check=False, capture=True
        )
        return result.returncode == 0 and "Running" in result.stdout
    except FileNotFoundError, OSError, subprocess.SubprocessError:
        return False


def _cluster_reachable(context: str | None = None) -> bool:
    """Return True if the target Kubernetes cluster (or Minikube) is reachable."""
    import devops_cli.commands.k8s as k8s

    cmd = ["kubectl", "cluster-info", "--request-timeout=5s"]
    if context:
        cmd.extend(["--context", context])
    try:
        res = k8s._run_cmd(cmd, check=False, capture=True)
        if res.returncode == 0:
            return True
    except FileNotFoundError, OSError, subprocess.SubprocessError:
        pass

    if not context or context == "minikube":
        return k8s._minikube_running()
    return False
