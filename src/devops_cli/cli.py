"""Shared CLI helpers."""

from __future__ import annotations

from typing import Any

import typer

from devops_cli.defaults import HELP_OPTION_NAMES


def new_typer(**kwargs: Any) -> typer.Typer:
    """Create a Typer app with consistent help option names."""
    context_settings = dict(kwargs.pop("context_settings", {}))
    context_settings.setdefault("help_option_names", list(HELP_OPTION_NAMES))
    return typer.Typer(context_settings=context_settings, **kwargs)
