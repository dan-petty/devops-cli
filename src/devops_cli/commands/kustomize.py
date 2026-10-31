"""Kustomize command group (kubectl/kustomize CLI wrappers)."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from devops_cli.config.commands import (
    build_kubectl_cmd,
    build_kustomize_build_cmd,
)
from devops_cli.config.defaults import (
    DEFAULT_CURRENT_PATH,
    DEFAULT_SUBPROCESS_TIMEOUT_SECONDS,
)
from devops_cli.core.cli import new_typer
from devops_cli.core.process import run_subprocess
from devops_cli.core.validation import validate_path
from devops_cli.dry_run import dry_run_class, is_dry_run
from devops_cli.lang import HELP

app = new_typer(help=HELP.kustomize.app, no_args_is_help=True)


@app.command(help=HELP.kustomize.build)
@dry_run_class("request-plan")
def build(
    path: Annotated[Path, typer.Argument(help=HELP.kustomize.target_dir)] = DEFAULT_CURRENT_PATH,
    output: Annotated[
        str | None, typer.Option("--output", "-o", help=HELP.kustomize.output)
    ] = None,
    dry_run: Annotated[bool, typer.Option("--dry-run", help=HELP.options.dry_run)] = False,
) -> None:
    """Build kustomize overlays (delegates to kustomize build)."""
    if dry_run or is_dry_run():
        from devops_cli.dry_run.requests import render_request_plan
        from devops_cli.k8s.manifest_plans import plan_kustomize_build

        requests = plan_kustomize_build(path=path, output=output)
        render_request_plan("devops kustomize build", requests)
        return

    target = validate_path(path)
    cmd = build_kustomize_build_cmd(target)
    if output:
        cmd += ["--output", output]
    run_subprocess(
        cmd, check=True, timeout=DEFAULT_SUBPROCESS_TIMEOUT_SECONDS, capture_output=False
    )


@app.command(help=HELP.kustomize.diff)
@dry_run_class("request-plan")
def diff(
    path: Annotated[Path, typer.Argument(help=HELP.kustomize.target_dir)] = DEFAULT_CURRENT_PATH,
    dry_run: Annotated[bool, typer.Option("--dry-run", help=HELP.options.dry_run)] = False,
) -> None:
    """Show a diff of pending changes (delegates to kubectl diff -k)."""
    if dry_run or is_dry_run():
        from devops_cli.dry_run.requests import render_request_plan
        from devops_cli.k8s.manifest_plans import plan_kustomize_diff

        requests = plan_kustomize_diff(path=path)
        render_request_plan("devops kustomize diff", requests)
        return

    target = validate_path(path)
    cmd = build_kubectl_cmd(["diff", "-k", str(target)])
    run_subprocess(cmd, timeout=DEFAULT_SUBPROCESS_TIMEOUT_SECONDS, capture_output=False)


@app.command(help=HELP.kustomize.apply)
@dry_run_class("request-plan")
def apply(
    path: Annotated[Path, typer.Argument(help=HELP.kustomize.target_dir)] = DEFAULT_CURRENT_PATH,
    dry_run: Annotated[bool, typer.Option("--dry-run", help=HELP.options.dry_run)] = False,
    namespace: Annotated[
        str | None, typer.Option("--namespace", "-n", help=HELP.options.namespace)
    ] = None,
    template: Annotated[
        bool, typer.Option("--template", "-t", help=HELP.k8s.template_flag)
    ] = False,
    domain: Annotated[
        str | None, typer.Option("--domain", "-d", help=HELP.k8s.template_domain)
    ] = None,
) -> None:
    """Apply a kustomization (delegates to kubectl apply -k)."""
    if namespace:
        from devops_cli.commands.k8s import _validate_k8s_identifier

        _validate_k8s_identifier(namespace, "namespace", namespace=True)

    if dry_run or is_dry_run():
        from devops_cli.dry_run.requests import render_request_plan
        from devops_cli.k8s.manifest_plans import plan_kustomize_apply

        requests = plan_kustomize_apply(
            path=path,
            namespace=namespace,
            template=template,
            domain=domain,
        )
        render_request_plan("devops kustomize apply", requests)
        return

    target = validate_path(path)
    if template or domain is not None:
        from devops_cli.k8s.template import render_manifest_path, resolve_template_domain

        effective_domain = resolve_template_domain(domain)
        rendered_yaml = render_manifest_path(target, domain=effective_domain)
        k_args = ["apply", "-f", "-"]
        if namespace:
            k_args.extend(["--namespace", namespace])
        cmd = build_kubectl_cmd(k_args)
        run_subprocess(
            cmd,
            input=rendered_yaml,
            check=True,
            timeout=DEFAULT_SUBPROCESS_TIMEOUT_SECONDS,
            capture_output=False,
        )
        return

    k_args = ["apply", "-k", str(target)]
    if namespace:
        k_args.extend(["--namespace", namespace])
    cmd = build_kubectl_cmd(k_args)
    run_subprocess(
        cmd, check=True, timeout=DEFAULT_SUBPROCESS_TIMEOUT_SECONDS, capture_output=False
    )
