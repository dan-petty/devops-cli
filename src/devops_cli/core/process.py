"""Subprocess execution utility with consolidated timeouts, error handling, and dry-run support."""

from __future__ import annotations

import asyncio
import fnmatch
import json
import os
import signal
import subprocess
import threading
import time
from pathlib import Path
from typing import Any

from devops_cli.config.constants import (
    CONST_EXIT_COMMAND_NOT_FOUND,
    CONST_GH_AUTH_SUBCOMMAND,
    CONST_GH_CLI,
    CONST_GH_LOGIN_ENV_VARS,
    CONST_GH_NON_API_COMMANDS,
    CONST_GH_TOKEN_ENV,
    CONST_GH_TOKEN_ENV_VARS,
    CONST_GIT_CLI,
)
from devops_cli.config.defaults import (
    DEFAULT_GH_AUTH_TOKEN_RETRY_SECONDS,
    DEFAULT_GH_AUTH_TOKEN_TIMEOUT_SECONDS,
    DEFAULT_SHELL_STOP_GRACE_SECONDS,
    DEFAULT_SHELL_STOP_POLL_SECONDS,
    DEFAULT_SUBPROCESS_TIMEOUT_SECONDS,
)
from devops_cli.dry_run import is_dry_run
from devops_cli.exceptions.base import DevOpsCLIError
from devops_cli.exceptions.git import GitHubUnauthenticatedError
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
    upper_key = key.upper()
    if upper_key in allowed_vars:
        return True
    if extra_allowed and (key in extra_allowed or upper_key in extra_allowed):
        return True
    return any(upper_key.startswith(p.upper()) for p in allowed_prefixes)


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
        extra_set = (
            frozenset(extra_allowed_keys) | frozenset(k.upper() for k in extra_allowed_keys)
            if extra_allowed_keys
            else frozenset()
        )
        base_env = {
            k: v
            for k, v in os.environ.items()
            if not _is_env_var_denied(k) and _is_env_var_allowed(k, extra_allowed=extra_set)
        }
    if env:
        from devops_cli.exceptions.security import SecurityError

        dangerous_env_keys = {
            "LD_PRELOAD",
            "LD_LIBRARY_PATH",
            "DYLD_INSERT_LIBRARIES",
            "DYLD_LIBRARY_PATH",
            "BASH_ENV",
            "ENV",
        }
        for k, v in env.items():
            if k.upper() in dangerous_env_keys:
                raise SecurityError(f"Prohibited dangerous environment variable override: '{k}'")
            if "\x00" in k or "\x00" in str(v):
                raise SecurityError(f"Null byte in environment variable prohibited: '{k}'")
            base_env[k] = str(v)
    return base_env


def _sanitize_command_for_telemetry(cmd: list[str]) -> str:
    """Produce a sanitized, bounded command summary for telemetry and spans."""
    from devops_cli.security.sanitizer import mask_secrets

    if not cmd:
        return ""
    sanitized_parts: list[str] = []
    redact_next = False
    for arg in cmd[:8]:
        if redact_next:
            sanitized_parts.append("[REDACTED]")
            redact_next = False
            continue
        if arg in ("--comment", "-c", "--body", "-b"):
            sanitized_parts.append(arg)
            redact_next = True
        elif any(arg.startswith(prefix) for prefix in ("title=", "body=", "comment=")):
            key = arg.split("=", 1)[0]
            sanitized_parts.append(f"{key}=[REDACTED]")
        else:
            masked = mask_secrets(arg)
            sanitized_parts.append(masked[:57] + "..." if len(masked) > 60 else masked)
    summary = " ".join(sanitized_parts) + ("..." if len(cmd) > 8 else "")
    return mask_secrets(summary)[:256]


def _validate_subprocess_cwd(cwd: Path | str | None) -> None:
    """Validate that subprocess working directory does not violate traversal or system path security."""
    if cwd is None:
        return
    from devops_cli.core.paths import is_forbidden_system_path, validate_no_path_traversal
    from devops_cli.exceptions.security import SecurityError

    validate_no_path_traversal(str(cwd), label="subprocess cwd")
    resolved_cwd = Path(cwd).resolve()
    if is_forbidden_system_path(resolved_cwd):
        raise SecurityError(f"Subprocess cwd cannot reside in forbidden system directory: '{cwd}'.")


# The process's one GitHub identity (#767): None until a lookup finds a token, then that token.
# A lookup that finds none is not kept, so a later call looks again; when and why it last failed
# is kept, for the error and for git, which waits before looking again.
_github_token: str | None = None
_github_lookup_failure: tuple[float, str] | None = None
_GITHUB_TOKEN_LOCK = threading.Lock()


