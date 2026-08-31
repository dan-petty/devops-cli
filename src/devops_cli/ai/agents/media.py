"""Pydantic AI Media externalization and content-addressed binary storage capabilities."""

from __future__ import annotations

import hashlib
import sqlite3
from pathlib import Path
from typing import Any, Protocol, runtime_checkable
from urllib.parse import parse_qs, urlencode, urlparse

from pydantic import BaseModel, Field

from devops_cli.ai.agents.capabilities import BaseCapability
from devops_cli.ai.agents.context import AgentHooks, RunContext


class BinaryContent(BaseModel):
    """Raw binary payload (image, audio, document) with MIME type."""

    data: bytes
    media_type: str = "application/octet-stream"

    @property
    def sha256_hex(self) -> str:
        """Compute SHA256 hexadecimal digest of the raw bytes."""
        return hashlib.sha256(self.data).hexdigest()

    @property
    def uri(self) -> str:
        """Return canonical content-addressed URI."""
        params = urlencode({"media_type": self.media_type})
        return f"media+sha256://{self.sha256_hex}?{params}"


@runtime_checkable
class MediaStore(Protocol):
    """Storage backend protocol for content-addressed media storage."""

    def put(self, content: BinaryContent) -> str: ...
    def get(self, uri: str) -> BinaryContent | None: ...
    def delete(self, uri: str) -> bool: ...


class InMemoryMediaStore(BaseModel):
    """In-memory content-addressed media store."""

    storage: dict[str, BinaryContent] = Field(default_factory=dict)

    def put(self, content: BinaryContent) -> str:
        """Save binary content and return its canonical URI."""
        uri = content.uri
        self.storage[uri] = content
        return uri

    def get(self, uri: str) -> BinaryContent | None:
        """Retrieve binary content for a canonical URI."""
        return self.storage.get(uri)

    def delete(self, uri: str) -> bool:
        """Delete stored binary content."""
        return self.storage.pop(uri, None) is not None


class DiskMediaStore:
    """Filesystem-backed content-addressed media store."""

    def __init__(self, root_dir: str | Path) -> None:
        self.root_dir = Path(root_dir)
        self.root_dir.mkdir(parents=True, exist_ok=True)

    def put(self, content: BinaryContent) -> str:
        """Save binary content to disk keyed by SHA256 digest."""
        digest = content.sha256_hex
        file_path = self.root_dir / digest
        file_path.write_bytes(content.data)
        return content.uri

    def get(self, uri: str) -> BinaryContent | None:
        """Read binary content from disk for a canonical URI."""
        parsed = urlparse(uri)
        if parsed.scheme != "media+sha256":
            return None
        digest = parsed.netloc
        file_path = self.root_dir / digest
        if not file_path.exists():
            return None
        data = file_path.read_bytes()
        media_type = parse_qs(parsed.query).get("media_type", ["application/octet-stream"])[0]
        return BinaryContent(data=data, media_type=media_type)

    def delete(self, uri: str) -> bool:
        """Delete media file from disk."""
        parsed = urlparse(uri)
        if parsed.scheme != "media+sha256":
            return False
        digest = parsed.netloc
        file_path = self.root_dir / digest
        if file_path.exists():
            file_path.unlink()
            return True
        return False


class SqliteMediaStore:
    """SQLite-backed content-addressed media store."""

    def __init__(self, db_path: str = ":memory:") -> None:
        self.db_path = db_path
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._init_db()

    def _init_db(self) -> None:
        with self._conn:
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS media_store (
                    digest TEXT PRIMARY KEY,
                    media_type TEXT NOT NULL,
                    data BLOB NOT NULL
                )
                """
            )

    def put(self, content: BinaryContent) -> str:
        """Save binary content in SQLite."""
        digest = content.sha256_hex
        with self._conn:
            self._conn.execute(
                """
                INSERT OR REPLACE INTO media_store (digest, media_type, data)
                VALUES (?, ?, ?)
                """,
                (digest, content.media_type, content.data),
            )
        return content.uri

    def get(self, uri: str) -> BinaryContent | None:
        """Retrieve binary content from SQLite."""
        parsed = urlparse(uri)
        if parsed.scheme != "media+sha256":
            return None
        digest = parsed.netloc
        cur = self._conn.cursor()
        cur.execute("SELECT media_type, data FROM media_store WHERE digest = ?", (digest,))
        row = cur.fetchone()
        if not row:
            return None
        return BinaryContent(media_type=row[0], data=row[1])

    def delete(self, uri: str) -> bool:
        """Delete binary content from SQLite."""
        parsed = urlparse(uri)
        if parsed.scheme != "media+sha256":
            return False
        digest = parsed.netloc
        with self._conn:
            cur = self._conn.execute("DELETE FROM media_store WHERE digest = ?", (digest,))
            return bool(cur.rowcount > 0)


def externalize_media(data: Any, store: MediaStore) -> Any:
    """Recursively replace BinaryContent instances with their content-addressed URI strings."""
    if isinstance(data, BinaryContent):
        return store.put(data)
    elif isinstance(data, dict):
        return {k: externalize_media(v, store) for k, v in data.items()}
    elif isinstance(data, list):
        return [externalize_media(item, store) for item in data]
    return data


def restore_media(data: Any, store: MediaStore) -> Any:
    """Recursively resolve media+sha256:// URIs back to BinaryContent instances."""
    if isinstance(data, str) and data.startswith("media+sha256://"):
        content = store.get(data)
        return content if content is not None else data
    elif isinstance(data, dict):
        return {k: restore_media(v, store) for k, v in data.items()}
    elif isinstance(data, list):
        return [restore_media(item, store) for item in data]
    return data


class MediaExternalizer(BaseCapability):
    """Capability that offloads large binary data from agent messages into content-addressed storage."""

    id: str = "media"
    store: Any = Field(default_factory=InMemoryMediaStore)

    def externalize(self, data: Any) -> Any:
        """Externalize binary content within payload."""
        return externalize_media(data, self.store)

    def restore(self, data: Any) -> Any:
        """Restore externalized URIs back into binary content."""
        return restore_media(data, self.store)

    def get_hooks(self) -> AgentHooks | None:
        """Bind tool execution return externalization."""

        def after_tool(ctx: RunContext[Any], tool_name: str, result: Any) -> None:
            if isinstance(result, (BinaryContent, dict, list)):
                _ = self.externalize(result)

        return AgentHooks(after_tool_execute=[after_tool])


Media = MediaExternalizer
