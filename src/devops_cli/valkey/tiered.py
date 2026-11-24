"""The tiered mapping of the project brain: an in-process tier over the shared Valkey tier (#4668).

ADR 0023 section 2 sets the tiers of a fact that each process reads the same: the memory of the
process, then the cache Valkey `valkey-devops`, then the source. `TieredMapping` is a
`MutableMapping`, so `cachetools.cached` takes it as its cache and the decorated read stays as it
is. The keys are text, so `cached` gets a `key` function that gives the text of the key, such as
`packaging.utils.canonicalize_name`, in place of its default tuple:

- A read looks in memory, then in Valkey. A Valkey read gets the value and the time that its key
  has left (`GET` and `PTTL`) in one round trip, and a hit fills the memory tier for that time,
  or for the TTL of the mapping when that is sooner: a value stays in memory no longer than its
  Valkey key (#6611). A miss in both raises `KeyError`, and `cached` reads the source and writes
  the value.
- A write keeps the value in memory and sends it to Valkey with the TTL of the mapping. A value
  whose encoded form is over `DEFAULT_BRAIN_VALUE_MAX_BYTES` stays in memory.
- The Valkey tier is the one tier of the process (`shared_cache_tier`), behind its circuit
  breaker. While Valkey fails, a read goes to the source and a write stays in memory; no error
  reaches the caller.

A value in Valkey is `<schema key>:<JSON>`. The schema key is the first 16 hex characters of the
sha256 of the JSON schema of the value type, as `LISTING_SCHEMA_KEY` is for the listing snapshot.
A value with another schema key is a miss, so a release that changes the type reads the source
again and writes the value under its own key. The prefix holds the version of the key kind, so a
new version never reads a key of an older one.

`__iter__` and `__len__` cover the memory tier only: a scan of Valkey for each call has no use.
Each read adds one to `devops_cli_brain_reads_total` and each write one to
`devops_cli_brain_writes_total`, with the store of the mapping and the result, never the key.
"""

from __future__ import annotations

import hashlib
import json
import logging
import threading
from collections.abc import Iterator, MutableMapping
from dataclasses import dataclass
from typing import Any, Final

from cachetools import TLRUCache
from pydantic import TypeAdapter, ValidationError

from devops_cli.config.constants import BrainRead, BrainStore, BrainWrite
from devops_cli.config.defaults import DEFAULT_BRAIN_MEMORY_ENTRIES, DEFAULT_BRAIN_VALUE_MAX_BYTES
from devops_cli.core import clock
from devops_cli.telemetry.instruments import BRAIN_READS_TOTAL, BRAIN_WRITES_TOTAL, emit
from devops_cli.valkey.cache import shared_cache_tier

logger = logging.getLogger(__name__)

# The text between the schema key and the JSON of a value, and between the prefix and a key.
_SEPARATOR: Final = ":"
# The length of a schema key, in hex characters.
_SCHEMA_KEY_CHARS: Final = 16
# The `PTTL` replies of a key with no TTL and of a key that does not exist.
_PTTL_NO_EXPIRY: Final = -1
_PTTL_NO_KEY: Final = -2

# The generation of the memory tiers of the process. `reset_tiered_mappings` starts a new one, and
# a mapping empties its memory tier when it next sees a new generation, so no registry keeps the
# mappings.
_generation = 0


def schema_key_of(adapter: TypeAdapter[Any]) -> str:
    """The first 16 hex characters of the sha256 of the JSON schema of the type of `adapter`."""
    schema = json.dumps(adapter.json_schema(), sort_keys=True)
    return hashlib.sha256(schema.encode()).hexdigest()[:_SCHEMA_KEY_CHARS]


def count_read(store: BrainStore, result: BrainRead) -> None:
    """Add one read of `store` to `devops_cli_brain_reads_total`."""
    emit(BRAIN_READS_TOTAL, 1, {"store": store.value, "result": result.value})


def count_write(store: BrainStore, result: BrainWrite) -> None:
    """Add one write of `store` to `devops_cli_brain_writes_total`."""
    emit(BRAIN_WRITES_TOTAL, 1, {"store": store.value, "result": result.value})


def _monotonic() -> float:
    """The clock of the memory tier: the clock seam, which the `clock` fixture of the tests moves."""
    return clock.monotonic()


@dataclass(frozen=True)
class _Held[V]:
    """A value of the memory tier, and the time on the clock seam when it expires."""

    value: V
    expires: float


def _expiry(key: str, held: _Held[Any], now: float) -> float:
    """The time to use of a value of the memory tier: the expiry that it holds."""
    return held.expires