def _lookup_github_token() -> tuple[str, str]:
    """Run `gh auth token`; it applies GH_TOKEN, then GITHUB_TOKEN, then gh's stored login.

    The child is a `gh auth` call, so it gets the ambient tokens and never a pinned one. Returns
    the token, or "" and the unauthenticated error's message when there is none.
    """
    from devops_cli.lang import ERRORS

    timeout = DEFAULT_GH_AUTH_TOKEN_TIMEOUT_SECONDS
    try:
        proc = run_subprocess(
            [CONST_GH_CLI, CONST_GH_AUTH_SUBCOMMAND, "token"],
            check=False,
            quiet=True,
            timeout=timeout,
            extra_allowed_env=CONST_GH_LOGIN_ENV_VARS,
        )
    except subprocess.TimeoutExpired:
        reason = ERRORS.git.github_token_lookup_timed_out.format(seconds=timeout)
        return "", ERRORS.git.github_token_lookup_failed.format(reason=reason)
    except OSError as err:
        return "", ERRORS.git.github_token_lookup_failed.format(reason=type(err).__name__)
    token = proc.stdout.strip() if proc.returncode == 0 else ""
    if token:
        return token, ""
    if proc.returncode == CONST_EXIT_COMMAND_NOT_FOUND:
        reason = ERRORS.git.github_token_lookup_not_found
        return "", ERRORS.git.github_token_lookup_failed.format(reason=reason)
    return "", ERRORS.git.github_unauthenticated.format(status=proc.returncode)


def _session_github_token(*, retry_now: bool) -> tuple[str, str]:
    """The session's token, looked up on first use; or "" and why gh gave none.

    A found token is kept for the life of the process. Without one, `retry_now` looks again at
    once (gh); otherwise a lookup that failed within the retry interval stands (git).
    """
    global _github_token, _github_lookup_failure
    with _GITHUB_TOKEN_LOCK:
        if _github_token:
            return _github_token, ""
        failure = _github_lookup_failure
        if (
            failure is not None
            and not retry_now
            and time.monotonic() - failure[0] < DEFAULT_GH_AUTH_TOKEN_RETRY_SECONDS
        ):
            return "", failure[1]
        token, why = _lookup_github_token()
        if token:
            _github_token, _github_lookup_failure = token, None
        else:
            _github_lookup_failure = (time.monotonic(), why)
        return token, why


def github_token() -> str:
    """The session's GitHub token, raising the unauthenticated error when gh has none."""
    token, why = _session_github_token(retry_now=True)
    if not token:
        raise GitHubUnauthenticatedError(why)
    return token


def reset_github_token() -> None:
    """Forget the looked-up token, so the next GitHub call runs `gh auth token` again."""
    global _github_token, _github_lookup_failure
    with _GITHUB_TOKEN_LOCK:
        _github_token, _github_lookup_failure = None, None


def is_local_gh_command(gh_args: list[str]) -> bool:
    """Whether gh's arguments make no call of the session's: `gh auth`, version or help.

    These need no identity, so they run before one is resolved and outside the pin.
    """
    return not gh_args or gh_args[0].lower() in CONST_GH_NON_API_COMMANDS


def _github_client_name(cmd: list[str]) -> str | None:
    """The GitHub client a command runs, gh or git, or None for any other program."""
    name = Path(cmd[0]).name if cmd else ""
    return name if name in (CONST_GH_CLI, CONST_GIT_CLI) else None


def _pin_github_token(
    cmd: list[str], sub_env: dict[str, str], caller_env: dict[str, str] | None = None
) -> None:
    """Give a gh or git child GH_TOKEN set to the session's token, and no other GitHub token.

    gh's local commands (`gh auth` subcommands, version and help) are exempt: they get the
    GH_TOKEN and GITHUB_TOKEN of the environment, or of `caller_env` where the caller set them,
    unchanged. Other gh calls without a token raise the unauthenticated error before they run;
    git runs without one.
    """
    client = _github_client_name(cmd)
    if client is None:
        return
    for name in CONST_GH_TOKEN_ENV_VARS:
        sub_env.pop(name, None)
    if client == CONST_GH_CLI and is_local_gh_command(cmd[1:]):
        given = {**os.environ, **(caller_env or {})}
        sub_env.update(
            {name: str(given[name]) for name in CONST_GH_TOKEN_ENV_VARS if name in given}
        )
        return
    if client == CONST_GH_CLI:
        token = github_token()
    else:
        token, _ = _session_github_token(retry_now=False)
    if token:
        sub_env[CONST_GH_TOKEN_ENV] = token


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
    _validate_subprocess_cwd(cwd)
    if is_dry_run() and not quiet and not _QUIET_SUBPROCESS_ARGS.intersection(cmd):
        print_dry_run_command(cmd, cwd=str(cwd) if cwd else None)

    bin_name = Path(cmd[0]).name if cmd else "unknown"
    cmd_summary = _sanitize_command_for_telemetry(cmd)
    start_time = time.perf_counter()

    sub_env = build_subprocess_env(
        env=env,
        isolate_env=isolate_env,
        extra_allowed_keys=extra_allowed_env,
    )
    _pin_github_token(cmd, sub_env, env)

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
        get_tracer().inject_trace_env(sub_env)
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
            dur = time.perf_counter() - start_time
            span_h.set_attribute("subprocess.executable_found", False)
            span_h.set_attribute("subprocess.exit_code", CONST_EXIT_COMMAND_NOT_FOUND)
            span_h.set_attribute("process.exit.code", CONST_EXIT_COMMAND_NOT_FOUND)
            span_h.set_attribute("subprocess.duration_seconds", dur)
            span_h.set_attribute("subprocess.status", "not_found")
            span_h.add_event("subprocess_not_found", {"bin": bin_name})
            if check:
                raise
            return subprocess.CompletedProcess(
                cmd,
                returncode=CONST_EXIT_COMMAND_NOT_FOUND,
                stdout="",
                stderr=f"Executable '{bin_name}' not found in PATH",
            )

        ret_code = getattr(proc, "returncode", 0)
        stdout_val = getattr(proc, "stdout", None)
        stderr_val = getattr(proc, "stderr", None)

        dur = time.perf_counter() - start_time
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
            from devops_cli.security.sanitizer import mask_secrets

            err_sample = mask_secrets(raw_sample) if raw_sample else ""
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


