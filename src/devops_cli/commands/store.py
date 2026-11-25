"""CLI command group for publishing and reading content-store objects (#4761)."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Annotated

import typer

from devops_cli.core.cli import new_typer
from devops_cli.dry_run import dry_run_class, is_dry_run
from devops_cli.dry_run.requests import render_request_plan
from devops_cli.lang import HELP
from devops_cli.output import print_info, print_success, print_table, print_warning, write_stdout
from devops_cli.store.ops import (
    get_object_to_file,
    list_kind_objects,
    presign_object,
    publish_file,
    resolve_web_url,
    run_doctor,
    sync_pending,
)
from devops_cli.store.store_plans import (
    plan_store_doctor,
    plan_store_get,
    plan_store_ls,
    plan_store_presign,
    plan_store_publish,
    plan_store_sync,
    plan_store_url,
)
from devops_cli.telemetry import trace_span

app = new_typer(help=HELP.store.group_help)

_JsonOption = Annotated[bool, typer.Option("--json", help="Emit structured JSON output")]
_DryRunOption = Annotated[bool, typer.Option("--dry-run", help=HELP.options.dry_run)]


@app.command("publish")
@dry_run_class("request-plan")
@trace_span("store.publish")
def store_publish(
    kind: Annotated[str, typer.Argument(help=HELP.store.arg_kind)],
    path: Annotated[Path, typer.Argument(help=HELP.store.arg_path)],
    key: Annotated[str | None, typer.Option("--key", help=HELP.store.opt_key)] = None,
    replace: Annotated[bool, typer.Option("--replace", help=HELP.store.opt_replace)] = False,
    json_output: _JsonOption = False,
    dry_run: _DryRunOption = False,
) -> None:
    """Publish a local file to the content store or queue it while unreachable."""
    if dry_run or is_dry_run():
        render_request_plan(
            "Planned requests for devops store publish (DRY RUN):",
            plan_store_publish(kind, str(path), key=key),
        )
        return
    result = publish_file(kind, path, key=key, replace=replace)
    if json_output:
        write_stdout(json.dumps(asdict(result), indent=2) + "\n")
        return
    if result.status == "pending":
        print_warning(
            f"Store unreachable; queued '{result.key}' (sha256={result.sha256[:12]}) as pending."
        )
        return
    if result.status == "skipped":
        print_info(f"Object s3://{result.bucket}/{result.key} already matches sha256; skipped.")
        return
    suffix = f" -> {result.url}" if result.url else ""
    print_success(f"Published s3://{result.bucket}/{result.key}{suffix}")


@app.command("sync")
@dry_run_class("request-plan")
@trace_span("store.sync")
def store_sync(
    json_output: _JsonOption = False,
    dry_run: _DryRunOption = False,
) -> None:
    """Upload queued artifacts from `store/pending.jsonl` to the content store."""
    if dry_run or is_dry_run():
        render_request_plan(
            "Planned requests for devops store sync (DRY RUN):",
            plan_store_sync(),
        )
        return
    result = sync_pending()
    if json_output:
        write_stdout(json.dumps(asdict(result), indent=2) + "\n")
        return
    print_success(
        f"Sync complete: uploaded={result.uploaded}, skipped={result.skipped}, "
        f"remaining={result.remaining}."
    )


@app.command("ls")
@dry_run_class("request-plan")
@trace_span("store.ls")
def store_ls(
    kind: Annotated[str, typer.Argument(help=HELP.store.arg_kind)],
    prefix: Annotated[str, typer.Option("--prefix", help=HELP.store.opt_prefix)] = "",
    json_output: _JsonOption = False,
    dry_run: _DryRunOption = False,
) -> None:
    """List objects stored under a content kind prefix."""
    if dry_run or is_dry_run():
        render_request_plan(
            "Planned requests for devops store ls (DRY RUN):",
            plan_store_ls(kind, prefix=prefix),
        )
        return
    entries = list_kind_objects(kind, prefix=prefix)
    if json_output:
        write_stdout(json.dumps([asdict(entry) for entry in entries], indent=2) + "\n")
        return
    if not entries:
        print_info(f"No objects found under kind '{kind}'.")
        return
    rows = [[entry.key, str(entry.size), entry.last_modified or ""] for entry in entries]
    print_table(f"Store Objects ({kind})", columns=["Key", "Size", "Last Modified"], rows=rows)


@app.command("get")
@dry_run_class("request-plan")
@trace_span("store.get")
def store_get(
    kind: Annotated[str, typer.Argument(help=HELP.store.arg_kind)],
    key: Annotated[str, typer.Argument(help=HELP.store.arg_key)],
    dest: Annotated[Path | None, typer.Argument(help=HELP.store.arg_dest)] = None,
    output: Annotated[Path | None, typer.Option("--output", "-o", help=HELP.store.arg_dest)] = None,
    json_output: _JsonOption = False,
    dry_run: _DryRunOption = False,
) -> None:
    """Download a stored object to a local file path."""
    if dry_run or is_dry_run():
        render_request_plan(
            "Planned requests for devops store get (DRY RUN):",
            plan_store_get(kind, key),
        )
        return
    target = dest or output or Path(Path(key).name)
    size = get_object_to_file(kind, key, target)
    if json_output:
        write_stdout(json.dumps({"path": str(target), "size": size}, indent=2) + "\n")
        return
    print_success(f"Downloaded {size} bytes to {target}")


@app.command("url")
@dry_run_class("request-plan")
@trace_span("store.url")
def store_url(
    kind: Annotated[str, typer.Argument(help=HELP.store.arg_kind)],
    key: Annotated[str, typer.Argument(help=HELP.store.arg_key)],
    json_output: _JsonOption = False,
    dry_run: _DryRunOption = False,
) -> None:
    """Print the public web URL for a web-visible content-kind object."""
    if dry_run or is_dry_run():
        render_request_plan(
            "Planned requests for devops store url (DRY RUN):",
            plan_store_url(kind, key),
        )
        return
    url = resolve_web_url(kind, key)
    if json_output:
        write_stdout(json.dumps({"url": url}, indent=2) + "\n")
        return
    typer.echo(url)


@app.command("presign")
@dry_run_class("request-plan")
@trace_span("store.presign")
def store_presign(
    kind: Annotated[str, typer.Argument(help=HELP.store.arg_kind)],
    key: Annotated[str, typer.Argument(help=HELP.store.arg_key)],
    expires: Annotated[int, typer.Option("--expires", help=HELP.store.opt_expires)] = 3600,
    json_output: _JsonOption = False,
    dry_run: _DryRunOption = False,
) -> None:
    """Generate a temporary SigV4 presigned GET URL (at most 7 days)."""
    if dry_run or is_dry_run():
        render_request_plan(
            "Planned requests for devops store presign (DRY RUN):",
            plan_store_presign(kind, key, expires_in=expires),
        )
        return
    url = presign_object(kind, key, expires_in=expires)
    if json_output:
        write_stdout(json.dumps({"url": url, "expires_in": expires}, indent=2) + "\n")
        return
    typer.echo(url)


@app.command("doctor")
@dry_run_class("request-plan")
@trace_span("store.doctor")
def store_doctor(
    endpoint: Annotated[
        list[str] | None, typer.Option("--endpoint", help=HELP.store.opt_endpoint)
    ] = None,
    json_output: _JsonOption = False,
    dry_run: _DryRunOption = False,
) -> None:
    """Run put, list, get, presign, and delete canary checks on configured endpoints."""
    extra = tuple(endpoint or ())
    if dry_run or is_dry_run():
        render_request_plan(
            "Planned requests for devops store doctor (DRY RUN):",
            plan_store_doctor(extra),
        )
        return
    reports = run_doctor(extra_endpoints=extra)
    if json_output:
        write_stdout(json.dumps([asdict(r) for r in reports], indent=2) + "\n")
        return
    rows = [[r.endpoint, r.canary_key, ", ".join(r.operations)] for r in reports]
    print_table("Content Store Doctor", columns=["Endpoint", "Canary Key", "Verified"], rows=rows)
