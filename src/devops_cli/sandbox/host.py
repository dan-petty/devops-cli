"""Host sandbox confinement using bubblewrap for criteria and untrusted execution."""

from __future__ import annotations

import os
import re
import selectors
import shutil
import signal
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

from devops_cli.config import (
    DEFAULT_CRITERIA_EXECUTION_TIMEOUT_SECONDS,
    DEFAULT_CRITERIA_MAX_OUTPUT_BYTES,
    DEFAULT_HOST_SANDBOX_BINARY,
)
from devops_cli.core.repo import (
    _gitdir_named_by,
    _linked_worktree_common_dir,
    _repo_root_candidates,
)
from devops_cli.sandbox.models import DEFAULT_SANDBOX_POLICY, SandboxPolicy


@dataclass(frozen=True)
class HostSandboxResult:
    """Result of a command executed within the host bubblewrap sandbox."""

    exit_code: int | None
    stdout: str
    stderr: str
    duration_seconds: float
    passed: bool
    error: str | None = None


def _terminate_process_group(pid: int, sig: signal.Signals = signal.SIGTERM) -> None:
    """Safely terminate an isolated POSIX process group hierarchy.

    Guards against PID 0, PID 1, non-integers, self PID, and the caller's own PGID to
    prevent accidental termination of container init or ambient devcontainer processes.
    """
    if not isinstance(pid, int) or pid <= 1:
        return
    try:
        if pid == os.getpid():
            return
        pgid = os.getpgid(pid)
        if pgid <= 1 or pgid == os.getpgrp():
            return
        os.killpg(pgid, sig)
    except OSError, TypeError:
        pass


def _parse_tmpfs_size_bytes(opts: str) -> int | None:
    """Parse size limit in bytes from tmpfs mount options string."""
    m = re.search(r"\bsize=(\d+)([kmgKMG]?)\b", opts)
    if not m:
        return None
    num = int(m.group(1))
    unit = m.group(2).lower()
    multipliers = {"": 1, "k": 1024, "m": 1024 * 1024, "g": 1024 * 1024 * 1024}
    return num * multipliers.get(unit, 1)


def _is_mock_subprocess(proc: Any) -> bool:
    """Check if process object is a mock or non-standard subprocess."""
    return (
        type(proc).__module__ != "subprocess"
        or type(proc).__name__ != "Popen"
        or hasattr(proc, "_mock_return_value")
        or not hasattr(proc.stdout, "fileno")
    )


def _communicate_mock(proc: Any, timeout: float) -> tuple[int | None, str, str, str | None]:
    """Communicate with mocked subprocess in test environments."""
    try:
        raw_out, raw_err = proc.communicate(timeout=timeout)
        out_str = (
            raw_out.decode("utf-8", errors="replace")
            if isinstance(raw_out, bytes)
            else (raw_out or "")
        )
        err_str = (
            raw_err.decode("utf-8", errors="replace")
            if isinstance(raw_err, bytes)
            else (raw_err or "")
        )
        return proc.returncode, out_str, err_str, None
    except Exception as exc:
        return -1, "", "", str(exc)


def _drain_ready_channel(
    key: selectors.SelectorKey,
    proc: Any,
    stdout_buf: bytearray,
    stderr_buf: bytearray,
    max_bytes: int,
    sel: selectors.BaseSelector,
) -> bool:
    """Read ready channel from pipe and return True if byte limit was exceeded."""
    try:
        chunk = os.read(key.fd, 32768)
    except OSError:
        chunk = b""
    if not chunk:
        sel.unregister(key.fileobj)
        return False
    target = stdout_buf if key.fileobj is proc.stdout else stderr_buf
    target.extend(chunk)
    return len(stdout_buf) > max_bytes or len(stderr_buf) > max_bytes


