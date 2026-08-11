"""Subprocess execution utility with consolidated timeouts, error handling, and dry-run support."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

from rich import print as rprint

from devops_cli.config.defaults import DEFAULT_SUBPROCESS_TIMEOUT_SECONDS
from devops_cli.core.dry_run import format_command, is_dry_run

_QUIET_SUBPROCESS_ARGS = frozenset(
    {"rev-parse", "symbolic-ref", "for-each-ref", "diff", "cat-file", "tag", "remote", "status"}
)


def run_subprocess(
    cmd: list[str],
    *,
    cwd: Path | None = None,
    capture_output: bool = True,
    text: bool = True,
    check: bool = False,
    quiet: bool = False,
    timeout: float = DEFAULT_SUBPROCESS_TIMEOUT_SECONDS,
) -> subprocess.CompletedProcess[Any]:
    """Execute a subprocess command with unified timeout bounds and dry-run reporting."""
    if is_dry_run() and not quiet and not _QUIET_SUBPROCESS_ARGS.intersection(cmd):
        rendered = format_command(cmd, cwd=str(cwd) if cwd else None)
        rprint(f"[yellow][dry-run][/yellow] Would run command: [cyan]{rendered}[/cyan]")
    return subprocess.run(
        cmd,
        cwd=cwd,
        capture_output=capture_output,
        text=text,
        check=check,
        timeout=timeout,
    )
