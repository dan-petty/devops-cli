# Design

## Context

See proposal.md for motivation and problem statement. The dashboard presently renders telemetry via `DomainPanel`, which only shows an instrument count table.

## Goals / Non-Goals

**Goals:**
- Provide a dedicated `TelemetryPanel` for `tab-telemetry`.
- Embed a LogQL input bar with syntax highlighting and streaming log viewer.
- Render ASCII sparklines and progress gauges for command latencies, token throughput, and cache hit ratio.
- Provide a `TraceWaterfallModal` that visualizes OpenTelemetry spans and multi-persona review traces.

**Non-Goals:**
- Implement browser-based dashboards or remote Grafana proxies.
- Add external charting dependencies to the project.

## Decisions

### Decision: Implement `TelemetryPanel` derived from `DomainPanel`
`TelemetryPanel` inherits from `DomainPanel` and registers in `_PANELS` for `CONST_DASHBOARD_DOMAIN_TELEMETRY`. This keeps compatibility with existing tests that construct `DomainPanel("telemetry")`.
- *Rejected Alternative*: Keep generic `DomainPanel`.
  *Evidence*: A generic `DomainPanel` only holds one static table and banner, preventing interactive input or log streaming.

### Decision: Use `RegexHighlighter` for LogQL input highlighting
Textual `Input` accepts a `highlighter` parameter. A `LogQLHighlighter` class highlights strings, operators, braces, tags, and parsers.
- *Rejected Alternative*: Implement a custom text editor widget.
  *Evidence*: Re-implementing text input handling introduces regressions in cursor navigation and key bindings.

### Decision: Compact ASCII sparklines and gauges
Render sparklines with Unicode blocks (` ▂▃▄▅▆▇█`) and gauges with progress blocks (`[████░░░░]`).
- *Rejected Alternative*: Introduce an external terminal plotting library.
  *Evidence*: Open tools such as plotille require adding external dependencies for basic bar rendering that a 20-line helper provides.

### Decision: Trace waterfall visualization in a modal screen
Implement `TraceWaterfallModal` as a `ModalScreen[None]`. The modal reuses `build_span_waterfall_tree`, `flatten_waterfall_tree`, and `render_waterfall_bar`.
- *Rejected Alternative*: Inline the waterfall table in the main panel.
  *Evidence*: The waterfall tree needs horizontal width that conflicts with the simultaneous LogQL log stream and metrics sparklines.

## Risks / Trade-offs

- [Slow Loki or Prometheus network endpoint] → Fetch telemetry asynchronously in worker threads and use bounded timeouts.
- [No traces recorded at startup] → Render an empty state notice prompting the operator to execute commands or reviews.