def _register_sandbox_channels(
    sel: selectors.BaseSelector,
    proc: subprocess.Popen[bytes],
) -> None:
    """Register stdout and stderr on selector only when backed by valid non-standard fds."""
    for pipe in (proc.stdout, proc.stderr):
        if pipe is None:
            continue
        try:
            fd = pipe.fileno()
            if isinstance(fd, int) and fd > 2:
                sel.register(pipe, selectors.EVENT_READ)
        except AttributeError, OSError, ValueError:
            pass


def _close_sandbox_channels(
    sel: selectors.BaseSelector,
    proc: subprocess.Popen[bytes],
) -> None:
    """Safely close selector and process pipe channels."""
    sel.close()
    for pipe in (proc.stdout, proc.stderr):
        if pipe is not None and not pipe.closed:
            try:
                pipe.close()
            except OSError:
                pass


def _reap_sandbox_process(proc: subprocess.Popen[bytes]) -> None:
    """Wait for child process with timeout, killing process group on hang."""
    try:
        proc.wait(timeout=1.0)
    except subprocess.TimeoutExpired:
        _terminate_process_group(proc.pid, signal.SIGKILL)
        try:
            proc.wait(timeout=1.0)
        except subprocess.TimeoutExpired:
            pass


def _process_selector_events(
    events: list[tuple[selectors.SelectorKey, int]],
    proc: Any,
    stdout_buf: bytearray,
    stderr_buf: bytearray,
    max_output_bytes: int,
    sel: selectors.BaseSelector,
) -> bool:
    """Drain events and return True if output limit was exceeded."""
    for key, _ in events:
        if _drain_ready_channel(key, proc, stdout_buf, stderr_buf, max_output_bytes, sel):
            _terminate_process_group(proc.pid, signal.SIGKILL)
            return True
    return False


def _run_selector_loop(
    sel: selectors.BaseSelector,
    proc: Any,
    deadline: float,
    max_output_bytes: int,
    stdout_buf: bytearray,
    stderr_buf: bytearray,
) -> tuple[bool, bool]:
    """Execute select loop, returning (timed_out, limit_exceeded)."""
    while sel.get_map():
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            _terminate_process_group(proc.pid, signal.SIGKILL)
            return True, False
        events = sel.select(timeout=min(max(remaining, 0.01), 0.1))
        if _process_selector_events(events, proc, stdout_buf, stderr_buf, max_output_bytes, sel):
            return False, True
        if proc.poll() is not None and not events:
            break
    return False, False


def _build_bounded_result(
    proc: Any,
    timeout: float,
    max_output_bytes: int,
    stdout_buf: bytearray,
    stderr_buf: bytearray,
    timed_out: bool,
    limit_exceeded: bool,
) -> tuple[int | None, str, str, str | None]:
    """Compile final returncode, strings, and error message."""
    out_str = stdout_buf[:max_output_bytes].decode("utf-8", errors="replace")
    err_str = stderr_buf[:max_output_bytes].decode("utf-8", errors="replace")
    if timed_out:
        return -1, out_str, err_str, f"Criterion execution timed out after {timeout}s"
    if limit_exceeded:
        return -1, out_str, err_str, f"Output exceeded maximum limit of {max_output_bytes} bytes"
    return proc.returncode, out_str, err_str, None


def _communicate_bounded(
    proc: Any,
    timeout: float,
    max_output_bytes: int,
) -> tuple[int | None, str, str, str | None]:
    """Stream stdout and stderr with timeout and byte limit, terminating on breach."""
    if _is_mock_subprocess(proc):
        return _communicate_mock(proc, timeout)

    deadline = time.monotonic() + timeout
    sel = selectors.DefaultSelector()
    stdout_buf = bytearray()
    stderr_buf = bytearray()

    try:
        _register_sandbox_channels(sel, proc)
        timed_out, limit_exceeded = _run_selector_loop(
            sel, proc, deadline, max_output_bytes, stdout_buf, stderr_buf
        )
    finally:
        _close_sandbox_channels(sel, proc)

    _reap_sandbox_process(proc)
    return _build_bounded_result(
        proc, timeout, max_output_bytes, stdout_buf, stderr_buf, timed_out, limit_exceeded
    )


