"""Self-contained dashboard widgets.

The dashboard previously declared every banner and table inline in one `compose`, then
addressed them from five near-identical `_refresh_*` methods that each queried the app by
widget id. Adding a domain meant editing a compose block, a column initialiser, a binding
table and a refresh method, and any of those could be forgotten independently.

A domain is now one widget that knows its own columns and renders its own snapshot, so the
app composes a panel per domain and holds no per-domain rendering code at all.
"""

from __future__ import annotations

import contextlib
import queue
import threading
import time
from collections.abc import Callable, Iterable

from textual import work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.widgets import DataTable, Static, TabbedContent, TabPane

from devops_cli.config.constants import (
    CONST_DASHBOARD_DOMAIN_AI,
    CONST_DASHBOARD_DOMAIN_DOCKER,
    CONST_DASHBOARD_DOMAIN_LABELS,
    CONST_DOCKER_RESOURCE_CONTAINERS,
    CONST_DOCKER_RESOURCE_LABELS,
    CONST_DOCKER_RESOURCES,
    CONST_LOG_STREAM_QUEUE_SIZE,
)
from devops_cli.config.defaults import (
    DEFAULT_LOG_REDRAW_INTERVAL_SECONDS,
    DEFAULT_LOG_STREAM_POLL_SECONDS,
)
from devops_cli.ui.log_buffer import VirtualLogBuffer
from devops_cli.ui.projections import (
    DOCKER_RESOURCE_COLUMNS,
    DOMAIN_COLUMNS,
    REVIEW_SESSION_COLUMNS,
    docker_resource_label,
    docker_resource_rows,
    loading_banner,
    render_banner,
    render_domain,
    review_session_rows,
)
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


__all__ = ["DockerPanel", "DomainPanel", "LogPane", "ReviewPanel"]


class DockerPanel(Vertical):
    """The Docker domain: one banner over nested tabs for each kind of resource.

    Containers, images, networks, volumes and registries are all Docker state, so they live
    under one header rather than competing with Kubernetes and Valkey for a top-level tab.
    Every view is projected from the same snapshot, so the whole panel costs one set of
    daemon queries per refresh.
    """

    DEFAULT_CSS = """
    DockerPanel {
        height: 1fr;
    }
    DockerPanel > Static {
        padding: 0 1;
        margin-bottom: 1;
        background: $boost;
        color: $text;
    }
    DockerPanel TabbedContent {
        height: 1fr;
    }
    DockerPanel DataTable {
        height: 1fr;
    }
    """

    def __init__(
        self, domain: str = CONST_DASHBOARD_DOMAIN_DOCKER, *, stale_after: float | None = None
    ) -> None:
        super().__init__(id=f"panel-{domain}")
        self.domain = domain
        self.stale_after = stale_after

    @property
    def label(self) -> str:
        """Human-readable name for this domain."""
        return CONST_DASHBOARD_DOMAIN_LABELS.get(self.domain, self.domain.title())

    def compose(self) -> ComposeResult:
        yield Static(loading_banner(self.domain), id=f"{self.domain}-banner")
        with TabbedContent(id="docker-resources"):
            for resource in CONST_DOCKER_RESOURCES:
                with TabPane(CONST_DOCKER_RESOURCE_LABELS[resource], id=f"docker-{resource}"):
                    # The containers table keeps its historical id so existing selection
                    # handling and tests continue to address it.
                    table_id = (
                        "docker-table"
                        if resource == CONST_DOCKER_RESOURCE_CONTAINERS
                        else f"docker-{resource}-table"
                    )
                    yield DataTable(id=table_id)

    def on_mount(self) -> None:
        """Install each resource view's column headers."""
        for resource in CONST_DOCKER_RESOURCES:
            table = self.query_one(f"#{self._table_id(resource)}", DataTable)
            table.cursor_type = "row"
            table.add_columns(*DOCKER_RESOURCE_COLUMNS[resource])

    @staticmethod
    def _table_id(resource: str) -> str:
        """Return the table id for a resource view."""
        if resource == CONST_DOCKER_RESOURCE_CONTAINERS:
            return "docker-table"
        return f"docker-{resource}-table"

    def apply(self, snapshot: DomainSnapshot) -> None:
        """Render a snapshot into the banner and every resource table."""
        self.query_one(Static).update(render_banner(snapshot, stale_after=self.stale_after))
        tabs = self.query_one("#docker-resources", TabbedContent)
        for resource in CONST_DOCKER_RESOURCES:
            table = self.query_one(f"#{self._table_id(resource)}", DataTable)
            rows = docker_resource_rows(resource, snapshot)
            table.clear()
            if rows:
                table.add_rows(rows)
            # The count rides on the tab label so it is readable without opening the tab.
            with contextlib.suppress(Exception):
                tabs.get_tab(f"docker-{resource}").label = docker_resource_label(resource, snapshot)


