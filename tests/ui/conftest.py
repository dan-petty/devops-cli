"""Package fixtures for the reactive dashboard UI tests."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from typing import Any
from unittest.mock import MagicMock

import pytest

import devops_cli.ui.refresh as refresh_module
from devops_cli.config.constants import CONST_DASHBOARD_DOMAINS
from devops_cli.ui.state import DashboardState
from tests.support.ui import SAMPLES


@pytest.fixture
def state() -> DashboardState:
    """Provide an empty dashboard state store."""
    return DashboardState()


@pytest.fixture
def empty_docker_engine(docker_engine: Any) -> Iterator[Any]:
    """Serve the dashboard's Docker provider from the shared engine double, holding nothing."""
    client = MagicMock()
    client.info.return_value = {}
    with docker_engine(client) as engine:
        yield engine


@pytest.fixture
def patched_fetchers(monkeypatch: pytest.MonkeyPatch) -> Callable[..., None]:
    """Replace the live providers so the dashboard refreshes deterministically.

    The app performs one refresh on mount regardless of the auto-refresh interval, so a
    test that does not control the providers is racing real network calls.
    """

    def apply(**overrides: Callable[[], Any]) -> None:
        fetchers = {domain: SAMPLES[domain] for domain in CONST_DASHBOARD_DOMAINS}
        fetchers.update(overrides)
        monkeypatch.setattr(refresh_module, "DOMAIN_FETCHERS", fetchers)

    return apply
