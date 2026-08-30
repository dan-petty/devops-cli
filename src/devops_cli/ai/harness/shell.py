"""Shell capability for executing sandboxed shell commands."""

from __future__ import annotations

import fnmatch
import logging
import os
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any

from pydantic import Field

from devops_cli.ai.agents.pydantic_agent import AgentTool, BaseCapability, Tool
from devops_cli.ai.harness.constants import (
    DEFAULT_DENIED_COMMANDS,
    INTERACTIVE_COMMANDS,
    LLM_API_KEY_ENV_PATTERNS,
)

logger = logging.getLogger(__name__)


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
    ) -> None:
        p = Path(cwd)
        if allowed_commands is not None and denied_commands is not None:
            raise ValueError(
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
            if cmd_name in self.denied_commands or parts[0] in self.denied_commands:
                return False, f"Command '{cmd_name}' is blocked by security denylist.", []

        return True, "", parts

    def _format_output(self, stdout: str, stderr: str, returncode: int) -> str:
        parts: list[str] = []
        if stdout.strip():
            parts.append(f"[stdout]\n{stdout.strip()}")
        if stderr.strip():
            parts.append(f"[stderr]\n{stderr.strip()}")
        if returncode != 0:
            parts.append(f"[exit code: {returncode}]")
        full_text = "\n".join(parts) or f"[Command exited with return code {returncode}]"
        if len(full_text) > self.max_output_chars:
            full_text = (
                f"[... output truncated, showing last {self.max_output_chars} characters ...]\n"
                + full_text[-self.max_output_chars :]
            )
        return full_text

    def get_tools(self) -> list[AgentTool | Callable[..., Any]]:
        bg_processes: dict[str, subprocess.Popen[str]] = {}
        bg_outputs: dict[str, list[str]] = {}

        def run_command(command: str, timeout_seconds: float | None = None) -> str:
            """Run a command synchronously and return labelled stdout/stderr plus exit code."""
            ok, err, parts = self._validate_command(command)
            if not ok:
                return err

            env = self._sanitize_env()
            exec_timeout = timeout_seconds if timeout_seconds is not None else self.timeout
            try:
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
            except subprocess.TimeoutExpired:
                return f"Command '{command}' timed out after {exec_timeout}s"
            except Exception as exc:
                return f"Execution error: {exc}"

        def start_command(command: str) -> str:
            """Launch a long-running command in the background and return a tracking ID."""
            ok, err, parts = self._validate_command(command)
            if not ok:
                return err

            import uuid

            cmd_id = f"cmd_{uuid.uuid4().hex[:8]}"
            env = self._sanitize_env()
            try:
                proc = subprocess.Popen(
                    parts,
                    cwd=str(self.cwd.resolve()),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    env=env,
                    start_new_session=True,
                )
                bg_processes[cmd_id] = proc
                bg_outputs[cmd_id] = []
                return f"Background command started with ID: {cmd_id}"
            except Exception as exc:
                return f"Failed to start background command: {exc}"

        def check_command(command_id: str) -> str:
            """Report status and accumulated output for a background command."""
            proc = bg_processes.get(command_id)
            if proc is None:
                return f"Error: background command ID '{command_id}' not found."

            ret = proc.poll()
            status = "RUNNING" if ret is None else f"FINISHED (exit code: {ret})"
            return f"Command {command_id} status: {status}"

        def stop_command(command_id: str) -> str:
            """Terminate a background command process group."""
            proc = bg_processes.pop(command_id, None)
            if proc is None:
                return f"Error: background command ID '{command_id}' not found."

            import signal

            try:
                os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
                proc.wait(timeout=3.0)
            except Exception:
                try:
                    os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
                except Exception:
                    pass

            return f"Background command {command_id} terminated."

        return [
            Tool.from_function(
                run_command,
                name="run_command",
                description="Run a command synchronously and return labelled stdout/stderr plus exit code.",
            ),
            Tool.from_function(
                run_command,
                name="run_shell",
                description="Run a shell command synchronously (alias for run_command).",
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
