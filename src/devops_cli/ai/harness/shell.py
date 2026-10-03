"""Shell capability for executing sandboxed shell commands."""

from __future__ import annotations

import fnmatch
import logging
import os
import shlex
import signal
import subprocess
import threading
import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import IO, Any

from pydantic import Field

from devops_cli.ai.agents.pydantic_agent import AgentTool, BaseCapability, Tool
from devops_cli.ai.harness.constants import (
    DEFAULT_DENIED_COMMANDS,
    INTERACTIVE_COMMANDS,
    LLM_API_KEY_ENV_PATTERNS,
)
from devops_cli.config.defaults import (
    DEFAULT_SHELL_BG_OUTPUT_LINES,
    DEFAULT_SHELL_DRAIN_TIMEOUT_SECONDS,
    DEFAULT_SHELL_STOP_GRACE_SECONDS,
    DEFAULT_SHELL_STOP_POLL_SECONDS,
)
from devops_cli.exceptions.ai import HarnessValidationError

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class _OutputRing:
    """A bounded line buffer handed off between a pipe reader thread and the tool caller.

    The lock is not optional: a ``deque`` raises if it is mutated while being iterated, and
    the reader thread appends continuously while the agent may call ``check_command`` at any
    moment. ``seen`` outlives the evicted lines so the caller can be told how much scrollback
    the cap discarded, rather than handed a truncated view that reads as the whole of it.
    """

    lines: deque[str]
    lock: threading.Lock = field(default_factory=threading.Lock)
    seen: int = 0

    def append(self, line: str) -> None:
        with self.lock:
            self.lines.append(line)
            self.seen += 1

    def render(self) -> str:
        with self.lock:
            dropped = self.seen - len(self.lines)
            text = "".join(self.lines)
        return f"[... {dropped} earlier line(s) dropped ...]\n{text}" if dropped else text


@dataclass(slots=True)
class _BackgroundCommand:
    """A backgrounded process paired with the ring buffers its reader threads drain into."""

    process: subprocess.Popen[str]
    stdout: _OutputRing
    stderr: _OutputRing
    readers: tuple[threading.Thread, ...] = ()

    def settle(self, timeout: float = DEFAULT_SHELL_DRAIN_TIMEOUT_SECONDS) -> None:
        """Wait for the reader threads once the process itself has exited.

        `poll()` reports an exit status as soon as the child is reaped, which is before the
        readers have necessarily banked what was still sitting in the pipes. Rendering at
        that moment produced a report saying FINISHED beside truncated output, and the
        missing lines never arrived because nothing read the rings again.
        """
        for reader in self.readers:
            reader.join(timeout=timeout)


def _drain_pipe(stream: IO[str] | None, sink: _OutputRing) -> None:
    """Pump one pipe into its ring buffer until EOF.

    A pipe nobody reads fills its kernel buffer (64 KiB on Linux) and then blocks the child
    on its next write forever, so the process neither finishes nor releases its concurrency
    slot. Errors are swallowed because this runs on a detached thread where a traceback would
    reach the operator's terminal instead of the caller, and a closed or broken pipe simply
    means the command is over.
    """
    if stream is None:
        return
    try:
        with stream:
            for line in stream:
                sink.append(line)
    except OSError, ValueError:
        logger.debug("Background command pipe closed while draining", exc_info=True)


def _spawn_reader(stream: IO[str] | None, sink: _OutputRing, name: str) -> threading.Thread:
    """Start the daemon thread that drains one pipe, so interpreter exit is never held up."""
    thread = threading.Thread(target=_drain_pipe, args=(stream, sink), name=name, daemon=True)
    thread.start()
    return thread


def _signal_process_group(pgid: int, sig: int) -> bool:
    """Send ``sig`` to the group, returning False once no member is left to receive it.

    Signal 0 only probes whether a member still exists. A group this process may not signal is
    reported and treated as out of reach, since signalling it again cannot succeed either.
    """
    try:
        os.killpg(pgid, sig)
    except ProcessLookupError:
        return False
    except PermissionError:
        name = signal.Signals(sig).name if sig else "signal 0"
        logger.warning("Not permitted to signal process group %s with %s", pgid, name)
        return False
    return True


