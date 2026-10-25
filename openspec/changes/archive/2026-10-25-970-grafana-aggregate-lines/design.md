# Design

## Context

Grafana dashboards in `k8s/monitoring/dashboards/` define multi-series breakdown panels for container, pod, node, and service metrics. See proposal.md for motivation.

## Goals / Non-Goals

**Goals:**
- Ensure all aggregate lines (`Total (Sum)` and `Average (Mean)`) accurately wrap the breakdown's displayed queries (`sum(<A>)` and `avg(<A>)`).
- Ensure `Calls in Flight per Deployment` includes both aggregate lines.
- Apply dashed styling and fixed reference colors via `byName` overrides to all aggregate lines.
- Ensure all dashboards pass `devops grafana dashboards lint`.
- Update tests to enforce query expressions and styling overrides across all 14 panels.

**Non-Goals:**
- Modifying breakdown panels in dashboards outside the 14 in-scope panels (e.g. `k8s-views-namespaces.json` or `k8s-views-global.json`).
- Adding PromQL linter rules to enforce aggregate line existence across all dashboards.

## Decisions

### Decision: Wrap refId A queries with `sum()` and `avg()`
Wrap the exact breakdown query from refId A in `sum(...)` and `avg(...)`.
- **Rejected alternative**: Re-deriving metric selectors without grouping (e.g., `avg(rate(container_cpu_usage_seconds_total...))`).
  - *Evidence*: Re-derived container queries average across individual containers rather than pods. In clusters where pods run multiple containers, this undercounts the average pod workload by approximately 17%.
- **Rejected alternative**: Using client-side Grafana transformations to calculate aggregates.
  - *Evidence*: Client-side transformations add browser rendering overhead and do not integrate cleanly with server-side alerting and variable interpolation.

### Decision: Match overrides by display name on the same axis
Apply field overrides matching `Total (Sum)` and `Average (Mean)` using `matcher.id: "byName"` on the primary axis.
- **Rejected alternative**: Assigning `Total (Sum)` to a secondary right axis (`custom.axisPlacement: "right"`).
  - *Evidence*: Secondary axes invite misinterpretation when users compare individual components directly against aggregate totals with mismatched vertical scales.
- **Rejected alternative**: Keeping default `palette-classic` line colors.
  - *Evidence*: Without overrides, reference lines blend visually with metric lines, obscuring the aggregate boundary.

## Risks / Trade-offs

- [Dominant Total Scale] Large sum totals on panels with many series may compress individual component line heights → Mitigated by keeping average lines visible and allowing interactive legend toggling.
- [ConfigMap Annotation Size] Adding overrides and queries increases JSON length in `k8s/monitoring/dashboards/` → Mitigated by verifying ConfigMap sizes remain well within the 262,144-byte limit in `tests/test_k8s_monitoring_dashboards.py`.

## Migration Plan

Changes are applied directly to the dashboard JSON definitions in git. Argo CD synchronizes updated ConfigMaps into the cluster. Grafana automatically reloads the dashboards without requiring manual migration steps.
