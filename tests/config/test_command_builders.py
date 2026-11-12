"""Unit tests for centralized command builders."""

from __future__ import annotations

from pathlib import Path

from devops_cli.config.commands import (
    BIN_GIT,
    BIN_GITLEAKS,
    BIN_KUBECTL,
    BIN_KUBELINTER,
    BIN_KUSTOMIZE,
    BIN_PLUTO,
    BIN_POPEYE,
    BIN_SEMGREP,
    BIN_TRIVY,
    BIN_UV,
    build_git_diff_cmd,
    build_gitleaks_cmd,
    build_kubectl_cmd,
    build_kubelinter_cmd,
    build_kustomize_build_cmd,
    build_pluto_cmd,
    build_popeye_cmd,
    build_semgrep_cmd,
    build_trivy_scan_cmd,
    build_uv_audit_cmd,
)


def test_command_builders() -> None:
    """Verify that all subprocess command builders return expected argument lists."""
    assert build_git_diff_cmd("feat", "main") == [BIN_GIT, "diff", "main...feat"]

    k8s_cmd = build_kubectl_cmd(["get", "pods"], context="prod-cluster")
    assert k8s_cmd == [BIN_KUBECTL, "--context", "prod-cluster", "get", "pods"]

    assert build_kustomize_build_cmd("overlays/prod") == [BIN_KUSTOMIZE, "build", "overlays/prod"]
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
    assert (
        build_popeye_cmd(),
        build_popeye_cmd("k3s"),
        build_popeye_cmd("k3s", namespace="argocd"),
    ) == (
        [BIN_POPEYE, "-o", "json", "-l", "warn", "-A"],
        [BIN_POPEYE, "-o", "json", "-l", "warn", "-A", "--context", "k3s"],
        [BIN_POPEYE, "-o", "json", "-l", "warn", "-n", "argocd", "--context", "k3s"],
    )
    assert (
        build_kubelinter_cmd("k8s"),
        build_pluto_cmd("k8s"),
        build_pluto_cmd("k8s/deployment.yaml"),
        build_pluto_cmd(Path("/srv/tree/k8s/deployment.yaml"), cwd=Path("/srv/tree/k8s")),
        build_pluto_cmd(Path("/srv/tree/k8s"), cwd=Path("/srv/scratch")),
        build_uv_audit_cmd(),
    ) == (
        [BIN_KUBELINTER, "lint", "k8s", "--format", "json"],
        [BIN_PLUTO, "detect-files", "-d", "k8s", "-o", "json"],
        [BIN_PLUTO, "detect", "k8s/deployment.yaml", "-o", "json"],
        [BIN_PLUTO, "detect", "deployment.yaml", "-o", "json"],
        [BIN_PLUTO, "detect-files", "-d", "../tree/k8s", "-o", "json"],
        [BIN_UV, "audit", "--frozen", "--quiet", "--output-format", "json"],
    )
    report = ["--report-format", "json", "--report-path", "-", "--redact"]
    assert (build_gitleaks_cmd("src", no_git=True), build_gitleaks_cmd("src", no_git=False)) == (
        [BIN_GITLEAKS, "dir", *report, "src"],
        [BIN_GITLEAKS, "git", *report, "src"],
    )
    assert build_semgrep_cmd(
        ["src", "docs"],
        configs=["p/default", "rules"],
        exclude_paths=["tests/*"],
    ) == [
        BIN_SEMGREP,
        "scan",
        "--json",
        "--metrics",
        "off",
        "--disable-version-check",
        "--jobs",
        "4",
        "--config",
        "p/default",
        "--config",
        "rules",
        "--disable-nosem",
        "--exclude",
        "tests/*",
        "--quiet",
        "src",
        "docs",
    ]
