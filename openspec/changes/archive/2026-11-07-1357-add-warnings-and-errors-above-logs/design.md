# Design

## Context

`sre-service.json` provides unified performance and log telemetry for services in Kubernetes namespaces. Loki streams lack an indexed `level` label for pod logs, but Loki's `discover_log_levels` populates `detected_level` as structured metadata. Pod logs also carry `pod` in structured metadata rather than as an indexed label.

## Goals / Non-Goals

**Goals:**
- Provide a dedicated top log panel displaying warning and error lines over the full query time range.
- Keep the existing live log panel below it showing all log lines.
- Fix pod filtering so selecting a pod does not blank either log panel.
- Pin `discover_log_levels: true` in `loki-values.yaml` to ensure level detection remains active across chart upgrades.

**Non-Goals:**
- Do not implement client-side browser log filtering (`showControls`), which only filters the 1,000 lines already retrieved.
- Do not filter on the indexed `level` label, which drops pod logs.
- Do not alter service variable scoping or flamegraph queries (handled by separate issues).

## Decisions

- **Decision: Filter on `detected_level` structured metadata with case-insensitive regex.**
  *Choice:* `{namespace=~"$namespace"} | pod=~"$pod" | detected_level=~"(?i)(warn|warning|error|err|critical|fatal|panic)"`.
  *Rejected alternative:* Filter on indexed `level` label. Pod-log streams do not have an indexed `level` label; filtering on `level` matches only Kubernetes events and drops pod warnings/errors.
  *Rejected alternative:* Case-sensitive regex without `(?i)`. Drops Kubernetes `Warning` events.

- **Decision: Separate panels instead of browser-side controls.**
  *Choice:* Two full-width panels: *Warnings & Errors (Loki)* (h=8, y=39) on top, and *Live Service Logs (Loki)* (h=12, y=47) below.
  *Rejected alternative:* Rely on Grafana `showControls`. That only filters lines within the 1,000-line datasource limit in the browser, losing older warnings in the requested range.

- **Decision: Move `pod=~"$pod"` from stream selector to filter stage.**
  *Choice:* `{namespace=~"$namespace"} | pod=~"$pod"`.
  *Rejected alternative:* Keep `pod=~"$pod"` inside `{...}` stream selector. Pod-log streams carry `pod` as structured metadata; querying `{namespace=~"...", pod=~"..."}` yields 0 results when a specific pod is selected.

- **Decision: Pin `discover_log_levels: true` in `loki-values.yaml`.**
  *Choice:* Explicitly declare `discover_log_levels: true` under `loki.limits_config`.
  *Rejected alternative:* Rely on chart default. A future chart or configuration upgrade could change or disable defaults silently.

## Risks / Trade-offs

- The new panel adds an additional query on dashboard refresh (every 10s). Because it targets warning/error lines using structured metadata filters, query execution is lightweight.
