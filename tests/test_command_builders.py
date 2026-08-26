"""Unit tests for centralized command builders."""

from __future__ import annotations

from pathlib import Path

from devops_cli.config.commands import (
    BIN_BANDIT,
    BIN_FIND,
    BIN_GIT,
    BIN_GITLEAKS,
    BIN_KUBECTL,
    BIN_KUBELINTER,
    BIN_KUSTOMIZE,
    BIN_PLUTO,
    BIN_POPEYE,
    BIN_SEMGREP,
    BIN_TERRAFORM,
    BIN_TOFU,
    BIN_TRIVY,
    BIN_UV,
    build_bandit_cmd,
    build_find_files_cmd,
    build_git_clone_cmd,
    build_git_diff_cmd,
    build_git_log_cmd,
    build_git_rev_parse_cmd,
    build_gitleaks_cmd,
    build_iac_cmd,
    build_kubectl_cmd,
    build_kubectl_port_forward_cmd,
    build_kubelinter_cmd,
    build_kustomize_build_cmd,
    build_pluto_cmd,
    build_popeye_cmd,
    build_semgrep_cmd,
    build_tf_cmd,
    build_tofu_cmd,
    build_trivy_scan_cmd,
    build_uv_audit_cmd,
)


def test_command_builders() -> None:
    """Verify that all subprocess command builders return expected argument lists."""
    assert build_git_rev_parse_cmd(["--show-toplevel"]) == [BIN_GIT, "rev-parse", "--show-toplevel"]
    assert build_git_diff_cmd("feat", "main") == [BIN_GIT, "diff", "main...feat"]
    assert build_git_log_cmd(5) == [BIN_GIT, "log", "-n5"]
    assert build_git_clone_cmd("https://github.com/org/repo.git", Path("/tmp/repo")) == [
        BIN_GIT,
        "clone",
        "https://github.com/org/repo.git",
        "/tmp/repo",
    ]

    find_cmd = build_find_files_cmd(".", maxdepth=2, exclude_paths=["./.git/*"])
    assert find_cmd == [BIN_FIND, ".", "-maxdepth", "2", "-not", "-path", "./.git/*"]

    k8s_cmd = build_kubectl_cmd(["get", "pods"], context="prod-cluster")
    assert k8s_cmd == [BIN_KUBECTL, "--context", "prod-cluster", "get", "pods"]

    pf_cmd = build_kubectl_port_forward_cmd("web", 8080, 80, "default", context="dev-cluster")
    assert pf_cmd == [
        BIN_KUBECTL,
        "port-forward",
        "svc/web",
        "8080:80",
        "--address",
        "127.0.0.1",
        "-n",
        "default",
        "--context",
        "dev-cluster",
    ]

    assert build_kustomize_build_cmd("overlays/prod") == [BIN_KUSTOMIZE, "build", "overlays/prod"]
    assert build_bandit_cmd("src") == [BIN_BANDIT, "-r", "src", "-q", "-x", "B608"]
    assert build_trivy_scan_cmd("src", "fs") == [
        BIN_TRIVY,
        "fs",
        "src",
        "--severity",
        "HIGH,CRITICAL",
        "--format",
        "json",
        "--quiet",
    ]
    assert build_popeye_cmd("k3s") == [
        BIN_POPEYE,
        "-o",
        "json",
        "-s",
        "error,warn",
        "--context",
        "k3s",
    ]
    assert build_kubelinter_cmd("k8s") == [BIN_KUBELINTER, "lint", "k8s", "--format", "json"]
    assert build_pluto_cmd("k8s") == [BIN_PLUTO, "detect-files", "-d", "k8s", "-o", "json"]
    assert build_uv_audit_cmd() == [BIN_UV, "audit"]
    assert build_tf_cmd("plan", ["-out=tfplan"]) == [BIN_TERRAFORM, "plan", "-out=tfplan"]
    assert build_tofu_cmd("apply", ["-auto-approve"]) == [BIN_TOFU, "apply", "-auto-approve"]
    assert build_iac_cmd("terraform", "validate") == [BIN_TERRAFORM, "validate"]
    assert build_iac_cmd("tofu", "validate") == [BIN_TOFU, "validate"]
    assert build_gitleaks_cmd("src", no_git=True) == [
        BIN_GITLEAKS,
        "detect",
        "--report-format",
        "json",
        "--no-git",
        "--source",
        "src",
    ]
    assert build_gitleaks_cmd("src", no_git=False) == [
        BIN_GITLEAKS,
        "detect",
        "--report-format",
        "json",
        "--source",
        "src",
    ]
    assert build_semgrep_cmd("src", exclude_paths=["tests/*"]) == [
        BIN_SEMGREP,
        "scan",
        "--json",
        "--config",
        "p/default",
        "--exclude",
        "tests/*",
        "src",
    ]
