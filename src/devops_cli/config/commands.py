"""Centralized subprocess command definitions, binary names, and argument builders."""

from __future__ import annotations

import os
from collections.abc import Sequence
from pathlib import Path

from devops_cli.config.constants import CONST_K8S_MANIFEST_EXTENSIONS, CONST_SEMGREP_JOBS
from devops_cli.config.defaults import (
    DEFAULT_FIND_MAXDEPTH,
    DEFAULT_GIT_LOG_COUNT,
    DEFAULT_REST_HOST,
    DEFAULT_TRIVY_HIGH_SEVERITY,
    DEFAULT_TRIVY_SCAN_TYPE,
)

# ── Binary Names ─────────────────────────────────────────────────────────────
BIN_ACTIONLINT: str = "actionlint"
BIN_ARGOCD: str = "argocd"
BIN_BANDIT: str = "bandit"
BIN_BASH: str = "bash"
BIN_COSIGN: str = "cosign"
BIN_DAGGER: str = "dagger"
BIN_DEVOPS: str = "devops"
BIN_DIFFT: str = "difft"
BIN_FIND: str = "find"
BIN_GIT: str = "git"
BIN_GITLEAKS: str = "gitleaks"
BIN_GO: str = "go"
BIN_GOLANGCI_LINT: str = "golangci-lint"
BIN_HELM: str = "helm"
BIN_K6: str = "k6"
BIN_KUBECTL: str = "kubectl"
BIN_KUBELINTER: str = "kube-linter"
BIN_KUSTOMIZE: str = "kustomize"
BIN_KYVERNO: str = "kyverno"
BIN_MYPY: str = "mypy"
BIN_NPM: str = "npm"
BIN_OPA: str = "opa"
BIN_OPENSPEC: str = "openspec"
BIN_OSV_SCANNER: str = "osv-scanner"
BIN_PLUTO: str = "pluto"
BIN_POPEYE: str = "popeye"
BIN_PRE_COMMIT: str = "pre-commit"
BIN_RUFF: str = "ruff"
BIN_SEMGREP: str = "semgrep"
BIN_STERN: str = "stern"
BIN_TERRAFORM: str = "terraform"
BIN_TOFU: str = "tofu"
BIN_TRIVY: str = "trivy"
BIN_UV: str = "uv"
BIN_ZIZMOR: str = "zizmor"


# The programs that a `devops roadmap implement` step (#2664) may start. The shell tool of the
# agent takes the first list: the project's own build tools, and not `devops` or `openspec`,
# which can write to GitHub or to the change. The step runs the verification commands of a group
# under the second list, which adds those two.
IMPLEMENT_SHELL_PROGRAMS: tuple[str, ...] = (BIN_GIT, BIN_UV, BIN_RUFF, BIN_MYPY)
IMPLEMENT_ALLOWED_PROGRAMS: tuple[str, ...] = (*IMPLEMENT_SHELL_PROGRAMS, BIN_OPENSPEC, BIN_DEVOPS)

# What a step agent runs in place of a program that its shell refuses (#2773). The key is the
# program that the model asks for, as the shell reads the first word. The value is the text of the
# replacement, which reads after "Instead of `<program>`:" in the refusal, and in a table of the
# prompt `roadmap_implement_step.md`. The first sentence of a value is the replacement itself. A test fails when the table, the prompt and
# `IMPLEMENT_SHELL_PROGRAMS` disagree.
PYTHON_REPLACEMENT: str = (
    "`uv run python`. Do not run `python -m pip`: the lockfile gives the dependencies"
)
IMPLEMENT_SHELL_REPLACEMENTS: dict[str, str] = {
    "python": PYTHON_REPLACEMENT,
    "python3": PYTHON_REPLACEMENT,
    "pytest": "`uv run pytest`",
    "pip": "nothing. The lockfile gives the dependencies",
    "pip3": "nothing. The lockfile gives the dependencies",
    "cat": "the tool `read_file`",
    "head": "the tool `read_file`",
    "tail": "the tool `read_file`",
    "ls": "the tool `list_files`",
    "find": "the tool `list_files`",
    "grep": "the tool `grep`",
    "rg": "the tool `grep`",
    "cd": "nothing. Every command runs in the checkout",
}


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


