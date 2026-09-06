"""Hierarchical and searchable persistent memory capability."""

from __future__ import annotations

import logging
import sqlite3
import time
import uuid
from collections.abc import Callable
from pathlib import Path
from typing import Any, Literal, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field

from devops_cli.ai.agents.pydantic_agent import (
    AgentTool,
    BaseCapability,
    RunContext,
    Tool,
)
from devops_cli.exceptions.ai import HarnessExecutionError, HarnessValidationError

logger = logging.getLogger(__name__)


class MemoryOperationConflictError(HarnessExecutionError):
    """Raised when an optimistic concurrency conflict or duplicate operation occurs in memory store."""


class MemoryFile(BaseModel):
    """A single notebook file in persistent memory."""

    model_config = ConfigDict(extra="ignore")

    path: str
    content: str
    version: str
    truncated: bool = False
    size_bytes: int = 0


class MemoryMutationResult(BaseModel):
    """Outcome of a memory write or mutation."""

    model_config = ConfigDict(extra="ignore")

    path: str
    version: str
    size_bytes: int
    status: str = "ok"


class MemorySearchResult(BaseModel):
    """Matched snippet from a memory search."""

    model_config = ConfigDict(extra="ignore")

    path: str
    snippet: str
    score: float = 0.0


@runtime_checkable
class MemoryStore(Protocol):
    """Protocol for persistent agent memory stores."""

    def read(self, path: str, max_chars: int = 65536) -> MemoryFile: ...

    def write(
        self,
        path: str,
        content: str,
        mode: Literal["append", "replace"] = "append",
        target_fragment: str | None = None,
        replacement: str | None = None,
        expected_version: str | None = None,
        operation_id: str | None = None,
    ) -> MemoryMutationResult: ...

    def delete(self, path: str, expected_version: str | None = None) -> bool: ...

    def list_paths(self, prefix: str = "", limit: int = 100) -> list[str]: ...


@runtime_checkable
class SearchableMemoryStore(MemoryStore, Protocol):
    """Memory store supporting fast text search."""

    def search(
        self,
        query: str,
        max_results: int = 10,
        max_result_chars: int = 4000,
        max_file_chars: int = 65536,
    ) -> list[MemorySearchResult]: ...


class InMemoryStore(BaseModel):
    """Process-lifetime in-memory notebook store with optimistic concurrency."""

    model_config = ConfigDict(extra="ignore")

    files: dict[str, MemoryFile] = Field(default_factory=dict)
    operations: set[str] = Field(default_factory=set)

    def read(self, path: str, max_chars: int = 65536) -> MemoryFile:
        clean = path.strip().lstrip("/")
        if clean not in self.files:
            return MemoryFile(path=clean, content="", version="0", size_bytes=0)
        f = self.files[clean]
        if len(f.content) > max_chars:
            return MemoryFile(
                path=clean,
                content=f.content[:max_chars],
                version=f.version,
                truncated=True,
                size_bytes=len(f.content),
            )
        return f

    def write(
        self,
        path: str,
        content: str,
        mode: Literal["append", "replace"] = "append",
        target_fragment: str | None = None,
        replacement: str | None = None,
        expected_version: str | None = None,
        operation_id: str | None = None,
    ) -> MemoryMutationResult:
        if operation_id and operation_id in self.operations:
            f = self.read(path)
            return MemoryMutationResult(
                path=f.path, version=f.version, size_bytes=f.size_bytes, status="idempotent_replay"
            )

        clean = path.strip().lstrip("/")
        existing = self.files.get(clean)
        if expected_version is not None and existing and existing.version != expected_version:
            raise MemoryOperationConflictError(
                f"Version mismatch on '{clean}': expected {expected_version}, got {existing.version}"
            )

        new_content = ""
        if mode == "replace" and target_fragment is not None:
            base = existing.content if existing else ""
            if target_fragment not in base:
                raise HarnessValidationError(f"Target fragment not found in memory file '{clean}'")
            new_content = base.replace(target_fragment, replacement or "", 1)
        elif mode == "replace":
            new_content = content
        else:
            base = existing.content if existing else ""
            new_content = f"{base}\n{content}".strip() if base else content

        new_version = uuid.uuid4().hex[:12]
        mf = MemoryFile(
            path=clean,
            content=new_content,
            version=new_version,
            size_bytes=len(new_content.encode("utf-8")),
        )
        self.files[clean] = mf
        if operation_id:
            self.operations.add(operation_id)
        return MemoryMutationResult(
            path=clean, version=new_version, size_bytes=mf.size_bytes, status="ok"
        )

    def delete(self, path: str, expected_version: str | None = None) -> bool:
        clean = path.strip().lstrip("/")
        if clean in self.files:
            if expected_version and self.files[clean].version != expected_version:
                raise MemoryOperationConflictError(f"Version mismatch on delete of '{clean}'")
            del self.files[clean]
            return True
        return False

    def list_paths(self, prefix: str = "", limit: int = 100) -> list[str]:
        clean_prefix = prefix.strip().lstrip("/")
        matches = [p for p in sorted(self.files.keys()) if p.startswith(clean_prefix)]
        return matches[:limit]

    def search(
        self,
        query: str,
        max_results: int = 10,
        max_result_chars: int = 4000,
        max_file_chars: int = 65536,
    ) -> list[MemorySearchResult]:
        q = query.strip().lower()
        if not q:
            return []
        terms = list(dict.fromkeys(q.split()))[:32]
        results: list[MemorySearchResult] = []
        total_chars = 0

        for path, mf in self.files.items():
            content_lower = mf.content[:max_file_chars].lower()
            score = sum(content_lower.count(t) for t in terms)
            if any(t in path.lower() for t in terms):
                score += 5
            if score > 0:
                snippet = mf.content[: min(300, max_result_chars)]
                results.append(MemorySearchResult(path=path, snippet=snippet, score=float(score)))
                total_chars += len(path) + len(snippet)
                if len(results) >= max_results or total_chars >= max_result_chars:
                    break

        results.sort(key=lambda r: r.score, reverse=True)
        return results[:max_results]