def _check_shell_syntax(command: str, denied_operators: list[str]) -> tuple[bool, str, list[str]]:
    """Validate shell operators, shlex parsing, and path traversal."""
    if not command.strip():
        return False, "Error: empty command", []

    for op in denied_operators:
        if op in command:
            return False, f"Shell operator '{op}' is blocked by security policy.", []

    try:
        parts = shlex.split(command)
    except Exception as exc:
        return False, f"Command parsing error: {exc}", []

    if not parts:
        return False, "Error: empty command", []

    if any(".." in part for part in parts):
        return False, "Path traversal in command arguments is blocked by security policy.", []

    return True, "", parts


def _check_command_permissions(
    cmd_name: str,
    full_cmd: str,
    allowed: list[str],
    denied: list[str],
    allow_interactive: bool,
) -> tuple[bool, str]:
    """Validate command against interactive policy, allowlist, and denylist."""
    if not allow_interactive and cmd_name in INTERACTIVE_COMMANDS:
        return False, f"Interactive command '{cmd_name}' is blocked in non-interactive agent shell."

    if allowed:
        if cmd_name not in allowed and full_cmd not in allowed:
            return False, f"Command '{cmd_name}' is blocked by security allowlist."
        return True, ""

    if denied and (
        cmd_name in denied
        or full_cmd in denied
        or any(cmd_name.startswith(f"{d}.") for d in denied)
    ):
        return False, f"Command '{cmd_name}' is blocked by security denylist."

    return True, ""


