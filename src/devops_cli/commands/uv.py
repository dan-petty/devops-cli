"""uv command wrappers for environment and task management."""

from __future__ import annotations

import importlib
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Annotated, Any

import typer

from devops_cli.config.defaults import DEFAULT_SUBPROCESS_TIMEOUT_SECONDS
from devops_cli.core.cli import new_typer
from devops_cli.lang import ERRORS, HELP

_LAZY_OBJECT_MAPPING: dict[str, tuple[str, str]] = {
    "run_subprocess": ("devops_cli.core.process", "run_subprocess"),
    "print_error": ("devops_cli.output", "print_error"),
}


def __getattr__(name: str) -> Any:
    if name in _LAZY_OBJECT_MAPPING:
        mod_path, obj_name = _LAZY_OBJECT_MAPPING[name]
        module = importlib.import_module(mod_path)
        return getattr(module, obj_name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def _get(name: str) -> Any:
    mod_dict = sys.modules[__name__].__dict__
    if name in mod_dict:
        return mod_dict[name]
    if name in _LAZY_OBJECT_MAPPING:
        mod_path, obj_name = _LAZY_OBJECT_MAPPING[name]
        module = importlib.import_module(mod_path)
        return getattr(module, obj_name)
    return getattr(sys.modules[__name__], name)


app = new_typer(help=HELP.uv.app, no_args_is_help=True)


def _get_project_root() -> Path:
    """Find repository root containing pyproject.toml or .git."""
    from devops_cli.core.repo import find_top_level_repo_root

    return find_top_level_repo_root()


def _run(cmd: Sequence[str]) -> None:
    full_cmd = list(cmd)
    if full_cmd and full_cmd[0] == "uv" and "--preview-features" not in full_cmd:
        full_cmd[1:1] = ["--preview-features", "malware-check"]
    result = _get("run_subprocess")(
        full_cmd,
        cwd=_get_project_root(),
        timeout=DEFAULT_SUBPROCESS_TIMEOUT_SECONDS,
        capture_output=False,
    )
    if result.returncode != 0:
        raise typer.Exit(result.returncode)


@app.command()
def sync(
    frozen: Annotated[bool, typer.Option("--frozen", help=HELP.uv.frozen)] = False,
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
        typer.Option("--upgrade", help=HELP.uv.upgrade),
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
            help=HELP.uv.version,
        ),
    ] = None,
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
        _get("print_error")(ERRORS.uv.no_version_provided, prefix=False)
        raise typer.Exit(1)

    import re

    if not re.match(r"^\d+(\.\d+)*[a-zA-Z0-9._-]*$", version):
        _get("print_error")(ERRORS.uv.invalid_version_format.format(version=version), prefix=False)
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
        _get("print_error")(ERRORS.uv.missing_command, prefix=False)
        raise typer.Exit(1)

    _run(["uv", "run", *ctx.args])
