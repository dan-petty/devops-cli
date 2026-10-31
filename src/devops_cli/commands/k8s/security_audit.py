"""Kubernetes RBAC auditing, manifest security linting, Popeye cluster sanitizing, Pluto deprecation checks, Kubeconform schema validation, and admission policy enforcement."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Annotated

import typer
from pydantic import BaseModel, ValidationError

import devops_cli.commands.k8s.cluster_runtime as runtime
from devops_cli.config.commands import BIN_KUBECTL
from devops_cli.config.constants import CONST_OUTPUT_FORMAT_TABLE
from devops_cli.config.defaults import (
    DEFAULT_CURRENT_PATH,
    DEFAULT_KUBECONFORM_VERSION,
    DEFAULT_TABLE_FORMAT,
)
from devops_cli.dry_run import dry_run_class, is_dry_run
from devops_cli.k8s.rbac import RbacBindingList, RbacRoleList, audit_rbac
from devops_cli.lang import ERRORS, HELP, MESSAGES
from devops_cli.output import (
    TableColumn,
    TablePayload,
    escape_text,
    format_k8s_lint_table,
    format_k8s_policy_table,
    format_k8s_rbac_table,
    format_k8s_schema_table,
    print,
    print_error,
    print_info,
    print_muted,
    print_success,
)
from devops_cli.output.serialization import emit_serialized, resolve_format


def _read_rbac[ListT: BaseModel](
    resources: str, namespace: str | None, as_list: type[ListT]
) -> ListT:
    """Read RBAC objects with a read-only `kubectl get`; exit 1 when they cannot be read."""
    scope = ["-n", namespace] if namespace else ["--all-namespaces"]
    cmd = [BIN_KUBECTL, "get", resources, "-o", "json", *scope]
    try:
        proc = runtime._run_cmd(cmd, check=False, capture=True)
        if proc.returncode == 0:
            return as_list.model_validate_json(proc.stdout)
        error = (proc.stderr or proc.stdout or f"exit code {proc.returncode}").strip()
    except (OSError, subprocess.SubprocessError, ValidationError) as exc:
        error = str(exc)
    print_error(
        ERRORS.k8s.resource_lookup_failed.format(resource=resources, exc=error[:256]), safe=True
    )
    raise typer.Exit(1)


@dry_run_class("request-plan")
def rbac_audit(
    namespace: Annotated[
        str | None, typer.Option("--namespace", "-n", help=HELP.k8s.rbac_namespace)
    ] = None,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help=HELP.options.dry_run),
    ] = False,
) -> None:
    """Audit RBAC RoleBindings and ServiceAccounts for overprivileged access."""
    if namespace:
        runtime._validate_k8s_identifier(namespace, "namespace", namespace=True)

    if dry_run or is_dry_run():
        from devops_cli.dry_run.requests import render_request_plan
        from devops_cli.k8s.cluster_plans import plan_k8s_rbac_audit

        requests = plan_k8s_rbac_audit(namespace=namespace)
        render_request_plan("devops k8s rbac-audit", requests)
        return

    bindings = _read_rbac("clusterrolebindings,rolebindings", namespace, RbacBindingList).items
    roles = _read_rbac("clusterroles,roles", namespace, RbacRoleList).items
    violations = audit_rbac(bindings, roles)
    if not violations:
        print_success(MESSAGES.k8s.rbac_audit_passed.format(bindings=len(bindings)))
        return

    rows = [
        [
            escape_text(v.namespace or MESSAGES.k8s.rbac_cluster_scope),
            escape_text(v.binding),
            escape_text(v.role),
            escape_text(v.subject),
            f"[red]FAIL[/red] {escape_text(v.reason)}",
        ]
        for v in violations
    ]
    print(format_k8s_rbac_table(rows))
    print_error(
        MESSAGES.k8s.rbac_audit_failed.format(violations=len(violations), bindings=len(bindings))
    )
    raise typer.Exit(1)


@dry_run_class("no-external-request")
def k8s_lint(
    target: Annotated[
        Path,
        typer.Argument(help=HELP.k8s.lint_target),
    ] = DEFAULT_CURRENT_PATH,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help=HELP.options.dry_run),
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
        return

    if findings.status != "ran":
        print_error(
            MESSAGES.k8s.kube_linter_not_run.format(status=findings.status, reason=findings.reason),
            safe=True,
        )
        raise typer.Exit(1)

    if not findings:
        print_success(MESSAGES.k8s.kube_linter_passed)
        return

    print(format_k8s_lint_table(findings, target_abs.name or str(target_abs)))
    raise typer.Exit(1)


@dry_run_class("request-plan")
def k8s_audit(
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help=HELP.options.dry_run),
    ] = False,
) -> None:
    """Sanitize active K8s/Minikube cluster resource health using Derailed Popeye."""
    if dry_run or is_dry_run():
        from devops_cli.dry_run.requests import render_request_plan
        from devops_cli.k8s.cluster_plans import plan_k8s_audit

        requests = plan_k8s_audit()
        render_request_plan("devops k8s audit", requests)
        return

    from devops_cli.security.popeye import run_popeye_scan

    print_info(MESSAGES.k8s.popeye_executing, prefix=False)
    findings = run_popeye_scan()

    if findings.status != "ran":
        print_error(
            MESSAGES.k8s.popeye_not_run.format(status=findings.status, reason=findings.reason),
            safe=True,
        )
        raise typer.Exit(1)

    if not findings:
        print_success(MESSAGES.k8s.popeye_passed)
        return

    columns: list[TableColumn | str | tuple[str, str | int]] = [
        TableColumn(header="Severity", style="bold"),
        TableColumn(header="Cluster Resource"),
        TableColumn(header="Finding Title"),
        TableColumn(header="Remediation"),
    ]
    sev_colors = {"HIGH": "red", "MEDIUM": "yellow", "LOW": "cyan", "INFO": "dim"}
    rows: list[list[str]] = []
    for finding in findings:
        style = sev_colors.get(finding.severity.upper(), "white")
        rows.append(
            [
                f"[{style}]{finding.severity}[/{style}]",
                finding.location,
                finding.title,
                finding.fix or "-",
            ]
        )

    print(TablePayload(title="Popeye Cluster Health Audit", columns=columns, rows=rows))


@dry_run_class("request-plan")
def k8s_check_deprecated(
    target: Annotated[
        Path,
        typer.Argument(help=HELP.k8s.pluto_target),
    ] = DEFAULT_CURRENT_PATH,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help=HELP.options.dry_run),
    ] = False,
) -> None:
    """Scan manifests for deprecated/removed K8s API versions using Fairwinds Pluto."""
    if dry_run or is_dry_run():
        from devops_cli.dry_run.requests import render_request_plan
        from devops_cli.k8s.manifest_plans import plan_k8s_check_deprecated

        requests = plan_k8s_check_deprecated(target)
        render_request_plan("devops k8s check-deprecated", requests)
        return

    from devops_cli.security.pluto import run_pluto_scan

    target_abs = target.resolve() if target.exists() else target
    print_info(
        f"[dim]Checking for deprecated Kubernetes APIs in '{target_abs}'...[/dim]", prefix=False
    )

    findings = run_pluto_scan(target=target_abs)

    if not findings:
        print_success(MESSAGES.k8s.pluto_passed)
        return

    columns: list[TableColumn | str | tuple[str, str | int]] = [
        TableColumn(header="Severity", style="bold red"),
        TableColumn(header="Resource Location"),
        TableColumn(header="Deprecation Warning"),
        TableColumn(header="Migration Target"),
    ]
    rows = [
        [finding.severity, finding.location, finding.title, finding.fix or "-"]
        for finding in findings
    ]
    print(
        TablePayload(
            title=f"Pluto Deprecated K8s API Report: {target_abs.name or target_abs}",
            columns=columns,
            rows=rows,
        )
    )


@dry_run_class("request-plan")
def k8s_validate(
    manifest_path: Annotated[
        Path,
        typer.Argument(help=HELP.k8s.manifest_path),
    ] = DEFAULT_CURRENT_PATH,
    k8s_version: Annotated[
        str,
        typer.Option("--kubernetes-version", "-v", help=HELP.k8s.k8s_version),
    ] = DEFAULT_KUBECONFORM_VERSION,
    strict: Annotated[
        bool,
        typer.Option("--strict/--no-strict", help=HELP.k8s.strict_schema),
    ] = True,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help=HELP.options.dry_run),
    ] = False,
    output_format: Annotated[
        str,
        typer.Option("--format", "-f", help=HELP.options.format_type),
    ] = DEFAULT_TABLE_FORMAT,
    json_output: Annotated[
        bool,
        typer.Option("--json", help=HELP.options.json_output),
    ] = False,
) -> None:
    """Validate Kubernetes YAML manifests against OpenAPI schemas using Kubeconform."""
    target_path = manifest_path.resolve()
    if dry_run or is_dry_run():
        from devops_cli.dry_run.requests import render_request_plan
        from devops_cli.k8s.manifest_plans import plan_k8s_validate

        requests = plan_k8s_validate(
            manifest_path=target_path,
            k8s_version=k8s_version,
            strict=strict,
        )
        render_request_plan("devops k8s validate", requests)
        return

    from devops_cli.security.kubeconform import run_kubeconform_validation

    print_muted(f"Validating Kubernetes manifests at '{target_path}' (k8s: {k8s_version})...")
    findings = run_kubeconform_validation(
        manifest_path=target_path,
        k8s_version=k8s_version,
        strict=strict,
    )

    if findings.status != "ran":
        print_error(
            MESSAGES.k8s.kubeconform_not_run.format(status=findings.status, reason=findings.reason),
            safe=True,
        )
        raise typer.Exit(1)

    resolved = resolve_format(output_format, json_output=json_output)
    if resolved != CONST_OUTPUT_FORMAT_TABLE:
        emit_serialized([f.model_dump() for f in findings], resolved)
        return

    if not findings:
        print_success(f"All Kubernetes manifests at '{target_path}' are valid schemas.")
        return

    print(format_k8s_schema_table(findings, target_path.name or str(target_path)))


@dry_run_class("no-external-request")
def validate_policy_cmd(
    manifest_path: Annotated[
        Path,
        typer.Argument(help=HELP.k8s.manifest_path),
    ] = DEFAULT_CURRENT_PATH,
    policy_path: Annotated[
        Path | None,
        typer.Option("--policy", "-p", help=HELP.k8s.policy_path),
    ] = None,
    engine: Annotated[
        str,
        typer.Option("--engine", "-e", help=HELP.k8s.policy_engine),
    ] = "kyverno",
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help=HELP.options.dry_run),
    ] = False,
    output_format: Annotated[
        str,
        typer.Option("--format", "-f", help=HELP.options.format_type),
    ] = DEFAULT_TABLE_FORMAT,
    json_output: Annotated[
        bool,
        typer.Option("--json", help=HELP.options.json_output),
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

    resolved = resolve_format(output_format, json_output=json_output)
    if resolved != CONST_OUTPUT_FORMAT_TABLE:
        emit_serialized(report.model_dump(), resolved)
        if report.failed_count > 0:
            raise typer.Exit(1)
        return

    if report.failed_count == 0:
        print_success(
            f"All manifests passed {report.engine.upper()} policy evaluation ({report.passed_count} rules passed)."
        )
        return

    print(format_k8s_policy_table(report))
    raise typer.Exit(1)
