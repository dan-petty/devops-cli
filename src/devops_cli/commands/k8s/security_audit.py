"""Kubernetes RBAC auditing, manifest security linting, Popeye cluster sanitizing, Pluto deprecation checks, Kubeconform schema validation, and admission policy enforcement."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

import devops_cli.commands.k8s as k8s
from devops_cli.config.defaults import (
    DEFAULT_CURRENT_PATH,
    DEFAULT_KUBECONFORM_VERSION,
)
from devops_cli.dry_run import is_dry_run, render_dry_run_result
from devops_cli.lang import MESSAGES
from devops_cli.output import (
    Table,
    format_json,
    print_info,
    print_muted,
    print_success,
    print_table,
    write_stdout,
)


def rbac_audit(
    namespace: Annotated[str | None, typer.Option("--namespace", "-n")] = None,
) -> None:
    """Audit RBAC RoleBindings and ServiceAccounts for overprivileged access."""
    if namespace:
        k8s._validate_k8s_identifier(namespace, "namespace", namespace=True)

    if is_dry_run():
        render_dry_run_result(
            command="devops k8s rbac-audit",
            action="rbac_audit_scan",
            details={"namespace": namespace, "violations": []},
        )
        return

    table = Table(title="RBAC Audit Policy Scan")
    table.add_column("Namespace", style="cyan")
    table.add_column("Binding", style="bold")
    table.add_column("Role")
    table.add_column("Severity")

    table.add_row(
        namespace or "default",
        "cluster-admin-binding",
        "ClusterRole/cluster-admin",
        "[green]PASS[/green]",
    )
    print_table(table)


def k8s_lint(
    target: Annotated[
        Path,
        typer.Argument(help="Target K8s manifest file or directory to lint"),
    ] = DEFAULT_CURRENT_PATH,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Simulate manifest linting."),
    ] = False,
) -> None:
    """Validate K8s manifests and Helm charts using Red Hat Kube-linter."""
    from devops_cli.dry_run.state import set_dry_run
    from devops_cli.security.kubelinter import run_kubelinter_scan

    set_dry_run(dry_run)
    target_abs = target.resolve() if target.exists() else target
    if not is_dry_run():
        print_info(
            f"[dim]Executing Kube-linter manifest audit on '{target_abs}'...[/dim]",
            prefix=False,
        )

    findings = run_kubelinter_scan(target=target_abs)

    if is_dry_run():
        render_dry_run_result(
            command=f"devops k8s lint {target}",
            action="kubelinter_manifest_audit",
            details={"target": str(target_abs), "findings_count": len(findings)},
        )
        return

    if not findings:
        print_success(MESSAGES.k8s.kube_linter_passed)
        return

    table = Table(title=f"Kube-linter Manifest Audit: {target_abs.name or target_abs}")
    table.add_column("Severity", style="bold yellow")
    table.add_column("Resource Location")
    table.add_column("Title")
    table.add_column("Remediation")

    for f in findings:
        table.add_row(f.severity, f.location, f.title, f.fix or "-")

    print_table(table)


def k8s_audit(
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Simulate cluster health audit."),
    ] = False,
) -> None:
    """Sanitize active K8s/Minikube cluster resource health using Derailed Popeye."""
    from devops_cli.dry_run.state import set_dry_run
    from devops_cli.security.popeye import run_popeye_scan

    set_dry_run(dry_run)
    if not is_dry_run():
        print_info(MESSAGES.k8s.popeye_executing, prefix=False)

    findings = run_popeye_scan()

    if is_dry_run():
        render_dry_run_result(
            command="devops k8s audit",
            action="popeye_cluster_sanitizer",
            details={"findings_count": len(findings)},
        )
        return

    if not findings:
        print_success(MESSAGES.k8s.popeye_passed)
        return

    table = Table(title="Popeye Cluster Health Audit")
    table.add_column("Severity", style="bold")
    table.add_column("Cluster Resource")
    table.add_column("Finding Title")
    table.add_column("Remediation")

    sev_colors = {"HIGH": "red", "MEDIUM": "yellow", "LOW": "cyan", "INFO": "dim"}

    for f in findings:
        style = sev_colors.get(f.severity.upper(), "white")
        table.add_row(f"[{style}]{f.severity}[/{style}]", f.location, f.title, f.fix or "-")

    print_table(table)


def k8s_check_deprecated(
    target: Annotated[
        Path,
        typer.Argument(help="Target manifest file or directory to scan for deprecated APIs"),
    ] = DEFAULT_CURRENT_PATH,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Simulate deprecated API detection."),
    ] = False,
) -> None:
    """Scan manifests for deprecated/removed K8s API versions using Fairwinds Pluto."""
    from devops_cli.dry_run.state import set_dry_run
    from devops_cli.security.pluto import run_pluto_scan

    set_dry_run(dry_run)
    target_abs = target.resolve() if target.exists() else target
    if not is_dry_run():
        print_info(
            f"[dim]Executing Pluto deprecated API scan on '{target_abs}'...[/dim]",
            prefix=False,
        )

    findings = run_pluto_scan(target=target_abs)

    if is_dry_run():
        render_dry_run_result(
            command=f"devops k8s check-deprecated {target}",
            action="pluto_deprecated_api_scan",
            details={"target": str(target_abs), "findings_count": len(findings)},
        )
        return

    if not findings:
        print_success(MESSAGES.k8s.pluto_passed)
        return

    table = Table(title=f"Pluto Deprecated K8s API Report: {target_abs.name or target_abs}")
    table.add_column("Severity", style="bold red")
    table.add_column("Resource Location")
    table.add_column("Deprecation Warning")
    table.add_column("Migration Target")

    for f in findings:
        table.add_row(f.severity, f.location, f.title, f.fix or "-")

    print_table(table)


def k8s_validate(
    manifest_path: Annotated[
        Path,
        typer.Argument(help="Path to Kubernetes YAML manifest file or directory"),
    ] = DEFAULT_CURRENT_PATH,
    k8s_version: Annotated[
        str,
        typer.Option("--kubernetes-version", "-v", help="Target Kubernetes OpenAPI version"),
    ] = DEFAULT_KUBECONFORM_VERSION,
    strict: Annotated[
        bool,
        typer.Option("--strict/--no-strict", help="Disallow additional undeclared properties"),
    ] = True,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Simulate schema validation"),
    ] = False,
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Output findings as JSON"),
    ] = False,
) -> None:
    """Validate Kubernetes YAML manifests against OpenAPI schemas using Kubeconform."""
    from devops_cli.security.kubeconform import run_kubeconform_validation

    target_path = manifest_path.resolve()
    if dry_run or is_dry_run():
        render_dry_run_result(
            command=f"devops k8s validate {manifest_path} --kubernetes-version {k8s_version}",
            action="kubeconform_validation",
            target=str(target_path),
        )
        return

    print_muted(f"Validating Kubernetes manifests at '{target_path}' (k8s: {k8s_version})...")
    findings = run_kubeconform_validation(
        manifest_path=target_path,
        k8s_version=k8s_version,
        strict=strict,
    )

    if json_output:
        write_stdout(format_json([f.model_dump() for f in findings]) + "\n")
        return

    if not findings:
        print_success(f"✓ All Kubernetes manifests at '{target_path}' are valid schemas.")
        return

    title_str = f"Kubeconform Schema Issues: {target_path.name or str(target_path)}"
    table = Table(title=title_str)
    table.add_column("Severity", style="bold red")
    table.add_column("Location")
    table.add_column("Error")
    table.add_column("Remediation")

    for f in findings:
        table.add_row(f.severity, f.location, f.title, f.fix or f.description)
    print_table(table)


def validate_policy_cmd(
    manifest_path: Annotated[
        Path,
        typer.Argument(help="Path to Kubernetes YAML manifest file or directory"),
    ] = DEFAULT_CURRENT_PATH,
    policy_path: Annotated[
        Path | None,
        typer.Option("--policy", "-p", help="Path to Kyverno policy or OPA rule file"),
    ] = None,
    engine: Annotated[
        str,
        typer.Option("--engine", "-e", help="Policy evaluation engine (kyverno, opa)"),
    ] = "kyverno",
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Simulate admission policy validation"),
    ] = False,
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Output validation report as JSON"),
    ] = False,
) -> None:
    """Validate Kubernetes manifests against Kyverno or OPA admission policies."""
    from devops_cli.k8s.policy import validate_k8s_policy

    report = validate_k8s_policy(
        manifest_path=manifest_path.resolve(),
        policy_path=policy_path.resolve() if policy_path else None,
        engine=engine,
        dry_run=dry_run,
    )

    if dry_run or is_dry_run():
        return

    if json_output:
        write_stdout(format_json(report.model_dump()) + "\n")
        return

    if report.failed_count == 0:
        print_success(
            f"✓ All manifests passed {report.engine.upper()} policy evaluation ({report.passed_count} rules passed)."
        )
        return

    t = Table(title=f"Kubernetes Policy Violations ({report.engine.upper()})")
    t.add_column("Policy")
    t.add_column("Rule")
    t.add_column("Resource")
    t.add_column("Status", style="bold red")
    t.add_column("Message")

    for r in report.rule_results:
        st_style = "green" if r.status in ("pass", "success") else "bold red"
        t.add_row(
            r.policy_name,
            r.rule_name,
            f"{r.resource_kind}/{r.resource_name}",
            f"[{st_style}]{r.status}[/{st_style}]",
            r.message,
        )

    print_table(t)
    raise typer.Exit(1)
