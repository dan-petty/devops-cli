"""Tests for Help behaviour in reactive dashboard."""

from __future__ import annotations

from collections.abc import Callable

from textual.widgets import Static

from devops_cli.ui.dashboard import DashboardApp, HelpScreen


async def test_the_help_screen_lists_navigation_and_command_keys(
    patched_fetchers: Callable[..., None],
) -> None:
    """The help screen presents navigation shortcuts and modal controls."""
    patched_fetchers()
    app = DashboardApp(refresh_interval=0)
    async with app.run_test() as pilot:
        app.push_screen(HelpScreen())
        await pilot.pause()
        help_text = str(app.screen.query_one("#help-body", Static).content)
        assert all(
            line in help_text
            for line in (
                "  1-3 : Switch Tabs",
                "  w   : Open trace waterfall modal (Telemetry)",
                "  esc : Close a dialog",
                "  r   : Refresh active data sources",
                "  q   : Quit the dashboard",
            )
        )
        assert "/   : Filter pods" not in help_text
        assert "Stream the pod's next container" not in help_text
