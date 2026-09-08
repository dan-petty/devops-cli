"""Unit tests for ReviewWorkerPool, TokenBucketRateLimiter, and streaming diff chunking."""

from __future__ import annotations

import asyncio
import time

import pytest

from devops_cli.ai.review.chunker import diff_pages, diff_stream_chunks
from devops_cli.ai.review.pool import (
    ReviewPoolError,
    ReviewWorkerPool,
    TokenBucketRateLimiter,
)

# ── TokenBucketRateLimiter Tests ──────────────────────────────────────────────


def test_token_bucket_initial_capacity() -> None:
    """Test token bucket starts at full capacity and tracks available tokens."""
    limiter = TokenBucketRateLimiter(rate=10.0, capacity=5.0)
    assert limiter.available_tokens == pytest.approx(5.0, abs=0.1)


def test_token_bucket_try_acquire() -> None:
    """Test non-blocking try_acquire consumes tokens and rejects when depleted."""
    limiter = TokenBucketRateLimiter(rate=10.0, capacity=2.0)
    assert limiter.try_acquire(1.0) is True
    assert limiter.try_acquire(1.0) is True
    assert limiter.try_acquire(1.0) is False


@pytest.mark.asyncio
async def test_token_bucket_async_acquire() -> None:
    """Test async acquire waits for token refill when bucket is empty."""
    limiter = TokenBucketRateLimiter(rate=20.0, capacity=1.0)
    assert limiter.try_acquire(1.0) is True

    t_start = time.monotonic()
    await limiter.acquire(1.0)
    elapsed = time.monotonic() - t_start

    # At rate 20 tokens/sec, 1 token requires ~0.05s
    assert elapsed >= 0.03
    assert limiter.available_tokens < 1.0


# ── ReviewWorkerPool Tests ───────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_worker_pool_concurrency_bounding() -> None:
    """Verify max in-flight tasks never exceed configured semaphore capacity."""
    max_concurrency = 2
    pool = ReviewWorkerPool(max_concurrency=max_concurrency)
    active_count = 0
    max_observed = 0

    async def _worker(item: int) -> int:
        nonlocal active_count, max_observed
        active_count += 1
        max_observed = max(max_observed, active_count)
        await asyncio.sleep(0.02)
        active_count -= 1
        return item * 2

    items = list(range(6))
    results = await pool.submit_all(_worker, items)

    assert results == [0, 2, 4, 6, 8, 10]
    assert max_observed <= max_concurrency
    assert active_count == 0


@pytest.mark.asyncio
async def test_worker_pool_empty_items() -> None:
    """Test worker pool gracefully handles empty collections."""
    pool = ReviewWorkerPool(max_concurrency=4)

    async def _dummy(x: int) -> int:
        return x

    results = await pool.submit_all(_dummy, [])
    assert results == []


@pytest.mark.asyncio
async def test_worker_pool_with_rate_limiter() -> None:
    """Test worker pool paces execution when bound to a TokenBucketRateLimiter."""
    limiter = TokenBucketRateLimiter(rate=10.0, capacity=2.0)
    pool = ReviewWorkerPool(max_concurrency=4, rate_limiter=limiter)

    async def _noop(x: int) -> int:
        return x

    t_start = time.monotonic()
    results = await pool.submit_all(_noop, list(range(4)))
    elapsed = time.monotonic() - t_start

    assert results == [0, 1, 2, 3]
    # 4 items with capacity 2 at 10/s takes at least 0.12s
    assert elapsed >= 0.12


@pytest.mark.asyncio
async def test_worker_pool_submit_sync_all() -> None:
    """Test running synchronous worker functions via asyncio.to_thread delegation."""
    pool = ReviewWorkerPool(max_concurrency=3)

    def _sync_worker(val: str) -> str:
        time.sleep(0.01)
        return val.upper()

    inputs = ["apple", "banana", "cherry"]
    results = await pool.submit_sync_all(_sync_worker, inputs)
    assert results == ["APPLE", "BANANA", "CHERRY"]


