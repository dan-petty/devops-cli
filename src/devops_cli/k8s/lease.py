"""A Kubernetes Lease that one process holds at a time (#6058).

The roadmap Service runs its rows only in the pod that holds the Lease `roadmap-service-rows`, so
the old pod and the new pod of a surge release do not run a row at the same time
(docs/SERVICE_PATTERNS.md, WK2). `LeaseHolder` applies the rules of the leader election of
client-go (`k8s.io/client-go/tools/leaderelection`) to a `coordination.k8s.io/v1` Lease:

- A process takes a Lease that does not exist, that has no holder, or whose holder did not renew
  it for its `leaseDurationSeconds`. The process measures that time on its own monotonic clock,
  from the time it first read that record of the holder, so the clocks of two nodes need not
  agree.
- Each write sends the `resourceVersion` that the process read. When two processes write at the
  same time, the API server refuses one of them with 409.
- The holder renews the Lease each retry period. When no renewal works for the renew deadline,
  `keep` returns, and the caller stops its work before another process can take the Lease.
- `release` gives the Lease back with no holder, as `ReleaseOnCancel` of client-go does, so a
  process that waits takes it within one retry period.

The tool: the official `kubernetes` client 36.0.3 of the project has a leader election
(`kubernetes.leaderelection`) with a ConfigMap lock only, a thread loop that does not stop, and
no release. Client 37 adds a Lease lock, but it also moves each model of the client to pydantic,
and its loop also has no stop and no release. So this module makes the three calls of client-go
(read, create, replace) through the `CustomObjectsApi` seam of `k8s/api.py`, which the fake
cluster of the tests also serves. #4575 removes the Lease of the rows with the rows of the pod.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from devops_cli.config.constants import (
    CONST_SERVICE_ROWS_LEASE_CALL_TIMEOUT_SECONDS,
    CONST_SERVICE_ROWS_LEASE_DURATION_SECONDS,
    CONST_SERVICE_ROWS_LEASE_RENEW_DEADLINE_SECONDS,
    CONST_SERVICE_ROWS_LEASE_RETRY_SECONDS,
)
from devops_cli.exceptions.k8s import KubernetesContextError
from devops_cli.k8s.api import CustomObjectsApi, api_error_type
from devops_cli.k8s.service import KubernetesService
from devops_cli.lang import MESSAGES

logger = logging.getLogger(__name__)

LEASE_GROUP = "coordination.k8s.io"
LEASE_VERSION = "v1"
LEASE_PLURAL = "leases"
_NOT_FOUND = 404
_CONFLICT = 409


@dataclass(frozen=True)
class LeaseTiming:
    """The times of a Lease, in seconds. The holder writes `duration` as `leaseDurationSeconds`.
    It stops its work when no renewal worked for `renew_deadline`. A process tries again after
    `retry`, and one API call ends after `call_timeout`. Each time is shorter than the time that
    holds it: a call ends before the renew deadline, and the holder stops before another process
    can take the Lease."""

    duration: int = CONST_SERVICE_ROWS_LEASE_DURATION_SECONDS
    renew_deadline: float = CONST_SERVICE_ROWS_LEASE_RENEW_DEADLINE_SECONDS
    retry: float = CONST_SERVICE_ROWS_LEASE_RETRY_SECONDS
    call_timeout: float = CONST_SERVICE_ROWS_LEASE_CALL_TIMEOUT_SECONDS


def _micro_time(moment: datetime) -> str:
    """`moment` as a `MicroTime` of the Kubernetes API: RFC 3339 in UTC, with microseconds."""
    return moment.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _call_errors() -> tuple[type[Exception], ...]:
    """The errors of one call: the reply of the API server, no configuration, or no connection."""
    from urllib3.exceptions import HTTPError

    return (api_error_type(), KubernetesContextError, HTTPError, OSError)


def _described(error: Exception) -> str:
    """The status and the reason of a reply of the API server, else the first line of `error`."""
    status = getattr(error, "status", None)
    if status is not None:
        return f"HTTP {status} {getattr(error, 'reason', '') or ''}".strip()
    return (str(error).splitlines() or [""])[0][:200]


class LeaseHolder:
    """The hold of this process on the Lease `name` in `namespace`, as `identity`.

    `acquire` waits until this process holds the Lease. `keep` renews it and returns when this
    process holds it no more. `release` gives it back. The calls of the API run in a thread, each
    with `timing.call_timeout`, so the event loop keeps serving while a call waits.
    """

    def __init__(
        self,
        name: str,
        namespace: str,
        identity: str,
        *,
        timing: LeaseTiming | None = None,
        service: KubernetesService | None = None,
        monotonic: Callable[[], float] = time.monotonic,
        now: Callable[[], datetime] = lambda: datetime.now(UTC),
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self.name = name
        self.namespace = namespace
        self.identity = identity
        self.timing = timing or LeaseTiming()
        self._service = service
        self._monotonic = monotonic
        self._now = now
        self._sleep = sleep
        self._held = False
        self._renewed_at = 0.0
        self._observed: dict[str, Any] | None = None
        self._observed_at = 0.0
        self._waiting_for: str | None = None

    @property
    def held(self) -> bool:
        """Whether this process held the Lease at its last read or write."""
        return self._held

    async def acquire(self) -> None:
        """Return when this process holds the Lease. Until then, try again each retry period."""
        while not await self._try():
            await self._sleep(self.timing.retry)

    async def keep(self) -> None:
        """Renew the Lease each retry period, and return when this process holds it no more:
        another process holds it, or no renewal worked for the renew deadline. The caller then
        stops the work that the Lease guards."""
        while self._held:
            await self._sleep(self.timing.retry)
            if await self._try():
                continue
            if self._monotonic() - self._renewed_at >= self.timing.renew_deadline:
                self._held = False

    async def release(self) -> bool:
        """Give the Lease back when this process holds it: write it with no holder and a duration
        of 1 s, as `ReleaseOnCancel` of client-go does. Return whether the Lease was given back.
        A renewal that was in flight when the caller stopped `keep` can make the first write a
        409, so a 409 reads the Lease again one time. When a call fails, the Lease ends after its
        duration."""
        if not self._held:
            return False
        self._held = False
        retried = False
        while True:
            try:
                lease = await asyncio.to_thread(self._read)
                spec = dict(lease.get("spec") or {})
                if spec.get("holderIdentity") != self.identity:
                    return False
                stamp = _micro_time(self._now())
                lease["spec"] = {
                    **spec,
                    "holderIdentity": None,
                    "leaseDurationSeconds": 1,
                    "acquireTime": stamp,
                    "renewTime": stamp,
                }
                await asyncio.to_thread(self._replace, lease)
            except _call_errors() as error:
                if retried or getattr(error, "status", None) != _CONFLICT:
                    self._report("release", error)
                    return False
                retried = True
                continue
            logger.info(
                MESSAGES.k8s.lease_given_back.format(
                    identity=self.identity, namespace=self.namespace, name=self.name
                )
            )
            return True

    async def _try(self) -> bool:
        """Take or renew the Lease one time. Return whether this process holds it now."""
        try:
            lease = await asyncio.to_thread(self._read)
        except _call_errors() as error:
            if getattr(error, "status", None) != _NOT_FOUND:
                self._report("read", error)
                return False
            return await self._create()
        spec = dict(lease.get("spec") or {})
        holder = spec.get("holderIdentity") or None
        if spec != self._observed:
            self._observed, self._observed_at = spec, self._monotonic()
        if holder is not None and holder != self.identity:
            duration = float(spec.get("leaseDurationSeconds") or self.timing.duration)
            if self._monotonic() - self._observed_at < duration:
                self._held = False
                self._wait_for(holder)
                return False
        ours = holder == self.identity
        stamp = _micro_time(self._now())
        transitions = int(spec.get("leaseTransitions") or 0)
        lease["spec"] = {
            "holderIdentity": self.identity,
            "leaseDurationSeconds": self.timing.duration,
            "acquireTime": (spec.get("acquireTime") or stamp) if ours else stamp,
            "renewTime": stamp,
            "leaseTransitions": transitions if ours else transitions + 1,
        }
        try:
            await asyncio.to_thread(self._replace, lease)
        except _call_errors() as error:
            self._report("update", error)
            return False
        return self._took(lease["spec"])

    async def _create(self) -> bool:
        """Create the Lease with this process as its holder. A 409 means that another process
        created it first."""
        stamp = _micro_time(self._now())
        spec: dict[str, Any] = {
            "holderIdentity": self.identity,
            "leaseDurationSeconds": self.timing.duration,
            "acquireTime": stamp,
            "renewTime": stamp,
            "leaseTransitions": 0,
        }
        body = {
            "apiVersion": f"{LEASE_GROUP}/{LEASE_VERSION}",
            "kind": "Lease",
            "metadata": {"name": self.name, "namespace": self.namespace},
            "spec": spec,
        }
        try:
            await asyncio.to_thread(self._create_body, body)
        except _call_errors() as error:
            self._report("create", error)
            return False
        return self._took(spec)

    def _took(self, spec: dict[str, Any]) -> bool:
        """Record that this process wrote `spec` as the holder, and log the first time."""
        first = not self._held
        self._held = True
        self._renewed_at = self._monotonic()
        self._observed, self._observed_at = spec, self._renewed_at
        self._waiting_for = None
        if first:
            logger.info(
                MESSAGES.k8s.lease_taken.format(
                    identity=self.identity, namespace=self.namespace, name=self.name
                )
            )
        return True

    def _wait_for(self, holder: str) -> None:
        """Log one time for each holder that this process waits for."""
        if holder != self._waiting_for:
            self._waiting_for = holder
            logger.info(
                MESSAGES.k8s.lease_held_by_other.format(
                    namespace=self.namespace, name=self.name, holder=holder, identity=self.identity
                )
            )

    def _report(self, call: str, error: Exception) -> None:
        logger.warning(
            MESSAGES.k8s.lease_call_failed.format(
                call=call,
                namespace=self.namespace,
                name=self.name,
                identity=self.identity,
                seconds=f"{self.timing.retry:g}",
                kind=type(error).__name__,
                error=_described(error),
            )
        )

    def _api(self) -> CustomObjectsApi:
        return (self._service or KubernetesService.get_instance()).custom_objects_api()

    def _read(self) -> dict[str, Any]:
        lease: dict[str, Any] = self._api().get_namespaced_custom_object(
            LEASE_GROUP,
            LEASE_VERSION,
            self.namespace,
            LEASE_PLURAL,
            self.name,
            _request_timeout=self.timing.call_timeout,
        )
        return lease

    def _create_body(self, body: dict[str, Any]) -> None:
        self._api().create_namespaced_custom_object(
            LEASE_GROUP,
            LEASE_VERSION,
            self.namespace,
            LEASE_PLURAL,
            body,
            _request_timeout=self.timing.call_timeout,
        )

    def _replace(self, lease: dict[str, Any]) -> None:
        self._api().replace_namespaced_custom_object(
            LEASE_GROUP,
            LEASE_VERSION,
            self.namespace,
            LEASE_PLURAL,
            self.name,
            lease,
            _request_timeout=self.timing.call_timeout,
        )


__all__ = ["LEASE_GROUP", "LEASE_PLURAL", "LEASE_VERSION", "LeaseHolder", "LeaseTiming"]
