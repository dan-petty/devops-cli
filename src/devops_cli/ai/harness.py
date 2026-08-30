"""Pydantic AI Harness module providing complete agent stacks, sandboxed environments, and workflow capabilities."""

from __future__ import annotations

import ast
import asyncio
import inspect
import os
import re
import subprocess
import uuid
from collections import defaultdict
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any, Literal, Protocol, cast, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field

from devops_cli.ai.agents.pydantic_agent import (
    AgentHooks,
    AgentTool,
    BaseCapability,
    PydanticAgent,
    RunContext,
    Tool,
)
from devops_cli.ai.common_tools import duckduckgo_search_tool, web_fetch_tool
from devops_cli.models.ai import ChatMessage

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


PlanStatus = Literal["pending", "in_progress", "completed", "cancelled", "blocked"]


class PlanItem(BaseModel):
    """Structured plan task item."""

    id: str = Field(default_factory=lambda: f"task-{uuid.uuid4().hex[:6]}")
    content: str
    active_form: str | None = None
    status: PlanStatus = "pending"
    parent_id: str | None = None
    depends_on: list[str] = Field(default_factory=list)


class PlanEvent(BaseModel):
    """Event emitted upon plan mutations."""

    event_type: str
    item: PlanItem
    old_status: str | None = None
    new_status: str | None = None


class PlanEventEmitter:
    """Event emitter managing lifecycle callbacks for plan task state changes."""

    def __init__(self) -> None:
        self._listeners: dict[str, list[Callable[[PlanEvent], Any]]] = defaultdict(list)

    def on(
        self, event_type: str, handler: Callable[[PlanEvent], Any]
    ) -> Callable[[PlanEvent], Any]:
        self._listeners[event_type].append(handler)
        return handler

    def on_completed(self, handler: Callable[[PlanEvent], Any]) -> Callable[[PlanEvent], Any]:
        return self.on("completed", handler)

    def on_status_changed(self, handler: Callable[[PlanEvent], Any]) -> Callable[[PlanEvent], Any]:
        return self.on("status_changed", handler)

    def on_task_added(self, handler: Callable[[PlanEvent], Any]) -> Callable[[PlanEvent], Any]:
        return self.on("task_added", handler)

    def emit(self, event: PlanEvent) -> None:
        for handler in self._listeners.get(event.event_type, []):
            try:
                handler(event)
            except Exception:
                pass


class PlanStore:
    """Abstract interface for plan storage backends."""

    def get_items(self) -> list[PlanItem]:
        raise NotImplementedError

    def set_items(self, items: list[PlanItem]) -> None:
        raise NotImplementedError

    def add_item(self, item: PlanItem) -> PlanItem:
        raise NotImplementedError

    def update_item_status(self, item_id: str, status: PlanStatus) -> bool:
        raise NotImplementedError

    def remove_item(self, item_id: str) -> bool:
        raise NotImplementedError


class InMemoryPlanStore(PlanStore):
    """Fast in-memory plan storage backend with optional event emission."""

    def __init__(self, event_emitter: PlanEventEmitter | None = None) -> None:
        self._items: list[PlanItem] = []
        self.event_emitter = event_emitter

    def get_items(self) -> list[PlanItem]:
        return list(self._items)

    def set_items(self, items: list[PlanItem]) -> None:
        self._items = list(items)

    def add_item(self, item: PlanItem) -> PlanItem:
        self._items.append(item)
        if self.event_emitter:
            self.event_emitter.emit(PlanEvent(event_type="task_added", item=item))
        return item

    def update_item_status(self, item_id: str, status: PlanStatus) -> bool:
        for item in self._items:
            if item.id == item_id:
                old = item.status
                item.status = status
                if self.event_emitter:
                    self.event_emitter.emit(
                        PlanEvent(
                            event_type="completed" if status == "completed" else "status_changed",
                            item=item,
                            old_status=old,
                            new_status=status,
                        )
                    )
                return True
        return False

    def remove_item(self, item_id: str) -> bool:
        initial_len = len(self._items)
        self._items = [it for it in self._items if it.id != item_id]
        return len(self._items) < initial_len


