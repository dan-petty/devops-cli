# Tasks

## 1. Sparklines, Gauges, and LogQL Highlighter

- [x] 1.1 Write failing tests in `tests/test_ui_sparklines.py` for `render_sparkline`, `render_gauge`, and `LogQLHighlighter`; verify that they fail with `uv run devops ci test tests/test_ui_sparklines.py`
- [x] 1.2 Implement `render_sparkline` and `render_gauge` in `src/devops_cli/ui/sparklines.py` and `LogQLHighlighter` in `src/devops_cli/ui/highlighters.py`; verify that they pass with `uv run devops ci test tests/test_ui_sparklines.py`

## 2. Trace Waterfall Modal

- [x] 2.1 Write failing tests in `tests/test_ui_waterfall_modal.py` for `TraceWaterfallModal` rendering span trees, waterfall heatmap bars, and dismiss behavior; verify that they fail with `uv run devops ci test tests/test_ui_waterfall_modal.py`
- [x] 2.2 Implement `TraceWaterfallModal` in `src/devops_cli/ui/waterfall_modal.py`; verify that they pass with `uv run devops ci test tests/test_ui_waterfall_modal.py`

## 3. TelemetryPanel and Dashboard Integration

- [x] 3.1 Write failing tests in `tests/test_ui_telemetry_panel.py` and update `tests/test_ui_dashboard.py` for `TelemetryPanel` composition, LogQL input execution, sparklines rendering, and waterfall modal invocation; verify that they fail with `uv run devops ci test tests/test_ui_telemetry_panel.py tests/test_ui_dashboard.py`
- [x] 3.2 Implement `TelemetryPanel` in `src/devops_cli/ui/widgets.py`, wire it in `src/devops_cli/ui/dashboard.py`, and update telemetry models in `src/devops_cli/ui/data_providers.py`; verify that they pass with `uv run devops ci test tests/test_ui_telemetry_panel.py tests/test_ui_dashboard.py`
- [x] 3.3 Regenerate documentation with `uv run devops docs generate --sync-readme` and verify with `uv run devops docs check` and `uv run devops openspec check`

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
