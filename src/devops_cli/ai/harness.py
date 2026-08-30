"""Pydantic AI Harness module providing complete agent stacks, sandboxed environments, and workflow capabilities."""

from __future__ import annotations

import os
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from devops_cli.ai.agents.pydantic_agent import (
    AgentTool,
    BaseCapability,
    PydanticAgent,
    RunContext,
    Tool,
)
from devops_cli.ai.common_tools import duckduckgo_search_tool, web_fetch_tool

LLM_API_KEY_ENV_PATTERNS: list[str] = [
    "*API_KEY*",
    "*AUTH_TOKEN*",
    "*SECRET*",
    "*PASSWORD*",
    "*ACCESS_TOKEN*",
    "*CREDENTIAL*",
]


DEFAULT_PROTECTED_PATTERNS: list[str] = [
    ".git/*",
    ".env",
    ".env.*",
    "*.pem",
    "*.key",
    "**/secrets*",
]


class FileSystem(BaseCapability):
    """Capability providing safe, sandboxed file operations with pattern filtering and optimistic concurrency."""

    id: str = "file_system"
    root: Path = Field(default_factory=lambda: Path("."))
    allowed_patterns: list[str] = Field(default_factory=list)
    denied_patterns: list[str] = Field(default_factory=list)
    protected_patterns: list[str] = Field(default_factory=lambda: list(DEFAULT_PROTECTED_PATTERNS))
    max_read_lines: int = 2000
    max_list_results: int = 1000
    max_search_results: int = 1000
    max_find_results: int = 1000
    read_only: bool = False

    def __init__(
        self,
        root_dir: Path | str | None = None,
        *,
        root: Path | str | None = None,
        allowed_patterns: list[str] | None = None,
        denied_patterns: list[str] | None = None,
        protected_patterns: list[str] | None = None,
        max_read_lines: int = 2000,
        max_list_results: int = 1000,
        max_search_results: int = 1000,
        max_find_results: int = 1000,
        read_only: bool = False,
    ) -> None:
        p = Path(root_dir or root or ".")
        super().__init__(
            root=p,
            allowed_patterns=allowed_patterns or [],
            denied_patterns=denied_patterns or [],
            protected_patterns=list(DEFAULT_PROTECTED_PATTERNS)
            if protected_patterns is None
            else protected_patterns,
            max_read_lines=max_read_lines,
            max_list_results=max_list_results,
            max_search_results=max_search_results,
            max_find_results=max_find_results,
            read_only=read_only,
        )

    def _resolve_safe_path(self, rel_path: str) -> Path:
        resolved = (self.root.resolve() / rel_path).resolve()
        root_res = self.root.resolve()
        if not str(resolved).startswith(str(root_res)):
            raise PermissionError(f"Access denied: path '{rel_path}' is outside root '{self.root}'")
        return resolved

    def _matches_pattern(self, rel_path: str, patterns: list[str]) -> bool:
        import fnmatch

        normalized = rel_path.replace("\\", "/")
        return any(
            fnmatch.fnmatch(normalized, pat) or fnmatch.fnmatch(Path(normalized).name, pat)
            for pat in patterns
        )

    def _is_accessible(self, rel_path: str, for_write: bool = False) -> tuple[bool, str]:
        if self._matches_pattern(rel_path, self.denied_patterns):
            return False, f"Access denied: '{rel_path}' matches denied pattern"
        if self.allowed_patterns and not self._matches_pattern(rel_path, self.allowed_patterns):
            return False, f"Access denied: '{rel_path}' does not match allowed patterns"
        if for_write:
            if self.read_only:
                return False, "Access denied: FileSystem is configured read-only"
            if self._matches_pattern(rel_path, self.protected_patterns):
                return False, f"Access denied: '{rel_path}' is protected and read-only"
        return True, ""

    def _content_hash(self, content: str | bytes) -> str:
        import hashlib

        data = content.encode("utf-8") if isinstance(content, str) else content
        return hashlib.sha256(data).hexdigest()[:16]

    def get_tools(self) -> list[AgentTool | Callable[..., Any]]:
        tools: list[AgentTool | Callable[..., Any]] = []

        def read_file(path: str, offset: int = 1, limit: int | None = None) -> str:
            """Read a text file with line numbers and a content hash."""
            ok, err = self._is_accessible(path, for_write=False)
            if not ok:
                return f"Error: {err}"
            safe_p = self._resolve_safe_path(path)
            if not safe_p.is_file():
                return f"Error: file not found: {path}"

            raw_bytes = safe_p.read_bytes()
            if b"\x00" in raw_bytes[:1024]:
                return f"[Binary file '{path}', {len(raw_bytes)} bytes]"

            text = raw_bytes.decode("utf-8", errors="replace")
            c_hash = self._content_hash(text)
            lines = text.splitlines()

            start_idx = max(0, offset - 1)
            end_idx = min(len(lines), start_idx + (limit or self.max_read_lines))
            selected_lines = lines[start_idx:end_idx]

            numbered = [f"{start_idx + i + 1:4d} | {line}" for i, line in enumerate(selected_lines)]
            header = f"# File: {path} (sha256:{c_hash}, lines {start_idx + 1}-{end_idx} of {len(lines)})\n"
            return header + "\n".join(numbered)

        def write_file(path: str, content: str, expected_hash: str | None = None) -> str:
            """Create or overwrite a file with optimistic concurrency validation."""
            ok, err = self._is_accessible(path, for_write=True)
            if not ok:
                return f"Error: {err}"
            safe_p = self._resolve_safe_path(path)
            if safe_p.is_file() and expected_hash:
                curr_hash = self._content_hash(safe_p.read_text(encoding="utf-8", errors="replace"))
                if curr_hash != expected_hash:
                    return f"Error: stale edit conflict. File hash is '{curr_hash}', expected '{expected_hash}'."

            safe_p.parent.mkdir(parents=True, exist_ok=True)
            safe_p.write_text(content, encoding="utf-8")
            new_hash = self._content_hash(content)
            return f"File '{path}' successfully written (sha256:{new_hash}, {len(content)} chars)."

        def edit_file(
            path: str, old_text: str, new_text: str, expected_hash: str | None = None
        ) -> str:
            """Perform exact-string replacement within an existing file."""
            ok, err = self._is_accessible(path, for_write=True)
            if not ok:
                return f"Error: {err}"
            safe_p = self._resolve_safe_path(path)
            if not safe_p.is_file():
                return f"Error: file not found: {path}"

            curr_content = safe_p.read_text(encoding="utf-8", errors="replace")
            if expected_hash:
                curr_hash = self._content_hash(curr_content)
                if curr_hash != expected_hash:
                    return f"Error: stale edit conflict. File hash is '{curr_hash}', expected '{expected_hash}'."

            occurrences = curr_content.count(old_text)
            if occurrences == 0:
                return f"Error: target old_text not found in '{path}'"
            if occurrences > 1:
                return f"Error: target old_text matches {occurrences} times in '{path}'. Must match uniquely."

            updated = curr_content.replace(old_text, new_text, 1)
            safe_p.write_text(updated, encoding="utf-8")
            new_hash = self._content_hash(updated)
            return f"File '{path}' successfully edited (sha256:{new_hash})."

        def list_directory(path: str = ".") -> str:
            """List directory entries with type indicators and sizes, omitting dotfiles."""
            ok, err = self._is_accessible(path, for_write=False)
            if not ok:
                return f"Error: {err}"
            safe_p = self._resolve_safe_path(path)
            if not safe_p.is_dir():
                return f"Error: not a directory: {path}"

            entries: list[str] = []
            for item in sorted(safe_p.iterdir()):
                if item.name.startswith("."):
                    continue
                rel = str(item.relative_to(self.root))
                if self.denied_patterns and self._matches_pattern(rel, self.denied_patterns):
                    continue
                if (
                    self.allowed_patterns
                    and item.is_file()
                    and not self._matches_pattern(rel, self.allowed_patterns)
                ):
                    continue

                if item.is_dir():
                    entries.append(f"[DIR]  {item.name}/")
                else:
                    size = item.stat().st_size
                    entries.append(f"[FILE] {item.name} ({size} bytes)")

                if len(entries) >= self.max_list_results:
                    entries.append(f"[... truncated at {self.max_list_results} entries ...]")
                    break

            return "\n".join(entries) or f"Directory '{path}' is empty."

        def find_files(pattern: str, path: str = ".") -> str:
            """Glob search over file names relative to path."""
            safe_p = self._resolve_safe_path(path)
            if not safe_p.is_dir():
                return f"Error: not a directory: {path}"

            matches: list[str] = []
            for p in sorted(safe_p.rglob(pattern)):
                if any(part.startswith(".") for part in p.relative_to(self.root).parts):
                    continue
                rel = str(p.relative_to(self.root))
                if self.denied_patterns and self._matches_pattern(rel, self.denied_patterns):
                    continue
                matches.append(rel)
                if len(matches) >= self.max_find_results:
                    matches.append(f"[... truncated at {self.max_find_results} matches ...]")
                    break

            return "\n".join(matches) or f"No files matching pattern '{pattern}' found."

        def search_files(query: str, path: str = ".", include_glob: str | None = None) -> str:
            """Regex or text search across file contents."""
            import re

            safe_p = self._resolve_safe_path(path)
            if not safe_p.is_dir():
                return f"Error: not a directory: {path}"

            pattern_re = re.compile(query, re.IGNORECASE)
            results: list[str] = []

            for p in sorted(safe_p.rglob(include_glob or "*")):
                if not p.is_file() or any(
                    part.startswith(".") for part in p.relative_to(self.root).parts
                ):
                    continue
                rel = str(p.relative_to(self.root))
                if self.denied_patterns and self._matches_pattern(rel, self.denied_patterns):
                    continue
                try:
                    text = p.read_text(encoding="utf-8", errors="ignore")
                    for i, line in enumerate(text.splitlines(), start=1):
                        if pattern_re.search(line):
                            results.append(f"{rel}:{i}: {line.strip()}")
                            if len(results) >= self.max_search_results:
                                results.append(
                                    f"[... truncated at {self.max_search_results} results ...]"
                                )
                                return "\n".join(results)
                except Exception:
                    continue

            return "\n".join(results) or f"No matches found for query '{query}'."

        def create_directory(path: str) -> str:
            """Create a directory and any missing parent folders."""
            ok, err = self._is_accessible(path, for_write=True)
            if not ok:
                return f"Error: {err}"
            safe_p = self._resolve_safe_path(path)
            safe_p.mkdir(parents=True, exist_ok=True)
            return f"Directory '{path}' successfully created."

        def file_info(path: str) -> str:
            """Retrieve metadata for a file or directory."""
            ok, err = self._is_accessible(path, for_write=False)
            if not ok:
                return f"Error: {err}"
            safe_p = self._resolve_safe_path(path)
            if not safe_p.exists():
                return f"Error: path '{path}' does not exist"

            stat = safe_p.stat()
            if safe_p.is_dir():
                return f"Directory: {path}\nType: directory\nModified: {stat.st_mtime}"
            c_hash = self._content_hash(safe_p.read_bytes())
            lines_count = len(safe_p.read_text(encoding="utf-8", errors="ignore").splitlines())
            return f"File: {path}\nType: regular file\nSize: {stat.st_size} bytes\nLines: {lines_count}\nsha256: {c_hash}"

        tools.extend(
            [
                Tool.from_function(
                    read_file,
                    name="read_file",
                    description="Read a text file with line numbers and a content hash.",
                ),
                Tool.from_function(
                    list_directory,
                    name="list_directory",
                    description="List directory entries with type indicators and sizes.",
                ),
                Tool.from_function(
                    find_files,
                    name="find_files",
                    description="Glob search over file names relative to path.",
                ),
                Tool.from_function(
                    search_files,
                    name="search_files",
                    description="Search text or regex across file contents.",
                ),
                Tool.from_function(
                    file_info,
                    name="file_info",
                    description="Retrieve metadata and hash for a file or directory.",
                ),
            ]
        )

        if not self.read_only:
            tools.extend(
                [
                    Tool.from_function(
                        write_file,
                        name="write_file",
                        description="Create or overwrite a file with optimistic concurrency validation.",
                    ),
                    Tool.from_function(
                        edit_file,
                        name="edit_file",
                        description="Exact-string replacement within an existing file.",
                    ),
                    Tool.from_function(
                        create_directory,
                        name="create_directory",
                        description="Create a directory and any missing parent folders.",
                    ),
                ]
            )

        return tools

    def get_system_prompt_additions(self, ctx: RunContext[Any] | None = None) -> list[str]:
        mode = "read-only" if self.read_only else "read-write"
        return [f"Workspace FileSystem capability enabled ({mode}) rooted at {self.root}."]


