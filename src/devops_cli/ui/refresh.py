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
from collections.abc import Callable
from typing import Any

from devops_cli.config.constants import (
    CONST_DASHBOARD_DOMAIN_DOCKER,
    CONST_DASHBOARD_DOMAIN_TELEMETRY,
    CONST_DASHBOARD_DOMAIN_VALKEY,
)
from devops_cli.ui.data_providers import (
    fetch_docker_status,
    fetch_telemetry_status,
    fetch_valkey_status,
)
from devops_cli.ui.state import DashboardState, DomainSnapshot

logger = logging.getLogger(__name__)

DOMAIN_FETCHERS: dict[str, Callable[[], Any]] = {
    CONST_DASHBOARD_DOMAIN_DOCKER: fetch_docker_status,
    CONST_DASHBOARD_DOMAIN_TELEMETRY: fetch_telemetry_status,
    CONST_DASHBOARD_DOMAIN_VALKEY: fetch_valkey_status,
}


def refresh_domain(state: DashboardState, domain: str) -> DomainSnapshot | None:
    """Fetch one domain and publish the result, returning the snapshot.

    Returns ``None`` when a refresh for the domain is already running, so the caller knows
    nothing was published. Provider failures are published as errors rather than raised:
    this runs on a worker thread, where an escaping exception would terminate the refresh
    silently and leave the panel showing data that never updates again.
    """
    fetcher = DOMAIN_FETCHERS.get(domain)
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


__all__ = [
    "DOMAIN_FETCHERS",
    "refresh_domain",
]
