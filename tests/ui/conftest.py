"""Package fixtures for the reactive dashboard UI tests.

A conftest loads before the root conftest isolates HOME when a run names a file under this
directory, as a test shard does (#2371). So this module imports no devops-cli module at its top:
devops-cli binds its paths under HOME when it is first imported.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock

import pytest

if TYPE_CHECKING:
    from devops_cli.ui.state import DashboardState


@pytest.fixture
def state() -> DashboardState:
    """Provide an empty dashboard state store."""
    from devops_cli.ui.state import DashboardState

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

    import devops_cli.ui.refresh as refresh_module
    from devops_cli.config.constants import CONST_DASHBOARD_DOMAINS
    from tests.support.ui import SAMPLES

    def apply(**overrides: Callable[[], Any]) -> None:
        fetchers = {domain: SAMPLES[domain] for domain in CONST_DASHBOARD_DOMAINS}
        fetchers.update(overrides)
        monkeypatch.setattr(refresh_module, "DOMAIN_FETCHERS", fetchers)

    return apply