def build_trivy_sbom_cmd(
    target: Path | str,
    format_type: str = "cyclonedx",
) -> list[str]:
    """Build an Aqua Trivy SBOM generation command (#1439)."""
    trivy_format = "spdx-json" if format_type in ("spdx", "spdx-json") else "cyclonedx"
    return [
        BIN_TRIVY,
        "fs",
        "--format",
        trivy_format,
        str(target),
    ]


def build_osv_scan_cmd(
    target_path: Path | str,
    *,
    lockfiles: Sequence[Path | str] | None = None,
    offline: bool = True,
) -> list[str]:
    """Build an OSV-Scanner security scan command (#1146)."""
    cmd = [
        BIN_OSV_SCANNER,
        "scan",
        "source",
        "--format",
        "json",
    ]
    if offline:
        cmd.extend(["--offline", "--offline-vulnerabilities"])
    cmd.extend(["--all-packages", "--all-vulns"])
    targets = lockfiles or [target_path]
    for lf in targets:
        cmd.extend(["--lockfile", str(lf)])
    return cmd


def build_popeye_cmd(context: str | None = None, namespace: str | None = None) -> list[str]:
    """Build a Popeye cluster scan that reports warnings and errors as JSON, over `namespace` or,
    with none, over every namespace. `-l` is Popeye's lint level; `-s` names resource sections."""
    cmd = [BIN_POPEYE, "-o", "json", "-l", "warn"]
    if namespace:
        cmd.extend(["-n", namespace])
    else:
        cmd.append("-A")
    if context:
        cmd.extend(["--context", context])
    return cmd


def build_kubelinter_cmd(target_path: Path | str) -> list[str]:
    """Build a kube-linter manifest scanner command."""
    return [BIN_KUBELINTER, "lint", str(target_path), "--format", "json"]


def build_pluto_cmd(
    target_path: Path | str,
    binary_name: str = BIN_PLUTO,
    target_versions: str | None = None,
    *,
    cwd: Path | None = None,
) -> list[str]:
    """Build a Pluto deprecated Kubernetes API scanner command.

    Pluto writes each `filePath` as its working directory joined to the path it read
    (`CheckForAPIVersion` in `pkg/finder/finder.go` of FairwindsOps/pluto), so a command that
    starts in `cwd` names the target relative to `cwd` (#1434).
    """
    p = Path(target_path)
    named = os.path.relpath(p, cwd) if cwd is not None else str(target_path)
    if p.is_file() or (not p.is_dir() and p.suffix.lower() in CONST_K8S_MANIFEST_EXTENSIONS):
        cmd = [binary_name, "detect", named, "-o", "json"]
    else:
        cmd = [binary_name, "detect-files", "-d", named, "-o", "json"]
    if target_versions:
        cmd.extend(["--target-versions", target_versions])
    return cmd


def build_uv_audit_cmd() -> list[str]:
    """Build the uv command that audits the `uv.lock` of the project in its working directory and
    writes a JSON report on stdout (#2106).

    `--frozen` audits the lockfile as it is: without it, uv locks the project again first and
    rewrites a stale `uv.lock`. `--quiet` drops the preview warnings that uv writes on stderr
    before an error, which would fill the reason of a failed scan; uv still writes the report
    and each error.
    """
    return [BIN_UV, "audit", "--frozen", "--quiet", "--output-format", "json"]


def build_npm_ci_cmd() -> list[str]:
    """Build the npm command that installs exactly what a `package-lock.json` records.

    `npm ci` refuses a manifest and lockfile that disagree and checks the sha512 of every package.
    No package script runs, the engine range of every package is enforced, a configured registry
    does not rewrite the lockfile's URLs, and neither the audit nor the funding request is sent.
    """
    return [
        BIN_NPM,
        "ci",
        "--ignore-scripts",
        "--no-audit",
        "--no-fund",
        "--engine-strict",
        "--replace-registry-host=never",
    ]


