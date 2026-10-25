"""Trace waterfall visualization modal screen."""

from __future__ import annotations

from typing import Any, ClassVar

from textual.app import ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import DataTable, Label, Static

from devops_cli.output import Text
from devops_cli.output.formatters.scalars import format_latency
from devops_cli.telemetry.tracer import build_span_waterfall_tree
from devops_cli.telemetry.waterfall import (
    flatten_waterfall_tree,
    render_waterfall_bar,
    resolve_trace_spans,
)

_WATERFALL_COLUMNS = (
    "Span / Subsystem",
    "Duration",
    "Offset",
    "Latency Waterfall Heatmap",
    "Status",
)


class TraceWaterfallModal(ModalScreen[None]):
    """Modal screen displaying an OpenTelemetry trace span waterfall breakdown."""

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("escape", "dismiss", "Close"),
        Binding("enter", "dismiss", "Close"),
    ]

    DEFAULT_CSS = """
    TraceWaterfallModal {
        align: center middle;
    }
    #waterfall-dialog {
        padding: 1 2;
        width: 92%;
        height: 85%;
        border: thick $primary;
        background: $surface;
    }
    #waterfall-title {
        text-style: bold;
        color: $accent;
        margin-bottom: 1;
    }
    #waterfall-status {
        margin-bottom: 1;
    }
    #waterfall-table {
        height: 1fr;
    }
    """

    def __init__(
        self,
        trace_id: str | None = None,
        spans: list[dict[str, Any]] | None = None,
    ) -> None:
        super().__init__()
        self.trace_id = trace_id or "unknown"
        if spans is None:
            resolved_id, resolved_spans = resolve_trace_spans(trace_id)
            self.trace_id = resolved_id
            self._spans = resolved_spans
        else:
            self._spans = spans

    def compose(self) -> ComposeResult:
        with Vertical(id="waterfall-dialog"):
            yield Label("OpenTelemetry Distributed Trace Waterfall", id="waterfall-title")
            yield Static("Resolving trace data...", id="waterfall-status")
            yield DataTable(id="waterfall-table", cursor_type="row")

    def on_mount(self) -> None:
        """Render waterfall span rows into the data table."""
        status_widget = self.query_one("#waterfall-status", Static)
        table = self.query_one("#waterfall-table", DataTable)
        table.add_columns(*_WATERFALL_COLUMNS)

        if not self._spans:
            status_widget.update(f"No spans found for trace {self.trace_id}.")
            return

        tree = build_span_waterfall_tree(self._spans)
        if not tree:
            status_widget.update(f"No valid span tree constructed for trace {self.trace_id}.")
            return

        total_dur_ms = max((n.duration_ms for n in tree), default=0.0)
        status_widget.update(
            Text.from_markup(
                f"Trace ID: [cyan]{self.trace_id}[/cyan] | Spans: {len(self._spans)} | "
                f"Total Latency: [green]{format_latency(total_dur_ms)}[/green]"
            )
        )

        flattened = flatten_waterfall_tree(tree)
        for node, prefix in flattened:
            is_err = "ERROR" in getattr(node, "status_code", "").upper()
            bar_markup = render_waterfall_bar(
                node.relative_offset_pct,
                node.relative_duration_pct,
                is_error=is_err,
            )
            status_markup = "[red]ERROR[/red]" if is_err else "[green]OK[/green]"

            table.add_row(
                Text.from_markup(f"{prefix}[bold]{node.name}[/bold]"),
                Text(format_latency(node.duration_ms)),
                Text(f"{node.relative_offset_pct:.0f}%"),
                Text.from_markup(bar_markup),
                Text.from_markup(status_markup),
            )


__all__ = ["TraceWaterfallModal"]
