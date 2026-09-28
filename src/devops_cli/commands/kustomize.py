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
from devops_cli.lang import HELP

app = new_typer(help=HELP.kustomize.app, no_args_is_help=True)


@app.command(help=HELP.kustomize.build)
def build(
    path: Annotated[Path, typer.Argument(help=HELP.kustomize.target_dir)] = DEFAULT_CURRENT_PATH,
    output: Annotated[
        str | None, typer.Option("--output", "-o", help=HELP.kustomize.output)
    ] = None,
) -> None:
    """Build kustomize overlays (delegates to kustomize build)."""
    target = validate_path(path)
    cmd = build_kustomize_build_cmd(target)
    if output:
        cmd += ["--output", output]
    run_subprocess(
        cmd, check=True, timeout=DEFAULT_SUBPROCESS_TIMEOUT_SECONDS, capture_output=False
    )


@app.command(help=HELP.kustomize.diff)
def diff(
    path: Annotated[Path, typer.Argument(help=HELP.kustomize.target_dir)] = DEFAULT_CURRENT_PATH,
) -> None:
    """Show a diff of pending changes (delegates to kubectl diff -k)."""
    target = validate_path(path)
    cmd = build_kubectl_cmd(["diff", "-k", str(target)])
    run_subprocess(cmd, timeout=DEFAULT_SUBPROCESS_TIMEOUT_SECONDS, capture_output=False)


@app.command(help=HELP.kustomize.apply)
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
    target = validate_path(path)
    if namespace:
        from devops_cli.commands.k8s import _validate_k8s_identifier

        _validate_k8s_identifier(namespace, "namespace", namespace=True)

    if template or domain is not None:
        from devops_cli.k8s.template import render_manifest_path, resolve_template_domain

        effective_domain = resolve_template_domain(domain)
        rendered_yaml = render_manifest_path(target, domain=effective_domain)
        k_args = ["apply", "-f", "-"]
        if dry_run:
            k_args.append("--dry-run=client")
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
    if dry_run:
        k_args.append("--dry-run=client")
    if namespace:
        k_args.extend(["--namespace", namespace])
    cmd = build_kubectl_cmd(k_args)
    run_subprocess(
        cmd, check=True, timeout=DEFAULT_SUBPROCESS_TIMEOUT_SECONDS, capture_output=False
    )
