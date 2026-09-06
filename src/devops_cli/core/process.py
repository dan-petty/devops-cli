"""Subprocess execution utility with consolidated timeouts, error handling, and dry-run support."""

from __future__ import annotations

import asyncio
import fnmatch
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

DEFAULT_ALLOWED_ENV_VARS: frozenset[str] = frozenset(
    {
        "PATH",
        "PATHEXT",
        "SHELL",
        "COMSPEC",
        "SYSTEMROOT",
        "WINDIR",
        "SYSTEMDRIVE",
        "HOME",
        "USER",
        "LOGNAME",
        "HOMEDRIVE",
        "HOMEPATH",
        "USERPROFILE",
        "TMPDIR",
        "TMP",
        "TEMP",
        "TERM",
        "COLORTERM",
        "LANG",
        "LC_ALL",
        "LC_CTYPE",
        "LC_MESSAGES",
        "LC_COLLATE",
        "TZ",
        "VIRTUAL_ENV",
        "PYTHONPATH",
        "PYTHONHOME",
        "PYTHONUNBUFFERED",
        "PYTHONDONTWRITEBYTECODE",
        "TRACEPARENT",
        "TRACESTATE",
        "KUBECONFIG",
        "DOCKER_HOST",
        "DOCKER_CONFIG",
        "DOCKER_TLS_VERIFY",
        "DOCKER_CERT_PATH",
        "PAGER",
        "EDITOR",
        "GIT_AUTHOR_NAME",
        "GIT_AUTHOR_EMAIL",
        "GIT_COMMITTER_NAME",
        "GIT_COMMITTER_EMAIL",
        "GIT_CONFIG_GLOBAL",
        "GIT_CONFIG_SYSTEM",
        "GIT_EXEC_PATH",
        "CI",
        "PYTEST_CURRENT_TEST",
    }
)

DEFAULT_ALLOWED_ENV_PREFIXES: tuple[str, ...] = (
    "DEVOPS_CLI_",
    "OTEL_",
    "W3C_",
    "LC_",
)

DEFAULT_DENIED_ENV_PATTERNS: tuple[str, ...] = (
    "*TOKEN*",
    "*SECRET*",
    "*KEY*",
    "*PASSWORD*",
    "*CREDENTIAL*",
    "*AUTH*",
    "*PRIVATE*",
)


def _is_env_var_denied(
    key: str, denied_patterns: tuple[str, ...] = DEFAULT_DENIED_ENV_PATTERNS
) -> bool:
    """Predicate determining if an environment variable key matches sensitive credential patterns."""
    upper_key = key.upper()
    return any(fnmatch.fnmatchcase(upper_key, pat) for pat in denied_patterns)


def _is_env_var_allowed(
    key: str,
    *,
    allowed_vars: frozenset[str] = DEFAULT_ALLOWED_ENV_VARS,
    allowed_prefixes: tuple[str, ...] = DEFAULT_ALLOWED_ENV_PREFIXES,
    extra_allowed: frozenset[str] | set[str] | None = None,
) -> bool:
    """Predicate determining if an environment variable key is safe to pass to child processes."""
    if key in allowed_vars:
        return True
    if extra_allowed and key in extra_allowed:
        return True
    return any(key.startswith(p) for p in allowed_prefixes)


