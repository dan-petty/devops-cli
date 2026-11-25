"""`devops k8s catalog`: generate and check the Kubernetes service catalog (#5535)."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from devops_cli.dry_run import dry_run_class, is_dry_run, set_dry_run
from devops_cli.dry_run.requests import PlannedRequest, render_request_plan
from devops_cli.exceptions.k8s import CatalogError
from devops_cli.k8s.catalog import (
    CATALOG_MD_NAME,
    build_catalog,
    collect_catalog_charts,
    render_catalog_markdown,
)
from devops_cli.k8s.environment import resolve_environment
from devops_cli.lang import HELP
from devops_cli.output import print_error, print_info, print_success
from devops_cli.output.serialization import emit_serialized

_FORMAT_MARKDOWN = "markdown"
_FORMAT_JSON = "json"
_VALID_FORMATS = (_FORMAT_MARKDOWN, _FORMAT_JSON)


def _render_dry_run(k8s_dir: Path | None) -> None:
    """List every chart that a catalog run would pull without executing helm or requests."""
    env = resolve_environment(k8s_dir)
    charts = collect_catalog_charts(env)
    requests = [
        PlannedRequest(
            method="helm",
            target=f"{chart.repo_url} {chart.chart}:{chart.version}",
            argv=(
                "helm",
                "template",
                chart.application,
                chart.chart,
                "--repo",
                chart.repo_url,
                "--version",
                chart.version,
            ),
        )
        for chart in charts
    ]
    render_request_plan(
        heading=f"Catalog plan for {env.root} ({len(charts)} chart(s)):",
        requests=requests,
        notes=(f"Would write {env.path(CATALOG_MD_NAME)}.",),
    )


@dry_run_class("request-plan")
def k8s_catalog(
    k8s_dir: Annotated[Path | None, typer.Option("--k8s-dir", help=HELP.k8s.k8s_dir)] = None,
    check: Annotated[bool, typer.Option("--check", help=HELP.k8s.catalog_check)] = False,
    output_format: Annotated[
        str, typer.Option("--format", help=HELP.k8s.catalog_format)
    ] = _FORMAT_MARKDOWN,
    dry_run: Annotated[bool, typer.Option("--dry-run", help=HELP.options.dry_run)] = False,
) -> None:
    """Build or check the Kubernetes service catalog from rendered Applications (#5535)."""
    fmt = output_format.strip().lower()
    if fmt not in _VALID_FORMATS:
        print_error(
            f"Invalid --format '{output_format}'. Expected one of: {', '.join(_VALID_FORMATS)}.",
            prefix=False,
        )
        raise typer.Exit(1)

    set_dry_run(dry_run or is_dry_run())
    if is_dry_run():
        _render_dry_run(k8s_dir)
        return

    env = resolve_environment(k8s_dir)
    catalog = build_catalog(env)

    if fmt == _FORMAT_JSON:
        emit_serialized(catalog.to_dict(), _FORMAT_JSON)
        return

    rendered = render_catalog_markdown(catalog)
    target = env.path(CATALOG_MD_NAME)
    if check:
        existing = target.read_text(encoding="utf-8") if target.is_file() else None
        if existing != rendered:
            raise CatalogError(
                f"{target} is missing or out of date; run `uv run devops k8s catalog`."
            )
        print_success(f"{target} matches rendered Applications.")
        return

    target.write_text(rendered, encoding="utf-8")
    print_info(f"Wrote {target} ({len(catalog.services)} services).", prefix=False)


__all__ = ["k8s_catalog"]
