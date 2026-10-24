"""Contract suite for the clock waiting seam (`devops_cli.core.clock`) and `ClockFake` (#1320).

Each contract case runs against both the fake (`clock` fixture) and the real seam (`time.sleep` and
`time.monotonic`), the real side with 10-50 ms waits so every case finishes well under 1 s.
"""

from __future__ import annotations

import time
from datetime import UTC, datetime

import httpx2
import pytest
from tenacity import wait_chain, wait_fixed

from devops_cli.ai.retries import create_retry_config, create_retry_transport
from devops_cli.core import clock as clock_seam
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


@pytest.mark.parametrize(("mode", "duration"), [("fake", 1.5), ("real", 0.02)])
def test_a_sync_wait_advances_the_monotonic_clock_by_at_least_its_duration(
    request: pytest.FixtureRequest, mode: str, duration: float
) -> None:
    """After a sync wait of `duration`, `clock_seam.monotonic()` has advanced by at least
    `duration`, and the fake records the wait."""
    fake = _install_mode(request, mode)
    before_mono = clock_seam.monotonic()

    clock_seam.sleep(duration)

    after_mono = clock_seam.monotonic()
    assert (
        after_mono - before_mono >= duration - _TOLERANCE,
        fake.waits if fake is not None else [duration],
    ) == (True, [duration])
