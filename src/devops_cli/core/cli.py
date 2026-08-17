"""CLI application creation helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import typer

from devops_cli.config.constants import CONST_HELP_OPTION_NAMES


def new_typer(**kwargs: Any) -> typer.Typer:
    """Create a Typer app with consistent help option names."""
    context_settings = dict(kwargs.pop("context_settings", {}))
    context_settings.setdefault("help_option_names", list(CONST_HELP_OPTION_NAMES))
    return typer.Typer(context_settings=context_settings, **kwargs)


def repo_label(repo_dir: Path) -> str:
    """Return the "<group>/<repo>" display label for a cloned repository directory."""
    return f"{repo_dir.parent.name}/{repo_dir.name}"