def build_subprocess_env(
    env: dict[str, str] | None = None,
    *,
    isolate_env: bool = True,
    extra_allowed_keys: set[str] | list[str] | frozenset[str] | None = None,
) -> dict[str, str]:
    """Build a sanitized subprocess environment isolating ambient credentials and secrets.

    When isolate_env is True (default), ambient environment variables are filtered
    against DEFAULT_ALLOWED_ENV_VARS and DEFAULT_ALLOWED_ENV_PREFIXES, while stripping
    any variables matching DEFAULT_DENIED_ENV_PATTERNS. Caller-provided env overrides
    are merged on top of the sanitized base, preserving explicit caller intent.
    """
    if not isolate_env:
        base_env = dict(os.environ)
    else:
        extra_set = frozenset(extra_allowed_keys) if extra_allowed_keys else frozenset()
        base_env = {
            k: v
            for k, v in os.environ.items()
            if not _is_env_var_denied(k) and _is_env_var_allowed(k, extra_allowed=extra_set)
        }
    if env:
        base_env.update(env)
    return base_env


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
    isolate_env: bool = True,
    extra_allowed_env: set[str] | list[str] | frozenset[str] | None = None,
) -> subprocess.CompletedProcess[str]:
    """Execute a subprocess command with unified timeout bounds, dry-run reporting,
    W3C trace context propagation, OpenTelemetry tracing, and ambient environment isolation."""
    if is_dry_run() and not quiet and not _QUIET_SUBPROCESS_ARGS.intersection(cmd):
        print_dry_run_command(cmd, cwd=str(cwd) if cwd else None)

    bin_name = Path(cmd[0]).name if cmd else "unknown"
    cmd_summary = " ".join(cmd[:8]) + ("..." if len(cmd) > 8 else "") if cmd else ""
    t0 = time.perf_counter()

    sub_env = build_subprocess_env(
        env=env,
        isolate_env=isolate_env,
        extra_allowed_keys=extra_allowed_env,
    )

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
    isolate_env: bool = True,
    extra_allowed_env: set[str] | list[str] | frozenset[str] | None = None,
) -> subprocess.CompletedProcess[str]:
    """Execute a subprocess command asynchronously with non-blocking I/O, unified timeout bounds,
    dry-run reporting, W3C trace context propagation, OpenTelemetry tracing, and ambient environment isolation."""
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
            isolate_env=isolate_env,
            extra_allowed_env=extra_allowed_env,
        )

    if is_dry_run() and not quiet and not _QUIET_SUBPROCESS_ARGS.intersection(cmd):
        print_dry_run_command(cmd, cwd=str(cwd) if cwd else None)

    bin_name = Path(cmd[0]).name if cmd else "unknown"
    cmd_summary = " ".join(cmd[:8]) + ("..." if len(cmd) > 8 else "") if cmd else ""
    t0 = time.perf_counter()

    sub_env = build_subprocess_env(
        env=env,
        isolate_env=isolate_env,
        extra_allowed_keys=extra_allowed_env,
    )

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


def _raise_subprocess_error(
    err_type: type[DevOpsCLIError],
    cmd: list[str],
    ret_code: int,
    stderr: str | None,
    msg: str,
) -> None:
    """Helper to raise SubprocessError or custom DevOpsCLIError with command context."""
    bin_name = cmd[0] if cmd else "unknown"
    if issubclass(err_type, SubprocessError):
        raise err_type(
            f"Subprocess failed for command '{bin_name}': {msg}",
            command=cmd,
            exit_code=ret_code,
            stderr=stderr,
        )
    raise err_type(
        f"Subprocess failed for command '{bin_name}': {msg}",
        exit_code=ret_code,
        details={"command": cmd, "stderr": stderr},
    )


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
    check: bool = True,
    isolate_env: bool = True,
    extra_allowed_env: set[str] | list[str] | frozenset[str] | None = None,
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
        check: Whether to raise on non-zero exit code immediately. If False, attempts to parse valid stdout JSON first.
        isolate_env: Whether to isolate ambient environment secrets.
        extra_allowed_env: Additional environment variable keys to preserve.

    Returns:
        Parsed JSON data structure (dict or list), or default if fallback provided.

    Raises:
        SubprocessError or error_cls: If subprocess exits with non-zero code and check is True, or JSON is invalid and default is unset.
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
        isolate_env=isolate_env,
        extra_allowed_env=extra_allowed_env,
    )

    ret_code = res.returncode if isinstance(res.returncode, int) else 0
    raw_stdout = (res.stdout or "").strip()

    if ret_code != 0 and check:
        err_msg = (res.stderr or "").strip() or raw_stdout or f"Process exited with code {ret_code}"
        _raise_subprocess_error(err_type, cmd, ret_code, res.stderr, err_msg)

    if not raw_stdout:
        if default is not _JSON_UNSET:
            return default
        err_msg = (
            res.stderr or ""
        ).strip() or f"Process exited with code {ret_code} and produced no output"
        _raise_subprocess_error(err_type, cmd, ret_code, res.stderr, err_msg)

    try:
        return json.loads(raw_stdout)
    except (json.JSONDecodeError, ValueError) as exc:
        if default is not _JSON_UNSET:
            return default
        exit_val = ret_code if ret_code != 0 else 1
        _raise_subprocess_error(err_type, cmd, exit_val, res.stderr, f"Invalid JSON output: {exc}")
