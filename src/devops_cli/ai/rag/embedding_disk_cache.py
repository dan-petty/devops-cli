"""The disk tier of the embedding cache: vectors that stay between two runs of the CLI (#4447).

On a workstation, no Valkey answers at the default `valkey.url`, and the memory tier of each
process starts empty. Thus each intake run sent all texts of its comparison set to the embedding
model again. This tier keeps the vectors in one SQLite file under the data directory, through the
stdlib `sqlite3`, so the next run sends only the texts that changed.

- A row has a model key and the SHA-256 of the text that the model gets, after the task prefix
  of the model. The engine makes the key from the provider and the model name that the request
  sends. Thus a changed text, another model or another provider is a miss.
- The file records one vector length for each model key. A row of another length is a miss, and
  a write of vectors of a new length removes the rows of the old length (#4546).
- A row holds the vector as IEEE 754 doubles in the byte order of the machine, so a hit gives the
  floats of the reply with no change.
- A hit sets the time of last use of its row. Each write removes the rows that no run used for
  `DEFAULT_RAG_EMBEDDING_DISK_CACHE_IDLE_SECONDS`, so the file holds the texts that runs ask for.
- The tier is a cache only. A row that is not a vector of the recorded length is a miss, and the
  vector that the model then gives replaces it. When the file cannot be opened, read or written,
  the tier logs one warning that names the file, and it is off for the rest of the life of the
  object. Each text then goes to the model.
"""

from __future__ import annotations

import contextlib
import hashlib
import logging
import sqlite3
import threading
import time
from array import array
from collections.abc import Iterator, Sequence
from pathlib import Path

from devops_cli.config.defaults import (
    DEFAULT_RAG_EMBEDDING_DISK_CACHE_FILENAME,
    DEFAULT_RAG_EMBEDDING_DISK_CACHE_IDLE_SECONDS,
)

logger = logging.getLogger(__name__)

_CREATE_TABLE = (
    "CREATE TABLE IF NOT EXISTS embeddings ("
    "model TEXT NOT NULL, text_sha256 TEXT NOT NULL, vector BLOB NOT NULL, used_at REAL NOT NULL, "
    "PRIMARY KEY (model, text_sha256)) WITHOUT ROWID"
)
_CREATE_INDEX = "CREATE INDEX IF NOT EXISTS embeddings_used_at ON embeddings (used_at)"
_CREATE_DIMENSIONS = (
    "CREATE TABLE IF NOT EXISTS dimensions (model TEXT PRIMARY KEY, dimension INTEGER NOT NULL)"
)
_SELECT_DIMENSION = "SELECT dimension FROM dimensions WHERE model = ?"
_SET_DIMENSION = "INSERT OR REPLACE INTO dimensions (model, dimension) VALUES (?, ?)"
_DROP_MODEL = "DELETE FROM embeddings WHERE model = ?"
_SELECT = "SELECT vector FROM embeddings WHERE model = ? AND text_sha256 = ?"
_UPSERT = (
    "INSERT OR REPLACE INTO embeddings (model, text_sha256, vector, used_at) VALUES (?, ?, ?, ?)"
)
_TOUCH = "UPDATE embeddings SET used_at = ? WHERE model = ? AND text_sha256 = ?"
_PRUNE = "DELETE FROM embeddings WHERE used_at < ?"
_BUSY_TIMEOUT_SECONDS = 10.0
_DOUBLE_SIZE = array("d").itemsize
# The switch to WAL needs an exclusive lock that SQLite refuses at once, so the threads of one
# process make it one at a time, as the spend ledger does (#1820).
_SETUP_LOCK = threading.Lock()


