"""DevOps CLI entry point with lazy command delegation."""

from __future__ import annotations

from importlib import import_module
from typing import Final

import typer
from rich import print as rprint

from devops_cli import __version__
from devops_cli.cli import new_typer

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
    "ai": ("devops_cli.commands.ai", "Configure and test AI providers."),
    "review": ("devops_cli.commands.review", "AI-powered code reviews using expert personas."),
}

app = new_typer(
    name="devops",
    help="DevOps CLI — manage repos, SSH keys, Kubernetes, and more.",
    no_args_is_help=True,
    rich_markup_mode="rich",
)


def _delegate(module_path: str, command_name: str, args: list[str]) -> None:
    module = import_module(module_path)
    module_app = getattr(module, "app")
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
        context_settings={"allow_extra_args": True, "ignore_unknown_options": True},
    )
    def _proxy(ctx: typer.Context) -> None:
        _delegate(module_path, name, list(ctx.args))


for _name, (_module_path, _help) in _COMMAND_SPECS.items():
    _register_command_proxy(_name, _module_path, _help)


def _version_callback(value: bool) -> None:
    if value:
        rprint(f"devops-cli [bold green]{__version__}[/bold green]")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        False,
        "--version",
        "-v",
        callback=_version_callback,
        is_eager=True,
        help="Show version and exit.",
    ),
) -> None:
    """DevOps CLI — manage repos, SSH keys, Kubernetes, and more."""
