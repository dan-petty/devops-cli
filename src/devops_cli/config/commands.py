"""Centralized subprocess command definitions, binary names, and argument builders."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

# ── Binary Names ─────────────────────────────────────────────────────────────
BIN_ACTIONLINT: str = "actionlint"
BIN_ARGOCD: str = "argocd"
BIN_BANDIT: str = "bandit"
BIN_DOCKER: str = "docker"
BIN_FIND: str = "find"
BIN_GIT: str = "git"
BIN_KUBECTL: str = "kubectl"
BIN_KUBELINTER: str = "kube-linter"
BIN_KUSTOMIZE: str = "kustomize"
BIN_PLUTO: str = "pluto"
BIN_POPEYE: str = "popeye"
BIN_TERRAFORM: str = "terraform"
BIN_TOFU: str = "tofu"
BIN_TRIVY: str = "trivy"
BIN_UV: str = "uv"


# ── Command Argument List Builders ───────────────────────────────────────────


def build_git_rev_parse_cmd(flags: Sequence[str]) -> list[str]:
    """Build a git rev-parse command."""
    return [BIN_GIT, "rev-parse", *flags]


def build_git_diff_cmd(branch: str, base: str) -> list[str]:
    """Build a git diff command between two branches."""
    return [BIN_GIT, "diff", f"{base}...{branch}"]


def build_git_log_cmd(count: int = 10, format_spec: str | None = None) -> list[str]:
    """Build a git log command."""
    cmd = [BIN_GIT, "log", f"-n{count}"]
    if format_spec:
        cmd.append(f"--format={format_spec}")
    return cmd


def build_git_clone_cmd(repo_url: str, dest_dir: Path) -> list[str]:
    """Build a git clone command."""
    return [BIN_GIT, "clone", repo_url, str(dest_dir)]


def build_find_files_cmd(
    target_dir: Path | str,
    maxdepth: int = 3,
    exclude_paths: Sequence[str] | None = None,
) -> list[str]:
    """Build a find command with standard path exclusions."""
    cmd = [BIN_FIND, str(target_dir), "-maxdepth", str(maxdepth)]
    if exclude_paths:
        for p in exclude_paths:
            cmd.extend(["-not", "-path", p])
    return cmd


def build_kubectl_cmd(args: Sequence[str], context: str | None = None) -> list[str]:
    """Build a kubectl command with optional context flag."""
    cmd = [BIN_KUBECTL]
    if context:
        cmd.extend(["--context", context])
    cmd.extend(args)
    return cmd


def build_kubectl_port_forward_cmd(
    service: str,
    local_port: int,
    remote_port: int,
    namespace: str,
    address: str = "127.0.0.1",
    context: str | None = None,
) -> list[str]:
    """Build a kubectl port-forward command."""
    cmd = [
        BIN_KUBECTL,
        "port-forward",
        f"svc/{service}",
        f"{local_port}:{remote_port}",
        "--address",
        address,
        "-n",
        namespace,
    ]
    if context:
        cmd.extend(["--context", context])
    return cmd


def build_kustomize_build_cmd(target_path: Path | str) -> list[str]:
    """Build a kustomize build command."""
    return [BIN_KUSTOMIZE, "build", str(target_path)]


def build_bandit_cmd(target: Path | str, exclude_tests: str = "B608") -> list[str]:
    """Build a bandit security scan command."""
    return [BIN_BANDIT, "-r", str(target), "-q", "-x", exclude_tests]


def build_trivy_scan_cmd(
    target: Path | str,
    scan_type: str = "fs",
    severity: str = "HIGH,CRITICAL",
) -> list[str]:
    """Build an Aqua Trivy security scan command."""
    return [
        BIN_TRIVY,
        scan_type,
        str(target),
        "--severity",
        severity,
        "--format",
        "json",
        "--quiet",
    ]


def build_popeye_cmd(context: str | None = None) -> list[str]:
    """Build a Popeye Kubernetes cluster scanner command."""
    cmd = [BIN_POPEYE, "-o", "json", "-s", "error,warn"]
    if context:
        cmd.extend(["--context", context])
    return cmd


def build_kubelinter_cmd(target_path: Path | str) -> list[str]:
    """Build a kube-linter manifest scanner command."""
    return [BIN_KUBELINTER, "lint", str(target_path), "--format", "json"]


def build_pluto_cmd(target_path: Path | str) -> list[str]:
    """Build a Pluto deprecated Kubernetes API scanner command."""
    return [BIN_PLUTO, "detect-files", "-d", str(target_path), "-o", "json"]


def build_uv_audit_cmd() -> list[str]:
    """Build a uv dependency audit command."""
    return [BIN_UV, "audit"]


def build_iac_cmd(binary: str, subcommand: str, args: Sequence[str] | None = None) -> list[str]:
    """Build an Infrastructure-as-Code command (terraform or tofu)."""
    bin_name = BIN_TOFU if binary.lower() in ("tofu", "opentofu", BIN_TOFU) else BIN_TERRAFORM
    cmd = [bin_name, subcommand]
    if args:
        cmd.extend(args)
    return cmd


def build_tf_cmd(subcommand: str, args: Sequence[str] | None = None) -> list[str]:
    """Build a terraform command."""
    return build_iac_cmd(BIN_TERRAFORM, subcommand, args=args)


def build_tofu_cmd(subcommand: str, args: Sequence[str] | None = None) -> list[str]:
    """Build an opentofu command."""
    return build_iac_cmd(BIN_TOFU, subcommand, args=args)