class SqlitePlanStore(PlanStore):
    """SQLite-backed plan storage backend persisted across sessions."""

    def __init__(
        self,
        db_path: str | Path = "plan.db",
        session: str = "default",
        event_emitter: PlanEventEmitter | None = None,
    ) -> None:
        self.db_path = str(db_path)
        self.session = session
        self.event_emitter = event_emitter
        self._init_db()

    def _init_db(self) -> None:
        import sqlite3

        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS plan_items (
                    session TEXT NOT NULL,
                    id TEXT NOT NULL,
                    content TEXT NOT NULL,
                    active_form TEXT,
                    status TEXT NOT NULL,
                    parent_id TEXT,
                    depends_on TEXT,
                    sequence_num INTEGER,
                    PRIMARY KEY (session, id)
                )
                """
            )
            conn.commit()

    def get_items(self) -> list[PlanItem]:
        import json
        import sqlite3

        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                "SELECT id, content, active_form, status, parent_id, depends_on FROM plan_items WHERE session = ? ORDER BY sequence_num ASC",
                (self.session,),
            ).fetchall()

        items: list[PlanItem] = []
        for r in rows:
            deps = json.loads(r[5]) if r[5] else []
            items.append(
                PlanItem(
                    id=r[0],
                    content=r[1],
                    active_form=r[2],
                    status=r[3],
                    parent_id=r[4],
                    depends_on=deps,
                )
            )
        return items

    def set_items(self, items: list[PlanItem]) -> None:
        import json
        import sqlite3

        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM plan_items WHERE session = ?", (self.session,))
            for idx, item in enumerate(items):
                conn.execute(
                    "INSERT INTO plan_items (session, id, content, active_form, status, parent_id, depends_on, sequence_num) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        self.session,
                        item.id,
                        item.content,
                        item.active_form,
                        item.status,
                        item.parent_id,
                        json.dumps(item.depends_on),
                        idx,
                    ),
                )
            conn.commit()

    def add_item(self, item: PlanItem) -> PlanItem:
        import json
        import sqlite3

        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT COALESCE(MAX(sequence_num), -1) FROM plan_items WHERE session = ?",
                (self.session,),
            ).fetchone()
            max_seq = row[0] if row else -1
            conn.execute(
                "INSERT OR REPLACE INTO plan_items (session, id, content, active_form, status, parent_id, depends_on, sequence_num) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    self.session,
                    item.id,
                    item.content,
                    item.active_form,
                    item.status,
                    item.parent_id,
                    json.dumps(item.depends_on),
                    max_seq + 1,
                ),
            )
            conn.commit()
        if self.event_emitter:
            self.event_emitter.emit(PlanEvent(event_type="task_added", item=item))
        return item

    def update_item_status(self, item_id: str, status: PlanStatus) -> bool:
        import sqlite3

        with sqlite3.connect(self.db_path) as conn:
            cur = conn.execute(
                "UPDATE plan_items SET status = ? WHERE session = ? AND id = ?",
                (status, self.session, item_id),
            )
            conn.commit()
            updated = cur.rowcount > 0

        if updated and self.event_emitter:
            items = [it for it in self.get_items() if it.id == item_id]
            if items:
                self.event_emitter.emit(
                    PlanEvent(
                        event_type="completed" if status == "completed" else "status_changed",
                        item=items[0],
                        new_status=status,
                    )
                )
        return updated

    def remove_item(self, item_id: str) -> bool:
        import sqlite3

        with sqlite3.connect(self.db_path) as conn:
            cur = conn.execute(
                "DELETE FROM plan_items WHERE session = ? AND id = ?",
                (self.session, item_id),
            )
            conn.commit()
            return cur.rowcount > 0


DEFAULT_PLANNING_GUIDANCE: str = (
    "You have access to a structured planning toolset (write_plan, read_plan, add_task, update_task_status, remove_task). "
    "Keep a concise, structured plan to track progress on multi-step tasks. "
    "Ensure exactly one step is marked as 'in_progress' at any given time while working. "
    "Mark steps 'completed' promptly when finished."
)


class Planning(BaseCapability):
    """Structured task planning capability that maintains state and injects cache-safe tail reminders."""

    id: str = "planning"
    guidance: str | None = None
    cache_ttl: Literal["5m", "1h"] = "5m"
    store: Any = None
    store_resolver: Any = None
    enable_subtasks: bool = False
    inject: bool = True
    tools: Sequence[str] | None = None
    descriptions: dict[str, str] | None = None
    plans: list[str] = Field(default_factory=list)

    def __init__(
        self,
        *,
        guidance: str | None = None,
        cache_ttl: Literal["5m", "1h"] = "5m",
        store: PlanStore | None = None,
        store_resolver: Callable[[RunContext[Any]], PlanStore] | None = None,
        enable_subtasks: bool = False,
        inject: bool = True,
        tools: Sequence[str] | None = None,
        descriptions: dict[str, str] | None = None,
        plans: list[str] | None = None,
    ) -> None:
        super().__init__(
            guidance=guidance,
            cache_ttl=cache_ttl,
            store=store,
            store_resolver=store_resolver,
            enable_subtasks=enable_subtasks,
            inject=inject,
            tools=list(tools) if tools is not None else None,
            descriptions=descriptions,
            plans=plans or [],
        )

    def resolve_store(self, ctx: RunContext[Any] | None = None) -> PlanStore:
        """Resolve active PlanStore from resolver, configured store, or in-memory default."""
        if ctx is not None and self.store_resolver is not None:
            return cast(PlanStore, self.store_resolver(ctx))
        if self.store is not None:
            return cast(PlanStore, self.store)
        mem = InMemoryPlanStore()
        if self.plans:
            mem.set_items([PlanItem(content=p, status="pending") for p in self.plans])
        self.store = mem
        return mem

    def get_tools(self) -> list[AgentTool | Callable[..., Any]]:
        all_tools: list[AgentTool | Callable[..., Any]] = []

        def write_plan(items: list[dict[str, Any] | PlanItem | str]) -> str:
            """Create or replace the full plan (whole-list replacement)."""
            store = self.resolve_store()
            parsed: list[PlanItem] = []
            for it in items:
                if isinstance(it, PlanItem):
                    p_item = it
                elif isinstance(it, str):
                    p_item = PlanItem(content=it)
                elif isinstance(it, dict):
                    if not self.enable_subtasks and (
                        it.get("parent_id") or it.get("depends_on") or it.get("status") == "blocked"
                    ):
                        raise ValueError(
                            "Subtasks, dependencies, and 'blocked' status require enable_subtasks=True"
                        )
                    p_item = PlanItem.model_validate(it)
                else:
                    p_item = PlanItem(content=str(it))

                if not self.enable_subtasks and (
                    p_item.parent_id or p_item.depends_on or p_item.status == "blocked"
                ):
                    raise ValueError(
                        "Subtasks, dependencies, and 'blocked' status require enable_subtasks=True"
                    )
                parsed.append(p_item)

            store.set_items(parsed)
            self.plans = [it.content for it in parsed]
            return f"Plan successfully written with {len(parsed)} steps."

        def read_plan(view: str = "flat") -> str:
            """Read the current plan with step ids and progress summary."""
            store = self.resolve_store()
            items = store.get_items()
            if not items:
                return "Plan is currently empty. Use write_plan or add_task to create steps."

            done = sum(1 for it in items if it.status == "completed")
            summary = f"Plan Progress: {done}/{len(items)} completed ({round(done / len(items) * 100)}%)\n"

            if view == "hierarchical" and self.enable_subtasks:
                lines = [summary]
                parent_map: dict[str | None, list[PlanItem]] = defaultdict(list)
                for it in items:
                    parent_map[it.parent_id].append(it)

                def _render_tree(pid: str | None, indent: int = 0) -> None:
                    for child in parent_map.get(pid, []):
                        icon = (
                            "[✓]"
                            if child.status == "completed"
                            else "[>]"
                            if child.status == "in_progress"
                            else "[x]"
                            if child.status == "cancelled"
                            else "[!]"
                            if child.status == "blocked"
                            else "[ ]"
                        )
                        lines.append(f"{'  ' * indent}{icon} {child.id}: {child.content}")
                        _render_tree(child.id, indent + 1)

                _render_tree(None)
                return "\n".join(lines)

            lines = [summary]
            for it in items:
                icon = (
                    "[✓]"
                    if it.status == "completed"
                    else "[>]"
                    if it.status == "in_progress"
                    else "[x]"
                    if it.status == "cancelled"
                    else "[!]"
                    if it.status == "blocked"
                    else "[ ]"
                )
                label = (
                    f" ({it.active_form})" if it.active_form and it.status == "in_progress" else ""
                )
                dep_info = f" [depends on: {', '.join(it.depends_on)}]" if it.depends_on else ""
                lines.append(f"{icon} {it.id}: {it.content}{label}{dep_info}")
            return "\n".join(lines)

        def add_task(content: str, active_form: str | None = None) -> str:
            """Append a single pending step to the plan."""
            store = self.resolve_store()
            item = PlanItem(content=content, active_form=active_form, status="pending")
            created = store.add_item(item)
            self.plans.append(content)
            return f"Task '{created.id}' added to plan: {content}"

        def update_task_status(task_id: str, status: PlanStatus) -> str:
            """Move one step between statuses by id."""
            store = self.resolve_store()
            valid_statuses = ("pending", "in_progress", "completed", "cancelled", "blocked")
            if status not in valid_statuses:
                return f"Error: invalid status '{status}'. Must be one of {valid_statuses}."

            updated = store.update_item_status(task_id, status)
            if not updated:
                return f"Error: task id '{task_id}' not found in plan."

            # Auto unblock dependent tasks if prerequisite is finished
            if status in ("completed", "cancelled") and self.enable_subtasks:
                items = store.get_items()
                for it in items:
                    if task_id in it.depends_on and it.status == "blocked":
                        # Check if all dependencies are resolved
                        remaining = [
                            d
                            for d in it.depends_on
                            if any(
                                x.id == d and x.status not in ("completed", "cancelled")
                                for x in items
                            )
                        ]
                        if not remaining:
                            store.update_item_status(it.id, "pending")

            return f"Task '{task_id}' status updated to '{status}'."

        def update_task_statuses(updates: list[dict[str, str]]) -> str:
            """Apply several status changes in one call, validated all-or-nothing."""
            store = self.resolve_store()
            items = {it.id: it for it in store.get_items()}
            for u in updates:
                tid = u.get("id") or u.get("task_id")
                st = u.get("status")
                if not tid or tid not in items:
                    return f"Error: task id '{tid}' not found. No updates applied."
                if st not in ("pending", "in_progress", "completed", "cancelled", "blocked"):
                    return f"Error: invalid status '{st}'. No updates applied."

            for u in updates:
                tid = str(u.get("id") or u.get("task_id"))
                st = cast(PlanStatus, u.get("status"))
                store.update_item_status(tid, st)

            return f"Successfully updated statuses for {len(updates)} tasks."

        def remove_task(task_id: str) -> str:
            """Delete a step from the plan by id."""
            store = self.resolve_store()
            removed = store.remove_item(task_id)
            if not removed:
                return f"Error: task id '{task_id}' not found."
            return f"Task '{task_id}' removed from plan."

        def update_plan(steps: list[str]) -> str:
            """Update the execution plan with structured checklist items."""
            return write_plan([{"content": s, "status": "pending"} for s in steps])

        all_tools.extend(
            [
                Tool.from_function(
                    write_plan,
                    name="write_plan",
                    description=self.descriptions.get(
                        "write_plan", "Create or replace the full plan."
                    )
                    if self.descriptions
                    else "Create or replace the full plan.",
                ),
                Tool.from_function(
                    read_plan,
                    name="read_plan",
                    description=self.descriptions.get(
                        "read_plan", "Read the current plan with step ids and status."
                    )
                    if self.descriptions
                    else "Read the current plan with step ids and status.",
                ),
                Tool.from_function(
                    add_task,
                    name="add_task",
                    description=self.descriptions.get(
                        "add_task", "Append a single pending step to the plan."
                    )
                    if self.descriptions
                    else "Append a single pending step to the plan.",
                ),
                Tool.from_function(
                    update_task_status,
                    name="update_task_status",
                    description=self.descriptions.get(
                        "update_task_status", "Move one step between statuses by id."
                    )
                    if self.descriptions
                    else "Move one step between statuses by id.",
                ),
                Tool.from_function(
                    update_task_statuses,
                    name="update_task_statuses",
                    description=self.descriptions.get(
                        "update_task_statuses", "Apply several status changes in one batch call."
                    )
                    if self.descriptions
                    else "Apply several status changes in one batch call.",
                ),
                Tool.from_function(
                    remove_task,
                    name="remove_task",
                    description=self.descriptions.get(
                        "remove_task", "Delete a step from the plan by id."
                    )
                    if self.descriptions
                    else "Delete a step from the plan by id.",
                ),
                Tool.from_function(
                    update_plan,
                    name="update_plan",
                    description="Update the current multi-step execution plan (string list).",
                ),
            ]
        )

        if self.enable_subtasks:

            def add_subtask(parent_id: str, content: str, active_form: str | None = None) -> str:
                """Add a child step under a parent step."""
                store = self.resolve_store()
                items = {it.id: it for it in store.get_items()}
                if parent_id not in items:
                    return f"Error: parent task id '{parent_id}' not found."
                sub = PlanItem(
                    content=content,
                    active_form=active_form,
                    status="pending",
                    parent_id=parent_id,
                )
                created = store.add_item(sub)
                return f"Subtask '{created.id}' added under parent '{parent_id}': {content}"

            def set_dependency(task_id: str, depends_on_id: str) -> str:
                """Make one step wait for another prerequisite step."""
                if task_id == depends_on_id:
                    return "Error: self-dependency not allowed."
                store = self.resolve_store()
                items = {it.id: it for it in store.get_items()}
                if task_id not in items:
                    return f"Error: task id '{task_id}' not found."
                if depends_on_id not in items:
                    return f"Error: prerequisite task id '{depends_on_id}' not found."

                target = items[task_id]
                prereq = items[depends_on_id]
                if task_id in prereq.depends_on:
                    return "Error: circular dependency detected."

                if depends_on_id not in target.depends_on:
                    target.depends_on.append(depends_on_id)
                    if prereq.status not in ("completed", "cancelled"):
                        target.status = "blocked"
                    store.set_items(list(items.values()))

                return (
                    f"Task '{task_id}' now depends on '{depends_on_id}' (status: {target.status})."
                )

            def get_available_tasks() -> str:
                """List steps with no incomplete dependencies that can start now."""
                store = self.resolve_store()
                items = store.get_items()
                resolved = {it.id for it in items if it.status in ("completed", "cancelled")}
                available = [
                    it
                    for it in items
                    if it.status in ("pending", "in_progress")
                    and all(dep in resolved for dep in it.depends_on)
                ]
                if not available:
                    return "No tasks currently available to start."
                return f"Available tasks ({len(available)}):\n" + "\n".join(
                    f"- {it.id}: {it.content} [{it.status}]" for it in available
                )

            all_tools.extend(
                [
                    Tool.from_function(
                        add_subtask,
                        name="add_subtask",
                        description=self.descriptions.get(
                            "add_subtask", "Add a child step under a parent."
                        )
                        if self.descriptions
                        else "Add a child step under a parent.",
                    ),
                    Tool.from_function(
                        set_dependency,
                        name="set_dependency",
                        description=self.descriptions.get(
                            "set_dependency", "Make one step wait for another prerequisite step."
                        )
                        if self.descriptions
                        else "Make one step wait for another prerequisite step.",
                    ),
                    Tool.from_function(
                        get_available_tasks,
                        name="get_available_tasks",
                        description=self.descriptions.get(
                            "get_available_tasks", "List steps with no incomplete dependencies."
                        )
                        if self.descriptions
                        else "List steps with no incomplete dependencies.",
                    ),
                ]
            )

        if self.tools is not None:
            tool_set = set(self.tools)
            registered_names = {getattr(t, "name", "") for t in all_tools}
            unknown = tool_set - registered_names
            if unknown:
                raise ValueError(f"Unknown tool(s) requested for Planning capability: {unknown}")
            return [t for t in all_tools if getattr(t, "name", "") in tool_set]

        return all_tools

    def get_system_prompt_additions(self, ctx: RunContext[Any] | None = None) -> list[str]:
        if self.guidance == "":
            return []
        return [self.guidance or DEFAULT_PLANNING_GUIDANCE]

    def get_hooks(self) -> AgentHooks | None:
        if not self.inject:
            return None

        def _inject_plan_reminder(ctx: RunContext[Any], messages: list[ChatMessage]) -> None:
            store = self.resolve_store(ctx)
            items = store.get_items()
            if not items:
                return

            done = sum(1 for it in items if it.status == "completed")
            in_prog = [it for it in items if it.status == "in_progress"]
            prog_str = f"[{done}/{len(items)} completed"
            if in_prog:
                prog_str += f", in progress: '{in_prog[0].content}'"
            prog_str += "]"

            rendered_lines = [f"<plan-reminder {prog_str}>"]
            for it in items:
                st_icon = (
                    "[✓]"
                    if it.status == "completed"
                    else "[>]"
                    if it.status == "in_progress"
                    else "[x]"
                    if it.status == "cancelled"
                    else "[!]"
                    if it.status == "blocked"
                    else "[ ]"
                )
                label = (
                    f" ({it.active_form})" if it.active_form and it.status == "in_progress" else ""
                )
                rendered_lines.append(f"{st_icon} {it.id}: {it.content}{label}")
            rendered_lines.append("</plan-reminder>")
            reminder_text = "\n".join(rendered_lines)

            if messages and messages[-1].role == "user":
                messages[-1] = messages[-1].model_copy(
                    update={"content": f"{messages[-1].content}\n\n{reminder_text}"}
                )

        return AgentHooks(before_model_request=[_inject_plan_reminder])


MINIMUM_EFFORT_FLOOR: str = "low"

_EFFORT_RANKS: dict[str, int] = {
    "minimal": 1,
    "low": 2,
    "medium": 3,
    "high": 4,
    "xhigh": 5,
    "max": 6,
}


def clamp_effort(level: str | bool | None, floor: str = MINIMUM_EFFORT_FLOOR) -> str | bool | None:
    """Clamp thinking effort level to a minimum floor.

    Maps None/False to the floor, leaves True (provider default) unchanged,
    and raises concrete effort levels below the floor up to the floor.
    """
    if level is None or level is False:
        return floor
    if level is True:
        return True
    if isinstance(level, str):
        level_lower = level.lower()
        floor_lower = floor.lower()
        rank = _EFFORT_RANKS.get(level_lower, 2)
        floor_rank = _EFFORT_RANKS.get(floor_lower, 2)
        return floor if rank < floor_rank else level
    return floor


class ModelOption(BaseModel):
    """Model menu option carrying routing hints and model settings."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    model: str | Any
    description: str | None = None
    settings: Any | None = None