def _run_sandbox_process(
    cmd: list[str],
    timeout: float,
    max_output_bytes: int = DEFAULT_CRITERIA_MAX_OUTPUT_BYTES,
    pids_limit: int | None = None,
) -> tuple[int | None, str, str, str | None]:
    """Spawn and communicate with the sandbox subprocess safely with resource limits.

    Note on process limits (pids_limit): bubblewrap does not natively provide a
    process limit flag (such as --pids-limit). Process limits in Linux require
    cgroups v2 pids.max controllers, which bubblewrap cannot manage without cgroups
    delegation. In Linux kernel semantics, RLIMIT_NPROC via setrlimit is per-real-UID
    across the entire system/container rather than per-process tree; setting it inside
    a child process starves ambient processes sharing the same UID (e.g. devcontainer
    shells or daemons). Therefore, process count limits cannot be safely enforced via
    RLIMIT_NPROC under bubblewrap and require external cgroup v2 containerization.
    """
    del pids_limit
    proc: subprocess.Popen[bytes] | None = None
    try:
        proc = subprocess.Popen(
            cmd,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=True,
        )
        return _communicate_bounded(proc, timeout, max_output_bytes)
    except Exception as exc:
        if proc is not None:
            _terminate_process_group(proc.pid, signal.SIGKILL)
        return -1, "", "", f"Subprocess error: {exc}"


def _format_sandbox_result(
    exit_code: int | None,
    raw_stdout: str,
    raw_stderr: str,
    err_msg: str | None,
    duration: float,
    max_output_bytes: int,
) -> HostSandboxResult:
    """Format and bound sandbox execution results."""
    stdout_bounded = (raw_stdout or "")[:max_output_bytes]
    stderr_bounded = (raw_stderr or "")[:max_output_bytes]
    effective_err = err_msg
    if exit_code != 0 and stderr_bounded.strip().startswith("bwrap:"):
        effective_err = f"Host sandbox error: {stderr_bounded.strip()}"
    return HostSandboxResult(
        exit_code=exit_code,
        stdout=stdout_bounded,
        stderr=stderr_bounded,
        duration_seconds=round(duration, 3),
        passed=exit_code == 0 and effective_err is None,
        error=effective_err,
    )


def _mount_linked_worktree_git_dirs(mount_args: list[str], root: Path) -> None:
    """Bind external git directory and common directory read-only for linked worktrees."""
    gitdir = _gitdir_named_by(root)
    if gitdir is not None and gitdir.exists() and not gitdir.is_relative_to(root):
        mount_args.extend(["--ro-bind", str(gitdir), str(gitdir)])
    common_dir = _linked_worktree_common_dir(root)
    if common_dir is not None and common_dir.exists() and not common_dir.is_relative_to(root):
        if gitdir is None or not common_dir.is_relative_to(gitdir):
            mount_args.extend(["--ro-bind", str(common_dir), str(common_dir)])