def build_npm_audit_cmd(project_dir: Path | str) -> list[str]:
    """Build the npm command that audits the `package-lock.json` in `project_dir` for known
    vulnerabilities without installing anything, and checks for no newer npm.

    npm exits 1 for a finding and for an audit that could not run alike, so it reports as JSON:
    the report tells the two apart (`devops_cli.core.dependency_audit`).
    """
    return [
        BIN_NPM,
        "audit",
        "--package-lock-only",
        "--json",
        "--no-update-notifier",
        "--prefix",
        str(project_dir),
    ]


def build_openspec_cmd(*args: str) -> list[str]:
    """Build an `openspec` command: the pinned OpenSpec's program, then its arguments."""
    return [BIN_OPENSPEC, *args]


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
    """Build a Gitleaks scan of the files at `target_path` (`dir`), or with `no_git` false of the
    history of its repository (`git`). Gitleaks writes its JSON report only to `--report-path`, so
    `-` sends it to stdout, and `--redact` keeps each secret out of the report (#1434)."""
    scan = "dir" if no_git else "git"
    report = ["--report-format", "json", "--report-path", "-", "--redact"]
    return [BIN_GITLEAKS, scan, *report, str(target_path)]


def build_zizmor_cmd(*targets: Path | str) -> list[str]:
    """Build a zizmor GitHub Actions audit with no network access and JSON output. With
    `--no-exit-codes` zizmor exits 0 whatever it finds, so any other exit means it did not run."""
    return [BIN_ZIZMOR, "--offline", "--no-exit-codes", "--format", "json", *map(str, targets)]


def build_semgrep_cmd(
    targets: Sequence[Path | str],
    configs: Sequence[str],
    exclude_paths: Sequence[str] = (),
    exclude_rules: Sequence[str] = (),
) -> list[str]:
    """Build a Semgrep scan: JSON on stdout, no metrics sent, no version check, a fixed number
    of jobs, and every finding reported whatever inline `nosemgrep` marker it carries. Every
    `semgrep scan` devops-cli starts is built here (#1144). The fixed jobs keep the address space
    of a scan the same on each host (`CONST_SEMGREP_JOBS`, #2096). Semgrep skips each rule whose
    id `exclude_rules` names (#1024)."""
    cmd = [
        BIN_SEMGREP,
        "scan",
        "--json",
        "--metrics",
        "off",
        "--disable-version-check",
        "--jobs",
        str(CONST_SEMGREP_JOBS),
    ]
    for config in configs:
        cmd.extend(["--config", config])
    cmd.append("--disable-nosem")
    for exclude_path in exclude_paths:
        cmd.extend(["--exclude", exclude_path])
    for exclude_rule in exclude_rules:
        cmd.extend(["--exclude-rule", exclude_rule])
    cmd.append("--quiet")
    cmd.extend(map(str, targets))
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


def build_cosign_sign_cmd(
    image: str,
    *,
    key: str | None = None,
    keyless: bool = True,
    upload: bool = True,
    annotations: Sequence[str] | None = None,
) -> list[str]:
    """Build a cosign sign command for container image signing."""
    cmd = [BIN_COSIGN, "sign"]
    if key:
        cmd.extend(["--key", key])
    elif keyless:
        cmd.append("--yes")
    if not upload:
        cmd.append("--upload=false")
    if annotations:
        for annotation in annotations:
            cmd.extend(["-a", annotation])
    cmd.append(image)
    return cmd


def build_cosign_verify_cmd(
    image: str,
    *,
    key: str | None = None,
    cert_identity: str | None = None,
    cert_issuer: str | None = None,
    attestation: bool = False,
    predicate_type: str | None = None,
    insecure_ignore_tlog: bool = False,
) -> list[str]:
    """Build a cosign verify or verify-attestation command."""
    subcmd = "verify-attestation" if attestation else "verify"
    cmd = [BIN_COSIGN, subcmd, "--output", "json"]
    if key:
        cmd.extend(["--key", key])
    if cert_identity:
        cmd.extend(["--certificate-identity", cert_identity])
    if cert_issuer:
        cmd.extend(["--certificate-oidc-issuer", cert_issuer])
    if predicate_type:
        cmd.extend(["--type", predicate_type])
    if insecure_ignore_tlog:
        cmd.append("--insecure-ignore-tlog=true")
    cmd.append(image)
    return cmd