class ReviewPanel(Vertical):
    """The AI review domain: findings for one session, plus a session picker.

    The session shown defaults to the newest completed one, and the picker lists every
    session newest-first so an earlier review can be opened without leaving the dashboard.
    """

    DEFAULT_CSS = """
    ReviewPanel {
        height: 1fr;
    }
    ReviewPanel > Static {
        padding: 0 1;
        margin-bottom: 1;
        background: $boost;
        color: $text;
    }
    ReviewPanel TabbedContent {
        height: 1fr;
    }
    ReviewPanel DataTable {
        height: 1fr;
    }
    """

    def __init__(
        self, domain: str = CONST_DASHBOARD_DOMAIN_AI, *, stale_after: float | None = None
    ) -> None:
        super().__init__(id=f"panel-{domain}")
        self.domain = domain
        self.stale_after = stale_after

    @property
    def label(self) -> str:
        """Human-readable name for this domain."""
        return CONST_DASHBOARD_DOMAIN_LABELS.get(self.domain, self.domain.title())

    def compose(self) -> ComposeResult:
        yield Static(loading_banner(self.domain), id=f"{self.domain}-banner")
        with TabbedContent(id="review-views"):
            with TabPane("Findings", id="review-findings"):
                yield DataTable(id="ai-table")
            with TabPane("Sessions", id="review-sessions"):
                yield DataTable(id="review-sessions-table")

    def on_mount(self) -> None:
        """Install the column headers for both views."""
        findings = self.query_one("#ai-table", DataTable)
        findings.cursor_type = "row"
        findings.add_columns(*DOMAIN_COLUMNS[self.domain])

        sessions = self.query_one("#review-sessions-table", DataTable)
        sessions.cursor_type = "row"
        sessions.add_columns(*REVIEW_SESSION_COLUMNS)

    def apply(self, snapshot: DomainSnapshot) -> None:
        """Render a snapshot into the banner, the findings table and the session list."""
        banner, rows = render_domain(snapshot, stale_after=self.stale_after)
        self.query_one(Static).update(banner)

        findings = self.query_one("#ai-table", DataTable)
        findings.clear()
        if rows:
            findings.add_rows(rows)

        sessions = self.query_one("#review-sessions-table", DataTable)
        sessions.clear()
        session_rows = review_session_rows(snapshot)
        if session_rows:
            sessions.add_rows(session_rows)


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
        self._lines: queue.Queue[str | None] = queue.Queue(maxsize=CONST_LOG_STREAM_QUEUE_SIZE)
        self._producer: threading.Thread | None = None

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
        """Consume a line source, redrawing as lines arrive."""
        self._stop.clear()
        self.buffer.clear()
        self._lines = queue.Queue(maxsize=CONST_LOG_STREAM_QUEUE_SIZE)
        self._producer = threading.Thread(
            target=self._produce, args=(source, self._stop, self._lines), daemon=True
        )
        self._producer.start()
        self._consume()

    def stop_stream(self) -> None:
        """Ask the stream to finish."""
        self._stop.set()

    def on_unmount(self) -> None:
        """Stop streaming when the pane goes away.

        The pane owns the stream, so it stops it. Doing this from the application instead
        does not work: by the time the app unmounts, the widget tree has been torn down and
        a query for the pane returns nothing, leaving the consumer spinning and the
        interpreter unable to exit.
        """
        self.stop_stream()

    @staticmethod
    def _produce(
        source: Callable[[], Iterable[str]],
        stop: threading.Event,
        lines: queue.Queue[str | None],
    ) -> None:
        """Read the stream on a daemon thread, handing lines to the consumer.

        A followed log never ends, and the read blocks until the next line arrives -- which
        for a quiet pod may be never. Textual waits for its thread workers on shutdown, so
        doing this read inside the worker meant pressing `q` hung the application until the
        process was killed.

        This thread is a daemon and is never joined: it is blocked in a socket read that
        cannot be interrupted, so the only way to stop waiting for it is not to.
        """
        try:
            for text in source():
                if stop.is_set():
                    break
                # Backpressure rather than dropping. The queue is bounded so a producer
                # faster than the terminal cannot grow it without limit, but discarding
                # here would break the buffer's count of everything the stream produced --
                # the figure the status line reports true position from. Waiting in slices
                # keeps the stop flag observable while the consumer catches up.
                while not stop.is_set():
                    try:
                        lines.put(text, timeout=DEFAULT_LOG_STREAM_POLL_SECONDS)
                        break
                    except queue.Full:
                        continue
        except Exception as exc:
            with contextlib.suppress(queue.Full):
                lines.put_nowait(f"stream ended: {type(exc).__name__}: {exc}")
        with contextlib.suppress(queue.Full):
            # Sentinel: tells the consumer the stream ended rather than merely paused.
            lines.put(None, timeout=DEFAULT_LOG_STREAM_POLL_SECONDS)

    @work(thread=True, group="log-stream", exclusive=True)
    def _consume(self) -> None:
        """Drain produced lines, coalescing redraws as they arrive.

        Waits with a timeout rather than blocking, so the stop flag is observed promptly
        even when the stream is silent, and the worker Textual waits for on shutdown is
        always one that can return.
        """
        last_draw = 0.0
        lines = self._lines
        while not self._stop.is_set():
            try:
                text = lines.get(timeout=DEFAULT_LOG_STREAM_POLL_SECONDS)
            except queue.Empty:
                continue
            if text is None:
                break
            self.buffer.append(text.rstrip("\n"))
            now = time.monotonic()
            if now - last_draw >= self.redraw_interval:
                last_draw = now
                self._schedule_redraw()
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
