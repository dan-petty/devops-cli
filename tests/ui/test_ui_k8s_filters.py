"""Tests for Kubernetes Panel: Filters behaviour in reactive dashboard."""

from __future__ import annotations

from collections.abc import Callable

from textual.widgets import Input, Select, TabbedContent

from devops_cli.ui.dashboard import DashboardApp
from devops_cli.ui.projections import (
    filter_pods,
    namespace_choices,
    render_keys,
)
from devops_cli.ui.state import DomainSnapshot
from tests.support.ui import (
    _cluster,
    _k8s_banner_text,
    _loaded,
    _pod,
    _refresh,
    _shown,
)


def test_filter_pods_matches_namespace_name_or_status_ignoring_case() -> None:
    """The text filter covers status too, so it doubles as the status filter."""
    summary = _cluster()
    records = dict(
        zip(render_keys(DomainSnapshot(domain="k8s", data=summary)), summary.pods, strict=True)
    )
    by_text = {
        text: [p.name for p in filter_pods(records, "", text).values()]
        for text in ("CRASH", "Kube-")
    }
    assert (by_text, len(filter_pods(records, "monitoring", ""))) == (
        {"CRASH": ["exporter-0"], "Kube-": ["coredns-0"]},
        12,
    )


def test_namespace_choices_keep_the_selected_namespace_after_its_pods_are_gone() -> None:
    """A namespace whose pods are being recreated stays selectable, so the filter holds."""
    assert namespace_choices(_cluster(without="monitoring").pods, "monitoring") == (
        "kube-system",
        "monitoring",
        "shop",
    )


async def test_slash_focuses_the_filter_box_and_typing_narrows_the_pods(
    patched_fetchers: Callable[..., None],
) -> None:
    """Letters typed into the box are text, not the tab keys bound to them."""
    patched_fetchers(k8s=_cluster)
    app = DashboardApp(refresh_interval=0)
    async with app.run_test() as pilot:
        await _loaded(pilot, app)
        await pilot.press("slash")
        focused = app.focused.id if app.focused else None
        await pilot.press(*"alloy-logs")
        await pilot.pause()
        assert (focused, app.query_one(TabbedContent).active, _shown(app)) == (
            "k8s-filter",
            "tab-k8s",
            [f"alloy-logs-{index}" for index in range(9)],
        )


async def test_typing_a_status_keeps_only_pods_in_it(patched_fetchers: Callable[..., None]) -> None:
    """`crash` finds the crashlooping pod, which its phase used to hide."""
    patched_fetchers(k8s=_cluster)
    app = DashboardApp(refresh_interval=0)
    async with app.run_test() as pilot:
        await _loaded(pilot, app)
        await pilot.press("slash", *"crash")
        await pilot.pause()
        assert _shown(app) == ["exporter-0"]


async def test_escape_clears_the_filter_and_returns_to_the_table(
    patched_fetchers: Callable[..., None],
) -> None:
    """Escape undoes the filter and hands the arrow keys back to the pod table."""
    patched_fetchers(k8s=_cluster)
    app = DashboardApp(refresh_interval=0)
    async with app.run_test() as pilot:
        await _loaded(pilot, app)
        await pilot.press("slash", *"web")
        await pilot.press("escape")
        await pilot.pause()
        assert (
            app.query_one("#k8s-filter", Input).value,
            app.focused.id if app.focused else None,
            len(_shown(app)),
        ) == ("", "k8s-table", 63)


async def test_choosing_a_namespace_lists_only_its_pods(
    patched_fetchers: Callable[..., None],
) -> None:
    """The selector is reached and operated from the keyboard, and narrows the table.

    From the pod table, shift+tab passes the text box to the selector; Enter opens it,
    and its options are All namespaces, kube-system, monitoring and shop.
    """
    patched_fetchers(k8s=_cluster)
    app = DashboardApp(refresh_interval=0)
    async with app.run_test() as pilot:
        await _loaded(pilot, app)
        await pilot.press("shift+tab", "shift+tab")
        focused = app.focused.id if app.focused else None
        await pilot.press("enter", "down", "down", "enter")
        await pilot.pause()
        assert (
            focused,
            app.query_one("#k8s-namespace", Select).value,
            len(_shown(app)),
            "showing 12 of 63" in _k8s_banner_text(app),
        ) == ("k8s-namespace", "monitoring", 12, True)


async def test_the_namespace_and_text_filters_survive_refreshes(
    patched_fetchers: Callable[..., None],
) -> None:
    """A refresh changes the namespaces on offer, never the one chosen or the text typed."""
    cluster = {"summary": _cluster()}
    patched_fetchers(k8s=lambda: cluster["summary"])
    app = DashboardApp(refresh_interval=0)
    async with app.run_test() as pilot:
        await _loaded(pilot, app)
        select = app.query_one("#k8s-namespace", Select)
        select.value = "monitoring"
        await pilot.press("slash", *"alloy")
        cluster["summary"] = _cluster(extra=(_pod("job-0", "batch"),))
        await _refresh(pilot, app)
        first = (select.value, len(_shown(app)), "showing 9 of 64" in _k8s_banner_text(app))
        cluster["summary"] = _cluster(without="monitoring")
        await _refresh(pilot, app)
        assert (first, select.value, _shown(app), "showing 0 of 51" in _k8s_banner_text(app)) == (
            ("monitoring", 9, True),
            "monitoring",
            [],
            True,
        )


async def test_a_namespace_added_by_a_refresh_becomes_selectable(
    patched_fetchers: Callable[..., None],
) -> None:
    """The options follow the cluster, so a new namespace can be chosen without a restart."""
    cluster = {"summary": _cluster()}
    patched_fetchers(k8s=lambda: cluster["summary"])
    app = DashboardApp(refresh_interval=0)
    async with app.run_test() as pilot:
        await _loaded(pilot, app)
        cluster["summary"] = _cluster(extra=(_pod("job-0", "batch"),))
        await _refresh(pilot, app)
        app.query_one("#k8s-namespace", Select).value = "batch"
        await pilot.pause()
        assert _shown(app) == ["job-0"]
