"""Shell capability for executing sandboxed shell commands."""

from __future__ import annotations

import fnmatch
import logging
import os
import subprocess
import threading
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
        )

    def _sanitize_env(self) -> dict[str, str]:

        base_env = dict(self.env) if self.env is not None else dict(os.environ)
        clean_env: dict[str, str] = {}
        for k, v in base_env.items():
            if not any(fnmatch.fnmatch(k.upper(), pat.upper()) for pat in self.denied_env_patterns):
                clean_env[k] = v
        return clean_env

    def _validate_command(self, command: str) -> tuple[bool, str, list[str]]:
        import shlex

        if not command.strip():
            return False, "Error: empty command", []

        for op in self.denied_operators:
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

        cmd_name = Path(parts[0]).name

        if not self.allow_interactive and cmd_name in INTERACTIVE_COMMANDS:
            return (
                False,
                f"Interactive command '{cmd_name}' is blocked in non-interactive agent shell.",
                [],
            )

        if self.allowed_commands:
            if cmd_name not in self.allowed_commands and parts[0] not in self.allowed_commands:
                return False, f"Command '{cmd_name}' is blocked by security allowlist.", []
        elif self.denied_commands:
            if (
                cmd_name in self.denied_commands
                or parts[0] in self.denied_commands
                or any(cmd_name.startswith(f"{d}.") for d in self.denied_commands)
            ):
                return False, f"Command '{cmd_name}' is blocked by security denylist.", []

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
        """Signal the whole POSIX group, escalating to SIGKILL if the group ignores SIGTERM.

        Killing only ``proc`` would leave any subshell it spawned running as an orphan
        reparented to PID 1, which is why the process was given its own session to begin with.
        """
        import signal

        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
            proc.wait(timeout=3.0)
        except Exception:
            try:
                os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
            except Exception:
                pass

    def get_tools(self) -> list[AgentTool | Callable[..., Any]]:
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