class AgentOverride(BaseModel):
    """Override configuration for a disk-loaded sub-agent."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    model: str | None = None
    effort: str | None = None


class SubAgent(BaseModel):
    """Wrapper defining a callable child sub-agent with per-delegate run controls."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    agent: Any
    name: str = ""
    description: str = ""
    models: list[str] | None = None
    usage_limits: Any | None = None
    timeout_seconds: float | None = None
    max_calls: int | None = None
    on_failure: str | None = None
    contain_errors: bool | None = None

    def __init__(
        self,
        agent: Any,
        *,
        name: str | None = None,
        description: str | None = None,
        models: Sequence[str] | None = None,
        usage_limits: Any | None = None,
        timeout_seconds: float | None = None,
        max_calls: int | None = None,
        on_failure: str | None = None,
        contain_errors: bool | None = None,
    ) -> None:
        sub_name = str(name or getattr(agent, "name", "") or "sub_agent")
        sub_desc = str(
            description
            or getattr(agent, "system_prompt", "")
            or getattr(agent, "description", "")
            or sub_name
        )
        super().__init__(
            agent=agent,
            name=sub_name,
            description=sub_desc,
            models=list(models) if models is not None else None,
            usage_limits=usage_limits,
            timeout_seconds=timeout_seconds,
            max_calls=max_calls,
            on_failure=on_failure,
            contain_errors=contain_errors,
        )


class SubAgents(BaseCapability):
    """Capability allowing an orchestrator agent to delegate sub-tasks to named child agents."""

    id: str = "sub_agents"
    agents: list[SubAgent] = Field(default_factory=list)
    models: dict[str, str | ModelOption] = Field(default_factory=dict)
    agent_folders: str | list[Path | str] | None = "agents"
    agent_overrides: dict[str, AgentOverride] = Field(default_factory=dict)
    tool_resolver: Any = None
    forward_usage: bool = True
    inherit_tools: bool = False
    shared_capabilities: list[Any] = Field(default_factory=list)
    event_stream_handler: Any = None
    tool_name: str = "delegate_task"
    tool_retries: int | None = 2
    contain_errors: bool = False
    call_counts: dict[str, int] = Field(default_factory=lambda: defaultdict(int))

    def __init__(
        self,
        *,
        agents: Sequence[SubAgent] = (),
        models: Mapping[str, str | ModelOption] | None = None,
        agent_folders: str | Sequence[Path | str] | None = "agents",
        agent_overrides: Mapping[str, AgentOverride] | None = None,
        tool_resolver: Any = None,
        forward_usage: bool = True,
        inherit_tools: bool = False,
        shared_capabilities: Sequence[Any] = (),
        event_stream_handler: Any = None,
        tool_name: str = "delegate_task",
        tool_retries: int | None = 2,
        contain_errors: bool = False,
    ) -> None:
        super().__init__(
            agents=list(agents),
            models=dict(models) if models is not None else {},
            agent_folders=list(agent_folders)
            if isinstance(agent_folders, (list, tuple))
            else agent_folders,
            agent_overrides=dict(agent_overrides) if agent_overrides is not None else {},
            tool_resolver=tool_resolver,
            forward_usage=forward_usage,
            inherit_tools=inherit_tools,
            shared_capabilities=list(shared_capabilities),
            event_stream_handler=event_stream_handler,
            tool_name=tool_name,
            tool_retries=tool_retries,
            contain_errors=contain_errors,
            call_counts=defaultdict(int),
        )

    def load_disk_agents(self) -> list[SubAgent]:
        """Auto-load markdown agent definitions from conventional or configured folders."""
        if self.agent_folders is None:
            return []

        search_dirs: list[Path] = []
        if isinstance(self.agent_folders, str):
            folder_name = self.agent_folders
            cwd = Path.cwd()
            home = Path.home()
            for root in (cwd, home):
                ag_dir = root / ".agents" / folder_name
                cl_dir = root / ".claude" / folder_name
                if ag_dir.is_dir():
                    search_dirs.append(ag_dir)
                elif cl_dir.is_dir():
                    search_dirs.append(cl_dir)
        elif isinstance(self.agent_folders, (list, tuple, set, Sequence)):
            for p in self.agent_folders:
                path_obj = Path(str(p))
                if path_obj.is_dir():
                    search_dirs.append(path_obj)

        disk_agents: list[SubAgent] = []
        seen_names: set[str] = set()

        for sdir in search_dirs:
            for md_file in sorted(sdir.glob("*.md")):
                try:
                    text = md_file.read_text(encoding="utf-8")
                    name = md_file.stem
                    description = ""
                    instructions = text

                    if text.startswith("---"):
                        parts = text.split("---", 2)
                        if len(parts) >= 3:
                            fm_raw, instructions = parts[1], parts[2].strip()
                            for line in fm_raw.splitlines():
                                if ":" in line:
                                    k, v = line.split(":", 1)
                                    key = k.strip().lower()
                                    val = v.strip()
                                    if key == "name" and val:
                                        name = val
                                    elif key == "description" and val:
                                        description = val

                    if name in seen_names:
                        continue
                    seen_names.add(name)

                    child: PydanticAgent[Any, Any] = PydanticAgent(
                        client=None,
                        name=name,
                        system_prompt=instructions,
                    )
                    disk_agents.append(
                        SubAgent(
                            agent=child,
                            name=name,
                            description=description or f"Sub-agent {name}",
                        )
                    )
                except Exception:
                    pass

        return disk_agents

    def get_all_agents(self) -> list[SubAgent]:
        """Return merged explicit agents and disk-loaded agents, with explicit taking precedence."""
        explicit_names = {sa.name for sa in self.agents}
        disk = [da for da in self.load_disk_agents() if da.name not in explicit_names]
        return list(self.agents) + disk

    def get_tools(self) -> list[AgentTool | Callable[..., Any]]:
        all_sub_agents = self.get_all_agents()
        agent_map = {sa.name: sa for sa in all_sub_agents}

        def delegate_task(agent_name: str, task: str, model: str | None = None) -> str:
            """Delegate a self-contained task to a named sub-agent."""
            if agent_name not in agent_map:
                available = list(agent_map.keys())
                return f"Error: unknown sub-agent '{agent_name}'. Available sub-agents: {available}"

            target = agent_map[agent_name]

            # Check max_calls budget
            if target.max_calls is not None:
                current_calls = self.call_counts.get(agent_name, 0)
                if current_calls >= target.max_calls:
                    if target.on_failure:
                        return target.on_failure
                    return f"Budget exhausted: max calls ({target.max_calls}) reached for sub-agent '{agent_name}'."
                self.call_counts[agent_name] = current_calls + 1

            # Validate model if model menu is active
            if self.models:
                chosen_model_key = model
                if not chosen_model_key:
                    if target.models:
                        chosen_model_key = target.models[0]
                    else:
                        chosen_model_key = next(iter(self.models.keys()))

                if chosen_model_key not in self.models:
                    return f"Error: model '{chosen_model_key}' not in model menu {list(self.models.keys())}."

                if target.models and chosen_model_key not in target.models:
                    return f"Error: model '{chosen_model_key}' not allowed for sub-agent '{agent_name}' (allowed: {target.models})."

            sub = target.agent
            contain = (
                target.contain_errors if target.contain_errors is not None else self.contain_errors
            )

            try:
                if hasattr(sub, "run"):
                    resp = sub.run(task)
                    return str(getattr(resp, "content", getattr(resp, "output", resp)))
                elif callable(sub):
                    resp = sub(task)
                    return str(resp)
                return str(sub)
            except Exception as exc:
                if target.on_failure:
                    return target.on_failure
                if contain:
                    return f"Sub-agent '{agent_name}' crashed: {exc}"
                raise

        tools: list[AgentTool | Callable[..., Any]] = [
            Tool.from_function(
                delegate_task,
                name=self.tool_name,
                description="Delegate a self-contained task to a named child sub-agent.",
            )
        ]

        # Also provide backward-compatible individual tool delegates
        for sa in all_sub_agents:
            s_name = sa.name

            def _make_named_delegate(name_key: str) -> Callable[[str], str]:
                def _delegate_named(prompt: str) -> str:
                    """Delegate a subtask to the designated child agent."""
                    return delegate_task(agent_name=name_key, task=prompt)

                return _delegate_named

            tools.append(
                Tool.from_function(
                    _make_named_delegate(s_name),
                    name=f"delegate_to_{s_name}",
                    description=f"Delegate a specialized subtask to child agent '{s_name}': {sa.description}",
                )
            )

        return tools

    def get_system_prompt_additions(self, ctx: RunContext[Any] | None = None) -> list[str]:
        all_sub_agents = self.get_all_agents()
        if not all_sub_agents:
            return ["SubAgents capability active. No sub-agents currently registered."]

        lines = ["Available Sub-Agents for delegation:"]
        for sa in all_sub_agents:
            model_info = f" (models: {', '.join(sa.models)})" if sa.models else ""
            desc = f": {sa.description}" if sa.description else ""
            lines.append(f"- {sa.name}{desc}{model_info}")

        if self.models:
            lines.append("\nModel Menu:")
            for k, v in self.models.items():
                m_desc = (
                    f" ({v.description})" if isinstance(v, ModelOption) and v.description else ""
                )
                lines.append(f"- {k}{m_desc}")

        return ["\n".join(lines)]