class TieredMapping[V](MutableMapping[str, V]):
    """Values of one type under one key prefix, in the memory of the process and in Valkey.

    `prefix` is the key prefix in Valkey, such as `valkey:brain:v1:fact:pypi`, and the key of a
    value is `<prefix>:<key>`. `adapter` validates and encodes the values. A written value lives
    `ttl` seconds in memory and in Valkey. A value read from Valkey lives in memory until its key
    expires, or `ttl` seconds when that is sooner. `store` is the label of the counters.
    """

    def __init__(
        self,
        prefix: str,
        adapter: TypeAdapter[V],
        *,
        ttl: int,
        store: BrainStore = BrainStore.FACT,
        entries: int = DEFAULT_BRAIN_MEMORY_ENTRIES,
    ) -> None:
        self.prefix = prefix
        self.ttl = ttl
        self.store = store
        self._adapter = adapter
        self._schema_key: str | None = None
        self._entries = entries
        self._memory: TLRUCache[str, _Held[V]] = (
            TLRUCache(maxsize=entries, ttu=_expiry, timer=_monotonic) if entries > 0 else None  # type: ignore[assignment]
        )
        self._lock = threading.Lock()
        self._generation = _generation

    @property
    def schema_key(self) -> str:
        """The schema key of the value type, which each value in Valkey starts with."""
        if self._schema_key is None:
            self._schema_key = schema_key_of(self._adapter)
        return self._schema_key

    def shared_key(self, key: str) -> str:
        """The Valkey key of `key`."""
        return f"{self.prefix}{_SEPARATOR}{key}"

    def __getitem__(self, key: str) -> V:
        if self._entries > 0:
            with self._lock:
                held = self._current().get(key)
            if held is not None:
                count_read(self.store, BrainRead.MEMORY)
                return held.value
        tier = shared_cache_tier()
        read = None if tier is None else tier.get_with_ttl(self.shared_key(key))
        text, remaining = (None, _PTTL_NO_KEY) if read is None else read
        found = [] if text is None else self._decoded(text)
        if found:
            self._fill(key, found[0], remaining)
            count_read(self.store, BrainRead.SHARED)
            return found[0]
        down = tier is None or tier.is_open
        count_read(self.store, BrainRead.FALLBACK if down else BrainRead.SOURCE)
        raise KeyError(key)

    def __setitem__(self, key: str, value: V) -> None:
        if self._entries > 0:
            with self._lock:
                self._current()[key] = _Held(value, _monotonic() + self.ttl)
        encoded = self.schema_key.encode() + _SEPARATOR.encode() + self._adapter.dump_json(value)
        if len(encoded) > DEFAULT_BRAIN_VALUE_MAX_BYTES:
            count_write(self.store, BrainWrite.OVERSIZE)
            return
        tier = shared_cache_tier()
        sent = tier is not None and tier.set(self.shared_key(key), encoded.decode(), ex=self.ttl)
        count_write(self.store, BrainWrite.SHARED if sent else BrainWrite.SKIPPED)

    def __delitem__(self, key: str) -> None:
        if self._entries > 0:
            with self._lock:
                self._current().pop(key, None)
        tier = shared_cache_tier()
        if tier is not None:
            tier.unlink(self.shared_key(key))

    def __iter__(self) -> Iterator[str]:
        if self._entries <= 0:
            return iter(())
        with self._lock:
            keys = list(self._current())
        return iter(keys)

    def __len__(self) -> int:
        if self._entries <= 0:
            return 0
        with self._lock:
            return len(self._current())

    def _fill(self, key: str, value: V, remaining: int) -> None:
        """Keep a value read from Valkey in memory for the `remaining` milliseconds of its key,
        or for `ttl` seconds when that is sooner or the key has no TTL. A key that expired
        between `GET` and `PTTL` leaves the memory tier as it is."""
        if self._entries <= 0 or remaining == _PTTL_NO_KEY:
            return
        seconds = self.ttl if remaining == _PTTL_NO_EXPIRY else min(self.ttl, remaining / 1000)
        with self._lock:
            self._current()[key] = _Held(value, _monotonic() + seconds)

    def _current(self) -> TLRUCache[str, _Held[V]]:
        """The memory tier, emptied first when `reset_tiered_mappings` started a new generation.
        The caller holds the lock."""
        if self._entries <= 0:
            return None  # type: ignore[return-value]
        if self._generation != _generation:
            self._memory.clear()
            self._generation = _generation
        return self._memory

    def _decoded(self, text: str) -> list[V]:
        """The value that `text` from Valkey holds, or nothing for another schema key or a value
        that does not validate."""
        schema, separator, body = text.partition(_SEPARATOR)
        if not separator or schema != self.schema_key:
            return []
        try:
            return [self._adapter.validate_json(body)]
        except ValidationError as exc:
            logger.debug(
                "A value of %s in Valkey does not validate, so the read is a miss: %s",
                self.prefix,
                exc.error_count(),
            )
            return []


def reset_tiered_mappings() -> None:
    """Empty the memory tier of each mapping of the process, as a new process starts; Valkey keeps
    its values."""
    global _generation
    _generation += 1


__all__ = [
    "TieredMapping",
    "count_read",
    "count_write",
    "reset_tiered_mappings",
    "schema_key_of",
]
