"""Contract suite for the clock waiting seam (`devops_cli.core.clock`) and `ClockFake` (#1320).

Each contract case runs against both the fake (`clock` fixture) and the real seam (`time.sleep`,
`asyncio.sleep`, `time.monotonic`), the real side with 10-50 ms waits so every case finishes well
under 1 s.
"""

from __future__ import annotations

import asyncio
import subprocess
import time
from datetime import UTC, datetime
from unittest.mock import patch

import httpx2
import pytest
from ratelimit import limits, sleep_and_retry
from tenacity import wait_chain, wait_fixed

from devops_cli.ai.retries import (
    create_async_retry_transport,
    create_retry_config,
    create_retry_transport,
)
from devops_cli.core import clock as clock_seam
from devops_cli.github.rate_limiter import reset_github_rate_limiter, run_gh
from tests.support.fakes.clock import ClockFake

_TOLERANCE = 1e-3


def _install_mode(request: pytest.FixtureRequest, mode: str) -> ClockFake | None:
    if mode == "fake":
        fake: ClockFake = request.getfixturevalue("clock")
        return fake
    return None


@pytest.mark.parametrize(("mode", "duration"), [("fake", 1.5), ("real", 0.02)])
def test_a_sync_wait_advances_the_wall_clock_by_at_least_its_duration(
    request: pytest.FixtureRequest, mode: str, duration: float
) -> None:
    """After a sync wait of `duration`, `time.time()` and `datetime.now(UTC)` have advanced by at
    least `duration`, and the fake records the wait."""
    fake = _install_mode(request, mode)
    before_epoch = time.time()
    before_dt = datetime.now(UTC)

    clock_seam.sleep(duration)

    after_epoch = time.time()
    after_dt = datetime.now(UTC)
    assert (
        after_epoch - before_epoch >= duration - _TOLERANCE,
        (after_dt - before_dt).total_seconds() >= duration - _TOLERANCE,
        fake.waits if fake is not None else [duration],
    ) == (True, True, [duration])


@pytest.mark.parametrize(("mode", "duration"), [("fake", 2.5), ("real", 0.02)])
@pytest.mark.asyncio
async def test_an_async_wait_advances_the_wall_clock_by_at_least_its_duration(
    request: pytest.FixtureRequest, mode: str, duration: float
) -> None:
    """After an async wait of `duration`, `time.time()` and `datetime.now(UTC)` have advanced by
    at least `duration`, and `asyncio.sleep` itself is untouched by the fake."""
    fake = _install_mode(request, mode)
    before_epoch = time.time()
    before_dt = datetime.now(UTC)

    answered = await clock_seam.async_sleep(duration, "done")
    await asyncio.sleep(0)

    after_epoch = time.time()
    after_dt = datetime.now(UTC)
    assert (
        answered,
        after_epoch - before_epoch >= duration - _TOLERANCE,
        (after_dt - before_dt).total_seconds() >= duration - _TOLERANCE,
        fake.waits if fake is not None else [duration],
    ) == ("done", True, True, [duration])


@pytest.mark.parametrize(
    ("mode", "waits"),
    [("fake", (1.0, 2.0)), ("real", (0.015, 0.025))],
)
def test_a_sync_tenacity_retry_with_fixed_waits_waits_those_amounts_in_order(
    request: pytest.FixtureRequest, mode: str, waits: tuple[float, float]
) -> None:
    """`create_retry_transport` routes tenacity's sync waits through the seam in order."""
    fake = _install_mode(request, mode)
    d1, d2 = waits
    stamps: list[float] = []

    class ThreeStepTransport(httpx2.BaseTransport):
        def handle_request(self, req: httpx2.Request) -> httpx2.Response:
            stamps.append(time.time())
            status = 503 if len(stamps) < 3 else 200
            return httpx2.Response(status, json={"attempt": len(stamps)}, request=req)

    config = create_retry_config(max_attempts=3, wait=wait_chain(wait_fixed(d1), wait_fixed(d2)))
    transport = create_retry_transport(config=config, wrapped=ThreeStepTransport())
    with httpx2.Client(transport=transport) as client:
        response = client.get("https://example.com/sync")

    gaps = [stamps[1] - stamps[0], stamps[2] - stamps[1]]
    assert (
        response.status_code,
        len(stamps),
        gaps[0] >= d1 - _TOLERANCE,
        gaps[1] >= d2 - _TOLERANCE,
        fake.waits if fake is not None else [d1, d2],
    ) == (200, 3, True, True, [d1, d2])