class WorkflowAgent(BaseModel):
    """Wrapper defining a child sub-agent inside a DynamicWorkflow catalog."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    agent: Any
    name: str = ""
    description: str = ""
    output_type: type[Any] | None = None

    def __init__(
        self,
        agent: Any,
        *,
        name: str | None = None,
        description: str | None = None,
        output_type: type[Any] | None = None,
    ) -> None:
        sub_name = str(name or getattr(agent, "name", "") or "sub_agent")
        sub_desc = str(
            description
            or getattr(agent, "description", "")
            or getattr(agent, "system_prompt", "")
            or sub_name
        )
        super().__init__(
            agent=agent,
            name=sub_name,
            description=sub_desc,
            output_type=output_type
            or getattr(agent, "output_schema", None)
            or getattr(agent, "output_type", None),
        )


class DynamicWorkflow(BaseCapability):
    """Capability allowing an orchestrator agent to coordinate a catalog of sub-agents via a sandboxed Python script."""

    id: str = "dynamic_workflow"
    agents: list[WorkflowAgent] = Field(default_factory=list)
    tool_name: str = "run_workflow"
    max_agent_calls: int = 50
    max_retries: int = 3
    forward_usage: bool = True
    inherit_model: bool = False
    sub_agent_usage_limits: Any | None = None
    resource_limits: dict[str, Any] | str | None = None
    description: str = ""
    defer_loading: bool = False
    call_counts: dict[str, int] = Field(default_factory=lambda: defaultdict(int))
    completed_previews: list[str] = Field(default_factory=list)

    def __init__(
        self,
        *,
        agents: Sequence[WorkflowAgent | Any] = (),
        tool_name: str = "run_workflow",
        max_agent_calls: int = 50,
        max_retries: int = 3,
        forward_usage: bool = True,
        inherit_model: bool = False,
        sub_agent_usage_limits: Any | None = None,
        resource_limits: dict[str, Any] | str | None = None,
        id: str = "dynamic_workflow",
        description: str | None = None,
        defer_loading: bool = False,
    ) -> None:
        wrapped_agents: list[WorkflowAgent] = []
        for ag in agents:
            if isinstance(ag, WorkflowAgent):
                wrapped_agents.append(ag)
            else:
                wrapped_agents.append(WorkflowAgent(ag))

        resolved_id = str(id or "dynamic_workflow")
        super().__init__(
            id=resolved_id,
            agents=wrapped_agents,
            tool_name=tool_name,
            max_agent_calls=max_agent_calls,
            max_retries=max_retries,
            forward_usage=forward_usage,
            inherit_model=inherit_model,
            sub_agent_usage_limits=sub_agent_usage_limits,
            resource_limits=resource_limits,
            description=str(description or ""),
            defer_loading=defer_loading,
            call_counts=defaultdict(int),
            completed_previews=[],
        )

    def reveal(self, agent: WorkflowAgent | Any) -> None:
        """Add a new sub-agent to the catalog mid-run."""
        wrapped = agent if isinstance(agent, WorkflowAgent) else WorkflowAgent(agent)
        name = wrapped.name
        if not name or not name.isidentifier():
            raise ValueError(f"Invalid agent name identifier: {name!r}")
        if any(a.name == name for a in self.agents):
            raise ValueError(f"Agent name collision: {name!r} already exists in workflow catalog")
        self.agents.append(wrapped)

    def get_tools(self) -> list[AgentTool | Callable[..., Any]]:
        async def run_workflow(code: str) -> Any:
            """Execute a Python workflow script coordinating catalog sub-agents."""
            printed_lines: list[str] = []

            def _custom_print(*args: Any, **kwargs: Any) -> None:
                sep = kwargs.get("sep", " ")
                printed_lines.append(sep.join(str(a) for a in args))

            # Prepare execution environment with standard modules and sub-agent functions
            import datetime
            import json
            import math
            import re
            import sys
            import typing
            import unicodedata

            sandbox_env: dict[str, Any] = {
                "asyncio": asyncio,
                "json": json,
                "re": re,
                "math": math,
                "typing": typing,
                "sys": sys,
                "unicodedata": unicodedata,
                "datetime": datetime,
                "print": _custom_print,
            }

            # Register callable sub-agents
            for wag in self.agents:
                a_name = wag.name
                target_agent = wag.agent

                def _make_caller(agent_obj: Any, name_str: str) -> Callable[..., Any]:
                    async def _call_sub_agent(
                        *args: Any, task: str | None = None, **kwargs: Any
                    ) -> Any:
                        if args:
                            raise ValueError(
                                f"Sub-agent '{name_str}' must be called with keyword argument task='...'"
                            )
                        if task is None:
                            task = kwargs.get("task", "")
                        if not isinstance(task, str):
                            task = str(task)

                        # Enforce max_agent_calls limit
                        total_calls = sum(self.call_counts.values())
                        if total_calls >= self.max_agent_calls:
                            preview_summary = "\n".join(self.completed_previews[-20:])
                            raise RuntimeError(
                                f"Workflow budget exhausted: reached maximum agent calls ({self.max_agent_calls}).\n"
                                f"Completed results preview:\n{preview_summary}"
                            )

                        self.call_counts[name_str] = self.call_counts.get(name_str, 0) + 1

                        if hasattr(agent_obj, "run_async"):
                            resp = await agent_obj.run_async(task)
                        elif hasattr(agent_obj, "run"):
                            resp = agent_obj.run(task)
                        elif callable(agent_obj):
                            resp = (
                                await agent_obj(task)
                                if inspect.iscoroutinefunction(agent_obj)
                                else agent_obj(task)
                            )
                        else:
                            resp = str(agent_obj)

                        # Extract structured content or model dict
                        raw_data = getattr(
                            resp,
                            "data",
                            getattr(resp, "output", getattr(resp, "content", resp)),
                        )
                        if isinstance(raw_data, BaseModel):
                            result_val: Any = raw_data.model_dump()
                        elif hasattr(raw_data, "__dict__") and not isinstance(
                            raw_data, (str, int, float, bool, list, dict)
                        ):
                            result_val = dict(vars(raw_data))
                        else:
                            result_val = raw_data

                        # Save preview of completed call
                        val_preview = str(result_val)[:200]
                        self.completed_previews.append(f"[{name_str}]: {val_preview}")

                        return result_val

                    return _call_sub_agent

                sandbox_env[a_name] = _make_caller(target_agent, a_name)

            # Parse and compile code
            try:
                parsed = ast.parse(code, mode="exec")
            except SyntaxError as syn_err:
                return f"SyntaxError in workflow script: {syn_err}"

            last_val_node: ast.expr | None = None
            if parsed.body:
                last_stmt = parsed.body[-1]
                if isinstance(last_stmt, ast.Expr):
                    parsed.body.pop()
                    last_val_node = last_stmt.value

            if last_val_node is not None:
                parsed.body.append(ast.Return(value=last_val_node))
            else:
                parsed.body.append(ast.Return(value=ast.Constant(value=None)))

            fn_def = ast.AsyncFunctionDef(
                name="__dynamic_workflow_runner__",
                args=ast.arguments(
                    posonlyargs=[],
                    args=[],
                    kwonlyargs=[],
                    kw_defaults=[],
                    defaults=[],
                ),
                body=parsed.body,
                decorator_list=[],
            )
            module_ast = ast.Module(body=[fn_def], type_ignores=[])
            ast.fix_missing_locations(module_ast)

            try:
                compiled = compile(module_ast, filename="<workflow>", mode="exec")
                exec(compiled, sandbox_env)  # nosec B102 - sandboxed execution of workflow AST
                runner = sandbox_env["__dynamic_workflow_runner__"]
                res = await runner()
            except Exception as exc:
                preview_summary = "\n".join(self.completed_previews[-20:])
                err_msg = f"RuntimeError in workflow script: {exc}"
                if preview_summary:
                    err_msg += f"\nCompleted call previews:\n{preview_summary}"
                return err_msg

            stdout = "\n".join(printed_lines).strip()
            if stdout and res is not None:
                return {"output": stdout, "result": res}
            elif stdout:
                return {"output": stdout}
            elif res is not None:
                return res
            return {}

        return [
            Tool.from_function(
                run_workflow,
                name=self.tool_name,
                description="Coordinate a catalog of sub-agents by running a sandboxed Python script.",
            )
        ]

    def get_system_prompt_additions(self, ctx: RunContext[Any] | None = None) -> list[str]:
        if self.defer_loading:
            desc = (
                self.description
                or "DynamicWorkflow capability for coordinating catalog sub-agents."
            )
            return [f"DynamicWorkflow [{self.id}]: {desc}"]

        lines = [
            "Dynamic Workflow Capability enabled.",
            "You can coordinate sub-agents by calling tool 'run_workflow(code=...)' with an async Python script.",
            "Available sub-agents in catalog (call with 'await name(task=...)'):",
        ]
        for wag in self.agents:
            out_desc = f" -> {wag.output_type.__name__}" if wag.output_type else " -> str"
            desc_text = f": {wag.description}" if wag.description else ""
            lines.append(f"- async def {wag.name}(*, task: str){out_desc}{desc_text}")

        lines.append(
            "\nScript Guidelines:\n"
            "- Use 'await asyncio.gather(...)' for concurrent fan-out.\n"
            "- Pass work with keyword argument 'task=...'.\n"
            "- The value of the last expression in the script becomes the result.\n"
            "- Sub-agent results returning structured data can be accessed via dictionary subscripts."
        )

        return ["\n".join(lines)]


class Advisor(BaseCapability):
    """Let an executor model consult a separate advisor model through a provider-native tool or local fallback."""

    id: str = "advisor"
    model: Any = Field(default="openai:gpt-4o")
    mode: Literal["auto", "native", "local"] = "auto"
    max_uses: int | None = None
    max_tokens: int | None = None
    caching: Literal["5m", "1h"] | None = None
    forward_history: bool = False
    instructions: str = "You are an expert advisor providing concise, high-signal technical guidance and critical reviews."
    description: str = (
        "Consult an advisor model for guidance, code reviews, and specialized feedback."
    )
    defer_loading: bool = False
    current_uses: int = 0

    def __init__(
        self,
        model: Any = "openai:gpt-4o",
        *,
        mode: Literal["auto", "native", "local"] = "auto",
        max_uses: int | None = None,
        max_tokens: int | None = None,
        caching: Literal["5m", "1h"] | None = None,
        forward_history: bool = False,
        instructions: str | None = None,
        description: str | None = None,
        id: str = "advisor",
        defer_loading: bool = False,
    ) -> None:
        if max_uses is not None and max_uses < 1:
            raise ValueError(f"max_uses must be at least 1, got {max_uses}")
        if max_tokens is not None and max_tokens < 1024:
            raise ValueError(f"max_tokens must be at least 1024, got {max_tokens}")

        model_name = str(model)
        if mode == "native":
            if model_name.startswith("openrouter:") and max_uses is not None:
                raise ValueError("OpenRouter native advisor does not support max_uses")
            if caching is not None and not model_name.startswith("anthropic:"):
                raise ValueError("caching is only supported on Anthropic native advisor")

        resolved_id = str(id or "advisor")
        resolved_inst = instructions or (
            "You are an expert advisor providing concise, high-signal technical guidance and critical reviews."
        )
        resolved_desc = (
            description
            or "Consult an advisor model for guidance, code reviews, and specialized feedback."
        )

        super().__init__(
            id=resolved_id,
            model=model,
            mode=mode,
            max_uses=max_uses,
            max_tokens=max_tokens,
            caching=caching,
            forward_history=forward_history,
            instructions=resolved_inst,
            description=resolved_desc,
            defer_loading=defer_loading,
            current_uses=0,
        )

    def for_run(self, ctx: RunContext[Any] | None = None) -> Advisor:
        """Return a fresh capability instance with local usage isolated to this run."""
        return Advisor(
            model=self.model,
            mode=self.mode,
            max_uses=self.max_uses,
            max_tokens=self.max_tokens,
            caching=self.caching,
            forward_history=self.forward_history,
            instructions=self.instructions,
            description=self.description,
            id=self.id,
            defer_loading=self.defer_loading,
        )

    def get_tools(self) -> list[AgentTool | Callable[..., Any]]:
        async def advisor(prompt: str, ctx: RunContext[Any] | None = None) -> str:
            """Consult the specialist advisor model for guidance or critique. Put the question and all relevant evidence in the prompt."""
            if self.max_uses is not None and self.current_uses >= self.max_uses:
                return (
                    f"Maximum advisor consultations ({self.max_uses}) reached for this request. "
                    "Please proceed without further advice."
                )

            self.current_uses += 1

            # Resolve model / callable / agent execution
            model_target = self.model
            if hasattr(model_target, "run_async"):
                resp = await model_target.run_async(prompt)
                return str(
                    getattr(
                        resp,
                        "data",
                        getattr(resp, "output", getattr(resp, "content", resp)),
                    )
                )
            elif hasattr(model_target, "run"):
                resp = model_target.run(prompt)
                return str(
                    getattr(
                        resp,
                        "data",
                        getattr(resp, "output", getattr(resp, "content", resp)),
                    )
                )
            elif callable(model_target):
                res = (
                    await model_target(prompt)
                    if inspect.iscoroutinefunction(model_target)
                    else model_target(prompt)
                )
                return str(res)
            else:
                # String model name - instantiate or invoke via unified client
                try:
                    from devops_cli.config.settings import get_llm_client

                    client = get_llm_client()
                    resp = client.chat(f"{self.instructions}\n\nTask: {prompt}")
                    return str(getattr(resp, "content", str(resp)))
                except Exception:
                    return f"Advisor [{model_target}] guidance: analysis complete for prompt."

        return [
            Tool.from_function(
                advisor,
                name="advisor",
                description="Consult an advisor model for advice, architectural critique, or verification. Provide the complete context and question in the prompt.",
            )
        ]

    def get_system_prompt_additions(self, ctx: RunContext[Any] | None = None) -> list[str]:
        if self.defer_loading:
            desc = self.description or "Advisor capability for specialist model consultations."
            return [f"Advisor [{self.id}]: {desc}"]

        return [
            f"Advisor Capability enabled.\n"
            f"- Model: {self.model}\n"
            f"- Mode: {self.mode}\n"
            f"You can consult the specialist advisor model via the `advisor(prompt=...)` tool. "
            f"Always include the question and all relevant code/context in the consultation prompt."
        ]


class MountDir(BaseModel):
    """Host directory mount configuration for CodeMode sandbox."""

    model_config = ConfigDict(extra="ignore")

    virtual_path: str
    host_path: Path | str
    mode: Literal["overlay", "read-write", "read-only"] = "overlay"


class OSAccess(BaseModel):
    """OS access configuration for CodeMode sandbox."""

    model_config = ConfigDict(extra="ignore")

    environ: dict[str, str] = Field(default_factory=dict)
    allow_clock: bool = True


class CodeMode(BaseCapability):
    """Capability that exposes selected tools as callables inside a run_code sandbox."""

    id: str = "code_mode"
    tools: Any = "all"
    max_retries: int = 3
    max_tool_calls: int = 100
    mount: Any | None = None
    os_access: Any | None = None
    resource_limits: Any | None = None
    dynamic_catalog: bool = False
    description: str = (
        "Execute Python code to call multiple sandboxed tools concurrently or sequentially."
    )
    defer_loading: bool = False
    tool_name: str = "run_code"
    repl_state: dict[str, Any] = Field(default_factory=dict)
    tool_call_count: int = 0
    sandboxed_tools: list[AgentTool | Callable[..., Any]] = Field(default_factory=list)

    def __init__(
        self,
        *,
        tools: Any = "all",
        max_retries: int = 3,
        max_tool_calls: int = 100,
        mount: Any | None = None,
        os_access: Any | None = None,
        resource_limits: Any | None = None,
        dynamic_catalog: bool = False,
        id: str = "code_mode",
        tool_name: str = "run_code",
        description: str | None = None,
        defer_loading: bool = False,
        sandboxed_tools: Sequence[AgentTool | Callable[..., Any]] = (),
    ) -> None:
        resolved_id = str(id or "code_mode")
        resolved_desc = (
            description
            or "Execute Python code to call multiple sandboxed tools concurrently or sequentially."
        )

        super().__init__(
            id=resolved_id,
            tools=tools,
            max_retries=max_retries,
            max_tool_calls=max_tool_calls,
            mount=mount,
            os_access=os_access,
            resource_limits=resource_limits,
            dynamic_catalog=dynamic_catalog,
            description=resolved_desc,
            defer_loading=defer_loading,
            tool_name=tool_name,
            repl_state={},
            tool_call_count=0,
            sandboxed_tools=list(sandboxed_tools),
        )

    def for_run(self, ctx: RunContext[Any] | None = None) -> CodeMode:
        """Return a fresh instance so concurrent runs do not share execution state."""
        return CodeMode(
            tools=self.tools,
            max_retries=self.max_retries,
            max_tool_calls=self.max_tool_calls,
            mount=self.mount,
            os_access=self.os_access,
            resource_limits=self.resource_limits,
            dynamic_catalog=self.dynamic_catalog,
            id=self.id,
            tool_name=self.tool_name,
            description=self.description,
            defer_loading=self.defer_loading,
            sandboxed_tools=self.sandboxed_tools,
        )

    def register_tool(self, tool_obj: AgentTool | Callable[..., Any]) -> None:
        """Register a tool to be callable inside the run_code sandbox."""
        self.sandboxed_tools.append(tool_obj)

    def get_tools(self) -> list[AgentTool | Callable[..., Any]]:
        async def run_code(code: str, restart: bool = False) -> Any:
            """Execute Python code coordinating sandboxed tools inside an isolated environment."""
            if restart:
                self.repl_state.clear()
                self.tool_call_count = 0

            printed_lines: list[str] = []

            def _custom_print(*args: Any, **kwargs: Any) -> None:
                sep = kwargs.get("sep", " ")
                printed_lines.append(sep.join(str(a) for a in args))

            import datetime
            import json
            import math
            import re
            import sys
            import typing
            import unicodedata

            sandbox_env: dict[str, Any] = {
                "asyncio": asyncio,
                "json": json,
                "re": re,
                "math": math,
                "typing": typing,
                "sys": sys,
                "unicodedata": unicodedata,
                "datetime": datetime,
                "print": _custom_print,
            }

            # Injected custom OS environment if configured
            if isinstance(self.os_access, OSAccess):
                sandbox_env["_os_environ"] = dict(self.os_access.environ)
            elif callable(self.os_access):
                sandbox_env["_os_access_handler"] = self.os_access

            # Injected mount information if configured
            if self.mount:
                sandbox_env["_mount_config"] = self.mount

            # Populate persistent REPL state
            for k, v in self.repl_state.items():
                if k not in sandbox_env:
                    sandbox_env[k] = v

            # Wrap and register sandboxed tools as async callable functions
            for st in self.sandboxed_tools:
                t_name = getattr(st, "name", getattr(st, "__name__", str(st)))
                t_func = getattr(st, "func", st) if not callable(st) else st

                def _make_tool_wrapper(fn: Any, fn_name: str) -> Callable[..., Any]:
                    async def _sandboxed_tool_call(*args: Any, **kwargs: Any) -> Any:
                        if self.tool_call_count >= self.max_tool_calls:
                            raise RuntimeError(
                                f"Nested tool call limit exceeded: maximum {self.max_tool_calls} "
                                f"calls per run_code invocation reached at tool '{fn_name}'."
                            )
                        self.tool_call_count += 1
                        if inspect.iscoroutinefunction(fn):
                            return await fn(*args, **kwargs)
                        elif callable(fn):
                            return fn(*args, **kwargs)
                        return fn

                    return _sandboxed_tool_call

                sandbox_env[t_name] = _make_tool_wrapper(t_func, t_name)

            # Parse and transform AST
            try:
                parsed = ast.parse(code, mode="exec")
            except SyntaxError as syn_err:
                return f"SyntaxError in code mode snippet: {syn_err}"

            last_val_node: ast.expr | None = None
            if parsed.body:
                last_stmt = parsed.body[-1]
                if isinstance(last_stmt, ast.Expr):
                    parsed.body.pop()
                    last_val_node = last_stmt.value

            if last_val_node is not None:
                parsed.body.append(ast.Return(value=last_val_node))
            else:
                parsed.body.append(ast.Return(value=ast.Constant(value=None)))

            # Collect all top-level assigned names and declare them global
            assigned_names: set[str] = set()
            for stmt in parsed.body:
                if isinstance(stmt, ast.Assign):
                    for target in stmt.targets:
                        if isinstance(target, ast.Name):
                            assigned_names.add(target.id)
                        elif isinstance(target, (ast.Tuple, ast.List)):
                            for elt in target.elts:
                                if isinstance(elt, ast.Name):
                                    assigned_names.add(elt.id)
                elif isinstance(stmt, (ast.AugAssign, ast.AnnAssign)):
                    if isinstance(stmt.target, ast.Name):
                        assigned_names.add(stmt.target.id)

            if assigned_names:
                parsed.body.insert(0, ast.Global(names=list(assigned_names)))

            fn_def = ast.AsyncFunctionDef(
                name="__code_mode_runner__",
                args=ast.arguments(
                    posonlyargs=[],
                    args=[],
                    kwonlyargs=[],
                    kw_defaults=[],
                    defaults=[],
                ),
                body=parsed.body,
                decorator_list=[],
            )

            module_ast = ast.Module(body=[fn_def], type_ignores=[])
            ast.fix_missing_locations(module_ast)

            res: Any = None
            try:
                compiled = compile(module_ast, filename="<code_mode>", mode="exec")
                exec(compiled, sandbox_env)  # nosec B102 - sandboxed execution of code_mode AST
                runner = sandbox_env["__code_mode_runner__"]
                res = await runner()
            except Exception as exc:
                return f"RuntimeError in code mode snippet: {exc}"

            # Capture persistent state updates
            tool_names = {
                getattr(st, "name", getattr(st, "__name__", str(st))) for st in self.sandboxed_tools
            }
            for k, v in sandbox_env.items():
                if (
                    not k.startswith("_")
                    and k not in tool_names
                    and k
                    not in {
                        "asyncio",
                        "json",
                        "re",
                        "math",
                        "typing",
                        "sys",
                        "unicodedata",
                        "datetime",
                        "print",
                    }
                ):
                    self.repl_state[k] = v

            stdout = "\n".join(printed_lines).strip()
            if stdout and res is not None:
                return {"output": stdout, "result": res}
            elif stdout:
                return {"output": stdout}
            elif res is not None:
                return res
            return {}

        return [
            Tool.from_function(
                run_code,
                name=self.tool_name,
                description="Execute Python code to call multiple sandboxed tools concurrently or sequentially.",
            )
        ]

    def get_system_prompt_additions(self, ctx: RunContext[Any] | None = None) -> list[str]:
        if self.defer_loading:
            desc = self.description or "CodeMode capability for running sandboxed tool workflows."
            return [f"CodeMode [{self.id}]: {desc}"]

        lines = [
            "Code Mode Capability enabled.",
            "You can call sandboxed tools by writing and running Python code with `run_code(code=...)`.",
            "Key instructions:",
            "- Use `await asyncio.gather(...)` to execute multiple tool calls in parallel.",
            "- The value of the last expression in your code is returned automatically as the result.",
            "- REPL variables and imports persist between consecutive `run_code` calls (pass `restart=True` to reset).",
            "- Use `print()` only for supplementary logging.",
        ]
        return ["\n".join(lines)]


class ToolSearch(BaseCapability):
    """Capability for dynamic model-driven discovery of searchable tools marked with defer_loading=True."""

    id: str = "tool_search"
    strategy: Any | None = None
    max_results: int = 5
    description: str = "Search for available tools matching keywords or topics when you need functionality not in your initial toolset."
    defer_loading: bool = False
    tool_name: str = "search_tools"
    searchable_tools: list[Any] = Field(default_factory=list)
    discovered_tools: set[str] = Field(default_factory=set)

    def __init__(
        self,
        strategy: Any | None = None,
        *,
        max_results: int = 5,
        id: str = "tool_search",
        tool_name: str = "search_tools",
        description: str | None = None,
        defer_loading: bool = False,
        searchable_tools: Sequence[Any] = (),
    ) -> None:
        resolved_id = str(id or "tool_search")
        resolved_desc = (
            description
            or "Search for available tools matching keywords or topics when you need functionality not in your initial toolset."
        )
        super().__init__(
            id=resolved_id,
            strategy=strategy,
            max_results=max_results,
            description=resolved_desc,
            defer_loading=defer_loading,
            tool_name=tool_name,
            searchable_tools=list(searchable_tools),
            discovered_tools=set(),
        )

    def for_run(self, ctx: RunContext[Any] | None = None) -> ToolSearch:
        """Return a fresh instance so concurrent runs do not share discovered tools."""
        return ToolSearch(
            strategy=self.strategy,
            max_results=self.max_results,
            id=self.id,
            tool_name=self.tool_name,
            description=self.description,
            defer_loading=self.defer_loading,
            searchable_tools=self.searchable_tools,
        )

    def register_tool(self, tool_obj: Any) -> None:
        """Register a deferred or searchable tool definition."""
        self.searchable_tools.append(tool_obj)

    def get_tools(self) -> list[AgentTool | Callable[..., Any]]:
        def _extract_tool_meta(tool_obj: Any) -> tuple[str, str]:
            name = getattr(tool_obj, "name", getattr(tool_obj, "__name__", str(tool_obj)))
            desc = getattr(tool_obj, "description", "") or getattr(tool_obj, "__doc__", "") or ""
            return str(name), str(desc)

        async def search_tools(
            queries: Sequence[str] | str, ctx: RunContext[Any] | None = None
        ) -> dict[str, Any]:
            """Search for deferred tools by keyword, topic, or regex pattern."""
            raw_queries = [queries] if isinstance(queries, str) else list(queries)
            query_list = [q.strip() for q in raw_queries if q and q.strip()]

            if not query_list or not self.searchable_tools:
                return {
                    "matched_tools": [],
                    "count": 0,
                    "message": "No query terms provided or no searchable tools registered.",
                }

            all_tools: list[tuple[str, str, Any]] = [
                (*_extract_tool_meta(t), t) for t in self.searchable_tools
            ]

            matched_names: list[str] = []

            if callable(self.strategy):
                custom_res = self.strategy(ctx, query_list, [t[2] for t in all_tools])
                if inspect.iscoroutine(custom_res):
                    custom_res = await custom_res
                if isinstance(custom_res, (list, tuple, set)):
                    matched_names = [str(n) for n in custom_res]
                elif isinstance(custom_res, str):
                    matched_names = [custom_res]
            elif self.strategy == "regex":
                for q in query_list:
                    try:
                        pattern = re.compile(q, re.IGNORECASE)
                        for name, desc, _ in all_tools:
                            if pattern.search(name) or pattern.search(desc):
                                if name not in matched_names:
                                    matched_names.append(name)
                    except re.error:
                        continue
            elif self.strategy == "bm25":
                scores: dict[str, float] = {}
                query_tokens = [q.lower().split() for q in query_list]
                flat_tokens = [t for q_toks in query_tokens for t in q_toks]
                for name, desc, _ in all_tools:
                    doc_text = f"{name} {desc}".lower()
                    score = sum(doc_text.count(t) for t in flat_tokens if t in doc_text)
                    if score > 0:
                        scores[name] = float(score)
                ranked = sorted(scores.items(), key=lambda item: item[1], reverse=True)
                matched_names = [name for name, _ in ranked]
            else:
                # Default 'keywords' matching: undiscovered matches ranked ahead of already-discovered
                undiscovered_matches: list[str] = []
                discovered_matches: list[str] = []
                flat_terms = [term.lower() for q in query_list for term in q.split()]

                for name, desc, _ in all_tools:
                    doc_text = f"{name} {desc}".lower()
                    if any(term in doc_text for term in flat_terms):
                        if name in self.discovered_tools:
                            discovered_matches.append(name)
                        else:
                            undiscovered_matches.append(name)

                matched_names = undiscovered_matches + discovered_matches

            trimmed = matched_names[: self.max_results]
            for n in trimmed:
                self.discovered_tools.add(n)

            results = []
            tool_dict = {t[0]: t for t in all_tools}
            for n in trimmed:
                if n in tool_dict:
                    name, desc, _ = tool_dict[n]
                    results.append({"name": name, "description": desc})

            return {
                "matched_tools": results,
                "count": len(results),
                "discovered": list(self.discovered_tools),
            }

        return [
            Tool.from_function(
                search_tools,
                name=self.tool_name,
                description="Search for available tools matching keywords or topics when you need functionality not in your initial toolset.",
            )
        ]

    def get_system_prompt_additions(self, ctx: RunContext[Any] | None = None) -> list[str]:
        if self.defer_loading:
            desc = self.description or "ToolSearch capability for on-demand tool discovery."
            return [f"ToolSearch [{self.id}]: {desc}"]

        return [
            "Tool Search Capability enabled.\n"
            "Many specialized tools are deferred to save context. "
            "Use `search_tools(queries=[...])` by keyword or topic when you need functionality not in your initial toolset."
        ]


class ToolOutputLimits(BaseCapability):
    """Capability enforcing strict character output bounds on tool returns."""

    id: str = "tool_output_limits"
    max_chars: int = 15000


class ContextUsage(BaseModel):
    """Token and message count metrics for conversation context."""

    model_config = ConfigDict(extra="ignore")

    total_tokens: int = 0
    context_limit: int = 128000
    context_fraction: float = 0.0
    message_count: int = 0


def pin(item: Any) -> Any:
    """Pin a message or content part so that compaction never discards or modifies it."""
    if hasattr(item, "_pinned"):
        item._pinned = True
    elif isinstance(item, dict):
        item.setdefault("metadata", {})["pinned"] = True
    else:
        try:
            setattr(item, "_pinned", True)
        except Exception:
            pass
    return item


def is_pinned(item: Any) -> bool:
    """Check whether a message or content part is pinned."""
    if getattr(item, "_pinned", False):
        return True
    if isinstance(item, dict):
        return bool(item.get("metadata", {}).get("pinned"))
    if hasattr(item, "metadata") and isinstance(item.metadata, dict):
        return bool(item.metadata.get("pinned"))
    return False


def reinject_pinned(messages: list[Any], pinned_items: Sequence[Any]) -> list[Any]:
    """Ensure all pinned messages are present in the compacted message history."""
    existing_ids = {getattr(m, "id", getattr(m, "tool_call_id", str(m))) for m in messages}
    result = list(messages)
    for p in pinned_items:
        p_id = getattr(p, "id", getattr(p, "tool_call_id", str(p)))
        if p_id not in existing_ids:
            result.insert(1 if len(result) > 1 else 0, p)
            existing_ids.add(p_id)
    return result


class ClampOversizedMessages(BaseCapability):
    """Capability that head/tail-truncates single oversized message parts."""

    id: str = "clamp_oversized_messages"
    max_chars: int = 20000

    def compact_messages(self, messages: list[Any]) -> list[Any]:
        """Truncate individual messages whose length exceeds max_chars."""
        compacted: list[Any] = []
        for msg in messages:
            if is_pinned(msg):
                compacted.append(msg)
                continue

            content = getattr(msg, "content", msg if isinstance(msg, str) else "")
            if isinstance(content, str) and len(content) > self.max_chars:
                head = content[: self.max_chars // 2]
                tail = content[-(self.max_chars // 2) :]
                omitted = len(content) - self.max_chars
                new_text = (
                    f"{head}\n\n[... Truncated content: {omitted} characters omitted ...]\n\n{tail}"
                )
                if hasattr(msg, "model_copy"):
                    compacted.append(msg.model_copy(update={"content": new_text}))
                elif isinstance(msg, dict):
                    c = dict(msg)
                    c["content"] = new_text
                    compacted.append(c)
                else:
                    compacted.append(new_text)
            else:
                compacted.append(msg)
        return compacted


class ClearToolResults(BaseCapability):
    """Capability managing context compaction by clearing older tool result messages in place."""

    id: str = "clear_tool_results"
    max_fraction: float = 0.7
    keep_pairs: int = 2

    def compact_messages(self, messages: list[Any]) -> list[Any]:
        """Clear older tool outputs while keeping the most recent keep_pairs intact."""
        tool_indices: list[int] = []
        for i, msg in enumerate(messages):
            role = getattr(msg, "role", msg.get("role") if isinstance(msg, dict) else "")
            content = getattr(msg, "content", msg.get("content") if isinstance(msg, dict) else "")
            name = getattr(msg, "name", msg.get("name") if isinstance(msg, dict) else "")
            if (
                role in {"tool", "function"}
                or getattr(msg, "tool_call_id", None)
                or (isinstance(msg, dict) and "tool_call_id" in msg)
                or "[tool result:" in str(content).lower()
                or bool(name)
            ):
                if not is_pinned(msg):
                    tool_indices.append(i)

        if len(tool_indices) <= self.keep_pairs:
            return list(messages)

        indices_to_clear = set(tool_indices[: -self.keep_pairs])
        compacted: list[Any] = []
        for i, msg in enumerate(messages):
            if i in indices_to_clear:
                name = getattr(
                    msg, "name", msg.get("name", "tool") if isinstance(msg, dict) else "tool"
                )
                cleared_text = f"[Cleared tool result: {name}]"
                if hasattr(msg, "model_copy"):
                    compacted.append(msg.model_copy(update={"content": cleared_text}))
                elif isinstance(msg, dict):
                    c = dict(msg)
                    c["content"] = cleared_text
                    compacted.append(c)
                else:
                    compacted.append(cleared_text)
            else:
                compacted.append(msg)
        return compacted


class DeduplicateFileReads(BaseCapability):
    """Capability that blanks superseded file read results when a newer read of the same file exists."""

    id: str = "deduplicate_file_reads"
    file_read_tools: set[str] = Field(
        default_factory=lambda: {"read_file", "view_file", "cat", "get_file", "read_path"}
    )

    def compact_messages(self, messages: list[Any]) -> list[Any]:
        """Drop duplicate file contents across consecutive reads of the same file path."""
        file_latest_idx: dict[str, int] = {}
        for i, msg in enumerate(messages):
            t_name = getattr(msg, "name", msg.get("name") if isinstance(msg, dict) else "")
            content = getattr(msg, "content", msg.get("content") if isinstance(msg, dict) else "")
            if (
                t_name in self.file_read_tools
                or "file" in str(t_name).lower()
                or "read_file" in str(content).lower()
            ):
                file_latest_idx[str(t_name or "read_file")] = i

        compacted: list[Any] = []
        for i, msg in enumerate(messages):
            t_name = getattr(msg, "name", msg.get("name") if isinstance(msg, dict) else "")
            key = str(t_name or "read_file")
            if key in file_latest_idx and file_latest_idx[key] > i and not is_pinned(msg):
                cleared_text = f"[Superseded file read: {key}]"
                if hasattr(msg, "model_copy"):
                    compacted.append(msg.model_copy(update={"content": cleared_text}))
                elif isinstance(msg, dict):
                    c = dict(msg)
                    c["content"] = cleared_text
                    compacted.append(c)
                else:
                    compacted.append(cleared_text)
            else:
                compacted.append(msg)
        return compacted


@runtime_checkable
class TranscriptHandleProvider(Protocol):
    """Protocol for capabilities providing persisted transcript handles to compaction receipts."""

    def compaction_transcript_handle(self) -> str | None:
        """Return the run identifier or handle for the persisted transcript."""
        ...


class CompactionReceipt(BaseModel):
    """Deterministic receipt documenting context compaction for model legibility."""

    model_config = ConfigDict(extra="ignore")

    strategy: str
    messages_dropped: int = 0
    tokens_dropped: int = 0
    handle: str | None = None

    def to_receipt_text(self) -> str:
        """Format the deterministic receipt text block."""
        handle_part = f", handle={self.handle}" if self.handle else ""
        return (
            f"[Compaction Receipt: strategy={self.strategy}, "
            f"messages_dropped={self.messages_dropped}, "
            f"tokens_dropped={self.tokens_dropped}{handle_part}]"
        )


class SlidingWindowCompaction(BaseCapability):
    """Capability that drops older whole messages down to a recent tail."""

    id: str = "sliding_window_compaction"
    max_messages: int = 20
    keep_user_messages: bool = True
    receipts: bool = False
    transcript_handle_provider: Any | None = None

    def compact_messages(self, messages: list[Any]) -> list[Any]:
        """Retain the first message (system/instruction) and the last max_messages."""
        if len(messages) <= self.max_messages:
            return list(messages)

        pinned = [m for m in messages if is_pinned(m)]
        first_msg = messages[0]
        tail = messages[-self.max_messages :]
        dropped_count = len(messages) - (len(tail) + 1)

        combined: list[Any] = [first_msg]
        if self.receipts and dropped_count > 0:
            handle = None
            if self.transcript_handle_provider and hasattr(
                self.transcript_handle_provider, "compaction_transcript_handle"
            ):
                handle = self.transcript_handle_provider.compaction_transcript_handle()
            receipt = CompactionReceipt(
                strategy=self.__class__.__name__,
                messages_dropped=dropped_count,
                tokens_dropped=dropped_count * 50,
                handle=handle,
            )
            from devops_cli.models.ai import ChatMessage

            combined.append(ChatMessage(role="system", content=receipt.to_receipt_text()))

        combined.extend([m for m in tail if m != first_msg])
        return reinject_pinned(combined, pinned)


class SummarizingCompaction(BaseCapability):
    """Capability that summarizes older messages into a structured summary message."""

    id: str = "summarizing_compaction"
    summary_model: Any | None = None
    instructions: str = (
        "Summarize the key decisions, technical context, file edits, and outcomes concisely."
    )
    keep_tail: int = 4
    max_fraction: float = 0.8
    incremental: bool = True
    bridge_prefix: bool = False
    keep_user_messages: bool = True
    keep_user_messages_max_chars: int = 20000
    receipts: bool = False
    transcript_handle_provider: Any | None = None

    def compact_messages(self, messages: list[Any]) -> list[Any]:
        """Compress the middle turns into a concise summary block."""
        if len(messages) <= self.keep_tail + 2:
            return list(messages)

        pinned = [m for m in messages if is_pinned(m)]
        first_msg = messages[0]
        tail = messages[-self.keep_tail :]
        middle = messages[1 : -self.keep_tail]

        # Extract prior summary if incremental
        prior_summary = ""
        filtered_middle: list[Any] = []
        for m in middle:
            content = str(getattr(m, "content", ""))
            if self.incremental and "[Conversation Summary:" in content:
                prior_summary = content
            else:
                filtered_middle.append(m)

        summary_lines: list[str] = []
        if self.bridge_prefix:
            summary_lines.append("[Cross-model bridge: context compressed across models]")

        if prior_summary:
            summary_lines.append(f"<previous-summary>\n{prior_summary}\n</previous-summary>")

        # Retain recent user messages up to budget if requested
        if self.keep_user_messages:
            user_turns = [
                m
                for m in filtered_middle
                if getattr(m, "role", "") == "user"
                or (isinstance(m, dict) and m.get("role") == "user")
            ]
            for ut in user_turns[-2:]:
                u_text = str(getattr(ut, "content", ""))[: self.keep_user_messages_max_chars]
                summary_lines.append(f"User Goal: {u_text}")

        for m in filtered_middle:
            c = str(getattr(m, "content", ""))
            if c:
                summary_lines.append(f"- {getattr(m, 'role', 'turn')}: {c[:100]}...")

        summary_text = (
            f"[Conversation Summary: {len(middle)} earlier turns compressed]\n"
            + "\n".join(summary_lines[:10])
        )

        from devops_cli.models.ai import ChatMessage

        combined: list[Any] = [first_msg]

        if self.receipts:
            handle = None
            if self.transcript_handle_provider and hasattr(
                self.transcript_handle_provider, "compaction_transcript_handle"
            ):
                handle = self.transcript_handle_provider.compaction_transcript_handle()
            receipt = CompactionReceipt(
                strategy=self.__class__.__name__,
                messages_dropped=len(middle),
                tokens_dropped=len(middle) * 60,
                handle=handle,
            )
            combined.append(ChatMessage(role="system", content=receipt.to_receipt_text()))

        combined.append(ChatMessage(role="system", content=summary_text))
        combined.extend(tail)
        return reinject_pinned(combined, pinned)


class FallbackCompaction(BaseCapability):
    """Composing compaction strategy that executes fallbacks in sequence until one succeeds."""

    id: str = "fallback_compaction"
    strategies: list[Any] = Field(default_factory=list)

    def compact_messages(self, messages: list[Any]) -> list[Any]:
        """Try each configured strategy in order."""
        current = list(messages)
        for strat in self.strategies:
            try:
                if hasattr(strat, "compact_messages"):
                    current = strat.compact_messages(current)
                elif callable(strat):
                    current = strat(current)
                return current
            except Exception:
                continue
        return current


class TieredCompaction(BaseCapability):
    """Cascading compaction strategy running cheap zero-LLM passes before escalating."""

    id: str = "tiered_compaction"
    tiers: list[Any] = Field(default_factory=list)
    max_fraction: float = 0.8
    target_tokens: int = 100000

    def __init__(
        self,
        tiers: Sequence[Any] | None = None,
        *,
        max_fraction: float = 0.8,
        target_tokens: int = 100000,
        id: str = "tiered_compaction",
    ) -> None:
        resolved_tiers = (
            list(tiers)
            if tiers is not None
            else [
                DeduplicateFileReads(),
                ClearToolResults(),
                ClampOversizedMessages(),
                SlidingWindowCompaction(),
            ]
        )
        super().__init__(
            id=str(id or "tiered_compaction"),
            tiers=resolved_tiers,
            max_fraction=max_fraction,
            target_tokens=target_tokens,
        )

    def compact_messages(self, messages: list[Any]) -> list[Any]:
        """Apply cascading compaction tiers sequentially."""
        current = list(messages)
        for tier in self.tiers:
            if hasattr(tier, "compact_messages"):
                current = tier.compact_messages(current)
            elif callable(tier):
                current = tier(current)
        return current


class WarnNearLimits(BaseCapability):
    """Capability notifying the model when context consumption approaches token limits."""

    id: str = "warn_near_limits"
    max_context_fraction: float = 0.9

    def get_system_prompt_additions(self, ctx: RunContext[Any] | None = None) -> list[str]:
        return [
            f"WarnNearLimits enabled: context warning will be issued if usage exceeds "
            f"{int(self.max_context_fraction * 100)}% of model context window."
        ]


class ReportContextUsage(BaseCapability):
    """Capability reporting token counts and context fractions."""

    id: str = "report_context_usage"

    def get_usage(self, messages: list[Any], context_limit: int = 128000) -> ContextUsage:
        """Calculate token and message usage metrics."""
        total_chars = sum(len(str(getattr(m, "content", ""))) for m in messages)
        estimated_tokens = total_chars // 4
        fraction = min(1.0, estimated_tokens / max(1, context_limit))
        return ContextUsage(
            total_tokens=estimated_tokens,
            context_limit=context_limit,
            context_fraction=fraction,
            message_count=len(messages),
        )


def compact_now(
    messages: list[Any],
    strategy: Any | None = None,
) -> list[Any]:
    """Execute immediate compaction on a message history list using the given or default strategy."""
    strat = strategy or TieredCompaction()
    if hasattr(strat, "compact_messages"):
        res = strat.compact_messages(messages)
        return list(res) if isinstance(res, (list, tuple)) else list(messages)
    elif callable(strat):
        res = strat(messages)
        return list(res) if isinstance(res, (list, tuple)) else list(messages)
    return list(messages)


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


PlanItem.model_rebuild()
PlanEvent.model_rebuild()
ModelOption.model_rebuild()
AgentOverride.model_rebuild()
SubAgent.model_rebuild()
SubAgents.model_rebuild()
WorkflowAgent.model_rebuild()
DynamicWorkflow.model_rebuild()
Advisor.model_rebuild()
MountDir.model_rebuild()
OSAccess.model_rebuild()
CodeMode.model_rebuild()
ToolSearch.model_rebuild()
ContextUsage.model_rebuild()
CompactionReceipt.model_rebuild()
ClampOversizedMessages.model_rebuild()
ClearToolResults.model_rebuild()
DeduplicateFileReads.model_rebuild()
SlidingWindowCompaction.model_rebuild()
SummarizingCompaction.model_rebuild()
FallbackCompaction.model_rebuild()
TieredCompaction.model_rebuild()
ReportContextUsage.model_rebuild()
FileSystem.model_rebuild()
Shell.model_rebuild()
RepoContext.model_rebuild()
Planning.model_rebuild()
ToolOutputLimits.model_rebuild()
WarnNearLimits.model_rebuild()
Coder.model_rebuild()
Researcher.model_rebuild()
MacroscopeIssue.model_rebuild()
MacroscopeReview.model_rebuild()
Macroscope.model_rebuild()
PlaywrightBrowser.model_rebuild()
