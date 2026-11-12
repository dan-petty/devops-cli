"""Infra repo subcommands: the Ansible inventory, playbooks and roles of a set of hosts (#5120)."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from devops_cli.core.cli import new_typer
from devops_cli.dry_run import is_dry_run
from devops_cli.dry_run.decorator import dry_run_class
from devops_cli.infra.access import AgentAccess, refuse_agent_raise
from devops_cli.lang import HELP, MESSAGES
from devops_cli.output import write_stdout
from devops_cli.telemetry import trace_span

app = new_typer(
    help=HELP.infra.app,
    no_args_is_help=True,
)


@app.callback()
def infra() -> None:
    """Keep `devops infra` a group: with one command and no callback, Typer runs the command as
    the group itself."""


@app.command("onboard", help=HELP.infra.onboard)
@dry_run_class("request-plan")
@trace_span("infra.onboard")
def onboard(
    repo: Annotated[str, typer.Argument(help=HELP.infra.onboard_repo)],
    path: Annotated[Path | None, typer.Option("--path", help=HELP.infra.onboard_path)] = None,
    kube_context: Annotated[
        str | None, typer.Option("--kube-context", help=HELP.infra.onboard_kube_context)
    ] = None,
    ssh_key_prefix: Annotated[
        str | None, typer.Option("--ssh-key-prefix", help=HELP.infra.onboard_ssh_key_prefix)
    ] = None,
    agent_access: Annotated[
        AgentAccess | None,
        typer.Option("--agent-access", help=HELP.infra.onboard_agent_access),
    ] = None,
    confirm: Annotated[bool, typer.Option("--confirm", help=HELP.infra.onboard_confirm)] = False,
    dry_run: Annotated[bool, typer.Option("--dry-run", help=HELP.options.dry_run)] = False,
) -> None:
    """Check an Ansible infra repo and, with --confirm, write its entry of infra.repos."""
    from devops_cli.config.settings import get_active_config_path, load_settings
    from devops_cli.dry_run.requests import render_request_plan
    from devops_cli.github.repo_ref import RepoRef, is_repository_name
    from devops_cli.infra.infra_plans import plan_onboard
    from devops_cli.infra.onboard import (
        check_onboarding,
        default_checkout,
        render_onboarding,
        resolve_target,
        write_entry,
    )

    refuse_agent_raise(agent_access)
    settings = load_settings()
    if dry_run or is_dry_run():
        named = is_repository_name(repo)
        entry = settings.infra.entry(RepoRef(repo)) if named else None
        checkout = (
            (path or (entry.path if entry else None) or default_checkout(RepoRef(repo), settings))
            if named
            else Path(repo)
        )
        render_request_plan(
            MESSAGES.infra.onboard_plan_title.format(repo=repo, path=checkout),
            plan_onboard(
                checkout,
                origin_lookup=not named,
                confirm=confirm,
                config_path=get_active_config_path(),
            ),
            [MESSAGES.infra.onboard_plan_reads_files],
            described=True,
        )
        return

    target = resolve_target(repo, path=path, settings=settings)
    report = check_onboarding(
        target,
        settings,
        kube_context=kube_context,
        ssh_key_prefix=ssh_key_prefix,
        agent_access=agent_access,
    )
    if confirm:
        report = write_entry(report, settings)
    write_stdout(render_onboarding(report) + "\n")
    if report.has_missing:
        raise typer.Exit(1)
