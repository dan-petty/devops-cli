"""Unit tests for Ollama dynamic slot leasing and least-loaded load balancing."""

from __future__ import annotations

import concurrent.futures
import time
from collections.abc import Iterator

import pytest

from devops_cli.ai.client import AIClientError
from devops_cli.ai.client.network import (
    acquire_ollama_slot,
    get_ollama_active_leases,
    reset_ollama_slots,
)


@pytest.fixture(autouse=True)
def _reset_slots() -> Iterator[None]:
    """Ensure clean slot state before and after each test."""
    reset_ollama_slots()
    yield
    reset_ollama_slots()


def test_acquire_ollama_slot_distributes_least_loaded() -> None:
    """Verify slots are leased from the least-loaded candidate node first."""
    candidates = ["http://example.com:11434", "http://example.com:11435"]

    with acquire_ollama_slot(candidates, max_parallel=1, timeout=2.0) as url1:
        # First node acquired
        assert url1 == "http://example.com:11434"
        assert (
            get_ollama_active_leases(url1),
            get_ollama_active_leases("http://example.com:11435"),
        ) == (1, 0)

        # Second lease must pick the empty node
        with acquire_ollama_slot(candidates, max_parallel=1, timeout=2.0) as url2:
            assert url2 == "http://example.com:11435"
            assert (get_ollama_active_leases(url1), get_ollama_active_leases(url2)) == (1, 1)

    # After exit, leases must return to 0
    assert (
        get_ollama_active_leases("http://example.com:11434"),
        get_ollama_active_leases("http://example.com:11435"),
    ) == (0, 0)


def test_acquire_ollama_slot_timeout_when_all_full() -> None:
    """Verify AIClientError is raised when all candidate nodes are fully utilized beyond timeout."""
    candidates = ["http://example.com:11434"]

    with acquire_ollama_slot(candidates, max_parallel=1, timeout=1.0):
        with pytest.raises(AIClientError, match="Timed out after"):
            with acquire_ollama_slot(candidates, max_parallel=1, timeout=0.1):
                pass


def test_concurrent_slot_leasing_across_threads() -> None:
    """Verify multi-threaded slot leasing properly synchronizes and shares capacity."""
    candidates = [
        "http://example.com:11434",
        "http://example.com:11435",
        "http://example.com:11436",
    ]

    def _worker(worker_id: int) -> str:
        with acquire_ollama_slot(candidates, max_parallel=1, timeout=3.0) as leased_url:
            time.sleep(0.05)
            return str(leased_url)

    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as executor:
        futures = [executor.submit(_worker, i) for i in range(6)]
        results = [f.result() for f in futures]

    assert len(results) == 6
    # All 3 nodes must have been leased
    distinct_nodes = set(results)
    assert distinct_nodes == set(candidates)
