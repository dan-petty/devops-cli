"""Unit tests for Ollama dynamic slot leasing and least-loaded load balancing, and the wait for
a slot as a histogram by priority and outcome (#815)."""

from __future__ import annotations

import concurrent.futures
import threading

import pytest

from devops_cli.ai.client import AIClientError
from devops_cli.ai.client.models import RequestPriority
from devops_cli.ai.client.network import (
    acquire_ollama_slot,
    get_ollama_active_leases,
    get_ollama_waiting_counts,
)
from devops_cli.telemetry.instruments import AI_OLLAMA_SLOT_WAIT
from tests.support.fakes.otlp import FakeCollector
from tests.support.waits import THREAD_HANDOFF_BOUND_SECONDS, wait_until

NODE = "http://example.com:11434"


def test_acquire_ollama_slot_distributes_least_loaded() -> None:
    """Verify slots are leased from the least-loaded candidate node first."""
    candidates = ["http://example.com:11434", "http://example.com:11435"]

    with acquire_ollama_slot(
        candidates, max_parallel=1, timeout=THREAD_HANDOFF_BOUND_SECONDS
    ) as url1:
        # First node acquired
        assert url1 == "http://example.com:11434"
        assert (
            get_ollama_active_leases(url1),
            get_ollama_active_leases("http://example.com:11435"),
        ) == (1, 0)

        # Second lease must pick the empty node
        with acquire_ollama_slot(
            candidates, max_parallel=1, timeout=THREAD_HANDOFF_BOUND_SECONDS
        ) as url2:
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

    with acquire_ollama_slot(candidates, max_parallel=1, timeout=THREAD_HANDOFF_BOUND_SECONDS):
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
    barrier = threading.Barrier(3)
    held_count = 0
    held_lock = threading.Lock()

    def _worker(worker_id: int) -> str:
        nonlocal held_count
        with acquire_ollama_slot(
            candidates, max_parallel=1, timeout=THREAD_HANDOFF_BOUND_SECONDS
        ) as leased_url:
            with held_lock:
                should_wait = held_count < 3
                if should_wait:
                    held_count += 1
            if should_wait:
                barrier.wait(timeout=THREAD_HANDOFF_BOUND_SECONDS)
            return str(leased_url)

    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as executor:
        futures = [executor.submit(_worker, i) for i in range(6)]
        results = [f.result() for f in futures]

    assert len(results) == 6
    # All 3 nodes must have been leased
    distinct_nodes = set(results)
    assert distinct_nodes == set(candidates)


def test_slot_leasing_takes_max_parallel_from_its_caller() -> None:
    """The client passes `ai.ollama_max_parallel` of its settings, so slot leasing declares no
    default of its own that could ignore the setting (#2447)."""
    import inspect

    from devops_cli.ai.client import network
    from devops_cli.ai.client.network import (
        acquire_ollama_slot,
        track_ollama_url,
    )
    from devops_cli.config.defaults import DEFAULT_AI_MAX_RESPONSE_BYTES

    sig_acquire = inspect.signature(acquire_ollama_slot)
    sig_track = inspect.signature(track_ollama_url)

    assert (
        sig_acquire.parameters["max_parallel"].default,
        sig_track.parameters["max_parallel"].default,
        network.DEFAULT_AI_MAX_RESPONSE_BYTES,
    ) == (
        inspect.Parameter.empty,
        inspect.Parameter.empty,
        DEFAULT_AI_MAX_RESPONSE_BYTES,
    )


