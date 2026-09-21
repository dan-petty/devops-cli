"""Thread-safe dashboard state store.

Refreshes previously ran as five synchronous network fetches on the UI thread, so a slow
cluster froze the whole interface until every call returned. Moving them to worker threads
means several threads now publish results while the UI thread reads them, which is exactly
the situation an unguarded shared dict gets wrong.

This store owns that shared state: workers publish domain snapshots, the UI reads
consistent values, and neither blocks the other for longer than a dict assignment.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from devops_cli.config.constants import CONST_DASHBOARD_DOMAINS
from devops_cli.config.defaults import DEFAULT_DASHBOARD_STALE_SECONDS


@dataclass(frozen=True)
class DomainSnapshot:
    """The most recent result for one dashboard domain."""

    domain: str
    data: Any = None
    updated_at: float = 0.0
    error: str | None = None

    @property
    def never_loaded(self) -> bool:
        """Report whether the domain has never produced a successful result."""
        return self.updated_at == 0.0

    @property
    def age(self) -> float:
        """Seconds since this domain last produced data, or 0.0 if it never has."""
        if self.never_loaded:
            return 0.0
        return max(0.0, time.time() - self.updated_at)

    def is_stale(self, max_age: float = DEFAULT_DASHBOARD_STALE_SECONDS) -> bool:
        """Report whether the displayed data has aged past a threshold.

        A domain that has never loaded is not stale — it is empty, which the UI renders
        differently. Conflating the two would show a staleness warning over a blank panel.
        """
        return not self.never_loaded and self.age >= max_age

    @property
    def ok(self) -> bool:
        """Report whether the last refresh for this domain succeeded."""
        return self.error is None and not self.never_loaded


@dataclass
class DashboardState:
    """Shared state published by refresh workers and read by the UI.

    Subscribers are notified outside the lock, so a slow listener cannot stall a worker
    that is merely trying to publish its result.
    """

    _snapshots: dict[str, DomainSnapshot] = field(default_factory=dict)
    _lock: threading.RLock = field(default_factory=threading.RLock)
    _subscribers: list[Callable[[DomainSnapshot], None]] = field(default_factory=list)
    _inflight: set[str] = field(default_factory=set)

    def begin_refresh(self, domain: str) -> bool:
        """Claim the right to refresh a domain, reporting whether the claim succeeded.

        The refresh timer fires on a fixed interval, but a fetch against an unreachable
        cluster can outlast several ticks. Without this claim each tick would start another
        thread against the same dead endpoint, so the slowest domain accumulates workers
        for as long as it stays slow. A tick that finds a refresh already running skips it.
        """
        with self._lock:
            if domain in self._inflight:
                return False
            self._inflight.add(domain)
            return True

    def finish_refresh(self, domain: str) -> None:
        """Release a refresh claim, allowing the next tick to fetch the domain again."""
        with self._lock:
            self._inflight.discard(domain)

    def in_flight(self) -> list[str]:
        """List domains with a refresh currently running."""
        with self._lock:
            return sorted(self._inflight)

    def publish(self, domain: str, data: Any) -> DomainSnapshot:
        """Record a successful refresh for a domain and notify subscribers."""
        snapshot = DomainSnapshot(domain=domain, data=data, updated_at=time.time())
        self._store(snapshot)
        self._notify(snapshot)
        return snapshot

    def publish_error(self, domain: str, error: str) -> DomainSnapshot:
        """Record a failed refresh, preserving the previous data for display.

        A transient cluster failure should dim the panel rather than blank it: the last
        known state is more useful than nothing while the next refresh is attempted.
        """
        with self._lock:
            previous = self._snapshots.get(domain)
        snapshot = DomainSnapshot(
            domain=domain,
            data=previous.data if previous else None,
            updated_at=previous.updated_at if previous else 0.0,
            error=error[:256],
        )
        self._store(snapshot)
        self._notify(snapshot)
        return snapshot

    def _store(self, snapshot: DomainSnapshot) -> None:
        """Commit a snapshot under the lock."""
        with self._lock:
            self._snapshots[snapshot.domain] = snapshot

    def _notify(self, snapshot: DomainSnapshot) -> None:
        """Notify subscribers outside the lock, isolating listener failures."""
        with self._lock:
            listeners = list(self._subscribers)
        for listener in listeners:
            try:
                listener(snapshot)
            except Exception:
                # A broken listener must not abort the publish or the worker behind it.
                continue

    def get(self, domain: str) -> DomainSnapshot:
        """Return the latest snapshot for a domain, or an empty one when never fetched."""
        with self._lock:
            return self._snapshots.get(domain) or DomainSnapshot(domain=domain)

    def snapshots(self) -> dict[str, DomainSnapshot]:
        """Return a consistent copy of every domain snapshot."""
        with self._lock:
            return dict(self._snapshots)

    def subscribe(self, listener: Callable[[DomainSnapshot], None]) -> Callable[[], None]:
        """Register a listener, returning a callable that unsubscribes it."""
        with self._lock:
            self._subscribers.append(listener)

        def _unsubscribe() -> None:
            with self._lock:
                if listener in self._subscribers:
                    self._subscribers.remove(listener)

        return _unsubscribe

    def pending_domains(self) -> list[str]:
        """List domains that have never produced a successful result."""
        with self._lock:
            return sorted(
                domain
                for domain in CONST_DASHBOARD_DOMAINS
                if domain not in self._snapshots or self._snapshots[domain].never_loaded
            )

    def failed_domains(self) -> list[str]:
        """List domains whose most recent refresh failed."""
        with self._lock:
            return sorted(
                domain for domain, snap in self._snapshots.items() if snap.error is not None
            )

    def clear(self) -> None:
        """Discard all snapshots, leaving subscribers registered."""
        with self._lock:
            self._snapshots.clear()


__all__ = [
    "DashboardState",
    "DomainSnapshot",
]
