"""Kubernetes PersistentVolume maintenance and orphan volume reclamation commands."""

from __future__ import annotations

import sys
from typing import Annotated

import typer

from devops_cli.config.constants import CONST_K8S_VOLUME_RECLAIM_HEADING
from devops_cli.core.cli import new_typer
from devops_cli.dry_run import is_dry_run
from devops_cli.dry_run.requests import render_request_plan
from devops_cli.k8s.volume import (
    get_k8s_client,
    plan_volume_reclaim_requests,
    reclaim_volume,
    verify_volume_orphaned,
)
from devops_cli.lang import ERRORS, HELP, MESSAGES
from devops_cli.output import print_error, print_info, print_success

app = new_typer(help=HELP.k8s.volume_app, no_args_is_help=True)


def _is_interactive() -> bool:
    """Check if the session has an interactive TTY standard input."""
    return getattr(sys.stdin, "isatty", lambda: False)()


@app.command(name="reclaim", help=HELP.k8s.volume_reclaim)
def volume_reclaim_cmd(
    name: Annotated[str, typer.Argument(help=HELP.k8s.volume_reclaim_name)],
    dry_run: Annotated[
        bool, typer.Option("--dry-run", help=HELP.k8s.volume_reclaim_dry_run)
    ] = False,
    yes: Annotated[bool, typer.Option("--yes", "-y", help=HELP.k8s.volume_reclaim_yes)] = False,
    patch: Annotated[bool, typer.Option("--patch", help=HELP.k8s.volume_reclaim_patch)] = False,
    context: Annotated[
        str | None, typer.Option("--context", "-c", help=HELP.k8s.context_target)
    ] = None,
) -> None:
    """Safely reclaim a named PersistentVolume if verified to be genuinely orphaned."""
    if dry_run or is_dry_run():
        requests = plan_volume_reclaim_requests(name=name, patch=patch)
        render_request_plan(CONST_K8S_VOLUME_RECLAIM_HEADING, requests)
        return

    core = get_k8s_client(context=context)
    try:
        pv = core.read_persistent_volume(name=name)
    except Exception as exc:
        print_error(ERRORS.k8s.volume_not_found.format(name=name))
        raise typer.Exit(1) from exc

    is_orphaned, reason = verify_volume_orphaned(core, pv)
    if not is_orphaned:
        print_error(f"Cannot reclaim PersistentVolume '{name}': {reason}")
        raise typer.Exit(1)

    if not yes:
        if not _is_interactive():
            print_error(ERRORS.k8s.volume_reclaim_non_interactive)
            raise typer.Exit(1)
        prompt = f"Are you sure you want to reclaim PersistentVolume '{name}'?"
        if not typer.confirm(prompt, default=False):
            print_info(MESSAGES.k8s.volume_reclaim_aborted.format(name=name))
            return

    action = reclaim_volume(core, name=name, patch=patch)
    print_success(MESSAGES.k8s.volume_reclaimed.format(name=name, action=action))


__all__ = [
    "_is_interactive",
    "app",
    "volume_reclaim_cmd",
]
