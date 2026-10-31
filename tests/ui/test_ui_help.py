"""Tests for Help behaviour in reactive dashboard."""

from __future__ import annotations

from collections.abc import Callable

from textual.widgets import Static

from devops_cli.ui.dashboard import DashboardApp, HelpScreen


async def test_the_help_screen_lists_the_kubernetes_and_log_keys(
    patched_fetchers: Callable[..., None],
) -> None:
    """`/`, `e`, `c` and Escape are hidden from the footer, so help is where they are found."""
    patched_fetchers()
    app = DashboardApp(refresh_interval=0)
    async with app.run_test() as pilot:
        app.push_screen(HelpScreen())
        await pilot.pause()
        help_text = str(app.screen.query_one("#help-body", Static).content)
        assert all(
            line in help_text
            for line in (
                "  /   : Filter pods by namespace, name or status (Kubernetes)",
                "  e   : Inspect the highlighted pod's containers and events (Kubernetes)",
                "  esc : Clear the pod filter, or close a dialog",
                "  c         : Stream the pod's next container",
            )
        )
