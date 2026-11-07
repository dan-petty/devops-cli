"""Runtime and subprocess execution helpers for Kubernetes commands."""

from __future__ import annotations

import json
import subprocess
from typing import Any

from devops_cli.config.defaults import DEFAULT_SUBPROCESS_TIMEOUT_SECONDS
from devops_cli.core.process import run_subprocess as run_subprocess
from devops_cli.core.validation import validate_k8s_name


def _validate_k8s_identifier(val: str, label: str, *, namespace: bool = False) -> None:
    validate_k8s_name(val, label, namespace=namespace)


def _validate_kubeconfig_context_name(val: str, label: str = "context name") -> None:
    from devops_cli.core.validation import validate_k8s_context_name

    validate_k8s_context_name(val, label=label)


def _run_cmd(
    cmd: list[str],
    *,
    input: str | None = None,
    check: bool = True,
    capture: bool = False,
    timeout: float = DEFAULT_SUBPROCESS_TIMEOUT_SECONDS,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    import os
    from pathlib import Path

    from devops_cli.core.paths import is_forbidden_system_path, validate_no_path_traversal
    from devops_cli.exceptions.security import SecurityError

    kubeconfig = os.environ.get("KUBECONFIG")
    if kubeconfig:
        for entry in kubeconfig.split(os.pathsep):
            clean_entry = entry.strip()
            if not clean_entry:
                continue
            validate_no_path_traversal(clean_entry, label="KUBECONFIG")
            resolved = Path(clean_entry).resolve()
            if is_forbidden_system_path(resolved):
                raise SecurityError(
                    f"KUBECONFIG cannot point to forbidden system directory: '{clean_entry}'."
                )

    return run_subprocess(
        cmd,
        input=input,
        env=env,
        check=check,
        capture_output=capture,
        text=True,
        timeout=timeout,
    )


# The addon `storage-provisioner-rancher` adds the StorageClass `local-path`, which the claims
# of the stacks name. The default addon `storage-provisioner` serves only the class `standard`.
_MINIKUBE_START_FLAGS = (
    "--driver=docker",
    "--cni=calico",
    "--addons=storage-provisioner-rancher",
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
    cpu_flags = list(_MINIKUBE_START_FLAGS)
    gpu_flags = [*cpu_flags, "--gpus=all"]
    cpu_text = f"Started Minikube cluster ({' '.join(cpu_flags)})"
    gpu_text = f"Started Minikube cluster ({' '.join(gpu_flags)})"
    if dry_run:
        return True, gpu_text if has_gpu else cpu_text

    if has_gpu:
        start_res = _run_cmd(["minikube", "start", *gpu_flags], check=False)
        if start_res.returncode == 0 and _minikube_running():
            _run_cmd(["minikube", "update-context"], check=False)
            return True, gpu_text

    fallback_res = _run_cmd(["minikube", "start", *cpu_flags], check=False)
    if fallback_res.returncode == 0 and _minikube_running():
        _run_cmd(["minikube", "update-context"], check=False)
        return True, cpu_text

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

    try:
        from devops_cli.k8s.service import KubernetesService

        if KubernetesService.get_instance().is_cluster_reachable(context=effective_context):
            return True
    except Exception:
        pass

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


def _read_nodes(context: str | None = None) -> list[dict[str, Any]] | None:
    """The cluster's nodes from `kubectl get nodes -o json`, or None when the read fails."""
    effective_context = resolve_effective_context(context)
    k_ctx = ["--context", effective_context] if effective_context else []
    try:
        res = _run_cmd(
            ["kubectl", "get", "nodes", "-o", "json"] + k_ctx,
            check=False,
            capture=True,
            timeout=5,
        )
        if res.returncode != 0 or not res.stdout:
            return None
        items = json.loads(res.stdout).get("items", [])
        return [dict(item) for item in items]
    except subprocess.SubprocessError, OSError, json.JSONDecodeError, KeyError, TypeError:
        return None


def _get_unready_nodes(context: str | None = None) -> list[str]:
    """Return a list of node names that are in NotReady status."""
    unready: list[str] = []
    for item in _read_nodes(context) or []:
        name = item.get("metadata", {}).get("name", "unknown")
        is_ready = any(
            cond.get("type") == "Ready" and cond.get("status") == "True"
            for cond in item.get("status", {}).get("conditions", [])
        )
        if not is_ready:
            unready.append(name)
    return unready
