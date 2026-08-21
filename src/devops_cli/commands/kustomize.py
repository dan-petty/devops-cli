"""Kustomize command group (kubectl/kustomize CLI wrappers)."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Annotated

import rich
import typer

from devops_cli.config.commands import (
    build_kubectl_cmd,
    build_kustomize_build_cmd,
)
from devops_cli.config.defaults import DEFAULT_SUBPROCESS_TIMEOUT_SECONDS
from devops_cli.core.cli import new_typer

app = new_typer(help="Kustomize build and apply operations.", no_args_is_help=True)


def _validate_path(path: Path) -> Path:
    resolved = path.resolve()
    if not resolved.exists():
        rich.print(f"[red]Path '{path}' does not exist.[/red]")
        raise typer.Exit(1)
    return resolved


@app.command()
def build(
    path: Annotated[Path, typer.Argument(help="Path to kustomization directory")] = Path("."),
    output: Annotated[
        str | None, typer.Option("--output", "-o", help="Output file or directory")
    ] = None,
) -> None:
    """Build kustomize overlays (delegates to kustomize build)."""
    target = _validate_path(path)
    cmd = build_kustomize_build_cmd(target)
    if output:
        cmd += ["--output", output]
    subprocess.run(cmd, check=True, timeout=DEFAULT_SUBPROCESS_TIMEOUT_SECONDS)


@app.command()
def diff(
    path: Annotated[Path, typer.Argument(help="Path to kustomization directory")] = Path("."),
) -> None:
    """Show a diff of pending changes (delegates to kubectl diff -k)."""
    target = _validate_path(path)
    cmd = build_kubectl_cmd(["diff", "-k", str(target)])
    subprocess.run(cmd, timeout=DEFAULT_SUBPROCESS_TIMEOUT_SECONDS)


@app.command()
def apply(
    path: Annotated[Path, typer.Argument(help="Path to kustomization directory")] = Path("."),
    dry_run: Annotated[bool, typer.Option("--dry-run")] = False,
    namespace: Annotated[str | None, typer.Option("--namespace", "-n")] = None,
) -> None:
    """Apply a kustomization (delegates to kubectl apply -k)."""
    target = _validate_path(path)
    if namespace:
        from devops_cli.commands.k8s import _validate_k8s_identifier

        _validate_k8s_identifier(namespace, "namespace", namespace=True)
    k_args = ["apply", "-k", str(target)]
    if dry_run:
        k_args.append("--dry-run=client")
    if namespace:
        k_args.extend(["--namespace", namespace])
    cmd = build_kubectl_cmd(k_args)
    subprocess.run(cmd, check=True, timeout=DEFAULT_SUBPROCESS_TIMEOUT_SECONDS)