class FileStore(BaseModel):
    """Filesystem-backed memory notebook store with atomic writes and directory containment."""

    model_config = ConfigDict(extra="ignore")

    directory: Path = Field(default_factory=lambda: Path(".agent-memory"))

    def __init__(self, directory: Path | str = ".agent-memory") -> None:
        p = Path(directory)
        super().__init__(directory=p)
        self.directory.mkdir(parents=True, exist_ok=True)

    def _resolve_path(self, path: str) -> Path:
        clean = path.strip().lstrip("/")
        target = (self.directory / clean).resolve()
        if not target.is_relative_to(self.directory.resolve()):
            raise PermissionError(f"Path traversal attempted in memory path: {path}")
        return target

    def read(self, path: str, max_chars: int = 65536) -> MemoryFile:
        p = self._resolve_path(path)
        if not p.exists() or not p.is_file():
            return MemoryFile(path=path, content="", version="0", size_bytes=0)
        text = p.read_text(encoding="utf-8")
        version = str(int(p.stat().st_mtime_ns))
        if len(text) > max_chars:
            return MemoryFile(
                path=path,
                content=text[:max_chars],
                version=version,
                truncated=True,
                size_bytes=len(text.encode("utf-8")),
            )
        return MemoryFile(
            path=path, content=text, version=version, size_bytes=len(text.encode("utf-8"))
        )

    def write(
        self,
        path: str,
        content: str,
        mode: Literal["append", "replace"] = "append",
        target_fragment: str | None = None,
        replacement: str | None = None,
        expected_version: str | None = None,
        operation_id: str | None = None,
    ) -> MemoryMutationResult:
        p = self._resolve_path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        existing_text = p.read_text(encoding="utf-8") if p.exists() else ""
        if expected_version is not None and p.exists():
            curr_v = str(int(p.stat().st_mtime_ns))
            if curr_v != expected_version:
                raise MemoryOperationConflictError(
                    f"Version mismatch on '{path}': expected {expected_version}, got {curr_v}"
                )

        if mode == "replace" and target_fragment is not None:
            if target_fragment not in existing_text:
                raise HarnessValidationError(f"Target fragment not found in memory file '{path}'")
            new_text = existing_text.replace(target_fragment, replacement or "", 1)
        elif mode == "replace":
            new_text = content
        else:
            new_text = f"{existing_text}\n{content}".strip() if existing_text else content

        p.write_text(new_text, encoding="utf-8")
        new_version = str(int(p.stat().st_mtime_ns))
        return MemoryMutationResult(
            path=path, version=new_version, size_bytes=len(new_text.encode("utf-8")), status="ok"
        )

    def delete(self, path: str, expected_version: str | None = None) -> bool:
        p = self._resolve_path(path)
        if p.exists() and p.is_file():
            if expected_version is not None:
                curr_v = str(int(p.stat().st_mtime_ns))
                if curr_v != expected_version:
                    raise MemoryOperationConflictError(f"Version mismatch on delete of '{path}'")
            p.unlink()
            return True
        return False

    def list_paths(self, prefix: str = "", limit: int = 100) -> list[str]:
        if not self.directory.exists():
            return []
        found: list[str] = []
        for item in sorted(self.directory.rglob("*")):
            if item.is_file() and not item.name.startswith("."):
                rel = str(item.relative_to(self.directory))
                if rel.startswith(prefix):
                    found.append(rel)
        return found[:limit]

    def search(
        self,
        query: str,
        max_results: int = 10,
        max_result_chars: int = 4000,
        max_file_chars: int = 65536,
    ) -> list[MemorySearchResult]:
        q = query.strip().lower()
        if not q:
            return []
        terms = list(dict.fromkeys(q.split()))[:32]
        results: list[MemorySearchResult] = []
        total_chars = 0

        for path in self.list_paths(limit=1000):
            mf = self.read(path, max_chars=max_file_chars)
            content_lower = mf.content.lower()
            score = sum(content_lower.count(t) for t in terms)
            if any(t in path.lower() for t in terms):
                score += 5
            if score > 0:
                snippet = mf.content[: min(300, max_result_chars)]
                results.append(MemorySearchResult(path=path, snippet=snippet, score=float(score)))
                total_chars += len(path) + len(snippet)
                if len(results) >= max_results or total_chars >= max_result_chars:
                    break

        results.sort(key=lambda r: r.score, reverse=True)
        return results[:max_results]


