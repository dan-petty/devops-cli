"""Grafana management commands (httpx REST API)."""

from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path
from typing import Annotated, Any

import typer

from devops_cli.config.constants import (
    CONST_MAX_FILE_SIZE_BYTES,
    CONST_OUTPUT_FORMAT_TABLE,
)
from devops_cli.config.defaults import (
    DEFAULT_GRAFANA_DASHBOARDS_DIRS,
    DEFAULT_GRAFANA_FOLDER_ID,
    DEFAULT_TABLE_FORMAT,
)
from devops_cli.config.settings import Settings, get_grafana_token, load_settings
from devops_cli.core.cli import new_typer
from devops_cli.dry_run import dry_run_class, is_dry_run
from devops_cli.dry_run.requests import render_request_plan
from devops_cli.grafana.client import DashboardSyncResult, GrafanaClient
from devops_cli.grafana.grafana_plans import (
    plan_grafana_alerts,
    plan_grafana_dashboards_export,
    plan_grafana_dashboards_import,
    plan_grafana_dashboards_list,
    plan_grafana_dashboards_sync,
    plan_grafana_datasources,
    plan_grafana_search,
)
from devops_cli.http.egress import configured_level
from devops_cli.http.urls import service_base_url
from devops_cli.lang import ERRORS, HELP, MESSAGES
from devops_cli.models.grafana import (
    DashboardLintReport,
    DashboardSyncOutcome,
    GrafanaAlertRule,
    GrafanaDashboard,
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


def _client(settings: Settings, base: str, headers: dict[str, str]) -> GrafanaClient:
    """A Grafana client that dials the configured level: loopback, or private with the flag."""
    return GrafanaClient(base, headers, configured_level(settings.ai))


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

    with _client(settings, base, headers) as grafana:
        items = grafana.list_dashboards()

    rows: list[list[str]] = []
    for item in items:
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

    with _client(settings, base, headers) as grafana:
        stored = grafana.dashboard(uid)

    dest = output or Path(f"{uid}.json")
    write_json_file(dest, stored)
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

    with _client(settings, base, headers) as grafana:
        saved = grafana.import_dashboard(dashboard, folder_id)
    print_success(MESSAGES.grafana.imported_success.format(slug=saved.get("slug", "unknown")))


# =============================================================================
# Command: devops grafana dashboards sync
# =============================================================================


def _report_sync(result: DashboardSyncResult) -> DashboardSyncOutcome:
    """Print what the sync did with one file, and return its outcome."""
    match result.outcome:
        case DashboardSyncOutcome.SYNCED:
            print_success(
                MESSAGES.grafana.synced_dashboard.format(title=result.title, file=result.file)
            )
        case DashboardSyncOutcome.SKIPPED:
            print_warning(
                MESSAGES.grafana.sync_skipped_provisioned.format(
                    title=result.title, file=result.file
                ),
                prefix=False,
            )
        case DashboardSyncOutcome.FAILED:
            print_error(
                ERRORS.grafana.sync_failed.format(file=result.file, exc=result.error),
                prefix=False,
            )
    return result.outcome


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

    With no directory, syncs the files of the environment and the product dashboard folders.
    Tries every file, then exits 1 if any failed. A dashboard Grafana holds as provisioned,
    such as one the dashboard sidecar loads from a ConfigMap, is skipped rather than failed.
    """
    search_dirs = (dir_path,) if dir_path else DEFAULT_GRAFANA_DASHBOARDS_DIRS
    json_files = [
        path
        for search_dir in search_dirs
        if search_dir.exists()
        for path in sorted(search_dir.glob("*.json"))
    ]

    if dry_run or is_dry_run():
        render_request_plan(
            "devops grafana dashboards sync",
            plan_grafana_dashboards_sync(_dry_run_base_url(), json_files),
        )
        return

    missing = [search_dir for search_dir in search_dirs if not search_dir.exists()]
    for search_dir in missing:
        print_warning(MESSAGES.grafana.dir_not_found.format(path=search_dir), prefix=False)
    if missing:
        raise typer.Exit(1)

    if not json_files:
        print_warning(
            MESSAGES.grafana.no_json_files.format(path=", ".join(map(str, search_dirs))),
            prefix=False,
        )
        return

    settings = load_settings()
    base, headers = _client_args(settings)

    with _client(settings, base, headers) as grafana:
        outcomes = Counter(
            _report_sync(grafana.sync_dashboard(dash_file)) for dash_file in json_files
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
    paths: Annotated[
        list[Path] | None, typer.Argument(help=HELP.grafana.lint_path, show_default=False)
    ] = None,
    output_format: Annotated[
        str,
        typer.Option("--format", "-f", help=HELP.options.format_type),
    ] = DEFAULT_TABLE_FORMAT,
    json_output: Annotated[bool, typer.Option("--json", help=HELP.options.json_output)] = False,
) -> None:
    """Statically check dashboard JSON for layout, query, and binding defects.

    Catches overlapping panels, duplicate ids, unbound datasources, malformed PromQL, and a
    uid two dashboards share before a dashboard reaches Grafana, where the only symptom is a
    blank, wrong, or overwritten dashboard. With no path, lints the environment and the
    product dashboard folders together, so a uid that two folders share is an error too.
    """
    from devops_cli.grafana import lint_dashboard_files

    targets = paths or list(DEFAULT_GRAFANA_DASHBOARDS_DIRS)
    files: list[Path] = []
    for path in targets:
        target = path.resolve()
        if target.is_dir():
            files.extend(sorted(target.glob("*.json")))
        elif target.is_file():
            files.append(target)
        else:
            print_error(ERRORS.grafana.dashboards_not_found.format(path=path), prefix=False)
            raise typer.Exit(1)

    if not files:
        print_warning(
            MESSAGES.grafana.no_dashboards_found.format(path=", ".join(map(str, targets)))
        )
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

    with _client(settings, base, headers) as grafana:
        items = grafana.search(query)

    rows: list[list[str]] = []
    for item in items:
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

    with _client(settings, base, headers) as grafana:
        items = grafana.datasources()

    rows: list[list[str]] = []
    for item in items:
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

    with _client(settings, base, headers) as grafana:
        items = grafana.alert_rules()

    rows: list[list[str]] = []
    for item in items:
        rule = GrafanaAlertRule.model_validate(item)
        rows.append([rule.uid, rule.title, rule.folder_uid, rule.condition])
    print_table(
        title=MESSAGES.grafana.table_title_alerts,
        columns=[("UID", "dim"), ("Title", "cyan"), "Folder", "Condition"],
        rows=rows,
    )
