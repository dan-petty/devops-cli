"""Self-contained dashboard widgets.

The dashboard previously declared every banner and table inline in one `compose`, then
addressed them from five near-identical `_refresh_*` methods that each queried the app by
widget id. Adding a domain meant editing a compose block, a column initialiser, a binding
table and a refresh method, and any of those could be forgotten independently.

A domain is now one widget that knows its own columns and renders its own snapshot, so the
app composes a panel per domain and holds no per-domain rendering code at all.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable, Iterable

from textual import work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.widgets import DataTable, Static

from devops_cli.config.constants import CONST_DASHBOARD_DOMAIN_LABELS
from devops_cli.config.defaults import DEFAULT_LOG_REDRAW_INTERVAL_SECONDS
from devops_cli.ui.log_buffer import VirtualLogBuffer
from devops_cli.ui.projections import DOMAIN_COLUMNS, loading_banner, render_domain
from devops_cli.ui.state import DomainSnapshot


class DomainPanel(Vertical):
    """A status banner and data table for one dashboard domain."""

    DEFAULT_CSS = """
    DomainPanel {
        height: 1fr;
    }
    DomainPanel > Static {
        padding: 0 1;
        margin-bottom: 1;
        background: $boost;
        color: $text;
    }
    DomainPanel > DataTable {
        height: 1fr;
    }
    """

    def __init__(self, domain: str, *, stale_after: float | None = None) -> None:
        super().__init__(id=f"panel-{domain}")
        self.domain = domain
        self.stale_after = stale_after

    @property
    def label(self) -> str:
        """Human-readable name for this domain."""
        return CONST_DASHBOARD_DOMAIN_LABELS.get(self.domain, self.domain.title())

    def compose(self) -> ComposeResult:
        yield Static(loading_banner(self.domain), id=f"{self.domain}-banner")
        yield DataTable(id=f"{self.domain}-table")

    def on_mount(self) -> None:
        """Install the column headers this domain declares."""
        table = self.query_one(DataTable)
        # Row selection, not cell selection: these tables are chosen from by record.
        table.cursor_type = "row"
        table.add_columns(*DOMAIN_COLUMNS[self.domain])

    def apply(self, snapshot: DomainSnapshot) -> None:
        """Render a snapshot into the banner and table.

        Called from the UI thread only; workers hand snapshots across via the app.
        """
        banner, rows = render_domain(snapshot, stale_after=self.stale_after)
        self.query_one(Static).update(banner)
        table = self.query_one(DataTable)
        table.clear()
        if rows:
            table.add_rows(rows)


__all__ = ["DomainPanel", "LogPane"]


class LogPane(Vertical):
    """A virtualized log tail bound to a bounded buffer.

    Only the lines currently on screen are rendered, and only the most recent
    ``max_lines`` are retained, so a tail of a busy pod costs a fixed amount of memory and
    a fixed amount of work per frame no matter how long it runs.
    """

    BINDINGS = [
        Binding("up", "scroll_lines(-1)", "Up", show=False),
        Binding("down", "scroll_lines(1)", "Down", show=False),
        Binding("pageup", "scroll_pages(-1)", "Page Up", show=False),
        Binding("pagedown", "scroll_pages(1)", "Page Down", show=False),
        Binding("end", "follow", "Follow", show=True),
    ]

    DEFAULT_CSS = """
    LogPane {
        height: 1fr;
    }
    LogPane > #log-status {
        padding: 0 1;
        background: $boost;
        color: $text;
    }
    LogPane > #log-body {
        height: 1fr;
        padding: 0 1;
    }
    """

    def __init__(
        self,
        buffer: VirtualLogBuffer | None = None,
        *,
        title: str = "Logs",
        id: str | None = None,
        redraw_interval: float = DEFAULT_LOG_REDRAW_INTERVAL_SECONDS,
    ) -> None:
        super().__init__(id=id)
        self.buffer = buffer if buffer is not None else VirtualLogBuffer()
        self.title = title
        self.redraw_interval = redraw_interval
        self._stop = threading.Event()

    def compose(self) -> ComposeResult:
        yield Static("", id="log-status")
        yield Static("", id="log-body")

    def on_mount(self) -> None:
        """Size the viewport to the pane and draw the empty state."""
        self.refresh_view()

    def on_resize(self) -> None:
        """Track the terminal size so the viewport matches what is actually visible."""
        visible = max(1, self.size.height - 1)
        self.buffer.resize_viewport(visible)
        self.refresh_view()

    def refresh_view(self) -> None:
        """Redraw from the buffer's current viewport.

        The cost of this is bounded by the viewport, not the stream, which is what lets it
        keep up with a log producing far more lines than a terminal can display.
        """
        lines = self.buffer.viewport_lines()
        self.query_one("#log-body", Static).update("\n".join(line.text for line in lines))
        self.query_one("#log-status", Static).update(f"{self.title} — {self.buffer.status()}")

    # -- Streaming ------------------------------------------------------------

    def start_stream(self, source: Callable[[], Iterable[str]]) -> None:
        """Consume a line source on a worker thread, redrawing as lines arrive."""
        self._stop.clear()
        self.buffer.clear()
        self._consume(source)

    def stop_stream(self) -> None:
        """Ask the streaming worker to finish after its current line."""
        self._stop.set()

    @work(thread=True, group="log-stream", exclusive=True)
    def _consume(self, source: Callable[[], Iterable[str]]) -> None:
        """Append lines off the UI thread, coalescing redraws as they arrive.

        Redrawing once per line would put the UI thread under exactly the load this pane
        exists to avoid, since a busy pod emits lines far faster than a terminal can
        usefully repaint. Every line is still retained; only the drawing is coalesced.
        """
        last_draw = 0.0
        try:
            for text in source():
                if self._stop.is_set():
                    break
                self.buffer.append(text.rstrip("\n"))
                now = time.monotonic()
                if now - last_draw >= self.redraw_interval:
                    last_draw = now
                    self._schedule_redraw()
        except Exception as exc:
            self.buffer.append(f"stream ended: {type(exc).__name__}: {exc}")
        # A final redraw guarantees the last lines are shown even if the stream ended
        # inside a coalescing window.
        self._schedule_redraw()

    def _schedule_redraw(self) -> None:
        """Ask the UI thread to redraw, tolerating an app that is shutting down."""
        try:
            self.app.call_from_thread(self.refresh_view)
        except Exception:
            # The app stopped while the stream was still running; nothing left to draw.
            return

    # -- Actions --------------------------------------------------------------

    def action_scroll_lines(self, delta: int) -> None:
        """Scroll the viewport by a number of lines."""
        self.buffer.scroll(delta)
        self.refresh_view()

    def action_scroll_pages(self, delta: int) -> None:
        """Scroll the viewport by whole pages."""
        self.buffer.scroll(delta * self.buffer.viewport)
        self.refresh_view()

    def action_follow(self) -> None:
        """Jump to the newest lines and resume following the stream."""
        self.buffer.scroll_to_end()
        self.refresh_view()
