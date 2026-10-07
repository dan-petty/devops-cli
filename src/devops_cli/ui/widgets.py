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
from typing import Any, ClassVar, Protocol, runtime_checkable

from textual import work
from textual.app import ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.css.query import NoMatches
from textual.widgets import DataTable, Input, Select, Static, TabbedContent, TabPane

from devops_cli.config.constants import (
    CONST_DASHBOARD_DOMAIN_AI,
    CONST_DASHBOARD_DOMAIN_DOCKER,
    CONST_DASHBOARD_DOMAIN_K8S,
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
from devops_cli.models.k8s import PodInfo
from devops_cli.output import Text
from devops_cli.ui.log_buffer import VirtualLogBuffer
from devops_cli.ui.pod_inspector import PodInspector
from devops_cli.ui.projections import (
    CONST_FINDING_DETAIL_EMPTY,
    CONST_K8S_ALL_NAMESPACES,
    CONST_K8S_ALL_NAMESPACES_LABEL,
    DOCKER_RESOURCE_COLUMNS,
    DOMAIN_COLUMNS,
    REVIEW_SESSION_COLUMNS,
    docker_resource_keys,
    docker_resource_label,
    docker_resource_rows,
    filter_pods,
    finding_detail,
    finding_records,
    k8s_filter_banner,
    k8s_pod_row,
    loading_banner,
    namespace_choices,
    render_banner,
    render_domain,
    render_keys,
    review_session_keys,
    review_session_rows,
)
from devops_cli.ui.state import DomainSnapshot


def _highlighted_key(table: DataTable[Any]) -> str | None:
    """Return the key of the row under the cursor, or None when the table is empty."""
    if not table.row_count:
        return None
    return table.coordinate_to_cell_key(table.cursor_coordinate).row_key.value


def _body_rows_shown(table: DataTable[Any]) -> int:
    """Count the rows a table shows below its header; none while it is not displayed.

    The dashboard's rows are one line high, so a row's index is its line in the body.
    """
    header = table.header_height if table.show_header else 0
    return max(0, table.scrollable_content_region.height - header)


def _offset_showing(row: int, scroll_y: float, shown: int) -> float:
    """Return the offset nearest `scroll_y` whose window of `shown` rows includes `row`."""
    return min(max(scroll_y, row - shown + 1), row)


def redraw_table(
    table: DataTable[Any],
    rows: list[tuple[str, ...]],
    keys: list[str],
    *,
    keep_place: bool = True,
) -> None:
    """Replace a table's rows, keeping the operator's place unless told to start over.

    `DataTable.clear` puts the cursor on the first row and scrolls to the top, so redrawing
    every table on each refresh tick sent the operator back to row one every few seconds.
    The cursor returns to the row with the same key or, when that record is gone, stays at
    its index on the shorter table. Both scroll offsets are restored after the next
    refresh: moving the cursor schedules its own scroll into view, which would otherwise
    undo them, and a table narrower than its columns is read scrolled to the right.

    A highlighted row that was on screen stays on screen: when a filter or new rows above
    it move it out of the old window, the view scrolls the least distance that shows it.
    One the operator had scrolled away from is left where it is.
    """
    key, index = _highlighted_key(table), table.cursor_row
    scroll_x, scroll_y = table.scroll_x, table.scroll_y
    shown = _body_rows_shown(table)
    on_screen = scroll_y <= index < scroll_y + shown
    table.clear()
    for row_key, cells in zip(keys, rows, strict=True):
        table.add_row(*cells, key=row_key)
    if not (keep_place and table.row_count):
        return
    restored = table.get_row_index(key) if key is not None and key in table.rows else index
    restored = min(restored, table.row_count - 1)
    table.move_cursor(row=restored, scroll=False)
    if on_screen:
        scroll_y = _offset_showing(restored, scroll_y, shown)
    table.call_after_refresh(table.scroll_to, x=scroll_x, y=scroll_y, animate=False)


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
        self._pending_snapshot: DomainSnapshot | None = None

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
        if self._pending_snapshot is not None:
            snapshot = self._pending_snapshot
            self._pending_snapshot = None
            self.apply(snapshot)

    def apply(self, snapshot: DomainSnapshot) -> None:
        """Render a snapshot into the banner and table.

        Called from the UI thread only; workers hand snapshots across via the app.
        """
        if not self.is_mounted:
            self._pending_snapshot = snapshot
            return
        try:
            banner, rows = render_domain(snapshot, stale_after=self.stale_after)
            self.query_one(Static).update(banner)
            redraw_table(self.query_one(DataTable), rows, render_keys(snapshot))
            self._pending_snapshot = None
        except NoMatches:
            self._pending_snapshot = snapshot


__all__ = ["DockerPanel", "DomainPanel", "K8sPanel", "LogPane", "ReviewPanel", "redraw_table"]


class K8sPanel(Vertical):
    """The Kubernetes domain: a banner, a namespace selector and text filter, and the pods.

    Both filters are applied to every snapshot, so a refresh never undoes them, and the
    table is redrawn by pod key, so the cursor stays on its pod. The panel keeps each
    listed pod's record, so opening its logs or inspecting it needs no further lookup.
    """

    # Hidden from the footer, which already truncates; the help screen lists them. Bound
    # here, so they act only while focus is inside the Kubernetes tab.
    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("slash", "focus_filter", "Filter pods", show=False),
        Binding("e", "inspect", "Inspect pod", show=False),
        Binding("escape", "clear_filter", "Clear filter", show=False),
    ]

    DEFAULT_CSS = """
    K8sPanel {
        height: 1fr;
    }
    K8sPanel > Static {
        padding: 0 1;
        margin-bottom: 1;
        background: $boost;
        color: $text;
    }
    K8sPanel #k8s-filters {
        height: auto;
    }
    K8sPanel #k8s-namespace {
        width: 32;
    }
    K8sPanel #k8s-filter {
        width: 1fr;
    }
    K8sPanel > DataTable {
        height: 1fr;
    }
    """

    def __init__(
        self, domain: str = CONST_DASHBOARD_DOMAIN_K8S, *, stale_after: float | None = None
    ) -> None:
        super().__init__(id=f"panel-{domain}")
        self.domain = domain
        self.stale_after = stale_after
        self._snapshot = DomainSnapshot(domain=domain)
        # Every pod in the last snapshot by row key, and the subset the filters list.
        self._pods: dict[str, PodInfo] = {}
        self._shown: dict[str, PodInfo] = {}
        # The namespaces the selector offers. The chosen one is read from the selector
        # itself, so a choice made while a refresh is queued is never overwritten.
        self._namespaces: tuple[str, ...] = ()
        self._pending_snapshot: DomainSnapshot | None = None

    @property
    def label(self) -> str:
        """Human-readable name for this domain."""
        return CONST_DASHBOARD_DOMAIN_LABELS.get(self.domain, self.domain.title())

    def compose(self) -> ComposeResult:
        yield Static(loading_banner(self.domain), id=f"{self.domain}-banner")
        yield Horizontal(
            Select(
                [(CONST_K8S_ALL_NAMESPACES_LABEL, CONST_K8S_ALL_NAMESPACES)],
                value=CONST_K8S_ALL_NAMESPACES,
                allow_blank=False,
                id="k8s-namespace",
            ),
            Input(placeholder="/ filter by namespace, name or status", id="k8s-filter"),
            id="k8s-filters",
        )
        yield DataTable(id=f"{self.domain}-table")

    def on_mount(self) -> None:
        """Install the column headers."""
        table = self._table()
        table.cursor_type = "row"
        table.add_columns(*DOMAIN_COLUMNS[self.domain])
        if self._pending_snapshot is not None:
            snapshot = self._pending_snapshot
            self._pending_snapshot = None
            self.apply(snapshot)

    def _table(self) -> DataTable[Any]:
        return self.query_one(f"#{self.domain}-table", DataTable)

    def _select(self) -> Select[str]:
        return self.query_one("#k8s-namespace", Select)

    def _namespace(self) -> str:
        """Return the chosen namespace, or the empty string for all of them."""
        value = self._select().value
        return value if isinstance(value, str) else CONST_K8S_ALL_NAMESPACES

    def apply(self, snapshot: DomainSnapshot) -> None:
        """Render a snapshot through the current filters.

        Called from the UI thread only; workers hand snapshots across via the app.
        """
        if not self.is_mounted:
            self._pending_snapshot = snapshot
            return
        try:
            self._snapshot = snapshot
            pods = snapshot.data.pods if snapshot.data is not None else []
            self._pods = dict(zip(render_keys(snapshot), pods, strict=True))
            self._offer_namespaces()
            self._redraw()
            self._pending_snapshot = None
        except NoMatches:
            self._pending_snapshot = snapshot

    def _offer_namespaces(self) -> None:
        """Offer the namespaces in the snapshot, keeping the one chosen.

        Replacing a Select's options resets its selection, so they are replaced only when
        the namespaces change, and the choice is put back at once.
        """
        chosen = self._namespace()
        choices = namespace_choices(self._pods.values(), chosen)
        if choices == self._namespaces:
            return
        self._namespaces = choices
        select = self._select()
        select.set_options(
            [
                (CONST_K8S_ALL_NAMESPACES_LABEL, CONST_K8S_ALL_NAMESPACES),
                *((namespace, namespace) for namespace in choices),
            ]
        )
        select.value = chosen

    def _redraw(self) -> None:
        """Redraw the banner and the pods the filters leave listed."""
        namespace, text = self._namespace(), self.query_one("#k8s-filter", Input).value
        self._shown = filter_pods(self._pods, namespace, text)
        banner = render_banner(self._snapshot, stale_after=self.stale_after)
        if namespace != CONST_K8S_ALL_NAMESPACES or text.strip():
            banner = k8s_filter_banner(banner, len(self._shown), len(self._pods))
        self.query_one(f"#{self.domain}-banner", Static).update(banner)
        rows = [k8s_pod_row(pod) for pod in self._shown.values()]
        redraw_table(self._table(), rows, list(self._shown))

    def pod_for(self, row_key: str | None) -> PodInfo | None:
        """Return the pod a listed row shows, if it is still listed and has a name.

        A record read from an object without a name cannot be tailed or inspected: the
        API would be asked for pod ''.
        """
        pod = self._shown.get(row_key) if row_key is not None else None
        return pod if pod is not None and pod.name else None

    def on_select_changed(self, event: Select.Changed) -> None:
        """Apply a namespace choice.

        The choice is read from the selector, not the message: restoring it after new
        options posts a change to the reset value first, which is stale by now.
        """
        self._redraw()

    def on_input_changed(self, event: Input.Changed) -> None:
        """Apply the text filter as it is typed."""
        self._redraw()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Enter in the filter box hands the arrow keys back to the pods."""
        self._table().focus()

    def action_focus_filter(self) -> None:
        """Move to the text filter."""
        self.query_one("#k8s-filter", Input).focus()

    def action_clear_filter(self) -> None:
        """Clear the text filter and return to the pods."""
        self.query_one("#k8s-filter", Input).value = ""
        self._table().focus()

    def action_inspect(self) -> None:
        """Open the inspector on the highlighted pod."""
        pod = self.pod_for(_highlighted_key(self._table()))
        if pod is not None:
            self.app.push_screen(PodInspector(pod))


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
        self._pending_snapshot: DomainSnapshot | None = None

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
        if self._pending_snapshot is not None:
            snapshot = self._pending_snapshot
            self._pending_snapshot = None
            self.apply(snapshot)

    @staticmethod
    def _table_id(resource: str) -> str:
        """Return the table id for a resource view."""
        if resource == CONST_DOCKER_RESOURCE_CONTAINERS:
            return "docker-table"
        return f"docker-{resource}-table"

    def apply(self, snapshot: DomainSnapshot) -> None:
        """Render a snapshot into the banner and every resource table."""
        if not self.is_mounted:
            self._pending_snapshot = snapshot
            return
        try:
            self.query_one(Static).update(render_banner(snapshot, stale_after=self.stale_after))
            tabs = self.query_one("#docker-resources", TabbedContent)
            for resource in CONST_DOCKER_RESOURCES:
                redraw_table(
                    self.query_one(f"#{self._table_id(resource)}", DataTable),
                    docker_resource_rows(resource, snapshot),
                    docker_resource_keys(resource, snapshot),
                )
                # The count rides on the tab label so it is readable without opening the tab.
                with contextlib.suppress(Exception):
                    tabs.get_tab(f"docker-{resource}").label = docker_resource_label(
                        resource, snapshot
                    )
            self._pending_snapshot = None
        except NoMatches:
            self._pending_snapshot = snapshot


class ReviewPanel(Vertical):
    """The AI review domain: findings for one session, plus a session picker.

    The session shown defaults to the newest completed one, and the picker lists every
    session newest-first so an earlier review can be opened without leaving the dashboard.
    Beside the findings table, a detail pane shows the whole record of the highlighted
    finding, whose text the table's four columns have no room for.
    """

    # Hidden from the footer, which already truncates; the help screen lists it. Bound
    # here, so it acts only while focus is inside AI Review.
    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("i", "toggle_detail", "Finding detail", show=False)
    ]

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
    ReviewPanel #review-findings-split {
        height: 1fr;
    }
    ReviewPanel #ai-table {
        width: 3fr;
    }
    ReviewPanel #finding-detail-pane {
        width: 2fr;
        height: 1fr;
        border-left: solid $primary;
    }
    ReviewPanel #finding-detail {
        padding: 0 1;
    }
    """

    def __init__(
        self, domain: str = CONST_DASHBOARD_DOMAIN_AI, *, stale_after: float | None = None
    ) -> None:
        super().__init__(id=f"panel-{domain}")
        self.domain = domain
        self.stale_after = stale_after
        # The session the findings table last showed, and its findings by row key. A
        # highlight is resolved against these, so one queued before a refresh cannot
        # show a finding the table no longer holds.
        self._session_name: str | None = None
        self._findings: dict[str, dict[str, Any]] = {}
        # The session and row key the detail pane last showed. Another finding is read
        # from its header down; the same one, shown again by a refresh, keeps its offset.
        self._shown: tuple[str | None, str | None] = (None, None)
        self._pending_snapshot: DomainSnapshot | None = None

    @property
    def label(self) -> str:
        """Human-readable name for this domain."""
        return CONST_DASHBOARD_DOMAIN_LABELS.get(self.domain, self.domain.title())

    def compose(self) -> ComposeResult:
        yield Static(loading_banner(self.domain), id=f"{self.domain}-banner")
        with TabbedContent(id="review-views"):
            with TabPane("Findings", id="review-findings"):
                yield self._findings_split()
            with TabPane("Sessions", id="review-sessions"):
                yield DataTable(id="review-sessions-table")

    @staticmethod
    def _findings_split() -> Horizontal:
        """Lay the findings table beside the pane that details its highlighted row.

        Finding text is model output quoting repository content, so the pane shows it
        literally rather than interpreting it as markup.
        """
        return Horizontal(
            DataTable(id="ai-table"),
            VerticalScroll(
                Static(CONST_FINDING_DETAIL_EMPTY, id="finding-detail", markup=False),
                id="finding-detail-pane",
            ),
            id="review-findings-split",
        )

    def on_mount(self) -> None:
        """Install the column headers for both views."""
        findings = self.query_one("#ai-table", DataTable)
        findings.cursor_type = "row"
        findings.add_columns(*DOMAIN_COLUMNS[self.domain])

        sessions = self.query_one("#review-sessions-table", DataTable)
        sessions.cursor_type = "row"
        sessions.add_columns(*REVIEW_SESSION_COLUMNS)

        if self._pending_snapshot is not None:
            snapshot = self._pending_snapshot
            self._pending_snapshot = None
            self.apply(snapshot)

    def apply(self, snapshot: DomainSnapshot) -> None:
        """Render a snapshot into the banner, the findings table and the session list.

        The findings table keeps its place across refreshes of one session. A different
        session starts at the top: its row 37 has nothing to do with the last one's.
        """
        if not self.is_mounted:
            self._pending_snapshot = snapshot
            return
        try:
            banner, rows = render_domain(snapshot, stale_after=self.stale_after)
            self.query_one(f"#{self.domain}-banner", Static).update(banner)

            session_name = snapshot.data.session_name if snapshot.data is not None else None
            findings = self.query_one("#ai-table", DataTable)
            keys = render_keys(snapshot)
            self._findings = finding_records(snapshot, keys)
            redraw_table(findings, rows, keys, keep_place=session_name == self._session_name)
            self._session_name = session_name
            self._show_finding(_highlighted_key(findings))

            redraw_table(
                self.query_one("#review-sessions-table", DataTable),
                review_session_rows(snapshot),
                review_session_keys(snapshot),
            )
            self._pending_snapshot = None
        except NoMatches:
            self._pending_snapshot = snapshot

    def _show_finding(self, row_key: str | None) -> None:
        """Show the finding a findings row holds, or say that none is selected."""
        record = self._findings.get(row_key) if row_key is not None else None
        detail = finding_detail(record) if record is not None else CONST_FINDING_DETAIL_EMPTY
        self.query_one("#finding-detail", Static).update(detail)
        shown = (self._session_name, row_key)
        if shown != self._shown:
            self._shown = shown
            # At once: Textual otherwise defers the scroll until after the next screen refresh,
            # and the top needs no layout of the new text.
            pane = self.query_one("#finding-detail-pane", VerticalScroll)
            pane.scroll_home(animate=False, immediate=True)

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        """Follow the findings cursor; the session picker's cursor is not a finding."""
        row_key = event.row_key.value
        if event.data_table.id == "ai-table" and row_key in self._findings:
            self._show_finding(row_key)

    def action_toggle_detail(self) -> None:
        """Show or hide the finding detail pane, giving its width back to the table."""
        pane = self.query_one("#finding-detail-pane", VerticalScroll)
        pane.display = not pane.display


