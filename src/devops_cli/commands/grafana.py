"""Grafana management commands (httpx REST API)."""

from __future__ import annotations

import json
import re
from collections import Counter
from http import HTTPStatus
from pathlib import Path
from typing import Annotated, Any
from urllib.parse import quote

import httpx2
import typer

from devops_cli.config.constants import (
    CONST_MAX_FILE_SIZE_BYTES,
    CONST_OUTPUT_FORMAT_TABLE,
)
from devops_cli.config.defaults import (
    DEFAULT_GRAFANA_DASHBOARDS_DIR,
    DEFAULT_GRAFANA_FOLDER_ID,
    DEFAULT_HTTP_TIMEOUT_SECONDS,
    DEFAULT_TABLE_FORMAT,
)
from devops_cli.config.settings import Settings, get_grafana_token, load_settings
from devops_cli.core.cli import new_typer
from devops_cli.dry_run import dry_run_class, is_dry_run
from devops_cli.dry_run.requests import render_request_plan
from devops_cli.exceptions import SSRFBlockedError
from devops_cli.grafana.grafana_plans import (
    plan_grafana_alerts,
    plan_grafana_dashboards_export,
    plan_grafana_dashboards_import,
    plan_grafana_dashboards_list,
    plan_grafana_dashboards_sync,
    plan_grafana_datasources,
    plan_grafana_search,
)
from devops_cli.http.client import new_http_client
from devops_cli.http.egress import configured_level
from devops_cli.http.urls import service_base_url
from devops_cli.lang import ERRORS, HELP, MESSAGES
from devops_cli.models.grafana import (
    DashboardLintReport,
    DashboardSyncOutcome,
    GrafanaAlertRule,
    GrafanaDashboard,
    GrafanaDashboardDetail,
    GrafanaDatasource,
)
from devops_cli.output import (
    print_error,
    print_info,
    print_success,
    print_table,
    print_warning,
    write_json_file,
)
from devops_cli.output.serialization import emit_serialized, resolve_format

# A refusal at the connect ends each command with its message and no traceback.
app = new_typer(help=HELP.grafana.app, no_args_is_help=True)

dashboards_app = new_typer(help=HELP.grafana.dashboards)
app.add_typer(dashboards_app, name="dashboards")


# =============================================================================
# Grafana Client Arguments Helper
# =============================================================================


def _client_args(settings: Settings) -> tuple[str, dict[str, str]]:
    """Return (base_url, headers) for Grafana API requests.

    The URL check reads only the URL. The client of `_client` checks the address at the connect.
    """
    if not settings.grafana.url:
        print_error(
            MESSAGES.grafana.url_not_configured,
            prefix=False,
        )
        raise typer.Exit(1)
    try:
        base = service_base_url(settings.grafana.url, "grafana.url")
    except ValueError as exc:
        print_error(str(exc), prefix=False)
        raise typer.Exit(1) from exc
    headers: dict[str, str] = {"Content-Type": "application/json"}
    token = get_grafana_token(settings)
    if token and not token.startswith("*"):
        headers["Authorization"] = f"Bearer {token}"
    else:
        from devops_cli.k8s.credentials import get_or_mint_grafana_auth

        minted_token, basic_auth = get_or_mint_grafana_auth(settings)
        if minted_token:
            headers["Authorization"] = f"Bearer {minted_token}"
        elif basic_auth:
            headers["Authorization"] = basic_auth
    return base, headers


def _client(settings: Settings) -> httpx2.Client:
    """A Grafana client that dials the configured level: loopback, or private with the flag."""
    return new_http_client(level=configured_level(settings.ai))


def _dry_run_base_url() -> str:
    """Return the Grafana base URL safely for dry-run request planning."""
    settings = load_settings()
    if settings.grafana.url:
        try:
            return service_base_url(settings.grafana.url, "grafana.url")
        except ValueError:
            pass
    return "https://grafana.example.com"


# =============================================================================
# Command: devops grafana dashboards list
# =============================================================================


