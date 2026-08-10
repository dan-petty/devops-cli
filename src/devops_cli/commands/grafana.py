"""Grafana management commands (httpx REST API)."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Annotated

import httpx2
import typer
from rich import print as rprint
from rich.console import Console
from rich.table import Table

from devops_cli.config.settings import Settings, get_grafana_token, load_settings
from devops_cli.core.cli import new_typer
from devops_cli.http.validation import validate_service_url
from devops_cli.models.grafana import GrafanaAlertRule, GrafanaDashboard, GrafanaDatasource

app = new_typer(help="Grafana dashboard and alert management.", no_args_is_help=True)
console = Console()

dashboards_app = new_typer(help="Manage Grafana dashboards.")
app.add_typer(dashboards_app, name="dashboards")


def _client_args(settings: Settings) -> tuple[str, dict[str, str]]:
    """Return (base_url, headers) for Grafana API requests."""
    if not settings.grafana.url:
        rprint("[red]Grafana URL not configured. Run: devops config set grafana.url <url>[/red]")
        raise typer.Exit(1)
    try:
        validate_service_url(
            settings.grafana.url, "Grafana", allow=settings.ai.allow_private_network
        )
    except ValueError as exc:
        rprint(f"[red]{exc}[/red]")
        raise typer.Exit(1)
    headers: dict[str, str] = {"Content-Type": "application/json"}
    token = get_grafana_token(settings)
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return settings.grafana.url.rstrip("/"), headers


# ── dashboards ────────────────────────────────────────────────────────────────


@dashboards_app.command("list")
def dashboards_list() -> None:
    """List all dashboards."""
    settings = load_settings()
    base, headers = _client_args(settings)

    with httpx2.Client() as http_client:
        response = http_client.get(
            f"{base}/api/search", headers=headers, params={"type": "dash-db"}, timeout=30
        )
        response.raise_for_status()

    table = Table(title="Grafana Dashboards")
    table.add_column("UID", style="dim")
    table.add_column("Title", style="cyan")
    table.add_column("Folder")

    for item in response.json():
        dash = GrafanaDashboard.model_validate(item)
        table.add_row(dash.uid, dash.title, dash.folder_title)
    console.print(table)


@dashboards_app.command("export")
def dashboards_export(
    uid: Annotated[str, typer.Argument(help="Dashboard UID")],
    output: Annotated[Path | None, typer.Option("--output", "-o")] = None,
) -> None:
    """Export a dashboard to JSON."""
    if not re.match(r"^[a-zA-Z0-9_-]+$", uid):
        rprint("[red]Invalid Dashboard UID: alphanumeric, hyphens, and underscores only.[/red]")
        raise typer.Exit(1)
    if output is not None:
        resolved = output.resolve()
        if not resolved.is_relative_to(Path.cwd().resolve()):
            rprint("[red]Invalid output path: path traversal not allowed.[/red]")
            raise typer.Exit(1)
    settings = load_settings()
    base, headers = _client_args(settings)

    with httpx2.Client() as http_client:
        response = http_client.get(f"{base}/api/dashboards/uid/{uid}", headers=headers, timeout=30)
        response.raise_for_status()

    dest = output or Path(f"{uid}.json")
    dest.write_text(json.dumps(response.json(), indent=2), encoding="utf-8")
    rprint(f"[green]Exported → {dest}[/green]")


@dashboards_app.command("import")
def dashboards_import(
    file: Annotated[Path, typer.Argument(help="Dashboard JSON file")],
    folder_id: Annotated[int, typer.Option("--folder-id")] = 0,
) -> None:
    """Import a dashboard from JSON."""
    settings = load_settings()
    base, headers = _client_args(settings)

    raw = json.loads(file.read_text(encoding="utf-8"))
    dashboard = raw.get("dashboard", raw)
    dashboard.pop("id", None)
    dashboard.pop("uid", None)

    with httpx2.Client() as http_client:
        response = http_client.post(
            f"{base}/api/dashboards/db",
            headers=headers,
            json={"dashboard": dashboard, "folderId": folder_id, "overwrite": True},
            timeout=30,
        )
        response.raise_for_status()
    rprint(f"[green]Imported:[/green] {response.json().get('slug', 'unknown')}")


# ── search & datasources ───────────────────────────────────────────────────────


@app.command()
def search(
    query: Annotated[str, typer.Option("--query", "-q", help="Search query")] = "",
) -> None:
    """Search Grafana dashboards and folders by query string."""
    settings = load_settings()
    base, headers = _client_args(settings)
    params = {"query": query} if query else {}

    with httpx2.Client() as http_client:
        response = http_client.get(f"{base}/api/search", headers=headers, params=params, timeout=30)
        response.raise_for_status()

    table = Table(title=f"Grafana Search: {query!r}" if query else "Grafana Search")
    table.add_column("UID", style="dim")
    table.add_column("Title", style="cyan")
    table.add_column("Type")
    table.add_column("Folder")

    for item in response.json():
        dash = GrafanaDashboard.model_validate(item)
        table.add_row(
            dash.uid,
            dash.title,
            item.get("type", ""),  # type is not on GrafanaDashboard — keep raw
            dash.folder_title,
        )
    console.print(table)


@app.command()
def datasources() -> None:
    """List configured datasources."""
    settings = load_settings()
    base, headers = _client_args(settings)

    with httpx2.Client() as http_client:
        response = http_client.get(f"{base}/api/datasources", headers=headers, timeout=30)
        response.raise_for_status()

    table = Table(title="Grafana Datasources")
    table.add_column("Name", style="cyan")
    table.add_column("Type")
    table.add_column("URL")
    table.add_column("Default", justify="center")

    for item in response.json():
        ds = GrafanaDatasource.model_validate(item)
        table.add_row(
            ds.name,
            ds.type,
            ds.url,
            "[green]●[/green]" if ds.is_default else "",
        )
    console.print(table)


# ── alerts ────────────────────────────────────────────────────────────────────


@app.command()
def alerts() -> None:
    """List alert rules (Grafana 9+ unified alerting)."""
    settings = load_settings()
    base, headers = _client_args(settings)

    with httpx2.Client() as http_client:
        response = http_client.get(
            f"{base}/api/v1/provisioning/alert-rules", headers=headers, timeout=30
        )
        response.raise_for_status()

    table = Table(title="Grafana Alert Rules")
    table.add_column("UID", style="dim")
    table.add_column("Title", style="cyan")
    table.add_column("Folder")
    table.add_column("Condition")

    for item in response.json():
        rule = GrafanaAlertRule.model_validate(item)
        table.add_row(rule.uid, rule.title, rule.folder_uid, rule.condition)
    console.print(table)
