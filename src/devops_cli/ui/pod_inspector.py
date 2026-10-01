"""The pod inspector: why a pod is unhealthy, without leaving the dashboard.

The table says a pod is in CrashLoopBackOff; the inspector says which container, how it
last ended and what the cluster has reported about it. Its container rows come from the
record the snapshot already holds, so opening it costs one API call: the pod's events,
fetched on a worker thread so the interface never waits on the cluster.
"""

from __future__ import annotations

import contextlib
from collections.abc import Callable
from typing import Any

from textual import work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import DataTable, Label, Static

from devops_cli.models.k8s import PodEventInfo, PodInfo
from devops_cli.ui.data_providers import describe_api_error, fetch_pod_events
from devops_cli.ui.projections import (
    POD_CONTAINER_COLUMNS,
    POD_EVENT_COLUMNS,
    pod_container_rows,
    pod_event_rows,
)


class PodInspector(ModalScreen[None]):
    """A dialog listing one pod's containers and its most recent events."""

    BINDINGS = [Binding("escape", "dismiss", "Close")]

    DEFAULT_CSS = """
    PodInspector {
        align: center middle;
    }
    #pod-inspector {
        padding: 1 2;
        width: 90%;
        height: 90%;
        border: thick $primary;
        background: $surface;
    }
    #pod-inspector Label {
        text-style: bold;
        color: $accent;
    }
    #inspector-containers {
        height: auto;
        max-height: 40%;
        margin-bottom: 1;
    }
    #inspector-events {
        height: 1fr;
    }
    """

    def __init__(self, pod: PodInfo) -> None:
        super().__init__()
        self.pod = pod

    def compose(self) -> ComposeResult:
        with Vertical(id="pod-inspector"):
            yield Label(f"Pod {self.pod.namespace}/{self.pod.name}  (Esc to close)")
            yield Label("Containers")
            yield DataTable(id="inspector-containers", cursor_type="row")
            yield Label("Events")
            yield Static("Loading events…", id="inspector-events-status", markup=False)
            yield DataTable(id="inspector-events", cursor_type="row")

    def on_mount(self) -> None:
        """Fill the containers from the record and start fetching the events."""
        containers = self.query_one("#inspector-containers", DataTable)
        containers.add_columns(*POD_CONTAINER_COLUMNS)
        containers.add_rows(pod_container_rows(self.pod))
        self.query_one("#inspector-events", DataTable).add_columns(*POD_EVENT_COLUMNS)
        self._load_events()

    @work(thread=True, exclusive=True, group="pod-events")
    def _load_events(self) -> None:
        """Fetch the events off the UI thread; a failure is shown, never raised."""
        pod = self.pod
        try:
            events = fetch_pod_events(pod.namespace, pod.name, pod.uid)
        except Exception as exc:
            self._hand_over(self._show_error, describe_api_error(exc))
            return
        self._hand_over(self._show_events, events)

    def _hand_over(self, show: Callable[[Any], None], result: Any) -> None:
        """Pass a result to the UI thread, unless the app closed while it was fetched."""
        with contextlib.suppress(RuntimeError):
            self.app.call_from_thread(show, result)

    def _show_events(self, events: list[PodEventInfo]) -> None:
        """List the events, newest first, or say there are none."""
        if not self.is_attached:
            return
        status = f"{len(events)} most recent, newest first" if events else "No events."
        self.query_one("#inspector-events-status", Static).update(status)
        self.query_one("#inspector-events", DataTable).add_rows(pod_event_rows(events))

    def _show_error(self, message: str) -> None:
        """Say why the events could not be listed. A dialog closed meanwhile shows nothing."""
        if self.is_attached:
            status = self.query_one("#inspector-events-status", Static)
            status.update(f"Events unavailable: {message}")


__all__ = ["PodInspector"]