@dashboards_app.command("list")
@dry_run_class("request-plan")
def dashboards_list(
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help=HELP.options.dry_run),
    ] = False,
) -> None:
    """List all dashboards."""
    if dry_run or is_dry_run():
        render_request_plan(
            "devops grafana dashboards list", plan_grafana_dashboards_list(_dry_run_base_url())
        )
        return

    settings = load_settings()
    base, headers = _client_args(settings)

    with _client(settings) as http_client:
        response = http_client.get(
            f"{base}/api/search",
            headers=headers,
            params={"type": "dash-db"},
            timeout=DEFAULT_HTTP_TIMEOUT_SECONDS,
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
@dry_run_class("request-plan")
def dashboards_export(
    uid: Annotated[str, typer.Argument(help=HELP.grafana.uid)],
    output: Annotated[Path | None, typer.Option("--output", "-o", help=HELP.options.output)] = None,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help=HELP.options.dry_run),
    ] = False,
) -> None:
    """Export a dashboard to JSON."""
    if dry_run or is_dry_run():
        render_request_plan(
            "devops grafana dashboards export",
            plan_grafana_dashboards_export(_dry_run_base_url(), uid),
        )
        return

    if not re.fullmatch(r"^[a-zA-Z0-9_-]+$", uid):
        print_error(
            ERRORS.grafana.invalid_uid,
            prefix=False,
        )
        raise typer.Exit(1)
    if output is not None:
        try:
            from devops_cli.core.paths import validate_no_path_traversal

            validate_no_path_traversal(output, label="Dashboard export output path")
        except Exception as exc:
            print_error(ERRORS.grafana.invalid_output_path, prefix=False)
            raise typer.Exit(1) from exc
        resolved = output.resolve()
        if not resolved.is_relative_to(Path.cwd().resolve()):
            print_error(ERRORS.grafana.invalid_output_path, prefix=False)
            raise typer.Exit(1)
    settings = load_settings()
    base, headers = _client_args(settings)

    with _client(settings) as http_client:
        response = http_client.get(
            f"{base}/api/dashboards/uid/{uid}",
            headers=headers,
            timeout=DEFAULT_HTTP_TIMEOUT_SECONDS,
        )
        response.raise_for_status()

    dest = output or Path(f"{uid}.json")
    write_json_file(dest, response.json())
    print_success(MESSAGES.grafana.exported_success.format(dest=dest))


# =============================================================================
# Command: devops grafana dashboards import
# =============================================================================