class SqliteMemoryStore(BaseModel):
    """Durable SQLite database-backed memory notebook store."""

    model_config = ConfigDict(extra="ignore")

    database: str = Field(default=":memory:")

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.database, check_same_thread=False)
        conn.execute(
            "CREATE TABLE IF NOT EXISTS memory_files (path TEXT PRIMARY KEY, content TEXT, version TEXT, updated_at REAL)"
        )
        return conn

    def read(self, path: str, max_chars: int = 65536) -> MemoryFile:
        clean = path.strip().lstrip("/")
        conn = self._get_conn()
        try:
            cur = conn.execute("SELECT content, version FROM memory_files WHERE path = ?", (clean,))
            row = cur.fetchone()
            if not row:
                return MemoryFile(path=clean, content="", version="0", size_bytes=0)
            content, version = row[0], row[1]
            if len(content) > max_chars:
                return MemoryFile(
                    path=clean,
                    content=content[:max_chars],
                    version=version,
                    truncated=True,
                    size_bytes=len(content.encode("utf-8")),
                )
            return MemoryFile(
                path=clean,
                content=content,
                version=version,
                size_bytes=len(content.encode("utf-8")),
            )
        finally:
            conn.close()

    def write(
        self,
        path: str,
        content: str,
        mode: Literal["append", "replace"] = "append",
        target_fragment: str | None = None,
        replacement: str | None = None,
        expected_version: str | None = None,
        operation_id: str | None = None,
    ) -> MemoryMutationResult:
        clean = path.strip().lstrip("/")
        conn = self._get_conn()
        try:
            cur = conn.execute("SELECT content, version FROM memory_files WHERE path = ?", (clean,))
            row = cur.fetchone()
            existing = row[0] if row else ""
            curr_v = row[1] if row else None
            if expected_version is not None and curr_v != expected_version:
                raise MemoryOperationConflictError(
                    f"Version mismatch on '{clean}': expected {expected_version}, got {curr_v}"
                )

            if mode == "replace" and target_fragment is not None:
                if target_fragment not in existing:
                    raise HarnessValidationError(
                        f"Target fragment not found in memory file '{clean}'"
                    )
                new_text = existing.replace(target_fragment, replacement or "", 1)
            elif mode == "replace":
                new_text = content
            else:
                new_text = f"{existing}\n{content}".strip() if existing else content

            new_v = uuid.uuid4().hex[:12]
            now = time.time()
            conn.execute(
                "INSERT OR REPLACE INTO memory_files (path, content, version, updated_at) VALUES (?, ?, ?, ?)",
                (clean, new_text, new_v, now),
            )
            conn.commit()
            return MemoryMutationResult(
                path=clean, version=new_v, size_bytes=len(new_text.encode("utf-8")), status="ok"
            )
        finally:
            conn.close()

    def delete(self, path: str, expected_version: str | None = None) -> bool:
        clean = path.strip().lstrip("/")
        conn = self._get_conn()
        try:
            if expected_version is not None:
                cur = conn.execute("SELECT version FROM memory_files WHERE path = ?", (clean,))
                row = cur.fetchone()
                if row and row[0] != expected_version:
                    raise MemoryOperationConflictError(f"Version mismatch on delete of '{clean}'")
            cur = conn.execute("DELETE FROM memory_files WHERE path = ?", (clean,))
            conn.commit()
            return cur.rowcount > 0
        finally:
            conn.close()

    def list_paths(self, prefix: str = "", limit: int = 100) -> list[str]:
        clean = prefix.strip().lstrip("/")
        conn = self._get_conn()
        try:
            cur = conn.execute(
                "SELECT path FROM memory_files WHERE path LIKE ? ORDER BY path LIMIT ?",
                (f"{clean}%", limit),
            )
            return [r[0] for r in cur.fetchall()]
        finally:
            conn.close()

    def search(
        self,
        query: str,
        max_results: int = 10,
        max_result_chars: int = 4000,
        max_file_chars: int = 65536,
    ) -> list[MemorySearchResult]:
        q = query.strip().lower()
        if not q:
            return []
        terms = list(dict.fromkeys(q.split()))[:32]
        conn = self._get_conn()
        try:
            cur = conn.execute("SELECT path, content FROM memory_files")
            results: list[MemorySearchResult] = []
            total_chars = 0
            for path, content in cur.fetchall():
                content_lower = (content or "")[:max_file_chars].lower()
                score = sum(content_lower.count(t) for t in terms)
                if any(t in path.lower() for t in terms):
                    score += 5
                if score <= 0:
                    continue
                snippet = (content or "")[: min(300, max_result_chars)]
                results.append(MemorySearchResult(path=path, snippet=snippet, score=float(score)))
                total_chars += len(path) + len(snippet)
                if len(results) >= max_results or total_chars >= max_result_chars:
                    break
            results.sort(key=lambda r: r.score, reverse=True)
            return results[:max_results]
        finally:
            conn.close()


