"""Helpers for the tests of the roadmap's due jobs."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any


def due_job_runner(name: str) -> Callable[..., Any]:
    """The runner of the row `name` in the default due table, as a due round calls it."""
    from devops_cli.roadmap.run import DEFAULT_DUE_TABLE

    return next(row.runner for row in DEFAULT_DUE_TABLE if row.name == name)
