"""DevOps CLI entry point with lazy command delegation."""

from __future__ import annotations

import atexit
import time
from importlib import import_module
from typing import Final

import typer
from rich import print as rprint
from rich.console import Console

from devops_cli import __version__
from devops_cli.core.cli import new_typer
from devops_cli.dry_run import is_dry_run, set_dry_run

_console = Console(stderr=True)
_timing: dict[str, float] = {}


def _print_elapsed() -> None:
    if "start" in _timing:
        elapsed = time.monotonic() - _timing["start"]
        _console.print(f"[dim]Elapsed: {elapsed:.2f}s[/dim]")


atexit.register(_print_elapsed)

# command -> (module path, help text)
_COMMAND_SPECS: Final[dict[str, tuple[str, str]]] = {
    "repos": ("devops_cli.commands.repos", "Clone and manage repositories."),
    "ssh": ("devops_cli.commands.ssh", "SSH key generation, rotation, and GitHub registration."),
    "branches": ("devops_cli.commands.branches", "Branch management and Jira workflows."),
    "devcontainer": ("devops_cli.commands.devcontainer", "Manage devcontainer configurations."),
    "workspace": ("devops_cli.commands.workspace", "Manage VS Code workspace files."),
    "install-tools": ("devops_cli.commands.install_tools", "Install DevOps tool binaries."),
    "k8s": ("devops_cli.commands.k8s", "Kubernetes resource management."),
    "kustomize": ("devops_cli.commands.kustomize", "Kustomize operations."),
    "docker": ("devops_cli.commands.docker", "Docker image management."),
    "grafana": ("devops_cli.commands.grafana", "Grafana dashboard and alert management."),
    "prometheus": ("devops_cli.commands.prometheus", "Prometheus query and rule management."),
    "argo": ("devops_cli.commands.argo", "Argo CD, Workflows, and Rollouts management."),
    "config": ("devops_cli.commands.config", "Manage devops-cli configuration."),
    "ci": ("devops_cli.commands.ci", "Run tests, linting, formatting, and type-checks."),
    "uv": ("devops_cli.commands.uv", "Run uv commands through devops."),
    "scan": ("devops_cli.commands.scan", "Security, vulnerability, secret, and IaC scanner."),
    "ai": ("devops_cli.commands.ai", "Configure and test AI providers."),
    "review": ("devops_cli.commands.review", "AI-powered code reviews using expert personas."),
    "mcp": ("devops_cli.commands.mcp", "FastMCP server for Model Context Protocol integration."),
    "docs": ("devops_cli.commands.docs", "Generate and validate CLI and API documentation."),
    "release": (
        "devops_cli.commands.release",
        "Manage release cycles, version bumping, changelogs, and release verification.",
    ),
    "tf": (
        "devops_cli.commands.tf",
        "OpenTofu and Terraform Infrastructure-as-Code operations.",
    ),
    "tofu": (
        "devops_cli.commands.tf",
        "OpenTofu and Terraform Infrastructure-as-Code operations (alias for tf).",
    ),
}


app = new_typer(
    name="devops",
    help="DevOps CLI — manage repos, SSH keys, Kubernetes, and more.",
    no_args_is_help=True,
    rich_markup_mode="rich",
)


def _delegate(module_path: str, command_name: str, args: list[str]) -> None:
    module = import_module(module_path)
    module_app = module.app
    command = typer.main.get_command(module_app)
    try:
        result = command.main(
            args=args,
            prog_name=f"devops {command_name}",
            standalone_mode=False,
        )
        if isinstance(result, int) and result != 0:
            raise typer.Exit(result)
    except SystemExit as exc:  # pragma: no cover - defensive for wrapped click exits
        code = exc.code if isinstance(exc.code, int) else 1
        raise typer.Exit(code) from exc


def _register_command_proxy(name: str, module_path: str, help_text: str) -> None:
    @app.command(
        name=name,
        help=help_text,
        add_help_option=False,
        context_settings={
            "allow_extra_args": True,
            "ignore_unknown_options": True,
        },
    )
    def _proxy(ctx: typer.Context) -> None:
        if is_dry_run():
            args = ["devops", name, *list(ctx.args)]
            rendered = " ".join(args)
            rprint(
                f"[yellow][dry-run][/yellow] Would run delegated command: [cyan]{rendered}[/cyan]"
            )
            return
        _delegate(module_path, name, list(ctx.args))


def _register_typer_group(name: str, module_path: str) -> None:
    module = import_module(module_path)
    module_app = module.app
    app.add_typer(module_app, name=name)


for _name, (_module_path, _help) in _COMMAND_SPECS.items():
    if _name == "review":
        _register_typer_group(_name, _module_path)
    else:
        _register_command_proxy(_name, _module_path, _help)


def _version_callback(value: bool) -> None:
    if value:
        rprint(f"devops-cli [bold green]{__version__}[/bold green]")
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
        help="Show version and exit.",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help=(
            "Show debug output of commands and AI requests without executing delegated "
            "subcommands or external write actions."
        ),
    ),
) -> None:
    """DevOps CLI — manage repos, SSH keys, Kubernetes, and more."""
    _timing["start"] = time.monotonic()
    set_dry_run(dry_run)
    ctx.obj = {"dry_run": dry_run}
