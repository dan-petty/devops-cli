"""uv command wrappers for environment and task management."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Annotated

import typer
from rich import print as rprint

from devops_cli.config.defaults import DEFAULT_SUBPROCESS_TIMEOUT_SECONDS
from devops_cli.core.cli import new_typer
from devops_cli.core.process import run_subprocess
from devops_cli.lang import ERRORS, HELP

app = new_typer(help=HELP.uv.app, no_args_is_help=True)

# Repo root: src/devops_cli/commands/uv.py -> parents[3]
_ROOT = Path(__file__).resolve().parents[3]


def _run(cmd: Sequence[str]) -> None:
    full_cmd = list(cmd)
    if full_cmd and full_cmd[0] == "uv" and "--preview-features" not in full_cmd:
        full_cmd[1:1] = ["--preview-features", "malware-check"]
    result = run_subprocess(
        full_cmd, cwd=_ROOT, timeout=DEFAULT_SUBPROCESS_TIMEOUT_SECONDS, capture_output=False
    )
    if result.returncode != 0:
        raise typer.Exit(result.returncode)


@app.command()
def sync(
    frozen: Annotated[bool, typer.Option("--frozen", help="Do not update lockfile")] = False,
) -> None:
    """Sync project dependencies into the virtual environment."""
    cmd = ["uv", "sync"]
    if frozen:
        cmd.append("--frozen")
    _run(cmd)


@app.command()
def lock(
    upgrade: Annotated[
        bool,
        typer.Option("--upgrade", help="Upgrade dependencies while locking"),
    ] = False,
) -> None:
    """Regenerate the uv lockfile."""
    cmd = ["uv", "lock"]
    if upgrade:
        cmd.append("--upgrade")
    _run(cmd)


@app.command(name="python-install")
def python_install(
    version: Annotated[
        str | None,
        typer.Option(
            "--version",
            "-v",
            help="Python version to install (defaults to .python-version)",
        ),
    ] = None,
) -> None:
    """Install project Python version with uv."""
    if version is None:
        version = (
            (_ROOT / ".python-version").read_text(encoding="utf-8").strip()
            if (_ROOT / ".python-version").exists()
            else None
        )

    if not version:
        rprint(f"[red]{ERRORS.uv.no_version_provided}[/red]")
        raise typer.Exit(1)

    import re

    if not re.match(r"^\d+(\.\d+)*[a-zA-Z0-9._-]*$", version):
        rprint(f"[red]{ERRORS.uv.invalid_version_format.format(version=version)}[/red]")
        raise typer.Exit(1)

    _run(["uv", "python", "install", version])


# NOTE (Design Justification - AGENTS.md §2): `devops uv run` is an intentional CLI proxy for
# local workstation tasks; execution is scoped strictly to the engineer's container.
@app.command(context_settings={"allow_extra_args": True, "ignore_unknown_options": True})
def run(ctx: typer.Context) -> None:
    """Run an arbitrary command using `uv run`.

    Example:
      devops uv run -- pytest -q
    """
    if not ctx.args:
        rprint(f"[red]{ERRORS.uv.missing_command}[/red]")
        raise typer.Exit(1)

    _run(["uv", "run", *ctx.args])