@dashboards_app.command("import")
@dry_run_class("request-plan")
def dashboards_import(
    file: Annotated[Path, typer.Argument(help=HELP.grafana.import_file)],
    folder_id: Annotated[
        int, typer.Option("--folder-id", help=HELP.grafana.folder_id)
    ] = DEFAULT_GRAFANA_FOLDER_ID,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help=HELP.options.dry_run),
    ] = False,
) -> None:
    """Import a dashboard from JSON."""
    if dry_run or is_dry_run():
        render_request_plan(
            "devops grafana dashboards import",
            plan_grafana_dashboards_import(_dry_run_base_url(), file, folder_id),
        )
        return

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
        raise typer.Exit(1) from exc

    if not isinstance(raw, dict):
        print_error(ERRORS.grafana.invalid_json_object.format(path=file), prefix=False)
        raise typer.Exit(1)

    dashboard = raw.get("dashboard", raw)
    if isinstance(dashboard, dict):
        dashboard.pop("id", None)
        dashboard.pop("uid", None)

    with _client(settings) as http_client:
        response = http_client.post(
            f"{base}/api/dashboards/db",
            headers=headers,
            json={"dashboard": dashboard, "folderId": folder_id, "overwrite": True},
            timeout=DEFAULT_HTTP_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
    print_success(
        MESSAGES.grafana.imported_success.format(slug=response.json().get("slug", "unknown"))
    )


# =============================================================================
# Command: devops grafana dashboards sync
# =============================================================================


def _is_provisioned(
    http_client: httpx2.Client, base: str, headers: dict[str, str], uid: str
) -> bool:
    """Report whether Grafana holds a dashboard as provisioned, so an API save cannot replace it.

    Read from `meta.provisioned` rather than the refusal's wording. A failed lookup counts as
    not provisioned, so the refused save is reported as the failure it was.
    """
    if not uid:
        return False
    try:
        response = http_client.get(
            f"{base}/api/dashboards/uid/{quote(uid, safe='')}",
            headers=headers,
            timeout=DEFAULT_HTTP_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        return GrafanaDashboardDetail.model_validate(response.json()).meta.provisioned
    except httpx2.HTTPError, ValueError:
        return False


def _post_dashboard(
    http_client: httpx2.Client, base: str, headers: dict[str, str], dash_file: Path
) -> DashboardSyncOutcome:
    """Post one dashboard file; Grafana refusing a provisioned dashboard is a skip."""
    raw = json.loads(dash_file.read_text(encoding="utf-8"))
    dashboard = raw.get("dashboard", raw)
    title = dashboard.get("title", dash_file.stem)
    response = http_client.post(
        f"{base}/api/dashboards/db",
        headers=headers,
        json={"dashboard": dashboard, "overwrite": True},
        timeout=DEFAULT_HTTP_TIMEOUT_SECONDS,
    )
    try:
        response.raise_for_status()
    except httpx2.HTTPStatusError as exc:
        uid = str(dashboard.get("uid") or "")
        if exc.response.status_code != HTTPStatus.BAD_REQUEST or not _is_provisioned(
            http_client, base, headers, uid
        ):
            raise
        print_warning(
            MESSAGES.grafana.sync_skipped_provisioned.format(title=title, file=dash_file.name),
            prefix=False,
        )
        return DashboardSyncOutcome.SKIPPED
    print_success(MESSAGES.grafana.synced_dashboard.format(title=title, file=dash_file.name))
    return DashboardSyncOutcome.SYNCED


def _sync_dashboard_file(
    http_client: httpx2.Client, base: str, headers: dict[str, str], dash_file: Path
) -> DashboardSyncOutcome:
    """Sync one dashboard file, reporting a failure without stopping the run.

    A refused address stops the run: the refusal applies to each file, and the `exit_on` of the
    app reports it.
    """
    try:
        return _post_dashboard(http_client, base, headers, dash_file)
    except SSRFBlockedError:
        raise
    except Exception as exc:
        print_error(ERRORS.grafana.sync_failed.format(file=dash_file.name, exc=exc), prefix=False)
        return DashboardSyncOutcome.FAILED


@dashboards_app.command("sync")
@dry_run_class("request-plan")
def dashboards_sync(
    dir_path: Annotated[
        Path | None,
        typer.Option("--dir", "-d", help=HELP.grafana.dashboards_dir),
    ] = None,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help=HELP.options.dry_run),
    ] = False,
) -> None:
    """Sync every dashboard JSON file in a directory to Grafana.

    Tries every file, then exits 1 if any failed. A dashboard Grafana holds as provisioned,
    such as one the dashboard sidecar loads from a ConfigMap, is skipped rather than failed.
    """
    search_dir = dir_path or DEFAULT_GRAFANA_DASHBOARDS_DIR
    json_files = sorted(search_dir.glob("*.json")) if search_dir.exists() else []

    if dry_run or is_dry_run():
        render_request_plan(
            "devops grafana dashboards sync",
            plan_grafana_dashboards_sync(_dry_run_base_url(), json_files),
        )
        return

    if not search_dir.exists():
        print_warning(MESSAGES.grafana.dir_not_found.format(path=search_dir), prefix=False)
        raise typer.Exit(1)

    if not json_files:
        print_warning(MESSAGES.grafana.no_json_files.format(path=search_dir), prefix=False)
        return

    settings = load_settings()
    base, headers = _client_args(settings)

    with _client(settings) as http_client:
        outcomes = Counter(
            _sync_dashboard_file(http_client, base, headers, dash_file) for dash_file in json_files
        )

    summary = MESSAGES.grafana.sync_completed.format(
        synced=outcomes[DashboardSyncOutcome.SYNCED],
        skipped=outcomes[DashboardSyncOutcome.SKIPPED],
        failed=outcomes[DashboardSyncOutcome.FAILED],
    )
    if outcomes[DashboardSyncOutcome.FAILED]:
        print_error(summary, prefix=False)
        raise typer.Exit(1)
    print_success(summary)


# =============================================================================
# Command: devops grafana search
# =============================================================================


# =============================================================================
# Command: devops grafana dashboards lint
# =============================================================================


def _lint_rows(reports: list[Any]) -> list[list[str]]:
    """Render lint issues across dashboards as table rows."""
    return [
        [
            report.source_file or report.dashboard_title,
            issue.severity,
            issue.panel or "(dashboard)",
            issue.message,
        ]
        for report in reports
        for issue in report.issues
    ]


