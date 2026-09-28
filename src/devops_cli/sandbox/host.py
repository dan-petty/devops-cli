"""Host sandbox confinement using bubblewrap for criteria and untrusted execution."""

from __future__ import annotations

import os
import shutil
import signal
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from devops_cli.config import (
    DEFAULT_CRITERIA_EXECUTION_TIMEOUT_SECONDS,
    DEFAULT_CRITERIA_MAX_OUTPUT_BYTES,
    DEFAULT_HOST_SANDBOX_BINARY,
)
from devops_cli.core.repo import find_worktree_root
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
    """Safely terminate a POSIX process group hierarchy."""
    try:
        pgid = os.getpgid(pid)
        os.killpg(pgid, sig)
    except OSError:
        pass


def _handle_timeout(
    proc: subprocess.Popen[str] | None,
    timeout: float,
) -> tuple[int | None, str, str, str | None]:
    """Handle subprocess timeout by killing the process group."""
    if proc is not None:
        _terminate_process_group(proc.pid, signal.SIGTERM)
        try:
            stdout, stderr = proc.communicate(timeout=2.0)
        except subprocess.TimeoutExpired:
            _terminate_process_group(proc.pid, signal.SIGKILL)
            stdout, stderr = proc.communicate()
    else:
        stdout, stderr = "", ""
    return -1, stdout, stderr, f"Criterion execution timed out after {timeout}s"


def _run_sandbox_process(
    cmd: list[str],
    timeout: float,
) -> tuple[int | None, str, str, str | None]:
    """Spawn and communicate with the sandbox subprocess safely."""
    proc: subprocess.Popen[str] | None = None
    try:
        proc = subprocess.Popen(
            cmd,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            start_new_session=True,
        )
        stdout, stderr = proc.communicate(timeout=timeout)
        return proc.returncode, stdout, stderr, None
    except subprocess.TimeoutExpired:
        return _handle_timeout(proc, timeout)
    except Exception as exc:
        if proc is not None:
            _terminate_process_group(proc.pid)
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
        """Resolve repository root and working directory mounts on top of tmpfs."""
        if repo_root is not None:
            effective_root = repo_root.resolve()
        else:
            wt_root = find_worktree_root(cwd)
            effective_root = wt_root.resolve() if wt_root else cwd.resolve()

        resolved_cwd = cwd.resolve()
        mount_args: list[str] = []
        for tmp_dir in self.policy.tmpfs:
            mount_args.extend(["--tmpfs", tmp_dir])  # nosec B108

        bind_flag = "--ro-bind" if self.policy.read_only else "--bind"
        mount_args.extend([bind_flag, str(effective_root), str(effective_root)])
        if not resolved_cwd.is_relative_to(effective_root):
            mount_args.extend([bind_flag, str(resolved_cwd), str(resolved_cwd)])

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
        exit_code, stdout, stderr, err_msg = _run_sandbox_process(bwrap_cmd, timeout)
        duration = time.monotonic() - t_start

        return _format_sandbox_result(
            exit_code=exit_code,
            raw_stdout=stdout,
            raw_stderr=stderr,
            err_msg=err_msg,
            duration=duration,
            max_output_bytes=max_output_bytes,
        )