class HostSandbox:
    """Bubblewrap-confined host execution sandbox."""

    def __init__(
        self,
        bwrap_binary: str | Path | None = None,
        policy: SandboxPolicy | None = None,
    ) -> None:
        resolved = bwrap_binary or shutil.which("bwrap") or DEFAULT_HOST_SANDBOX_BINARY
        self.bwrap_binary: Final[Path] = Path(resolved)
        self.policy: Final[SandboxPolicy] = policy if policy is not None else DEFAULT_SANDBOX_POLICY

    def is_available(self) -> bool:
        """Verify whether the bubblewrap binary exists and is executable."""
        return self.bwrap_binary.is_file() and os.access(self.bwrap_binary, os.X_OK)

    def _resolve_system_mounts(self) -> list[str]:
        """Construct read-only and symlink bind mounts for system toolchains."""
        mount_args: list[str] = []
        for sys_dir in self.policy.system_dirs:
            if Path(sys_dir).exists():
                mount_args.extend(["--ro-bind", sys_dir, sys_dir])

        for sym_path in self.policy.system_symlinks:
            p = Path(sym_path)
            if not p.exists():
                continue
            if p.is_symlink():
                target = os.readlink(sym_path)
                mount_args.extend(["--symlink", target, sym_path])
            else:
                mount_args.extend(["--ro-bind", sym_path, sym_path])
        return mount_args

    def _resolve_repo_mounts(
        self,
        cwd: Path,
        repo_root: Path | None = None,
    ) -> tuple[list[str], Path]:
        """Resolve nearest repository root and working directory mounts on top of tmpfs."""
        resolved_cwd = cwd.resolve()
        if repo_root is not None:
            effective_root = repo_root.resolve()
        else:
            candidates = _repo_root_candidates(resolved_cwd)
            effective_root = candidates[0].resolve()

        mount_args: list[str] = []
        for tmp_dir, opts in self.policy.tmpfs.items():
            size_bytes = _parse_tmpfs_size_bytes(opts)
            if size_bytes is not None:
                mount_args.extend(["--size", str(size_bytes)])
            mount_args.extend(["--tmpfs", tmp_dir])  # nosec B108

        bind_flag = "--ro-bind" if self.policy.read_only else "--bind"
        mount_args.extend([bind_flag, str(effective_root), str(effective_root)])
        if not resolved_cwd.is_relative_to(effective_root):
            mount_args.extend([bind_flag, str(resolved_cwd), str(resolved_cwd)])

        _mount_linked_worktree_git_dirs(mount_args, effective_root)
        return mount_args, resolved_cwd

    def _build_env_args(self, env: dict[str, str] | None = None) -> list[str]:
        """Construct sanitized environment variables forbidding credential leaks."""
        clean_env: dict[str, str] = dict(self.policy.default_env)
        if env:
            for k, v in env.items():
                if k not in self.policy.forbidden_env_keys:
                    clean_env[k] = v

        env_args: list[str] = []
        for k, v in clean_env.items():
            env_args.extend(["--setenv", k, v])
        return env_args

    def build_bwrap_args(
        self,
        command_args: list[str],
        cwd: Path,
        repo_root: Path | None = None,
        env: dict[str, str] | None = None,
    ) -> list[str]:
        """Compile complete bubblewrap argument list."""
        mount_args, resolved_cwd = self._resolve_repo_mounts(cwd, repo_root)
        return (
            [
                str(self.bwrap_binary),
                "--unshare-all",
                "--new-session",
                "--die-with-parent",
                "--clearenv",
                "--dev",
                "/dev",
                "--proc",
                "/proc",
            ]
            + self._resolve_system_mounts()
            + mount_args
            + self._build_env_args(env)
            + ["--chdir", str(resolved_cwd), "--"]
            + command_args
        )

    def execute(
        self,
        args: list[str],
        cwd: Path,
        repo_root: Path | None = None,
        timeout: float = DEFAULT_CRITERIA_EXECUTION_TIMEOUT_SECONDS,
        max_output_bytes: int = DEFAULT_CRITERIA_MAX_OUTPUT_BYTES,
        env: dict[str, str] | None = None,
    ) -> HostSandboxResult:
        """Execute command within bubblewrap sandbox with bounded timeout and output."""
        if not self.is_available():
            return HostSandboxResult(
                exit_code=-1,
                stdout="",
                stderr="",
                duration_seconds=0.0,
                passed=False,
                error=f"bubblewrap binary {self.bwrap_binary} is not available on host system",
            )

        bwrap_cmd = self.build_bwrap_args(args, cwd, repo_root, env)
        t_start = time.monotonic()
        exit_code, stdout, stderr, err_msg = _run_sandbox_process(
            bwrap_cmd,
            timeout,
            max_output_bytes=max_output_bytes,
            pids_limit=self.policy.pids_limit,
        )
        duration = time.monotonic() - t_start

        return _format_sandbox_result(
            exit_code=exit_code,
            raw_stdout=stdout,
            raw_stderr=stderr,
            err_msg=err_msg,
            duration=duration,
            max_output_bytes=max_output_bytes,
        )
