"""Tests for Container-Aware Logs behaviour in reactive dashboard."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest
from textual.widgets import TabbedContent

import devops_cli.ui.dashboard as dashboard_module
from devops_cli.models.k8s import PodInfo
from devops_cli.ui.dashboard import DashboardApp
from devops_cli.ui.data_providers import (
    K8sSummary,
)
from devops_cli.ui.pod_inspector import PodInspector
from devops_cli.ui.projections import (
    log_title,
    next_container,
)
from devops_cli.ui.refresh import (
    pod_log_source,
)
from devops_cli.ui.widgets import LogPane
from tests.support.fakes.kubernetes import (
    pod,
)
from tests.support.ui import (
    _loaded,
    _recording_source,
    _sidecar_pod,
)


@pytest.mark.parametrize(
    ("annotated", "expected"),
    [
        (True, (["app", "sidecar"], "default/web-0 [sidecar] (1 of 2 containers)")),
        (False, (["sidecar", "app"], "default/web-0 [app] (2 of 2 containers)")),
    ],
)
async def test_enter_streams_the_default_container_and_c_moves_to_the_next(
    patched_fetchers: Callable[..., None],
    monkeypatch: pytest.MonkeyPatch,
    annotated: bool,
    expected: tuple[list[str], str],
) -> None:
    """A pod with two containers could not be tailed at all: the API wants a container."""
    requested: list[str | None] = []
    patched_fetchers(k8s=lambda: _sidecar_pod(annotated))
    monkeypatch.setattr(dashboard_module, "pod_log_source", _recording_source(requested))
    app = DashboardApp(refresh_interval=0)
    async with app.run_test() as pilot:
        await _loaded(pilot, app)
        await pilot.press("enter")
        await pilot.pause()
        await pilot.press("c")
        await pilot.pause()
        assert (requested, app.query_one("#log-pane", LogPane).title) == expected


async def test_a_pod_without_a_name_opens_no_stream_and_no_inspector(
    patched_fetchers: Callable[..., None], monkeypatch: pytest.MonkeyPatch
) -> None:
    """A record whose pod has no name would stream and inspect pod '', which the API refuses."""
    nameless = pod()
    nameless.metadata.name = None
    requested: list[str | None] = []
    patched_fetchers(k8s=lambda: K8sSummary(connected=True, pods=[PodInfo.from_pod(nameless)]))
    monkeypatch.setattr(dashboard_module, "pod_log_source", _recording_source(requested))
    app = DashboardApp(refresh_interval=0)
    async with app.run_test() as pilot:
        await _loaded(pilot, app)
        await pilot.press("enter", "e")
        await pilot.pause()
        assert requested == []
        assert app.query_one(TabbedContent).active == "tab-k8s"
        assert not isinstance(app.screen, PodInspector)


def test_log_titles_name_the_container_and_its_place_among_them() -> None:
    """Init containers are counted, so every container of the pod can be reached with `c`."""
    info = PodInfo.from_pod(pod("web-0", containers=("app", "web"), init_containers=("migrate",)))
    assert (
        log_title(info, "web"),
        next_container(info, "web"),
        next_container(info, "migrate"),
    ) == ("default/web-0 [web] (2 of 3 containers)", "migrate", "app")


def test_a_pod_log_source_reads_the_container_it_was_given(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Without a container, the API server answers 400 for any pod with more than one."""
    opened: list[dict[str, Any]] = []

    class FakeService:
        @staticmethod
        def get_instance() -> Any:
            return FakeService()

        def read_pod_logs(self, **kwargs: Any) -> Any:
            opened.append(kwargs)
            return iter(["one"])

    monkeypatch.setattr("devops_cli.k8s.service.KubernetesService", FakeService)
    list(pod_log_source("web-0", "shop", "app")())
    assert (opened[0]["pod"], opened[0]["namespace"], opened[0]["container"]) == (
        "web-0",
        "shop",
        "app",
    )
