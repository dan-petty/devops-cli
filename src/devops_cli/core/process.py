"""Subprocess execution utility with consolidated timeouts, error handling, and dry-run support."""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
import time
from pathlib import Path
from typing import Any

from devops_cli.config.defaults import DEFAULT_SUBPROCESS_TIMEOUT_SECONDS
from devops_cli.dry_run import is_dry_run
from devops_cli.exceptions.base import DevOpsCLIError
from devops_cli.exceptions.tools import SubprocessError
from devops_cli.output import print_dry_run_command
from devops_cli.telemetry import record_metric, trace_span
from devops_cli.telemetry.tracer import get_tracer

_QUIET_SUBPROCESS_ARGS = frozenset(
    {"rev-parse", "symbolic-ref", "for-each-ref", "diff", "cat-file", "tag", "remote", "status"}
)


def run_subprocess(
    cmd: list[str],
    *,
    input: str | None = None,
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
                input=input,
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
            raw_sample = (
                (stderr_val or stdout_val or "")[:400]
                if isinstance(stderr_val or stdout_val, str)
                else ""
            )
            from devops_cli.ai.review.sanitization import _mask_secrets_in_content

            err_sample = _mask_secrets_in_content(raw_sample) if raw_sample else ""
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


async def run_subprocess_async(
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
    """Execute a subprocess command asynchronously with non-blocking I/O, unified timeout bounds,
    dry-run reporting, W3C trace context propagation, and OpenTelemetry tracing."""
    if getattr(subprocess.run, "__module__", "") != "subprocess":
        return await asyncio.to_thread(
            run_subprocess,
            cmd,
            cwd=cwd,
            env=env,
            capture_output=capture_output,
            text=text,
            check=check,
            quiet=quiet,
            timeout=timeout,
        )

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
        get_tracer().inject_trace_context(sub_env)
        stdout_pipe = asyncio.subprocess.PIPE if capture_output else None
        stderr_pipe = asyncio.subprocess.PIPE if capture_output else None

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=cwd,
                env=sub_env,
                stdout=stdout_pipe,
                stderr=stderr_pipe,
            )
            try:
                stdout_bytes, stderr_bytes = await asyncio.wait_for(
                    proc.communicate(), timeout=timeout
                )
            except TimeoutError:
                proc.kill()
                await proc.wait()
                raise subprocess.TimeoutExpired(cmd, timeout) from None
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

        ret_code = proc.returncode if proc.returncode is not None else 0
        stdout_str = (
            stdout_bytes.decode("utf-8", errors="replace")
            if (text and stdout_bytes is not None)
            else (stdout_bytes.decode("utf-8", errors="replace") if stdout_bytes else "")
        )
        stderr_str = (
            stderr_bytes.decode("utf-8", errors="replace")
            if (text and stderr_bytes is not None)
            else (stderr_bytes.decode("utf-8", errors="replace") if stderr_bytes else "")
        )

        dur = time.perf_counter() - t0
        span_h.set_attribute("subprocess.exit_code", ret_code)
        span_h.set_attribute("process.exit.code", ret_code)
        span_h.set_attribute("subprocess.duration_seconds", dur)
        span_h.set_attribute("subprocess.status", "ok" if ret_code == 0 else "non_zero")

        if stdout_bytes:
            span_h.set_attribute("subprocess.stdout_bytes", len(stdout_bytes))
        if stderr_bytes:
            span_h.set_attribute("subprocess.stderr_bytes", len(stderr_bytes))

        if ret_code != 0 and check:
            span_h.set_attribute("error", True)
            raw_sample = (stderr_str or stdout_str or "")[:400]
            from devops_cli.ai.review.sanitization import _mask_secrets_in_content

            err_sample = _mask_secrets_in_content(raw_sample) if raw_sample else ""
            if err_sample:
                span_h.set_attribute("subprocess.error_sample", err_sample)
            span_h.add_event(
                "subprocess_failed",
                {"exit_code": ret_code, "error_sample": err_sample},
            )
            raise subprocess.CalledProcessError(ret_code, cmd, output=stdout_str, stderr=stderr_str)

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
        return subprocess.CompletedProcess(
            cmd,
            returncode=ret_code,
            stdout=stdout_str,
            stderr=stderr_str,
        )


_JSON_UNSET = object()


def run_json_subprocess(
    cmd: list[str],
    *,
    input: str | None = None,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
    quiet: bool = True,
    timeout: float = DEFAULT_SUBPROCESS_TIMEOUT_SECONDS,
    default: Any = _JSON_UNSET,
    error_cls: type[DevOpsCLIError] | None = None,
) -> Any:
    """Execute subprocess and safely deserialize its stdout as JSON.

    Args:
        cmd: Command arguments list.
        input: Optional stdin string.
        cwd: Working directory.
        env: Environment variables override.
        quiet: Suppress output.
        timeout: Subprocess timeout in seconds.
        default: Fallback value if JSON parsing fails.
        error_cls: Exception class to raise upon command or parsing failure (defaults to SubprocessError).

    Returns:
        Parsed JSON data structure (dict or list), or default if fallback provided.

    Raises:
        SubprocessError or error_cls: If subprocess exits with non-zero code or JSON is invalid and default is unset.
    """
    err_type = error_cls or SubprocessError
    res = run_subprocess(
        cmd,
        input=input,
        cwd=cwd,
        env=env,
        quiet=quiet,
        timeout=timeout,
        check=False,
    )

    ret_code = res.returncode
    is_non_zero = isinstance(ret_code, int) and ret_code != 0

    if is_non_zero:
        err_msg = (
            (res.stderr or "").strip()
            or (res.stdout or "").strip()
            or f"Process exited with code {ret_code}"
        )
        if issubclass(err_type, SubprocessError):
            raise err_type(
                f"Subprocess failed for command '{cmd[0] if cmd else 'unknown'}': {err_msg}",
                command=cmd,
                exit_code=ret_code,
                stderr=res.stderr,
            )
        raise err_type(
            f"Subprocess failed for command '{cmd[0] if cmd else 'unknown'}': {err_msg}",
            exit_code=ret_code,
            details={"command": cmd, "stderr": res.stderr},
        )

    raw_stdout = (res.stdout or "").strip()
    if not raw_stdout and default is not _JSON_UNSET:
        return default

    try:
        return json.loads(raw_stdout)
    except (json.JSONDecodeError, ValueError) as exc:
        if default is not _JSON_UNSET:
            return default
        exit_val = ret_code if isinstance(ret_code, int) else 1
        if issubclass(err_type, SubprocessError):
            raise err_type(
                f"Failed to parse JSON output from command '{cmd[0] if cmd else 'unknown'}': {exc}",
                command=cmd,
                exit_code=exit_val,
                details={"raw_stdout": raw_stdout[:500]},
            ) from exc
        raise err_type(
            f"Failed to parse JSON output from command '{cmd[0] if cmd else 'unknown'}': {exc}",
            exit_code=exit_val,
            details={"command": cmd, "raw_stdout": raw_stdout[:500]},
        ) from exc
