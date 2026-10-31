"""Tests for TelemetryPanel interactive widget and dashboard integration."""

from __future__ import annotations

from unittest.mock import patch

from textual.app import App, ComposeResult
from textual.widgets import DataTable, Input, Static

from devops_cli.k8s.logql import LogEntry, LogQueryResult
from devops_cli.ui.data_providers import TelemetrySummary
from devops_cli.ui.state import DomainSnapshot
from devops_cli.ui.waterfall_modal import TraceWaterfallModal
from devops_cli.ui.widgets import LogPane, TelemetryPanel


class DummyTelemetryApp(App[None]):
    """Host application for testing TelemetryPanel."""

    def __init__(self, panel: TelemetryPanel) -> None:
        super().__init__()
        self.panel = panel

    def compose(self) -> ComposeResult:
        yield self.panel


async def test_telemetry_panel_compose_and_snapshot() -> None:
    """TelemetryPanel renders sparklines, LogQL input, and trace table upon snapshot."""
    panel = TelemetryPanel()
    app = DummyTelemetryApp(panel)

    sample_summary = TelemetrySummary(
        counter_count=2,
        gauge_count=1,
        histogram_count=0,
        counters={"requests": 5.0, "errors": 1.0},
        gauges={"queue_depth": 2.0},
        source="Prometheus",
        latency_samples=[10.0, 20.0, 30.0, 40.0, 50.0],
        token_throughput_samples=[100.0, 200.0, 300.0],
        cache_hit_ratio=0.75,
        recent_traces=[
            {
                "trace_id": "1234567890abcdef1234567890abcdef",
                "root_name": "ai.chat",
                "duration_ms": 150.0,
                "span_count": 4,
                "status": "OK",
            }
        ],
    )

    async with app.run_test() as pilot:
        await pilot.pause()

        # Check components exist
        assert panel.query_one("#logql-query-input", Input) is not None
        assert panel.query_one("#logql-log-pane", LogPane) is not None
        assert panel.query_one("#telemetry-table", DataTable) is not None
        assert panel.query_one("#telemetry-sparklines", Static) is not None

        # Apply snapshot
        panel.apply(DomainSnapshot(domain="telemetry", data=sample_summary))
        await pilot.pause()

        # Check sparklines text content
        sparklines_text = str(panel.query_one("#telemetry-sparklines", Static).content)
        assert "Command Latency" in sparklines_text
        assert "Token Throughput" in sparklines_text
        assert "Cache Hit Ratio" in sparklines_text
        assert "75.0%" in sparklines_text

        # Check metrics table content
        table = panel.query_one("#telemetry-table", DataTable)
        assert table.row_count == 3


async def test_telemetry_panel_logql_query_submission() -> None:
    """Submitting a LogQL query triggers log stream in LogPane."""
    panel = TelemetryPanel()
    app = DummyTelemetryApp(panel)

    mock_result = LogQueryResult(
        query='{app="gateway"} |= "initialized"',
        entries=[
            LogEntry(
                timestamp="2026-10-25T12:00:00Z",
                line="service initialized successfully",
                stream_labels={"app": "gateway"},
            )
        ],
        source="loki",
    )

    async with app.run_test() as pilot:
        await pilot.pause()

        with patch(
            "devops_cli.ui.widgets.execute_logql_query", return_value=mock_result
        ) as mock_exec:
            input_widget = panel.query_one("#logql-query-input", Input)
            input_widget.value = '{app="gateway"} |= "initialized"'
            await pilot.press("enter")
            await pilot.pause()

            mock_exec.assert_called()
            log_pane = panel.query_one("#logql-log-pane", LogPane)
            assert '{app="gateway"}' in log_pane.title
            log_pane._close_source()


async def test_telemetry_panel_opens_waterfall_modal() -> None:
    """Pressing 'w' shortcut or selecting a trace row opens TraceWaterfallModal."""
    panel = TelemetryPanel()
    app = DummyTelemetryApp(panel)

    sample_summary = TelemetrySummary(
        recent_traces=[
            {
                "trace_id": "abcdef1234567890abcdef1234567890",
                "root_name": "review.run",
                "duration_ms": 250.0,
                "span_count": 1,
                "status": "OK",
                "spans": [
                    {
                        "traceId": "abcdef1234567890abcdef1234567890",
                        "spanId": "1111222233334444",
                        "name": "review.run",
                        "startTimeUnixNano": "1000000000000000000",
                        "endTimeUnixNano": "1000000000250000000",
                        "status": {"code": "STATUS_CODE_OK"},
                    }
                ],
            }
        ]
    )

    async with app.run_test() as pilot:
        await pilot.pause()
        panel.apply(DomainSnapshot(domain="telemetry", data=sample_summary))
        await pilot.pause()

        # Focus table and press 'w' to open waterfall modal
        table = panel.query_one("#telemetry-table", DataTable)
        app.set_focus(table)
        await pilot.pause()
        await pilot.press("w")
        await pilot.pause()

        assert any(isinstance(s, TraceWaterfallModal) for s in app.screen_stack)
