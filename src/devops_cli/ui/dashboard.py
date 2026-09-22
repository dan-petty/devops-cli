"""Interactive Terminal UI Dashboard powered by Textual.

Refreshes run on worker threads and publish into a shared state store; the UI thread only
renders what has been published. The previous design called five blocking provider
functions in sequence from the keypress handler, so the interface stopped responding for
the sum of five network round trips and one unreachable cluster froze every unrelated tab.
"""

from __future__ import annotations

from functools import partial
from typing import Any

from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import (
    Button,
    DataTable,
    Footer,
    Header,
    Label,
    Static,
    TabbedContent,
    TabPane,
)

from devops_cli.config.constants import (
    CONST_DASHBOARD_DOMAIN_AI,
    CONST_DASHBOARD_DOMAIN_DOCKER,
    CONST_DASHBOARD_DOMAIN_K8S,
    CONST_DASHBOARD_DOMAIN_LABELS,
    CONST_DASHBOARD_DOMAINS,
    CONST_LOGS_TAB_ID,
)
from devops_cli.config.defaults import (
    DEFAULT_DASHBOARD_REFRESH_SECONDS,
    DEFAULT_DASHBOARD_STALE_SECONDS,
)
from devops_cli.ui.data_providers import fetch_review_status
from devops_cli.ui.refresh import DOMAIN_FETCHERS, pod_log_source, refresh_domain
from devops_cli.ui.state import DashboardState, DomainSnapshot
from devops_cli.ui.widgets import DockerPanel, DomainPanel, LogPane, ReviewPanel


def _tab_id(domain: str) -> str:
    """Return the TabPane id for a domain."""
    return f"tab-{domain}"


def _panel_for(domain: str) -> DomainPanel | DockerPanel | ReviewPanel:
    """Build the panel a domain renders into.

    Most domains are a banner over one table. Docker and AI Review carry several views of
    one snapshot, so they compose nested tabs instead; choosing here keeps `compose` flat.
    """
    stale_after = DEFAULT_DASHBOARD_STALE_SECONDS
    if domain == CONST_DASHBOARD_DOMAIN_DOCKER:
        return DockerPanel(domain, stale_after=stale_after)
    if domain == CONST_DASHBOARD_DOMAIN_AI:
        return ReviewPanel(domain, stale_after=stale_after)
    return DomainPanel(domain, stale_after=stale_after)


class HelpScreen(ModalScreen[None]):
    """Help modal displaying keyboard shortcuts and operational commands."""

    DEFAULT_CSS = """
    HelpScreen {
        align: center middle;
    }
    #help-dialog {
        padding: 1 2;
        width: 78;
        height: auto;
        border: thick $primary;
        background: $surface;
    }
    #help-title {
        text-style: bold;
        color: $accent;
        margin-bottom: 1;
    }
    #help-body {
        margin-bottom: 1;
    }
    #close-btn {
        width: 100%;
    }
    """

    BINDINGS = [
        Binding("escape", "dismiss", "Close Help"),
        Binding("enter", "dismiss", "Close Help"),
    ]

    def compose(self) -> ComposeResult:
        tab_hints = "  ".join(
            f"{index}={CONST_DASHBOARD_DOMAIN_LABELS[domain]}"
            for index, domain in enumerate(CONST_DASHBOARD_DOMAINS, start=1)
        )
        help_text = (
            "Keyboard Navigation:\n\n"
            f"  1-{len(CONST_DASHBOARD_DOMAINS)} : Switch Tabs\n"
            f"        {tab_hints}\n"
            "  l   : Streamed pod logs\n"
            "  r   : Refresh active data sources\n"
            "  ctrl+p : Command palette\n"
            "  ?   : Open this help dialog\n"
            "  q   : Quit the dashboard\n\n"
            "In the log pane:\n\n"
            "  up/down   : Scroll one line\n"
            "  pgup/pgdn : Scroll one page\n"
            "  end       : Resume following the stream\n\n"
            "Tip: select a pod on the Kubernetes tab to tail its logs.\n"
            "Refreshes run in the background; the interface stays responsive while\n"
            "a slow or unreachable subsystem is still being queried."
        )
        with Vertical(id="help-dialog"):
            yield Label("DevOps CLI Dashboard Help", id="help-title")
            yield Static(help_text, id="help-body")
            yield Button("Close (Esc)", variant="primary", id="close-btn")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss()