def _print_lint_results(reports: list[DashboardLintReport]) -> None:
    """Render lint issues as a table, then the summary line."""
    error_count = sum(len(r.errors) for r in reports)
    warning_count = sum(len(r.warnings) for r in reports)

    if error_count or warning_count:
        print_table(
            title=MESSAGES.grafana.table_title_lint,
            columns=[("Dashboard", "cyan"), "Severity", "Panel", "Issue"],
            rows=_lint_rows(reports),
        )

    print_info(
        MESSAGES.grafana.lint_summary.format(
            dashboards=len(reports),
            panels=sum(r.panel_count for r in reports),
            errors=error_count,
            warnings=warning_count,
        )
    )


@dashboards_app.command("lint")
@dry_run_class("no-external-request")
def dashboards_lint(
    path: Annotated[
        Path, typer.Argument(help=HELP.grafana.lint_path)
    ] = DEFAULT_GRAFANA_DASHBOARDS_DIR,
    output_format: Annotated[
        str,
        typer.Option("--format", "-f", help=HELP.options.format_type),
    ] = DEFAULT_TABLE_FORMAT,
    json_output: Annotated[bool, typer.Option("--json", help=HELP.options.json_output)] = False,
) -> None:
    """Statically check dashboard JSON for layout, query, and binding defects.

    Catches overlapping panels, duplicate ids, unbound datasources, malformed PromQL, and a
    uid two dashboards share before a dashboard reaches Grafana, where the only symptom is a
    blank, wrong, or overwritten dashboard.
    """
    from devops_cli.grafana import lint_dashboard_files

    target = path.resolve()

    if target.is_dir():
        files = sorted(target.glob("*.json"))
    elif target.is_file():
        files = [target]
    else:
        print_error(ERRORS.grafana.dashboards_not_found.format(path=path), prefix=False)
        raise typer.Exit(1)

    if not files:
        print_warning(MESSAGES.grafana.no_dashboards_found.format(path=path))
        return

    reports = lint_dashboard_files(files)

    resolved = resolve_format(output_format, json_output=json_output)
    if resolved != CONST_OUTPUT_FORMAT_TABLE:
        emit_serialized([r.model_dump() for r in reports], resolved)
    else:
        _print_lint_results(reports)
    if any(r.errors for r in reports):
        raise typer.Exit(1)


@app.command()
@dry_run_class("request-plan")
def search(
    query: Annotated[str, typer.Option("--query", "-q", help=HELP.grafana.query)] = "",
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help=HELP.options.dry_run),
    ] = False,
) -> None:
    """Search Grafana dashboards and folders by query string."""
    if dry_run or is_dry_run():
        render_request_plan(
            "devops grafana search", plan_grafana_search(_dry_run_base_url(), query)
        )
        return

    settings = load_settings()
    base, headers = _client_args(settings)
    params = {"query": query} if query else {}

    with _client(settings) as http_client:
        response = http_client.get(
            f"{base}/api/search",
            headers=headers,
            params=params,
            timeout=DEFAULT_HTTP_TIMEOUT_SECONDS,
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
@dry_run_class("request-plan")
def datasources(
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help=HELP.options.dry_run),
    ] = False,
) -> None:
    """List configured datasources."""
    if dry_run or is_dry_run():
        render_request_plan(
            "devops grafana datasources", plan_grafana_datasources(_dry_run_base_url())
        )
        return

    settings = load_settings()
    base, headers = _client_args(settings)

    with _client(settings) as http_client:
        response = http_client.get(
            f"{base}/api/datasources",
            headers=headers,
            timeout=DEFAULT_HTTP_TIMEOUT_SECONDS,
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
@dry_run_class("request-plan")
def alerts(
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help=HELP.options.dry_run),
    ] = False,
) -> None:
    """List alert rules (Grafana 9+ unified alerting)."""
    if dry_run or is_dry_run():
        render_request_plan("devops grafana alerts", plan_grafana_alerts(_dry_run_base_url()))
        return

    settings = load_settings()
    base, headers = _client_args(settings)

    with _client(settings) as http_client:
        response = http_client.get(
            f"{base}/api/v1/provisioning/alert-rules",
            headers=headers,
            timeout=DEFAULT_HTTP_TIMEOUT_SECONDS,
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
