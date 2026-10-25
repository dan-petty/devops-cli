# Proposal

## Why

Issue #691: the workstation dashboard has a Telemetry tab that displays only a table of metric names and counts. Operators must leave the terminal dashboard to run LogQL log queries in Loki or inspect distributed trace waterfalls in Tempo. The terminal user interface needs to unify the observability triad of logs, metrics, and traces directly inside the `tab-telemetry` view.

## What Changes

- Embed a centralized Loki LogQL query console in the `tab-telemetry` panel with syntax highlighting and a live streaming log viewer.
- Render real-time ASCII sparklines and gauges for command execution latencies, LLM token throughput, and cache hit ratios.
- Add a trace waterfall modal screen that visualizes OpenTelemetry distributed traces and review spans with relative offset and latency heatmaps.
- Update `devops_cli.ui.dashboard.DashboardApp` to route `tab-telemetry` focus to the LogQL input bar and bind the `w` key to open the trace waterfall modal.
- The change alters interactive terminal dashboard behavior, so it carries a spec delta for `telemetry-dashboard`.
- The change fits one pull request.

## Capabilities

### New Capabilities

- `telemetry-dashboard`: Interactive terminal UI telemetry dashboard (`tab-telemetry`) that renders Prometheus performance sparklines and gauges, executes LogQL queries against Loki with live log streaming, and displays OpenTelemetry trace waterfalls.

### Modified Capabilities

None.

## Impact

- `src/devops_cli/ui/widgets.py`: Add `TelemetryPanel` with LogQL query input, streaming log pane, sparkline widgets, and recent trace table.
- `src/devops_cli/ui/waterfall_modal.py`: Add `TraceWaterfallModal` modal screen to render trace span waterfall trees and heatmap bars.
- `src/devops_cli/ui/sparklines.py`: Add ASCII sparkline and gauge renderers.
- `src/devops_cli/ui/highlighters.py`: Add `LogQLHighlighter` for syntax highlighting LogQL query expressions.
- `src/devops_cli/ui/dashboard.py`: Register `TelemetryPanel` in `_PANELS` and wire focus handling and trace waterfall shortcut keys.
- `src/devops_cli/ui/data_providers.py`: Extend `TelemetrySummary` and `fetch_telemetry_status` to include performance metric samples and recent trace summaries.

## Feasibility

- Loki querying is implemented in `src/devops_cli/k8s/logql.py:413` via `execute_logql_query`, which connects to `/loki/api/v1/query_range` and falls back to kubectl logs.
- Textual 2.1.2 `Input` widget accepts a `highlighter` instance of `rich.highlighter.RegexHighlighter`, enabling syntax highlighting for LogQL tokens.
- OpenTelemetry span trees, relative offsets, and ANSI waterfall bars are implemented in `src/devops_cli/telemetry/tracer.py:438` and `src/devops_cli/telemetry/waterfall.py:24`.
- In-memory spans and metrics are tracked in `src/devops_cli/telemetry/tracer.py` (`_COMPLETED_SPANS_BUFFER`) and `src/devops_cli/telemetry/metrics.py` (`GLOBAL_METRICS`).

## Existing Tool Considered

- Grafana Explore and Tempo web UI provide complete browser-based observability interfaces. Launching a web browser disrupts the terminal workflow and requires external network access. Textual and Rich already provide native terminal rendering components for interactive tables, input boxes, and ANSI styling. Building terminal-native widgets keeps the operator in the terminal and reuses existing logql and waterfall modules.
- Internal code deleted: Replaces the static `DomainPanel` usage for telemetry in `_PANELS` with the dedicated interactive `TelemetryPanel`.
