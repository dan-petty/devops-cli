"""Unit tests for AI/LLM request priority classification and priority-aware slot leasing."""

from __future__ import annotations

import concurrent.futures
import threading
from typing import Any

import pytest

from devops_cli.ai.client.models import AIClientError, CallSampling, RequestPriority
from devops_cli.ai.client.network import (
    acquire_ollama_slot,
    current_request_priority,
    get_ollama_waiting_counts,
    request_priority_scope,
)
from devops_cli.ai.client.unified import LLMClient
from devops_cli.config.settings import AIConfig
from devops_cli.telemetry.tracer import get_tracer
from tests.support.waits import THREAD_HANDOFF_BOUND_SECONDS, wait_until


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
    """Whether the specified priority queue reaches the expected count within the bound."""
    return wait_until(lambda: get_ollama_waiting_counts().get(priority_key, 0) == expected)


def test_acquire_ollama_slot_priority_preemption() -> None:
    """Verify HIGH priority requests preempt waiting NORMAL requests for newly freed slots."""
    candidates = ["http://example.com:11434"]
    slot_holder_gate = threading.Event()
    holder_acquired = threading.Event()
    acquisition_order: list[str] = []

    def _slot_holder() -> bool:
        """Hold the slot until the test lets it go; whether the test did."""
        with acquire_ollama_slot(candidates, max_parallel=1, timeout=THREAD_HANDOFF_BOUND_SECONDS):
            holder_acquired.set()
            return slot_holder_gate.wait(timeout=THREAD_HANDOFF_BOUND_SECONDS)

    def _enqueue(p: RequestPriority, tag: str) -> None:
        with acquire_ollama_slot(
            candidates, max_parallel=1, timeout=THREAD_HANDOFF_BOUND_SECONDS, priority=p
        ):
            acquisition_order.append(tag)

    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        f_holder = executor.submit(_slot_holder)
        assert holder_acquired.wait(timeout=THREAD_HANDOFF_BOUND_SECONDS) is True

        f_normal = executor.submit(_enqueue, RequestPriority.NORMAL, "normal")
        assert _wait_until_waiting("normal", 1) is True

        f_high = executor.submit(_enqueue, RequestPriority.HIGH, "high")
        assert _wait_until_waiting("high", 1) is True

        slot_holder_gate.set()
        held_until_released = f_holder.result()
        f_high.result()
        f_normal.result()

    assert (acquisition_order, held_until_released) == (["high", "normal"], True)


def test_as_available_non_blocking_when_full(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify AS_AVAILABLE requests raise immediately without blocking when cluster is full."""
    candidates = ["http://example.com:11434"]
    slot_held = threading.Event()
    release_gate = threading.Event()
    waits: list[float | None] = []

    def _occupy() -> bool:
        """Hold the slot until the test lets it go; whether the test did."""
        with acquire_ollama_slot(candidates, max_parallel=1, timeout=THREAD_HANDOFF_BOUND_SECONDS):
            slot_held.set()
            return release_gate.wait(timeout=THREAD_HANDOFF_BOUND_SECONDS)

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        f = executor.submit(_occupy)
        assert slot_held.wait(timeout=THREAD_HANDOFF_BOUND_SECONDS) is True

        with (
            monkeypatch.context() as patch_wait,
            pytest.raises(AIClientError, match="No capacity available for as-available"),
        ):
            patch_wait.setattr(
                threading.Condition,
                "wait",
                lambda self, timeout=None: waits.append(timeout) or False,
            )
            with acquire_ollama_slot(
                candidates, max_parallel=1, priority=RequestPriority.AS_AVAILABLE
            ):
                pass

        release_gate.set()
        assert (waits, f.result()) == ([], True)


def test_as_available_yields_when_higher_priority_waiting() -> None:
    """Verify AS_AVAILABLE requests do not acquire slots while higher priority tasks wait."""
    candidates = ["http://example.com:11434"]
    slot_held = threading.Event()
    release_gate = threading.Event()

    def _occupy() -> bool:
        """Hold the slot until the test lets it go; whether the test did."""
        with acquire_ollama_slot(candidates, max_parallel=1, timeout=THREAD_HANDOFF_BOUND_SECONDS):
            slot_held.set()
            return release_gate.wait(timeout=THREAD_HANDOFF_BOUND_SECONDS)

    def _normal_waiter() -> None:
        with acquire_ollama_slot(
            candidates,
            max_parallel=1,
            timeout=THREAD_HANDOFF_BOUND_SECONDS,
            priority=RequestPriority.NORMAL,
        ):
            pass

    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        f_hold = executor.submit(_occupy)
        assert slot_held.wait(timeout=THREAD_HANDOFF_BOUND_SECONDS) is True

        f_normal = executor.submit(_normal_waiter)
        assert _wait_until_waiting("normal", 1) is True

        with pytest.raises(AIClientError, match="No capacity available for as-available"):
            with acquire_ollama_slot(
                candidates, max_parallel=1, timeout=0.0, priority=RequestPriority.AS_AVAILABLE
            ):
                pass

        release_gate.set()
        held_until_released = f_hold.result()
        f_normal.result()

    assert held_until_released is True


def test_llm_client_chat_defaults_to_high_priority(
    monkeypatch: pytest.MonkeyPatch, config: Any
) -> None:
    """Verify LLMClient.chat records HIGH priority on the dispatch telemetry span."""
    config(telemetry={"enabled": True})
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
        sampling: CallSampling | None = None,
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
    assert attrs.get("llm.request.priority") == "high"
