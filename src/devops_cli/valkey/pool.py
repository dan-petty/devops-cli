"""Bounded Valkey connection pool with health checking and idle eviction.

Every cache read previously paid a TCP handshake plus an `AUTH` round trip, which
dominates the cost of the operation it was serving. Pooling amortises that setup across
callers so a cache hit costs one round trip rather than three.
"""

from __future__ import annotations

import logging
import threading
import time
from collections import deque
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any

from devops_cli.config.defaults import (
    DEFAULT_VALKEY_HOST,
    DEFAULT_VALKEY_POOL_IDLE_TIMEOUT_SECONDS,
    DEFAULT_VALKEY_POOL_MAX_SIZE,
    DEFAULT_VALKEY_PORT,
    DEFAULT_VALKEY_TIMEOUT_SECONDS,
)
from devops_cli.exceptions.valkey import ValkeyConnectionError, ValkeyError
from devops_cli.valkey.client import ValkeyClient

logger = logging.getLogger(__name__)


@dataclass
class PooledConnection:
    """A checked-in connection and the moment it was last returned to the pool."""

    client: ValkeyClient
    returned_at: float


@dataclass
class PoolStats:
    """Observability counters for pool behaviour."""

    created: int = 0
    reused: int = 0
    discarded: int = 0
    in_use: int = 0
    idle: int = 0

    @property
    def reuse_ratio(self) -> float:
        """Fraction of checkouts served by an existing connection."""
        total = self.created + self.reused
        return round(self.reused / total, 4) if total else 0.0


class ValkeyConnectionPool:
    """Thread-safe pool of authenticated Valkey connections.

    Connections idle beyond the eviction window are discarded rather than handed out,
    because a server-side timeout would otherwise surface as a mid-operation failure.
    """

    def __init__(
        self,
        host: str = DEFAULT_VALKEY_HOST,
        port: int = DEFAULT_VALKEY_PORT,
        password: str | None = None,
        db: int = 0,
        timeout: float = DEFAULT_VALKEY_TIMEOUT_SECONDS,
        max_size: int = DEFAULT_VALKEY_POOL_MAX_SIZE,
        idle_timeout: float = DEFAULT_VALKEY_POOL_IDLE_TIMEOUT_SECONDS,
        allow_private_network: bool = True,
    ) -> None:
        self.host = host
        self.port = port
        self.password = password
        self.db = db
        self.timeout = timeout
        self.max_size = max(1, max_size)
        self.idle_timeout = idle_timeout
        self.allow_private_network = allow_private_network

        self._idle: deque[PooledConnection] = deque()
        self._lock = threading.Lock()
        self._in_use = 0
        self.stats = PoolStats()

    def _build_client(self) -> ValkeyClient:
        """Construct a new client bound to this pool's endpoint."""
        return ValkeyClient(
            host=self.host,
            port=self.port,
            password=self.password,
            db=self.db,
            timeout=self.timeout,
            allow_private_network=self.allow_private_network,
        )

    def _take_idle(self, now: float) -> ValkeyClient | None:
        """Pop the newest idle connection that has not gone stale."""
        while self._idle:
            pooled = self._idle.pop()
            if now - pooled.returned_at <= self.idle_timeout:
                return pooled.client
            self.stats.discarded += 1
            self._close_quietly(pooled.client)
        return None

    @staticmethod
    def _close_quietly(client: ValkeyClient) -> None:
        """Close a connection, treating teardown failures as already-closed."""
        try:
            client.close()
        except Exception as exc:
            logger.debug("Discarding Valkey connection failed to close cleanly: %s", exc)

    def acquire(self) -> ValkeyClient:
        """Check out a live connection, reusing an idle one when available."""
        now = time.monotonic()
        with self._lock:
            if self._in_use >= self.max_size and not self._idle:
                raise ValkeyConnectionError(
                    f"Valkey connection pool exhausted ({self.max_size} in use).",
                    host=self.host,
                    port=self.port,
                )
            client = self._take_idle(now)
            self._in_use += 1
            if client is not None:
                self.stats.reused += 1
            else:
                self.stats.created += 1

        if client is None:
            client = self._build_client()

        try:
            client.connect()
        except ValkeyError:
            with self._lock:
                self._in_use -= 1
            self._close_quietly(client)
            raise
        return client

    def release(self, client: ValkeyClient, *, discard: bool = False) -> None:
        """Return a connection to the pool, or discard it when it is no longer usable."""
        with self._lock:
            self._in_use = max(0, self._in_use - 1)
            if discard or len(self._idle) >= self.max_size:
                self.stats.discarded += 1
                self._close_quietly(client)
                return
            self._idle.append(PooledConnection(client=client, returned_at=time.monotonic()))

    @contextmanager
    def connection(self) -> Iterator[ValkeyClient]:
        """Borrow a connection for the duration of a block.

        A connection is discarded rather than returned when the block raises a connection
        error, since the socket state after such a failure is unknown.
        """
        client = self.acquire()
        try:
            yield client
        except ValkeyConnectionError:
            self.release(client, discard=True)
            raise
        else:
            self.release(client)

    def execute(self, *parts: Any) -> Any:
        """Run a single command on a pooled connection."""
        with self.connection() as client:
            return client.execute(*parts)

    def pipeline(self, commands: list[list[Any]]) -> list[Any]:
        """Run a batch of commands on a pooled connection in one round trip."""
        with self.connection() as client:
            return client.pipeline(commands)

    def get_stats(self) -> PoolStats:
        """Snapshot current pool occupancy alongside lifetime counters."""
        with self._lock:
            self.stats.in_use = self._in_use
            self.stats.idle = len(self._idle)
            return PoolStats(**vars(self.stats))

    def close(self) -> None:
        """Close every idle connection and reset the pool."""
        with self._lock:
            while self._idle:
                self._close_quietly(self._idle.pop().client)
            self._in_use = 0


_DEFAULT_POOL: ValkeyConnectionPool | None = None
_POOL_LOCK = threading.Lock()


def get_pool(**overrides: Any) -> ValkeyConnectionPool:
    """Return the process-wide pool, constructing it on first use."""
    global _DEFAULT_POOL
    with _POOL_LOCK:
        if _DEFAULT_POOL is None:
            _DEFAULT_POOL = ValkeyConnectionPool(**overrides)
        return _DEFAULT_POOL


def reset_pool() -> None:
    """Close and drop the process-wide pool, for clean test isolation."""
    global _DEFAULT_POOL
    with _POOL_LOCK:
        if _DEFAULT_POOL is not None:
            _DEFAULT_POOL.close()
        _DEFAULT_POOL = None


__all__ = [
    "PoolStats",
    "PooledConnection",
    "ValkeyConnectionPool",
    "get_pool",
    "reset_pool",
]
