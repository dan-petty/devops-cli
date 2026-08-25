"""Grafana management commands (httpx REST API)."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Annotated

import httpx2
import typer
from rich.table import Table

from devops_cli.config.constants import CONST_MAX_FILE_SIZE_BYTES
from devops_cli.config.defaults import DEFAULT_HTTP_REQUEST_TIMEOUT_SECONDS
from devops_cli.config.settings import Settings, get_grafana_token, load_settings
from devops_cli.core.cli import new_typer
from devops_cli.dry_run import is_dry_run, render_dry_run_result
from devops_cli.http.validation import validate_service_url
from devops_cli.models.grafana import GrafanaAlertRule, GrafanaDashboard, GrafanaDatasource
from devops_cli.output import (
    print_error,
    print_success,
    print_table,
    print_warning,
    write_json_file,
)

app = new_typer(help="Grafana dashboard and alert management.", no_args_is_help=True)

dashboards_app = new_typer(help="Manage Grafana dashboards.")
app.add_typer(dashboards_app, name="dashboards")


# =============================================================================
# Grafana Client Arguments Helper
# =============================================================================


def _client_args(settings: Settings) -> tuple[str, dict[str, str]]:
    """Return (base_url, headers) for Grafana API requests."""
    if not settings.grafana.url:
        print_error(
            "Grafana URL not configured. Run: devops config set grafana.url <url>",
            prefix=False,
        )
        raise typer.Exit(1)
    try:
        validate_service_url(
            settings.grafana.url, "Grafana", allow=settings.ai.allow_private_network
        )
    except ValueError as exc:
        print_error(str(exc), prefix=False)
        raise typer.Exit(1)
    headers: dict[str, str] = {"Content-Type": "application/json"}
    token = get_grafana_token(settings)
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return settings.grafana.url.rstrip("/"), headers


# =============================================================================
# Command: devops grafana dashboards list
# =============================================================================


@dashboards_app.command("list")
def dashboards_list() -> None:
    """List all dashboards."""
    if is_dry_run():
        render_dry_run_result(
            command="devops grafana dashboards list",
            action="list_grafana_dashboards",
            details={"dashboards": []},
        )
        return

    settings = load_settings()
    base, headers = _client_args(settings)

    with httpx2.Client() as http_client:
        response = http_client.get(
            f"{base}/api/search",
            headers=headers,
            params={"type": "dash-db"},
            timeout=DEFAULT_HTTP_REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()

    table = Table(title="Grafana Dashboards")
    table.add_column("UID", style="dim")
    table.add_column("Title", style="cyan")
    table.add_column("Folder")

    for item in response.json():
        dash = GrafanaDashboard.model_validate(item)
        table.add_row(dash.uid, dash.title, dash.folder_title)
    print_table(table)


# =============================================================================
# Command: devops grafana dashboards export
# =============================================================================


@dashboards_app.command("export")
def dashboards_export(
    uid: Annotated[str, typer.Argument(help="Dashboard UID")],
    output: Annotated[Path | None, typer.Option("--output", "-o")] = None,
) -> None:
    """Export a dashboard to JSON."""
    if not re.match(r"^[a-zA-Z0-9_-]+$", uid):
        print_error(
            "Invalid Dashboard UID: alphanumeric, hyphens, and underscores only.",
            prefix=False,
        )
        raise typer.Exit(1)
    if output is not None:
        resolved = output.resolve()
        if not resolved.is_relative_to(Path.cwd().resolve()):
            print_error("Invalid output path: path traversal not allowed.", prefix=False)
            raise typer.Exit(1)
    settings = load_settings()
    base, headers = _client_args(settings)

    with httpx2.Client() as http_client:
        response = http_client.get(
            f"{base}/api/dashboards/uid/{uid}",
            headers=headers,
            timeout=DEFAULT_HTTP_REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()

    dest = output or Path(f"{uid}.json")
    write_json_file(dest, response.json())
    print_success(f"Exported → {dest}")


# =============================================================================
# Command: devops grafana dashboards import
# =============================================================================


@dashboards_app.command("import")
def dashboards_import(
    file: Annotated[Path, typer.Argument(help="Dashboard JSON file")],
    folder_id: Annotated[int, typer.Option("--folder-id")] = 0,
) -> None:
    """Import a dashboard from JSON."""
    settings = load_settings()
    base, headers = _client_args(settings)

    if file.stat().st_size > CONST_MAX_FILE_SIZE_BYTES:
        print_error(
            f"File '{file}' exceeds maximum allowed size ({CONST_MAX_FILE_SIZE_BYTES} bytes).",
            prefix=False,
        )
        raise typer.Exit(1)

    try:
        raw = json.loads(file.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        print_error(f"Failed to parse dashboard JSON file '{file}': {exc}", prefix=False)
        raise typer.Exit(1)

    if not isinstance(raw, dict):
        print_error(f"Invalid dashboard JSON in '{file}': expected JSON object.", prefix=False)
        raise typer.Exit(1)

    dashboard = raw.get("dashboard", raw)
    if isinstance(dashboard, dict):
        dashboard.pop("id", None)
        dashboard.pop("uid", None)

    if is_dry_run():
        title = dashboard.get("title", "<unknown>") if isinstance(dashboard, dict) else "<unknown>"
        render_dry_run_result(
            command="devops grafana dashboards import",
            target=str(file),
            action="import_dashboard",
            details={"folder_id": folder_id, "title": title},
        )
        return

    with httpx2.Client() as http_client:
        response = http_client.post(
            f"{base}/api/dashboards/db",
            headers=headers,
            json={"dashboard": dashboard, "folderId": folder_id, "overwrite": True},
            timeout=DEFAULT_HTTP_REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
    print_success(f"Imported: {response.json().get('slug', 'unknown')}")


# =============================================================================
# Command: devops grafana dashboards sync
# =============================================================================


@dashboards_app.command("sync")
def dashboards_sync(
    dir_path: Annotated[
        Path | None,
        typer.Option("--dir", "-d", help="Directory containing dashboard JSON files"),
    ] = None,
) -> None:
    """Sync all bundled/local dashboards to Grafana."""
    search_dir = dir_path or Path("k8s/monitoring/dashboards")
    if not search_dir.exists():
        print_warning(f"Dashboard directory '{search_dir}' not found.", prefix=False)
        raise typer.Exit(1)

    json_files = sorted(search_dir.glob("*.json"))
    if not json_files:
        print_warning(f"No dashboard JSON files found in '{search_dir}'.", prefix=False)
        return

    if is_dry_run():
        render_dry_run_result(
            command="devops grafana dashboards sync",
            target=str(search_dir),
            action="sync_dashboards",
            details={"files": [f.name for f in json_files]},
        )
        return

    settings = load_settings()
    base, headers = _client_args(settings)

    success_count = 0
    with httpx2.Client() as http_client:
        for dash_file in json_files:
            try:
                raw = json.loads(dash_file.read_text(encoding="utf-8"))
                dashboard = raw.get("dashboard", raw)
                title = dashboard.get("title", dash_file.stem)
                response = http_client.post(
                    f"{base}/api/dashboards/db",
                    headers=headers,
                    json={"dashboard": dashboard, "overwrite": True},
                    timeout=DEFAULT_HTTP_REQUEST_TIMEOUT_SECONDS,
                )
                response.raise_for_status()
                print_success(f"Synced dashboard: [bold]{title}[/bold] ({dash_file.name})")
                success_count += 1
            except Exception as exc:
                print_error(f"Failed to sync '{dash_file.name}': {exc}", prefix=False)

    print_success(
        f"Dashboard sync completed: {success_count}/{len(json_files)} synced successfully."
    )


# =============================================================================
# Command: devops grafana search
# =============================================================================


@app.command()
def search(
    query: Annotated[str, typer.Option("--query", "-q", help="Search query")] = "",
) -> None:
    """Search Grafana dashboards and folders by query string."""
    settings = load_settings()
    base, headers = _client_args(settings)
    params = {"query": query} if query else {}

    with httpx2.Client() as http_client:
        response = http_client.get(
            f"{base}/api/search",
            headers=headers,
            params=params,
            timeout=DEFAULT_HTTP_REQUEST_TIMEOUT_SECONDS,
        )
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
    print_table(table)


# =============================================================================
# Command: devops grafana datasources
# =============================================================================


@app.command()
def datasources() -> None:
    """List configured datasources."""
    settings = load_settings()
    base, headers = _client_args(settings)

    with httpx2.Client() as http_client:
        response = http_client.get(
            f"{base}/api/datasources",
            headers=headers,
            timeout=DEFAULT_HTTP_REQUEST_TIMEOUT_SECONDS,
        )
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
    print_table(table)


# =============================================================================
# Command: devops grafana alerts
# =============================================================================


@app.command()
def alerts() -> None:
    """List alert rules (Grafana 9+ unified alerting)."""
    settings = load_settings()
    base, headers = _client_args(settings)

    with httpx2.Client() as http_client:
        response = http_client.get(
            f"{base}/api/v1/provisioning/alert-rules",
            headers=headers,
            timeout=DEFAULT_HTTP_REQUEST_TIMEOUT_SECONDS,
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
    print_table(table)