class DashboardApp(App[None]):
    """Full-screen responsive Textual workstation dashboard."""

    TITLE = "DevOps CLI — Workstation Dashboard"
    SUB_TITLE = "Real-Time Workstation Situational Awareness"

    # The numeric tab bindings are hidden from the footer. Each tab already shows its own
    # number in its label, and listing nine of them crowded out Refresh, Help and Quit --
    # the footer truncated mid-word, leaving "q Qu".
    BINDINGS = [
        *(
            Binding(
                str(index),
                f"switch_tab('{_tab_id(domain)}')",
                CONST_DASHBOARD_DOMAIN_LABELS[domain],
                show=False,
                priority=True,
            )
            for index, domain in enumerate(CONST_DASHBOARD_DOMAINS, start=1)
        ),
        Binding("l", f"switch_tab('{CONST_LOGS_TAB_ID}')", "Logs", show=True, priority=True),
        Binding("r", "refresh_data", "Refresh", show=True),
        Binding("question_mark", "show_help", "Help", show=True),
        Binding("q", "quit", "Quit", show=True),
    ]

    # Without this Textual renders the raw key, so the footer read "^p palette".
    COMMAND_PALETTE_DISPLAY = "ctrl+p"

    DEFAULT_CSS = """
    TabbedContent {
        height: 1fr;
    }
    """

    def __init__(
        self,
        initial_tab: str = "tab-k8s",
        refresh_interval: int = DEFAULT_DASHBOARD_REFRESH_SECONDS,
        state: DashboardState | None = None,
    ) -> None:
        super().__init__()
        self._initial_tab = (
            initial_tab if initial_tab.startswith("tab-") else _tab_id(initial_tab.lower())
        )
        self._refresh_interval = max(0, refresh_interval)
        self._state = state if state is not None else DashboardState()
        # None means "the newest completed session"; set by picking one from the session
        # list, and reset whenever the review domain is refreshed without a selection.
        self._review_session: str | None = None

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with TabbedContent(initial=self._initial_tab):
            for index, domain in enumerate(CONST_DASHBOARD_DOMAINS, start=1):
                label = CONST_DASHBOARD_DOMAIN_LABELS[domain]
                with TabPane(f"{label} ({index})", id=_tab_id(domain)):
                    yield _panel_for(domain)
            with TabPane("Logs (l)", id=CONST_LOGS_TAB_ID):
                yield LogPane(id="log-pane", title="Select a pod on the Kubernetes tab")
        yield Footer()

    def on_mount(self) -> None:
        self.action_refresh_data()
        if self._refresh_interval > 0:
            self.set_interval(self._refresh_interval, self.action_refresh_data)

    def action_switch_tab(self, tab_id: str) -> None:
        """Switch the active TabPane by id."""
        self.query_one(TabbedContent).active = tab_id

    def action_show_help(self) -> None:
        """Display the help dialog modal."""
        self.push_screen(HelpScreen())

    def action_refresh_data(self) -> None:
        """Start a background refresh for every domain.

        Returns immediately. Each domain is fetched on its own worker thread and renders as
        soon as it arrives, so a fast subsystem is not held behind a slow one and the key
        that triggered the refresh is never what makes the interface hang.
        """
        for domain in CONST_DASHBOARD_DOMAINS:
            self._refresh_worker(domain)

    def _fetchers_for(self, domain: str) -> dict[str, Any] | None:
        """Return a fetcher override for a domain, or None to use the registered one.

        The review domain is the only one whose fetch is parameterised: it renders whichever
        session the operator selected rather than always the newest.
        """
        if domain == CONST_DASHBOARD_DOMAIN_AI and self._review_session:
            return {**DOMAIN_FETCHERS, domain: partial(fetch_review_status, self._review_session)}
        return None

    @work(thread=True, group="dashboard-refresh")
    def _refresh_worker(self, domain: str) -> None:
        """Fetch one domain off the UI thread and hand the result back for rendering."""
        snapshot = refresh_domain(self._state, domain, self._fetchers_for(domain))
        if snapshot is not None:
            self.call_from_thread(self.apply_snapshot, snapshot)

    def _select_review_session(self, event: DataTable.RowSelected) -> None:
        """Display the review session named by the selected row."""
        row = event.data_table.get_row(event.row_key)
        name = str(row[0]) if row else ""
        if not name:
            return
        self._review_session = name
        self._refresh_worker(CONST_DASHBOARD_DOMAIN_AI)

    def apply_snapshot(self, snapshot: DomainSnapshot) -> None:
        """Render a published snapshot into its panel, if the panel is still mounted.

        A projection that cannot render the data it was given is reported in that domain's
        own banner. Letting it propagate would fail the worker and, because this runs on
        the UI thread, take down a dashboard whose other four subsystems are healthy.
        """
        panels: list[Any] = [
            *self.query(f"#panel-{snapshot.domain}").results(DomainPanel),
            *self.query(f"#panel-{snapshot.domain}").results(DockerPanel),
            *self.query(f"#panel-{snapshot.domain}").results(ReviewPanel),
        ]
        for panel in panels:
            try:
                panel.apply(snapshot)
            except Exception as exc:
                # The fallback carries no data, so rendering it cannot fail the same way:
                # retaining the payload that just broke the projection would only re-raise.
                message = f"render failed: {type(exc).__name__}: {exc}"
                self._state.publish_error(snapshot.domain, message)
                panel.apply(DomainSnapshot(domain=snapshot.domain, error=message))

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Route a row selection to the action that row represents."""
        if event.data_table.id == "review-sessions-table":
            self._select_review_session(event)
            return
        if event.data_table.id != f"{CONST_DASHBOARD_DOMAIN_K8S}-table":
            return
        row = event.data_table.get_row(event.row_key)
        namespace, pod = str(row[0]), str(row[1])
        if not pod:
            return
        pane = self.query_one("#log-pane", LogPane)
        pane.title = f"{namespace}/{pod}"
        pane.start_stream(pod_log_source(pod, namespace))
        self.action_switch_tab(CONST_LOGS_TAB_ID)


__all__ = ["DashboardApp", "HelpScreen"]
