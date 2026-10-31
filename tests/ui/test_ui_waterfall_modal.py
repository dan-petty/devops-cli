"""Tests for trace waterfall modal screen."""

from __future__ import annotations

from textual.app import App, ComposeResult
from textual.widgets import DataTable, Static

from devops_cli.ui.waterfall_modal import TraceWaterfallModal


class DummyModalApp(App[None]):
    """Host application for testing the waterfall modal screen."""

    def __init__(self, modal: TraceWaterfallModal) -> None:
        super().__init__()
        self.modal = modal

    def compose(self) -> ComposeResult:
        yield Static("Root App")

    def on_mount(self) -> None:
        self.push_screen(self.modal)


async def test_trace_waterfall_modal_renders_spans() -> None:
    """Waterfall modal builds span tree and populates data table."""
    sample_spans = [
        {
            "traceId": "11112222333344445555666677778888",
            "spanId": "aaaa1111bbbb2222",
            "parentSpanId": None,
            "name": "review.run",
            "startTimeUnixNano": "1000000000000000000",
            "endTimeUnixNano": "1000000000500000000",
            "status": {"code": "STATUS_CODE_OK"},
            "attributes": [{"key": "review.stage", "value": {"stringValue": "all"}}],
        },
        {
            "traceId": "11112222333344445555666677778888",
            "spanId": "cccc3333dddd4444",
            "parentSpanId": "aaaa1111bbbb2222",
            "name": "review.persona_review",
            "startTimeUnixNano": "1000000000100000000",
            "endTimeUnixNano": "1000000000400000000",
            "status": {"code": "STATUS_CODE_OK"},
            "attributes": [{"key": "persona", "value": {"stringValue": "devsecops"}}],
        },
    ]

    modal = TraceWaterfallModal(trace_id="11112222333344445555666677778888", spans=sample_spans)
    app = DummyModalApp(modal)

    async with app.run_test() as pilot:
        await pilot.pause()
        table = modal.query_one("#waterfall-table", DataTable)
        assert table.row_count == 2

        # Dismiss modal via escape
        await pilot.press("escape")
        await pilot.pause()
        assert modal not in app.screen_stack


async def test_trace_waterfall_modal_empty_state() -> None:
    """Waterfall modal handles missing spans gracefully."""
    modal = TraceWaterfallModal(trace_id="00000000000000000000000000000000", spans=[])
    app = DummyModalApp(modal)

    async with app.run_test() as pilot:
        await pilot.pause()
        status_label = modal.query_one("#waterfall-status", Static)
        assert "No spans" in str(status_label.content)