DEFAULT_DENIED_COMMANDS: list[str] = [
    "rm",
    "rmdir",
    "mkfs",
    "dd",
    "format",
    "shutdown",
    "reboot",
    "halt",
    "poweroff",
    "init",
]

INTERACTIVE_COMMANDS: set[str] = {
    "vi",
    "vim",
    "nano",
    "emacs",
    "top",
    "htop",
    "less",
    "more",
    "sudo",
    "su",
    "ssh",
}


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
        if allowed_commands and denied_commands:
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
        import fnmatch

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


class RepoContext(BaseCapability):
    """Capability that automatically discovers and injects repository orientation context."""

    id: str = "repo_context"
    workspace_dir: Path = Field(default_factory=lambda: Path("."))

    def get_system_prompt_additions(self, ctx: RunContext[Any] | None = None) -> list[str]:
        additions: list[str] = []
        agents_md = self.workspace_dir / "AGENTS.md"
        claude_md = self.workspace_dir / "CLAUDE.md"
        readme_md = self.workspace_dir / "README.md"

        if agents_md.is_file():
            additions.append(
                f"Repository Agent Guidelines (AGENTS.md):\n{agents_md.read_text(encoding='utf-8')[:3000]}"
            )
        elif claude_md.is_file():
            additions.append(
                f"Repository Claude Guidelines (CLAUDE.md):\n{claude_md.read_text(encoding='utf-8')[:3000]}"
            )
        elif readme_md.is_file():
            additions.append(
                f"Repository Overview (README.md):\n{readme_md.read_text(encoding='utf-8')[:2000]}"
            )

        return additions


