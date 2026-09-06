"""FileSystem capability for safe, sandboxed file operations."""

from __future__ import annotations

import fnmatch
import hashlib
import logging
import re
from collections.abc import Callable
from pathlib import Path
from typing import Any

from pydantic import Field

from devops_cli.ai.agents.pydantic_agent import AgentTool, BaseCapability, RunContext, Tool
from devops_cli.ai.harness.constants import DEFAULT_PROTECTED_PATTERNS

logger = logging.getLogger(__name__)


def _search_single_file_lines(
    p: Path,
    rel: str,
    pattern_re: re.Pattern[str],
    results: list[str],
    max_results: int,
) -> bool:
    """Search lines of a single file for regex pattern. Returns True if max_results reached."""
    try:
        text = p.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return False

    for i, line in enumerate(text.splitlines(), start=1):
        if not pattern_re.search(line):
            continue
        results.append(f"{rel}:{i}: {line.strip()}")
        if len(results) >= max_results:
            results.append(f"[... truncated at {max_results} results ...]")
            return True
    return False


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
        if not resolved.is_relative_to(root_res):
            raise PermissionError(f"Access denied: path '{rel_path}' is outside root '{self.root}'")
        return resolved

    def _matches_pattern(self, rel_path: str, patterns: list[str]) -> bool:

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
        """Compute full SHA-256 hash for strong collision-resistant optimistic concurrency."""
        data = content.encode("utf-8") if isinstance(content, str) else content
        return hashlib.sha256(data).hexdigest()

    def _read_file(self, path: str, offset: int = 1, limit: int | None = None) -> str:
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
        header = (
            f"# File: {path} (sha256:{c_hash}, lines {start_idx + 1}-{end_idx} of {len(lines)})\n"
        )
        return header + "\n".join(numbered)

    def _write_file(self, path: str, content: str, expected_hash: str | None = None) -> str:
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

    def _edit_file(
        self, path: str, old_text: str, new_text: str, expected_hash: str | None = None
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

    def _list_directory(self, path: str = ".") -> str:
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

    def _find_files(self, pattern: str, path: str = ".") -> str:
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

    def _search_files(self, query: str, path: str = ".", include_glob: str | None = None) -> str:
        """Regex or text search across file contents."""
        safe_p = self._resolve_safe_path(path)
        if not safe_p.is_dir():
            return f"Error: not a directory: {path}"

        try:
            pattern_re = re.compile(query, re.IGNORECASE)
        except re.error as e:
            return f"Error: Invalid regular expression '{query}': {e}"

        results: list[str] = []
        for p in sorted(safe_p.rglob(include_glob or "*")):
            if not p.is_file() or any(
                part.startswith(".") for part in p.relative_to(self.root).parts
            ):
                continue
            rel = str(p.relative_to(self.root))
            if self.denied_patterns and self._matches_pattern(rel, self.denied_patterns):
                continue
            if _search_single_file_lines(p, rel, pattern_re, results, self.max_search_results):
                return "\n".join(results)

        return "\n".join(results) or f"No matches found for query '{query}'."

    def _create_directory(self, path: str) -> str:
        """Create a directory and any missing parent folders."""
        ok, err = self._is_accessible(path, for_write=True)
        if not ok:
            return f"Error: {err}"
        safe_p = self._resolve_safe_path(path)
        safe_p.mkdir(parents=True, exist_ok=True)
        return f"Directory '{path}' successfully created."

    def _file_info(self, path: str) -> str:
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
        lines_count = len(safe_p.read_text(encoding="utf-8", errors="replace").splitlines())
        return (
            f"File: {path}\n"
            f"Type: regular file\n"
            f"Size: {stat.st_size} bytes\n"
            f"Lines: {lines_count}\n"
            f"Modified: {stat.st_mtime}\n"
            f"sha256: {c_hash}"
        )

    def get_tools(self) -> list[AgentTool | Callable[..., Any]]:
        read_tools: list[AgentTool | Callable[..., Any]] = [
            Tool.from_function(
                self._read_file,
                name="read_file",
                description="Read file contents with line offset/limit.",
            ),
            Tool.from_function(
                self._list_directory, name="list_directory", description="List directory entries."
            ),
            Tool.from_function(
                self._find_files,
                name="find_files",
                description="Find files matching a glob pattern.",
            ),
            Tool.from_function(
                self._search_files,
                name="search_files",
                description="Search file contents by regex pattern.",
            ),
            Tool.from_function(
                self._file_info,
                name="file_info",
                description="Retrieve metadata and hash for a file or directory.",
            ),
        ]

        if self.read_only:
            return read_tools

        write_tools: list[AgentTool | Callable[..., Any]] = [
            Tool.from_function(
                self._write_file,
                name="write_file",
                description="Create or overwrite a file with optimistic concurrency validation.",
            ),
            Tool.from_function(
                self._edit_file,
                name="edit_file",
                description="Exact-string replacement within an existing file.",
            ),
            Tool.from_function(
                self._create_directory,
                name="create_directory",
                description="Create a directory and any missing parent folders.",
            ),
        ]
        return [*read_tools, *write_tools]

    def get_system_prompt_additions(self, ctx: RunContext[Any] | None = None) -> list[str]:
        mode = "read-only" if self.read_only else "read-write"
        return [f"Workspace FileSystem capability enabled ({mode}) rooted at {self.root}."]