class Memory(BaseCapability):
    """Persistent, namespaced agent notebook capability with bounded prompt injection and search."""

    id: str = "memory"
    store: Any = Field(default_factory=InMemoryStore)
    store_resolver: Any = None
    agent_name: str = "main"
    heading: str = ""
    namespace: Any = ""
    inject_memory: bool = True
    max_tokens: int = 2000
    max_lines: int = 200
    max_memory_size: int = 65536
    max_search_results: int = 10
    max_search_result_chars: int = 4000
    max_search_files: int = 1000
    injection_errors: Literal["ignore", "raise"] = "ignore"
    guidance: str | None = None
    tool_prefix: str = ""

    def __init__(
        self,
        store: Any = None,
        *,
        store_resolver: Any = None,
        agent_name: str = "main",
        heading: str = "",
        namespace: Any = "",
        inject_memory: bool = True,
        max_tokens: int = 2000,
        max_lines: int = 200,
        max_memory_size: int = 65536,
        max_search_results: int = 10,
        max_search_result_chars: int = 4000,
        max_search_files: int = 1000,
        injection_errors: Literal["ignore", "raise"] = "ignore",
        guidance: str | None = None,
        tool_prefix: str = "",
        id: str = "memory",
    ) -> None:
        resolved_store = store if store is not None else InMemoryStore()
        super().__init__(
            id=str(id or "memory"),
            store=resolved_store,
            store_resolver=store_resolver,
            agent_name=agent_name,
            heading=heading,
            namespace=namespace,
            inject_memory=inject_memory,
            max_tokens=max_tokens,
            max_lines=max_lines,
            max_memory_size=max_memory_size,
            max_search_results=max_search_results,
            max_search_result_chars=max_search_result_chars,
            max_search_files=max_search_files,
            injection_errors=injection_errors,
            guidance=guidance,
            tool_prefix=tool_prefix,
        )

    def prefix_tools(self, prefix: str) -> Memory:  # type: ignore[override]
        """Return a copy of this Memory capability with prefixed tool names."""
        return Memory(
            store=self.store,
            store_resolver=self.store_resolver,
            agent_name=self.agent_name,
            heading=self.heading,
            namespace=self.namespace,
            inject_memory=self.inject_memory,
            max_tokens=self.max_tokens,
            max_lines=self.max_lines,
            max_memory_size=self.max_memory_size,
            max_search_results=self.max_search_results,
            max_search_result_chars=self.max_search_result_chars,
            max_search_files=self.max_search_files,
            injection_errors=self.injection_errors,
            guidance=self.guidance,
            tool_prefix=prefix,
            id=f"{self.id}_{prefix}",
        )

    def _get_active_store(self, ctx: RunContext[Any] | None = None) -> Any:
        if self.store_resolver and ctx is not None:
            try:
                return self.store_resolver(ctx)
            except Exception:
                if self.injection_errors == "raise":
                    raise
        return self.store

    def get_system_prompt_additions(self, ctx: RunContext[Any] | None = None) -> list[str]:
        additions: list[str] = []
        heading_text = f"## {self.heading}\n\n" if self.heading else ""
        guidance = self.guidance or (
            "You have access to a persistent memory notebook across sessions. "
            "Use write_memory to record notes, read_memory to view notebooks, and search_memory to retrieve context."
        )
        additions.append(f"{heading_text}{guidance}")

        if self.inject_memory:
            try:
                active_store = self._get_active_store(ctx)
                mem_file = active_store.read("MEMORY.md", max_chars=self.max_memory_size)
                other_paths = [
                    p
                    for p in active_store.list_paths(limit=self.max_search_files)
                    if p != "MEMORY.md"
                ]
                lines = mem_file.content.splitlines()[: self.max_lines]
                content_excerpt = "\n".join(lines)

                listing = f"\nOther memory notes: {', '.join(other_paths)}" if other_paths else ""
                memory_block = f"<memory>\n{content_excerpt}{listing}\n</memory>"
                additions.append(memory_block)
            except Exception:
                if self.injection_errors == "raise":
                    raise
        return additions

    def get_tools(self) -> list[AgentTool | Callable[..., Any]]:
        prefix = f"{self.tool_prefix}_" if self.tool_prefix else ""
        store = self.store

        def write_memory(
            path: str = "MEMORY.md",
            content: str = "",
            mode: str = "append",
            target_fragment: str | None = None,
            replacement: str | None = None,
        ) -> str:
            """Write or append text notes to a memory file, or replace a unique text fragment."""
            try:
                res = store.write(
                    path=path,
                    content=content,
                    mode="replace" if mode == "replace" else "append",
                    target_fragment=target_fragment,
                    replacement=replacement,
                )
                return f"Memory updated: '{res.path}' (version: {res.version}, size: {res.size_bytes} bytes)"
            except Exception as e:
                return f"Error writing to memory '{path}': {e}"

        def read_memory(path: str = "MEMORY.md", max_chars: int = 65536) -> str:
            """Read a bounded prefix of a memory notebook file."""
            try:
                clamped = min(max(1, max_chars), self.max_memory_size)
                f = store.read(path, max_chars=clamped)
                trunc_note = " [truncated]" if f.truncated else ""
                return f"--- {f.path} (v{f.version}){trunc_note} ---\n{f.content}"
            except Exception as e:
                return f"Error reading memory '{path}': {e}"

        def delete_memory(path: str) -> str:
            """Delete a memory file. The main notebook MEMORY.md is protected."""
            clean = path.strip().lstrip("/")
            if clean == "MEMORY.md":
                return "Error: Cannot delete protected root notebook MEMORY.md"
            try:
                ok = store.delete(clean)
                return f"Deleted memory '{clean}'" if ok else f"Memory '{clean}' not found"
            except Exception as e:
                return f"Error deleting memory '{path}': {e}"

        def search_memory(query: str, max_results: int = 10) -> str:
            """Search across persistent memory notebook files."""
            try:
                clamped_k = min(max(1, max_results), self.max_search_results)
                search_fn = getattr(store, "search", None)
                if not callable(search_fn):
                    return f"No memory entries matching query '{query}'."
                matches = search_fn(
                    query=query,
                    max_results=clamped_k,
                    max_result_chars=self.max_search_result_chars,
                    max_file_chars=self.max_memory_size,
                )
                if not matches:
                    return f"No memory entries matching query '{query}'."
                lines = [f"Found {len(matches)} memory match(es):"]
                lines.extend(f"- **{m.path}** (score: {m.score:.1f}): {m.snippet}" for m in matches)
                return "\n".join(lines)
            except Exception as e:
                return f"Error searching memory: {e}"

        return [
            Tool.from_function(
                write_memory,
                name=f"{prefix}write_memory",
                description="Append to or replace content in persistent memory notebooks.",
            ),
            Tool.from_function(
                read_memory,
                name=f"{prefix}read_memory",
                description="Read content from a persistent memory notebook file.",
            ),
            Tool.from_function(
                delete_memory,
                name=f"{prefix}delete_memory",
                description="Delete a non-root memory note from persistent storage.",
            ),
            Tool.from_function(
                search_memory,
                name=f"{prefix}search_memory",
                description="Search across notebook files in persistent memory.",
            ),
        ]