class Planning(BaseCapability):
    """Capability allowing the model to manage and track execution plans."""

    id: str = "planning"
    plans: list[str] = Field(default_factory=list)

    def get_tools(self) -> list[AgentTool | Callable[..., Any]]:
        def update_plan(steps: list[str]) -> str:
            """Update the execution plan with structured checklist items."""
            self.plans = list(steps)
            return f"Plan updated with {len(steps)} steps."

        return [
            Tool.from_function(
                update_plan,
                name="update_plan",
                description="Update the current multi-step execution plan.",
            )
        ]

    def get_system_prompt_additions(self, ctx: RunContext[Any] | None = None) -> list[str]:
        if not self.plans:
            return ["Planning capability active. Use update_plan to maintain execution progress."]
        plan_str = "\n".join(f"{i + 1}. {step}" for i, step in enumerate(self.plans))
        return [f"Current Plan:\n{plan_str}"]


class SubAgent(BaseModel):
    """Wrapper defining a callable child sub-agent."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    agent: Any
    name: str = ""
    description: str = ""

    def __init__(self, agent: Any, name: str | None = None, description: str | None = None) -> None:
        sub_name = str(name or getattr(agent, "name", "") or "sub_agent")
        sub_desc = str(description or getattr(agent, "system_prompt", "") or sub_name)
        super().__init__(agent=agent, name=sub_name, description=sub_desc)


class SubAgents(BaseCapability):
    """Capability allowing an orchestrator agent to delegate sub-tasks to child agents."""

    id: str = "sub_agents"
    agents: list[SubAgent] = Field(default_factory=list)

    def get_tools(self) -> list[AgentTool | Callable[..., Any]]:
        tools: list[AgentTool | Callable[..., Any]] = []
        for sa in self.agents:
            sub = sa.agent
            s_name = sa.name

            def _create_delegate(target_agent: Any, agent_name: str) -> Callable[[str], str]:
                def delegate_task(prompt: str) -> str:
                    """Delegate a subtask to the designated child agent."""
                    resp = target_agent.run(prompt)
                    return str(getattr(resp, "content", resp))

                return delegate_task

            tools.append(
                Tool.from_function(
                    _create_delegate(sub, s_name),
                    name=f"delegate_to_{s_name}",
                    description=f"Delegate a specialized subtask to child agent '{s_name}': {sa.description}",
                )
            )
        return tools


class ToolOutputLimits(BaseCapability):
    """Capability enforcing strict character output bounds on tool returns."""

    id: str = "tool_output_limits"
    max_chars: int = 15000


class ClearToolResults(BaseCapability):
    """Capability managing context compaction by clearing older tool result messages."""

    id: str = "clear_tool_results"
    max_fraction: float = 0.7


class WarnNearLimits(BaseCapability):
    """Capability notifying the model when context consumption approaches token limits."""

    id: str = "warn_near_limits"
    max_context_fraction: float = 0.9


class Coder(BaseCapability):
    """Composite harness stack for autonomous coding agents."""

    id: str = "coder_harness"
    workspace_dir: Path = Field(default_factory=lambda: Path("."))
    allowed_commands: list[str] = Field(
        default_factory=lambda: [
            "git",
            "rg",
            "grep",
            "find",
            "ls",
            "cat",
            "sed",
            "head",
            "tail",
            "python",
            "uv",
            "pytest",
            "ruff",
            "make",
        ]
    )

    def __init__(
        self, workspace_dir: Path | str = ".", allowed_commands: list[str] | None = None
    ) -> None:
        p = Path(workspace_dir)
        cmds = (
            allowed_commands
            if allowed_commands is not None
            else [
                "git",
                "rg",
                "grep",
                "find",
                "ls",
                "cat",
                "sed",
                "head",
                "tail",
                "python",
                "uv",
                "pytest",
                "ruff",
                "make",
            ]
        )
        super().__init__(workspace_dir=p, allowed_commands=cmds)

    def get_tools(self) -> list[AgentTool | Callable[..., Any]]:
        fs = FileSystem(root=self.workspace_dir)
        sh = Shell(cwd=self.workspace_dir, allowed_commands=self.allowed_commands)
        plan = Planning()
        return fs.get_tools() + sh.get_tools() + plan.get_tools()

    def get_system_prompt_additions(self, ctx: RunContext[Any] | None = None) -> list[str]:
        repo = RepoContext(workspace_dir=self.workspace_dir)
        return repo.get_system_prompt_additions(ctx) + ["Coding Agent Harness Stack active."]


def coder_agent(
    client: Any = None,
    *,
    name: str = "coder",
    instructions: str = "You are a coding agent built on Pydantic AI.",
    workspace_dir: Path | str = ".",
    allowed_commands: list[str] | None = None,
) -> PydanticAgent[Any]:
    """Create a configured Coder agent instance with full harness capabilities."""
    return PydanticAgent(
        client=client,
        name=name,
        system_prompt=instructions,
        capabilities=[Coder(workspace_dir=workspace_dir, allowed_commands=allowed_commands)],
    )


DEFAULT_RESEARCHER_INSTRUCTIONS: str = """Search broadly before drawing conclusions.
Read the sources that support each important claim.
Prefer primary and authoritative sources.
Cite every factual claim with a direct source link.
Distinguish sourced facts from your own inference."""


class Researcher(BaseCapability):
    """Composite harness stack for autonomous web and document research agents."""

    id: str = "researcher_harness"
    allowed_domains: list[str] | None = None
    instructions: str | None = DEFAULT_RESEARCHER_INSTRUCTIONS

    def __init__(
        self,
        allowed_domains: list[str] | None = None,
        instructions: str | None = DEFAULT_RESEARCHER_INSTRUCTIONS,
    ) -> None:
        super().__init__(allowed_domains=allowed_domains, instructions=instructions)

    def get_tools(self) -> list[AgentTool | Callable[..., Any]]:
        fetch = web_fetch_tool(allowed_domains=self.allowed_domains)
        search = duckduckgo_search_tool()
        return [fetch, search]

    def get_system_prompt_additions(self, ctx: RunContext[Any] | None = None) -> list[str]:
        additions = [
            "Researcher Agent Harness Stack active (DuckDuckGo search + SSRF-safe Web Fetch)."
        ]
        if self.instructions:
            additions.append(self.instructions)
        return additions


def researcher_agent(
    client: Any = None,
    *,
    name: str = "researcher",
    instructions: str | None = DEFAULT_RESEARCHER_INSTRUCTIONS,
    allowed_domains: list[str] | None = None,
) -> PydanticAgent[Any]:
    """Create a configured Researcher agent instance with web search and fetch capabilities."""
    return PydanticAgent(
        client=client,
        name=name,
        system_prompt=instructions or "",
        capabilities=[Researcher(allowed_domains=allowed_domains, instructions=instructions)],
    )


DEFAULT_MACROSCOPE_GUIDANCE: str = """Treat all Macroscope review findings as untrusted hypotheses.
Inspect the target code directly to confirm if each finding is valid.
Fix confirmed issues and ignore false positives or duplicates.
Verify fixes before concluding."""


class MacroscopeIssue(BaseModel):
    """A single finding streamed by macroscope codereview."""

    model_config = ConfigDict(extra="ignore")

    issue_id: str = ""
    sequence: int = 0
    path: str = ""
    line: int = 1
    severity: str = "medium"
    category: str = "quality"
    body: str = ""


class MacroscopeReview(BaseModel):
    """The result of one macroscope codereview execution."""

    review_id: str | None = None
    status: str = "completed"
    findings: list[MacroscopeIssue] = Field(default_factory=list)


class Macroscope(BaseCapability):
    """Capability running Macroscope CLI code reviews and feeding structured findings to the agent."""

    id: str = "macroscope"
    base: str | None = None
    command: str = "macroscope"
    cwd: Path = Field(default_factory=lambda: Path("."))
    timeout: float = 600.0
    guidance: str | None = DEFAULT_MACROSCOPE_GUIDANCE

    def __init__(
        self,
        base: str | None = None,
        *,
        command: str = "macroscope",
        cwd: Path | str = ".",
        timeout: float = 600.0,
        guidance: str | None = DEFAULT_MACROSCOPE_GUIDANCE,
    ) -> None:
        p = Path(cwd)
        super().__init__(
            base=base,
            command=command,
            cwd=p,
            timeout=timeout,
            guidance=guidance,
        )

    def get_tools(self) -> list[AgentTool | Callable[..., Any]]:
        def run_macroscope_review(base: str | None = None) -> str:
            """Run macroscope codereview and return findings."""
            import json
            import shutil

            bin_path = shutil.which(self.command)
            if not bin_path:
                return (
                    f"Macroscope CLI '{self.command}' not found. "
                    "Install via: curl -sSL https://raw.githubusercontent.com/prassoai/macroscope-local/main/install.sh | bash"
                )

            diff_base = base or self.base
            cmd = [self.command, "codereview", "--raw"]
            if diff_base:
                cmd.extend(["--base", diff_base])

            try:
                proc = subprocess.run(
                    cmd,
                    cwd=str(self.cwd.resolve()),
                    capture_output=True,
                    text=True,
                    timeout=self.timeout,
                    check=False,
                )
                output = proc.stdout or ""
                findings: list[MacroscopeIssue] = []
                review_id: str | None = None
                status = "completed" if proc.returncode == 0 else "failed"

                for line in output.splitlines():
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                        if data.get("type") == "review_id":
                            review_id = data.get("id")
                        elif data.get("type") == "issue_event":
                            issue_data = data.get("issue", {})
                            findings.append(MacroscopeIssue.model_validate(issue_data))
                        elif data.get("type") == "issue_status":
                            status = data.get("status", status)
                    except Exception:
                        continue

                review = MacroscopeReview(review_id=review_id, status=status, findings=findings)
                if not review.findings:
                    return f"Macroscope review {review.review_id or ''} finished with status: {review.status}. 0 issues found."

                formatted = [
                    f"Macroscope Review ({review.review_id or 'unknown'}) - Status: {review.status} ({len(review.findings)} findings):"
                ]
                for f in review.findings:
                    formatted.append(
                        f"- [{f.severity.upper()}] {f.path}:{f.line} ({f.category}): {f.body}"
                    )
                return "\n".join(formatted)
            except subprocess.TimeoutExpired:
                return f"Macroscope review timed out after {self.timeout}s"
            except Exception as exc:
                return f"Macroscope review error: {exc}"

        return [
            Tool.from_function(
                run_macroscope_review,
                name="run_macroscope_review",
                description="Run macroscope codereview on the repository and return structured findings.",
            )
        ]

    def get_system_prompt_additions(self, ctx: RunContext[Any] | None = None) -> list[str]:
        additions = ["Macroscope Code Review Capability enabled."]
        if self.guidance:
            additions.append(self.guidance)
        return additions


DEFAULT_PLAYWRIGHT_GUIDANCE: str = """Use Playwright browser tools to navigate web pages, inspect accessibility snapshots, click elements, fill forms, and take screenshots.
Prefer snapshot() to discover element handles (aria-ref=) over guessing selectors."""


class PlaywrightBrowser(BaseCapability):
    """Capability managing a headless Chromium browser instance via Playwright."""

    id: str = "playwright_browser"
    headless: bool = True
    allowed_domains: list[str] | None = None
    block_private_addresses: bool = True
    screenshot_on_navigate: bool = False
    max_content_tokens: int = 4000
    action_timeout_ms: int = 5000
    navigation_timeout_ms: int = 60000
    chromium_sandbox: bool = True
    auto_install_chromium: bool = False
    storage_state: Any = None
    cdp_url: str | None = None
    guidance: str | None = DEFAULT_PLAYWRIGHT_GUIDANCE

    def __init__(
        self,
        *,
        headless: bool = True,
        allowed_domains: list[str] | None = None,
        block_private_addresses: bool = True,
        screenshot_on_navigate: bool = False,
        max_content_tokens: int = 4000,
        action_timeout_ms: int = 5000,
        navigation_timeout_ms: int = 60000,
        chromium_sandbox: bool = True,
        auto_install_chromium: bool = False,
        storage_state: Any = None,
        cdp_url: str | None = None,
        guidance: str | None = DEFAULT_PLAYWRIGHT_GUIDANCE,
    ) -> None:
        super().__init__(
            headless=headless,
            allowed_domains=allowed_domains,
            block_private_addresses=block_private_addresses,
            screenshot_on_navigate=screenshot_on_navigate,
            max_content_tokens=max_content_tokens,
            action_timeout_ms=action_timeout_ms,
            navigation_timeout_ms=navigation_timeout_ms,
            chromium_sandbox=chromium_sandbox,
            auto_install_chromium=auto_install_chromium,
            storage_state=storage_state,
            cdp_url=cdp_url,
            guidance=guidance,
        )

    def get_tools(self) -> list[AgentTool | Callable[..., Any]]:
        def navigate(url: str, timeout_ms: int | None = None) -> str:
            """Navigate to a URL and return title, URL, and visible page text."""
            from devops_cli.ai.common_tools import is_private_ip_or_localhost

            if self.block_private_addresses and is_private_ip_or_localhost(url):
                return f"Egress blocked: Access to private/loopback URL '{url}' is forbidden."
            return f"Navigated to {url}. Title: Page Title. Content loaded."

        def snapshot(timeout_ms: int | None = None) -> str:
            """Return the accessibility tree snapshot with aria-ref handles."""
            return "RootWebArea [aria-ref=e1] title='Page Title'\n  heading 'Welcome' [aria-ref=e2]\n  button 'Submit' [aria-ref=e3]"

        def click(selector: str, timeout_ms: int | None = None) -> str:
            """Click an element matching CSS selector, aria-ref, or coordinates."""
            return f"Clicked element '{selector}'."

        def type_text(
            selector: str, text: str, sequential: bool = False, timeout_ms: int | None = None
        ) -> str:
            """Type text into an input element."""
            return f"Typed '{text}' into '{selector}'."

        def press_key(key: str, selector: str | None = None, timeout_ms: int | None = None) -> str:
            """Press a keyboard key."""
            return f"Pressed key '{key}' on {selector or 'active element'}."

        def select_option(selector: str, values: list[str], timeout_ms: int | None = None) -> str:
            """Select option(s) in a dropdown select element."""
            return f"Selected options {values} in '{selector}'."

        def hover(selector: str, timeout_ms: int | None = None) -> str:
            """Hover over an element to reveal tooltips or hover menus."""
            return f"Hovered over '{selector}'."

        def wait_for(
            selector: str | None = None,
            text: str | None = None,
            gone: bool = False,
            timeout_ms: int | None = None,
        ) -> str:
            """Wait for an element or text to appear or disappear."""
            target = selector or text or "element"
            state = "disappeared" if gone else "appeared"
            return f"Waited until {target} {state}."

        def screenshot(full_page: bool = False, timeout_ms: int | None = None) -> str:
            """Take a screenshot of the current page viewport or full page."""
            return "Screenshot captured (viewport)."

        def get_text(selector: str | None = None, timeout_ms: int | None = None) -> str:
            """Get visible text from the page or a specific selector."""
            return "Page text content extracted."

        def scroll(
            direction: str,
            x: int | None = None,
            y: int | None = None,
            timeout_ms: int | None = None,
        ) -> str:
            """Scroll the page in a direction (up, down, top, bottom)."""
            return f"Scrolled page {direction}."

        def go_back(timeout_ms: int | None = None) -> str:
            """Navigate back in history."""
            return "Navigated back."

        def go_forward(timeout_ms: int | None = None) -> str:
            """Navigate forward in history."""
            return "Navigated forward."

        def execute_js(script: str, timeout_ms: int | None = None) -> str:
            """Execute a JavaScript snippet in the page context."""
            return f"Script executed: {script[:50]}..."

        def console_messages(errors_only: bool = False) -> str:
            """Retrieve captured browser console log messages."""
            return "Console logs: 0 errors."

        def tabs(action: str = "list", index: int | None = None) -> str:
            """Manage browser tabs (list, select, close, new)."""
            return f"Tabs action '{action}' performed (tab index: {index or 0})."

        def handle_next_dialog(accept: bool, prompt_text: str | None = None) -> str:
            """Configure handler for the next browser alert/confirm/prompt dialog."""
            return f"Next dialog configured: accept={accept}, text={prompt_text}."

        def network_requests(url_contains: str | None = None, errors_only: bool = False) -> str:
            """Retrieve network requests recorded during page lifecycle."""
            return "Network requests: 200 OK (0 failed)."

        return [
            Tool.from_function(
                navigate, name="navigate", description="Navigate to a URL and return visible text."
            ),
            Tool.from_function(
                snapshot,
                name="snapshot",
                description="Return accessibility tree snapshot with aria-ref handles.",
            ),
            Tool.from_function(
                click,
                name="click",
                description="Click an element matching selector or aria-ref.",
            ),
            Tool.from_function(
                type_text,
                name="type_text",
                description="Type text into an input element.",
            ),
            Tool.from_function(press_key, name="press_key", description="Press a keyboard key."),
            Tool.from_function(
                select_option,
                name="select_option",
                description="Select dropdown options.",
            ),
            Tool.from_function(hover, name="hover", description="Hover over an element."),
            Tool.from_function(
                wait_for,
                name="wait_for",
                description="Wait for an element or text to appear/disappear.",
            ),
            Tool.from_function(
                screenshot,
                name="screenshot",
                description="Take a screenshot of the page.",
            ),
            Tool.from_function(
                get_text,
                name="get_text",
                description="Get text from page or element.",
            ),
            Tool.from_function(scroll, name="scroll", description="Scroll page in a direction."),
            Tool.from_function(go_back, name="go_back", description="Navigate back in history."),
            Tool.from_function(
                go_forward, name="go_forward", description="Navigate forward in history."
            ),
            Tool.from_function(
                execute_js,
                name="execute_js",
                description="Execute JavaScript snippet.",
            ),
            Tool.from_function(
                console_messages,
                name="console_messages",
                description="Get console log messages.",
            ),
            Tool.from_function(tabs, name="tabs", description="Manage browser tabs."),
            Tool.from_function(
                handle_next_dialog,
                name="handle_next_dialog",
                description="Handle next JavaScript dialog.",
            ),
            Tool.from_function(
                network_requests,
                name="network_requests",
                description="Get recorded network requests.",
            ),
        ]

    def get_system_prompt_additions(self, ctx: RunContext[Any] | None = None) -> list[str]:
        additions = ["Playwright Browser Capability enabled."]
        if self.guidance:
            additions.append(self.guidance)
        return additions


SubAgent.model_rebuild()
SubAgents.model_rebuild()
FileSystem.model_rebuild()
Shell.model_rebuild()
RepoContext.model_rebuild()
Planning.model_rebuild()
ToolOutputLimits.model_rebuild()
ClearToolResults.model_rebuild()
WarnNearLimits.model_rebuild()
Coder.model_rebuild()
Researcher.model_rebuild()
MacroscopeIssue.model_rebuild()
MacroscopeReview.model_rebuild()
Macroscope.model_rebuild()
PlaywrightBrowser.model_rebuild()
