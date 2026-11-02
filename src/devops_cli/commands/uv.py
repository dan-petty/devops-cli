"""uv command wrappers for environment and task management."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Annotated, Any

import typer

from devops_cli.config.defaults import DEFAULT_SUBPROCESS_TIMEOUT_SECONDS
from devops_cli.core.cli import new_typer
from devops_cli.core.process import prepare_tool_cmd, run_subprocess
from devops_cli.dry_run import is_dry_run
from devops_cli.dry_run.decorator import dry_run_class
from devops_cli.dry_run.requests import PlannedRequest, render_request_plan
from devops_cli.lang import ERRORS, HELP
from devops_cli.output import print_error

app = new_typer(help=HELP.uv.app, no_args_is_help=True)


def _get_project_root() -> Path:
    """Find repository or worktree root containing pyproject.toml or .git."""
    from devops_cli.core.repo import find_worktree_root

    return find_worktree_root()


def _plan(cmd: Sequence[str], *, dry_run: bool) -> bool:
    """Print the one request of `cmd`, as the process runner starts it, when this is a dry run.
    It returns whether it printed the plan, so that the caller starts nothing."""
    if not (dry_run or is_dry_run()):
        return False
    argv = tuple(prepare_tool_cmd(cmd))
    request = PlannedRequest(method="uv", target=" ".join(cmd[1:2]), argv=argv)
    render_request_plan(f"devops {' '.join(cmd)}", [request])
    return True


def _dry_run_option() -> Any:
    """The `--dry-run` option of each uv command."""
    return typer.Option("--dry-run", help=HELP.options.dry_run)


def sync_argv(*, frozen: bool) -> list[str]:
    """The command of `devops uv sync`."""
    return ["uv", "sync", *(["--frozen"] if frozen else [])]


def lock_argv(*, upgrade: bool) -> list[str]:
    """The command of `devops uv lock`."""
    return ["uv", "lock", *(["--upgrade"] if upgrade else [])]


def python_install_argv(version: str) -> list[str]:
    """The command of `devops uv python-install`."""
    return ["uv", "python", "install", version]


def run_argv(args: Sequence[str]) -> list[str]:
    """The command of `devops uv run`."""
    return ["uv", "run", *args]


def _run(cmd: Sequence[str]) -> None:
    result = run_subprocess(
        cmd,
        cwd=_get_project_root(),
        timeout=DEFAULT_SUBPROCESS_TIMEOUT_SECONDS,
        capture_output=False,
    )
    if result.returncode != 0:
        raise typer.Exit(result.returncode)


@app.command()
@dry_run_class("request-plan")
def sync(
    frozen: Annotated[bool, typer.Option("--frozen", help=HELP.uv.frozen)] = False,
    dry_run: Annotated[bool, _dry_run_option()] = False,
) -> None:
    """Sync project dependencies into the virtual environment."""
    cmd = sync_argv(frozen=frozen)
    if not _plan(cmd, dry_run=dry_run):
        _run(cmd)


@app.command()
@dry_run_class("request-plan")
def lock(
    upgrade: Annotated[
        bool,
        typer.Option("--upgrade", help=HELP.uv.upgrade),
    ] = False,
    dry_run: Annotated[bool, _dry_run_option()] = False,
) -> None:
    """Regenerate the uv lockfile."""
    cmd = lock_argv(upgrade=upgrade)
    if not _plan(cmd, dry_run=dry_run):
        _run(cmd)


@app.command(name="python-install")
@dry_run_class("request-plan")
def python_install(
    version: Annotated[
        str | None,
        typer.Option(
            "--version",
            "-v",
            help=HELP.uv.version,
        ),
    ] = None,
    dry_run: Annotated[bool, _dry_run_option()] = False,
) -> None:
    """Install project Python version with uv."""
    root = _get_project_root()
    if version is None:
        version = (
            (root / ".python-version").read_text(encoding="utf-8").strip()
            if (root / ".python-version").exists()
            else None
        )

    if not version:
        print_error(ERRORS.uv.no_version_provided, prefix=False)
        raise typer.Exit(1)

    import re

    if not re.fullmatch(r"^\d+(\.\d+)*[a-zA-Z0-9._-]*$", version):
        print_error(ERRORS.uv.invalid_version_format.format(version=version), prefix=False)
        raise typer.Exit(1)

    cmd = python_install_argv(version)
    if not _plan(cmd, dry_run=dry_run):
        _run(cmd)


# NOTE (Design Justification - SECURITY.md, principle 3): `devops uv run` is an intentional CLI proxy for
# local workstation tasks; execution is scoped strictly to the engineer's container.
@app.command(context_settings={"allow_extra_args": True, "ignore_unknown_options": True})
@dry_run_class("request-plan")
def run(ctx: typer.Context, dry_run: Annotated[bool, _dry_run_option()] = False) -> None:
    """Run an arbitrary command using `uv run`.

    Example:
      devops uv run -- pytest -q

    A dry run lists the one `uv run` command and starts nothing. What that command does is
    not a request of devops-cli, so the plan does not list it.
    """
    if not ctx.args:
        print_error(ERRORS.uv.missing_command, prefix=False)
        raise typer.Exit(1)

    cmd = run_argv(ctx.args)
    if not _plan(cmd, dry_run=dry_run):
        _run(cmd)