@pytest.mark.parametrize(
    ("mode", "waits"),
    [("fake", (1.0, 2.0)), ("real", (0.015, 0.025))],
)
@pytest.mark.asyncio
async def test_an_async_tenacity_retry_with_fixed_waits_waits_those_amounts_in_order(
    request: pytest.FixtureRequest, mode: str, waits: tuple[float, float]
) -> None:
    """`create_async_retry_transport` routes tenacity's async waits through the seam in order."""
    fake = _install_mode(request, mode)
    d1, d2 = waits
    stamps: list[float] = []

    class ThreeStepAsyncTransport(httpx2.AsyncBaseTransport):
        async def handle_async_request(self, req: httpx2.Request) -> httpx2.Response:
            stamps.append(time.time())
            status = 503 if len(stamps) < 3 else 200
            return httpx2.Response(status, json={"attempt": len(stamps)}, request=req)

    config = create_retry_config(max_attempts=3, wait=wait_chain(wait_fixed(d1), wait_fixed(d2)))
    transport = create_async_retry_transport(config=config, wrapped=ThreeStepAsyncTransport())
    async with httpx2.AsyncClient(transport=transport) as client:
        response = await client.get("https://example.com/async")

    gaps = [stamps[1] - stamps[0], stamps[2] - stamps[1]]
    assert (
        response.status_code,
        len(stamps),
        gaps[0] >= d1 - _TOLERANCE,
        gaps[1] >= d2 - _TOLERANCE,
        fake.waits if fake is not None else [d1, d2],
    ) == (200, 3, True, True, [d1, d2])


@pytest.mark.parametrize(("mode", "period"), [("fake", 60.0), ("real", 0.03)])
def test_a_ratelimit_window_built_with_the_seam_makes_the_third_call_wait_out_the_period(
    request: pytest.FixtureRequest, mode: str, period: float
) -> None:
    """`ratelimit.limits(calls=2, period=period, clock=clock_seam.monotonic)` lets the first two
    calls through and holds the third until `period` ends."""
    fake = _install_mode(request, mode)
    stamps: list[float] = []
    window = limits(calls=2, period=period, clock=clock_seam.monotonic)
    call = sleep_and_retry(window(lambda: stamps.append(time.time())))

    for _ in range(3):
        call()

    assert (
        len(stamps),
        stamps[1] - stamps[0] < period / 2,
        stamps[2] - stamps[0] >= period - _TOLERANCE,
        fake.waits if fake is not None else [period],
    ) == (3, True, True, [period])


def test_the_github_rate_limiter_builds_its_burst_limit_with_the_seam_when_constructed(
    clock: ClockFake,
) -> None:
    """Each `GitHubRateLimiter` builds its 60-calls-per-60s burst limit with `clock_seam.monotonic`
    when constructed, so the 61st exempt call in one window waits 60 s and a fresh limiter starts
    its own window."""
    reset_github_rate_limiter()
    payload = '{"resources": {"core": {"limit": 5000, "remaining": 5000, "reset": 1999999999}}}'
    answer = subprocess.CompletedProcess(["gh", "api", "rate_limit"], 0, payload, "")
    with patch("devops_cli.github.rate_limiter.run_subprocess", return_value=answer):
        for _ in range(61):
            run_gh(["api", "rate_limit"])
        reset_github_rate_limiter()
        run_gh(["api", "rate_limit"])

    assert clock.waits == [60.0]
