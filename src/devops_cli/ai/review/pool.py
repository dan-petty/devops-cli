"""Parallel asynchronous worker pool and rate limiter for AI code review execution."""

from __future__ import annotations

import asyncio
import concurrent.futures
import logging
import time
from collections.abc import Callable, Coroutine, Iterable
from typing import Any

from devops_cli.exceptions import ReviewPoolError

logger = logging.getLogger(__name__)


class TokenBucketRateLimiter:
    """Token bucket rate limiter providing asynchronous and non-blocking token acquisition."""

    def __init__(self, rate: float = 10.0, capacity: float = 10.0) -> None:
        self.rate = max(0.1, float(rate))
        self.capacity = max(1.0, float(capacity))
        self._tokens = self.capacity
        self._last_time = time.monotonic()
        self._lock = asyncio.Lock()

    def _refill(self) -> None:
        now = time.monotonic()
        elapsed = now - self._last_time
        if elapsed > 0:
            self._tokens = min(self.capacity, self._tokens + elapsed * self.rate)
            self._last_time = now

    @property
    def available_tokens(self) -> float:
        """Return currently available tokens after lazy refill."""
        self._refill()
        return self._tokens

    def try_acquire(self, tokens: float = 1.0) -> bool:
        """Attempt non-blocking token acquisition, returning True on success."""
        self._refill()
        if self._tokens >= tokens:
            self._tokens -= tokens
            return True
        return False

    async def acquire(self, tokens: float = 1.0) -> None:
        """Asynchronously wait until required tokens are available and consume them."""
        while True:
            async with self._lock:
                self._refill()
                if self._tokens >= tokens:
                    self._tokens -= tokens
                    return
                deficit = tokens - self._tokens
                wait_time = max(0.005, deficit / self.rate)
            await asyncio.sleep(wait_time)


class ReviewWorkerPool:
    """Bounded concurrent async worker pool utilizing Python 3.14 asyncio.TaskGroup."""

    def __init__(
        self,
        max_concurrency: int = 4,
        rate_limiter: TokenBucketRateLimiter | None = None,
        timeout_per_task: float | None = None,
    ) -> None:
        self.max_concurrency = max(1, int(max_concurrency))
        self.rate_limiter = rate_limiter
        self.timeout_per_task = timeout_per_task

    async def _execute_task[T, R](
        self,
        fn: Callable[[T], Coroutine[Any, Any, R]],
        item: T,
        index: int,
        results: list[Any],
        sem: asyncio.Semaphore,
        return_exceptions: bool,
    ) -> None:
        """Execute a single task bounded by semaphore and rate limiter."""
        async with sem:
            if self.rate_limiter is not None:
                await self.rate_limiter.acquire(1.0)
            try:
                coro = fn(item)
                if self.timeout_per_task is not None:
                    res = await asyncio.wait_for(coro, timeout=self.timeout_per_task)
                else:
                    res = await coro
                results[index] = res
            except Exception as exc:
                if return_exceptions:
                    results[index] = exc
                else:
                    raise

    async def submit_all[T, R](
        self,
        fn: Callable[[T], Coroutine[Any, Any, R]],
        items: Iterable[T],
        *,
        return_exceptions: bool = False,
    ) -> list[R | Exception]:
        """Concurrently execute coroutines across items using asyncio.TaskGroup."""
        items_list = list(items)
        if not items_list:
            return []

        results: list[Any] = [None] * len(items_list)
        sem = asyncio.Semaphore(self.max_concurrency)

        try:
            async with asyncio.TaskGroup() as tg:
                for idx, itm in enumerate(items_list):
                    tg.create_task(
                        self._execute_task(fn, itm, idx, results, sem, return_exceptions)
                    )
        except ExceptionGroup as eg:
            if not return_exceptions:
                if len(eg.exceptions) == 1:
                    raise eg.exceptions[0] from eg
                raise ReviewPoolError(str(eg), errors=list(eg.exceptions)) from eg

        return results

    async def submit_sync_all[T, R](
        self,
        fn: Callable[[T], R],
        items: Iterable[T],
        *,
        return_exceptions: bool = False,
    ) -> list[R | Exception]:
        """Concurrently execute synchronous worker functions delegated to threads."""

        async def _thread_worker(item: T) -> R:
            return await asyncio.to_thread(fn, item)

        return await self.submit_all(_thread_worker, items, return_exceptions=return_exceptions)

    def run_sync[T, R](
        self,
        fn: Callable[[T], Coroutine[Any, Any, R]],
        items: Iterable[T],
        *,
        return_exceptions: bool = False,
    ) -> list[R | Exception]:
        """Synchronously dispatch async submit_all, handling existing event loops safely."""
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        coro = self.submit_all(fn, items, return_exceptions=return_exceptions)
        if loop is not None and loop.is_running():
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool_exec:
                return pool_exec.submit(asyncio.run, coro).result()
        return asyncio.run(coro)

    def run_sync_all[T, R](
        self,
        fn: Callable[[T], R],
        items: Iterable[T],
        *,
        return_exceptions: bool = False,
    ) -> list[R | Exception]:
        """Synchronously dispatch synchronous worker functions via worker pool."""

        async def _thread_worker(item: T) -> R:
            return await asyncio.to_thread(fn, item)

        return self.run_sync(_thread_worker, items, return_exceptions=return_exceptions)


__all__ = [
    "ReviewPoolError",
    "ReviewWorkerPool",
    "TokenBucketRateLimiter",
]
