"""CLI command to generate gitignored .argocd-source.yaml overrides for local development."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from devops_cli.config.defaults import DEFAULT_K8S_DIR
from devops_cli.config.settings import load_settings
from devops_cli.exceptions.k8s import KubernetesContextError
from devops_cli.k8s.argocd_source import (
    _locate_configmap_template,
    generate_argocd_source,
    render_argocd_source_content,
)
from devops_cli.lang import HELP
from devops_cli.output import print_error, print_success


def argocd_source(
    k8s_dir: Annotated[Path, typer.Option("--k8s-dir", help=HELP.k8s.k8s_dir)] = DEFAULT_K8S_DIR,
    domain: Annotated[
        str | None, typer.Option("--domain", "-d", help=HELP.k8s.template_domain)
    ] = None,
    dry_run: Annotated[
        bool, typer.Option("--dry-run", help=HELP.k8s.argocd_source_dry_run)
    ] = False,
) -> None:
    """Generate gitignored .argocd-source.yaml with local development overrides."""
    try:
        if dry_run:
            template_path = _locate_configmap_template(k8s_dir.resolve())
            rendered = render_argocd_source_content(
                template_path.read_text(encoding="utf-8"),
                settings=load_settings(),
                domain=domain,
            )
            typer.echo(rendered)
            return

        written = generate_argocd_source(k8s_dir=k8s_dir, domain=domain)
        targets_str = ", ".join(str(p) for p in written)
        print_success(f"Generated {len(written)} Argo CD source override file(s): {targets_str}")
    except (FileNotFoundError, KubernetesContextError) as exc:
        print_error(f"Failed to generate Argo CD source overrides: {exc}")
        raise typer.Exit(1) from exc
