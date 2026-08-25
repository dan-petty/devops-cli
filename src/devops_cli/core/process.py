"""Subprocess execution utility with consolidated timeouts, error handling, and dry-run support."""

from __future__ import annotations

import os
import subprocess
import time
from pathlib import Path

from devops_cli.config.defaults import DEFAULT_SUBPROCESS_TIMEOUT_SECONDS
from devops_cli.dry_run import is_dry_run
from devops_cli.output import print_dry_run_command
from devops_cli.telemetry import record_metric, trace_span
from devops_cli.telemetry.tracer import get_tracer

_QUIET_SUBPROCESS_ARGS = frozenset(
    {"rev-parse", "symbolic-ref", "for-each-ref", "diff", "cat-file", "tag", "remote", "status"}
)


def run_subprocess(
    cmd: list[str],
    *,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
    capture_output: bool = True,
    text: bool = True,
    check: bool = False,
    quiet: bool = False,
    timeout: float = DEFAULT_SUBPROCESS_TIMEOUT_SECONDS,
) -> subprocess.CompletedProcess[str]:
    """Execute a subprocess command with unified timeout bounds, dry-run reporting,
    W3C trace context propagation, and OTel tracing."""
    if is_dry_run() and not quiet and not _QUIET_SUBPROCESS_ARGS.intersection(cmd):
        print_dry_run_command(cmd, cwd=str(cwd) if cwd else None)

    bin_name = Path(cmd[0]).name if cmd else "unknown"
    cmd_summary = " ".join(cmd[:8]) + ("..." if len(cmd) > 8 else "") if cmd else ""
    t0 = time.perf_counter()

    sub_env = dict(env or os.environ)

    with trace_span(
        f"subprocess.{bin_name}",
        attributes={
            "subprocess.bin": bin_name,
            "subprocess.cmd": cmd_summary,
            "subprocess.args_count": len(cmd),
            "subprocess.cwd": str(cwd or ""),
            "subprocess.timeout_seconds": timeout,
            "process.executable.name": bin_name,
            "process.command_line": cmd_summary,
            "process.working_directory": str(cwd or ""),
        },
    ) as span_h:
        # Inject active subprocess span as parent trace context for child process
        get_tracer().inject_trace_context(sub_env)
        try:
            proc = subprocess.run(
                cmd,
                cwd=cwd,
                env=sub_env,
                capture_output=capture_output,
                text=text,
                check=check,
                timeout=timeout,
            )
        except FileNotFoundError:
            dur = time.perf_counter() - t0
            span_h.set_attribute("subprocess.executable_found", False)
            span_h.set_attribute("subprocess.exit_code", 127)
            span_h.set_attribute("process.exit.code", 127)
            span_h.set_attribute("subprocess.duration_seconds", dur)
            span_h.set_attribute("subprocess.status", "not_found")
            span_h.add_event("subprocess_not_found", {"bin": bin_name})
            if check:
                raise
            return subprocess.CompletedProcess(
                cmd,
                returncode=127,
                stdout="",
                stderr=f"Executable '{bin_name}' not found in PATH",
            )

        ret_code = getattr(proc, "returncode", 0)
        stdout_val = getattr(proc, "stdout", None)
        stderr_val = getattr(proc, "stderr", None)

        dur = time.perf_counter() - t0
        span_h.set_attribute("subprocess.exit_code", ret_code)
        span_h.set_attribute("process.exit.code", ret_code)
        span_h.set_attribute("subprocess.duration_seconds", dur)
        span_h.set_attribute("subprocess.status", "ok" if ret_code == 0 else "non_zero")

        if stdout_val is not None:
            stdout_len = (
                len(stdout_val.encode("utf-8")) if isinstance(stdout_val, str) else len(stdout_val)
            )
            span_h.set_attribute("subprocess.stdout_bytes", stdout_len)
        if stderr_val is not None:
            stderr_len = (
                len(stderr_val.encode("utf-8")) if isinstance(stderr_val, str) else len(stderr_val)
            )
            span_h.set_attribute("subprocess.stderr_bytes", stderr_len)

        if ret_code != 0 and check:
            span_h.set_attribute("error", True)
            err_sample = (
                (stderr_val or stdout_val or "")[:400]
                if isinstance(stderr_val or stdout_val, str)
                else ""
            )
            if err_sample:
                span_h.set_attribute("subprocess.error_sample", err_sample)
            span_h.add_event(
                "subprocess_failed",
                {"exit_code": ret_code, "error_sample": err_sample},
            )
        else:
            span_h.add_event(
                "subprocess_completed",
                {"exit_code": ret_code, "duration_seconds": dur},
            )

        record_metric(
            "devops_cli_subprocess_seconds",
            dur,
            unit="s",
            attributes={"bin": bin_name, "status": "ok" if ret_code == 0 else "error"},
        )
        return proc
