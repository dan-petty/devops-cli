"""`devops k8s tunnel`: keep the forward to the Kubernetes API route at `k8s.<domain>` running (#1641)."""

from __future__ import annotations

import shutil
from typing import Annotated

import typer

from devops_cli.config.defaults import DEFAULT_K8S_TUNNEL_PORT, DEFAULT_REST_HOST
from devops_cli.config.settings import load_settings
from devops_cli.core.cli import new_typer
from devops_cli.core.validation import validate_k8s_context_name
from devops_cli.dry_run import is_dry_run, render_dry_run_result
from devops_cli.exceptions.k8s import KubernetesTunnelError
from devops_cli.k8s.tunnel import (
    TUNNEL_CONTEXT_SUFFIX,
    forward_command,
    load_tunnel,
    login_command,
    remember_context,
    start_tunnel,
    stop_tunnel,
    tunnel_state_file,
    tunnel_status,
    write_tunnel_context,
)
from devops_cli.lang import ERRORS, HELP, MESSAGES
from devops_cli.output import print_info, print_success

app = new_typer(help=HELP.k8s.tunnel_app, no_args_is_help=True)


def _tunnel_host() -> str:
    host = load_settings().k8s.tunnel_host
    if not host:
        raise KubernetesTunnelError(ERRORS.k8s.tunnel_host_unset)
    return host


@app.command("start", help=HELP.k8s.tunnel_start)
def tunnel_start(
    port: Annotated[
        int, typer.Option("--port", "-p", help=HELP.k8s.tunnel_port)
    ] = DEFAULT_K8S_TUNNEL_PORT,
    add_context: Annotated[
        bool, typer.Option("--context", help=HELP.k8s.tunnel_add_context)
    ] = False,
    from_context: Annotated[
        str | None, typer.Option("--from-context", help=HELP.k8s.tunnel_from_context)
    ] = None,
    dry_run: Annotated[bool, typer.Option("--dry-run", help=HELP.options.dry_run)] = False,
) -> None:
    """Log in to Cloudflare Access and start the forward to k8s.tunnel_host."""
    host = _tunnel_host()
    home_context = from_context or load_settings().k8s.context
    if add_context:
        validate_k8s_context_name(home_context, label="--from-context")
    state_file = tunnel_state_file()
    cloudflared = shutil.which("cloudflared")
    if dry_run or is_dry_run():
        program = cloudflared or "cloudflared"
        details = {
            "login": " ".join(login_command(program, host)),
            "forward": " ".join(
                forward_command(
                    program, host, DEFAULT_REST_HOST, port, state_file.with_suffix(".log")
                )
            ),
        }
        if add_context:
            details["context"] = f"<cluster of {home_context}>{TUNNEL_CONTEXT_SUFFIX}"
        render_dry_run_result(
            command="devops k8s tunnel start", action="k8s_tunnel_start", details=details
        )
        return

    if cloudflared is None:
        raise KubernetesTunnelError(ERRORS.k8s.tunnel_cloudflared_missing)
    outcome = start_tunnel(
        host, cloudflared=cloudflared, address=DEFAULT_REST_HOST, port=port, state_file=state_file
    )
    record = outcome.record
    message = (
        MESSAGES.k8s.tunnel_started if outcome.started else MESSAGES.k8s.tunnel_already_running
    )
    print_success(
        message.format(
            host=record.hostname, listener=record.listener, pid=record.pid, log=record.log_file
        )
    )
    if add_context:
        context = write_tunnel_context(home_context, address=record.address, port=record.port)
        remember_context(state_file, context)
        print_success(MESSAGES.k8s.tunnel_context_written.format(context=context))


@app.command("stop", help=HELP.k8s.tunnel_stop)
def tunnel_stop(
    dry_run: Annotated[bool, typer.Option("--dry-run", help=HELP.options.dry_run)] = False,
) -> None:
    """Stop the recorded forward and its process group."""
    state_file = tunnel_state_file()
    if dry_run or is_dry_run():
        record = load_tunnel(state_file)
        render_dry_run_result(
            command="devops k8s tunnel stop",
            action="k8s_tunnel_stop",
            details={"pid": record.pid if record and record.is_alive else None},
        )
        return
    record = stop_tunnel(state_file)
    if record is None:
        print_info(MESSAGES.k8s.tunnel_none_running)
        return
    print_success(MESSAGES.k8s.tunnel_stopped.format(host=record.hostname, pid=record.pid))


@app.command("status", help=HELP.k8s.tunnel_status)
def tunnel_status_cmd(
    port: Annotated[int | None, typer.Option("--port", "-p", help=HELP.k8s.tunnel_port)] = None,
    context: Annotated[
        str | None, typer.Option("--context", "-c", help=HELP.k8s.tunnel_status_context)
    ] = None,
) -> None:
    """Show the recorded forward, its port and whether the API server answers."""
    if context:
        validate_k8s_context_name(context, label="--context")
    status = tunnel_status(
        tunnel_state_file(), address=DEFAULT_REST_HOST, port=port, context=context
    )
    record = status.record
    if record is None:
        print_info(MESSAGES.k8s.tunnel_none_recorded)
    else:
        print_info(
            MESSAGES.k8s.tunnel_forward.format(
                pid=record.pid,
                host=record.hostname,
                listener=record.listener,
                started=record.started_at[:19],
            )
        )
    port_message = (
        MESSAGES.k8s.tunnel_port_listening if status.listening else MESSAGES.k8s.tunnel_port_closed
    )
    print_info(port_message.format(listener=status.listener))
    if status.context is None:
        print_info(MESSAGES.k8s.tunnel_api_unchecked)
        return
    api_message = (
        MESSAGES.k8s.tunnel_api_answers if status.api_answers else MESSAGES.k8s.tunnel_api_silent
    )
    print_info(api_message.format(context=status.context))
