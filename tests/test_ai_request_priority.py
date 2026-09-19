"""Unit tests for AI/LLM request priority classification and priority-aware slot leasing."""

from __future__ import annotations

import concurrent.futures
import threading
import time
from collections.abc import Iterator
from typing import Any

import pytest

from devops_cli.ai.client.models import AIClientError, RequestPriority
from devops_cli.ai.client.network import (
    acquire_ollama_slot,
    current_request_priority,
    get_ollama_waiting_counts,
    request_priority_scope,
    reset_ollama_slots,
)
from devops_cli.ai.client.unified import LLMClient
from devops_cli.config.settings import AIConfig
from devops_cli.telemetry.tracer import get_tracer, reset_tracer


@pytest.fixture(autouse=True)
def _clean_state() -> Iterator[None]:
    """Ensure clean slot state and reset tracer before and after each test."""
    reset_ollama_slots()
    reset_tracer()
    yield
    reset_ollama_slots()
    reset_tracer()


def test_request_priority_hierarchy_and_weights() -> None:
    """Verify enum weights and comparison operators strictly order priorities."""
    high = RequestPriority.HIGH
    normal = RequestPriority.NORMAL
    bg = RequestPriority.AS_AVAILABLE

    assert (high.weight, normal.weight, bg.weight) == (30, 20, 10)
    assert (high > normal, normal > bg, high > bg) == (True, True, True)
    assert (bg < normal, normal < high, bg <= normal) == (True, True, True)


def test_request_priority_scope_contextvar() -> None:
    """Verify request_priority_scope manages ContextVar lifecycle and nesting."""
    assert current_request_priority.get() == RequestPriority.NORMAL

    with request_priority_scope(RequestPriority.HIGH):
        assert current_request_priority.get() == RequestPriority.HIGH
        with request_priority_scope("as_available"):
            assert current_request_priority.get() == RequestPriority.AS_AVAILABLE
        assert current_request_priority.get() == RequestPriority.HIGH

    assert current_request_priority.get() == RequestPriority.NORMAL


def _wait_until_waiting(priority_key: str, expected: int = 1) -> bool:
    """Poll until the specified priority queue reaches expected count."""
    for _ in range(50):
        if get_ollama_waiting_counts().get(priority_key, 0) == expected:
            return True
        time.sleep(0.02)
    return False


def test_acquire_ollama_slot_priority_preemption() -> None:
    """Verify HIGH priority requests preempt waiting NORMAL requests for newly freed slots."""
    candidates = ["http://example.com:11434"]
    slot_holder_gate = threading.Event()
    holder_acquired = threading.Event()
    acquisition_order: list[str] = []

    def _slot_holder() -> None:
        with acquire_ollama_slot(candidates, max_parallel=1, timeout=5.0):
            holder_acquired.set()
            slot_holder_gate.wait(timeout=5.0)

    def _enqueue(p: RequestPriority, tag: str) -> None:
        with acquire_ollama_slot(candidates, max_parallel=1, timeout=5.0, priority=p):
            acquisition_order.append(tag)

    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        f_holder = executor.submit(_slot_holder)
        assert holder_acquired.wait(timeout=2.0) is True

        f_normal = executor.submit(_enqueue, RequestPriority.NORMAL, "normal")
        _wait_until_waiting("normal", 1)

        f_high = executor.submit(_enqueue, RequestPriority.HIGH, "high")
        _wait_until_waiting("high", 1)

        slot_holder_gate.set()
        f_holder.result()
        f_high.result()
        f_normal.result()

    assert acquisition_order == ["high", "normal"]


def test_as_available_non_blocking_when_full() -> None:
    """Verify AS_AVAILABLE requests raise immediately without blocking when cluster is full."""
    candidates = ["http://example.com:11434"]
    slot_held = threading.Event()
    release_gate = threading.Event()

    def _occupy() -> None:
        with acquire_ollama_slot(candidates, max_parallel=1, timeout=2.0):
            slot_held.set()
            release_gate.wait(timeout=2.0)

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        f = executor.submit(_occupy)
        assert slot_held.wait(timeout=1.0) is True

        t0 = time.monotonic()
        with pytest.raises(AIClientError, match="No capacity available for as-available"):
            with acquire_ollama_slot(
                candidates, max_parallel=1, priority=RequestPriority.AS_AVAILABLE
            ):
                pass
        elapsed = time.monotonic() - t0

        assert elapsed < 0.2
        release_gate.set()
        f.result()


def test_as_available_yields_when_higher_priority_waiting() -> None:
    """Verify AS_AVAILABLE requests do not acquire slots while higher priority tasks wait."""
    candidates = ["http://example.com:11434"]
    slot_held = threading.Event()
    release_gate = threading.Event()

    def _occupy() -> None:
        with acquire_ollama_slot(candidates, max_parallel=1, timeout=3.0):
            slot_held.set()
            release_gate.wait(timeout=3.0)

    def _normal_waiter() -> None:
        with acquire_ollama_slot(
            candidates, max_parallel=1, timeout=3.0, priority=RequestPriority.NORMAL
        ):
            pass

    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        f_hold = executor.submit(_occupy)
        assert slot_held.wait(timeout=1.0) is True

        f_normal = executor.submit(_normal_waiter)
        assert _wait_until_waiting("normal", 1) is True

        with pytest.raises(AIClientError, match="No capacity available for as-available"):
            with acquire_ollama_slot(
                candidates, max_parallel=1, timeout=0.0, priority=RequestPriority.AS_AVAILABLE
            ):
                pass

        release_gate.set()
        f_hold.result()
        f_normal.result()


def test_llm_client_chat_defaults_to_high_priority(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify LLMClient.chat records HIGH priority on the dispatch telemetry span."""
    sent_spans: list[dict[str, Any]] = []
    tracer = get_tracer()
    monkeypatch.setattr(tracer, "_send_payload", lambda path, p: sent_spans.append(p))

    cfg = AIConfig(provider="ollama", model="test-model", ollama_urls=["http://example.com:11434"])
    client = LLMClient(cfg)

    def fake_messages(
        _self: object,
        _sys: str,
        _msgs: list[Any],
        *,
        enable_thinking: bool = True,
        priority: RequestPriority | str | None = None,
    ) -> Any:
        from devops_cli.ai.client.models import LLMResponse

        return LLMResponse("OK", backend_info="ollama (example.com)")

    monkeypatch.setattr(LLMClient, "_ollama_messages", fake_messages)

    res = client.chat("system instructions", "hello interactive user", use_cache=False)
    assert str(res) == "OK"

    dispatch_spans = [
        span
        for s in sent_spans
        for span in s.get("resourceSpans", [{}])[0].get("scopeSpans", [{}])[0].get("spans", [])
        if span.get("name") == "ai.llm.dispatch"
    ]
    assert len(dispatch_spans) >= 1
    attrs = {
        a["key"]: next(iter(a["value"].values())) for a in dispatch_spans[0].get("attributes", [])
    }
    assert attrs.get("gen_ai.request.priority") == "high"
