"""Subprocess execution utility with consolidated timeouts, error handling, and dry-run support."""

from __future__ import annotations

import subprocess
import time
from pathlib import Path
from typing import Any

from rich import print as rprint

from devops_cli.config.defaults import DEFAULT_SUBPROCESS_TIMEOUT_SECONDS
from devops_cli.core.dry_run import format_command, is_dry_run
from devops_cli.telemetry import record_metric, trace_span

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
    """Execute a subprocess command with unified timeout bounds, dry-run reporting,
    and OTel tracing."""
    if is_dry_run() and not quiet and not _QUIET_SUBPROCESS_ARGS.intersection(cmd):
        rendered = format_command(cmd, cwd=str(cwd) if cwd else None)
        rprint(f"[yellow][dry-run][/yellow] Would run command: [cyan]{rendered}[/cyan]")

    bin_name = Path(cmd[0]).name if cmd else "unknown"
    cmd_summary = " ".join(cmd[:8]) + ("..." if len(cmd) > 8 else "") if cmd else ""
    t0 = time.perf_counter()

    with trace_span(
        f"subprocess.{bin_name}",
        attributes={
            "subprocess.bin": bin_name,
            "subprocess.cmd": cmd_summary,
            "subprocess.cwd": str(cwd or ""),
        },
    ) as span_h:
        proc = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=capture_output,
            text=text,
            check=check,
            timeout=timeout,
        )
        dur = time.perf_counter() - t0
        span_h.set_attribute("subprocess.exit_code", proc.returncode)
        span_h.set_attribute("subprocess.duration_seconds", dur)
        record_metric(
            "devops_cli_subprocess_seconds",
            dur,
            unit="s",
            attributes={"bin": bin_name, "status": "ok" if proc.returncode == 0 else "error"},
        )
        return proc