def test_worker_pool_run_sync_runner() -> None:
    """Test synchronous runner bridging async TaskGroup execution."""
    pool = ReviewWorkerPool(max_concurrency=2)

    async def _double(n: int) -> int:
        await asyncio.sleep(0.01)
        return n * 2

    outputs = pool.run_sync(_double, [1, 2, 3])
    assert outputs == [2, 4, 6]


def test_worker_pool_run_sync_sync_callable() -> None:
    """Test synchronous runner executing synchronous functions."""
    pool = ReviewWorkerPool(max_concurrency=2)

    def _square(n: int) -> int:
        return n * n

    outputs = pool.run_sync_all(_square, [2, 3, 4])
    assert outputs == [4, 9, 16]


@pytest.mark.asyncio
async def test_worker_pool_error_propagation() -> None:
    """Test exceptions within tasks are wrapped or propagated cleanly."""
    pool = ReviewWorkerPool(max_concurrency=2)

    async def _failing_worker(val: int) -> int:
        if val == 2:
            raise ValueError("Task failed")
        return val

    with pytest.raises((ValueError, ExceptionGroup, ReviewPoolError)):
        await pool.submit_all(_failing_worker, [1, 2, 3])


@pytest.mark.asyncio
async def test_worker_pool_return_exceptions() -> None:
    """Test return_exceptions=True captures exceptions alongside successful results."""
    pool = ReviewWorkerPool(max_concurrency=2)

    async def _partial_failing(val: int) -> int:
        if val == 1:
            raise RuntimeError("Boom")
        return val * 10

    results = await pool.submit_all(_partial_failing, [0, 1, 2], return_exceptions=True)
    assert results[0] == 0
    assert isinstance(results[1], RuntimeError)
    assert results[2] == 20


# ── Streaming Diff Chunker Tests ─────────────────────────────────────────────


def test_diff_stream_chunks_basic() -> None:
    """Test diff_stream_chunks generates chunks lazily matching diff_pages output."""
    diff = "diff --git a/one.py b/one.py\n+line one\ndiff --git a/two.py b/two.py\n+line two\n"
    chunks = list(diff_stream_chunks(diff, max_chars=1000))
    expected = diff_pages(diff, max_chars=1000)

    assert chunks == expected
    assert len(chunks) == 2
    assert "one.py" in chunks[0]
    assert "two.py" in chunks[1]


def test_diff_stream_chunks_from_line_iterator() -> None:
    """Test diff_stream_chunks consumes an iterable of lines without full diff string in memory."""
    lines = [
        "diff --git a/pkg/module.py b/pkg/module.py\n",
        "--- a/pkg/module.py\n",
        "+++ b/pkg/module.py\n",
        "@@ -1,3 +1,3 @@\n",
        "+new content\n",
    ]

    stream = (line for line in lines)
    chunks = list(diff_stream_chunks(stream, max_chars=500))

    assert len(chunks) == 1
    assert "pkg/module.py" in chunks[0]
    assert "+new content" in chunks[0]


def test_diff_stream_chunks_skips_generated_files() -> None:
    """Test autogenerated files like uv.lock or package-lock.json are skipped in stream."""
    diff = (
        "diff --git a/uv.lock b/uv.lock\n"
        "+# lockfile content\n"
        "diff --git a/src/app.py b/src/app.py\n"
        "+# app code\n"
    )
    chunks = list(diff_stream_chunks(diff, max_chars=1000))

    assert len(chunks) == 1
    assert "src/app.py" in chunks[0]
    assert "uv.lock" not in chunks[0]


def test_diff_stream_chunks_empty_stream() -> None:
    """Test empty input stream yields empty string fallback."""
    chunks = list(diff_stream_chunks("", max_chars=1000))
    assert chunks == [""]
