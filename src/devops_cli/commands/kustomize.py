"""Kustomize command group (kubectl/kustomize CLI wrappers)."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Annotated

import typer

from devops_cli.config.defaults import DEFAULT_SUBPROCESS_TIMEOUT_SECONDS
from devops_cli.core.cli import new_typer

app = new_typer(help="Kustomize build and apply operations.", no_args_is_help=True)


@app.command()
def build(
    path: Annotated[Path, typer.Argument(help="Path to kustomization directory")] = Path("."),
    output: Annotated[
        str | None, typer.Option("--output", "-o", help="Output file or directory")
    ] = None,
) -> None:
    """Build kustomize overlays (delegates to kustomize build)."""
    cmd = ["kustomize", "build", str(path)]
    if output:
        cmd += ["--output", output]
    subprocess.run(cmd, check=True, timeout=DEFAULT_SUBPROCESS_TIMEOUT_SECONDS)


@app.command()
def diff(
    path: Annotated[Path, typer.Argument(help="Path to kustomization directory")] = Path("."),
) -> None:
    """Show a diff of pending changes (delegates to kubectl diff -k)."""
    # kubectl diff returns exit code 1 when diffs exist; don't treat that as error
    subprocess.run(["kubectl", "diff", "-k", str(path)], timeout=DEFAULT_SUBPROCESS_TIMEOUT_SECONDS)


@app.command()
def apply(
    path: Annotated[Path, typer.Argument(help="Path to kustomization directory")] = Path("."),
    dry_run: Annotated[bool, typer.Option("--dry-run")] = False,
    namespace: Annotated[str | None, typer.Option("--namespace", "-n")] = None,
) -> None:
    """Apply a kustomization (delegates to kubectl apply -k)."""
    if namespace:
        from devops_cli.commands.k8s import _validate_k8s_identifier

        _validate_k8s_identifier(namespace, "namespace", namespace=True)
    cmd = ["kubectl", "apply", "-k", str(path)]
    if dry_run:
        cmd += ["--dry-run=client"]
    if namespace:
        cmd += ["--namespace", namespace]
    subprocess.run(cmd, check=True, timeout=DEFAULT_SUBPROCESS_TIMEOUT_SECONDS)
