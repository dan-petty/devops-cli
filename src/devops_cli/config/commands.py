"""Centralized subprocess command definitions, binary names, and argument builders."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from devops_cli.config.defaults import (
    DEFAULT_BANDIT_EXCLUDE,
    DEFAULT_FIND_MAXDEPTH,
    DEFAULT_GIT_LOG_COUNT,
    DEFAULT_REST_HOST,
    DEFAULT_SEMGREP_CONFIG,
    DEFAULT_TRIVY_HIGH_SEVERITY,
    DEFAULT_TRIVY_SCAN_TYPE,
)

# ── Binary Names ─────────────────────────────────────────────────────────────
BIN_ACTIONLINT: str = "actionlint"
BIN_ARGOCD: str = "argocd"
BIN_BANDIT: str = "bandit"
BIN_DAGGER: str = "dagger"
BIN_DIFFT: str = "difft"
BIN_DOCKER: str = "docker"
BIN_FIND: str = "find"
BIN_GIT: str = "git"
BIN_GITLEAKS: str = "gitleaks"
BIN_HELM: str = "helm"
BIN_K6: str = "k6"
BIN_KUBECTL: str = "kubectl"
BIN_KUBELINTER: str = "kube-linter"
BIN_KUSTOMIZE: str = "kustomize"
BIN_KYVERNO: str = "kyverno"
BIN_OPA: str = "opa"
BIN_PLUTO: str = "pluto"
BIN_POPEYE: str = "popeye"
BIN_SEMGREP: str = "semgrep"
BIN_STERN: str = "stern"
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


def build_git_log_cmd(
    count: int = DEFAULT_GIT_LOG_COUNT, format_spec: str | None = None
) -> list[str]:
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
    maxdepth: int = DEFAULT_FIND_MAXDEPTH,
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
    address: str = DEFAULT_REST_HOST,
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


def build_bandit_cmd(target: Path | str, exclude_tests: str = DEFAULT_BANDIT_EXCLUDE) -> list[str]:
    """Build a bandit security scan command."""
    return [BIN_BANDIT, "-r", str(target), "-q", "-x", exclude_tests]


def build_trivy_scan_cmd(
    target: Path | str,
    scan_type: str = DEFAULT_TRIVY_SCAN_TYPE,
    severity: str = DEFAULT_TRIVY_HIGH_SEVERITY,
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


def build_gitleaks_cmd(target_path: Path | str, no_git: bool = True) -> list[str]:
    """Build a Gitleaks secret scanner command."""
    cmd = [BIN_GITLEAKS, "detect", "--report-format", "json"]
    if no_git:
        cmd.extend(["--no-git", "--source", str(target_path)])
    else:
        cmd.extend(["--source", str(target_path)])
    return cmd


def build_semgrep_cmd(
    target_path: Path | str,
    config: str = DEFAULT_SEMGREP_CONFIG,
    exclude_paths: Sequence[str] | None = None,
) -> list[str]:
    """Build a Semgrep AST security and code quality scan command."""
    cmd = [BIN_SEMGREP, "scan", "--json", "--config", config]
    if exclude_paths:
        for p in exclude_paths:
            cmd.extend(["--exclude", p])
    cmd.append(str(target_path))
    return cmd


def build_kyverno_validate_cmd(
    manifest_path: Path | str,
    policy_path: Path | str | None = None,
) -> list[str]:
    """Build a Kyverno CLI validate command for Kubernetes admission policies."""
    cmd = [BIN_KYVERNO, "apply"]
    if policy_path:
        cmd.append(str(policy_path))
    cmd.extend(["--resource", str(manifest_path), "--output", "json"])
    return cmd


def build_opa_eval_cmd(
    data_path: Path | str,
    input_path: Path | str | None = None,
    query: str = "data",
) -> list[str]:
    """Build an Open Policy Agent (OPA) eval command."""
    cmd = [BIN_OPA, "eval", "--data", str(data_path), "--format", "json"]
    if input_path:
        cmd.extend(["--input", str(input_path)])
    cmd.append(query)
    return cmd


def build_stern_cmd(
    pod_query: str,
    namespace: str | None = None,
    container: str | None = None,
    tail_lines: int | None = None,
    follow: bool = False,
) -> list[str]:
    """Build a Stern multi-pod log streamer command."""
    cmd = [BIN_STERN, pod_query]
    if namespace:
        cmd.extend(["-n", namespace])
    if container:
        cmd.extend(["-c", container])
    if tail_lines is not None:
        cmd.extend(["--tail", str(tail_lines)])
    if not follow:
        cmd.append("--no-follow")
    return cmd


def build_helm_diff_cmd(
    release_name: str,
    chart_path: Path | str,
    namespace: str | None = None,
    values_files: Sequence[Path | str] | None = None,
) -> list[str]:
    """Build a Helm Diff plugin command."""
    cmd = [BIN_HELM, "diff", "upgrade", release_name, str(chart_path)]
    if namespace:
        cmd.extend(["-n", namespace])
    if values_files:
        for v in values_files:
            cmd.extend(["-f", str(v)])
    return cmd


def build_difft_cmd(
    path_a: Path | str,
    path_b: Path | str | None = None,
) -> list[str]:
    """Build a Difftastic structural AST diff command."""
    cmd = [BIN_DIFFT, "--color", "never"]
    cmd.append(str(path_a))
    if path_b:
        cmd.append(str(path_b))
    return cmd


def build_k6_cmd(
    script_path: Path | str,
    vus: int | None = None,
    duration: str | None = None,
    summary_export: Path | str | None = None,
) -> list[str]:
    """Build a k6 load test command."""
    cmd = [BIN_K6, "run", str(script_path)]
    if vus is not None:
        cmd.extend(["--vus", str(vus)])
    if duration is not None:
        cmd.extend(["--duration", duration])
    if summary_export is not None:
        cmd.extend(["--summary-export", str(summary_export)])
    return cmd


def build_dagger_cmd(
    pipeline_path: Path | str,
    function_name: str | None = None,
    args: Sequence[str] | None = None,
) -> list[str]:
    """Build a Dagger pipeline execution command."""
    cmd = [BIN_DAGGER, "call", "-m", str(pipeline_path)]
    if function_name:
        cmd.append(function_name)
    if args:
        cmd.extend(args)
    return cmd
