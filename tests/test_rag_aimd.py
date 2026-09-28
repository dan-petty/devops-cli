"""Unit tests for Additive Increase / Multiplicative Decrease (AIMD) embedding batch sizing."""

from __future__ import annotations

from devops_cli.ai.rag.embeddings import EmbeddingsEngine
from devops_cli.config.defaults import (
    DEFAULT_RAG_EMBEDDING_LATENCY_THRESHOLD_SECONDS,
    DEFAULT_RAG_EMBEDDING_MIN_BATCH_SIZE,
)
from devops_cli.config.settings import AIConfig


def test_aimd_multiplicative_decrease_on_degradation() -> None:
    """Verify batch size halves down to minimum of 1 on successive latency degradation events."""
    ai_cfg = AIConfig(provider="ollama", ollama_urls=["http://example.com:11434"])
    engine = EmbeddingsEngine(ai_cfg, batch_size=32)

    assert (
        engine._current_batch_size,
        engine._configured_batch_size,
        engine._consecutive_successes,
    ) == (32, 32, 0)

    # First latency spike (> threshold): halves to 16
    engine._record_batch_latency(DEFAULT_RAG_EMBEDDING_LATENCY_THRESHOLD_SECONDS + 0.5)
    assert (engine._current_batch_size, engine._consecutive_successes) == (16, 0)

    # Second latency spike: halves to 8
    engine._record_batch_latency(DEFAULT_RAG_EMBEDDING_LATENCY_THRESHOLD_SECONDS + 1.0)
    assert (engine._current_batch_size, engine._consecutive_successes) == (8, 0)

    # Halve repeatedly down to floor
    assert (
        engine._apply_aimd_decrease(),
        engine._apply_aimd_decrease(),
        engine._apply_aimd_decrease(),
        engine._apply_aimd_decrease(),
    ) == (
        4,
        2,
        DEFAULT_RAG_EMBEDDING_MIN_BATCH_SIZE,
        DEFAULT_RAG_EMBEDDING_MIN_BATCH_SIZE,
    )


def test_aimd_additive_increase_recovery_after_low_latency() -> None:
    """Verify batch size additively recovers by +2 after every 2 consecutive low-latency batches."""
    ai_cfg = AIConfig(provider="ollama", ollama_urls=["http://example.com:11434"])
    engine = EmbeddingsEngine(ai_cfg, batch_size=16)

    # Force batch size down to 4
    engine._current_batch_size = 4

    # Batch 1 (fast): consecutive_successes becomes 1, batch size stays 4
    engine._record_batch_latency(0.5)
    assert (engine._current_batch_size, engine._consecutive_successes) == (4, 1)

    # Batch 2 (fast): consecutive_successes reaches 2 -> batch size increments by 2 (to 6)
    engine._record_batch_latency(0.4)
    assert (engine._current_batch_size, engine._consecutive_successes) == (6, 0)

    # Batch 3 (fast): consecutive_successes becomes 1
    engine._record_batch_latency(0.3)
    assert (engine._current_batch_size, engine._consecutive_successes) == (6, 1)

    # Batch 4 (fast): consecutive_successes reaches 2 -> batch size increments to 8
    engine._record_batch_latency(0.2)
    assert (engine._current_batch_size, engine._consecutive_successes) == (8, 0)


def test_aimd_additive_increase_capped_at_configured_maximum() -> None:
    """Verify batch size does not exceed configured ceiling during additive increase."""
    ai_cfg = AIConfig(provider="ollama", ollama_urls=["http://example.com:11434"])
    engine = EmbeddingsEngine(ai_cfg, batch_size=10)
    engine._current_batch_size = 9

    # Trigger 2 fast batches -> increases from 9 to capped 10
    engine._record_batch_latency(0.1)
    engine._record_batch_latency(0.1)
    assert engine._current_batch_size == 10

    # Trigger 2 more fast batches -> remains at configured ceiling 10
    engine._record_batch_latency(0.1)
    engine._record_batch_latency(0.1)
    assert engine._current_batch_size == 10


def test_aimd_transient_spike_resets_success_counter() -> None:
    """Verify transient latency degradation resets consecutive successes counter immediately."""
    ai_cfg = AIConfig(provider="ollama", ollama_urls=["http://example.com:11434"])
    engine = EmbeddingsEngine(ai_cfg, batch_size=16)
    engine._current_batch_size = 8

    # 1 fast batch
    engine._record_batch_latency(0.2)
    assert engine._consecutive_successes == 1

    # Transient latency spike: resets counter to 0 and cuts batch size to 4
    engine._record_batch_latency(DEFAULT_RAG_EMBEDDING_LATENCY_THRESHOLD_SECONDS + 0.1)
    assert (engine._current_batch_size, engine._consecutive_successes) == (4, 0)
