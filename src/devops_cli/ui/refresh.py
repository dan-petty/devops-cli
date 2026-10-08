"""Domain refresh coordination for the dashboard.

The dashboard used to refresh by calling five provider functions in sequence directly on
the UI thread, so the interface was unresponsive for the sum of five network round trips
and a single unreachable cluster froze every unrelated tab.

This module holds the part of refreshing that has nothing to do with Textual: which
fetcher serves which domain, how a failure becomes a snapshot instead of a traceback, and
how repeated ticks against a slow endpoint are prevented from stacking up. Keeping it
here means the behaviour can be tested without running an app.
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable, Iterable, Sequence
from typing import TYPE_CHECKING, Any

from devops_cli.config.constants import (
    CONST_DASHBOARD_DOMAIN_AI,
    CONST_DASHBOARD_DOMAIN_DOCKER,
    CONST_DASHBOARD_DOMAIN_K8S,
    CONST_DASHBOARD_DOMAIN_TELEMETRY,
    CONST_DASHBOARD_DOMAIN_VALKEY,
    CONST_DASHBOARD_DOMAINS,
)
from devops_cli.config.defaults import DEFAULT_LOG_TAIL_LINES
from devops_cli.ui.data_providers import (
    fetch_docker_status,
    fetch_k8s_status,
    fetch_review_status,
    fetch_telemetry_status,
    fetch_valkey_status,
)
from devops_cli.ui.state import DashboardState, DomainSnapshot

if TYPE_CHECKING:
    from devops_cli.k8s.service import PodLogStream

logger = logging.getLogger(__name__)

DOMAIN_FETCHERS: dict[str, Callable[[], Any]] = {
    CONST_DASHBOARD_DOMAIN_K8S: fetch_k8s_status,
    CONST_DASHBOARD_DOMAIN_DOCKER: fetch_docker_status,
    CONST_DASHBOARD_DOMAIN_TELEMETRY: fetch_telemetry_status,
    CONST_DASHBOARD_DOMAIN_AI: fetch_review_status,
    CONST_DASHBOARD_DOMAIN_VALKEY: fetch_valkey_status,
}


def refresh_domain(
    state: DashboardState,
    domain: str,
    fetchers: dict[str, Callable[[], Any]] | None = None,
) -> DomainSnapshot | None:
    """Fetch one domain and publish the result, returning the snapshot.

    Returns ``None`` when a refresh for the domain is already running, so the caller knows
    nothing was published. Provider failures are published as errors rather than raised:
    this runs on a worker thread, where an escaping exception would terminate the refresh
    silently and leave the panel showing data that never updates again.
    """
    table = DOMAIN_FETCHERS if fetchers is None else fetchers
    fetcher = table.get(domain)
    if fetcher is None:
        return state.publish_error(domain, f"No provider registered for domain '{domain}'")

    if not state.begin_refresh(domain):
        return None
    try:
        data = fetcher()
    except Exception as exc:
        logger.debug("Dashboard refresh failed for domain %s: %s", domain, exc)
        return state.publish_error(domain, f"{type(exc).__name__}: {exc}")
    else:
        return state.publish(domain, data)
    finally:
        state.finish_refresh(domain)


def refresh_all(
    state: DashboardState,
    domains: Sequence[str] = CONST_DASHBOARD_DOMAINS,
    fetchers: dict[str, Callable[[], Any]] | None = None,
) -> list[DomainSnapshot]:
    """Refresh every domain in sequence, returning the snapshots that were published.

    Callers wanting concurrency run :func:`refresh_domain` per domain on its own worker;
    this exists for the non-interactive summary path, where sequential is correct.
    """
    published = [refresh_domain(state, domain, fetchers) for domain in domains]
    return [snapshot for snapshot in published if snapshot is not None]


__all__ = [
    "DOMAIN_FETCHERS",
    "PodLogSource",
    "pod_log_source",
    "refresh_all",
    "refresh_domain",
]


class PodLogSource:
    """One container's log lines, followed live, opened when called and closable at any time.

    The stream is opened when the source is called rather than when it is built, so the
    blocking connection is established on the worker thread that consumes it and never on
    the UI thread. Closing it ends a read blocked on a quiet container, so a replaced
    stream gives back its connection and thread; a source closed before its stream opened
    closes the stream as soon as it does.
    """

    def __init__(self, pod: str, namespace: str, container: str | None, tail_lines: int) -> None:
        self.pod, self.namespace, self.container = pod, namespace, container
        self.tail_lines = tail_lines
        self._lock = threading.Lock()
        self._stream: PodLogStream | None = None
        self._closed = False

    def __call__(self) -> Iterable[str]:
        from devops_cli.k8s.service import KubernetesService

        stream = KubernetesService.get_instance().read_pod_logs(
            pod=self.pod,
            namespace=self.namespace,
            container=self.container,
            tail_lines=self.tail_lines,
            follow=True,
        )
        with self._lock:
            self._stream, closed = stream, self._closed
        if closed:
            stream.close()
        return stream

    def close(self) -> None:
        """Stop the stream, now if it is open or else as soon as it opens."""
        with self._lock:
            self._closed, stream = True, self._stream
        if stream is not None:
            stream.close()


def pod_log_source(
    pod: str,
    namespace: str,
    container: str | None = None,
    tail_lines: int = DEFAULT_LOG_TAIL_LINES,
) -> PodLogSource:
    """Build the source of one container's log lines, followed live.

    A pod with more than one container needs the container named: the API server answers
    400 otherwise.
    """
    return PodLogSource(pod, namespace, container, tail_lines)
