"""Interactive Terminal UI Dashboard powered by Textual."""

from __future__ import annotations

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

from devops_cli.ui.data_providers import (
    fetch_docker_status,
    fetch_k8s_status,
    fetch_review_status,
    fetch_telemetry_status,
    fetch_valkey_status,
)


class HelpScreen(ModalScreen[None]):
    """Help modal displaying keyboard shortcuts and operational commands."""

    DEFAULT_CSS = """
    HelpScreen {
        align: center middle;
    }
    #help-dialog {
        padding: 1 2;
        width: 65;
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
        help_text = (
            "Keyboard Navigation:\n\n"
            "  1-5 : Switch Tabs (1=K8s, 2=Docker, 3=Telemetry, 4=AI, 5=Valkey)\n"
            "  r   : Refresh active data sources\n"
            "  ?   : Open this help dialog\n"
            "  q   : Quit the dashboard\n\n"
            "Tip: You can also click tab headers or use arrow keys."
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

    BINDINGS = [
        Binding("1", "switch_tab('tab-k8s')", "K8s", show=True, priority=True),
        Binding("2", "switch_tab('tab-docker')", "Docker", show=True, priority=True),
        Binding("3", "switch_tab('tab-telemetry')", "Telemetry", show=True, priority=True),
        Binding("4", "switch_tab('tab-ai')", "AI Review", show=True, priority=True),
        Binding("5", "switch_tab('tab-valkey')", "Valkey", show=True, priority=True),
        Binding("r", "refresh_data", "Refresh", show=True),
        Binding("question_mark", "show_help", "Help", show=True),
        Binding("q", "quit", "Quit", show=True),
    ]

    DEFAULT_CSS = """
    TabbedContent {
        height: 1fr;
    }
    DataTable {
        height: 1fr;
    }
    .status-banner {
        padding: 0 1;
        margin-bottom: 1;
        background: $boost;
        color: $text;
    }
    """

    def __init__(
        self,
        initial_tab: str = "tab-k8s",
        refresh_interval: int = 5,
    ) -> None:
        super().__init__()
        self._initial_tab = (
            initial_tab if initial_tab.startswith("tab-") else f"tab-{initial_tab.lower()}"
        )
        self._refresh_interval = max(1, refresh_interval)

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with TabbedContent(initial=self._initial_tab):
            with TabPane("Kubernetes (1)", id="tab-k8s"):
                yield Static(id="k8s-banner", classes="status-banner")
                yield DataTable(id="k8s-table")
            with TabPane("Docker (2)", id="tab-docker"):
                yield Static(id="docker-banner", classes="status-banner")
                yield DataTable(id="docker-table")
            with TabPane("Telemetry (3)", id="tab-telemetry"):
                yield Static(id="telemetry-banner", classes="status-banner")
                yield DataTable(id="telemetry-table")
            with TabPane("AI Review (4)", id="tab-ai"):
                yield Static(id="ai-banner", classes="status-banner")
                yield DataTable(id="ai-table")
            with TabPane("Valkey Cache (5)", id="tab-valkey"):
                yield Static(id="valkey-banner", classes="status-banner")
                yield DataTable(id="valkey-table")
        yield Footer()

    def on_mount(self) -> None:
        self._init_tables()
        self.action_refresh_data()
        if self._refresh_interval > 0:
            self.set_interval(self._refresh_interval, self.action_refresh_data)

    def _init_tables(self) -> None:
        k8s_table = self.query_one("#k8s-table", DataTable)
        k8s_table.add_columns("Namespace", "Pod Name", "Status", "Ready", "Restarts")

        docker_table = self.query_one("#docker-table", DataTable)
        docker_table.add_columns("Container ID", "Name", "Image", "Status")

        telemetry_table = self.query_one("#telemetry-table", DataTable)
        telemetry_table.add_columns("Metric Name", "Type", "Value / Count")

        ai_table = self.query_one("#ai-table", DataTable)
        ai_table.add_columns("Severity", "Title", "Location", "Status")

        valkey_table = self.query_one("#valkey-table", DataTable)
        valkey_table.add_columns("Metric Property", "Value")

    def action_switch_tab(self, tab_id: str) -> None:
        """Switch the active TabPane by id."""
        tabs = self.query_one(TabbedContent)
        tabs.active = tab_id

    def action_show_help(self) -> None:
        """Display the help dialog modal."""
        self.push_screen(HelpScreen())

    def action_refresh_data(self) -> None:
        """Reload and update all dashboard tables and status banners."""
        self._refresh_k8s()
        self._refresh_docker()
        self._refresh_telemetry()
        self._refresh_ai()
        self._refresh_valkey()

    def _refresh_k8s(self) -> None:
        summary = fetch_k8s_status()
        banner = self.query_one("#k8s-banner", Static)
        status_color = "green" if summary.connected else "yellow"
        mk_txt = " | Minikube: Active" if summary.minikube_active else ""
        banner.update(
            f"[{status_color}]●[/{status_color}] Kubernetes: {'Connected' if summary.connected else 'Disconnected'}{mk_txt}"
        )

        table = self.query_one("#k8s-table", DataTable)
        table.clear()
        for p in summary.pods:
            table.add_row(p["namespace"], p["name"], p["status"], p["ready"], p["restarts"])

    def _refresh_docker(self) -> None:
        summary = fetch_docker_status()
        banner = self.query_one("#docker-banner", Static)
        status_color = "green" if summary.connected else "yellow"
        banner.update(
            f"[{status_color}]●[/{status_color}] Docker: {'Active' if summary.connected else 'Inactive'} ({len(summary.containers)} containers)"
        )

        table = self.query_one("#docker-table", DataTable)
        table.clear()
        for c in summary.containers:
            table.add_row(c["id"], c["name"], c["image"], c["status"])

    def _refresh_telemetry(self) -> None:
        summary = fetch_telemetry_status()
        banner = self.query_one("#telemetry-banner", Static)
        banner.update(
            f"OpenTelemetry: {summary.counter_count} Counters, {summary.gauge_count} Gauges, {summary.histogram_count} Histograms"
        )

        table = self.query_one("#telemetry-table", DataTable)
        table.clear()
        for name, val in summary.counters.items():
            table.add_row(name, "Counter", f"{val:.1f}")
        for name, val in summary.gauges.items():
            table.add_row(name, "Gauge", f"{val:.1f}")

    def _refresh_ai(self) -> None:
        summary = fetch_review_status()
        banner = self.query_one("#ai-banner", Static)
        if summary.has_session:
            dist_str = (
                " | ".join(f"{k}: {v}" for k, v in summary.severity_distribution.items()) or "None"
            )
            banner.update(
                f"Latest Review: {summary.session_name} | Total: {summary.total_findings} (Verified: {summary.verified_count}) | {dist_str}"
            )
        else:
            banner.update("No active or past AI code review sessions found.")

        table = self.query_one("#ai-table", DataTable)
        table.clear()
        for f in summary.findings:
            table.add_row(
                f.get("severity", "MEDIUM"),
                f.get("title", "Untitled")[:45],
                f.get("location", "—"),
                f.get("status", "UNVERIFIED"),
            )

    def _refresh_valkey(self) -> None:
        summary = fetch_valkey_status()
        banner = self.query_one("#valkey-banner", Static)
        status_color = "green" if summary.connected else "yellow"
        banner.update(
            f"[{status_color}]●[/{status_color}] Valkey Cache: {summary.version} | Used Memory: {summary.used_memory} | Hit Ratio: {summary.hit_ratio:.1f}%"
        )

        table = self.query_one("#valkey-table", DataTable)
        table.clear()
        table.add_row("Server Version", summary.version)
        table.add_row("Status", "Connected" if summary.connected else "Offline")
        table.add_row("Used Memory", summary.used_memory)
        table.add_row("Cache Hit Ratio", f"{summary.hit_ratio:.1f}%")
        table.add_row("Connected Clients", str(summary.connected_clients))
        table.add_row("Key Count", str(summary.key_count))
        table.add_row("Total Commands", str(summary.total_commands))
