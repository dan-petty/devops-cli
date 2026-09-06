"""DevOps CLI entry point with lazy command delegation."""

from __future__ import annotations

import atexit
import time
from importlib import import_module
from typing import Final

import typer

from devops_cli import __version__
from devops_cli.core.cli import new_typer
from devops_cli.dry_run import is_dry_run, set_dry_run
from devops_cli.lang import HELP

_timing: dict[str, float] = {}


def _print_elapsed() -> None:
    if "start" in _timing:
        elapsed = time.monotonic() - _timing["start"]
        from devops_cli.output import print_muted

        print_muted(f"Elapsed: {elapsed:.2f}s", to_stderr=True)


atexit.register(_print_elapsed)

# command -> (module path, help text)
_COMMAND_SPECS: Final[dict[str, tuple[str, str]]] = {
    "repos": ("devops_cli.commands.repos", HELP.repos.app),
    "ssh": ("devops_cli.commands.ssh", HELP.ssh.app),
    "branches": ("devops_cli.commands.branches", HELP.branches.app),
    "devcontainer": ("devops_cli.commands.devcontainer", HELP.devcontainer.app),
    "workspace": ("devops_cli.commands.workspace", HELP.workspace.app),
    "install-tools": ("devops_cli.commands.install_tools", HELP.install.app),
    "k8s": ("devops_cli.commands.k8s", HELP.k8s.app),
    "kustomize": ("devops_cli.commands.kustomize", HELP.kustomize.app),
    "docker": ("devops_cli.commands.docker", HELP.docker.app),
    "grafana": ("devops_cli.commands.grafana", HELP.grafana.app),
    "prometheus": ("devops_cli.commands.prometheus", HELP.prometheus.app),
    "argo": ("devops_cli.commands.argo", HELP.argo.app),
    "config": ("devops_cli.commands.config", HELP.config.app),
    "ci": ("devops_cli.commands.ci", HELP.ci.app),
    "uv": ("devops_cli.commands.uv", HELP.uv.app),
    "scan": ("devops_cli.commands.scan", HELP.scan.app),
    "ai": ("devops_cli.commands.ai", HELP.ai.app),
    "review": ("devops_cli.commands.review", HELP.review.app),
    "mcp": ("devops_cli.commands.mcp", HELP.mcp.app),
    "docs": ("devops_cli.commands.docs", HELP.docs.app),
    "release": ("devops_cli.commands.release", HELP.release.app),
    "pr": ("devops_cli.commands.pr", HELP.pr.app),
    "gh": ("devops_cli.commands.gh", HELP.gh.app),
    "tf": ("devops_cli.commands.tf", HELP.tf.app),
    "tls": ("devops_cli.commands.tls", HELP.tls.app),
    "telemetry": ("devops_cli.commands.telemetry", HELP.telemetry.app),
    "serve": ("devops_cli.commands.serve", HELP.serve.app),
    "test": ("devops_cli.commands.test_cmd", HELP.test.app),
    "pipeline": ("devops_cli.commands.pipeline", HELP.pipeline.app),
    "vault": ("devops_cli.commands.vault", "Enterprise HashiCorp Vault secret broker"),
}


app = new_typer(
    name="devops",
    help=HELP.main.app,
    no_args_is_help=True,
    rich_markup_mode="rich",
)


def _delegate(module_path: str, command_name: str, args: list[str]) -> None:
    module = import_module(module_path)
    module_app = module.app
    command = typer.main.get_command(module_app)

    # Fast dispatch for help queries to avoid importing telemetry/OTLP network exporters
    if any(a in ("-h", "--help") for a in args):
        command.main(
            args=args,
            prog_name=f"devops {command_name}",
            standalone_mode=False,
        )
        return

    from devops_cli.telemetry import record_metric, trace_span

    args_summary = " ".join(args) if args else ""
    t0 = time.perf_counter()
    with trace_span(
        f"cli.{command_name}",
        attributes={
            "cli.command": command_name,
            "cli.args": args_summary,
            "cli.args_count": len(args),
            "cli.module": module_path,
            "cli.version": __version__,
            "cli.is_dry_run": is_dry_run(),
        },
    ) as span_h:
        span_h.add_event("command_delegated", {"command": command_name, "module": module_path})
        try:
            result = command.main(
                args=args,
                prog_name=f"devops {command_name}",
                standalone_mode=False,
            )
            dur = time.perf_counter() - t0
            exit_code = result if isinstance(result, int) else 0
            span_h.set_attribute("cli.exit_code", exit_code)
            span_h.set_attribute("cli.duration_seconds", dur)
            span_h.set_attribute("cli.status", "ok" if exit_code == 0 else "error")
            span_h.add_event(
                "command_completed",
                {"command": command_name, "exit_code": exit_code, "duration_seconds": dur},
            )
            record_metric(
                "devops_cli_command_total",
                1.0,
                attributes={
                    "command": command_name,
                    "status": "ok" if exit_code == 0 else "error",
                },
            )
            record_metric(
                "devops_cli_command_duration_seconds",
                dur,
                unit="s",
                attributes={"command": command_name},
            )
            if exit_code != 0:
                raise typer.Exit(exit_code)
        except SystemExit as exc:  # pragma: no cover - defensive for wrapped click exits
            dur = time.perf_counter() - t0
            code = exc.code if isinstance(exc.code, int) else 1
            span_h.set_attribute("cli.exit_code", code)
            span_h.set_attribute("cli.duration_seconds", dur)
            span_h.set_attribute("cli.status", "ok" if code == 0 else "error")
            span_h.add_event(
                "command_exited",
                {"command": command_name, "exit_code": code, "duration_seconds": dur},
            )
            record_metric(
                "devops_cli_command_total",
                1.0,
                attributes={"command": command_name, "status": "ok" if code == 0 else "error"},
            )
            record_metric(
                "devops_cli_command_duration_seconds",
                dur,
                unit="s",
                attributes={"command": command_name},
            )
            raise typer.Exit(code) from exc


for _name, (_module_path, _help) in _COMMAND_SPECS.items():
    app.add_typer(f"{_module_path}:app", name=_name, help=_help)


def _version_callback(value: bool) -> None:
    if value:
        from devops_cli.output import get_console

        get_console().print(f"devops-cli [bold green]{__version__}[/bold green]")
        raise typer.Exit()


@app.callback()
def main(
    ctx: typer.Context,
    version: bool = typer.Option(
        False,
        "--version",
        "-v",
        callback=_version_callback,
        is_eager=True,
        help=HELP.main.version,
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help=HELP.main.dry_run,
    ),
) -> None:
    """DevOps CLI — manage repos, SSH keys, Kubernetes, and more."""
    _timing["start"] = time.monotonic()
    set_dry_run(dry_run)
    ctx.obj = {"dry_run": dry_run}


def main_entry() -> None:
    """Fast CLI entrypoint dispatcher."""
    from devops_cli.entry import main

    main()
