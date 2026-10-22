"""Unit tests for the tiered L1/L2 cache."""

from __future__ import annotations

import time
from typing import Any
from unittest.mock import MagicMock

import pytest

from devops_cli.cache.tiered import (
    LRUCache,
    TieredCache,
    build_cache_key,
    digest_key,
)
from devops_cli.exceptions.valkey import ValkeyConnectionError
from devops_cli.valkey.client import ValkeyClient

# ─────────────────────────────────────────────────────────────────────────────
# 1. Key namespacing
# ─────────────────────────────────────────────────────────────────────────────


def test_keys_are_namespaced_under_a_single_root() -> None:
    """Every key shares one root so a shared Valkey instance stays partitioned."""
    assert build_cache_key("ai:embedding", "abc") == "devops-cli:ai:embedding:abc"
    assert build_cache_key("ai:llm") == "devops-cli:ai:llm"


def test_empty_key_parts_are_dropped() -> None:
    """Blank segments never produce a doubled separator."""
    assert build_cache_key("ns", "", "tail") == "devops-cli:ns:tail"


def test_digest_keys_are_stable_and_content_addressed() -> None:
    """The same payload always digests to the same key, and differing payloads diverge."""
    first = digest_key("ai:embedding", "hello world")
    again = digest_key("ai:embedding", "hello world")
    other = digest_key("ai:embedding", "goodbye world")

    assert (first == again, first == other) == (True, False)
    assert first.startswith("devops-cli:ai:embedding:")


def test_digest_keys_are_order_independent_for_mappings() -> None:
    """Structurally equal payloads digest identically regardless of key order."""
    assert digest_key("ns", {"a": 1, "b": 2}) == digest_key("ns", {"b": 2, "a": 1})


# ─────────────────────────────────────────────────────────────────────────────
# 2. L1 LRU
# ─────────────────────────────────────────────────────────────────────────────


def test_l1_round_trips_values() -> None:
    """A stored value is returned until it expires."""
    cache = LRUCache(max_entries=4)
    cache.set("k", {"v": 1}, ttl=60)
    assert cache.get("k") == {"v": 1}


def test_l1_expires_entries() -> None:
    """An entry past its TTL is treated as absent."""
    cache = LRUCache(max_entries=4)
    cache.set("k", "v", ttl=0.0)
    time.sleep(0.01)
    assert cache.get("k") is None


def test_l1_evicts_least_recently_used() -> None:
    """At capacity the least recently *used* entry is evicted, not the oldest written."""
    cache = LRUCache(max_entries=2)
    cache.set("a", 1, ttl=60)
    cache.set("b", 2, ttl=60)
    cache.get("a")  # Refreshes "a", making "b" the eviction candidate.
    cache.set("c", 3, ttl=60)

    assert (cache.get("a"), cache.get("b"), cache.get("c")) == (1, None, 3)
    assert cache.evictions == 1


def test_l1_deletes_by_key_and_namespace() -> None:
    """Entries can be removed individually or by namespace prefix."""
    cache = LRUCache()
    cache.set("devops-cli:ns:a", 1, ttl=60)
    cache.set("devops-cli:ns:b", 2, ttl=60)
    cache.set("devops-cli:other:c", 3, ttl=60)

    assert cache.delete("devops-cli:ns:a") is True
    assert cache.delete("devops-cli:ns:a") is False
    assert cache.delete_namespace("devops-cli:ns") == 1
    assert cache.get("devops-cli:other:c") == 3


# ─────────────────────────────────────────────────────────────────────────────
# 3. Tiered read/write
# ─────────────────────────────────────────────────────────────────────────────


def _backend(**overrides: Any) -> MagicMock:
    """Build a stub L2 backend exposing execute()."""
    backend = MagicMock()
    backend.execute.return_value = overrides.get("value")
    return backend


def test_l2_hit_is_promoted_into_l1() -> None:
    """An L2 hit is cached in L1, so the repeat read costs no round trip."""
    backend = _backend(value='{"v": 1}')
    cache = TieredCache(backend=backend)

    first = cache.get("devops-cli:ns:k")
    calls_after_first = backend.execute.call_count
    second = cache.get("devops-cli:ns:k")

    assert (first, second) == ({"v": 1}, {"v": 1})
    assert backend.execute.call_count == calls_after_first
    assert (cache.stats.l1_hits, cache.stats.l2_hits) == (1, 1)


def test_miss_is_counted_and_returns_none() -> None:
    """An absent key reports a miss rather than a spurious value."""
    cache = TieredCache(backend=_backend(value=None))
    assert cache.get("devops-cli:ns:absent") is None
    assert cache.stats.misses == 1


def test_write_targets_the_requested_tiers() -> None:
    """Tier selection controls whether a write reaches Valkey."""
    backend = _backend()
    cache = TieredCache(backend=backend)

    cache.set("devops-cli:ns:l1only", "v", tier="l1")
    assert backend.execute.called is False

    cache.set("devops-cli:ns:both", "v", tier="l1_l2")
    assert backend.execute.call_args[0][0] == "SET"