@runtime_checkable
class _ClosableSource(Protocol):
    """A log source that can stop a read blocked in its producer, as a pod's can."""

    def close(self) -> None:
        """Stop the stream, from any thread."""


class LogPane(Vertical, can_focus=True):
    """A virtualized log tail bound to a bounded buffer.

    Only the lines currently on screen are rendered, and only the most recent
    ``max_lines`` are retained, so a tail of a busy pod costs a fixed amount of memory and
    a fixed amount of work per frame no matter how long it runs.

    The pane takes focus so its scroll keys reach it: Textual looks for a key's binding
    only on the focused widget and its ancestors.
    """

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("up", "scroll_lines(-1)", "Up", show=False),
        Binding("down", "scroll_lines(1)", "Down", show=False),
        Binding("pageup", "scroll_pages(-1)", "Page Up", show=False),
        Binding("pagedown", "scroll_pages(1)", "Page Down", show=False),
        Binding("end", "follow", "Follow", show=True),
        # The app knows which pod is tailed and how to open its streams.
        Binding("c", "app.next_container", "Next container", show=False),
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
    LogPane:focus > #log-status {
        text-style: bold;
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
        # The current stream's stop flag and queue. Each stream gets its own, so stopping
        # one can never be undone by starting the next.
        self._stop = threading.Event()
        self._lines: queue.Queue[str | None] = queue.Queue(maxsize=CONST_LOG_STREAM_QUEUE_SIZE)
        self._producer: threading.Thread | None = None
        # The current stream's source, closed when the stream is replaced or stopped.
        self._source: Callable[[], Iterable[str]] | None = None
        # Held across a buffer write and the stop check before it, and across stopping a
        # stream and clearing the buffer, so a stopped stream cannot write one more line.
        self._write_lock = threading.Lock()

    def compose(self) -> ComposeResult:
        yield Static("", id="log-status", markup=False)
        yield Static("", id="log-body", markup=False)

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
        self.query_one("#log-body", Static).update(
            Text.from_ansi("\n".join(line.text for line in lines))
        )
        self.query_one("#log-status", Static).update(f"{self.title} — {self.buffer.status()}")

    # -- Streaming ------------------------------------------------------------

    def start_stream(self, source: Callable[[], Iterable[str]]) -> None:
        """Consume a line source, redrawing as lines arrive, in place of any previous one.

        The previous stream is stopped by its own flag, which its producer and consumer
        both watch, so neither reads or writes again once the new stream starts. Its source
        is closed too, when it can be: a producer blocked reading a quiet container sees no
        flag, and would hold its connection and thread until the container wrote again.
        """
        with self._write_lock:
            self._stop.set()
            self.buffer.clear()
        self._close_source()
        self._source = source
        self._stop = threading.Event()
        self._lines = queue.Queue(maxsize=CONST_LOG_STREAM_QUEUE_SIZE)
        self._producer = threading.Thread(
            target=self._produce, args=(source, self._stop, self._lines), daemon=True
        )
        self._producer.start()
        self._consume(self._stop, self._lines)

    def stop_stream(self) -> None:
        """Ask the stream to finish, closing its source if it can be closed."""
        self._stop.set()
        self._close_source()

    def _close_source(self) -> None:
        """Close the current stream's source, once."""
        source, self._source = self._source, None
        if isinstance(source, _ClosableSource):
            source.close()

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

        This thread is a daemon and is never joined: it may be blocked in a socket read
        that only closing its source ends, and a source that cannot be closed leaves it
        blocked, so nothing waits for it. A closed source ends the read with an end of
        stream or an error, and the thread returns.
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

    @work(thread=True, group="log-stream")
    def _consume(self, stop: threading.Event, lines: queue.Queue[str | None]) -> None:
        """Drain one stream's lines, coalescing redraws as they arrive.

        Waits with a timeout rather than blocking, so the stop flag is observed promptly
        even when the stream is silent, and the worker Textual waits for on shutdown is
        always one that can return. Cancelling a thread worker does not stop its thread,
        so the stream's own flag is what ends it.
        """
        last_draw = 0.0
        while not stop.is_set():
            try:
                text = lines.get(timeout=DEFAULT_LOG_STREAM_POLL_SECONDS)
            except queue.Empty:
                continue
            if text is None or not self._append(stop, text):
                break
            now = time.monotonic()
            if now - last_draw >= self.redraw_interval:
                last_draw = now
                self._schedule_redraw()
        # A final redraw guarantees the last lines are shown even if the stream ended
        # inside a coalescing window.
        self._schedule_redraw()

    def _append(self, stop: threading.Event, text: str) -> bool:
        """Add a stream's line to the buffer unless the stream was stopped meanwhile."""
        with self._write_lock:
            if stop.is_set():
                return False
            self.buffer.append(text.rstrip("\n"))
            return True

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
