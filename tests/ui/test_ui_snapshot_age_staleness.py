"""Tests for Snapshot Age & Staleness behaviour in reactive dashboard."""

from __future__ import annotations

from devops_cli.ui.state import DashboardState, DomainSnapshot
from tests.support.ui import (
    _valkey,
)


def test_a_never_loaded_snapshot_reports_zero_age() -> None:
    """Age is meaningless before the first successful fetch."""
    snapshot = DomainSnapshot(domain="valkey")
    assert (snapshot.age, snapshot.never_loaded) == (0.0, True)


def test_an_errored_snapshot_retains_the_age_of_the_data_it_shows(
    state: DashboardState,
) -> None:
    """The banner must age from when the data was fetched, not when the error occurred."""
    state.publish("valkey", _valkey())
    fetched_at = state.get("valkey").updated_at
    snapshot = state.publish_error("valkey", "down")
    assert snapshot.updated_at == fetched_at
