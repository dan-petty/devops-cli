"""Runtime and subprocess execution helpers for Kubernetes commands."""

from __future__ import annotations

import subprocess
from typing import Any

import typer

from devops_cli.config.defaults import DEFAULT_SUBPROCESS_TIMEOUT_SECONDS
from devops_cli.core.process import run_subprocess as run_subprocess
from devops_cli.core.validation import validate_k8s_name
from devops_cli.output import print_error


def _validate_k8s_identifier(val: str, label: str, *, namespace: bool = False) -> None:
    validate_k8s_name(val, label, namespace=namespace)


def _validate_kubeconfig_context_name(val: str, label: str = "context name") -> None:
    from devops_cli.core.validation import validate_k8s_context_name

    validate_k8s_context_name(val, label=label)


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
    return run_subprocess(
        cmd,
        input=input,
        check=check,
        capture_output=capture,
        text=True,
        timeout=timeout,
    )


def _minikube_running() -> bool:
    try:
        result = _run_cmd(
            ["minikube", "status", "--format", "{{.Host}}"], check=False, capture=True
        )
        return result.returncode == 0 and "Running" in result.stdout
    except FileNotFoundError, OSError, subprocess.SubprocessError:
        return False


def _start_minikube(dry_run: bool = False) -> tuple[bool, str]:
    """Start Minikube cluster with GPU support fallback and context refresh."""
    import shutil

    has_gpu = bool(shutil.which("nvidia-smi"))
    gpu_suffix = " (--driver=docker --gpus=all)" if has_gpu else " (--driver=docker)"
    if dry_run:
        return True, f"Started Minikube cluster{gpu_suffix}"

    if has_gpu:
        start_res = _run_cmd(["minikube", "start", "--driver=docker", "--gpus=all"], check=False)
        if start_res.returncode == 0 and _minikube_running():
            _run_cmd(["minikube", "update-context"], check=False)
            return True, f"Started Minikube cluster{gpu_suffix}"

    fallback_res = _run_cmd(["minikube", "start", "--driver=docker"], check=False)
    if fallback_res.returncode == 0 and _minikube_running():
        _run_cmd(["minikube", "update-context"], check=False)
        return True, "Started Minikube cluster (--driver=docker)"

    return False, "Failed to start Minikube cluster"


def should_autostart_minikube(target_context: str | None = None) -> bool:
    """Determine whether Minikube should autostart based on target context and env overrides."""
    import os

    from devops_cli.config.settings import load_settings

    env_val = os.getenv("DEVOPS_MINIKUBE_AUTOSTART")
    if env_val is None:
        env_val = os.getenv("DEVOPS_K8S_AUTOSTART_MINIKUBE")

    if env_val is not None:
        return env_val.strip().lower() in ("true", "1", "yes", "on")

    effective_ctx = target_context
    if not effective_ctx:
        try:
            effective_ctx = load_settings().k8s.context
        except Exception:
            # If configuration cannot be loaded, fail closed to prevent accidental start
            return False

    return bool(effective_ctx and effective_ctx.strip().lower() == "minikube")


def resolve_effective_context(context: str | None = None) -> str | None:
    """Resolve the effective Kubernetes context from parameter or configuration."""
    if context and context.strip():
        return context.strip()
    try:
        from devops_cli.config.settings import load_settings

        configured = load_settings().k8s.context
        return configured.strip() if configured and configured.strip() else None
    except Exception:
        return None


def _cluster_reachable(context: str | None = None) -> bool:
    """Return True if the target Kubernetes cluster (or Minikube) is reachable."""
    effective_context = resolve_effective_context(context)

    cmd = ["kubectl", "cluster-info", "--request-timeout=5s"]
    if effective_context:
        cmd.extend(["--context", effective_context])
    try:
        res = _run_cmd(cmd, check=False, capture=True)
        if res.returncode == 0:
            return True
    except FileNotFoundError, OSError, subprocess.SubprocessError:
        pass

    if effective_context and effective_context.strip().lower() == "minikube":
        return _minikube_running()
    return False