def _signal_process_group(pgid: int, sig: int) -> bool:
    """Send a signal to the process group, returning False if unreachable."""
    if not hasattr(os, "killpg"):
        return False
    try:
        os.killpg(pgid, sig)
    except ProcessLookupError, PermissionError:
        return False
    return True


def _is_invalid_pgid(pgid: int | None) -> bool:
    """Check whether a pgid is invalid or belongs to the current process group."""
    if not isinstance(pgid, int) or pgid <= 1:
        return True
    return bool(hasattr(os, "getpgrp") and pgid == os.getpgrp())


async def _wait_for_group_exit_async(
    proc: asyncio.subprocess.Process, pgid: int, deadline: float
) -> bool:
    """Poll for group exit until deadline. Returns True if group exited."""
    while time.monotonic() < deadline:
        if proc.returncode is not None and not _signal_process_group(pgid, 0):
            return True
        try:
            await asyncio.wait_for(proc.wait(), timeout=DEFAULT_SHELL_STOP_POLL_SECONDS)
            if not _signal_process_group(pgid, 0):
                return True
        except TimeoutError:
            pass
    return not _signal_process_group(pgid, 0)


async def _terminate_process_group_async(
    proc: asyncio.subprocess.Process,
    *,
    stop_grace_seconds: float = DEFAULT_SHELL_STOP_GRACE_SECONDS,
) -> None:
    """Terminate the process group of proc on timeout, escalating from SIGTERM to SIGKILL."""
    pgid = proc.pid
    if _is_invalid_pgid(pgid) or not _signal_process_group(pgid, signal.SIGTERM):
        proc.kill()
        await proc.wait()
        return

    deadline = time.monotonic() + stop_grace_seconds
    if await _wait_for_group_exit_async(proc, pgid, deadline):
        return

    _signal_process_group(pgid, signal.SIGKILL)
    try:
        await asyncio.wait_for(proc.wait(), timeout=stop_grace_seconds)
    except TimeoutError:
        pass


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
    _validate_subprocess_cwd(cwd)
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
    cmd_summary = _sanitize_command_for_telemetry(cmd)
    start_time = time.perf_counter()

    sub_env = build_subprocess_env(
        env=env,
        isolate_env=isolate_env,
        extra_allowed_keys=extra_allowed_env,
    )
    # The first GitHub call runs `gh auth token`, a blocking child; keep it off the event loop.
    await asyncio.to_thread(_pin_github_token, cmd, sub_env, env)

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
        get_tracer().inject_trace_env(sub_env)
        stdout_pipe = asyncio.subprocess.PIPE if capture_output else None
        stderr_pipe = asyncio.subprocess.PIPE if capture_output else None

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=cwd,
                env=sub_env,
                stdout=stdout_pipe,
                stderr=stderr_pipe,
                start_new_session=True,
            )
            try:
                stdout_bytes, stderr_bytes = await asyncio.wait_for(
                    proc.communicate(), timeout=timeout
                )
            except TimeoutError:
                await _terminate_process_group_async(proc)
                raise subprocess.TimeoutExpired(cmd, timeout) from None
        except FileNotFoundError:
            dur = time.perf_counter() - start_time
            span_h.set_attribute("subprocess.executable_found", False)
            span_h.set_attribute("subprocess.exit_code", CONST_EXIT_COMMAND_NOT_FOUND)
            span_h.set_attribute("process.exit.code", CONST_EXIT_COMMAND_NOT_FOUND)
            span_h.set_attribute("subprocess.duration_seconds", dur)
            span_h.set_attribute("subprocess.status", "not_found")
            span_h.add_event("subprocess_not_found", {"bin": bin_name})
            if check:
                raise
            return subprocess.CompletedProcess(
                cmd,
                returncode=CONST_EXIT_COMMAND_NOT_FOUND,
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

        dur = time.perf_counter() - start_time
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
            from devops_cli.security.sanitizer import mask_secrets

            err_sample = mask_secrets(raw_sample) if raw_sample else ""
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