def test_acquire_ollama_slot_effective_timeout_defaults() -> None:
    """Verify acquire_ollama_slot calculates effective timeout using centralized defaults."""
    from unittest.mock import patch

    from devops_cli.ai.client.models import RequestPriority
    from devops_cli.ai.client.network import acquire_ollama_slot
    from devops_cli.config.defaults import DEFAULT_OLLAMA_SLOT_TIMEOUT_SECONDS

    with patch(
        "devops_cli.ai.client.network._wait_for_slot", return_value="http://example.com:11434"
    ) as mock_wait:
        with acquire_ollama_slot(["http://example.com:11434"], max_parallel=2, timeout=None):
            pass
        eff_timeout = mock_wait.call_args[0][4]

        with acquire_ollama_slot(
            ["http://example.com:11434"],
            max_parallel=2,
            timeout=None,
            priority=RequestPriority.AS_AVAILABLE,
        ):
            pass
        as_avail_timeout = mock_wait.call_args[0][4]

        assert (eff_timeout, as_avail_timeout) == (
            DEFAULT_OLLAMA_SLOT_TIMEOUT_SECONDS,
            0.0,
        )


def _slot_waits(otlp: FakeCollector) -> dict[tuple[str, str], tuple[int, float]]:
    """The observations of the Ollama slot wait sent, as (count, seconds) by (priority, outcome)."""
    waits: dict[tuple[str, str], tuple[int, float]] = {}
    for metric in otlp.metrics:
        if metric["name"] != AI_OLLAMA_SLOT_WAIT.name:
            continue
        for point in metric["exponentialHistogram"]["dataPoints"]:
            attrs = {a["key"]: next(iter(a["value"].values())) for a in point["attributes"]}
            count, seconds = waits.get((attrs["priority"], attrs["outcome"]), (0, 0.0))
            waits[(attrs["priority"], attrs["outcome"])] = (
                count + int(point["count"]),
                seconds + point["sum"],
            )
    return waits


def _counts(waits: dict[tuple[str, str], tuple[int, float]]) -> dict[tuple[str, str], int]:
    return {labels: count for labels, (count, _) in waits.items()}


def test_a_call_with_a_free_slot_observes_its_wait_by_priority(otlp: FakeCollector) -> None:
    """A call that finds a free slot sends one observation with the priority it asked for, or
    the priority of its context when it names none."""
    with acquire_ollama_slot([NODE], max_parallel=2, priority=RequestPriority.HIGH):
        pass
    with acquire_ollama_slot([NODE], max_parallel=2):
        pass

    assert _counts(_slot_waits(otlp)) == {("high", "ok"): 1, ("normal", "ok"): 1}


def _lease_once(priority: RequestPriority) -> str:
    with acquire_ollama_slot(
        [NODE], max_parallel=1, timeout=THREAD_HANDOFF_BOUND_SECONDS, priority=priority
    ) as leased_url:
        return leased_url


def test_a_call_that_waits_for_a_held_slot_observes_the_wait(otlp: FakeCollector) -> None:
    """A normal call queued behind a held slot sends one `ok` observation once the holder
    releases, and its wait is above 0 s."""
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        with acquire_ollama_slot([NODE], max_parallel=1, priority=RequestPriority.HIGH):
            waiter = pool.submit(_lease_once, RequestPriority.NORMAL)
            queued = wait_until(lambda: get_ollama_waiting_counts()["normal"] == 1)
        leased_url = waiter.result(timeout=THREAD_HANDOFF_BOUND_SECONDS)

    waits = _slot_waits(otlp)
    assert (queued, leased_url, _counts(waits), waits.get(("normal", "ok"), (0, 0.0))[1] > 0) == (
        True,
        NODE,
        {("high", "ok"): 1, ("normal", "ok"): 1},
        True,
    )


def test_an_as_available_call_with_no_free_slot_observes_a_timeout(otlp: FakeCollector) -> None:
    """An as-available call finds the only slot held, fails at once and sends one `timeout`
    observation."""
    with acquire_ollama_slot([NODE], max_parallel=1, priority=RequestPriority.HIGH):
        with pytest.raises(AIClientError, match="No capacity available"):
            with acquire_ollama_slot([NODE], max_parallel=1, priority=RequestPriority.AS_AVAILABLE):
                pass

    assert _counts(_slot_waits(otlp)) == {("high", "ok"): 1, ("as_available", "timeout"): 1}