class Shell(BaseCapability):
    """Capability for executing shell commands with allowlists, denylists, background processes, and credential stripping."""

    id: str = "shell"
    cwd: Path = Field(default_factory=lambda: Path("."))
    allowed_commands: list[str] = Field(default_factory=list)
    denied_commands: list[str] = Field(default_factory=lambda: list(DEFAULT_DENIED_COMMANDS))
    denied_operators: list[str] = Field(default_factory=list)
    allow_interactive: bool = False
    env: dict[str, str] | None = None
    denied_env_patterns: list[str] = Field(default_factory=lambda: list(LLM_API_KEY_ENV_PATTERNS))
    timeout: float = 60.0
    max_output_chars: int = 20000
    max_bg_processes: int = 10
    max_bg_output_lines: int = DEFAULT_SHELL_BG_OUTPUT_LINES
    stop_grace_seconds: float = DEFAULT_SHELL_STOP_GRACE_SECONDS

    def __init__(
        self,
        cwd: Path | str = ".",
        *,
        allowed_commands: list[str] | None = None,
        denied_commands: list[str] | None = None,
        denied_operators: list[str] | None = None,
        allow_interactive: bool = False,
        env: dict[str, str] | None = None,
        denied_env_patterns: list[str] | None = None,
        timeout: float = 60.0,
        max_output_chars: int = 20000,
        max_bg_processes: int = 10,
        max_bg_output_lines: int = DEFAULT_SHELL_BG_OUTPUT_LINES,
        stop_grace_seconds: float = DEFAULT_SHELL_STOP_GRACE_SECONDS,
    ) -> None:
        p = Path(cwd)
        if allowed_commands is not None and denied_commands is not None:
            raise HarnessValidationError(
                "allowed_commands and denied_commands are mutually exclusive; specify one or the other."
            )
        super().__init__(
            cwd=p,
            allowed_commands=allowed_commands or [],
            denied_commands=list(DEFAULT_DENIED_COMMANDS)
            if denied_commands is None and not allowed_commands
            else (denied_commands or []),
            denied_operators=denied_operators or [],
            allow_interactive=allow_interactive,
            env=env,
            denied_env_patterns=list(LLM_API_KEY_ENV_PATTERNS)
            if denied_env_patterns is None
            else denied_env_patterns,
            timeout=timeout,
            max_output_chars=max_output_chars,
            max_bg_processes=max_bg_processes,
            max_bg_output_lines=max_bg_output_lines,
            stop_grace_seconds=stop_grace_seconds,
        )

    def _sanitize_env(self) -> dict[str, str]:

        base_env = dict(self.env) if self.env is not None else dict(os.environ)
        clean_env: dict[str, str] = {}
        for k, v in base_env.items():
            if not any(fnmatch.fnmatch(k.upper(), pat.upper()) for pat in self.denied_env_patterns):
                clean_env[k] = v
        return clean_env

    def _validate_command(self, command: str) -> tuple[bool, str, list[str]]:
        ok, err, parts = _check_shell_syntax(command, self.denied_operators)
        if not ok:
            return False, err, []

        cmd_name = Path(parts[0]).name
        ok, err = _check_command_permissions(
            cmd_name, parts[0], self.allowed_commands, self.denied_commands, self.allow_interactive
        )
        if not ok:
            return False, err, []

        return True, "", parts

    def _label_streams(self, stdout: str, stderr: str) -> list[str]:
        parts: list[str] = []
        if stdout.strip():
            parts.append(f"[stdout]\n{stdout.strip()}")
        if stderr.strip():
            parts.append(f"[stderr]\n{stderr.strip()}")
        return parts

    def _cap_output(self, text: str) -> str:
        if len(text) <= self.max_output_chars:
            return text
        return (
            f"[... output truncated, showing last {self.max_output_chars} characters ...]\n"
            + text[-self.max_output_chars :]
        )

    def _format_output(self, stdout: str, stderr: str, returncode: int) -> str:
        parts = self._label_streams(stdout, stderr)
        if returncode != 0:
            parts.append(f"[exit code: {returncode}]")
        return self._cap_output(
            "\n".join(parts) or f"[Command exited with return code {returncode}]"
        )

    def _new_ring(self) -> _OutputRing:
        return _OutputRing(lines=deque(maxlen=self.max_bg_output_lines))

    def _run_sync(self, parts: list[str], env: dict[str, str], exec_timeout: float) -> str:
        proc = subprocess.run(
            parts,
            cwd=str(self.cwd.resolve()),
            capture_output=True,
            text=True,
            timeout=exec_timeout,
            env=env,
            check=False,
        )
        return self._format_output(proc.stdout or "", proc.stderr or "", proc.returncode)

    def _launch_background(
        self, parts: list[str], env: dict[str, str], cmd_id: str
    ) -> _BackgroundCommand:
        """Spawn the process and immediately attach a reader thread to each of its pipes.

        The readers are attached before the caller ever sees the tracking ID so there is no
        window in which the child can fill a pipe that nobody is emptying.
        """
        proc = subprocess.Popen(
            parts,
            cwd=str(self.cwd.resolve()),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            # A subprocess writes bytes, not text. Under strict decoding one undecodable
            # byte raises `UnicodeDecodeError` inside the reader thread -- and that is a
            # `ValueError`, so the handler below closed the pipe and the child died of
            # SIGPIPE on its next write. A command is not wrong to emit a stray byte, so
            # the byte is replaced rather than the command killed.
            errors="replace",
            env=env,
            start_new_session=True,
        )
        record = _BackgroundCommand(process=proc, stdout=self._new_ring(), stderr=self._new_ring())
        record.readers = (
            _spawn_reader(proc.stdout, record.stdout, f"{cmd_id}-stdout"),
            _spawn_reader(proc.stderr, record.stderr, f"{cmd_id}-stderr"),
        )
        return record

    def _render_background_report(self, command_id: str, record: _BackgroundCommand) -> str:
        """Compose the status line together with whatever the reader threads have banked."""
        ret = record.process.poll()
        if ret is not None:
            record.settle()
        status = "RUNNING" if ret is None else f"FINISHED (exit code: {ret})"
        body = self._cap_output(
            "\n".join(self._label_streams(record.stdout.render(), record.stderr.render()))
        )
        header = f"Command {command_id} status: {status}"
        return f"{header}\n{body}" if body else header

    def _terminate_process_group(self, proc: subprocess.Popen[str]) -> None:
        """Signal the whole POSIX group, escalating to SIGKILL for members that outlast SIGTERM.

        Killing only ``proc`` would leave any subshell it spawned running as an orphan
        reparented to PID 1, which is why the process was given its own session to begin with.
        That makes its pid the group id for as long as any member lives, so the group is
        signalled by it: looking the group up through ``getpgid`` failed once the leader had
        exited and been reaped, and its members kept running. The group is probed until no
        member is left, reaping the leader each time so its zombie does not keep the group in
        sight, and whatever is still there when the grace period ends gets SIGKILL.
        """
        pgid = proc.pid
        if not isinstance(pgid, int) or pgid <= 1 or pgid == os.getpgrp():
            return
        if not _signal_process_group(pgid, signal.SIGTERM):
            proc.poll()
            return
        deadline = time.monotonic() + self.stop_grace_seconds
        while time.monotonic() < deadline:
            proc.poll()
            if not _signal_process_group(pgid, 0):
                return
            time.sleep(DEFAULT_SHELL_STOP_POLL_SECONDS)
        _signal_process_group(pgid, signal.SIGKILL)
        try:
            proc.wait(timeout=self.stop_grace_seconds)
        except subprocess.TimeoutExpired:
            logger.warning(
                "Process group %s leader did not exit %ss after SIGKILL",
                pgid,
                self.stop_grace_seconds,
            )

    def get_tools(self) -> list[AgentTool | Callable[..., Any]]:  # noqa: C901
        bg_commands: dict[str, _BackgroundCommand] = {}

        def run_command(command: str, timeout_seconds: float | None = None) -> str:
            """Run a command synchronously and return labelled stdout/stderr plus exit code."""
            ok, err, parts = self._validate_command(command)
            if not ok:
                return err

            env = self._sanitize_env()
            exec_timeout = timeout_seconds if timeout_seconds is not None else self.timeout
            try:
                return self._run_sync(parts, env, exec_timeout)
            except subprocess.TimeoutExpired:
                return f"Command '{command}' timed out after {exec_timeout}s"
            except Exception as exc:
                return f"Execution error: {exc}"

        def start_command(command: str) -> str:
            """Launch a long-running command in the background and return a tracking ID."""
            active_count = sum(1 for c in bg_commands.values() if c.process.poll() is None)
            if active_count >= self.max_bg_processes:
                return f"Maximum limit of concurrent background processes ({self.max_bg_processes}) reached. Blocked."

            ok, err, parts = self._validate_command(command)
            if not ok:
                return err

            import uuid

            cmd_id = f"cmd_{uuid.uuid4().hex[:8]}"
            env = self._sanitize_env()
            try:
                bg_commands[cmd_id] = self._launch_background(parts, env, cmd_id)
                return f"Background command started with ID: {cmd_id}"
            except Exception as exc:
                return f"Failed to start background command: {exc}"

        def check_command(command_id: str) -> str:
            """Report status and accumulated output for a background command."""
            record = bg_commands.get(command_id)
            if record is None:
                return f"Error: background command ID '{command_id}' not found."
            return self._render_background_report(command_id, record)

        def stop_command(command_id: str) -> str:
            """Terminate a background command process group."""
            record = bg_commands.pop(command_id, None)
            if record is None:
                return f"Error: background command ID '{command_id}' not found."

            self._terminate_process_group(record.process)
            return f"Background command {command_id} terminated."

        return [
            Tool.from_function(
                run_command,
                name="run_command",
                description="Run a command synchronously and return labelled stdout/stderr plus exit code.",
            ),
            Tool.from_function(
                start_command,
                name="start_command",
                description="Launch a long-running command in the background; returns command_id.",
            ),
            Tool.from_function(
                check_command,
                name="check_command",
                description="Report status and output for a background command_id.",
            ),
            Tool.from_function(
                stop_command,
                name="stop_command",
                description="Terminate a background command_id process group.",
            ),
        ]
