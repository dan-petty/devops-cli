"""Grafana management commands (httpx REST API)."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Annotated

import httpx2
import typer

from devops_cli.config.constants import CONST_MAX_FILE_SIZE_BYTES
from devops_cli.config.defaults import (
    DEFAULT_GRAFANA_FOLDER_ID,
    DEFAULT_HTTP_REQUEST_TIMEOUT_SECONDS,
)
from devops_cli.config.settings import Settings, get_grafana_token, load_settings
from devops_cli.core.cli import new_typer
from devops_cli.dry_run import is_dry_run, render_dry_run_result
from devops_cli.http.validation import validate_service_url
from devops_cli.lang import ERRORS, HELP, MESSAGES
from devops_cli.models.grafana import GrafanaAlertRule, GrafanaDashboard, GrafanaDatasource
from devops_cli.output import (
    print_error,
    print_success,
    print_table,
    print_warning,
    write_json_file,
)

app = new_typer(help=HELP.grafana.app, no_args_is_help=True)

dashboards_app = new_typer(help=HELP.grafana.dashboards)
app.add_typer(dashboards_app, name="dashboards")


# =============================================================================
# Grafana Client Arguments Helper
# =============================================================================


def _client_args(settings: Settings) -> tuple[str, dict[str, str]]:
    """Return (base_url, headers) for Grafana API requests."""
    if not settings.grafana.url:
        print_error(
            MESSAGES.grafana.url_not_configured,
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

    rows: list[list[str]] = []
    for item in response.json():
        dash = GrafanaDashboard.model_validate(item)
        rows.append([dash.uid, dash.title, dash.folder_title])
    print_table(
        title=MESSAGES.grafana.table_title_dashboards,
        columns=[("UID", "dim"), ("Title", "cyan"), "Folder"],
        rows=rows,
    )


# =============================================================================
# Command: devops grafana dashboards export
# =============================================================================


@dashboards_app.command("export")
def dashboards_export(
    uid: Annotated[str, typer.Argument(help=HELP.grafana.uid)],
    output: Annotated[Path | None, typer.Option("--output", "-o", help=HELP.options.output)] = None,
) -> None:
    """Export a dashboard to JSON."""
    if not re.match(r"^[a-zA-Z0-9_-]+$", uid):
        print_error(
            ERRORS.grafana.invalid_uid,
            prefix=False,
        )
        raise typer.Exit(1)
    if output is not None:
        resolved = output.resolve()
        if not resolved.is_relative_to(Path.cwd().resolve()):
            print_error(ERRORS.grafana.invalid_output_path, prefix=False)
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
    print_success(MESSAGES.grafana.exported_success.format(dest=dest))


# =============================================================================
# Command: devops grafana dashboards import
# =============================================================================


@dashboards_app.command("import")
def dashboards_import(
    file: Annotated[Path, typer.Argument(help=HELP.grafana.import_file)],
    folder_id: Annotated[
        int, typer.Option("--folder-id", help=HELP.grafana.folder_id)
    ] = DEFAULT_GRAFANA_FOLDER_ID,
) -> None:
    """Import a dashboard from JSON."""
    settings = load_settings()
    base, headers = _client_args(settings)

    if file.stat().st_size > CONST_MAX_FILE_SIZE_BYTES:
        print_error(
            ERRORS.grafana.file_too_large.format(path=file, max_bytes=CONST_MAX_FILE_SIZE_BYTES),
            prefix=False,
        )
        raise typer.Exit(1)

    try:
        raw = json.loads(file.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        print_error(ERRORS.grafana.parse_failed.format(path=file, exc=exc), prefix=False)
        raise typer.Exit(1)

    if not isinstance(raw, dict):
        print_error(ERRORS.grafana.invalid_json_object.format(path=file), prefix=False)
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
    print_success(
        MESSAGES.grafana.imported_success.format(slug=response.json().get("slug", "unknown"))
    )


# =============================================================================
# Command: devops grafana dashboards sync
# =============================================================================


@dashboards_app.command("sync")
def dashboards_sync(
    dir_path: Annotated[
        Path | None,
        typer.Option("--dir", "-d", help=HELP.grafana.dashboards_dir),
    ] = None,
) -> None:
    """Sync all bundled/local dashboards to Grafana."""
    search_dir = dir_path or Path("k8s/monitoring/dashboards")
    if not search_dir.exists():
        print_warning(MESSAGES.grafana.dir_not_found.format(path=search_dir), prefix=False)
        raise typer.Exit(1)

    json_files = sorted(search_dir.glob("*.json"))
    if not json_files:
        print_warning(MESSAGES.grafana.no_json_files.format(path=search_dir), prefix=False)
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
                print_success(
                    MESSAGES.grafana.synced_dashboard.format(title=title, file=dash_file.name)
                )
                success_count += 1
            except Exception as exc:
                print_error(
                    ERRORS.grafana.sync_failed.format(file=dash_file.name, exc=exc), prefix=False
                )

    print_success(
        MESSAGES.grafana.sync_completed.format(synced=success_count, total=len(json_files))
    )


# =============================================================================
# Command: devops grafana search
# =============================================================================


@app.command()
def search(
    query: Annotated[str, typer.Option("--query", "-q", help=HELP.grafana.query)] = "",
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

    rows: list[list[str]] = []
    for item in response.json():
        dash = GrafanaDashboard.model_validate(item)
        rows.append(
            [
                dash.uid,
                dash.title,
                item.get("type", ""),  # type is not on GrafanaDashboard — keep raw
                dash.folder_title,
            ]
        )
    print_table(
        title=MESSAGES.grafana.table_title_search.format(query=query)
        if query
        else "Grafana Search",
        columns=[("UID", "dim"), ("Title", "cyan"), "Type", "Folder"],
        rows=rows,
    )


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

    rows: list[list[str]] = []
    for item in response.json():
        ds = GrafanaDatasource.model_validate(item)
        rows.append(
            [
                ds.name,
                ds.type,
                ds.url,
                "[green]●[/green]" if ds.is_default else "",
            ]
        )
    print_table(
        title=MESSAGES.grafana.table_title_datasources,
        columns=[("Name", "cyan"), "Type", "URL", ("Default", "center")],
        rows=rows,
    )


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

    rows: list[list[str]] = []
    for item in response.json():
        rule = GrafanaAlertRule.model_validate(item)
        rows.append([rule.uid, rule.title, rule.folder_uid, rule.condition])
    print_table(
        title=MESSAGES.grafana.table_title_alerts,
        columns=[("UID", "dim"), ("Title", "cyan"), "Folder", "Condition"],
        rows=rows,
    )