def _digest(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def _blob(conn: sqlite3.Connection, model: str, digest: str) -> object:
    """The stored value of the vector of `digest`; None when the file holds no such row."""
    row = conn.execute(_SELECT, (model, digest)).fetchone()
    return None if row is None else row[0]


def _dimension(conn: sqlite3.Connection, model: str) -> int | None:
    """The recorded vector length of `model`; None when the file records none."""
    row = conn.execute(_SELECT_DIMENSION, (model,)).fetchone()
    return None if row is None else int(row[0])


def _vector(blob: object, dimension: int) -> list[float] | None:
    """The vector in `blob`; None for a value that is not an array of `dimension` doubles."""
    if not isinstance(blob, bytes) or len(blob) != dimension * _DOUBLE_SIZE:
        return None
    values = array("d")
    values.frombytes(blob)
    return values.tolist()


class EmbeddingDiskCache:
    """The vector of each model key and text, kept in the SQLite file at `path`."""

    def __init__(
        self, path: Path, *, idle_seconds: float = DEFAULT_RAG_EMBEDDING_DISK_CACHE_IDLE_SECONDS
    ) -> None:
        self.path = path
        self._idle_seconds = idle_seconds
        self._ready = False
        self._off = False

    def get_many(self, model: str, texts: Sequence[str]) -> list[list[float] | None]:
        """The vector of each text in turn: None for a text that the file does not hold.

        Only a row of the recorded length of `model` is a hit.
        """
        if self._off or not texts:
            return [None] * len(texts)
        digests = [_digest(text) for text in texts]
        try:
            with self._connection() as conn:
                dimension = _dimension(conn, model)
                found = {
                    digest: vector
                    for digest in set(digests)
                    if dimension is not None
                    and (vector := _vector(_blob(conn, model, digest), dimension)) is not None
                }
                now = time.time()
                conn.executemany(_TOUCH, [(now, model, digest) for digest in found])
        except (sqlite3.Error, OSError) as exc:
            self._turn_off(exc)
            return [None] * len(texts)
        return [found.get(digest) for digest in digests]

    def put_many(self, model: str, entries: Sequence[tuple[str, list[float]]]) -> None:
        """Keep the vector of each text, then remove the rows that no run used for the idle time.

        The length of the first vector becomes the recorded length of `model`: a vector of another
        length is not kept, and a new length removes the rows of the old one.
        """
        dimension = len(entries[0][1]) if entries else 0
        if self._off or not dimension:
            return
        now = time.time()
        rows = [
            (model, _digest(text), array("d", vector).tobytes(), now)
            for text, vector in entries
            if len(vector) == dimension
        ]
        try:
            with self._connection() as conn:
                if _dimension(conn, model) != dimension:
                    conn.execute(_DROP_MODEL, (model,))
                    conn.execute(_SET_DIMENSION, (model, dimension))
                conn.executemany(_UPSERT, rows)
                conn.execute(_PRUNE, (now - self._idle_seconds,))
        except (sqlite3.Error, OSError) as exc:
            self._turn_off(exc)

    @contextlib.contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        """A connection in one transaction, which commits when the block ends with no error."""
        if not self._ready:
            self.path.parent.mkdir(parents=True, exist_ok=True)
        with (
            contextlib.closing(sqlite3.connect(self.path, timeout=_BUSY_TIMEOUT_SECONDS)) as conn,
            conn,
        ):
            if not self._ready:
                self._set_up(conn)
            yield conn

    def _set_up(self, conn: sqlite3.Connection) -> None:
        with _SETUP_LOCK:
            if conn.execute("PRAGMA journal_mode").fetchone()[0].lower() != "wal":
                conn.execute("PRAGMA journal_mode=WAL")
            conn.execute(_CREATE_TABLE)
            conn.execute(_CREATE_INDEX)
            conn.execute(_CREATE_DIMENSIONS)
        self._ready = True

    def _turn_off(self, exc: Exception) -> None:
        self._off = True
        logger.warning(
            "The embedding disk cache %s is off for this run, and each text goes to the model: %s",
            self.path,
            exc,
        )


def embedding_disk_cache() -> EmbeddingDiskCache:
    """The disk cache of embeddings under the configured data directory.

    The file is in the folder `ai` of the data directory, beside the spend ledger. A relative
    `data.dir` resolves as the spend ledger resolves it, so every worktree of a repository uses
    one file. The cache opens no file before its first lookup.
    """
    from devops_cli.config.settings import load_settings
    from devops_cli.core.repo import resolve_review_data_path

    folder = resolve_review_data_path(load_settings().data.dir) / "ai"
    return EmbeddingDiskCache(folder / DEFAULT_RAG_EMBEDDING_DISK_CACHE_FILENAME)
