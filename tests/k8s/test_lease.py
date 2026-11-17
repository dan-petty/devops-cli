"""The handover of a Kubernetes Lease between two processes, over the fake of the Lease API (#6058).

Each holder runs the code of `devops_cli.k8s.lease` against the `cluster` fake, whose
`replace_namespaced_custom_object` refuses a write from an old `resourceVersion` as the API server
does (`tests/k8s/test_kubernetes_contract.py`). The holders read a monotonic clock that moves only
when a holder sleeps, so each test reads the seconds of the Lease that a pod would wait.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import pytest

from devops_cli.k8s.lease import (
    LEASE_GROUP,
    LEASE_PLURAL,
    LEASE_VERSION,
    LeaseHolder,
    LeaseTiming,
)
from tests.support.fakes.kubernetes import FakeCluster, api_exception, connection_refused

NAME = "roadmap-service-rows"
NAMESPACE = "devops"
TIMING = LeaseTiming()


class _LeaseClock:
    """The monotonic clock of the holders: each sleep of a holder moves it on by its seconds."""

    def __init__(self) -> None:
        self.now = 0.0
        self._marks: list[tuple[float, asyncio.Event]] = []

    def monotonic(self) -> float:
        return self.now

    async def sleep(self, seconds: float) -> None:
        self.now += seconds
        for mark, reached in self._marks:
            if self.now >= mark:
                reached.set()
        await asyncio.sleep(0)

    def reach(self, mark: float) -> asyncio.Event:
        """An event that a sleep sets when the clock reaches `mark`."""
        reached = asyncio.Event()
        self._marks.append((mark, reached))
        return reached


def _holder(identity: str, lease_clock: _LeaseClock) -> LeaseHolder:
    return LeaseHolder(
        NAME, NAMESPACE, identity, monotonic=lease_clock.monotonic, sleep=lease_clock.sleep
    )


def _stored(cluster: FakeCluster) -> dict[str, Any]:
    """The spec of the Lease that the fake holds."""
    (lease,) = cluster.custom_objects.objects[(LEASE_GROUP, LEASE_VERSION, LEASE_PLURAL)]
    spec: dict[str, Any] = lease["spec"]
    return spec


def test_a_pod_that_waits_takes_the_lease_only_after_the_holder_gives_it_back(
    cluster: FakeCluster,
) -> None:
    """The old pod creates the Lease and renews it through four Lease durations, and the new pod
    does not take it. After the old pod's drain, it gives the Lease back, and the new pod takes it
    at its next try: the holder changes one time."""
    lease_clock = _LeaseClock()
    old, new = _holder("pod-old", lease_clock), _holder("pod-new", lease_clock)

    async def handover() -> tuple[Any, ...]:
        await old.acquire()
        keeping = asyncio.create_task(old.keep())
        waiting = asyncio.create_task(new.acquire())
        await lease_clock.reach(4 * TIMING.duration).wait()
        during = (new.held, _stored(cluster)["holderIdentity"])
        keeping.cancel()
        await asyncio.gather(keeping, return_exceptions=True)
        given_back = await old.release()
        await waiting
        spec = _stored(cluster)
        return during, given_back, new.held, spec["holderIdentity"], spec["leaseTransitions"]

    assert asyncio.run(handover()) == ((False, "pod-old"), True, True, "pod-new", 1)


def test_a_killed_holder_loses_the_lease_after_its_duration(cluster: FakeCluster) -> None:
    """A killed holder renews nothing and gives nothing back. The other pod takes the Lease at its
    first try after `leaseDurationSeconds` from the time it first read the record of the holder,
    and not before. The killed holder cannot give back the Lease of the new holder."""
    lease_clock = _LeaseClock()
    killed, new = _holder("pod-killed", lease_clock), _holder("pod-new", lease_clock)

    async def takeover() -> tuple[Any, ...]:
        await killed.acquire()
        first_read = lease_clock.now
        await new.acquire()
        waited = lease_clock.now - first_read
        return waited, await killed.release(), _stored(cluster)["holderIdentity"]

    # The new pod tries each 2 s: at 14 s the Lease of 15 s still holds, at 16 s it has ended.
    assert asyncio.run(takeover()) == (16.0, False, "pod-new")


@pytest.mark.parametrize(
    ("refused", "error"),
    [
        pytest.param(
            "get_namespaced_custom_object",
            api_exception(503, "Service Unavailable"),
            id="read-refused",
        ),
        pytest.param("replace_namespaced_custom_object", connection_refused(), id="no-connection"),
    ],
)
def test_a_holder_whose_renewals_fail_stops_at_the_renew_deadline(
    cluster: FakeCluster, caplog: pytest.LogCaptureFixture, refused: str, error: Exception
) -> None:
    """When the API server refuses each renewal, or does not answer, `keep` returns at the renew
    deadline of 10 s. The holder then stops its work before the Lease of 15 s ends and another
    pod can take it. Each failed call is a warning that names the call."""
    lease_clock = _LeaseClock()
    holder = _holder("pod-a", lease_clock)

    async def lose() -> tuple[float, bool]:
        await holder.acquire()
        taken = lease_clock.now
        cluster.custom_objects.fail(refused, error)
        await holder.keep()
        return lease_clock.now - taken, holder.held

    with caplog.at_level(logging.WARNING, logger="devops_cli.k8s.lease"):
        lost = asyncio.run(lose())

    call = "read" if refused.startswith("get") else "update"
    failed = [m for m in caplog.messages if m.startswith(f"The {call} of the Lease")]
    assert (lost, len(failed)) == ((TIMING.renew_deadline, False), 5)


def test_a_pod_that_another_pod_beat_to_the_create_tries_again(cluster: FakeCluster) -> None:
    """Two pods that find no Lease both create it, and the API server refuses the second with
    409. That pod reads the Lease again at its next try."""
    lease_clock = _LeaseClock()
    late = _holder("pod-late", lease_clock)
    cluster.custom_objects.fail("create_namespaced_custom_object", api_exception(409, "Conflict"))

    async def race() -> tuple[bool, int, bool]:
        trying = asyncio.create_task(late.acquire())
        await lease_clock.reach(2 * TIMING.retry).wait()
        refused = late.held
        creates = [call for call, _ in cluster.custom_objects.calls if call.startswith("create")]
        cluster.custom_objects.failures.clear()
        await trying
        return refused, len(creates), late.held

    assert asyncio.run(race()) == (False, 2, True)


def test_a_release_that_meets_a_409_two_times_leaves_the_lease_to_its_duration(
    cluster: FakeCluster,
) -> None:
    """A renewal in flight can change the Lease between the read and the write of the release, so
    a 409 reads the Lease again one time. A second 409 leaves the Lease to end after its
    duration."""
    holder = _holder("pod-a", _LeaseClock())

    async def release() -> bool:
        await holder.acquire()
        cluster.custom_objects.fail(
            "replace_namespaced_custom_object", api_exception(409, "Conflict")
        )
        return await holder.release()

    given_back = asyncio.run(release())

    replaces = [call for call, _ in cluster.custom_objects.calls if call.startswith("replace")]
    assert (given_back, len(replaces), _stored(cluster)["holderIdentity"]) == (False, 2, "pod-a")


def test_a_process_that_does_not_hold_the_lease_gives_nothing_back(cluster: FakeCluster) -> None:
    holder = _holder("pod-a", _LeaseClock())

    assert (asyncio.run(holder.release()), cluster.custom_objects.calls) == (False, [])
