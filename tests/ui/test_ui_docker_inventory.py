"""Tests for Docker Inventory behaviour in reactive dashboard."""

from __future__ import annotations

import time
from collections.abc import Callable

import pytest
from textual.widgets import DataTable, TabbedContent, TabPane

from devops_cli.config.constants import (
    CONST_DOCKER_RESOURCES,
)
from devops_cli.ui.dashboard import DashboardApp
from devops_cli.ui.data_providers import (
    DockerSummary,
)
from devops_cli.ui.projections import (
    DOCKER_RESOURCE_COLUMNS,
    docker_resource_label,
    docker_resource_rows,
    docker_rows,
)
from devops_cli.ui.state import DashboardState, DomainSnapshot
from devops_cli.ui.widgets import DockerPanel
from tests.support.ui import (
    _docker,
    _settle,
)


def test_stopped_containers_are_listed_alongside_running_ones() -> None:
    """The panel disagreed with `docker ps -a`: it listed only running containers."""
    summary = DockerSummary(
        connected=True,
        containers=[
            {"id": "a", "name": "up", "image": "i", "status": "running"},
            {"id": "b", "name": "down", "image": "i", "status": "exited"},
        ],
    )
    assert [row[3] for row in docker_rows(summary)] == ["running", "exited"]


@pytest.mark.parametrize(
    ("resource", "expected_first"),
    [
        ("containers", "abc123"),
        ("images", "img001"),
        ("networks", "net001"),
        ("volumes", "data"),
        ("registries", "https://index.docker.io/v1/"),
    ],
)
def test_each_docker_resource_projects_from_the_shared_snapshot(
    resource: str, expected_first: str
) -> None:
    """Every Docker view is rendered from one inventory, not from its own daemon query."""
    snapshot = DomainSnapshot(domain="docker", data=_docker(), updated_at=time.time())
    assert docker_resource_rows(resource, snapshot)[0][0] == expected_first


@pytest.mark.parametrize("resource", list(CONST_DOCKER_RESOURCES))
def test_each_docker_resource_row_matches_its_column_count(resource: str) -> None:
    """A mismatch raises inside Textual on the UI thread when the row is added."""
    snapshot = DomainSnapshot(domain="docker", data=_docker(), updated_at=time.time())
    widths = {len(row) for row in docker_resource_rows(resource, snapshot)}
    assert widths == {len(DOCKER_RESOURCE_COLUMNS[resource])}


@pytest.mark.parametrize("resource", list(CONST_DOCKER_RESOURCES))
def test_a_docker_resource_renders_nothing_before_the_first_fetch(resource: str) -> None:
    """An unloaded panel renders empty rather than raising."""
    assert docker_resource_rows(resource, DomainSnapshot(domain="docker")) == []


def test_a_docker_sub_tab_label_carries_its_row_count() -> None:
    """Counts are readable without opening each tab."""
    snapshot = DomainSnapshot(domain="docker", data=_docker(), updated_at=time.time())
    assert docker_resource_label("images", snapshot) == "Images (1)"


def test_a_docker_sub_tab_label_omits_a_count_before_loading() -> None:
    """A count of zero before the first fetch would claim the daemon has nothing."""
    assert docker_resource_label("images", DomainSnapshot(domain="docker")) == "Images"


async def test_every_docker_resource_lives_under_the_single_docker_tab(
    patched_fetchers: Callable[..., None],
) -> None:
    """Docker resources are Docker state and belong under one header.

    Promoting each to a top-level tab made them compete with Kubernetes and Valkey for
    attention, and crowded the footer past the point of truncation.
    """
    patched_fetchers()
    state = DashboardState()
    app = DashboardApp(refresh_interval=0, state=state)
    async with app.run_test() as pilot:
        await _settle(pilot, lambda: not state.pending_domains())
        panel = app.query_one("#panel-docker", DockerPanel)
        tabs = {
            pane.id for pane in panel.query_one("#docker-resources", TabbedContent).query(TabPane)
        }
        assert tabs == {f"docker-{resource}" for resource in CONST_DOCKER_RESOURCES}


async def test_the_docker_panel_populates_every_resource_table(
    patched_fetchers: Callable[..., None],
) -> None:
    """One fetch fills all five views."""
    patched_fetchers()
    state = DashboardState()
    app = DashboardApp(refresh_interval=0, state=state)
    async with app.run_test() as pilot:
        await _settle(pilot, lambda: not state.pending_domains())
        panel = app.query_one("#panel-docker", DockerPanel)
        counts = {
            resource: panel.query_one(f"#{panel._table_id(resource)}", DataTable).row_count
            for resource in CONST_DOCKER_RESOURCES
        }
        assert counts == dict.fromkeys(CONST_DOCKER_RESOURCES, 1)
