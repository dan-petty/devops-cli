"""Core CLI infrastructure: application creation and execution context."""

from __future__ import annotations

from devops_cli.core.cli import new_typer, repo_label
from devops_cli.core.dry_run import format_command, is_dry_run, set_dry_run
from devops_cli.core.process import run_subprocess
from devops_cli.core.repo import (
    find_repo_root,
    is_ignored_by_git,
    list_repo_files,
    read_gitignore_patterns,
)

__all__ = [
    "find_repo_root",
    "format_command",
    "is_dry_run",
    "is_ignored_by_git",
    "list_repo_files",
    "new_typer",
    "read_gitignore_patterns",
    "repo_label",
    "run_subprocess",
    "set_dry_run",
]