def test_unknown_tier_is_rejected() -> None:
    """An unrecognised tier fails loudly rather than silently skipping a write."""
    cache = TieredCache(backend=_backend())
    with pytest.raises(ValueError, match="Unknown cache tier"):
        cache.set("k", "v", tier="l3")


def test_unreachable_backend_degrades_to_l1() -> None:
    """A cache is an optimisation: an unreachable L2 must not break the caller."""
    backend = MagicMock()
    backend.execute.side_effect = ValkeyConnectionError("offline")
    cache = TieredCache(backend=backend)

    cache.set("devops-cli:ns:k", "value")
    assert cache.get("devops-cli:ns:k") == "value"


def test_batch_read_fetches_l1_misses_in_one_round_trip() -> None:
    """Keys missing from L1 are fetched together, not one request at a time."""
    backend = MagicMock()
    backend.execute.return_value = ['"one"', None, '"three"']
    cache = TieredCache(backend=backend)

    found = cache.get_many(["devops-cli:ns:a", "devops-cli:ns:b", "devops-cli:ns:c"])

    assert found == {"devops-cli:ns:a": "one", "devops-cli:ns:c": "three"}
    assert backend.execute.call_args[0][0] == "MGET"
    assert backend.execute.call_count == 1


def test_batch_read_serves_known_keys_from_l1() -> None:
    """Keys already in L1 are excluded from the network batch entirely."""
    backend = MagicMock()
    backend.execute.return_value = ['"two"']
    cache = TieredCache(backend=backend)
    cache.set("devops-cli:ns:a", "one", tier="l1")

    found = cache.get_many(["devops-cli:ns:a", "devops-cli:ns:b"])

    assert found == {"devops-cli:ns:a": "one", "devops-cli:ns:b": "two"}
    assert backend.execute.call_args[0][1:] == ("devops-cli:ns:b",)


def test_batch_read_without_a_backend_counts_misses() -> None:
    """With no L2 reachable, unmatched keys are misses rather than errors."""
    cache = TieredCache(backend=None)
    assert cache.get_many(["devops-cli:ns:a"]) == {}
    assert cache.stats.misses == 1


def test_namespace_invalidation_clears_both_tiers() -> None:
    """A namespace can be invalidated as a unit across L1 and L2."""
    backend = MagicMock()
    backend.execute.side_effect = [["devops-cli:ns:a", "devops-cli:ns:b"], 2]
    cache = TieredCache(backend=backend)
    cache.set("devops-cli:ns:a", 1, tier="l1")

    removed = cache.invalidate_namespace("ns")

    assert removed == 3
    assert cache.l1.get("devops-cli:ns:a") is None


def test_stats_report_hit_ratio_and_evictions() -> None:
    """Counters distinguish the two tiers so each one's value is visible."""
    cache = TieredCache(backend=_backend(value='"v"'))
    cache.get("devops-cli:ns:k")
    cache.get("devops-cli:ns:k")

    stats = cache.get_stats()
    assert (stats.l2_hits, stats.l1_hits, stats.misses) == (1, 1, 0)
    assert stats.hit_ratio == 1.0


# ─────────────────────────────────────────────────────────────────────────────
# 4. L2 over a Valkey server
# ─────────────────────────────────────────────────────────────────────────────


def test_a_second_cache_reads_what_the_first_wrote_through_valkey(
    valkey_client: ValkeyClient,
) -> None:
    """L2 is shared: another process, with an empty L1, reads the value back."""
    writer = TieredCache(backend=valkey_client)
    writer.set("devops-cli:ns:a", {"v": 1}, ttl=60)
    writer.set("devops-cli:ns:b", [2], ttl=60)
    writer.set("devops-cli:other:c", 3, ttl=60)

    reader = TieredCache(backend=valkey_client)
    assert reader.get_many(["devops-cli:ns:a", "devops-cli:ns:b", "devops-cli:ns:absent"]) == {
        "devops-cli:ns:a": {"v": 1},
        "devops-cli:ns:b": [2],
    }
    assert (reader.get("devops-cli:other:c"), reader.stats.l2_hits) == (3, 3)


def test_deleting_and_invalidating_reach_valkey(valkey_client: ValkeyClient) -> None:
    """A removed key and an invalidated namespace are gone from L2, not only from L1."""
    cache = TieredCache(backend=valkey_client)
    for key in ("devops-cli:ns:a", "devops-cli:ns:b", "devops-cli:other:c"):
        cache.set(key, 1, ttl=60)

    assert (cache.delete("devops-cli:ns:a"), cache.invalidate_namespace("ns")) == (True, 2)
    assert valkey_client.keys("*") == ["devops-cli:other:c"]
