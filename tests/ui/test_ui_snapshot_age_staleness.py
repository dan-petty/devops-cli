"""Tests for Snapshot Age & Staleness behaviour in reactive dashboard."""

from __future__ import annotations

import time

from devops_cli.ui.state import DashboardState, DomainSnapshot
from tests.support.ui import (
    _valkey,
)


def test_a_never_loaded_snapshot_reports_zero_age() -> None:
    """Age is meaningless before the first successful fetch."""
    snapshot = DomainSnapshot(domain="valkey")
    assert (snapshot.age, snapshot.never_loaded) == (0.0, True)


def test_a_never_loaded_snapshot_is_not_reported_as_stale() -> None:
    """Empty and stale are rendered differently, so they must not be conflated."""
    assert DomainSnapshot(domain="valkey").is_stale(max_age=0.0) is False


def test_a_snapshot_ages_past_its_threshold() -> None:
    """Data fetched long ago is flagged stale."""
    old = DomainSnapshot(domain="valkey", data=_valkey(), updated_at=time.time() - 120.0)
    assert (old.is_stale(max_age=30.0), old.is_stale(max_age=600.0)) == (True, False)


def test_a_freshly_published_snapshot_is_not_stale(state: DashboardState) -> None:
    """A just-published snapshot falls inside any sane threshold."""
    snapshot = state.publish("valkey", _valkey())
    assert snapshot.is_stale(max_age=30.0) is False


def test_an_errored_snapshot_retains_the_age_of_the_data_it_shows(
    state: DashboardState,
) -> None:
    """The banner must age from when the data was fetched, not when the error occurred."""
    state.publish("valkey", _valkey())
    fetched_at = state.get("valkey").updated_at
    snapshot = state.publish_error("valkey", "down")
    assert snapshot.updated_at == fetched_at
